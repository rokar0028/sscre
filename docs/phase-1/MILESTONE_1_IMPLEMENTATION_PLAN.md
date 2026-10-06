# Milestone 1 Implementation Plan — Minimal FastAPI Service

## Goal

Create the smallest runnable SSCRE web service:

```text
HTTP client
    ↓
FastAPI application
    ↓
GET /health → {"status": "ok"}
```

This milestone establishes the API boundary. Query processing and caching are
implemented in later milestones.

## Learning objectives

- [ ] HTTP methods, especially `GET`
- [ ] HTTP status codes
- [ ] JSON request and response bodies
- [ ] FastAPI route declarations
- [ ] Application factories
- [ ] Uvicorn and the ASGI server model
- [ ] Pydantic validation
- [ ] API testing with FastAPI `TestClient`

## Implementation steps

### 1. Install runtime dependencies

- [x] Add FastAPI to the project dependencies.
- [x] Add Uvicorn as the local ASGI server.
- [x] Add HTTP client test support.

### 2. Create the application factory

- [x] Add `create_app()` in `src/sscre/app.py`.
- [x] Configure the application title as `SSCRE`.
- [x] Keep application construction separate from server startup.

### 3. Add the health endpoint

- [x] Add `GET /health`.
- [x] Return JSON: `{"status": "ok"}`.
- [x] Return HTTP status `200` for a healthy application.

### 4. Add API tests

- [x] Test that the health endpoint returns status `200`.
- [x] Test that the response body is valid JSON.
- [x] Test that the response contains the expected status.

### 5. Run the service locally

- [x] Start the service with Uvicorn.
- [x] Call the endpoint with an HTTP client.
- [x] Confirm the live response is `HTTP 200`.

## Verification checklist

- [x] FastAPI is installed in the project virtual environment.
- [x] Uvicorn starts the application.
- [x] `GET /health` returns `{"status": "ok"}`.
- [x] The health endpoint has an automated test.
- [x] The full test suite passes (`.venv\Scripts\python.exe -m pytest -q`;
  27 passed, 6 skipped).
- [ ] No linter errors are reported (no linter is currently configured).

## Completion criteria

Milestone 1 is complete when the application starts locally and a client can
receive a successful JSON response from `GET /health`. The service must remain
small enough that the application factory, route, server command, and test can
each be explained independently.
