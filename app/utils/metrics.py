"""
Metrics Utility Module
Provides helper functions for recording Prometheus metrics
"""
import logging
from prometheus_client import Counter, Histogram, Gauge
import time
from functools import wraps
from typing import Callable, Optional, Any

logger = logging.getLogger(__name__)


class MetricsHelper:
    """Helper class for recording metrics"""

    @staticmethod
    def record_backend_request(
        service: str,
        method: str,
        endpoint: str,
        status_code: int,
        duration: float,
        requests_in_progress: Optional[Gauge] = None
    ):
        """Record backend service request metrics"""
        from app.main import (
            BACKEND_REQUESTS_TOTAL,
            BACKEND_REQUEST_DURATION
        )

        BACKEND_REQUESTS_TOTAL.labels(
            service=service,
            method=method,
            endpoint=endpoint,
            status=status_code
        ).inc()

        BACKEND_REQUEST_DURATION.labels(
            service=service,
            endpoint=endpoint
        ).observe(duration)

    @staticmethod
    def record_auth_validation(
        validation_type: str,
        duration: float,
        success: bool,
        failure_type: Optional[str] = None
    ):
        """Record authentication validation metrics"""
        from app.main import (
            AUTH_VALIDATION_DURATION,
            AUTH_FAILURES_TOTAL
        )

        AUTH_VALIDATION_DURATION.labels(
            validation_type=validation_type
        ).observe(duration)

        if not success and failure_type:
            AUTH_FAILURES_TOTAL.labels(
                failure_type=failure_type
            ).inc()

    @staticmethod
    def record_cache_operation(
        operation: str,
        status: str,
        duration: float
    ):
        """Record cache operation metrics"""
        from app.main import (
            CACHE_REQUESTS_TOTAL,
            CACHE_DURATION
        )

        CACHE_REQUESTS_TOTAL.labels(
            operation=operation,
            status=status
        ).inc()

        CACHE_DURATION.labels(
            operation=operation
        ).observe(duration)

    @staticmethod
    def record_circuit_breaker_state(
        service: str,
        state: str  # 'closed', 'open', 'half_open'
    ):
        """Record circuit breaker state change"""
        from app.main import CIRCUIT_BREAKER_STATE

        state_map = {'closed': 0, 'open': 1, 'half_open': 2}
        CIRCUIT_BREAKER_STATE.labels(
            service=service
        ).set(state_map.get(state, 0))

    @staticmethod
    def record_circuit_breaker_failure(service: str):
        """Record circuit breaker failure"""
        from app.main import CIRCUIT_BREAKER_FAILURES_TOTAL

        CIRCUIT_BREAKER_FAILURES_TOTAL.labels(
            service=service
        ).inc()

    @staticmethod
    def record_circuit_breaker_success(service: str):
        """Record circuit breaker success"""
        from app.main import CIRCUIT_BREAKER_SUCCESS_TOTAL

        CIRCUIT_BREAKER_SUCCESS_TOTAL.labels(
            service=service
        ).inc()

    @staticmethod
    def record_circuit_breaker_rejected(service: str):
        """Record circuit breaker rejection"""
        from app.main import CIRCUIT_BREAKER_REJECTED_TOTAL

        CIRCUIT_BREAKER_REJECTED_TOTAL.labels(
            service=service
        ).inc()

    @staticmethod
    def record_error(error_type: str, endpoint: str):
        """Record error occurrence"""
        from app.main import ERRORS_TOTAL

        ERRORS_TOTAL.labels(
            error_type=error_type,
            endpoint=endpoint
        ).inc()


def track_time(metric_histogram: Histogram, labels: dict = None):
    """
    Decorator to track function execution time

    Usage:
        @track_time(BACKEND_REQUEST_DURATION, {'service': 'auth-service', 'endpoint': '/login'})
        async def some_function():
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                if labels:
                    metric_histogram.labels(**labels).observe(duration)
                else:
                    metric_histogram.labels().observe(duration)

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                if labels:
                    metric_histogram.labels(**labels).observe(duration)
                else:
                    metric_histogram.labels().observe(duration)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def track_backend_request(service: str):
    """
    Decorator to track backend service requests

    Usage:
        @track_backend_request('auth-service')
        async def call_auth_service():
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            from app.main import BACKEND_REQUESTS_IN_PROGRESS

            # Increment in-progress gauge
            BACKEND_REQUESTS_IN_PROGRESS.labels(service=service).inc()

            start_time = time.time()
            status_code = 200
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status_code = 500
                logger.error(f"Backend request to {service} failed: {e}")
                raise
            finally:
                duration = time.time() - start_time
                BACKEND_REQUESTS_IN_PROGRESS.labels(service=service).dec()

                MetricsHelper.record_backend_request(
                    service=service,
                    method='POST',  # Default, can be overridden
                    endpoint=func.__name__,
                    status_code=status_code,
                    duration=duration
                )

        return wrapper
    return decorator
