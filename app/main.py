"""
Goalixa BFF - Backend for Frontend
A unified API layer for the Goalixa PWA
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
import httpx
import logging
from prometheus_client import Counter, Histogram, Gauge, generate_latest, Info
from fastapi import Response
import time

from app.config import settings
from app.routers import auth, app_router, health, aggregate
from app.middleware.auth_middleware import AuthMiddleware
from app.middleware.logging_middleware import LoggingMiddleware
from app.middleware.rate_limit_middleware import RateLimitMiddleware
from app.utils.cache import get_redis_client, close_redis_client
from app import http_client as http_client_module

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Prometheus Metrics
# Request metrics
REQUEST_COUNT = Counter(
    'bff_request_count',
    'Total request count',
    ['method', 'endpoint', 'status']
)
REQUEST_DURATION = Histogram(
    'bff_request_duration_seconds',
    'Request duration',
    ['method', 'endpoint'],
    buckets=(.005, .01, .025, .05, .075, .1, .25, .5, .75, 1.0, 2.5, 5.0, 7.5, 10.0, float('inf'))
)

# Authentication metrics
AUTH_REQUESTS_TOTAL = Counter(
    'bff_auth_requests_total',
    'Total authentication requests',
    ['method', 'endpoint', 'status']
)
AUTH_VALIDATION_DURATION = Histogram(
    'bff_auth_validation_seconds',
    'Authentication validation duration',
    ['validation_type'],  # 'local_jwt' or 'auth_service'
    buckets=(.001, .005, .01, .025, .05, .1, .25, .5, 1.0, float('inf'))
)
AUTH_FAILURES_TOTAL = Counter(
    'bff_auth_failures_total',
    'Total authentication failures',
    ['failure_type']  # 'no_token', 'invalid_token', 'expired_token', 'service_error'
)

# Backend service metrics
BACKEND_REQUESTS_TOTAL = Counter(
    'bff_backend_requests_total',
    'Total backend service requests',
    ['service', 'method', 'endpoint', 'status']
)
BACKEND_REQUEST_DURATION = Histogram(
    'bff_backend_request_duration_seconds',
    'Backend service request duration',
    ['service', 'endpoint'],
    buckets=(.01, .05, .1, .25, .5, .75, 1.0, 2.5, 5.0, 10.0, float('inf'))
)
BACKEND_REQUESTS_IN_PROGRESS = Gauge(
    'bff_backend_requests_in_progress',
    'Number of backend requests in progress',
    ['service']
)

# Circuit breaker metrics
CIRCUIT_BREAKER_STATE = Gauge(
    'bff_circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=open, 2=half_open)',
    ['service']
)
CIRCUIT_BREAKER_FAILURES_TOTAL = Counter(
    'bff_circuit_breaker_failures_total',
    'Total circuit breaker failures',
    ['service']
)
CIRCUIT_BREAKER_SUCCESS_TOTAL = Counter(
    'bff_circuit_breaker_success_total',
    'Total circuit breaker successes',
    ['service']
)
CIRCUIT_BREAKER_REJECTED_TOTAL = Counter(
    'bff_circuit_breaker_rejected_total',
    'Total requests rejected by circuit breaker',
    ['service']
)

# Cache metrics
CACHE_REQUESTS_TOTAL = Counter(
    'bff_cache_requests_total',
    'Total cache requests',
    ['operation', 'status']  # operation: 'hit' or 'miss'
)
CACHE_DURATION = Histogram(
    'bff_cache_operation_seconds',
    'Cache operation duration',
    ['operation'],
    buckets=(.0001, .0005, .001, .005, .01, .025, .05, .1, float('inf'))
)

# Rate limiting metrics
RATE_LIMIT_REQUESTS_TOTAL = Counter(
    'bff_rate_limit_requests_total',
    'Total rate limit checks',
    ['status']  # 'allowed' or 'blocked'
)

# Error metrics
ERRORS_TOTAL = Counter(
    'bff_errors_total',
    'Total errors encountered',
    ['error_type', 'endpoint']
)

# Application info
APP_INFO = Info(
    'bff_build_info',
    'BFF build information'
)

# HTTP Async Client for backend services
http_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    global http_client

    # Startup
    logger.info("Starting Goalixa BFF...")

    # Initialize application info
    APP_INFO.info({
        'version': '1.0.0',
        'environment': settings.environment
    })

    # Initialize Redis if enabled
    if settings.redis_enabled:
        await get_redis_client()
        logger.info("Redis caching enabled")

    # Initialize HTTP client with connection pooling
    limits = httpx.Limits(
        max_keepalive_connections=50,
        max_connections=100,
        keepalive_expiry=30.0
    )
    timeout = httpx.Timeout(30.0, connect=10.0)

    http_client = httpx.AsyncClient(
        limits=limits,
        timeout=timeout,
        verify=settings.http_verify_tls
    )

    # Set the shared HTTP client in the http_client module
    http_client_module.set_http_client(http_client)

    logger.info(f"BFF connected to auth service at {settings.auth_service_url}")
    logger.info(f"BFF connected to app service at {settings.app_service_url}")

    yield

    # Shutdown
    logger.info("Shutting down Goalixa BFF...")
    await http_client.aclose()

    # Close Redis connection
    if settings.redis_enabled:
        await close_redis_client()

    logger.info("BFF shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Goalixa BFF",
    description="Backend for Frontend - Unified API layer for Goalixa PWA",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# GZip Middleware for response compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Custom Middlewares
# Note: Middlewares are processed in reverse order of registration
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuthMiddleware, http_client=http_client)
app.add_middleware(LoggingMiddleware)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(auth.router, prefix="/bff/auth", tags=["Auth"])
app.include_router(app_router.router, prefix="/bff/app", tags=["App"])
app.include_router(aggregate.router, prefix="/bff/aggregate", tags=["Aggregate"])

# Metrics endpoint for Prometheus scraping
@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(content=generate_latest(), media_type="text/plain")


@app.get("/")
async def root():
    """Root endpoint with BFF information"""
    return {
        "service": "Goalixa BFF",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "auth": "/bff/auth/*",
            "app": "/bff/app/*",
            "aggregate": "/bff/aggregate/*",
            "metrics": "/metrics"
        }
    }


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=500
    ).inc()

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred. Please try again later.",
            "detail": str(exc) if settings.debug else None
        }
    )


# Request metrics middleware
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Middleware to collect request metrics"""
    start_time = time.time()

    response = await call_next(request)

    # Record metrics
    duration = time.time() - start_time
    REQUEST_DURATION.labels(
        method=request.method,
        endpoint=request.url.path
    ).observe(duration)

    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()

    return response


# Startup event for additional initialization
@app.on_event("startup")
async def startup_event():
    """Additional startup tasks"""
    logger.info("Goalixa BFF is ready to accept requests")


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Additional cleanup tasks"""
    logger.info("Goalixa BFF shutdown complete")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
