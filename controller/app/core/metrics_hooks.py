"""Background task that periodically refreshes gauge metrics from DB state.

Gauges represent current state, not deltas — so we need to recompute them
periodically. Counter metrics are updated inline at event time.
"""
import asyncio
from collections import Counter as PyCounter
from datetime import datetime, timezone

from sqlmodel import select

from app.core.logging import get_logger
from app.core.metrics import node_last_heartbeat_seconds, nodes_total
from app.db.session import AsyncSessionFactory
from app.models.node import Node

log = get_logger("metrics_hooks")


async def refresh_node_gauges() -> None:
    """Recompute nodes_total and node_last_heartbeat_seconds from DB."""
    async with AsyncSessionFactory() as session:
        result = await session.execute(select(Node))
        nodes = list(result.scalars().all())

    # Reset all label combinations before recomputing
    nodes_total.clear()

    # Count by (state, role) combinations
    counts: PyCounter = PyCounter()
    for n in nodes:
        counts[(n.state.value, n.role)] += 1

    for (state, role), count in counts.items():
        nodes_total.labels(state=state, role=role).set(count)

    # Per-node heartbeat freshness.
    # SQLite returns naive datetimes on readback — assume UTC so we can
    # subtract from a tz-aware `now` without TypeError.
    now = datetime.now(timezone.utc)
    for n in nodes:
        if n.last_heartbeat_at:
            hb = n.last_heartbeat_at
            if hb.tzinfo is None:
                hb = hb.replace(tzinfo=timezone.utc)
            age = (now - hb).total_seconds()
            node_last_heartbeat_seconds.labels(node_id=n.node_id).set(age)


async def periodic_gauge_refresh(interval_seconds: int = 30) -> None:
    """Background loop refreshing gauges every N seconds."""
    log.info("metrics_refresh_started", interval=interval_seconds)
    while True:
        try:
            await refresh_node_gauges()
        except Exception:
            log.exception("metrics_refresh_failed")
        await asyncio.sleep(interval_seconds)
