"""Tests for GET /api/v1/health.

These are unit tests — all backing service checks are mocked so the tests:
- Run without Docker or any real dependencies.
- Are fast (no network).
- Test the endpoint's *logic* (status aggregation, response shape).

Integration tests (with real services) are tagged @pytest.mark.slow
and run only in CI where Docker services are available.
"""

from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

# ---------------------------------------------------------------------------
# Helpers — patch targets match the module where the names are looked up
# ---------------------------------------------------------------------------

DB_CHECK = "app.api.v1.health.check_db_connection"
REDIS_CHECK = "app.api.v1.health._check_redis"
STORAGE_CHECK = "app.api.v1.health._check_storage"


class TestHealthAllOk:
    """All backing services healthy → status: ok."""

    async def test_returns_200(self, async_client: AsyncClient) -> None:
        with (
            patch(DB_CHECK, new_callable=AsyncMock, return_value=True),
            patch(REDIS_CHECK, new_callable=AsyncMock, return_value=True),
            patch(STORAGE_CHECK, new_callable=AsyncMock, return_value=True),
        ):
            response = await async_client.get("/api/v1/health")

        assert response.status_code == 200

    async def test_overall_status_is_ok(self, async_client: AsyncClient) -> None:
        with (
            patch(DB_CHECK, new_callable=AsyncMock, return_value=True),
            patch(REDIS_CHECK, new_callable=AsyncMock, return_value=True),
            patch(STORAGE_CHECK, new_callable=AsyncMock, return_value=True),
        ):
            response = await async_client.get("/api/v1/health")

        body = response.json()
        assert body["status"] == "ok"

    async def test_all_services_ok(self, async_client: AsyncClient) -> None:
        with (
            patch(DB_CHECK, new_callable=AsyncMock, return_value=True),
            patch(REDIS_CHECK, new_callable=AsyncMock, return_value=True),
            patch(STORAGE_CHECK, new_callable=AsyncMock, return_value=True),
        ):
            response = await async_client.get("/api/v1/health")

        body = response.json()
        assert body["services"]["db"] == "ok"
        assert body["services"]["redis"] == "ok"
        assert body["services"]["storage"] == "ok"

    async def test_version_present(self, async_client: AsyncClient) -> None:
        with (
            patch(DB_CHECK, new_callable=AsyncMock, return_value=True),
            patch(REDIS_CHECK, new_callable=AsyncMock, return_value=True),
            patch(STORAGE_CHECK, new_callable=AsyncMock, return_value=True),
        ):
            response = await async_client.get("/api/v1/health")

        body = response.json()
        assert "version" in body
        assert body["version"] == "0.1.0"

    async def test_environment_present(self, async_client: AsyncClient) -> None:
        with (
            patch(DB_CHECK, new_callable=AsyncMock, return_value=True),
            patch(REDIS_CHECK, new_callable=AsyncMock, return_value=True),
            patch(STORAGE_CHECK, new_callable=AsyncMock, return_value=True),
        ):
            response = await async_client.get("/api/v1/health")

        body = response.json()
        assert body["environment"] == "development"


class TestHealthDbDown:
    """DB down → status: degraded, but endpoint still returns 200."""

    async def test_still_returns_200(self, async_client: AsyncClient) -> None:
        with (
            patch(DB_CHECK, new_callable=AsyncMock, return_value=False),
            patch(REDIS_CHECK, new_callable=AsyncMock, return_value=True),
            patch(STORAGE_CHECK, new_callable=AsyncMock, return_value=True),
        ):
            response = await async_client.get("/api/v1/health")

        assert response.status_code == 200

    async def test_overall_status_is_degraded(self, async_client: AsyncClient) -> None:
        with (
            patch(DB_CHECK, new_callable=AsyncMock, return_value=False),
            patch(REDIS_CHECK, new_callable=AsyncMock, return_value=True),
            patch(STORAGE_CHECK, new_callable=AsyncMock, return_value=True),
        ):
            response = await async_client.get("/api/v1/health")

        body = response.json()
        assert body["status"] == "degraded"

    async def test_db_service_shows_error(self, async_client: AsyncClient) -> None:
        with (
            patch(DB_CHECK, new_callable=AsyncMock, return_value=False),
            patch(REDIS_CHECK, new_callable=AsyncMock, return_value=True),
            patch(STORAGE_CHECK, new_callable=AsyncMock, return_value=True),
        ):
            response = await async_client.get("/api/v1/health")

        body = response.json()
        assert body["services"]["db"] == "error"
        assert body["services"]["redis"] == "ok"
        assert body["services"]["storage"] == "ok"


class TestHealthAllDown:
    """All services down → degraded but 200."""

    async def test_all_services_error(self, async_client: AsyncClient) -> None:
        with (
            patch(DB_CHECK, new_callable=AsyncMock, return_value=False),
            patch(REDIS_CHECK, new_callable=AsyncMock, return_value=False),
            patch(STORAGE_CHECK, new_callable=AsyncMock, return_value=False),
        ):
            response = await async_client.get("/api/v1/health")

        body = response.json()
        assert response.status_code == 200
        assert body["status"] == "degraded"
        assert all(v == "error" for v in body["services"].values())


class TestHealthResponseShape:
    """Response always has the expected envelope shape."""

    async def test_required_keys_present(self, async_client: AsyncClient) -> None:
        with (
            patch(DB_CHECK, new_callable=AsyncMock, return_value=True),
            patch(REDIS_CHECK, new_callable=AsyncMock, return_value=True),
            patch(STORAGE_CHECK, new_callable=AsyncMock, return_value=True),
        ):
            response = await async_client.get("/api/v1/health")

        body = response.json()
        assert set(body.keys()) == {"status", "version", "environment", "services"}
        assert set(body["services"].keys()) == {"db", "redis", "storage"}


class TestLivenessProbe:
    """GET /health lightweight liveness check."""

    async def test_liveness_returns_200(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert "version" in body


class TestReadinessProbe:
    """GET /ready readiness check."""

    async def test_readiness_healthy_returns_200(self, async_client: AsyncClient) -> None:
        with (
            patch(DB_CHECK, new_callable=AsyncMock, return_value=True),
            patch(REDIS_CHECK, new_callable=AsyncMock, return_value=True),
            patch(STORAGE_CHECK, new_callable=AsyncMock, return_value=True),
        ):
            response = await async_client.get("/ready")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["dependencies"]["database"] == "ok"
        assert body["dependencies"]["redis"] == "ok"
        assert body["dependencies"]["storage"] == "ok"

    async def test_readiness_degraded_returns_503(self, async_client: AsyncClient) -> None:
        with (
            patch(DB_CHECK, new_callable=AsyncMock, return_value=False),
            patch(REDIS_CHECK, new_callable=AsyncMock, return_value=True),
            patch(STORAGE_CHECK, new_callable=AsyncMock, return_value=True),
        ):
            response = await async_client.get("/ready")

        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "degraded"
        assert body["dependencies"]["database"] == "error"
        assert body["dependencies"]["redis"] == "ok"

    async def test_readiness_with_workers_flag(self, async_client: AsyncClient) -> None:
        with (
            patch(DB_CHECK, new_callable=AsyncMock, return_value=True),
            patch(REDIS_CHECK, new_callable=AsyncMock, return_value=True),
            patch(STORAGE_CHECK, new_callable=AsyncMock, return_value=True),
            patch(
                "app.api.v1.health._check_celery_worker", new_callable=AsyncMock, return_value=True
            ),
        ):
            response = await async_client.get("/ready?include_workers=true")

        assert response.status_code == 200
        body = response.json()
        assert body["dependencies"]["workers"] == "ok"
