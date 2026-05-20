"""Identity verification endpoint — confirms mTLS extraction is working."""
from fastapi import APIRouter
from pydantic import BaseModel

from app.core.security import MTLSIdentityDep

router = APIRouter(tags=["identity"])


class WhoamiResponse(BaseModel):
    common_name: str
    full_dn: str
    verified: bool
    role: str  # "controller" | "node" | "unknown"
    node_id: str | None


@router.get("/whoami", response_model=WhoamiResponse)
async def whoami(identity: MTLSIdentityDep) -> WhoamiResponse:
    """Return the verified identity extracted from the client certificate.

    Useful for:
    - Verifying mTLS pipeline end-to-end
    - Debugging cert SANs / CN
    - Pi nodes confirming their identity is properly recognized
    """
    role = "controller" if identity.is_controller else "node" if identity.is_node else "unknown"

    return WhoamiResponse(
        common_name=identity.common_name,
        full_dn=identity.full_dn,
        verified=identity.verified,
        role=role,
        node_id=identity.node_id,
    )
