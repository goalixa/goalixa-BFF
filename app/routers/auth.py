"""
Authentication Router - Handles auth-related requests
"""
from fastapi import APIRouter, Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
import httpx
import logging
import time

from app.config import service_urls
from app.http_client import get_http_client
from app.utils.circuit_breaker import get_circuit_breaker, CircuitBreakerOpenError

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize circuit breaker for auth service
auth_service_breaker = get_circuit_breaker(
    "auth-service",
    failure_threshold=5,
    recovery_timeout=30.0
)


def _forward_set_cookie_headers(source_response: httpx.Response, target_response: Response) -> None:
    """
    Forward all Set-Cookie headers from upstream auth response without mutation.
    """
    for cookie_header in source_response.headers.get_list("set-cookie"):
        target_response.headers.append("set-cookie", cookie_header)


async def _forward_auth_request(
    method: str,
    url: str,
    request: Request,
    include_body: bool = True
) -> Response:
    """
    Helper function to forward auth requests using shared HTTP client
    with circuit breaker protection

    Args:
        method: HTTP method
        url: Target URL
        request: Original request
        include_body: Whether to include request body

    Returns:
        Response from auth service
    """
    start_time = time.time()

    async def _do_request():
        # Track in-progress requests
        try:
            from app.main import BACKEND_REQUESTS_IN_PROGRESS
            BACKEND_REQUESTS_IN_PROGRESS.labels(service='auth-service').inc()
        except ImportError:
            pass

        try:
            if get_http_client() is None:
                logger.error("Shared HTTP client not initialized")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Service not properly initialized"
                )

            body = await request.body() if include_body else None

            headers = {
                k: v for k, v in request.headers.items()
                if k.lower() not in ['host', 'content-length'] if not include_body or k.lower() != 'content-length'
            }

            response = await get_http_client().request(
                method=method,
                url=url,
                content=body,
                headers=headers,
                cookies=request.cookies
            )

            # Record metrics
            try:
                from app.utils.metrics import MetricsHelper
                duration = time.time() - start_time
                MetricsHelper.record_backend_request(
                    service='auth-service',
                    method=method,
                    endpoint=url,
                    status_code=response.status_code,
                    duration=duration
                )
            except ImportError:
                pass

            # Parse JSON only if there's content
            response_content = None
            if response.status_code != 204 and response.content:
                try:
                    response_content = response.json()
                except Exception as e:
                    logger.warning(f"Failed to parse response JSON: {e}")
                    response_content = {"raw_content": response.text}

            json_response = JSONResponse(
                status_code=response.status_code,
                content=response_content
            )

            _forward_set_cookie_headers(response, json_response)

            return json_response

        finally:
            # Decrement in-progress requests
            try:
                from app.main import BACKEND_REQUESTS_IN_PROGRESS
                BACKEND_REQUESTS_IN_PROGRESS.labels(service='auth-service').dec()
            except ImportError:
                pass

    try:
        return await auth_service_breaker.call(_do_request)
    except CircuitBreakerOpenError:
        logger.warning("Circuit breaker is open - auth service unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth service temporarily unavailable. Please try again later."
        )


@router.post("/login")
async def login(request: Request):
    """
    Forward login request to auth service
    Handles session cookies and JWT tokens
    """
    try:
        response = await _forward_auth_request("POST", service_urls.AUTH_LOGIN, request)
        logger.info(f"Login request processed: {response.status_code}")
        return response
    except httpx.RequestError as e:
        logger.error(f"Auth service error during login: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable"
        )


@router.post("/register")
async def register(request: Request):
    """Forward registration request to auth service"""
    try:
        response = await _forward_auth_request("POST", service_urls.AUTH_REGISTER, request)
        logger.info(f"Registration request processed: {response.status_code}")
        return response
    except httpx.RequestError as e:
        logger.error(f"Auth service error during registration: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable"
        )


@router.post("/logout")
async def logout(request: Request):
    """Forward logout request to auth service"""
    try:
        response = await _forward_auth_request("POST", service_urls.AUTH_LOGOUT, request)
        logger.info("Logout request processed")
        return response
    except httpx.RequestError as e:
        logger.error(f"Auth service error during logout: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable"
        )


@router.post("/refresh")
async def refresh(request: Request):
    """Forward refresh token request to auth service"""
    try:
        response = await _forward_auth_request("POST", service_urls.AUTH_REFRESH, request)
        logger.info("Token refresh request processed")
        return response
    except httpx.RequestError as e:
        logger.error(f"Auth service error during token refresh: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable"
        )


@router.get("/me")
async def get_current_user(request: Request):
    """Get current authenticated user"""
    try:
        if get_http_client() is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service not properly initialized"
            )

        headers = {
            k: v for k, v in request.headers.items()
            if k.lower() not in ['host']
        }

        auth_response = await get_http_client().get(
            service_urls.AUTH_ME,
            headers=headers,
            cookies=request.cookies
        )

        if auth_response.status_code == 401:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )

        return JSONResponse(
            status_code=auth_response.status_code,
            content=auth_response.json()
        )

    except httpx.RequestError as e:
        logger.error(f"Auth service error getting user: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable"
        )


@router.post("/forgot")
async def forgot_password(request: Request):
    """Forward forgot password request"""
    try:
        return await _forward_auth_request("POST", service_urls.AUTH_FORGOT, request)
    except httpx.RequestError as e:
        logger.error(f"Auth service error during forgot password: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable"
        )


@router.post("/password-reset/request")
async def password_reset_request(request: Request):
    """Forward password reset request"""
    try:
        return await _forward_auth_request("POST", service_urls.AUTH_PASSWORD_RESET_REQUEST, request)
    except httpx.RequestError as e:
        logger.error(f"Auth service error during password reset request: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable"
        )


@router.post("/password-reset/confirm")
async def password_reset_confirm(request: Request):
    """Forward password reset confirmation"""
    try:
        return await _forward_auth_request("POST", service_urls.AUTH_PASSWORD_RESET_CONFIRM, request)
    except httpx.RequestError as e:
        logger.error(f"Auth service error during password reset confirm: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable"
        )


@router.get("/google")
async def google_login():
    """Get Google OAuth URL"""
    try:
        if get_http_client() is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service not properly initialized"
            )

        auth_response = await get_http_client().get(
            service_urls.AUTH_GOOGLE
        )

        return JSONResponse(
            status_code=auth_response.status_code,
            content=auth_response.json()
        )

    except httpx.RequestError as e:
        logger.error(f"Auth service error during Google OAuth: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable"
        )
