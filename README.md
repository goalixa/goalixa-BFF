# goalixa-bff

Backend-for-Frontend (BFF) service for the Goalixa platform.

## Overview

goalixa-bff is a dedicated backend service that provides a unified API layer for the Goalixa PWA (Progressive Web App). It acts as an intermediary between the frontend and internal backend services such as auth and goalixa-app.

Instead of the frontend communicating directly with multiple services, it communicates with this BFF through a single, consistent API.

## Responsibilities

- Provide frontend-optimized API endpoints
- Forward authentication requests to the auth service
- Handle session-based authentication using secure HttpOnly cookies
- Aggregate and compose responses from multiple backend services
- Normalize error handling and response formats
- Simplify frontend architecture and reduce coupling

## Architecture

Browser (PWA)
↓
Traefik (API Gateway / Ingress)
↓
goalixa-bff
↓
auth service

goalixa-app service


## Benefits

- Single API entry point for the frontend
- Improved security (backend services are not directly exposed)
- Reduced frontend complexity
- Easier backend evolution and refactoring
- Better observability and control

## Tech Stack

- Python
- FastAPI
- HTTPX
- Docker
- Kubernetes
- Traefik

## Role in Goalixa Platform

goalixa-bff serves only the application frontend (`app.goalixa.com`).

The landing site (`goalixa.com`) remains a separate application and does not use this BFF.

## Status

Early development.
