"""AI contract risk analysis service.

Orchestrates contract risk analysis execution for an AnalysisJob:
queued → processing → completed | failed.
Loads text chunks, invokes the LLM risk detection engine, stores findings,
and maintains idempotency.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.db.session import set_tenant_context
from app.models.analysis_job import AnalysisJob, AnalysisJobStatus
from app.repositories import (
    analysis_job_repo,
    contract_chunk_repo,
    contract_version_repo,
    risk_finding_repo,
)
from app.services import llm_service

logger = get_logger(__name__)


async def trigger_analysis(
    session: AsyncSession,
    *,
    contract_id: uuid.UUID,
    org_id: uuid.UUID,
) -> AnalysisJob:
    """Create a new AnalysisJob in queued status and dispatch Celery worker task.

    Args:
        session: Active database session.
        contract_id: UUID of the target contract.
        org_id: Organization UUID for RLS context.

    Returns:
        Created AnalysisJob.
    """
    versions = await contract_version_repo.list_by_contract(session, contract_id)
    if not versions:
        raise NotFoundError(f"No contract versions found for contract {contract_id}")
    latest_version = versions[-1]

    job = await analysis_job_repo.create(
        session,
        contract_id=contract_id,
        version_id=latest_version.id,
        org_id=org_id,
    )
    await session.commit()

    try:
        from app.workers.tasks import analyze_contract_job

        analyze_contract_job.delay(str(job.id))
    except Exception as exc:
        logger.error(
            "Failed to enqueue analyze_contract_job",
            analysis_job_id=str(job.id),
            exc_info=exc,
        )

    return job


async def analyze_contract(
    session: AsyncSession,
    analysis_job_id: uuid.UUID,
) -> AnalysisJob:
    """Execute AI risk analysis for a given AnalysisJob ID.

    Flow:
        1. Load AnalysisJob and set RLS tenant context.
        2. Guard against duplicate execution (if already completed).
        3. Mark AnalysisJob status = processing & COMMIT transaction.
        4. Load contract text chunks.
        5. Invoke LLM risk analysis engine.
        6. Delete previous risk findings for version (idempotency).
        7. Bulk insert detected RiskFinding records.
        8. Mark AnalysisJob status = completed with findings count & COMMIT transaction.

    On error:
        - Roll back findings transaction.
        - Mark AnalysisJob status = failed with safe error message & COMMIT transaction.

    Args:
        session: Active database session.
        analysis_job_id: UUID of the AnalysisJob.

    Returns:
        Updated AnalysisJob record.
    """
    job = await analysis_job_repo.get_by_id(session, analysis_job_id)
    if job is None:
        raise NotFoundError(f"AnalysisJob {analysis_job_id} not found")

    await set_tenant_context(session, str(job.org_id))

    if job.status == AnalysisJobStatus.completed:
        logger.info("AnalysisJob already completed, skipping", job_id=str(analysis_job_id))
        return job

    # Update to processing & commit early boundary
    now = datetime.now(UTC)
    await analysis_job_repo.update_status(session, analysis_job_id, AnalysisJobStatus.processing)
    job.started_at = now
    await session.commit()

    await set_tenant_context(session, str(job.org_id))

    try:
        # Load text chunks
        chunks = await contract_chunk_repo.list_by_contract(session, job.contract_id)
        chunks_data = [
            {"id": c.id, "chunk_index": c.chunk_index, "content": c.content} for c in chunks
        ]

        # Analyze text
        raw_findings = llm_service.analyze_contract_text(chunks_data)

        # Clear old findings (for idempotency)
        await risk_finding_repo.delete_by_contract_and_version(
            session, job.contract_id, job.version_id
        )

        # Build RiskFinding records with M5 RAG grounding
        from app.services import retrieval_service

        findings_rows = []
        for f in raw_findings:
            chunk_id = f.get("chunk_id")
            metadata_json = dict(f.get("metadata_json") or {})
            evidence_text = f.get("evidence", "")

            if evidence_text:
                try:
                    grounded_results = await retrieval_service.search_chunks(
                        session,
                        evidence_text,
                        contract_id=job.contract_id,
                        version_id=job.version_id,
                        top_k=1,
                    )
                    if grounded_results:
                        top_match = grounded_results[0]
                        if chunk_id is None:
                            chunk_id = top_match["chunk_id"]
                        metadata_json["grounding"] = {
                            "chunk_id": str(top_match["chunk_id"]),
                            "chunk_index": top_match["chunk_index"],
                            "similarity_score": top_match["similarity_score"],
                        }
                except Exception as g_exc:
                    logger.warning(
                        "Failed to ground risk finding with similarity search",
                        finding_title=f.get("title"),
                        exc_info=g_exc,
                    )

            findings_rows.append(
                {
                    "id": uuid.uuid4(),
                    "contract_id": job.contract_id,
                    "version_id": job.version_id,
                    "org_id": job.org_id,
                    "chunk_id": chunk_id,
                    "category": f["category"],
                    "severity": f["severity"],
                    "title": f["title"],
                    "description": f["description"],
                    "evidence": f["evidence"],
                    "recommendation": f["recommendation"],
                    "confidence": f["confidence"],
                    "metadata_json": metadata_json if metadata_json else None,
                }
            )

        await risk_finding_repo.bulk_create(session, findings_data=findings_rows)

        # Complete job
        finish_time = datetime.now(UTC)
        job.status = AnalysisJobStatus.completed
        job.completed_at = finish_time
        job.findings_count = len(findings_rows)
        job.error_message = None

        await session.commit()

        logger.info(
            "Contract risk analysis completed",
            analysis_job_id=str(analysis_job_id),
            contract_id=str(job.contract_id),
            findings_count=len(findings_rows),
        )
        return job

    except Exception as exc:
        logger.error("AnalysisJob execution failed", job_id=str(analysis_job_id), exc_info=exc)
        await session.rollback()

        await set_tenant_context(session, str(job.org_id))
        safe_error = _format_safe_error(exc)

        await analysis_job_repo.update_status(
            session,
            analysis_job_id,
            AnalysisJobStatus.failed,
            error_message=safe_error,
        )
        await session.commit()

        raise


# Backward compatibility alias
run_analysis = analyze_contract


def _format_safe_error(exc: Exception) -> str:
    """Format an exception into a safe human-readable string for clients."""
    err_str = str(exc)
    if (
        "key" in err_str.lower()
        or "token" in err_str.lower()
        or "password" in err_str.lower()
        or "secret" in err_str.lower()
    ):
        return f"{exc.__class__.__name__}: Analysis encountered an internal error"
    return f"{exc.__class__.__name__}: {err_str}" if err_str else exc.__class__.__name__
