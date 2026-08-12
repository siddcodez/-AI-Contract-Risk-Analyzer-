"""API v1 router — aggregates all v1 endpoint routers."""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.contracts import router as contracts_router
from app.api.v1.health import router as health_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health_router)
api_v1_router.include_router(contracts_router)
api_v1_router.include_router(auth_router)
