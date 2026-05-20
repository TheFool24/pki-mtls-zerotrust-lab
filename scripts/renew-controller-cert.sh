#!/bin/bash
# Keeps the controller leaf cert alive. Called from a systemd timer every 8h.
#
# Normal path: `step ca renew` while the cert is still valid.
# Self-heal path: if the cert already EXPIRED (e.g. the lab box was powered off
# across the renewal window — a 24h cert can't survive >24h downtime), `step ca
# renew` refuses to act. In that case we re-issue a fresh cert via the admin
# provisioner so the system recovers automatically on next boot/timer.
#
# The /usr/local/bin/step wrapper mounts $(pwd) as /workdir, so we cd into the
# cert directory and use RELATIVE filenames — host paths aren't visible inside
# the container.
set -euo pipefail

CERT_DIR="/opt/thesis-lab/step-ca/issued/controller"
CA_URL="https://ca.thesis.local:9000"
PROVISIONER="thesis-admin@vutp.bg"
PROVISIONER_PW="/secrets/provisioner-password.txt"   # path inside the step container
CN="controller.thesis.local"
SANS=(--san "controller.thesis.local" --san "10.50.20.200" --san "master-lab")
LIFETIME="24h"          # cert validity at issue/reissue
RENEW_THRESHOLD="8h"    # renew when fewer than this many hours remain

cd "$CERT_DIR"

ts() { date -Iseconds; }

reissue_fresh() {
    echo "$(ts) Re-issuing a fresh cert via provisioner $PROVISIONER..."
    step ca certificate "$CN" controller.crt controller.key \
        "${SANS[@]}" \
        --provisioner "$PROVISIONER" \
        --provisioner-password-file "$PROVISIONER_PW" \
        --not-after "$LIFETIME" \
        --force
    echo "$(ts) Fresh cert issued."
}

refresh_nginx() {
    # step ca renew/certificate writes the full chain into controller.crt,
    # so a plain copy is correct. No-op if nginx isn't deployed yet.
    local crt="/opt/thesis-lab/nginx/certs/server.crt"
    if [ -f "$crt" ]; then
        cp controller.crt "$crt"
        cp controller.key /opt/thesis-lab/nginx/certs/server.key
        chmod 644 "$crt" /opt/thesis-lab/nginx/certs/server.key
        echo "$(ts) Refreshed nginx server.crt + server.key."
        if docker ps --filter name=thesis-nginx --filter status=running -q | grep -q .; then
            docker exec thesis-nginx nginx -s reload
            echo "$(ts) Reloaded nginx."
        fi
    fi
}

if step certificate needs-renewal controller.crt --expires-in="$RENEW_THRESHOLD"; then
    echo "$(ts) Cert within renewal window; attempting renew..."
    if step ca renew controller.crt controller.key --force --ca-url="$CA_URL"; then
        echo "$(ts) Renewed."
    else
        echo "$(ts) Renew failed (likely already expired); falling back to fresh issue."
        reissue_fresh
    fi
    refresh_nginx
else
    echo "$(ts) Cert still valid, no renewal needed."
fi
