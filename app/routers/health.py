"""
Health Check Router
"""
from fastapi import APIRouter, HTTPException
import httpx
import logging

from app.config import settings
from app.utils.circuit_breaker import get_circuit_breaker, _circuit_breakers

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


@router.post("/health/circuit-breaker/reset")
async def reset_circuit_breakers():
    """
    Reset all circuit breakers (development only)
    This endpoint allows manually resetting circuit breakers that have opened
    """
    reset_breakers = []

    for name, breaker in _circuit_breakers.items():
        # Store current state before reset
        old_state = breaker.state.value
        old_failures = breaker.failure_count

        # Reset the circuit breaker
        breaker._state = breaker.CircuitState.CLOSED
        breaker._failure_count = 0
        breaker._half_open_calls = 0
        breaker._last_failure_time = None

        reset_breakers.append({
            "name": name,
            "previous_state": old_state,
            "previous_failures": old_failures,
            "new_state": "closed"
        })

        logger.info(f"Circuit breaker '{name}' manually reset")

    return {
        "status": "success",
        "message": "All circuit breakers have been reset",
        "reset_breakers": reset_breakers
    }


@router.get("/health/circuit-breaker/status")
async def get_circuit_breaker_status():
    """
    Get status of all circuit breakers
    """
    breakers_status = []

    for name, breaker in _circuit_breakers.items():
        breakers_status.append({
            "name": name,
            "state": breaker.state.value,
            "failure_count": breaker.failure_count,
            "failure_threshold": breaker.failure_threshold,
            "recovery_timeout": breaker.recovery_timeout,
            "last_failure_time": breaker.last_failure_time
        })

    return {
        "circuit_breakers": breakers_status
    }
