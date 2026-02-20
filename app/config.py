"""
Configuration for BFF Service
"""
from pydantic_settings import BaseSettings
from typing import List
import os


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
    AUTH_LOGIN = f"{settings.auth_service_url}/auth/login"
    AUTH_REGISTER = f"{settings.auth_service_url}/auth/register"
    AUTH_LOGOUT = f"{settings.auth_service_url}/auth/logout"
    AUTH_REFRESH = f"{settings.auth_service_url}/auth/refresh"
    AUTH_ME = f"{settings.auth_service_url}/auth/me"
    AUTH_FORGOT = f"{settings.auth_service_url}/auth/forgot"
    AUTH_PASSWORD_RESET_REQUEST = f"{settings.auth_service_url}/auth/password-reset/request"
    AUTH_PASSWORD_RESET_CONFIRM = f"{settings.auth_service_url}/auth/password-reset/confirm"
    AUTH_GOOGLE = f"{settings.auth_service_url}/auth/google"

    # App Service - Tasks
    APP_TASKS = f"{settings.app_service_url}/app/tasks"
    APP_TASK_START = f"{settings.app_service_url}/app/tasks"
    APP_TASK_STOP = f"{settings.app_service_url}/app/tasks"
    APP_TASK_COMPLETE = f"{settings.app_service_url}/app/tasks"
    APP_TASK_DELETE = f"{settings.app_service_url}/app/tasks"

    # App Service - Projects
    APP_PROJECTS = f"{settings.app_service_url}/app/projects"
    APP_PROJECT_DELETE = f"{settings.app_service_url}/app/projects"

    # App Service - Goals
    APP_GOALS = f"{settings.app_service_url}/app/goals"
    APP_GOAL_DETAIL = f"{settings.app_service_url}/app/goals"
    APP_GOAL_EDIT = f"{settings.app_service_url}/app/goals"
    APP_GOAL_DELETE = f"{settings.app_service_url}/app/goals"
    APP_GOAL_SUBGOALS = f"{settings.app_service_url}/app/goals/subgoals"

    # App Service - Habits
    APP_HABITS = f"{settings.app_service_url}/app/habits"
    APP_HABIT_TRACK = f"{settings.app_service_url}/app/habits"

    # App Service - Todos
    APP_TODOS = f"{settings.app_service_url}/app/todos"

    # App Service - Reminders
    APP_REMINDERS = f"{settings.app_service_url}/app/reminders"

    # App Service - Labels
    APP_LABELS = f"{settings.app_service_url}/app/labels"

    # App Service - Reports
    APP_REPORTS_SUMMARY = f"{settings.app_service_url}/app/reports/summary"

    # App Service - Timer
    APP_TIMER_ENTRIES = f"{settings.app_service_url}/app/timer/entries"

    # App Service - Settings
    APP_SETTINGS_PROFILE = f"{settings.app_service_url}/app/settings/profile"
    APP_SETTINGS_TIMEZONE = f"{settings.app_service_url}/app/settings/timezone"
    APP_SETTINGS_NOTIFICATIONS = f"{settings.app_service_url}/app/settings/notifications"


service_urls = ServiceURLs()
