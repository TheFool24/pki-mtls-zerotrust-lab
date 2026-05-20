"""Audit log model — every significant action gets recorded."""
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class AuditAction(str, Enum):
    """Enumeration of audit-worthy actions.

    Convention: <resource>.<verb>
    Add new entries as endpoints are added — don't use ad-hoc strings.
    """
    NODE_REGISTER = "node.register"
    NODE_HEARTBEAT = "node.heartbeat"
    NODE_STATE_CHANGE = "node.state_change"
    NODE_UPDATE = "node.update"
    NODE_DELETE = "node.delete"
    AUTH_FAILURE = "auth.failure"
    AUTH_SUCCESS = "auth.success"
    ADMIN_ACTION = "admin.action"


class AuditResult(str, Enum):
    SUCCESS = "success"
    REJECTED = "rejected"
    ERROR = "error"


class AuditEventBase(SQLModel):
    actor_cn: str = Field(max_length=255, index=True,
                          description="CN of the requester (from mTLS cert)")
    action: AuditAction = Field(index=True)
    target: str | None = Field(default=None, max_length=255, index=True,
                               description="Affected entity, e.g. 'node:pi-01'")
    result: AuditResult = Field(default=AuditResult.SUCCESS, index=True)


class AuditEvent(AuditEventBase, table=True):
    """Persisted audit event."""
    __tablename__ = "audit_events"

    id: int | None = Field(default=None, primary_key=True)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        index=True,
    )
    # SQLite supports JSON natively from 3.38; SQLAlchemy adapts
    details: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))


class AuditEventRead(AuditEventBase):
    """Response model for GET /audit."""
    id: int
    timestamp: datetime
    details: dict[str, Any] | None
