#!/bin/bash
# Renews controller leaf cert via step CLI wrapper.
# Called from systemd timer every 8 hours.
#
# The /usr/local/bin/step wrapper mounts $(pwd) as /workdir in the container,
# so the script cd's to the cert directory and uses RELATIVE filenames —
# host paths like /opt/thesis-lab/... aren't visible inside the container.
set -euo pipefail

CERT_DIR="/opt/thesis-lab/step-ca/issued/controller"
cd "$CERT_DIR"

if step certificate needs-renewal controller.crt --expires-in=8h; then
    echo "$(date -Iseconds) Renewing controller cert..."
    step ca renew controller.crt controller.key \
        --force \
        --ca-url=https://ca.thesis.local:9000
    echo "$(date -Iseconds) Renewed."

    # Also refresh the nginx server cert (controller cert is reused).
    # step ca renew already writes the full chain (leaf + intermediate) into
    # controller.crt, so a plain copy is correct — no concatenation needed.
    # No-op if nginx isn't deployed yet.
    NGINX_CRT="/opt/thesis-lab/nginx/certs/server.crt"
    if [ -f "$NGINX_CRT" ]; then
        cp controller.crt "$NGINX_CRT"
        cp controller.key /opt/thesis-lab/nginx/certs/server.key
        chmod 644 "$NGINX_CRT" /opt/thesis-lab/nginx/certs/server.key
        echo "$(date -Iseconds) Refreshed nginx server.crt + server.key."
        # Reload nginx so it picks up the new cert without dropping connections.
        if docker ps --filter name=thesis-nginx --filter status=running -q | grep -q .; then
            docker exec thesis-nginx nginx -s reload
            echo "$(date -Iseconds) Reloaded nginx."
        fi
    fi
else
    echo "$(date -Iseconds) Cert still valid, no renewal needed."
fi
