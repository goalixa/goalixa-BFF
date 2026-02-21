"""
App Router - Handles all app-related requests
"""
from fastapi import APIRouter, Request, HTTPException, status, Response
from fastapi.responses import JSONResponse
import httpx
import logging
from typing import Optional

from app.config import settings, service_urls
from app.main import http_client as shared_http_client
from app.utils.circuit_breaker import get_circuit_breaker, CircuitBreakerOpenError

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize circuit breaker for app service
app_service_breaker = get_circuit_breaker(
    "app-service",
    failure_threshold=5,
    recovery_timeout=30.0
)


async def forward_request(
    request: Request,
    service_url: str,
    method: str = None
):
    """
    Generic request forwarding function using shared HTTP client

    Args:
        request: The incoming request
        service_url: The backend service URL
        method: HTTP method (defaults to request method)

    Returns:
        JSONResponse from backend service
    """
    async def _do_request():
        method = method or request.method
        body = await request.body() if method in ["POST", "PUT", "PATCH"] else None

        # Build URL with query parameters
        url = service_url
        if request.url.query:
            url += f"?{request.url.query}"

        # Filter headers - remove host and content-length
        headers = {
            k: v for k, v in request.headers.items()
            if k.lower() not in ['host', 'content-length']
        }

        # Use shared HTTP client from main app
        if shared_http_client is None:
            logger.error("Shared HTTP client not initialized")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service not properly initialized"
            )

        response = await shared_http_client.request(
            method=method,
            url=url,
            content=body,
            headers=headers,
            cookies=request.cookies
        )

        # Handle empty responses
        if response.status_code == 204:
            return Response(status_code=204)

        return JSONResponse(
            status_code=response.status_code,
            content=response.json()
        )

    try:
        # Use circuit breaker for the request
        return await app_service_breaker.call(_do_request)

    except CircuitBreakerOpenError:
        logger.warning("Circuit breaker is open - app service unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="App service temporarily unavailable. Please try again later."
        )
    except httpx.RequestError as e:
        logger.error(f"App service connection error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="App service unavailable"
        )
    except httpx.HTTPStatusError as e:
        logger.error(f"App service returned error status: {e.response.status_code}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=e.response.json() if e.response.headers.get("content-type", "").startswith("application/json") else str(e.response.text)
        )
    except Exception as e:
        logger.error(f"Unexpected error in forward_request: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


async def forward_request(
    request: Request,
    service_url: str,
    method: str = None
):
    """
    Generic request forwarding function

    Args:
        request: The incoming request
        service_url: The backend service URL
        method: HTTP method (defaults to request method)

    Returns:
        JSONResponse from backend service
    """
    try:
        method = method or request.method
        body = await request.body() if method in ["POST", "PUT", "PATCH"] else None

        # Build URL with query parameters
        url = service_url
        if request.url.query:
            url += f"?{request.url.query}"

        # Filter headers
        headers = {
            k: v for k, v in request.headers.items()
            if k.lower() not in ['host', 'content-length']
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            auth_response = await client.request(
                method=method,
                url=url,
                content=body,
                headers=headers,
                cookies=request.cookies
            )

        return JSONResponse(
            status_code=auth_response.status_code,
            content=auth_response.json() if auth_response.status_code != 204 else None
        )

    except httpx.RequestError as e:
        logger.error(f"App service error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="App service unavailable"
        )
    except httpx.HTTPStatusError as e:
        logger.error(f"App service returned error: {e}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=e.response.json()
        )


# ============= TASKS =============

@router.get("/tasks")
async def get_tasks(request: Request):
    """Get all tasks"""
    return await forward_request(request, service_urls.APP_TASKS)


@router.post("/tasks")
async def create_task(request: Request):
    """Create a new task"""
    return await forward_request(request, service_urls.APP_TASKS)


@router.post("/tasks/{task_id}/start")
async def start_task(task_id: str, request: Request):
    """Start a task timer"""
    url = f"{service_urls.APP_TASK_START}/{task_id}/start"
    return await forward_request(request, url)


@router.post("/tasks/{task_id}/stop")
async def stop_task(task_id: str, request: Request):
    """Stop a task timer"""
    url = f"{service_urls.APP_TASK_STOP}/{task_id}/stop"
    return await forward_request(request, url)


@router.post("/tasks/{task_id}/complete")
async def complete_task(task_id: str, request: Request):
    """Mark a task as complete"""
    url = f"{service_urls.APP_TASK_COMPLETE}/{task_id}/complete"
    return await forward_request(request, url)


@router.post("/tasks/{task_id}/delete")
async def delete_task(task_id: str, request: Request):
    """Delete a task"""
    url = f"{service_urls.APP_TASK_DELETE}/{task_id}/delete"
    return await forward_request(request, url)


# ============= PROJECTS =============

@router.get("/projects")
async def get_projects(request: Request):
    """Get all projects"""
    return await forward_request(request, service_urls.APP_PROJECTS)


@router.post("/projects")
async def create_project(request: Request):
    """Create a new project"""
    return await forward_request(request, service_urls.APP_PROJECTS)


@router.post("/projects/{project_id}/delete")
async def delete_project(project_id: str, request: Request):
    """Delete a project"""
    url = f"{service_urls.APP_PROJECT_DELETE}/{project_id}/delete"
    return await forward_request(request, url)


# ============= GOALS =============

@router.get("/goals")
async def get_goals(request: Request):
    """Get all goals"""
    return await forward_request(request, service_urls.APP_GOALS)


@router.post("/goals")
async def create_goal(request: Request):
    """Create a new goal"""
    return await forward_request(request, service_urls.APP_GOALS)


@router.get("/goals/{goal_id}")
async def get_goal(goal_id: str, request: Request):
    """Get goal details"""
    url = f"{service_urls.APP_GOAL_DETAIL}/{goal_id}"
    return await forward_request(request, url)


@router.post("/goals/{goal_id}/edit")
async def edit_goal(goal_id: str, request: Request):
    """Edit a goal"""
    url = f"{service_urls.APP_GOAL_EDIT}/{goal_id}/edit"
    return await forward_request(request, url)


@router.post("/goals/{goal_id}/delete")
async def delete_goal(goal_id: str, request: Request):
    """Delete a goal"""
    url = f"{service_urls.APP_GOAL_DELETE}/{goal_id}/delete"
    return await forward_request(request, url)


@router.post("/goals/subgoals/{subgoal_id}/toggle")
async def toggle_subgoal(subgoal_id: str, request: Request):
    """Toggle subgoal completion"""
    url = f"{service_urls.APP_GOAL_SUBGOALS}/{subgoal_id}/toggle"
    return await forward_request(request, url)


# ============= HABITS =============

@router.get("/habits")
async def get_habits(request: Request):
    """Get all habits"""
    return await forward_request(request, service_urls.APP_HABITS)


@router.post("/habits")
async def create_habit(request: Request):
    """Create a new habit"""
    return await forward_request(request, service_urls.APP_HABITS)


@router.post("/habits/{habit_id}/track")
async def track_habit(habit_id: str, request: Request):
    """Track habit completion"""
    url = f"{service_urls.APP_HABIT_TRACK}/{habit_id}/track"
    return await forward_request(request, url)


# ============= TODOS =============

@router.get("/todos")
async def get_todos(request: Request):
    """Get all todos"""
    return await forward_request(request, service_urls.APP_TODOS)


@router.post("/todos")
async def create_todo(request: Request):
    """Create a new todo"""
    return await forward_request(request, service_urls.APP_TODOS)


# ============= REMINDERS =============

@router.get("/reminders")
async def get_reminders(request: Request):
    """Get all reminders"""
    return await forward_request(request, service_urls.APP_REMINDERS)


@router.post("/reminders")
async def create_reminder(request: Request):
    """Create a new reminder"""
    return await forward_request(request, service_urls.APP_REMINDERS)


# ============= LABELS =============

@router.get("/labels")
async def get_labels(request: Request):
    """Get all labels"""
    return await forward_request(request, service_urls.APP_LABELS)


@router.post("/labels")
async def create_label(request: Request):
    """Create a new label"""
    return await forward_request(request, service_urls.APP_LABELS)


# ============= REPORTS =============

@router.get("/reports/summary")
async def get_reports_summary(request: Request):
    """Get reports summary"""
    return await forward_request(request, service_urls.APP_REPORTS_SUMMARY)


# ============= TIMER =============

@router.get("/timer/entries")
async def get_timer_entries(request: Request):
    """Get timer entries"""
    return await forward_request(request, service_urls.APP_TIMER_ENTRIES)


# ============= SETTINGS =============

@router.get("/settings/profile")
async def get_profile(request: Request):
    """Get user profile"""
    return await forward_request(request, service_urls.APP_SETTINGS_PROFILE)


@router.post("/settings/profile")
async def update_profile(request: Request):
    """Update user profile"""
    return await forward_request(request, service_urls.APP_SETTINGS_PROFILE)


@router.post("/settings/timezone")
async def update_timezone(request: Request):
    """Update user timezone"""
    return await forward_request(request, service_urls.APP_SETTINGS_TIMEZONE)


@router.get("/settings/notifications")
async def get_notification_settings(request: Request):
    """Get notification settings"""
    return await forward_request(request, service_urls.APP_SETTINGS_NOTIFICATIONS)


@router.post("/settings/notifications")
async def update_notification_settings(request: Request):
    """Update notification settings"""
    return await forward_request(request, service_urls.APP_SETTINGS_NOTIFICATIONS)
