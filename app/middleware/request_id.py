"""Request ID Correlation Middleware.

Extracts or generates a unique correlation ID for every incoming HTTP request:
- Accepts incoming X-Request-ID header if valid (alphanumeric, hyphens, underscores, <= 64 chars).
- Generates a UUID4 if missing, malformed, or oversized.
- Binds request_id to structlog context vars for log correlation across the request lifecycle.
- Adds X-Request-ID header to the HTTP response.
"""

import re
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import get_logger, request_id_ctx

logger = get_logger(__name__)

# Valid request ID pattern: alphanumeric, hyphens, underscores; 1-64 chars
VALID_REQUEST_ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def validate_or_generate_request_id(incoming_id: str | None) -> str:
    """Validate incoming request ID format or generate a UUID4.

    Replaces malformed or oversized IDs to prevent header injection / log spoofing.
    """
    if incoming_id and VALID_REQUEST_ID_REGEX.match(incoming_id):
        return incoming_id
    return str(uuid.uuid4())


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware for injecting and propagating request correlation IDs."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        raw_header = request.headers.get("X-Request-ID")
        req_id = validate_or_generate_request_id(raw_header)
        token = request_id_ctx.set(req_id)

        start = time.perf_counter()
        response: Response | None = None
        try:
            response = await call_next(request)
        except Exception:
            from app.core.exceptions import _make_error_response

            response = _make_error_response(
                status_code=500,
                code="INTERNAL_ERROR",
                message="An internal error occurred. Please try again later.",
                request=request,
            )
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            request_id_ctx.reset(token)
            logger.info(
                "Request completed",
                method=request.method,
                path=request.url.path,
                status_code=getattr(response, "status_code", 500) if response else 500,
                duration_ms=round(duration_ms, 2),
            )

        if response is not None:
            response.headers["X-Request-ID"] = req_id
            return response
        raise RuntimeError("Request handling did not produce a response")
