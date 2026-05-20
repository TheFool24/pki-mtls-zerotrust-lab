"""Node model — represents a registered Pi node in the lab."""
from datetime import datetime, timezone
from enum import Enum

from sqlmodel import Field, SQLModel


class NodeState(str, Enum):
    """Operational state of a node.

    State transitions:
    - onboarding: just enrolled, awaiting first heartbeat
    - active: healthy, regularly checking in
    - stale: missed expected heartbeats (configurable threshold)
    - revoked: cert revoked by admin (manual or policy)
    - decommissioned: removed from active fleet (soft delete)
    """
    ONBOARDING = "onboarding"
    ACTIVE = "active"
    STALE = "stale"
    REVOKED = "revoked"
    DECOMMISSIONED = "decommissioned"


class NodeBase(SQLModel):
    """Shared fields between API models and DB model."""
    node_id: str = Field(index=True, unique=True, max_length=64,
                         description="Short identifier (e.g. 'pi-01')")
    common_name: str = Field(max_length=255,
                             description="Full CN from cert (e.g. 'pi-01.thesis.local')")
    role: str = Field(max_length=32,
                      description="Role label: valid | revoked | compromised | onboarding")
    state: NodeState = Field(default=NodeState.ONBOARDING)
    ip_address: str | None = Field(default=None, max_length=45)
    notes: str | None = Field(default=None, max_length=512)


class Node(NodeBase, table=True):
    """Persisted node record."""
    __tablename__ = "nodes"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_heartbeat_at: datetime | None = Field(default=None)


# API I/O models
class NodeCreate(NodeBase):
    """Payload for POST /nodes (registration)."""
    pass


class NodeRead(NodeBase):
    """Response model for GET /nodes."""
    id: int
    created_at: datetime
    updated_at: datetime
    last_heartbeat_at: datetime | None


class NodeHeartbeat(SQLModel):
    """Payload for POST /nodes/{id}/heartbeat — optional metadata."""
    status_note: str | None = None
