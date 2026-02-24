"""
Authentication Middleware
Validates JWT tokens and attaches user info to request state
"""
from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import logging
from typing import Callable, Optional
import jwt
import httpx

from app.config import settings
from app.http_client import get_http_client

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to validate authentication tokens
    Skips validation for public endpoints
    Validates JWT tokens locally or calls auth service for validation
    """

    def __init__(self, app, http_client=None):
        super().__init__(app)
        self.http_client = http_client

        # Public endpoints that don't require authentication
        self.public_paths = {
            "/",
            "/health",
            "/readiness",
            "/liveness",
            "/metrics",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/bff/auth/login",
            "/bff/auth/register",
            "/bff/auth/forgot",
            "/bff/auth/password-reset/request",
            "/bff/auth/password-reset/confirm",
            "/bff/auth/google",
            "/bff/auth/refresh",
        }

    def _is_public_path(self, path: str) -> bool:
        """Check if path is public (exact match or starts with public prefix)"""
        if path in self.public_paths:
            return True

        # Check for path prefixes
        public_prefixes = [
            "/bff/auth/login",
            "/bff/auth/register",
            "/bff/auth/forgot",
            "/bff/auth/password-reset",
            "/bff/auth/google",
            "/bff/auth/refresh",
        ]
        return any(path.startswith(prefix) for prefix in public_prefixes)

    async def _validate_jwt_locally(self, token: str) -> Optional[dict]:
        """
        Validate JWT token locally using the JWT secret

        Args:
            token: JWT token string

        Returns:
            Decoded payload if valid, None otherwise
        """
        try:
            # Remove 'Bearer ' prefix if present
            if token.startswith("Bearer "):
                token = token[7:]

            payload = jwt.decode(
                token,
                settings.jwt_secret,
                algorithms=[settings.jwt_algorithm]
            )

            # Only treat access tokens as authenticated user context.
            token_type = payload.get("type")
            if token_type and token_type != "access":
                return None
            return payload

        except jwt.ExpiredSignatureError:
            logger.warning("JWT token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {e}")
            return None
        except Exception as e:
            logger.error(f"Error validating JWT token: {e}")
            return None

    async def _validate_with_auth_service(self, request: Request) -> Optional[dict]:
        """
        Validate token by calling auth service's /me endpoint

        Args:
            request: The incoming request

        Returns:
            User data if valid, None otherwise
        """
        try:
            if get_http_client() is None:
                logger.error("Shared HTTP client not initialized")
                return None

            headers = {
                k: v for k, v in request.headers.items()
                if k.lower() not in ['host']
            }

            response = await get_http_client().get(
                f"{settings.auth_service_url}{settings.auth_api_prefix}/me",
                headers=headers,
                cookies=request.cookies
            )

            if response.status_code == 200:
                return response.json()
            else:
                return None

        except httpx.RequestError as e:
            logger.error(f"Error calling auth service for validation: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during auth validation: {e}")
            return None

    async def _extract_token(self, request: Request) -> Optional[str]:
        """
        Extract JWT token from request (Authorization header or cookie)

        Args:
            request: The incoming request

        Returns:
            Token string if found, None otherwise
        """
        # Try Authorization header first
        auth_header = request.headers.get("Authorization")
        if auth_header:
            return auth_header

        # Try known access-token cookie names
        cookie_candidates = (
            settings.auth_access_cookie_name,
            "access_token",      # legacy fallback
            "goalixa_access",    # explicit fallback for local envs
        )
        for cookie_name in cookie_candidates:
            access_token = request.cookies.get(cookie_name)
            if access_token:
                return f"Bearer {access_token}"

        return None

    async def dispatch(self, request: Request, call_next: Callable):
        """Process request and validate auth if needed"""

        path = request.url.path

        # Skip auth for public endpoints
        if self._is_public_path(path):
            return await call_next(request)

        # Skip auth for OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)

        # Validate authentication
        try:
            # Extract token from request
            token = await self._extract_token(request)

            if not token:
                logger.warning(f"No token found for {path}")
                request.state.authenticated = False
                request.state.user = None
                return await call_next(request)

            # Try to validate JWT locally first (faster)
            user_payload = await self._validate_jwt_locally(token)

            # If local validation fails, try auth service (fallback)
            if user_payload is None:
                user_payload = await self._validate_with_auth_service(request)

            if user_payload:
                # User is authenticated
                request.state.authenticated = True
                request.state.user = user_payload
                logger.debug(f"User authenticated: {user_payload.get('user_id', 'unknown')}")
            else:
                # Authentication failed
                request.state.authenticated = False
                request.state.user = None

            response = await call_next(request)
            return response

        except Exception as e:
            logger.error(f"Auth middleware error: {e}")
            # Continue with request but mark as unauthenticated
            request.state.authenticated = False
            request.state.user = None
            return await call_next(request)
