"""Contract report service — coordinates report data assembly, storage, and audit logs."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.models.audit_log import AuditActionType
from app.models.report_job import ReportJob, ReportJobStatus
from app.models.risk_finding import RiskFinding
from app.repositories import (
    contract_repo,
    contract_version_repo,
    missing_clause_repo,
    report_job_repo,
    review_action_repo,
    risk_finding_repo,
)
from app.services import audit_service, storage_service
from app.services.comparison_service import compute_version_risk_score
from app.services.report_generator import create_annotated_contract_pdf

logger = get_logger(__name__)


async def trigger_report_generation(
    session: AsyncSession,
    *,
    contract_id: uuid.UUID,
    version_id: uuid.UUID | None,
    org_id: uuid.UUID,
) -> ReportJob:
    """Trigger or deduplicate an async report generation job for a contract version."""
    # 1. Validate contract exists under tenant
    contract = await contract_repo.get_by_id(session, contract_id)
    if contract is None:
        raise NotFoundError("Contract not found")

    # 2. Resolve version ID
    if version_id is None:
        latest_ver = await contract_version_repo.get_latest_by_contract(session, contract_id)
        if latest_ver is None:
            raise NotFoundError("No contract versions found")
        target_version_id = latest_ver.id
    else:
        version = await contract_version_repo.get_by_id(session, version_id)
        if version is None or version.contract_id != contract_id:
            raise NotFoundError("Contract version not found")
        target_version_id = version.id

    # 3. Check for active/in-flight job (deduplication lock)
    existing = await report_job_repo.get_latest_by_contract_and_version(
        session, contract_id, target_version_id
    )
    if existing and existing.status in (ReportJobStatus.queued, ReportJobStatus.processing):
        logger.info(
            "report_generation_deduplicated",
            job_id=str(existing.id),
            contract_id=str(contract_id),
            version_id=str(target_version_id),
        )
        return existing

    # 4. Create new job record
    job = await report_job_repo.create(
        session,
        contract_id=contract_id,
        version_id=target_version_id,
        org_id=org_id,
    )
    await session.commit()
    return job


async def execute_report_generation(
    session: AsyncSession,
    *,
    job_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
    user_email: str | None = None,
    ip_address: str | None = None,
) -> ReportJob:
    """Execute the end-to-end PDF report generation, storage, and audit logging."""
    job = await report_job_repo.get_by_id(session, job_id)
    if job is None:
        raise NotFoundError("Report job not found")

    await report_job_repo.update_status(session, job, ReportJobStatus.processing)
    await session.commit()

    try:
        # Load contract & version metadata
        contract = await contract_repo.get_by_id(session, job.contract_id)
        version = await contract_version_repo.get_by_id(session, job.version_id)
        if contract is None or version is None:
            raise NotFoundError("Contract or version entity missing")

        # Load findings for this specific version
        findings: list[RiskFinding] = await risk_finding_repo.list_by_contract_and_version(
            session, job.contract_id, job.version_id
        )
        risk_score = compute_version_risk_score(findings)

        # Load missing clauses
        missing_clauses = await missing_clause_repo.list_by_contract_and_version(
            session, job.contract_id, job.version_id
        )

        # Load review actions
        reviews = await review_action_repo.list_by_contract(session, job.contract_id)

        # Transform to plain dicts for generator
        findings_data = [
            {
                "category": f.category.value if hasattr(f.category, "value") else str(f.category),
                "severity": f.severity.value if hasattr(f.severity, "value") else str(f.severity),
                "title": f.title,
                "description": f.description,
                "evidence": f.evidence,
                "recommendation": f.recommendation,
                "status": getattr(f, "status", "pending_review"),
            }
            for f in findings
        ]

        missing_data = [
            {
                "clause_type": mc.clause_type,
                "confidence": mc.confidence,
                "reason": mc.reason,
            }
            for mc in missing_clauses
        ]

        reviews_data = [
            {
                "action": r.action,
                "comment": r.comment,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in reviews
        ]

        # Generate binary PDF
        pdf_bytes = create_annotated_contract_pdf(
            contract_title=contract.title,
            file_name=version.file_name,
            version_number=version.version_number,
            risk_score=risk_score,
            findings=findings_data,
            missing_clauses=missing_data,
            reviews=reviews_data,
            org_id=str(job.org_id),
        )

        # Upload to MinIO/S3
        storage_key = (
            f"contracts/{job.org_id}/{job.contract_id}/reports/"
            f"v{version.version_number}_report_{job.id}.pdf"
        )
        storage_service.upload_file(
            file_data=pdf_bytes,
            key=storage_key,
            content_type="application/pdf",
        )

        # Update job record to completed
        await report_job_repo.update_status(
            session,
            job,
            ReportJobStatus.completed,
            storage_key=storage_key,
            file_size=len(pdf_bytes),
        )

        # Record REPORT_GENERATED in audit_logs
        await audit_service.log_audit_event(
            session,
            org_id=job.org_id,
            action=AuditActionType.REPORT_GENERATED,
            entity_type="contract_report",
            entity_id=job.id,
            user_id=user_id,
            user_email=user_email,
            metadata_json={
                "contract_id": str(job.contract_id),
                "version_id": str(job.version_id),
                "version_number": version.version_number,
                "storage_key": storage_key,
                "file_size": len(pdf_bytes),
                "findings_count": len(findings),
            },
            ip_address=ip_address,
        )

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
                event_type="REPORT_GENERATED",
                data={
                    "job_id": str(job.id),
                    "version_id": str(job.version_id),
                    "storage_key": storage_key,
                    "status": "completed",
                },
            )

            await notification_service.dispatch(
                NotificationEvent(
                    event_type=NotificationType.REPORT_GENERATED,
                    contract_id=cid_str,
                    contract_title=contract.title,
                    org_id=str(job.org_id),
                    recipient_email=user_email,
                    summary=(
                        f"Annotated PDF report v{version.version_number} generated successfully."
                    ),
                )
            )
        except Exception as ws_err:
            logger.warning("report_event_broadcast_failed_non_fatal", error=str(ws_err))

        return job

    except Exception as exc:
        logger.exception("report_generation_failed", job_id=str(job.id), error=str(exc))
        await report_job_repo.update_status(
            session,
            job,
            ReportJobStatus.failed,
            error_message=str(exc),
        )
        await session.commit()

        try:
            from app.services.websocket_manager import ws_manager

            await ws_manager.broadcast_event(
                contract_id=str(job.contract_id),
                event_type="REPORT_FAILED",
                data={"job_id": str(job.id), "status": "failed", "error": str(exc)},
            )
        except Exception as ws_fail_err:
            logger.warning("report_failed_broadcast_failed", error=str(ws_fail_err))

        raise
