"""API Rate Limiting and Abuse Protection.

Provides Redis-backed rate limiting with fallback to in-memory tracking.
Key features:
- Configurable rate limits per endpoint category (upload, search, analysis).
- Tenant/user aware keying (user.id / org_id or IP address fallback).
- Relaxed / bypassable in test mode or when RATE_LIMIT_ENABLED=False.
- Raises RateLimitError (HTTP 429) when limits are exceeded.
"""

import time
from collections import defaultdict
from collections.abc import Callable
from typing import Any

import redis.asyncio as aioredis
from fastapi import Request

from app.core.config import get_settings
from app.core.exceptions import RateLimitError
from app.core.logging import get_logger

logger = get_logger(__name__)

# Fallback in-memory store: key -> list of timestamps
_in_memory_store: dict[str, list[float]] = defaultdict(list)


def parse_rate_limit(rate_limit_str: str) -> tuple[int, int]:
    """Parse string format like '10/minute', '5/second', '100/hour' into (count, window_seconds)."""
    parts = rate_limit_str.strip().lower().split("/")
    if len(parts) != 2:
        return 10, 60
    count = int(parts[0])
    unit = parts[1]
    if unit in ("second", "sec", "s"):
        window = 1
    elif unit in ("minute", "min", "m"):
        window = 60
    elif unit in ("hour", "hr", "h"):
        window = 3600
    elif unit in ("day", "d"):
        window = 86400
    else:
        window = 60
    return count, window


async def check_rate_limit(
    key: str,
    rate_limit_str: str,
) -> None:
    """Check rate limit for a given identifier key against a limit spec."""
    settings = get_settings()

    if not settings.RATE_LIMIT_ENABLED or settings.ENVIRONMENT == "test":
        return

    max_requests, window_seconds = parse_rate_limit(rate_limit_str)
    now = time.time()
    cutoff = now - window_seconds

    redis_ok = False
    try:
        redis_client = aioredis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=1)
        pipe = redis_client.pipeline()
        redis_key = f"ratelimit:{key}"
        pipe.zremrangebyscore(redis_key, 0, cutoff)
        pipe.zadd(redis_key, {str(now): now})
        pipe.zcard(redis_key)
        pipe.expire(redis_key, window_seconds)
        results = await pipe.execute()
        await redis_client.aclose()

        request_count = results[2]
        redis_ok = True

        if request_count > max_requests:
            logger.warning(
                "Rate limit exceeded (Redis)",
                key=key,
                count=request_count,
                max=max_requests,
            )
            raise RateLimitError(f"Rate limit exceeded. Maximum {rate_limit_str} allowed.")

    except RateLimitError:
        raise
    except Exception as exc:
        if redis_ok:
            raise
        logger.warning("Redis rate limit check failed, falling back to in-memory", exc_info=exc)

    # In-memory fallback
    if not redis_ok:
        timestamps = [t for t in _in_memory_store[key] if t > cutoff]
        timestamps.append(now)
        _in_memory_store[key] = timestamps
        if len(timestamps) > max_requests:
            logger.warning(
                "Rate limit exceeded (in-memory)",
                key=key,
                count=len(timestamps),
                max=max_requests,
            )
            raise RateLimitError(f"Rate limit exceeded. Maximum {rate_limit_str} allowed.")


def rate_limiter(
    category: str,
    get_limit: Callable[[], str],
) -> Callable[..., Any]:
    """Dependency factory generating rate-limit checks for routes."""

    async def _dependency(request: Request) -> None:
        settings = get_settings()
        if not settings.RATE_LIMIT_ENABLED or settings.ENVIRONMENT == "test":
            return

        # Key by user ID if authenticated, else client IP
        user_id = getattr(request.state, "user_id", None)
        if not user_id:
            client = request.client
            ip = client.host if client else "unknown"
            key = f"{category}:{ip}"
        else:
            key = f"{category}:user:{user_id}"

        limit_spec = get_limit()
        await check_rate_limit(key, limit_spec)

    return _dependency


def rate_limit_upload() -> Callable[..., Any]:
    """Rate limit dependency for upload endpoints."""
    return rate_limiter("upload", lambda: get_settings().RATE_LIMIT_UPLOAD)


def rate_limit_search() -> Callable[..., Any]:
    """Rate limit dependency for search/retrieval endpoints."""
    return rate_limiter("search", lambda: get_settings().RATE_LIMIT_SEARCH)


def rate_limit_analysis() -> Callable[..., Any]:
    """Rate limit dependency for manual analysis trigger endpoints."""
    return rate_limiter("analysis", lambda: get_settings().RATE_LIMIT_ANALYSIS)


def rate_limit_ask() -> Callable[..., Any]:
    """Rate limit dependency for grounded contract Q&A endpoints."""
    return rate_limiter("ask", lambda: get_settings().RATE_LIMIT_ASK)
