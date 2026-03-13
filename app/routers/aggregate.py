"""
Aggregate Router - Handles data aggregation from multiple services
"""
from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import JSONResponse
import httpx
import logging
import asyncio
from typing import Dict, Any, Optional

from app.config import settings, service_urls
from app.http_client import get_http_client
from app.utils.cache import cached, get, set

router = APIRouter()
logger = logging.getLogger(__name__)


async def fetch_from_service(
    service_url: str,
    request: Request,
    service_name: str
) -> Optional[Dict[str, Any]]:
    """
    Fetch data from a backend service using shared HTTP client

    Args:
        service_url: The service endpoint URL
        request: The incoming request
        service_name: Name of the service for logging

    Returns:
        JSON response or None if error
    """
    try:
        if get_http_client() is None:
            logger.error(f"Shared HTTP client not initialized for {service_name}")
            return None

        headers = {
            k: v for k, v in request.headers.items()
            if k.lower() not in ['host', 'content-length']
        }

        response = await get_http_client().get(
            service_url,
            headers=headers,
            cookies=request.cookies
        )

        if response.status_code == 200:
            return response.json()
        else:
            logger.warning(f"{service_name} returned {response.status_code}")
            return None

    except httpx.RequestError as e:
        logger.error(f"Error fetching from {service_name}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching from {service_name}: {e}")
        return None


@router.get("/dashboard")
async def get_dashboard_data(request: Request):
    """
    Aggregate dashboard data from multiple services
    This reduces multiple frontend requests into a single BFF call
    Results are cached for configured TTL
    """
    try:
        # Try to get from cache first
        user_id = getattr(request.state, 'user', {}).get('user_id') if hasattr(request.state, 'user') else None
        cache_key = f"dashboard:{user_id or 'anonymous'}"

        if settings.redis_enabled:
            cached_data = await get(cache_key)
            if cached_data:
                logger.debug("Returning cached dashboard data")
                return JSONResponse(cached_data)

        # Define service endpoints to fetch
        service_endpoints = [
            ("tasks", f"{service_urls.APP_TASKS}"),
            ("projects", f"{service_urls.APP_PROJECTS}"),
            ("goals", f"{service_urls.APP_GOALS}"),
            ("habits", f"{service_urls.APP_HABITS}"),
            ("todos", f"{service_urls.APP_TODOS}"),
            ("user", service_urls.AUTH_ME),
        ]

        # Fetch data from multiple endpoints in parallel
        tasks = [
            fetch_from_service(url, request, name)
            for name, url in service_endpoints
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results and handle errors properly
        response_data = {
            "status": "success",
            "data": {},
            "errors": [],
            "timestamp": asyncio.get_event_loop().time()
        }

        service_names = [name for name, _ in service_endpoints]
        failed_services = []

        for i, (result, service_name) in enumerate(zip(results, service_names)):
            if isinstance(result, Exception):
                # Log the error and mark the service as failed
                logger.error(f"Failed to fetch {service_name}: {result}")
                failed_services.append(service_name)
                response_data["data"][service_name] = None if service_name == "user" else []
            elif result is None:
                # Service returned None (error in fetch_from_service)
                failed_services.append(service_name)
                response_data["data"][service_name] = None if service_name == "user" else []
            else:
                # Success - add the data
                response_data["data"][service_name] = result

        # Add error information if any services failed
        if failed_services:
            response_data["errors"] = [
                f"Failed to fetch data from: {', '.join(failed_services)}"
            ]
            logger.warning(f"Dashboard aggregation partially failed: {failed_services}")

            # If critical services (user) failed, return degraded response
            # Otherwise return success with partial data
            if "user" in failed_services:
                response_data["status"] = "degraded"
            else:
                response_data["status"] = "partial"

        # Cache the result (even partial results can be cached for a shorter time)
        if settings.redis_enabled:
            cache_ttl = settings.cache_ttl_dashboard if response_data["status"] == "success" else 60
            await set(cache_key, response_data, ttl=cache_ttl)

        return JSONResponse(response_data)

    except Exception as e:
        logger.error(f"Error aggregating dashboard data: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to aggregate dashboard data"
        )


@router.get("/timer-dashboard")
async def get_timer_dashboard(request: Request):
    """
    Proxy timer dashboard request to backend service
    The backend already has the complete logic for building timer dashboard payload
    """
    try:
        # Build query string from request parameters
        query_params = dict(request.query_params)
        query_string = "&".join(f"{k}={v}" for k, v in query_params.items())
        url = f"{service_urls.APP_TIMER_DASHBOARD}?{query_string}" if query_string else service_urls.APP_TIMER_DASHBOARD

        # Forward request to backend service
        if get_http_client() is None:
            logger.error("Shared HTTP client not initialized for timer dashboard")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service unavailable"
            )

        headers = {
            k: v for k, v in request.headers.items()
            if k.lower() not in ['host', 'content-length']
        }

        response = await get_http_client().get(
            url,
            headers=headers,
            cookies=request.cookies
        )

        if response.status_code == 200:
            # Return the backend response as-is
            return JSONResponse(
                content=response.json(),
                status_code=response.status_code
            )
        else:
            logger.error(f"Backend timer dashboard returned {response.status_code}: {response.text}")
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Backend service error: {response.status_code}"
            )

    except httpx.RequestError as e:
        logger.error(f"Error fetching timer dashboard from backend: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to reach backend service"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in timer dashboard: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch timer dashboard data"
        )


@router.get("/planner")
async def get_planner_data(request: Request):
    """
    Aggregate planner data
    Combines habits, todos, and goals for the planner view
    """
    try:
        tasks = [
            fetch_from_service(f"{service_urls.APP_HABITS}", request, "habits"),
            fetch_from_service(f"{service_urls.APP_TODOS}", request, "todos"),
            fetch_from_service(f"{service_urls.APP_GOALS}", request, "goals"),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        return JSONResponse({
            "status": "success",
            "data": {
                "habits": results[0] if results[0] else [],
                "todos": results[1] if results[1] else [],
                "goals": results[2] if results[2] else [],
            }
        })

    except Exception as e:
        logger.error(f"Error aggregating planner data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to aggregate planner data"
        )


@router.get("/reports")
async def get_reports_data(request: Request):
    """
    Aggregate reports data
    Combines summary with tasks and projects for reporting
    """
    try:
        tasks = [
            fetch_from_service(service_urls.APP_REPORTS_SUMMARY, request, "summary"),
            fetch_from_service(f"{service_urls.APP_TASKS}", request, "tasks"),
            fetch_from_service(f"{service_urls.APP_PROJECTS}", request, "projects"),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        return JSONResponse({
            "status": "success",
            "data": {
                "summary": results[0] if results[0] else {},
                "tasks": results[1] if results[1] else [],
                "projects": results[2] if results[2] else [],
            }
        })

    except Exception as e:
        logger.error(f"Error aggregating reports data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to aggregate reports data"
        )


@router.get("/overview")
async def get_overview_data(request: Request):
    """
    Get overview data combining multiple sources
    Optimized for the overview page
    """
    try:
        tasks = [
            fetch_from_service(service_urls.AUTH_ME, request, "user"),
            fetch_from_service(f"{service_urls.APP_TASKS}", request, "tasks"),
            fetch_from_service(service_urls.APP_REPORTS_SUMMARY, request, "summary"),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        return JSONResponse({
            "status": "success",
            "data": {
                "user": results[0] if results[0] else None,
                "tasks": results[1] if results[1] else [],
                "summary": results[2] if results[2] else {},
            }
        })

    except Exception as e:
        logger.error(f"Error aggregating overview data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to aggregate overview data"
        )
