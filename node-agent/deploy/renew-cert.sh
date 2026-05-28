#!/bin/bash
# Thesis Node — certificate renewal (mTLS /renew endpoint; X5C-free, no fallback).
#
# Renewal authenticates with the node's EXISTING valid cert as an mTLS client
# credential to step-ca's /renew endpoint (`step ca renew`). The renewed cert
# inherits the original issuing provisioner (node-enrollment) and reuses the key.
#
# NO secret is stored on the node, and there is deliberately NO automatic
# re-enrollment fallback: if the cert is already expired (node was offline past
# its lifetime), `step ca renew` cannot authenticate and this fails LOUDLY.
# Recovery is then a manual, controller-mediated re-enrollment (RUNBOOK-reenroll.md).
#
# Invoked by thesis-cert-renew.timer (every 8h) and on boot (OnBootSec). Runs as
# the same user as the agent (jojo), which owns the cert + key.
set -uo pipefail

CERT="/etc/thesis-lab/certs/pi-01.crt"
KEY="/etc/thesis-lab/certs/pi-01.key"
CA_URL="https://ca.thesis.local:9000"
CA_ROOT="/etc/thesis-lab/certs/ca-root.crt"
RENEW_THRESHOLD="48h"          # renew when less than this remains (of the 7d/168h life)
STEP="/usr/local/bin/step"
AGENT="thesis-node-agent.service"
LOG_TAG="thesis-cert-renew"

log() { logger -t "$LOG_TAG" -- "$1"; echo "$(date -Iseconds) $1"; }

if [[ ! -f "$CERT" || ! -f "$KEY" ]]; then
    log "FATAL: cert or key missing ($CERT / $KEY). Manual re-enrollment required — RUNBOOK-reenroll.md."
    exit 1
fi

# needs-renewal exits 0 when the cert expires within the window, 1 when it doesn't.
if "$STEP" certificate needs-renewal "$CERT" --expires-in="$RENEW_THRESHOLD"; then
    log "Cert within renewal window ($RENEW_THRESHOLD). Renewing via mTLS /renew endpoint..."
    if "$STEP" ca renew "$CERT" "$KEY" --ca-url="$CA_URL" --root="$CA_ROOT" --force; then
        log "Renewal SUCCESS — fresh cert installed (key reused)."
        # Agent caches its SSLContext at startup; restart to load the new cert.
        if systemctl is-active --quiet "$AGENT"; then
            if sudo systemctl restart "$AGENT"; then
                log "Restarted $AGENT to load the renewed cert."
            else
                log "WARN: renewal succeeded but agent restart failed — agent still holds old cert."
            fi
        fi
        exit 0
    else
        log "FATAL: 'step ca renew' FAILED. Cert is likely expired (node offline > lifetime). "\
"Manual re-enrollment required — RUNBOOK-reenroll.md. NO automatic fallback by design."
        exit 1
    fi
else
    log "Cert valid beyond ${RENEW_THRESHOLD}; no renewal needed."
    exit 0
fi
