"""Audit logging helper — double-write to DB and structured log.

Every state-changing or security-relevant action MUST go through this module.
Ensures audit trail consistency between persistent storage (queryable via API)
and stdout JSON logs (Loki ingestion in Step 8/9).
"""
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
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
    """Record an audit event to DB and stdout simultaneously.

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

    # Mirror to structured log — for Loki / Grafana
    log.info(
        "audit_event",
        event_id=event.id,
        actor_cn=actor_cn,
        action=action.value,
        target=target,
        result=result.value,
        details=details,
    )

    return event
