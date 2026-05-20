"""Health check endpoint — used by Docker healthcheck and external monitoring."""
from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    timestamp: datetime


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Basic liveness — does NOT require mTLS (called by Nginx healthcheck)."""
    return HealthResponse(
        status="ok",
        service=settings.service_name,
        version=settings.service_version,
        timestamp=datetime.now(timezone.utc),
    )
