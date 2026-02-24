"""
Authentication Middleware
Validates JWT tokens and attaches user info to request state
"""
from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, RedirectResponse
import logging
from typing import Callable, Optional
import jwt
import httpx
import time

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
        start_time = time.time()
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

            # Record successful validation
            try:
                from app.utils.metrics import MetricsHelper
                duration = time.time() - start_time
                MetricsHelper.record_auth_validation('local_jwt', duration, True)
            except ImportError:
                pass

            return payload

        except jwt.ExpiredSignatureError:
            logger.warning("JWT token has expired")
            try:
                from app.utils.metrics import MetricsHelper
                duration = time.time() - start_time
                MetricsHelper.record_auth_validation('local_jwt', duration, False, 'expired_token')
            except ImportError:
                pass
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {e}")
            try:
                from app.utils.metrics import MetricsHelper
                duration = time.time() - start_time
                MetricsHelper.record_auth_validation('local_jwt', duration, False, 'invalid_token')
            except ImportError:
                pass
            return None
        except Exception as e:
            logger.error(f"Error validating JWT token: {e}")
            try:
                from app.utils.metrics import MetricsHelper
                duration = time.time() - start_time
                MetricsHelper.record_auth_validation('local_jwt', duration, False, 'validation_error')
            except ImportError:
                pass
            return None

    async def _validate_with_auth_service(self, request: Request) -> Optional[dict]:
        """
        Validate token by calling auth service's /me endpoint

        Args:
            request: The incoming request

        Returns:
            User data if valid, None otherwise
        """
        start_time = time.time()
        try:
            if get_http_client() is None:
                logger.error("Shared HTTP client not initialized")
                try:
                    from app.utils.metrics import MetricsHelper
                    duration = time.time() - start_time
                    MetricsHelper.record_auth_validation('auth_service', duration, False, 'service_error')
                except ImportError:
                    pass
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
                try:
                    from app.utils.metrics import MetricsHelper
                    duration = time.time() - start_time
                    MetricsHelper.record_auth_validation('auth_service', duration, True)
                except ImportError:
                    pass
                return response.json()
            else:
                try:
                    from app.utils.metrics import MetricsHelper
                    duration = time.time() - start_time
                    MetricsHelper.record_auth_validation('auth_service', duration, False, 'invalid_token')
                except ImportError:
                    pass
                return None

        except httpx.RequestError as e:
            logger.error(f"Error calling auth service for validation: {e}")
            try:
                from app.utils.metrics import MetricsHelper
                duration = time.time() - start_time
                MetricsHelper.record_auth_validation('auth_service', duration, False, 'service_error')
            except ImportError:
                pass
            return None
        except Exception as e:
            logger.error(f"Unexpected error during auth validation: {e}")
            try:
                from app.utils.metrics import MetricsHelper
                duration = time.time() - start_time
                MetricsHelper.record_auth_validation('auth_service', duration, False, 'validation_error')
            except ImportError:
                pass
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
                return self._handle_unauthorized(request, path, call_next)

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
                return self._handle_unauthorized(request, path, call_next, token_expired=True)

            response = await call_next(request)
            return response

        except Exception as e:
            logger.error(f"Auth middleware error: {e}")
            return self._handle_unauthorized(request, path, call_next, error=str(e))

    def _handle_unauthorized(
        self,
        request: Request,
        path: str,
        call_next: Optional[Callable] = None,
        token_expired: bool = False,
        error: Optional[str] = None
    ):
        """
        Handle unauthorized requests

        For API requests (Accept: application/json): Return 401 JSON
        For browser requests: Redirect to login page
        """
        _ = call_next  # Unused parameter (kept for interface consistency)
        _ = error  # Unused parameter (logged elsewhere)

        request.state.authenticated = False
        request.state.user = None

        # Check if this is an API request (expects JSON response)
        accept_header = request.headers.get("Accept", "")
        is_api_request = "application/json" in accept_header or path.startswith("/bff/")
        is_browser_navigation = "text/html" in accept_header

        # For API requests, return 401
        if is_api_request or not is_browser_navigation:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "unauthorized",
                    "message": "Authentication required" if not token_expired else "Session expired. Please login again.",
                    "redirect_url": "/auth/login"
                }
            )

        # For browser navigation, redirect to login
        login_url = "/auth/login"
        logger.info(f"Redirecting unauthenticated browser request to {login_url}")
        return RedirectResponse(
            url=login_url,
            status_code=status.HTTP_302_FOUND
        )
