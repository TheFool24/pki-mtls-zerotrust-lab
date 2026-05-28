"""Certificate revocation enforcement.

step-ca is the source of truth: a cert is revoked with `step ca revoke`, which
publishes its serial in the CA's CRL (served at /crl). This module fetches that
CRL periodically and caches the set of revoked serials; `app.core.security` then
rejects any request bearing a revoked client-cert serial.

Zero Trust framing: revocation is checked per request against current CA state,
not just at the TLS handshake — so revoking a node takes effect on its next call.
"""
import asyncio

import httpx
from cryptography import x509

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("revocation")

# Cache of revoked serials (as ints). Read by security.is_revoked().
_revoked_serials: frozenset[int] = frozenset()


def is_revoked(serial: int) -> bool:
    return serial in _revoked_serials


async def _fetch_revoked_serials() -> frozenset[int]:
    """Fetch step-ca's CRL (DER) over TLS verified against the CA trust bundle,
    and return the set of revoked serial numbers."""
    async with httpx.AsyncClient(verify=settings.ca_trust_file, timeout=10.0) as client:
        resp = await client.get(settings.crl_url)
        resp.raise_for_status()
    crl = x509.load_der_x509_crl(resp.content)
    return frozenset(entry.serial_number for entry in crl)


async def periodic_crl_refresh(interval_seconds: int | None = None) -> None:
    """Background loop refreshing the revoked-serial cache."""
    global _revoked_serials
    interval = interval_seconds or settings.crl_refresh_seconds
    log.info("crl_refresh_started", url=settings.crl_url, interval=interval)
    while True:
        try:
            serials = await _fetch_revoked_serials()
            if serials != _revoked_serials:
                log.info("crl_updated", revoked_count=len(serials))
            _revoked_serials = serials
        except Exception:
            log.exception("crl_refresh_failed")  # keep last good cache
        await asyncio.sleep(interval)
