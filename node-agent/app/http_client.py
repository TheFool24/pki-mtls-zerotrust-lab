"""mTLS httpx client + controller API wrappers (register, heartbeat)."""
import socket
import ssl

import httpx

from app.config import settings
from app.logging_setup import get_logger

log = get_logger("http_client")


def _build_ssl_context() -> ssl.SSLContext:
    """Client-side mTLS context. httpx 0.28 silently ignores the deprecated
    `cert=(crt, key)` tuple form (the cert is never presented → nginx 400), so
    we build an explicit context: verify the controller against our CA AND load
    our own leaf to present on the handshake."""
    ctx = ssl.create_default_context(cafile=str(settings.controller_ca))
    ctx.load_cert_chain(
        certfile=str(settings.client_cert),
        keyfile=str(settings.client_key),
    )
    return ctx


def build_client() -> httpx.AsyncClient:
    """One client per process — connection-pooled, keep-alived."""
    return httpx.AsyncClient(
        base_url=settings.controller_url,
        verify=_build_ssl_context(),
        timeout=httpx.Timeout(10.0, connect=5.0),
        headers={"User-Agent": f"thesis-node-agent/{settings.node_id}"},
    )


def _primary_ip() -> str:
    """Best-effort: which IP would we use to reach the controller? Used as the
    `ip_address` field on registration. Not security-critical — controller
    has the authoritative routing view."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.50.20.200", 443))
        return s.getsockname()[0]
    except OSError:
        return ""
    finally:
        s.close()


async def register(client: httpx.AsyncClient) -> bool:
    """Idempotent self-registration. Returns True if newly registered, False if
    already-known (409). Raises on any other failure so the caller can decide."""
    payload = {
        "node_id": settings.node_id,
        "common_name": settings.node_common_name,
        "role": settings.node_role,
        "ip_address": _primary_ip() or None,
    }
    r = await client.post("/api/v1/nodes", json=payload)
    if r.status_code == 201:
        log.info("registered", node_id=settings.node_id, response=r.json())
        return True
    if r.status_code == 409:
        log.info("already_registered", node_id=settings.node_id)
        return False
    r.raise_for_status()
    return False  # unreachable but keeps type checker happy


async def heartbeat(client: httpx.AsyncClient, note: str | None = None) -> dict:
    payload = {"status_note": note} if note else {}
    r = await client.post(
        f"/api/v1/nodes/{settings.node_id}/heartbeat",
        json=payload,
    )
    r.raise_for_status()
    return r.json()
