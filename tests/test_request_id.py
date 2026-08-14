"""Tests for request correlation ID middleware and validation."""

import pytest
from app.middleware.request_id import validate_or_generate_request_id
from httpx import AsyncClient


def test_validate_or_generate_request_id_valid() -> None:
    valid_id = "req_12345-abc_DEF"
    result = validate_or_generate_request_id(valid_id)
    assert result == valid_id


def test_validate_or_generate_request_id_missing() -> None:
    result = validate_or_generate_request_id(None)
    assert isinstance(result, str)
    assert len(result) == 36


def test_validate_or_generate_request_id_malformed() -> None:
    malformed_ids = [
        "invalid id with spaces",
        "req<script>alert(1)</script>",
        "req;DROP TABLE users;--",
        "x" * 70,  # oversized (>64 chars)
        "",
    ]
    for bad_id in malformed_ids:
        result = validate_or_generate_request_id(bad_id)
        assert result != bad_id
        assert len(result) == 36  # Replaced with UUID4


@pytest.mark.asyncio
async def test_middleware_generates_request_id(async_client: AsyncClient) -> None:
    response = await async_client.get("/health")
    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    req_id = response.headers["X-Request-ID"]
    assert len(req_id) == 36


@pytest.mark.asyncio
async def test_middleware_propagates_valid_request_id(async_client: AsyncClient) -> None:
    custom_id = "test-correlation-id-12345"
    response = await async_client.get("/health", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == custom_id


@pytest.mark.asyncio
async def test_middleware_replaces_malformed_request_id(async_client: AsyncClient) -> None:
    bad_id = "bad id with spaces!!!"
    response = await async_client.get("/health", headers={"X-Request-ID": bad_id})
    assert response.status_code == 200
    returned_id = response.headers["X-Request-ID"]
    assert returned_id != bad_id
    assert len(returned_id) == 36
