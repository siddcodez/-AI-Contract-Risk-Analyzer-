# =============================================================================
# Stage 1: Build & Dependency Base
# =============================================================================
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY app/ ./app/

# Install python package and all runtime dependencies into virtual environment
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip && \
    /opt/venv/bin/pip install --no-cache-dir -e .


# =============================================================================
# Stage 2: Minimal Runtime Base
# =============================================================================
FROM python:3.12-slim AS runtime-base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root application user
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/bash -m appuser

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

COPY alembic.ini ./
COPY alembic/ ./alembic/
COPY app/ ./app/

RUN chown -R appuser:appgroup /app

USER appuser


# =============================================================================
# Target: API (FastAPI with Uvicorn)
# =============================================================================
FROM runtime-base AS api

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]


# =============================================================================
# Target: Worker (Celery background processing)
# =============================================================================
FROM runtime-base AS worker

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD celery -A app.workers.celery_app inspect ping -d celery@$HOSTNAME || exit 1

CMD ["celery", "-A", "app.workers.celery_app", "worker", "-l", "info", "-c", "2"]
