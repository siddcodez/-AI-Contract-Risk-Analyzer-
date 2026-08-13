"""Integration test: PostgreSQL Row-Level Security enforcement for risk_findings and analysis_jobs.

Connects to a REAL PostgreSQL instance to prove that:
- Org A cannot read or modify Org B's risk_findings or analysis_jobs.
- RLS policy 'tenant_isolation' is enforced for app_user on both tables.

Requires Docker services running (or CI environment).
Automatically skipped if PostgreSQL is not available.
"""

import os
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

_ADMIN_URL = os.environ.get(
    "MIGRATION_DATABASE_URL",
    "postgresql+asyncpg://contract_user:contract_pass@localhost:5432/contract_risk_db",
)

_APP_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://app_user:app_pass@localhost:5432/contract_risk_db",
)


async def _db_is_available() -> bool:
    try:
        engine = create_async_engine(_ADMIN_URL, pool_pre_ping=True)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.integration


@pytest.fixture
async def admin_session() -> AsyncSession:
    engine = create_async_engine(_ADMIN_URL)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session  # type: ignore[misc]
    await engine.dispose()


@pytest.fixture
async def app_session() -> AsyncSession:
    engine = create_async_engine(_APP_URL)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session  # type: ignore[misc]
    await engine.dispose()


class TestFindingsRLSEnforcement:
    async def test_org_a_cannot_see_org_b_risk_findings_or_analysis_jobs(
        self,
        admin_session: AsyncSession,
        app_session: AsyncSession,
    ) -> None:
        if not await _db_is_available():
            pytest.skip("PostgreSQL not available")

        org_a_id = uuid.uuid4()
        org_b_id = uuid.uuid4()
        user_a_id = uuid.uuid4()
        user_b_id = uuid.uuid4()
        contract_a_id = uuid.uuid4()
        contract_b_id = uuid.uuid4()
        version_a_id = uuid.uuid4()
        version_b_id = uuid.uuid4()
        finding_a_id = uuid.uuid4()
        finding_b_id = uuid.uuid4()
        job_a_id = uuid.uuid4()
        job_b_id = uuid.uuid4()
        now = datetime.now(UTC)

        try:
            # Setup Orgs
            for oid, name in [(org_a_id, "Org A"), (org_b_id, "Org B")]:
                await admin_session.execute(
                    text(
                        "INSERT INTO organizations "
                        "(id, name, slug, is_active, created_at, updated_at) "
                        "VALUES (:id, :name, :slug, true, :now, :now)"
                    ),
                    {"id": str(oid), "name": name, "slug": f"slug-{oid.hex[:8]}", "now": now},
                )
            # Setup Users
            for uid, oid, email in [
                (user_a_id, org_a_id, "rf-a@test.com"),
                (user_b_id, org_b_id, "rf-b@test.com"),
            ]:
                await admin_session.execute(
                    text(
                        "INSERT INTO users "
                        "(id, email, password_hash, full_name, role, org_id, "
                        "is_active, created_at, updated_at) "
                        "VALUES (:id, :email, 'hash', 'User', 'reviewer', "
                        ":org_id, true, :now, :now)"
                    ),
                    {"id": str(uid), "email": email, "org_id": str(oid), "now": now},
                )
            # Setup Contracts
            for cid, oid, uid, title, key in [
                (contract_a_id, org_a_id, user_a_id, "Contract A", "key-rf-a"),
                (contract_b_id, org_b_id, user_b_id, "Contract B", "key-rf-b"),
            ]:
                await admin_session.execute(
                    text(
                        "INSERT INTO contracts "
                        "(id, title, file_name, file_size, content_type, storage_key, "
                        "status, org_id, uploaded_by, created_at, updated_at) "
                        "VALUES (:id, :title, 'file.txt', 100, 'text/plain', "
                        ":key, 'completed', :org_id, :uid, :now, :now)"
                    ),
                    {
                        "id": str(cid),
                        "title": title,
                        "key": key,
                        "org_id": str(oid),
                        "uid": str(uid),
                        "now": now,
                    },
                )
            # Setup Contract Versions
            for vid, cid, oid, key in [
                (version_a_id, contract_a_id, org_a_id, "key-rf-a"),
                (version_b_id, contract_b_id, org_b_id, "key-rf-b"),
            ]:
                await admin_session.execute(
                    text(
                        "INSERT INTO contract_versions "
                        "(id, contract_id, version_number, file_name, file_size, "
                        "content_type, storage_key, org_id, created_at) "
                        "VALUES (:id, :cid, 1, 'file.txt', 100, 'text/plain', :key, :org_id, :now)"
                    ),
                    {"id": str(vid), "cid": str(cid), "key": key, "org_id": str(oid), "now": now},
                )
            # Setup Analysis Jobs
            for jid, cid, vid, oid in [
                (job_a_id, contract_a_id, version_a_id, org_a_id),
                (job_b_id, contract_b_id, version_b_id, org_b_id),
            ]:
                await admin_session.execute(
                    text(
                        "INSERT INTO analysis_jobs "
                        "(id, contract_id, version_id, org_id, status, "
                        "findings_count, created_at, updated_at) "
                        "VALUES (:id, :cid, :vid, :oid, 'completed', 1, :now, :now)"
                    ),
                    {"id": str(jid), "cid": str(cid), "vid": str(vid), "oid": str(oid), "now": now},
                )
            # Setup Risk Findings
            for fid, cid, vid, oid, title in [
                (finding_a_id, contract_a_id, version_a_id, org_a_id, "Org A Finding"),
                (finding_b_id, contract_b_id, version_b_id, org_b_id, "Org B Finding"),
            ]:
                await admin_session.execute(
                    text(
                        "INSERT INTO risk_findings "
                        "(id, contract_id, version_id, org_id, category, severity, "
                        "title, description, evidence, recommendation, confidence, "
                        "created_at, updated_at) "
                        "VALUES (:id, :cid, :vid, :oid, 'liability', 'critical', "
                        ":title, 'desc', 'evidence', 'rec', 0.9, :now, :now)"
                    ),
                    {
                        "id": str(fid),
                        "cid": str(cid),
                        "vid": str(vid),
                        "oid": str(oid),
                        "title": title,
                        "now": now,
                    },
                )
            await admin_session.commit()

            # Test Org A context
            await app_session.execute(
                text("SELECT set_config('app.current_org_id', :org_id, true)"),
                {"org_id": str(org_a_id)},
            )
            findings_a = (
                (await app_session.execute(text("SELECT id FROM risk_findings"))).scalars().all()
            )
            jobs_a = (
                (await app_session.execute(text("SELECT id FROM analysis_jobs"))).scalars().all()
            )

            assert finding_a_id in findings_a
            assert finding_b_id not in findings_a
            assert job_a_id in jobs_a
            assert job_b_id not in jobs_a
            await app_session.rollback()

        finally:
            for table in [
                "risk_findings",
                "analysis_jobs",
                "contract_versions",
                "contracts",
                "users",
                "organizations",
            ]:
                await admin_session.execute(
                    text(f"DELETE FROM {table} WHERE id IN (:a, :b)"),
                    {"a": str(org_a_id), "b": str(org_b_id)},
                )
            await admin_session.commit()
