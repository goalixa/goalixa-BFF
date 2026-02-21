"""
Circuit Breaker Pattern
Prevents cascading failures by stopping requests to failing services
"""
import asyncio
import logging
from enum import Enum
from typing import Callable, Optional, Any
from functools import wraps
import time

from app.config import settings

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation, requests pass through
    OPEN = "open"          # Circuit is open, requests fail fast
    HALF_OPEN = "half_open"  # Testing if service has recovered


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open"""
    pass


class CircuitBreaker:
    """
    Circuit breaker implementation for protecting against failing services

    States:
    - CLOSED: Normal operation, requests pass through to service
    - OPEN: Service has failed too many times, requests fail immediately
    - HALF_OPEN: Testing if service has recovered (allowing limited requests)

    Transitions:
    CLOSED -> OPEN: When failure threshold is reached
    OPEN -> HALF_OPEN: After timeout period has elapsed
    HALF_OPEN -> CLOSED: When test request succeeds
    HALF_OPEN -> OPEN: When test request fails
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: Exception = Exception,
        half_open_max_calls: int = 3
    ):
        """
        Initialize circuit breaker

        Args:
            name: Name of the circuit breaker (for logging)
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
            expected_exception: Exception type that counts as failure
            half_open_max_calls: Max calls allowed in half-open state
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._last_success_time: Optional[float] = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state"""
        return self._state

    @property
    def failure_count(self) -> int:
        """Get current failure count"""
        return self._failure_count

    @property
    def last_failure_time(self) -> Optional[float]:
        """Get last failure time"""
        return self._last_failure_time

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        if self._last_failure_time is None:
            return True

        elapsed = time.time() - self._last_failure_time
        return elapsed >= self.recovery_timeout

    async def _open_circuit(self):
        """Open the circuit"""
        self._state = CircuitState.OPEN
        self._last_failure_time = time.time()
        logger.warning(f"Circuit breaker '{self.name}' opened after {self._failure_count} failures")

    async def _close_circuit(self):
        """Close the circuit (recovery successful)"""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._half_open_calls = 0
        self._last_success_time = time.time()
        logger.info(f"Circuit breaker '{self.name}' closed - service recovered")

    async def _half_open_circuit(self):
        """Move to half-open state for testing"""
        self._state = CircuitState.HALF_OPEN
        self._half_open_calls = 0
        logger.info(f"Circuit breaker '{self.name}' moved to half-open state for testing")

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function through the circuit breaker

        Args:
            func: Function to call
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerOpenError: When circuit is open
            Exception: When function raises an exception
        """
        async with self._lock:
            # Check if circuit is open
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    await self._half_open_circuit()
                else:
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' is open. "
                        f"Service unavailable. Try again later."
                    )

            # In half-open state, limit the number of calls
            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' is in half-open state. "
                        f"Max test calls reached."
                    )
                self._half_open_calls += 1

        try:
            # Execute the function
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            # Success - handle state transitions
            async with self._lock:
                if self._state == CircuitState.HALF_OPEN:
                    await self._close_circuit()
                elif self._state == CircuitState.CLOSED:
                    self._failure_count = 0

            return result

        except self.expected_exception as e:
            # Failure - handle state transitions
            async with self._lock:
                self._failure_count += 1
                self._last_failure_time = time.time()

                logger.warning(
                    f"Circuit breaker '{self.name}' recorded failure "
                    f"({self._failure_count}/{self.failure_threshold}): {e}"
                )

                if self._failure_count >= self.failure_threshold:
                    await self._open_circuit()
                elif self._state == CircuitState.HALF_OPEN:
                    await self._open_circuit()

            raise

        except Exception as e:
            # Unexpected exception - also count as failure
            async with self._lock:
                self._failure_count += 1
                self._last_failure_time = time.time()

                logger.error(
                    f"Circuit breaker '{self.name}' recorded unexpected error: {e}"
                )

                if self._failure_count >= self.failure_threshold:
                    await self._open_circuit()
                elif self._state == CircuitState.HALF_OPEN:
                    await self._open_circuit()

            raise


# Global circuit breaker instances
_circuit_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(
    service_name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0
) -> CircuitBreaker:
    """
    Get or create a circuit breaker for a service

    Args:
        service_name: Name of the service
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Seconds to wait before attempting recovery

    Returns:
        CircuitBreaker instance
    """
    if service_name not in _circuit_breakers:
        _circuit_breakers[service_name] = CircuitBreaker(
            name=service_name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout
        )

    return _circuit_breakers[service_name]


def with_circuit_breaker(
    service_name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0
):
    """
    Decorator to apply circuit breaker to a function

    Args:
        service_name: Name of the service
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Seconds to wait before attempting recovery

    Usage:
        @with_circuit_breaker("auth-service", failure_threshold=5, recovery_timeout=60)
        async def call_auth_service():
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            breaker = get_circuit_breaker(
                service_name,
                failure_threshold,
                recovery_timeout
            )
            return await breaker.call(func, *args, **kwargs)

        return wrapper

    return decorator
