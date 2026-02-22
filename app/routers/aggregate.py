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
    Results are cached for 60 seconds
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

        # Fetch data from multiple endpoints in parallel
        tasks = [
            fetch_from_service(f"{service_urls.APP_TASKS}", request, "tasks"),
            fetch_from_service(f"{service_urls.APP_PROJECTS}", request, "projects"),
            fetch_from_service(f"{service_urls.APP_GOALS}", request, "goals"),
            fetch_from_service(f"{service_urls.APP_HABITS}", request, "habits"),
            fetch_from_service(f"{service_urls.APP_TODOS}", request, "todos"),
            fetch_from_service(service_urls.AUTH_ME, request, "user"),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        response_data = {
            "status": "success",
            "data": {
                "tasks": results[0] if results[0] else [],
                "projects": results[1] if results[1] else [],
                "goals": results[2] if results[2] else [],
                "habits": results[3] if results[3] else [],
                "todos": results[4] if results[4] else [],
                "user": results[5] if results[5] else None,
                "timestamp": asyncio.get_event_loop().time()
            }
        }

        # Cache the result
        if settings.redis_enabled:
            await set(cache_key, response_data, ttl=60)

        return JSONResponse(response_data)

    except Exception as e:
        logger.error(f"Error aggregating dashboard data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to aggregate dashboard data"
        )


@router.get("/timer-dashboard")
async def get_timer_dashboard(request: Request):
    """
    Aggregate timer-specific data
    Combines active tasks, recent entries, and projects
    """
    try:
        tasks = [
            fetch_from_service(f"{service_urls.APP_TASKS}", request, "tasks"),
            fetch_from_service(f"{service_urls.APP_TIMER_ENTRIES}", request, "timer_entries"),
            fetch_from_service(f"{service_urls.APP_PROJECTS}", request, "projects"),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        return JSONResponse({
            "status": "success",
            "data": {
                "tasks": results[0] if results[0] else [],
                "timer_entries": results[1] if results[1] else [],
                "projects": results[2] if results[2] else [],
            }
        })

    except Exception as e:
        logger.error(f"Error aggregating timer dashboard: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to aggregate timer data"
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
