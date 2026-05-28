"""Startup cert-validity gate. Refuses to start with a missing/unreadable/expired
client cert and says so loudly — rather than starting and silently failing every
mTLS call. Uses the `step` CLI (already on the node) to read the cert, so there is
no `cryptography` dependency on the node.

Security property this enforces: an expired cert is NOT silently worked around.
Renewal authenticates with the *existing valid* cert; once expired, recovery is a
deliberate manual re-enrollment (see RUNBOOK-reenroll.md). There is no automatic
fallback by design — this gate makes that failure mode visible and explicit."""
import json
import subprocess
import sys
from datetime import datetime, timezone

from app.config import settings
from app.logging_setup import get_logger

log = get_logger("cert_guard")

STEP_BIN = "/usr/local/bin/step"
RENEW_WARN_HOURS = 48


def assert_cert_usable() -> None:
    cert = str(settings.client_cert)
    try:
        proc = subprocess.run(
            [STEP_BIN, "certificate", "inspect", cert, "--format", "json"],
            capture_output=True, text=True, timeout=10,
        )
    except FileNotFoundError:
        log.error("cert_check_no_step", step=STEP_BIN,
                  action="cannot verify cert; refusing to start")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        log.error("cert_check_timeout", action="refusing to start")
        sys.exit(1)

    if proc.returncode != 0:
        log.error("cert_unreadable", path=cert, stderr=proc.stderr.strip()[:200],
                  action="MANUAL RE-ENROLLMENT REQUIRED — see RUNBOOK-reenroll.md")
        sys.exit(1)

    try:
        end = json.loads(proc.stdout)["validity"]["end"]
        not_after = datetime.fromisoformat(end.replace("Z", "+00:00"))
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        log.error("cert_parse_failed", error=str(exc), action="refusing to start")
        sys.exit(1)

    now = datetime.now(timezone.utc)
    if now >= not_after:
        log.error(
            "cert_expired",
            expired_at=not_after.isoformat(),
            action="renewal cannot recover an expired cert. MANUAL RE-ENROLLMENT "
                   "REQUIRED — see RUNBOOK-reenroll.md. No automatic fallback by design.",
        )
        sys.exit(1)

    hours_left = round((not_after - now).total_seconds() / 3600, 1)
    if hours_left < RENEW_WARN_HOURS:
        log.warning("cert_near_expiry", hours_left=hours_left,
                    note="renewal timer should renew shortly")
    else:
        log.info("cert_valid", hours_left=hours_left)
