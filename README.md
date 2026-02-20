# Goalixa BFF - Backend for Frontend

A dedicated Backend for Frontend (BFF) service providing a unified API layer for frontend applications.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Development](#development)
- [Deployment](#deployment)
- [API Documentation](#api-documentation)
- [Monitoring](#monitoring)

## Overview

This BFF acts as an intermediary between frontend applications and backend microservices. Instead of the frontend communicating directly with multiple services, it communicates with this BFF through a single, consistent API.

### Problem It Solves

- **Multiple Service Calls**: Reduces multiple frontend API calls into single aggregated requests
- **Complex Frontend Logic**: Offloads data composition and transformation to the backend
- **Security**: Backend services are not directly exposed to the internet
- **Flexibility**: Backend can evolve without breaking frontend integrations
- **Performance**: Parallel data fetching and caching at the BFF level

## Architecture

```
┌─────────────────┐
│   Frontend App  │
└────────┬────────┘
         │ HTTPS
         ▼
┌─────────────────────────────────────┐
│        API Gateway / Ingress        │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│            BFF Service              │
│                                     │
│  • Authentication handling         │
│  • Request aggregation             │
│  • Response transformation          │
│  • Caching layer                    │
└──────┬──────────────────┬───────────┘
       │                  │
       ▼                  ▼
┌─────────────┐    ┌─────────────┐
│ Auth Service│    │ App Service │
└─────────────┘    └─────────────┘
```

## Features

### Core Features

- **Unified API**: Single entry point for all frontend API calls
- **Authentication Proxy**: Secure token handling with HttpOnly cookies
- **Request Aggregation**: Combine multiple service calls into one
- **Response Transformation**: Format data optimally for the frontend
- **Caching**: Redis-based caching for frequently accessed data
- **Error Handling**: Consistent error responses across all endpoints
- **Logging**: Structured logging for debugging and monitoring
- **Metrics**: Prometheus metrics for observability

### API Endpoints

#### Health & Monitoring
- `GET /health` - Basic health check
- `GET /health/liveness` - Liveness probe
- `GET /health/readiness` - Readiness probe
- `GET /health/deep` - Deep health with backend checks
- `GET /metrics` - Prometheus metrics

#### Authentication (`/bff/auth/*`)
- `POST /bff/auth/login` - User login
- `POST /bff/auth/register` - User registration
- `POST /bff/auth/logout` - User logout
- `POST /bff/auth/refresh` - Refresh access token
- `GET /bff/auth/me` - Get current user
- `POST /bff/auth/forgot` - Forgot password
- `POST /bff/auth/password-reset/request` - Request password reset
- `POST /bff/auth/password-reset/confirm` - Confirm password reset
- `GET /bff/auth/google` - Google OAuth URL

#### App Routes (`/bff/app/*`)
- Tasks, Projects, Goals, Habits, Todos, Reminders, Labels
- Reports and Timer entries
- Settings (profile, timezone, notifications)

#### Aggregate Endpoints (`/bff/aggregate/*`)
- `GET /bff/aggregate/dashboard` - Complete dashboard data
- `GET /bff/aggregate/timer-dashboard` - Timer-specific data
- `GET /bff/aggregate/planner` - Planner view data
- `GET /bff/aggregate/reports` - Reports data
- `GET /bff/aggregate/overview` - Overview page data

## Tech Stack

- **Python 3.11+**
- **FastAPI** - Modern async web framework
- **HTTPX** - Async HTTP client
- **Uvicorn** - ASGI server
- **Redis** - Caching layer
- **Prometheus** - Metrics collection
- **Docker** - Containerization
- **Kubernetes** - Orchestration

## Project Structure

```
goalixa-BFF/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application entry point
│   ├── config.py            # Configuration and settings
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py          # Authentication endpoints
│   │   ├── app_router.py    # App service endpoints
│   │   ├── aggregate.py     # Aggregate endpoints
│   │   └── health.py        # Health check endpoints
│   └── middleware/
│       ├── __init__.py
│       ├── auth_middleware.py
│       └── logging_middleware.py
├── k8s/
│   ├── deployment.yaml      # Kubernetes deployment and service
│   ├── ingress.yaml         # Ingress configuration
│   ├── secrets.yaml         # Kubernetes secrets template
│   └── api-gateway-configmap.yaml  # API Gateway config
├── docs/
│   └── PWA_INTEGRATION.md   # Integration guide
├── Dockerfile               # Docker image build
├── docker-compose.yml       # Local development
├── requirements.txt         # Python dependencies
├── .env.example             # Environment variables template
├── deploy.sh                # Deployment script
└── README.md                # This file
```

## Quick Start

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- kubectl (for Kubernetes deployment)

### Local Development

1. **Create environment file**
```bash
cp .env.example .env
# Edit .env with your configuration
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Run with uvicorn**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- Metrics: http://localhost:8000/metrics

### Docker Compose (Local)

```bash
docker-compose up -d
```

## Development

### Environment Variables

See `.env.example` for all available configuration options.

Key variables:
- `AUTH_SERVICE_URL` - Auth service URL
- `APP_SERVICE_URL` - App service URL
- `REDIS_URL` - Redis connection string
- `JWT_SECRET` - Secret for JWT validation
- `CORS_ORIGINS` - Allowed CORS origins

### Configuration

Edit `app/config.py` to customize:
- Backend service URLs
- CORS settings
- Cache configuration
- Rate limiting
- Timeout values

## Deployment

### Environment Setup

Before deploying, update the following in your environment:

1. **Service URLs**: Update `AUTH_SERVICE_URL` and `APP_SERVICE_URL` in the deployment YAML
2. **Secrets**: Create Kubernetes secrets for sensitive data
3. **Ingress**: Configure ingress for your domain
4. **CORS**: Update allowed origins for your frontend domain

### Deploy to Kubernetes

```bash
# Update the deploy script with your container registry
./deploy.sh
```

Or manually:

```bash
# 1. Create namespace
kubectl create namespace goalixa-bff

# 2. Create secrets (edit with your values)
kubectl apply -f k8s/secrets.yaml

# 3. Build and push image (update with your registry)
docker build -t YOUR_REGISTRY/goalixa-bff:latest .
docker push YOUR_REGISTRY/goalixa-bff:latest

# 4. Update deployment.yaml with your image registry
# 5. Deploy
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/ingress.yaml
```

## API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

Interactive API documentation with try-it-out functionality.

## Monitoring

### Prometheus Metrics

The BFF exposes Prometheus metrics at `/metrics`:

- `bff_request_count` - Total request count
- `bff_request_duration_seconds` - Request duration histogram

### Health Checks

- **Basic**: `/health` - Quick health check
- **Liveness**: `/health/liveness` - K8s liveness probe
- **Readiness**: `/health/readiness` - K8s readiness probe
- **Deep**: `/health/deep` - Checks backend service connectivity

### Logging

Logs are structured JSON format:
```json
{
  "timestamp": "2024-02-20T10:30:00Z",
  "level": "INFO",
  "message": "Request completed",
  "method": "GET",
  "path": "/bff/app/tasks",
  "status_code": 200,
  "duration_ms": 45.23
}
```

## Performance Tips

1. **Use Aggregate Endpoints**: Combine multiple API calls into one
2. **Enable Caching**: Redis caching reduces backend load
3. **Connection Pooling**: HTTPX maintains connection pools
4. **Parallel Requests**: Aggregate endpoints fetch data in parallel

## Security Considerations

- **Secrets Management**: Use Kubernetes Secrets or your secret manager
- **HttpsOnly Cookies**: Ensure HTTPS is enabled in production
- **CORS**: Configure allowed origins appropriately
- **Rate Limiting**: Configure rate limits at the API Gateway
- **Service Discovery**: Use proper service discovery mechanisms

## License

See LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
