# PWA Integration with BFF

This document describes how to integrate the Goalixa PWA with the new BFF service.

## Overview

The PWA should now make requests to the BFF endpoints instead of directly to the auth and app services.

## Base URL Changes

### Before:
```javascript
const API_BASE_URL = 'https://api.goalixa.com';
// or
const AUTH_API = 'https://auth.goalixa.com';
const APP_API = 'https://app.goalixa.com';
```

### After:
```javascript
const API_BASE_URL = 'https://api.goalixa.com/bff';
```

## Endpoint Mapping

### Authentication Endpoints

| Old Endpoint | New BFF Endpoint |
|--------------|------------------|
| `POST /auth/login` | `POST /bff/auth/login` |
| `POST /auth/register` | `POST /bff/auth/register` |
| `POST /auth/logout` | `POST /bff/auth/logout` |
| `POST /auth/refresh` | `POST /bff/auth/refresh` |
| `GET /auth/me` | `GET /bff/auth/me` |
| `POST /auth/forgot` | `POST /bff/auth/forgot` |
| `POST /auth/password-reset/request` | `POST /bff/auth/password-reset/request` |
| `POST /auth/password-reset/confirm` | `POST /bff/auth/password-reset/confirm` |

### App Endpoints

All app endpoints remain the same but are prefixed with `/bff/app/`:

| Old Endpoint | New BFF Endpoint |
|--------------|------------------|
| `GET /app/tasks` | `GET /bff/app/tasks` |
| `POST /app/tasks` | `POST /bff/app/tasks` |
| `GET /app/projects` | `GET /bff/app/projects` |
| `GET /app/goals` | `GET /bff/app/goals` |
| etc. | `GET /bff/app/...` |

### New Aggregate Endpoints

The BFF provides new aggregate endpoints that combine data from multiple services:

| Endpoint | Description |
|----------|-------------|
| `GET /bff/aggregate/dashboard` | Complete dashboard data (tasks, projects, goals, habits, todos, user) |
| `GET /bff/aggregate/timer-dashboard` | Timer-specific data (tasks, entries, projects) |
| `GET /bff/aggregate/planner` | Planner data (habits, todos, goals) |
| `GET /bff/aggregate/reports` | Reports data (summary, tasks, projects) |
| `GET /bff/aggregate/overview` | Overview data (user, tasks, summary) |

## PWA API Client Updates

### Update goalixa-pwa/js/api.js

```javascript
// Update the base configuration
const API_CONFIG = {
    baseURL: 'https://api.goalixa.com/bff',
    timeout: 30000,
    headers: {
        'Content-Type': 'application/json'
    }
};

// Helper function to build URLs
function buildURL(endpoint) {
    return `${API_CONFIG.baseURL}${endpoint}`;
}

// Example API call
async function login(email, password) {
    const response = await fetch(buildURL('/auth/login'), {
        method: 'POST',
        credentials: 'include', // Important for cookies
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ email, password })
    });

    if (!response.ok) {
        throw new Error('Login failed');
    }

    return response.json();
}

// Example aggregate call - gets all dashboard data in one request
async function getDashboard() {
    const response = await fetch(buildURL('/aggregate/dashboard'), {
        method: 'GET',
        credentials: 'include'
    });

    if (!response.ok) {
        throw new Error('Failed to fetch dashboard');
    }

    return response.json();
}
```

## Benefits of Using BFF

1. **Single Entry Point**: All API calls go through one endpoint
2. **Fewer Requests**: Aggregate endpoints reduce multiple calls into one
3. **Better Performance**: Parallel data fetching at the BFF level
4. **Simplified Frontend**: Less complex API logic in the PWA
5. **Security**: Backend services are not directly exposed
6. **Flexibility**: Backend can change without affecting frontend

## Migration Steps

1. Update `goalixa-pwa/js/api.js` with new base URL
2. Update all endpoint calls to use `/bff/` prefix
3. Replace multiple sequential API calls with aggregate endpoints where possible
4. Test authentication flow (login/logout)
5. Test all CRUD operations
6. Test aggregate endpoints

## Example: Before and After

### Before (Multiple Calls):

```javascript
async function loadDashboard() {
    const tasks = await fetch('/app/tasks');
    const projects = await fetch('/app/projects');
    const goals = await fetch('/app/goals');
    const habits = await fetch('/app/habits');
    const todos = await fetch('/app/todos');
    const user = await fetch('/auth/me');

    return {
        tasks: await tasks.json(),
        projects: await projects.json(),
        goals: await goals.json(),
        habits: await habits.json(),
        todos: await todos.json(),
        user: await user.json()
    };
}
```

### After (Single Call):

```javascript
async function loadDashboard() {
    const response = await fetch('/bff/aggregate/dashboard', {
        credentials: 'include'
    });

    const data = await response.json();
    return data.data; // Contains all dashboard data
}
```

## Error Handling

The BFF provides consistent error responses:

```javascript
try {
    const response = await fetch('/bff/app/tasks');
    const data = await response.json();

    if (!response.ok) {
        // BFF error format
        throw new Error(data.error || 'Request failed');
    }

    return data;
} catch (error) {
    console.error('API Error:', error);
    // Handle error
}
```

## Cookie Handling

The BFF uses HttpOnly cookies for authentication. Ensure your fetch calls include:

```javascript
fetch('/bff/endpoint', {
    credentials: 'include' // Required for cookies
});
```
