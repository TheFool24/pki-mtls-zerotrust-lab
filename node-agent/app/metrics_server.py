"""aiohttp HTTPS server exposing /metrics — terminates mTLS and enforces an
allowed-CN check before responding.

The allowed-CN check is the defense-in-depth layer: ssl.CERT_REQUIRED already
ensures the client has a valid leaf signed by our CA, but ANY such leaf would
otherwise be accepted. The CN allowlist ensures only the designated scraper(s)
can pull metrics — a compromised neighbor node cannot exfiltrate metrics from
this node even with a valid cert."""
import ssl

from aiohttp import web

from app.config import settings
from app.logging_setup import get_logger
from app.metrics import render

log = get_logger("metrics_server")


def _peer_cn(request: web.Request) -> str | None:
    """Extract the CN from the verified peer cert. Returns None if there's no
    peer cert (shouldn't happen with CERT_REQUIRED, but defensive)."""
    ssl_obj = request.transport.get_extra_info("ssl_object") if request.transport else None
    if ssl_obj is None:
        return None
    peercert = ssl_obj.getpeercert()
    if not peercert:
        return None
    # subject is a tuple of RDN tuples: ((('commonName', 'x'),), (('organization', 'y'),))
    for rdn in peercert.get("subject", ()):
        for key, val in rdn:
            if key == "commonName":
                return val
    return None


@web.middleware
async def cn_allowlist_middleware(request: web.Request, handler):
    allowed = settings.allowed_cns_set()
    cn = _peer_cn(request)
    if cn is None or cn not in allowed:
        log.warning(
            "metrics_scrape_rejected",
            peer_cn=cn,
            allowed=sorted(allowed),
            peer=request.remote,
        )
        return web.Response(status=403, text="forbidden\n")
    return await handler(request)


async def metrics_handler(request: web.Request) -> web.Response:
    return web.Response(body=render(), content_type="text/plain; version=0.0.4")


def build_ssl_context() -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_3
    ctx.load_cert_chain(certfile=str(settings.client_cert), keyfile=str(settings.client_key))
    ctx.load_verify_locations(cafile=str(settings.controller_ca))
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx


def build_app() -> web.Application:
    app = web.Application(middlewares=[cn_allowlist_middleware])
    app.router.add_get("/metrics", metrics_handler)
    return app
