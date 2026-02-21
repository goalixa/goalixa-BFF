"""
Configuration for BFF Service
"""
from pydantic_settings import BaseSettings
from typing import List
import os


def _normalize_prefix(prefix: str) -> str:
    prefix = (prefix or "").strip()
    if not prefix:
        return ""
    if not prefix.startswith("/"):
        prefix = f"/{prefix}"
    return prefix.rstrip("/")


def _build_service_url(base_url: str, api_prefix: str, path: str) -> str:
    base = (base_url or "").rstrip("/")
    prefix = _normalize_prefix(api_prefix)
    suffix = path if path.startswith("/") else f"/{path}"
    return f"{base}{prefix}{suffix}"


class Settings(BaseSettings):
    """Application settings"""

    # Application
    app_name: str = "BFF Service"
    debug: bool = False
    environment: str = "development"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Backend Services URLs (configure for your environment)
    auth_service_url: str = os.getenv("AUTH_SERVICE_URL", "http://localhost:5001")
    app_service_url: str = os.getenv("APP_SERVICE_URL", "http://localhost:5000")
    auth_api_prefix: str = os.getenv("AUTH_API_PREFIX", "/api")
    app_api_prefix: str = os.getenv("APP_API_PREFIX", "/api")

    # Kubernetes service URLs (example - update with your service names)
    # auth_service_url: str = "http://auth-service.namespace.svc.cluster.local:5001"
    # app_service_url: str = "http://app-service.namespace.svc.cluster.local:80"

    # CORS (update with your frontend domains)
    cors_origins: List[str] = [
        "http://localhost:8080",
        "http://localhost:3000",
    ]

    # JWT Settings (for token validation if needed)
    jwt_secret: str = os.getenv("JWT_SECRET", "your-secret-key")
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # Redis (for caching)
    redis_url: str = "redis://redis.harbor.svc.cluster.local:6379/0"
    redis_enabled: bool = True
    cache_ttl_seconds: int = 300  # 5 minutes default

    # Security
    allowed_hosts: List[str] = ["*"]
    secure_cookies: bool = True
    cookie_domain: str = ".goalixa.com"

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 100
    rate_limit_period: int = 60  # seconds

    # Timeout
    request_timeout: float = 30.0
    connect_timeout: float = 10.0
    http_verify_tls: bool = os.getenv("HTTP_VERIFY_TLS", "1") == "1"

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    # Health Check
    health_check_interval: int = 30

    class Config:
        env_file = ".env"
        case_sensitive = False


# Create settings instance
settings = Settings()


# Service URLs configuration
class ServiceURLs:
    """Backend service URLs"""

    # Auth Service
    AUTH_LOGIN = _build_service_url(settings.auth_service_url, settings.auth_api_prefix, "/login")
    AUTH_REGISTER = _build_service_url(settings.auth_service_url, settings.auth_api_prefix, "/register")
    AUTH_LOGOUT = _build_service_url(settings.auth_service_url, settings.auth_api_prefix, "/logout")
    AUTH_REFRESH = _build_service_url(settings.auth_service_url, settings.auth_api_prefix, "/refresh")
    AUTH_ME = _build_service_url(settings.auth_service_url, settings.auth_api_prefix, "/me")
    AUTH_FORGOT = _build_service_url(settings.auth_service_url, settings.auth_api_prefix, "/forgot")
    AUTH_PASSWORD_RESET_REQUEST = _build_service_url(
        settings.auth_service_url,
        settings.auth_api_prefix,
        "/password-reset/request",
    )
    AUTH_PASSWORD_RESET_CONFIRM = _build_service_url(
        settings.auth_service_url,
        settings.auth_api_prefix,
        "/password-reset/confirm",
    )
    AUTH_GOOGLE = _build_service_url(settings.auth_service_url, settings.auth_api_prefix, "/google")

    # App Service - Tasks
    APP_TASKS = _build_service_url(settings.app_service_url, settings.app_api_prefix, "/tasks")
    APP_TASK_START = _build_service_url(settings.app_service_url, settings.app_api_prefix, "/tasks")
    APP_TASK_STOP = _build_service_url(settings.app_service_url, settings.app_api_prefix, "/tasks")
    APP_TASK_COMPLETE = _build_service_url(settings.app_service_url, settings.app_api_prefix, "/tasks")
    APP_TASK_DELETE = _build_service_url(settings.app_service_url, settings.app_api_prefix, "/tasks")

    # App Service - Projects
    APP_PROJECTS = _build_service_url(settings.app_service_url, settings.app_api_prefix, "/projects")
    APP_PROJECT_DELETE = _build_service_url(settings.app_service_url, settings.app_api_prefix, "/projects")

    # App Service - Goals
    APP_GOALS = _build_service_url(settings.app_service_url, settings.app_api_prefix, "/goals")
    APP_GOAL_DETAIL = _build_service_url(settings.app_service_url, settings.app_api_prefix, "/goals")
    APP_GOAL_EDIT = _build_service_url(settings.app_service_url, settings.app_api_prefix, "/goals")
    APP_GOAL_DELETE = _build_service_url(settings.app_service_url, settings.app_api_prefix, "/goals")
    APP_GOAL_SUBGOALS = _build_service_url(
        settings.app_service_url,
        settings.app_api_prefix,
        "/goals/subgoals",
    )

    # App Service - Habits
    APP_HABITS = _build_service_url(settings.app_service_url, settings.app_api_prefix, "/habits")
    APP_HABIT_TRACK = _build_service_url(settings.app_service_url, settings.app_api_prefix, "/habits")

    # App Service - Todos
    APP_TODOS = _build_service_url(settings.app_service_url, settings.app_api_prefix, "/todos")

    # App Service - Reminders
    APP_REMINDERS = _build_service_url(settings.app_service_url, settings.app_api_prefix, "/reminders")

    # App Service - Labels
    APP_LABELS = _build_service_url(settings.app_service_url, settings.app_api_prefix, "/labels")

    # App Service - Reports
    APP_REPORTS_SUMMARY = _build_service_url(
        settings.app_service_url,
        settings.app_api_prefix,
        "/reports/summary",
    )

    # App Service - Timer
    APP_TIMER_ENTRIES = _build_service_url(
        settings.app_service_url,
        settings.app_api_prefix,
        "/timer/entries",
    )

    # App Service - Settings
    APP_SETTINGS_PROFILE = _build_service_url(
        settings.app_service_url,
        settings.app_api_prefix,
        "/settings/profile",
    )
    APP_SETTINGS_TIMEZONE = _build_service_url(
        settings.app_service_url,
        settings.app_api_prefix,
        "/settings/timezone",
    )
    APP_SETTINGS_NOTIFICATIONS = _build_service_url(
        settings.app_service_url,
        settings.app_api_prefix,
        "/settings/notifications",
    )


service_urls = ServiceURLs()
