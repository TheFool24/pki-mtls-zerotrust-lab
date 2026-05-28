"""Heartbeat loop. Self-registers on startup (idempotent), then beats with
random jitter so multiple nodes coming up together don't synchronize their
load on the controller."""
import asyncio
import random

import httpx

from app.config import settings
from app.http_client import build_client, heartbeat, register
from app.logging_setup import get_logger
from app.metrics import heartbeats_total

log = get_logger("heartbeat")


async def _attempt_register(client: httpx.AsyncClient) -> None:
    """Retry registration with exponential backoff until it succeeds or 409s.
    The agent refuses to start beating before it's known to the controller."""
    delay = 2.0
    for attempt in range(1, 11):
        try:
            await register(client)
            return
        except httpx.HTTPError as exc:
            log.warning("register_failed", attempt=attempt, error=str(exc))
            await asyncio.sleep(delay)
            delay = min(delay * 1.8, 60.0)
    raise RuntimeError("could not register after 10 attempts")


async def run() -> None:
    """Driver: register-once, then beat forever."""
    async with build_client() as client:
        await _attempt_register(client)
        log.info("heartbeat_loop_starting",
                 interval=settings.heartbeat_interval,
                 jitter=settings.heartbeat_jitter)

        while True:
            try:
                await heartbeat(client)
                heartbeats_total.labels(result="success").inc()
            except httpx.HTTPError as exc:
                heartbeats_total.labels(result="failure").inc()
                log.error("heartbeat_failed", error=str(exc))
            # ±jitter around the configured interval
            j = settings.heartbeat_jitter
            await asyncio.sleep(
                settings.heartbeat_interval + random.uniform(-j, j)
            )
