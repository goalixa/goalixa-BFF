"""
Rate Limiting Middleware
Protects against abuse by limiting request rate per client
"""
from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import logging
from typing import Dict, Optional
import time
import hashlib
from collections import defaultdict

from app.config import settings

logger = logging.getLogger(__name__)


class InMemoryRateLimiter:
    """
    In-memory rate limiter using sliding window counter
    For production, consider using Redis for distributed rate limiting
    """

    def __init__(self):
        # Store request timestamps per client
        self.requests: Dict[str, list] = defaultdict(list)

    def _get_client_key(self, request: Request) -> str:
        """
        Generate a unique key for the client
        Uses IP address, or user ID if available
        """
        # Try to get user_id from authenticated request
        if hasattr(request.state, 'user') and request.state.user:
            user_id = request.state.user.get('user_id')
            if user_id:
                return f"user:{user_id}"

        # Fall back to IP address
        # Get real IP from headers if behind proxy
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            ip = forwarded_for.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "unknown"

        # Hash IP for privacy (optional, can be removed for debugging)
        return hashlib.sha256(ip.encode()).hexdigest()[:16]

    def is_allowed(self, request: Request) -> bool:
        """
        Check if request should be allowed based on rate limit

        Args:
            request: The incoming request

        Returns:
            True if allowed, False otherwise
        """
        if not settings.rate_limit_enabled:
            return True

        client_key = self._get_client_key(request)
        current_time = time.time()

        # Get the client's request history
        request_history = self.requests[client_key]

        # Remove old requests outside the time window
        window_start = current_time - settings.rate_limit_period
        self.requests[client_key] = [
            timestamp for timestamp in request_history
            if timestamp > window_start
        ]

        # Check if under limit
        if len(self.requests[client_key]) < settings.rate_limit_requests:
            self.requests[client_key].append(current_time)
            return True

        logger.warning(f"Rate limit exceeded for client: {client_key}")
        return False

    def get_reset_time(self, request: Request) -> float:
        """
        Get the timestamp when the rate limit will reset

        Args:
            request: The incoming request

        Returns:
            Unix timestamp of reset time
        """
        client_key = self._get_client_key(request)
        request_history = self.requests.get(client_key, [])

        if request_history:
            # Reset time is when the oldest request in window expires
            oldest_request = min(request_history)
            return oldest_request + settings.rate_limit_period

        return time.time() + settings.rate_limit_period


# Global rate limiter instance
rate_limiter = InMemoryRateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce rate limiting
    Adds rate limit headers to responses
    """

    # Paths to exclude from rate limiting
    EXCLUDED_PATHS = {
        "/health",
        "/readiness",
        "/liveness",
        "/metrics",
        "/docs",
        "/redoc",
        "/openapi.json",
    }

    def __init__(self, app):
        super().__init__(app)
        self.rate_limiter = rate_limiter

    def _is_excluded_path(self, path: str) -> bool:
        """Check if path should be excluded from rate limiting"""
        return path in self.EXCLUDED_PATHS

    async def dispatch(self, request: Request, call_next):
        """Process request and enforce rate limits"""

        path = request.url.path

        # Skip rate limiting for excluded paths
        if self._is_excluded_path(path):
            return await call_next(request)

        # Check rate limit
        if not self.rate_limiter.is_allowed(request):
            reset_time = self.rate_limiter.get_reset_time(request)

            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Limit is {settings.rate_limit_requests} requests per {settings.rate_limit_period} seconds.",
                    "retry_after": int(reset_time - time.time())
                },
                headers={
                    "Retry-After": str(int(reset_time - time.time())),
                    "X-RateLimit-Limit": str(settings.rate_limit_requests),
                    "X-RateLimit-Window": str(settings.rate_limit_period),
                }
            )

        response = await call_next(request)

        # Add rate limit headers to response
        client_key = self.rate_limiter._get_client_key(request)
        remaining = settings.rate_limit_requests - len(self.rate_limiter.requests.get(client_key, []))

        response.headers["X-RateLimit-Limit"] = str(settings.rate_limit_requests)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
        response.headers["X-RateLimit-Reset"] = str(int(self.rate_limiter.get_reset_time(request)))

        return response
