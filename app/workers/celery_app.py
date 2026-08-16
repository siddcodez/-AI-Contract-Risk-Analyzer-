"""Celery application instance.

Configured here and imported by workers and FastAPI (for enqueuing tasks).
No tasks are defined in this file — tasks live in app/workers/tasks/.

Design decisions:
- Serializer: JSON only (never pickle — pickle is an RCE risk with untrusted data).
- Timezone: UTC always.
- task_track_started=True: workers update state to STARTED when a task begins,
  giving the WebSocket endpoint a finer-grained status signal.
- Soft/hard time limits: conservative defaults, overridden per task where needed.
"""

import ssl

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

broker_url = settings.CELERY_BROKER_URL or settings.REDIS_URL
backend_url = settings.CELERY_RESULT_BACKEND or settings.REDIS_URL

ssl_conf: dict[str, object] = {}
if broker_url and broker_url.startswith("rediss://"):
    ssl_conf["broker_use_ssl"] = {"ssl_cert_reqs": ssl.CERT_NONE}
if backend_url and backend_url.startswith("rediss://"):
    ssl_conf["redis_backend_use_ssl"] = {"ssl_cert_reqs": ssl.CERT_NONE}

celery_app = Celery(
    "contract_risk",
    broker=broker_url,
    backend=backend_url,
    include=[
        "app.workers.tasks",
    ],
)

celery_app.conf.update(
    # Serialization — JSON only, no pickle
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Timezone
    timezone="UTC",
    enable_utc=True,
    task_ignore_result=True,
    # Tracking
    task_track_started=True,
    # Time limits (seconds) — tasks should override if they need more
    task_soft_time_limit=300,  # 5 min: sends SoftTimeLimitExceeded, task can clean up
    task_time_limit=360,  # 6 min: hard kill
    # Result TTL — keep results 24h (enough for status polling)
    result_expires=86400,
    # Retry policy defaults (each task can override)
    task_acks_late=True,  # ack only after the task completes — safer for retries
    task_reject_on_worker_lost=True,
    # Worker settings
    worker_prefetch_multiplier=1,  # one task at a time per worker process (LLM tasks are heavy)
    **ssl_conf,
)
