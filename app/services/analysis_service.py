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
    contract_repo,
    contract_version_repo,
    risk_finding_repo,
)
from app.services import llm_service, missing_clause_service, retrieval_service

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
        from app.core.logging import request_id_ctx
        from app.workers.tasks import analyze_contract_job

        analyze_contract_job.delay(str(job.id), request_id=request_id_ctx.get(""))
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

    logger.info(
        "analysis_started",
        analysis_job_id=str(analysis_job_id),
        contract_id=str(job.contract_id),
        org_id=str(job.org_id),
    )

    try:
        # Load text chunks
        chunks = await contract_chunk_repo.list_by_contract(session, job.contract_id)
        chunks_data = [
            {"id": c.id, "chunk_index": c.chunk_index, "content": c.content} for c in chunks
        ]

        # Analyze text
        raw_findings = llm_service.analyze_contract_text(chunks_data)
        logger.info(
            "findings_generated",
            analysis_job_id=str(analysis_job_id),
            contract_id=str(job.contract_id),
            count=len(raw_findings),
        )

        # Clear old findings (for idempotency)
        await risk_finding_repo.delete_by_contract_and_version(
            session, job.contract_id, job.version_id
        )

        # Build RiskFinding records with M5 RAG grounding
        logger.info(
            "retrieval_started",
            analysis_job_id=str(analysis_job_id),
            contract_id=str(job.contract_id),
        )
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

        logger.info(
            "retrieval_completed",
            analysis_job_id=str(analysis_job_id),
            contract_id=str(job.contract_id),
        )

        await risk_finding_repo.bulk_create(session, findings_data=findings_rows)

        # M7.2: Detect and persist missing clauses for this contract version
        try:
            contract_obj = await contract_repo.get_by_id(session, job.contract_id)
            contract_title = getattr(contract_obj, "title", "")
            if not isinstance(contract_title, str):
                contract_title = ""
            inferred_contract_type = missing_clause_service.normalize_contract_type(contract_title)

            missing_clauses = await missing_clause_service.detect_missing_clauses(
                session,
                contract_id=job.contract_id,
                version_id=job.version_id,
                org_id=job.org_id,
                contract_type=inferred_contract_type,
            )
            logger.info(
                "missing_clauses_detected",
                analysis_job_id=str(analysis_job_id),
                contract_id=str(job.contract_id),
                missing_count=len(missing_clauses),
            )
        except Exception as mc_exc:
            logger.warning(
                "Failed to detect missing clauses during analysis",
                analysis_job_id=str(analysis_job_id),
                contract_id=str(job.contract_id),
                exc_info=mc_exc,
            )

        # Complete job
        finish_time = datetime.now(UTC)
        job.status = AnalysisJobStatus.completed
        job.completed_at = finish_time
        job.findings_count = len(findings_rows)
        job.error_message = None

        await session.commit()

        # Real-time WebSocket broadcast & Notification dispatch
        try:
            from app.services.notification_service import (
                NotificationEvent,
                NotificationType,
                notification_service,
            )
            from app.services.websocket_manager import ws_manager

            cid_str = str(job.contract_id)
            await ws_manager.broadcast_event(
                contract_id=cid_str,
                event_type="ANALYSIS_COMPLETED",
                data={
                    "job_id": str(analysis_job_id),
                    "status": "completed",
                    "findings_count": len(findings_rows),
                },
            )

            # Check for high-risk findings to alert
            has_high_risk = any(f.get("severity") in ("high", "critical") for f in findings_rows)
            if has_high_risk:
                await notification_service.dispatch(
                    NotificationEvent(
                        event_type=NotificationType.HIGH_RISK_FINDING_DETECTED,
                        contract_id=cid_str,
                        contract_title=getattr(contract_obj, "title", "Contract"),
                        org_id=str(job.org_id),
                        summary=(
                            f"Detected {len(findings_rows)} risk finding(s) "
                            "with high/critical severity."
                        ),
                    )
                )
        except Exception as ws_err:
            logger.warning("event_broadcast_failed_non_fatal", error=str(ws_err))

        logger.info(
            "analysis_completed",
            analysis_job_id=str(analysis_job_id),
            contract_id=str(job.contract_id),
            findings_count=len(findings_rows),
        )
        return job

    except Exception as exc:
        logger.error(
            "analysis_failed",
            analysis_job_id=str(analysis_job_id),
            exc_info=exc,
        )
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

        try:
            from app.services.websocket_manager import ws_manager

            await ws_manager.broadcast_event(
                contract_id=str(job.contract_id),
                event_type="ANALYSIS_FAILED",
                data={"job_id": str(analysis_job_id), "status": "failed", "error": safe_error},
            )
        except Exception as ws_fail_err:
            logger.warning("analysis_failed_broadcast_failed", error=str(ws_fail_err))

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
