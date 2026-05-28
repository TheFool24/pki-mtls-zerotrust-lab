"""Node registration and management endpoints."""
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.audit import record_event
from app.core.logging import get_logger
from app.core.security import MTLSIdentityDep
from app.db.session import get_session
from app.models.audit import AuditAction, AuditResult
from app.models.node import Node, NodeCreate, NodeHeartbeat, NodeRead, NodeState

log = get_logger("nodes")
router = APIRouter(prefix="/nodes", tags=["nodes"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_model=list[NodeRead])
async def list_nodes(
    identity: MTLSIdentityDep,
    session: SessionDep,
) -> list[Node]:
    """List all registered nodes. Requires verified mTLS."""
    result = await session.execute(select(Node).order_by(Node.node_id))
    nodes = result.scalars().all()
    log.info("nodes_listed", actor=identity.common_name, count=len(nodes))
    return list(nodes)


@router.post("", response_model=NodeRead, status_code=status.HTTP_201_CREATED)
async def register_node(
    payload: NodeCreate,
    identity: MTLSIdentityDep,
    session: SessionDep,
) -> Node:
    """Register a new node.

    Authorization rules:
    - Only the controller itself OR the node whose CN matches `common_name` can register.
    - Prevents pi-01 from registering pi-02 (lateral movement defense).
    """
    # Authorization
    is_self_registration = (
        identity.is_node
        and identity.common_name == payload.common_name
    )
    is_controller_action = identity.is_controller

    if not (is_self_registration or is_controller_action):
        await record_event(
            session,
            actor_cn=identity.common_name,
            action=AuditAction.AUTH_FAILURE,
            target=f"node:{payload.node_id}",
            result=AuditResult.REJECTED,
            details={"reason": "actor not authorized to register this node"},
        )
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot register a node on behalf of another identity",
        )

    # Check for existing node. Idempotent re-registration by the same actor
    # (the auth check above already enforced identity == payload.common_name)
    # is operational noise — kept silent so the audit log stays a security
    # artifact, not a fleet-restart log. The CN-mismatch case is caught by
    # the AUTH_FAILURE record above before we ever get here.
    existing = await session.execute(
        select(Node).where(Node.node_id == payload.node_id)
    )
    if existing.scalar_one_or_none():
        log.info(
            "node_register_duplicate",
            actor=identity.common_name,
            node_id=payload.node_id,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Node '{payload.node_id}' is already registered",
        )

    # Create the node
    node = Node(**payload.model_dump())
    session.add(node)
    await session.flush()

    await record_event(
        session,
        actor_cn=identity.common_name,
        action=AuditAction.NODE_REGISTER,
        target=f"node:{node.node_id}",
        result=AuditResult.SUCCESS,
        details={"role": node.role, "ip": node.ip_address},
    )

    await session.commit()
    await session.refresh(node)
    return node


@router.get("/{node_id}", response_model=NodeRead)
async def get_node(
    node_id: str,
    identity: MTLSIdentityDep,
    session: SessionDep,
) -> Node:
    """Get single node by node_id."""
    result = await session.execute(
        select(Node).where(Node.node_id == node_id)
    )
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node '{node_id}' not found",
        )
    return node


@router.post("/{node_id}/heartbeat", response_model=NodeRead)
async def heartbeat(
    node_id: str,
    payload: NodeHeartbeat,
    identity: MTLSIdentityDep,
    session: SessionDep,
) -> Node:
    """Node check-in. Only the node itself can heartbeat for itself."""
    result = await session.execute(
        select(Node).where(Node.node_id == node_id)
    )
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node '{node_id}' not found",
        )

    # Strict authorization: the heartbeating identity must match the node
    if identity.common_name != node.common_name:
        await record_event(
            session,
            actor_cn=identity.common_name,
            action=AuditAction.AUTH_FAILURE,
            target=f"node:{node_id}",
            result=AuditResult.REJECTED,
            details={
                "reason": "heartbeat from non-matching identity",
                "claimed_node": node_id,
            },
        )
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot heartbeat on behalf of another node",
        )

    # State transition is a security-relevant event (onboarding→active means a
    # newly-enrolled node has confirmed liveness); routine heartbeats are
    # operational telemetry only. Keeping the audit table clean: only state
    # changes get a row, freshness flows through metrics + structlog.
    now = datetime.now(timezone.utc)
    state_changed = False
    prior_state = node.state
    if node.state == NodeState.ONBOARDING:
        node.state = NodeState.ACTIVE
        state_changed = True

    node.last_heartbeat_at = now
    node.updated_at = now
    session.add(node)

    if state_changed:
        await record_event(
            session,
            actor_cn=identity.common_name,
            action=AuditAction.NODE_STATE_CHANGE,
            target=f"node:{node.node_id}",
            result=AuditResult.SUCCESS,
            details={
                "from": prior_state.value,
                "to": node.state.value,
                "trigger": "heartbeat",
            },
        )
    else:
        # Routine heartbeat — structured log only (Loki captures), no audit row.
        log.info(
            "node_heartbeat",
            node_id=node.node_id,
            actor=identity.common_name,
            state=node.state.value,
            note=payload.status_note,
        )

    await session.commit()
    await session.refresh(node)
    return node
