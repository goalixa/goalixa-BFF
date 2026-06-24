# Goalixa BFF

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?logo=fastapi&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-Cache-DC382D?logo=redis&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

Backend for Frontend service that provides a unified API layer for frontend applications.

## Why BFF?

| Problem | Solution |
|---------|----------|
| Multiple service calls | Single aggregated request |
| Complex frontend logic | Data composition on backend |
| Direct service exposure | Backend services protected |
| Breaking changes | Frontend isolated from backend evolution |
| Performance | Parallel fetching + caching |

## Architecture

```
┌─────────────────┐
│   Frontend App  │
└────────┬────────┘
         │
┌────────▼────────┐
│   API Gateway   │
└────────┬────────┘
         │
┌────────▼────────────────────────┐
│          BFF Service            │
│  • Auth proxy                   │
│  • Request aggregation          │
│  • Response transformation      │
│  • Caching                      │
└────────┬───────────┬────────────┘
         │           │
    ┌────▼────┐ ┌────▼────┐
    │  Auth   │ │ Core-API│
    │ Service │ │ Service │
    └─────────┘ └─────────┘
```

## Tech Stack

- **Python 3.11**
- **FastAPI** - Async web framework
- **HTTPX** - Async HTTP client
- **Redis** - Caching layer
- **Prometheus** - Metrics

## Features

| Feature | Description |
|---------|-------------|
| **Unified API** | Single entry point for all frontend calls |
| **Auth Proxy** | Secure token handling with HTTP-only cookies |
| **Aggregation** | Combine multiple service calls |
| **Caching** | Redis-based performance optimization |
| **Metrics** | Prometheus metrics for observability |

## Getting Started

### Installation

```bash
git clone https://github.com/goalixa/goalixa-bff.git
cd goalixa-bff

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Configuration

Create a `.env` file:

```bash
AUTH_SERVICE_URL=http://localhost:8001
APP_SERVICE_URL=http://localhost:8002
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=your-secret
```

| Variable | Description | Required |
|----------|-------------|----------|
| `AUTH_SERVICE_URL` | Auth service endpoint | Yes |
| `APP_SERVICE_URL` | Core API endpoint | Yes |
| `REDIS_URL` | Redis connection string | No |
| `JWT_SECRET` | Secret for token validation | Yes |

### Run

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

### Health
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Basic health check |
| GET | `/health/liveness` | Kubernetes liveness probe |
| GET | `/health/readiness` | Kubernetes readiness probe |
| GET | `/health/deep` | Check all backend services |
| GET | `/metrics` | Prometheus metrics |

### Authentication (`/bff/auth/*`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/bff/auth/login` | User login |
| POST | `/bff/auth/register` | Registration |
| POST | `/bff/auth/logout` | Logout |
| POST | `/bff/auth/refresh` | Refresh token |
| GET | `/bff/auth/me` | Current user |

### App Routes (`/bff/app/*`)
Proxies to Core-API:
- Tasks, Projects, Goals, Habits
- Todos, Reminders, Labels
- Reports, Timer entries, Settings

### Aggregate Endpoints (`/bff/aggregate/*`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/bff/aggregate/dashboard` | Complete dashboard data |
| GET | `/bff/aggregate/timer-dashboard` | Timer view data |
| GET | `/bff/aggregate/planner` | Planner view data |
| GET | `/bff/aggregate/reports` | Reports data |
| GET | `/bff/aggregate/overview` | Overview page data |

## Project Structure

```
goalixa-BFF/
├── app/
│   ├── main.py           # FastAPI app
│   ├── config.py         # Configuration
│   ├── routers/
│   │   ├── auth.py       # Auth endpoints
│   │   ├── app_router.py # App proxy
│   │   ├── aggregate.py  # Aggregations
│   │   └── health.py     # Health checks
│   └── middleware/
├── helm/                 # Kubernetes deployment
├── requirements.txt
└── Dockerfile
```

## Deployment

### Docker

```bash
docker build -t goalixa-bff:latest .
docker run -p 8000:80 goalixa-bff:latest
```

### Kubernetes

```bash
helm upgrade --install goalixa-bff ./helm \
  --namespace goalixa \
  --create-namespace
```

## API Documentation

When running, access interactive docs:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## Performance Tips

1. Use aggregate endpoints to reduce round trips
2. Enable Redis caching for frequently accessed data
3. Connection pooling is handled automatically by HTTPX
4. Aggregate endpoints fetch data in parallel

## License

MIT License - see [LICENSE](LICENSE) for details.

---

Built by [Amirreza Rezaie](https://github.com/amirrezarezaie)
