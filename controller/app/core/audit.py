"""Audit logging helper — DB + structured log + Prometheus counter."""
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.metrics import audit_events_total
from app.models.audit import AuditAction, AuditEvent, AuditResult

log = get_logger("audit")


async def record_event(
    session: AsyncSession,
    *,
    actor_cn: str,
    action: AuditAction,
    target: str | None = None,
    result: AuditResult = AuditResult.SUCCESS,
    details: dict[str, Any] | None = None,
) -> AuditEvent:
    """Triple-write: DB row + structlog line + Prometheus counter increment.

    The DB write is awaited but commit is NOT performed here — caller must
    commit (or rollback) as part of the wrapping transaction.
    """
    event = AuditEvent(
        actor_cn=actor_cn,
        action=action,
        target=target,
        result=result,
        details=details,
    )
    session.add(event)
    await session.flush()  # populate event.id and event.timestamp

    # Structured log
    log.info(
        "audit_event",
        event_id=event.id,
        actor_cn=actor_cn,
        action=action.value,
        target=target,
        result=result.value,
        details=details,
    )

    # Prometheus counter
    audit_events_total.labels(action=action.value, result=result.value).inc()

    return event
