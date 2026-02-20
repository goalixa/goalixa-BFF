"""
Health Check Router
"""
from fastapi import APIRouter, HTTPException
import httpx
import logging

from app.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
async def health_check():
    """
    Basic health check endpoint
    Returns service health status
    """
    return {
        "status": "healthy",
        "service": "Goalixa BFF",
        "version": "1.0.0"
    }


@router.get("/readiness")
async def readiness_check():
    """
    Readiness probe - checks if BFF is ready to accept requests
    """
    return {
        "status": "ready",
        "service": "Goalixa BFF"
    }


@router.get("/liveness")
async def liveness_check():
    """
    Liveness probe - checks if BFF is alive
    """
    return {
        "status": "alive",
        "service": "Goalixa BFF"
    }


@router.get("/health/deep")
async def deep_health_check():
    """
    Deep health check - verifies connectivity to backend services
    """
    health_status = {
        "bff": {"status": "healthy"},
        "services": {}
    }

    # Check auth service
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.auth_service_url}/health")
            health_status["services"]["auth"] = {
                "status": "healthy" if response.status_code == 200 else "unhealthy",
                "status_code": response.status_code
            }
    except Exception as e:
        logger.error(f"Auth service health check failed: {e}")
        health_status["services"]["auth"] = {
            "status": "unhealthy",
            "error": str(e)
        }

    # Check app service
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.app_service_url}/health")
            health_status["services"]["app"] = {
                "status": "healthy" if response.status_code == 200 else "unhealthy",
                "status_code": response.status_code
            }
    except Exception as e:
        logger.error(f"App service health check failed: {e}")
        health_status["services"]["app"] = {
            "status": "unhealthy",
            "error": str(e)
        }

    # Overall status
    all_healthy = all(
        s.get("status") == "healthy"
        for s in health_status["services"].values()
    )

    health_status["overall"] = "healthy" if all_healthy else "degraded"

    return health_status
