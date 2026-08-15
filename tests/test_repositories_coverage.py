"""Targeted unit tests for all repository modules:
- risk_finding_repo
- audit_log_repo
- report_job_repo
- organization_repo
- user_repo
- contract_repo
- contract_chunk_repo
- comparison_repo
- missing_clause_repo
- processing_job_repo
- analysis_job_repo
- contract_version_repo
- review_action_repo
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.models.analysis_job import AnalysisJob, AnalysisJobStatus
from app.models.contract import Contract, ContractStatus
from app.models.contract_chunk import ContractChunk
from app.models.contract_comparison import ContractComparison
from app.models.contract_version import ContractVersion
from app.models.missing_clause import MissingClause
from app.models.organization import Organization
from app.models.processing_job import JobStatus, ProcessingJob
from app.models.report_job import ReportJobStatus
from app.models.review_action import ReviewAction
from app.models.risk_finding import RiskCategory, RiskFinding, RiskSeverity
from app.models.user import User, UserRole
from app.repositories import (
    analysis_job_repo,
    audit_log_repo,
    comparison_repo,
    contract_chunk_repo,
    contract_repo,
    contract_version_repo,
    missing_clause_repo,
    organization_repo,
    processing_job_repo,
    report_job_repo,
    review_action_repo,
    risk_finding_repo,
    user_repo,
)

# ---------------------------------------------------------------------------
# 1. Risk Finding Repo Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_risk_finding_repo_crud_and_counts() -> None:
    session = AsyncMock()
    cid = uuid.uuid4()
    vid = uuid.uuid4()
    oid = uuid.uuid4()

    finding = RiskFinding(
        id=uuid.uuid4(),
        contract_id=cid,
        version_id=vid,
        org_id=oid,
        category="liability",
        severity="critical",
        title="Unlimited Liability",
        description="High risk clause",
        evidence="Quote",
        recommendation="Cap liability",
        confidence=0.95,
    )

    # 1. bulk_create
    res_bulk = await risk_finding_repo.bulk_create(
        session,
        findings_data=[
            {
                "id": finding.id,
                "contract_id": cid,
                "version_id": vid,
                "org_id": oid,
                "category": "liability",
                "severity": "critical",
                "title": "Unlimited Liability",
                "description": "desc",
                "evidence": "ev",
                "recommendation": "rec",
                "confidence": 0.9,
            }
        ],
    )
    assert len(res_bulk) == 1

    # 2. get_by_id
    mock_result = MagicMock()
    mock_result.scalars().first.return_value = finding
    session.execute.return_value = mock_result
    res_get = await risk_finding_repo.get_by_id(session, finding.id)
    assert res_get == finding

    # 3. list_by_contract_and_version
    mock_list_result = MagicMock()
    mock_list_result.scalars().all.return_value = [finding]
    session.execute.return_value = mock_list_result
    res_list = await risk_finding_repo.list_by_contract_and_version(session, cid, vid)
    assert len(res_list) == 1

    # 4. count_by_contract
    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 5
    session.execute.return_value = mock_count_result
    count = await risk_finding_repo.count_by_contract(
        session,
        cid,
        category=RiskCategory.liability,
        severity=RiskSeverity.critical,
    )
    assert count == 5

    # 5. get_summary_by_contract
    mock_summary_result = MagicMock()
    mock_summary_result.all.return_value = [("critical", 2), ("high", 3)]
    session.execute.return_value = mock_summary_result
    summary = await risk_finding_repo.get_summary_by_contract(session, cid)
    assert summary["critical"] == 2
    assert summary["high"] == 3
    assert summary["total"] == 5


# ---------------------------------------------------------------------------
# 2. Audit Log Repo Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audit_log_repo_create_and_filters() -> None:
    session = AsyncMock()
    oid = uuid.uuid4()
    uid = uuid.uuid4()

    # 1. create
    log = await audit_log_repo.create(
        session,
        org_id=oid,
        action="review_finding_approved",
        entity_type="risk_finding",
        user_id=uid,
        user_email="user@test.com",
    )
    assert log.action == "review_finding_approved"

    # 2. list_audit_logs with filters
    mock_list_res = MagicMock()
    mock_list_res.scalars().all.return_value = [log]
    session.execute.return_value = mock_list_res
    logs = await audit_log_repo.list_audit_logs(
        session,
        action="review_finding_approved",
        entity_type="risk_finding",
        skip=0,
        limit=10,
    )
    assert len(logs) == 1

    # 3. count_audit_logs
    mock_cnt_res = MagicMock()
    mock_cnt_res.scalar.return_value = 1
    session.execute.return_value = mock_cnt_res
    cnt = await audit_log_repo.count_audit_logs(session, action="review_finding_approved")
    assert cnt == 1


# ---------------------------------------------------------------------------
# 3. Report Job Repo Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_report_job_repo_create_get_and_transitions() -> None:
    session = AsyncMock()
    cid = uuid.uuid4()
    vid = uuid.uuid4()
    oid = uuid.uuid4()

    # 1. create
    job = await report_job_repo.create(session, contract_id=cid, version_id=vid, org_id=oid)
    assert job.status == ReportJobStatus.queued

    # 2. get_by_id
    mock_get_res = MagicMock()
    mock_get_res.scalars().first.return_value = job
    session.execute.return_value = mock_get_res
    res_get = await report_job_repo.get_by_id(session, job.id)
    assert res_get == job

    # 3. get_latest_by_contract_and_version
    mock_latest_res = MagicMock()
    mock_latest_res.scalars().first.return_value = job
    session.execute.return_value = mock_latest_res
    res_latest = await report_job_repo.get_latest_by_contract_and_version(session, cid, vid)
    assert res_latest == job

    # 4. update_status to processing
    res_proc = await report_job_repo.update_status(session, job, ReportJobStatus.processing)
    assert res_proc.status == "processing"
    assert res_proc.started_at is not None

    # 5. update_status to completed with artifacts
    res_comp = await report_job_repo.update_status(
        session,
        job,
        ReportJobStatus.completed,
        storage_key="reports/v1.pdf",
        file_size=5000,
    )
    assert res_comp.status == "completed"
    assert res_comp.storage_key == "reports/v1.pdf"
    assert res_comp.file_size == 5000
    assert res_comp.completed_at is not None

    # 6. update_status to failed
    res_failed = await report_job_repo.update_status(
        session,
        job,
        ReportJobStatus.failed,
        error_message="PDF generation timeout",
    )
    assert res_failed.status == "failed"
    assert res_failed.error_message == "PDF generation timeout"


# ---------------------------------------------------------------------------
# 4. Organization Repo Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_organization_repo_slug_and_crud() -> None:
    session = AsyncMock()
    org_id = uuid.uuid4()
    org = Organization(id=org_id, name="Acme Corp", slug="acme-corp", is_active=True)

    # 1. slug generator test
    slug1 = organization_repo.generate_slug("Acme & Co., LLC!")
    assert slug1 == "acme-co-llc"
    assert organization_repo.generate_slug("!!!") == "org"

    # 2. get_by_id
    mock_res = MagicMock()
    mock_res.scalars().first.return_value = org
    session.execute.return_value = mock_res
    res = await organization_repo.get_by_id(session, org_id)
    assert res == org

    # 3. get_by_slug
    mock_res_slug = MagicMock()
    mock_res_slug.scalars().first.return_value = org
    session.execute.return_value = mock_res_slug
    res_slug = await organization_repo.get_by_slug(session, "acme-corp")
    assert res_slug == org

    # 4. create_with_unique_slug (handles duplicate slug detection)
    with patch("app.repositories.organization_repo.get_by_slug") as mock_slug_lookup:
        # First call finds collision, second call is None (free)
        mock_slug_lookup.side_effect = [org, None]
        created = await organization_repo.create_with_unique_slug(session, name="Acme Corp")
        assert created.slug == "acme-corp-1"
        assert created.name == "Acme Corp"
        session.add.assert_called_once()
        session.flush.assert_called_once()


# ---------------------------------------------------------------------------
# 5. User Repo Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_repo_crud_and_auth() -> None:
    session = AsyncMock()
    uid = uuid.uuid4()
    oid = uuid.uuid4()
    user = User(
        id=uid,
        email="test@acme.com",
        password_hash="hash123",
        full_name="Test User",
        role=UserRole.admin,
        org_id=oid,
        is_active=True,
    )

    # 1. get_by_id
    mock_res = MagicMock()
    mock_res.scalars().first.return_value = user
    session.execute.return_value = mock_res
    res_user = await user_repo.get_by_id(session, uid)
    assert res_user == user

    # 2. create
    created_user = await user_repo.create(
        session,
        email="new@acme.com",
        password_hash="hashed",
        full_name="New User",
        role=UserRole.reviewer,
        org_id=oid,
    )
    assert created_user.email == "new@acme.com"
    assert created_user.role == UserRole.reviewer
    session.add.assert_called_once()

    # 3. get_by_email_for_auth
    row_data = {
        "id": uid,
        "email": "test@acme.com",
        "password_hash": "hash123",
        "full_name": "Test User",
        "role": "admin",
        "org_id": oid,
        "is_active": True,
        "created_at": "2026-08-15T00:00:00Z",
        "updated_at": "2026-08-15T00:00:00Z",
    }
    mock_auth_res = MagicMock()
    mock_auth_res.mappings().first.return_value = row_data
    mock_org_res = MagicMock()
    mock_org_res.scalars().first.return_value = Organization(id=oid, name="Acme", slug="acme")

    session.execute.side_effect = [mock_auth_res, mock_org_res]
    auth_user = await user_repo.get_by_email_for_auth(session, "test@acme.com")
    assert auth_user is not None
    assert auth_user.email == "test@acme.com"
    assert auth_user.organization.name == "Acme"

    # 4. email_exists
    mock_exists_res = MagicMock()
    mock_exists_res.first.return_value = (1,)
    session.execute.side_effect = None
    session.execute.return_value = mock_exists_res
    exists = await user_repo.email_exists(session, "test@acme.com")
    assert exists is True

    # 5. list_by_org
    mock_list_res = MagicMock()
    mock_list_res.scalars().all.return_value = [user]
    session.execute.return_value = mock_list_res
    user_list = await user_repo.list_by_org(session, oid)
    assert len(user_list) == 1


# ---------------------------------------------------------------------------
# 6. Contract Repo Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_contract_repo_crud_and_status() -> None:
    session = AsyncMock()
    cid = uuid.uuid4()
    oid = uuid.uuid4()
    uid = uuid.uuid4()

    contract = Contract(
        id=cid,
        title="MSA Agreement",
        file_name="msa.pdf",
        file_size=1024,
        content_type="application/pdf",
        storage_key=f"{oid}/{cid}/msa.pdf",
        org_id=oid,
        uploaded_by=uid,
        status=ContractStatus.pending,
    )

    # 1. create
    c = await contract_repo.create(
        session,
        title="MSA Agreement",
        file_name="msa.pdf",
        file_size=1024,
        content_type="application/pdf",
        storage_key=f"{oid}/{cid}/msa.pdf",
        org_id=oid,
        uploaded_by=uid,
    )
    assert c.title == "MSA Agreement"

    # 2. get_by_id
    mock_res = MagicMock()
    mock_res.scalars().first.return_value = contract
    session.execute.return_value = mock_res
    res = await contract_repo.get_by_id(session, cid)
    assert res == contract

    # 3. list_by_org
    mock_list_res = MagicMock()
    mock_list_res.scalars().all.return_value = [contract]
    session.execute.return_value = mock_list_res
    contracts = await contract_repo.list_by_org(session, oid, skip=0, limit=10)
    assert len(contracts) == 1

    # 4. count_by_org
    mock_cnt_res = MagicMock()
    mock_cnt_res.scalar.return_value = 3
    session.execute.return_value = mock_cnt_res
    cnt = await contract_repo.count_by_org(session, oid)
    assert cnt == 3

    # 5. update_status
    with patch("app.repositories.contract_repo.get_by_id", return_value=contract):
        updated = await contract_repo.update_status(session, cid, ContractStatus.completed)
        assert updated is not None
        assert updated.status == ContractStatus.completed


# ---------------------------------------------------------------------------
# 7. Contract Chunk Repo Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_contract_chunk_repo_operations() -> None:
    session = AsyncMock()
    cid = uuid.uuid4()
    vid = uuid.uuid4()
    oid = uuid.uuid4()

    chunk = ContractChunk(
        id=uuid.uuid4(),
        contract_id=cid,
        version_id=vid,
        org_id=oid,
        chunk_index=0,
        content="Limitation of liability clause text",
        token_count=10,
        embedding=[0.1] * 1536,
    )

    # 1. bulk_create
    created_chunks = await contract_chunk_repo.bulk_create(
        session,
        chunks_data=[
            {
                "contract_id": cid,
                "version_id": vid,
                "org_id": oid,
                "chunk_index": 0,
                "content": "text",
                "token_count": 5,
            }
        ],
    )
    assert len(created_chunks) == 1

    # 2. delete_by_contract_and_version
    await contract_chunk_repo.delete_by_contract_and_version(session, cid, vid)
    session.execute.assert_called()

    # 3. list_by_contract
    mock_res = MagicMock()
    mock_res.scalars().all.return_value = [chunk]
    session.execute.return_value = mock_res
    chunks = await contract_chunk_repo.list_by_contract(session, cid)
    assert len(chunks) == 1

    # 4. similarity_search
    mock_sim_res = MagicMock()
    mock_sim_res.all.return_value = [(chunk, 0.88)]
    session.execute.return_value = mock_sim_res
    sim_results = await contract_chunk_repo.similarity_search(
        session,
        query_vector=[0.1] * 1536,
        contract_id=cid,
        version_id=vid,
        top_k=3,
        min_score=0.2,
        distance_metric="cosine",
    )
    assert len(sim_results) == 1
    assert sim_results[0][1] == 0.88

    # 5. search_precedent_chunks
    mock_prec_res = MagicMock()
    mock_prec_res.all.return_value = [(chunk, "Vendor MSA", "vendor_msa.pdf", 0.92)]
    session.execute.return_value = mock_prec_res
    precedent_results = await contract_chunk_repo.search_precedent_chunks(
        session,
        query_vector=[0.1] * 1536,
        exclude_contract_id=cid,
        top_k=5,
        min_score=0.5,
    )
    assert len(precedent_results) == 1
    assert precedent_results[0][1] == "Vendor MSA"


# ---------------------------------------------------------------------------
# 8. Comparison Repo Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_comparison_repo_operations() -> None:
    session = AsyncMock()
    cid = uuid.uuid4()
    v1 = uuid.uuid4()
    v2 = uuid.uuid4()
    oid = uuid.uuid4()

    comp = ContractComparison(
        id=uuid.uuid4(),
        contract_id=cid,
        from_version_id=v1,
        to_version_id=v2,
        org_id=oid,
        risk_score_from=50,
        risk_score_to=70,
        risk_delta=20,
        clauses_added_count=2,
        clauses_removed_count=1,
        clauses_modified_count=3,
        clauses_unchanged_count=5,
        diff_summary_json=[],
    )

    # 1. create
    c = await comparison_repo.create(
        session,
        comparison_data={
            "id": comp.id,
            "contract_id": cid,
            "from_version_id": v1,
            "to_version_id": v2,
            "org_id": oid,
            "risk_score_from": 50,
            "risk_score_to": 70,
            "risk_delta": 20,
            "clauses_added_count": 2,
            "clauses_removed_count": 1,
            "clauses_modified_count": 3,
            "clauses_unchanged_count": 5,
            "diff_summary_json": [],
        },
    )
    assert c.id == comp.id

    # 2. get_by_versions
    mock_res = MagicMock()
    mock_res.scalars().first.return_value = comp
    session.execute.return_value = mock_res
    res = await comparison_repo.get_by_versions(session, cid, v1, v2)
    assert res == comp

    # 3. update_comparison
    updated = await comparison_repo.update_comparison(
        session, comp, update_data={"clauses_added_count": 5}
    )
    assert updated.clauses_added_count == 5

    # 4. delete_by_contract
    await comparison_repo.delete_by_contract(session, cid)
    session.flush.assert_called()


# ---------------------------------------------------------------------------
# 9. Missing Clause Repo Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_clause_repo_operations() -> None:
    session = AsyncMock()
    cid = uuid.uuid4()
    vid = uuid.uuid4()
    oid = uuid.uuid4()

    mc = MissingClause(
        id=uuid.uuid4(),
        contract_id=cid,
        version_id=vid,
        org_id=oid,
        clause_type="force_majeure",
        confidence=0.9,
        reason="Standard clause missing",
        status="missing",
    )

    # 1. bulk_create
    created = await missing_clause_repo.bulk_create(
        session,
        items=[
            {
                "contract_id": cid,
                "version_id": vid,
                "org_id": oid,
                "clause_type": "force_majeure",
                "confidence": 0.9,
                "reason": "missing",
                "status": "missing",
            }
        ],
    )
    assert len(created) == 1

    # 2. delete_by_contract_and_version
    await missing_clause_repo.delete_by_contract_and_version(session, cid, vid)
    session.execute.assert_called()

    # 3. list_by_contract_and_version
    mock_res = MagicMock()
    mock_res.scalars().all.return_value = [mc]
    session.execute.return_value = mock_res
    items = await missing_clause_repo.list_by_contract_and_version(session, cid, vid)
    assert len(items) == 1

    # 4. list_by_contract
    all_items = await missing_clause_repo.list_by_contract(session, cid)
    assert len(all_items) == 1


# ---------------------------------------------------------------------------
# 10. Processing Job, Analysis Job, Version & Review Repos
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_processing_job_repo_operations() -> None:
    session = AsyncMock()
    cid = uuid.uuid4()
    oid = uuid.uuid4()
    job = ProcessingJob(id=uuid.uuid4(), contract_id=cid, org_id=oid, status=JobStatus.queued)

    # 1. create
    c = await processing_job_repo.create(session, contract_id=cid, org_id=oid)
    assert c.status == JobStatus.queued

    # 2. get_by_id
    mock_res = MagicMock()
    mock_res.scalars().first.return_value = job
    session.execute.return_value = mock_res
    res = await processing_job_repo.get_by_id(session, job.id)
    assert res == job

    # 3. get_by_contract_id
    res_contract = await processing_job_repo.get_by_contract_id(session, cid)
    assert res_contract == job

    # 4. update_status
    with patch("app.repositories.processing_job_repo.get_by_id", return_value=job):
        updated = await processing_job_repo.update_status(
            session, job.id, JobStatus.failed, error_message="Parse failed"
        )
        assert updated is not None
        assert updated.status == JobStatus.failed
        assert updated.error_message == "Parse failed"


@pytest.mark.asyncio
async def test_analysis_job_repo_operations() -> None:
    session = AsyncMock()
    cid = uuid.uuid4()
    vid = uuid.uuid4()
    oid = uuid.uuid4()
    job = AnalysisJob(
        id=uuid.uuid4(),
        contract_id=cid,
        version_id=vid,
        org_id=oid,
        status=AnalysisJobStatus.queued,
    )

    # 1. create
    c = await analysis_job_repo.create(session, contract_id=cid, version_id=vid, org_id=oid)
    assert c.status == AnalysisJobStatus.queued

    # 2. get_by_id
    mock_res = MagicMock()
    mock_res.scalars().first.return_value = job
    session.execute.return_value = mock_res
    res = await analysis_job_repo.get_by_id(session, job.id)
    assert res == job

    # 3. get_latest_by_contract
    res_latest = await analysis_job_repo.get_latest_by_contract(session, cid)
    assert res_latest == job

    # 4. update_status
    with patch("app.repositories.analysis_job_repo.get_by_id", return_value=job):
        updated = await analysis_job_repo.update_status(
            session,
            job.id,
            AnalysisJobStatus.completed,
            findings_count=12,
        )
        assert updated is not None
        assert updated.status == AnalysisJobStatus.completed
        assert updated.findings_count == 12


@pytest.mark.asyncio
async def test_contract_version_and_review_action_repos() -> None:
    session = AsyncMock()
    cid = uuid.uuid4()
    vid = uuid.uuid4()
    oid = uuid.uuid4()
    uid = uuid.uuid4()
    fid = uuid.uuid4()

    version = ContractVersion(
        id=vid,
        contract_id=cid,
        version_number=1,
        file_name="contract.pdf",
        file_size=100,
        content_type="application/pdf",
        storage_key="s3/key",
        org_id=oid,
    )

    # Version repo: create, list_by_contract, get_by_id, get_latest_by_contract
    v_created = await contract_version_repo.create(
        session,
        contract_id=cid,
        version_number=1,
        file_name="contract.pdf",
        file_size=100,
        content_type="application/pdf",
        storage_key="s3/key",
        org_id=oid,
    )
    assert v_created.version_number == 1

    mock_v_res = MagicMock()
    mock_v_res.scalars().all.return_value = [version]
    mock_v_res.scalars().first.return_value = version
    session.execute.return_value = mock_v_res

    v_list = await contract_version_repo.list_by_contract(session, cid)
    assert len(v_list) == 1
    v_get = await contract_version_repo.get_by_id(session, vid)
    assert v_get == version
    v_latest = await contract_version_repo.get_latest_by_contract(session, cid)
    assert v_latest == version

    # Review action repo: create, list_by_finding, list_by_contract
    review = ReviewAction(
        id=uuid.uuid4(),
        contract_id=cid,
        finding_id=fid,
        reviewer_id=uid,
        org_id=oid,
        action="dismissed",
        comment="False positive",
    )
    r_created = await review_action_repo.create(
        session,
        contract_id=cid,
        finding_id=fid,
        reviewer_id=uid,
        org_id=oid,
        action="dismissed",
        comment="False positive",
    )
    assert r_created.action == "dismissed"

    mock_r_res = MagicMock()
    mock_r_res.scalars().all.return_value = [review]
    session.execute.return_value = mock_r_res

    r_finding = await review_action_repo.list_by_finding(session, fid)
    assert len(r_finding) == 1
    r_contract = await review_action_repo.list_by_contract(session, cid)
    assert len(r_contract) == 1
