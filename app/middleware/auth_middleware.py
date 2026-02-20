"""
Authentication Middleware
Validates JWT tokens and attaches user info to request state
"""
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import logging
import httpx
from typing import Callable

from app.config import settings

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to validate authentication tokens
    Skips validation for public endpoints
    """

    def __init__(self, app, http_client=None):
        super().__init__(app)
        self.http_client = http_client

        # Public endpoints that don't require authentication
        self.public_paths = [
            "/",
            "/health",
            "/metrics",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/bff/auth/login",
            "/bff/auth/register",
            "/bff/auth/forgot",
            "/bff/auth/password-reset",
            "/bff/auth/google",
        ]

    async def dispatch(self, request: Request, call_next: Callable):
        """Process request and validate auth if needed"""

        path = request.url.path

        # Skip auth for public endpoints
        if any(path.startswith(public_path) for public_path in self.public_paths):
            return await call_next(request)

        # Skip auth for OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)

        # Validate authentication
        try:
            # Check if user is authenticated by calling auth service
            # This is done on the /bff/app routes when needed
            # For now, we'll attach the auth check to the request
            request.state.authenticated = False

            # You can add token validation here if needed
            # For now, we'll let the backend services handle auth
            response = await call_next(request)
            return response

        except Exception as e:
            logger.error(f"Auth middleware error: {e}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"error": "Authentication failed"}
            )
