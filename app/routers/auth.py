"""
Authentication Router - Handles auth-related requests
"""
from fastapi import APIRouter, Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
import httpx
import logging

from app.config import service_urls

router = APIRouter()
logger = logging.getLogger(__name__)


def _forward_set_cookie_headers(source_response: httpx.Response, target_response: JSONResponse) -> None:
    """
    Forward all Set-Cookie headers from upstream auth response without mutation.
    """
    for cookie_header in source_response.headers.get_list("set-cookie"):
        target_response.headers.append("set-cookie", cookie_header)


@router.post("/login")
async def login(request: Request):
    """
    Forward login request to auth service
    Handles session cookies and JWT tokens
    """
    try:
        body = await request.body()

        async with httpx.AsyncClient() as client:
            auth_response = await client.post(
                service_urls.AUTH_LOGIN,
                content=body,
                headers={k: v for k, v in request.headers.items() if k.lower() != 'host'},
                timeout=30.0
            )

        # Forward response with cookies
        response = JSONResponse(
            status_code=auth_response.status_code,
            content=auth_response.json() if auth_response.status_code != 204 else None
        )

        _forward_set_cookie_headers(auth_response, response)

        logger.info(f"Login request processed: {auth_response.status_code}")
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
        body = await request.body()

        async with httpx.AsyncClient() as client:
            auth_response = await client.post(
                service_urls.AUTH_REGISTER,
                content=body,
                headers={k: v for k, v in request.headers.items() if k.lower() != 'host'},
                timeout=30.0
            )

        response = JSONResponse(
            status_code=auth_response.status_code,
            content=auth_response.json() if auth_response.status_code != 204 else None
        )

        _forward_set_cookie_headers(auth_response, response)

        logger.info(f"Registration request processed: {auth_response.status_code}")
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
        body = await request.body()

        async with httpx.AsyncClient() as client:
            auth_response = await client.post(
                service_urls.AUTH_LOGOUT,
                content=body,
                headers={k: v for k, v in request.headers.items()
                        if k.lower() not in ['host', 'content-length']},
                cookies=request.cookies,
                timeout=30.0
            )

        response = JSONResponse(
            status_code=auth_response.status_code,
            content=auth_response.json() if auth_response.status_code != 204 else None
        )

        _forward_set_cookie_headers(auth_response, response)

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
        body = await request.body()

        async with httpx.AsyncClient() as client:
            auth_response = await client.post(
                service_urls.AUTH_REFRESH,
                content=body,
                headers={k: v for k, v in request.headers.items()
                        if k.lower() not in ['host', 'content-length']},
                cookies=request.cookies,
                timeout=30.0
            )

        response = JSONResponse(
            status_code=auth_response.status_code,
            content=auth_response.json() if auth_response.status_code != 204 else None
        )

        _forward_set_cookie_headers(auth_response, response)

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
        async with httpx.AsyncClient() as client:
            auth_response = await client.get(
                service_urls.AUTH_ME,
                headers={k: v for k, v in request.headers.items()
                        if k.lower() not in ['host']},
                cookies=request.cookies,
                timeout=30.0
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
        body = await request.body()

        async with httpx.AsyncClient() as client:
            auth_response = await client.post(
                service_urls.AUTH_FORGOT,
                content=body,
                headers={k: v for k, v in request.headers.items() if k.lower() != 'host'},
                timeout=30.0
            )

        return JSONResponse(
            status_code=auth_response.status_code,
            content=auth_response.json() if auth_response.status_code != 204 else None
        )

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
        body = await request.body()

        async with httpx.AsyncClient() as client:
            auth_response = await client.post(
                service_urls.AUTH_PASSWORD_RESET_REQUEST,
                content=body,
                headers={k: v for k, v in request.headers.items() if k.lower() != 'host'},
                timeout=30.0
            )

        return JSONResponse(
            status_code=auth_response.status_code,
            content=auth_response.json() if auth_response.status_code != 204 else None
        )

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
        body = await request.body()

        async with httpx.AsyncClient() as client:
            auth_response = await client.post(
                service_urls.AUTH_PASSWORD_RESET_CONFIRM,
                content=body,
                headers={k: v for k, v in request.headers.items() if k.lower() != 'host'},
                timeout=30.0
            )

        return JSONResponse(
            status_code=auth_response.status_code,
            content=auth_response.json() if auth_response.status_code != 204 else None
        )

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
        async with httpx.AsyncClient() as client:
            auth_response = await client.get(
                service_urls.AUTH_GOOGLE,
                timeout=30.0
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
