"""mTLS identity extraction from Nginx-forwarded headers, with metrics.

The mTLS handshake terminates at Nginx (Step 6). Nginx verifies the client
certificate against the Root CA and forwards the verification status + the
subject DN as headers. This module extracts and validates that identity, and
records the outcome as a Prometheus counter (thesis_mtls_auth_total).
"""
import re
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.core.config import settings
from app.core.logging import get_logger
from app.core.metrics import mtls_auth_total

log = get_logger("security")

# Match CN=<value> in subject DN; value can contain anything up to comma or slash
_CN_PATTERN = re.compile(r"CN=([^,/]+)")


@dataclass(frozen=True)
class MTLSIdentity:
    """Verified identity extracted from a client certificate via Nginx."""
    common_name: str
    full_dn: str
    verified: bool

    @property
    def is_controller(self) -> bool:
        return self.common_name.startswith("controller.")

    @property
    def is_node(self) -> bool:
        return self.common_name.startswith("pi-")

    @property
    def node_id(self) -> str | None:
        """Extract node-id from CN (e.g. 'pi-01.thesis.local' -> 'pi-01')."""
        if not self.is_node:
            return None
        return self.common_name.split(".")[0]


def get_mtls_identity(
    x_client_verify: Annotated[str | None, Header()] = None,
    x_client_dn: Annotated[str | None, Header()] = None,
) -> MTLSIdentity:
    """FastAPI dependency that extracts and validates mTLS identity.

    Rejects requests without verified mTLS unless settings.allow_unauthenticated.
    """
    # Dev escape hatch — never True in production
    if settings.allow_unauthenticated and not x_client_verify:
        log.warning("unauthenticated_request_allowed", reason="dev_mode")
        return MTLSIdentity(common_name="dev-bypass", full_dn="", verified=False)

    if x_client_verify is None or x_client_dn is None:
        mtls_auth_total.labels(result="missing_headers").inc()
        log.warning("mtls_headers_missing",
                    has_verify=x_client_verify is not None,
                    has_dn=x_client_dn is not None)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="mTLS identity headers missing — request did not pass through Nginx mTLS proxy",
        )

    if x_client_verify != "SUCCESS":
        mtls_auth_total.labels(result="verify_failed").inc()
        log.warning("mtls_verify_failed", verify_status=x_client_verify, dn=x_client_dn)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Client certificate verification failed: {x_client_verify}",
        )

    match = _CN_PATTERN.search(x_client_dn)
    if not match:
        mtls_auth_total.labels(result="cn_parse_failed").inc()
        log.error("mtls_cn_parse_failed", dn=x_client_dn)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not extract CN from client DN",
        )

    mtls_auth_total.labels(result="success").inc()
    cn = match.group(1).strip()
    return MTLSIdentity(common_name=cn, full_dn=x_client_dn, verified=True)


# Type alias for dependency injection
MTLSIdentityDep = Annotated[MTLSIdentity, Depends(get_mtls_identity)]
