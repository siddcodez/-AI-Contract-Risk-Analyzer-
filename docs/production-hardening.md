# Production Hardening, Observability & Reliability Guide (M6)

This document describes the production-hardening measures, observability features, and reliability mechanisms implemented in the AI Contract Risk Analyzer platform.

---

## 1. Structured Application Logging

- **Framework**: `structlog` configured at application startup via `configure_logging()`.
- **Output Formats**:
  - **Production Mode** (`ENVIRONMENT=production`): Structured JSON logged to `sys.stdout` for ingestion by CloudWatch, Datadog, ELK, etc.
  - **Development Mode** (`ENVIRONMENT=development`): Colored, human-readable console renderer.
- **Correlation Context**:
  Every log record automatically includes bound context variables:
  - `timestamp` (ISO 8601 format)
  - `level` (`INFO`, `WARNING`, `ERROR`, etc.)
  - `logger` (module name)
  - `message` / `event`
  - `request_id`
  - `organization_id` / `org_id`
  - `user_id`
  - `contract_id`
  - `job_id`
  - `analysis_job_id`
- **Data Protection Rules**:
  - Sensitive keys (`password`, `jwt`, `token`, `access_token`, `api_key`, `secret`, `contract_text`, `embedding`) are automatically redacted (`[REDACTED]`).
  - Raw contract text and vector embeddings are never written to log output.

---

## 2. Request Correlation IDs

- **Middleware**: `RequestIDMiddleware` in `app/middleware/request_id.py`.
- **Header**: `X-Request-ID`.
- **Behavior**:
  1. Inspects incoming `X-Request-ID` HTTP header.
  2. Validates pattern (`^[a-zA-Z0-9_-]{1,64}$`).
  3. Replaces missing, malformed, or >64 char IDs with a secure `uuid.uuid4()`.
  4. Binds the ID to `request_id_ctx` for all downstream application logging.
  5. Returns `X-Request-ID` header on all HTTP responses.

---

## 3. Celery Task Correlation

- **Tasks**: `process_contract_job` and `analyze_contract_job` in `app/workers/tasks.py`.
- **Traceability**:
  - Enqueued with `request_id` from the triggering HTTP context.
  - Automatically sets correlation context (`request_id`, `job_id`, `analysis_job_id`, `task_id`) at worker start.
  - Clears correlation context in `finally` block upon completion or failure.
  - Enables end-to-end log tracing: `HTTP request → Upload → Processing job → Processing worker → Analysis job → Analysis worker`.

---

## 4. Centralized API Error Handling

- **Error Envelope**:
  All API exceptions return a uniform JSON response structure:
  ```json
  {
      "error": {
          "code": "NOT_FOUND",
          "message": "Resource not found",
          "request_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
          "details": {}
      }
  }
  ```
- **Mapped Exception Types**:
  - `AppError` and domain subclasses (`NotFoundError`, `AuthenticationError`, `ForbiddenError`, `ConflictError`, `ValidationError`, `RateLimitError`, `StorageError`, `ProcessingError`).
  - FastAPI `RequestValidationError` / Pydantic `ValidationError` (status 422, code `VALIDATION_ERROR`).
  - `SQLAlchemyError` (status 500, code `DATABASE_ERROR`, generic safe message).
  - Unhandled `Exception` (status 500, code `INTERNAL_ERROR`, generic safe message).
- **Security Safeguards**:
  - Internal stack traces, raw SQL queries, file system paths, and database credentials are never exposed to clients.
  - Full exception trace is recorded in structured logs accompanied by the request correlation ID.

---

## 5. Health & Readiness Probes

- **Liveness Probe** (`GET /health`):
  - Fast, lightweight check verifying process responsiveness.
  - Does NOT query external backing services or database pool.
  - Returns HTTP 200 OK.
- **Readiness Probe** (`GET /ready`):
  - Pings backing dependencies: PostgreSQL (`database`), Redis (`redis`), MinIO/S3 (`storage`).
  - Returns HTTP 200 OK when all backing services respond:
    ```json
    {
        "status": "ok",
        "version": "0.1.0",
        "environment": "production",
        "dependencies": {
            "database": "ok",
            "redis": "ok",
            "storage": "ok"
        }
    }
    ```
  - Returns HTTP 503 Service Unavailable when a required dependency fails:
    ```json
    {
        "status": "degraded",
        "version": "0.1.0",
        "environment": "production",
        "dependencies": {
            "database": "error",
            "redis": "ok",
            "storage": "ok"
        }
    }
    ```
- **Celery Worker Visibility**:
  - `GET /ready?include_workers=true` optionally pings worker responsiveness via Celery control API.

---

## 6. API Rate Limiting & Abuse Protection

- **Implementation**: Sliding window rate limiter in `app/core/rate_limit.py`.
- **Backing Store**: Redis pipeline counters with automatic fallback to in-memory window tracking if Redis is unreachable.
- **Configurable Settings** in `app/core/config.py`:
  - `RATE_LIMIT_ENABLED`: `True` | `False` (bypassed in test environment).
  - `RATE_LIMIT_UPLOAD`: default `"10/minute"`.
  - `RATE_LIMIT_SEARCH`: default `"30/minute"`.
  - `RATE_LIMIT_ANALYSIS`: default `"10/minute"`.
- **Target Endpoints**:
  - `POST /api/v1/contracts/upload`
  - `POST /api/v1/contracts/{id}/search`
  - `POST /api/v1/contracts/{id}/retrieval`
  - `POST /api/v1/contracts/{id}/analyze`
- **Exceeded Limit Behavior**: Returns HTTP 429 Too Many Requests (`RateLimitError`).

---

## 7. Pagination Hardening

- **Bounded Parameters**:
  - `skip`: `int >= 0`
  - `limit`: `1 <= int <= MAX_PAGE_SIZE` (default `20`, maximum `100`).
- **Enforced Endpoints**:
  - `GET /api/v1/contracts/list`
  - `GET /api/v1/contracts/{id}/findings`
- **Invalid Inputs**: Returns HTTP 422 Unprocessable Content (`VALIDATION_ERROR`).

---

## 8. Production Configuration Validation

- **Fail-Fast Environment Validator**:
  When `ENVIRONMENT=production`, application startup immediately fails if any of the following insecure default values are present:
  - Default or weak `SECRET_KEY` containing "secret", "dev", "default", "example", etc.
  - Default database credentials (e.g., `postgres:postgres`).
  - Default MinIO credentials (`minioadmin:minioadmin`).
  - Missing `LLM_API_KEY` when `LLM_PROVIDER` is set to an external service.

---

## 9. Pipeline Failure Resilience & Retry Policy

- **Celery Task Resilience**:
  - **Transient Failures** (`StorageError`, `ConnectionError`, `TimeoutError`, `OSError`): Retried up to 3 times with exponential backoff.
  - **Permanent Failures** (`DocumentExtractionError`, `ValidationError`): Terminate immediately without retrying, persisting safe error messages to database job records.
- **Idempotency**:
  - Reprocessing or re-analyzing a contract version clears prior text chunks or risk findings before bulk-inserting new records, ensuring duplicate executions do not duplicate database rows.
