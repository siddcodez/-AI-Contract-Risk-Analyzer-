"""API v1 router — aggregates all v1 endpoint routers."""

from fastapi import APIRouter

from app.api.v1.analysis import router as analysis_router
from app.api.v1.audit_logs import router as audit_logs_router
from app.api.v1.auth import router as auth_router
from app.api.v1.comparisons import router as comparisons_router
from app.api.v1.contracts import router as contracts_router
from app.api.v1.health import router as health_router
from app.api.v1.missing_clauses import router as missing_clauses_router
from app.api.v1.reports import router as reports_router
from app.api.v1.search import router as search_router
from app.api.v1.upload import router as upload_router
from app.api.v1.websocket import router as websocket_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health_router)
api_v1_router.include_router(contracts_router)
api_v1_router.include_router(upload_router)
api_v1_router.include_router(analysis_router)
api_v1_router.include_router(missing_clauses_router)
api_v1_router.include_router(comparisons_router)
api_v1_router.include_router(search_router)
api_v1_router.include_router(audit_logs_router)
api_v1_router.include_router(reports_router)
api_v1_router.include_router(websocket_router)
api_v1_router.include_router(auth_router)
