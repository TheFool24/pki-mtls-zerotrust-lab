"""Audit log query endpoint."""
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.security import MTLSIdentityDep
from app.db.session import get_session
from app.models.audit import AuditEvent, AuditEventRead

router = APIRouter(prefix="/audit", tags=["audit"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_model=list[AuditEventRead])
async def list_audit_events(
    identity: MTLSIdentityDep,
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    actor_cn: str | None = Query(default=None),
    action: str | None = Query(default=None),
) -> list[AuditEvent]:
    """Query audit events with filtering.

    For now, any authenticated node can read audit log. In a production
    deployment, this would be restricted to controller/admin role only.
    Logged as future enhancement in Гл. 6.
    """
    stmt = select(AuditEvent).order_by(AuditEvent.timestamp.desc())

    if actor_cn:
        stmt = stmt.where(AuditEvent.actor_cn == actor_cn)
    if action:
        stmt = stmt.where(AuditEvent.action == action)

    stmt = stmt.offset(offset).limit(limit)

    result = await session.execute(stmt)
    return list(result.scalars().all())
