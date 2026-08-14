"""Tests for API rate limiting and abuse protection."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.core.config import get_settings
from app.core.exceptions import RateLimitError
from app.core.rate_limit import check_rate_limit, parse_rate_limit


def test_parse_rate_limit() -> None:
    count, window = parse_rate_limit("10/minute")
    assert count == 10
    assert window == 60

    count, window = parse_rate_limit("5/second")
    assert count == 5
    assert window == 1

    count, window = parse_rate_limit("100/hour")
    assert count == 100
    assert window == 3600


@pytest.mark.asyncio
async def test_rate_limit_disabled_in_test_mode() -> None:
    get_settings.cache_clear()
    settings = get_settings()
    with patch.object(settings, "RATE_LIMIT_ENABLED", False):
        await check_rate_limit("test_key_1", "1/minute")
        await check_rate_limit("test_key_1", "1/minute")


@pytest.mark.asyncio
async def test_rate_limit_exceeded_in_memory_fallback() -> None:
    get_settings.cache_clear()
    settings = get_settings()
    with (
        patch.object(settings, "ENVIRONMENT", "development"),
        patch.object(settings, "RATE_LIMIT_ENABLED", True),
        patch("redis.asyncio.Redis.from_url", side_effect=Exception("Redis offline")),
    ):
        key = "test_user_exceed"
        spec = "2/minute"

        # First 2 allowed
        await check_rate_limit(key, spec)
        await check_rate_limit(key, spec)

        # 3rd request exceeds limit
        with pytest.raises(RateLimitError) as exc_info:
            await check_rate_limit(key, spec)

        assert "Rate limit exceeded" in str(exc_info.value)
        assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_rate_limit_redis_success() -> None:
    get_settings.cache_clear()
    settings = get_settings()
    mock_pipe = MagicMock()
    mock_pipe.execute = AsyncMock(return_value=[0, 1, 1, True])
    mock_redis = AsyncMock()
    mock_redis.pipeline = MagicMock(return_value=mock_pipe)
    mock_redis.aclose = AsyncMock()

    with (
        patch.object(settings, "ENVIRONMENT", "development"),
        patch.object(settings, "RATE_LIMIT_ENABLED", True),
        patch("redis.asyncio.Redis.from_url", return_value=mock_redis),
    ):
        await check_rate_limit("test_user_redis", "5/minute")
        assert mock_pipe.zadd.called
