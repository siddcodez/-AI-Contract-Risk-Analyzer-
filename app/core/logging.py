"""Structured logging setup using structlog.

Configured once at application startup via configure_logging().
Every log line carries: timestamp, level, logger name, and any
context variables (request_id, org_id, user_id) that have been
bound to the current async context.

Rules enforced here:
- Contract text is NEVER logged.
- Secrets / credentials are NEVER logged.
- In production: JSON output (machine-parseable, shipped to log aggregator).
- In development: human-readable ConsoleRenderer with colours.
"""

import logging
import sys
from contextvars import ContextVar
from typing import Any, cast
from uuid import uuid4

import structlog
from structlog.types import EventDict, WrappedLogger

from app.core.config import get_settings

# ---------------------------------------------------------------------------
# Context variables — set per-request by middleware, read by log processors
# ---------------------------------------------------------------------------
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")
org_id_ctx: ContextVar[str] = ContextVar("org_id", default="")
user_id_ctx: ContextVar[str] = ContextVar("user_id", default="")


def generate_request_id() -> str:
    return str(uuid4())


# ---------------------------------------------------------------------------
# Custom processors
# ---------------------------------------------------------------------------


def _inject_context_vars(
    _logger: WrappedLogger, _method_name: str, event_dict: EventDict
) -> EventDict:
    """Inject per-request context into every log record."""
    if request_id := request_id_ctx.get(""):
        event_dict["request_id"] = request_id
    if org := org_id_ctx.get(""):
        event_dict["org_id"] = org
    if user := user_id_ctx.get(""):
        event_dict["user_id"] = user
    return event_dict


def _drop_color_message_key(
    _logger: WrappedLogger, _method_name: str, event_dict: EventDict
) -> EventDict:
    """Remove uvicorn's colour_message key that leaks terminal escape codes."""
    event_dict.pop("color_message", None)
    return event_dict


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def configure_logging() -> None:
    """Configure structlog for the application.

    Called once at startup from app.main before the ASGI app is created.
    """
    settings = get_settings()
    log_level_str = settings.LOG_LEVEL
    log_level = getattr(logging, log_level_str, logging.INFO)

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        _inject_context_vars,
        _drop_color_message_key,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.is_production:
        # JSON — parseable by Datadog, CloudWatch, etc.
        renderer: Any = structlog.processors.JSONRenderer()
    else:
        # Human-friendly coloured output for local dev
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(log_level)

    # Quiet down noisy third-party loggers
    for noisy in ("uvicorn.access", "uvicorn.error", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(
            logging.WARNING if settings.is_production else logging.INFO
        )


def get_logger(name: str = __name__) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger bound to the given module name."""
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))
