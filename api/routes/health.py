from __future__ import annotations

from fastapi import APIRouter

from api.schemas.health import HealthResponse


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Health check")
def get_health() -> HealthResponse:
    return HealthResponse(status="ok", service="multi-rag-bot-api")
