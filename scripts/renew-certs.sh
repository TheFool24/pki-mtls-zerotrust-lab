#!/bin/bash
# Renew controller-side service certs. Called from a systemd timer every 8h.
#
# Each cert has two failure modes the script handles:
#   1) Cert still valid but inside renewal window  → `step ca renew` (cert-to-cert,
#      no provisioner password needed).
#   2) Cert already expired (lab was powered off across the window) → `step ca
#      renew` refuses; fall back to re-issue via the cert's issuing provisioner.
#      This is what kept the controller's nginx cert alive across multi-day
#      downtime — same pattern now extended to Prometheus's scraper cert.
#
# The /usr/local/bin/step wrapper mounts $(pwd) as /workdir, so we cd into each
# cert directory and use RELATIVE filenames — host paths aren't visible inside
# the container.
set -euo pipefail

CA_URL="https://ca.thesis.local:9000"
RENEW_THRESHOLD="8h"    # renew when fewer than this many hours remain
LIFETIME="24h"          # validity at re-issue (matches renewal cadence headroom)

ts() { date -Iseconds; }
log() { echo "$(ts) $*"; }

# ── Per-cert post-actions ─────────────────────────────────────────────────────

post_controller() {
    # Controller leaf is also the nginx server cert.
    local crt="/opt/thesis-lab/nginx/certs/server.crt"
    if [ -f "$crt" ]; then
        cp /opt/thesis-lab/step-ca/issued/controller/controller.crt "$crt"
        cp /opt/thesis-lab/step-ca/issued/controller/controller.key /opt/thesis-lab/nginx/certs/server.key
        chmod 644 "$crt" /opt/thesis-lab/nginx/certs/server.key
        log "  refreshed nginx server.crt/server.key"
        if docker ps --filter name=thesis-nginx --filter status=running -q | grep -q .; then
            docker exec thesis-nginx nginx -s reload
            log "  reloaded nginx"
        fi
    fi
}

post_prometheus() {
    # Scraper client cert. Loose perms required for Prometheus container to read.
    chmod 644 /opt/thesis-lab/step-ca/issued/prometheus/prometheus.crt \
              /opt/thesis-lab/step-ca/issued/prometheus/prometheus.key
    # SIGHUP triggers config + TLS material reload (no scrape gap).
    if docker ps --filter name=thesis-prometheus --filter status=running -q | grep -q .; then
        docker exec thesis-prometheus kill -HUP 1
        log "  signaled Prometheus to reload (HUP)"
    fi
}

# ── Core renewal flow ─────────────────────────────────────────────────────────

renew_cert() {
    local name="$1"          # tag used for logging and post_<name> dispatch
    local cert_dir="$2"
    local cn="$3"
    local provisioner="$4"   # JWK provisioner for re-issue fallback
    local pw_file="$5"       # path INSIDE container (/secrets/...)
    local sans_csv="$6"      # comma-separated SAN list

    log "[$name] checking renewal need..."
    cd "$cert_dir"

    if ! step certificate needs-renewal "${name}.crt" --expires-in="$RENEW_THRESHOLD"; then
        log "[$name] still outside renewal window, skipping"
        return 0
    fi

    log "[$name] within renewal window; attempting cert-to-cert renew..."
    if step ca renew "${name}.crt" "${name}.key" --force --ca-url="$CA_URL"; then
        log "[$name] renewed via existing cert"
    else
        log "[$name] renew failed (likely expired); re-issuing via $provisioner"
        local san_args=()
        IFS=',' read -ra sans <<< "$sans_csv"
        for s in "${sans[@]}"; do san_args+=(--san "$s"); done
        step ca certificate "$cn" "${name}.crt" "${name}.key" \
            "${san_args[@]}" \
            --provisioner "$provisioner" \
            --provisioner-password-file "$pw_file" \
            --not-after "$LIFETIME" \
            --force
        log "[$name] fresh cert issued via $provisioner"
    fi

    # Dispatch post-action by name (post_controller, post_prometheus, ...).
    if declare -F "post_${name}" > /dev/null; then
        log "[$name] running post-action"
        "post_${name}"
    fi
}

# ── Cert registry ─────────────────────────────────────────────────────────────
# Format per entry: name|cert_dir|cn|provisioner|provisioner_pw_file|sans_csv
# pw_file path is INSIDE the step-cli container (/secrets/... — bind from host).
CERTS=(
    "controller|/opt/thesis-lab/step-ca/issued/controller|controller.thesis.local|thesis-admin@vutp.bg|/secrets/provisioner-password.txt|controller.thesis.local,10.50.20.200,master-lab"
    "prometheus|/opt/thesis-lab/step-ca/issued/prometheus|prometheus.thesis.local|service-scraper|/secrets/service-scraper-password.txt|prometheus.thesis.local,prometheus"
)

for entry in "${CERTS[@]}"; do
    IFS='|' read -r name dir cn prov pw sans <<< "$entry"
    renew_cert "$name" "$dir" "$cn" "$prov" "$pw" "$sans" || log "[$name] FAILED — continuing with next cert"
done

log "done."
