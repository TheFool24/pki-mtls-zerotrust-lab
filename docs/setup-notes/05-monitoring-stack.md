# 05 — Monitoring stack (Step 9A + 9B)

**Date:** 2026-05-21
**Step:** 9 (parts A + B)
**Status:** 9A ✅, 9B ✅, 9C (Grafana) pending

## Цел

Observability layer — metrics (Prometheus), logs (Loki), и dashboards (Grafana, Step 9C).
Захранва Гл. 4 (Мониторинг) и Гл. 5 evidence collection.

## Архитектурни решения

### Stack components (Decision 1)

| Service | Image | Purpose |
|---------|-------|---------|
| Prometheus | `prom/prometheus:v2.55.1` | Metrics TSDB, 30-day retention |
| Node Exporter | `prom/node-exporter:v1.8.2` | Host metrics (CPU/mem/disk/net) |
| cAdvisor | `gcr.io/cadvisor/cadvisor:v0.49.1` | Per-container resource stats |
| Loki | `grafana/loki:3.3.2` | Logs TSDB, 30-day retention |
| Promtail | `grafana/promtail:3.3.2` | Log shipper, Docker SD enabled |

Static IPs on thesis-lab-net: prometheus .40, node-exporter .41, cadvisor .42,
loki .50, promtail .51.

### FastAPI instrumentation (Decision 2 — Option C)

1. **Automatic HTTP metrics** via `prometheus-fastapi-instrumentator`
2. **Custom business metrics** in `app/core/metrics.py`:
   - `thesis_nodes_total{state,role}`, `thesis_mtls_auth_total{result}`,
     `thesis_audit_events_total{action,result}`,
     `thesis_node_last_heartbeat_seconds{node_id}`,
     `thesis_cert_issued_total{provisioner}`,
     `thesis_db_operation_duration_seconds{operation}`
3. **Background gauge refresh** every 30s (`metrics_hooks.periodic_gauge_refresh`)

`/metrics` exposed at controller:8000, NOT proxied by nginx → reachable only
inside the Docker network (Prometheus scrapes directly). Network-ACL approach.

### Log ingestion (Decision 3)

Pipeline: stdout (structlog JSON) → Docker captures → Promtail (Docker SD) →
JSON pipeline stage → Loki push.

**Label cardinality control** — only bounded fields promoted to labels:
`level`, `event`, `audit_action`, `audit_result` (+ Promtail/Loki auto-labels
`container`, `role`, `tier`, `job`, `service_name`, `detected_level`).
`actor_cn` deliberately NOT a label (unbounded with many nodes) — stays in the
log line for full-text search.

Promtail Docker SD filter: `thesis.role` label. Adding that label to a container
auto-enrolls it in log shipping (same pattern as k8s). 8 targets discovered.

## Verification

### 9A
- All 6 containers healthy; Prometheus targets all UP (prometheus,
  thesis-controller, node, cadvisor).
- `thesis_mtls_auth_total{result="success"}=5` after traffic; gauge refresh
  produced `thesis_nodes_total{state="active",role="valid"}=1`.

### 9B
- Loki `/ready` → ready; Promtail discovered 8 Docker targets.
- Loki labels include `audit_action`, `audit_result`, `event`, `level`.
- `{container="thesis-controller", audit_action="node.heartbeat"}` → 1 stream
  with full structlog payload (actor_cn, event_id, result).
- nginx port-80 redirect logs reach Loki (status=301).

## Plan deviations / fixes

1. **Removed step-ca-health scrape job** — step-ca `/health` returns JSON, not
   Prometheus format (would show DOWN). Liveness via Docker healthcheck + cAdvisor.
2. **Naive datetime fix in `metrics_hooks.py`** — SQLite returns naive datetimes;
   tz-aware subtraction crashes the gauge refresh. Added UTC assumption.
3. **Single-file step-ca password mount** — least privilege (daemon needs only
   the CA password, not provisioner passwords).
4. **Loki schema v13 + TSDB from the start** — `compactor` block mandatory in 3.x
   for retention; `delete_request_store: filesystem` required.

## Known gaps (to address in 9C or later)

- **nginx mTLS access logs (port 443) are file-based**, written to
  `/var/log/nginx/mtls-access.log`, so Promtail (stdout reader) doesn't capture
  them — only the port-80 301 redirects. Options: route mtls-access to
  `/dev/stdout`, or add a Promtail static_config tailing the nginx-logs volume.
  The security-critical audit trail (controller structlog) IS fully captured.
- **busybox wget** in alpine images can't resolve single-label Docker names
  (`controller`) — use FQDN alias or IP for manual tests. Prometheus (Go) and
  nginx resolve the short name fine, so scraping/proxying are unaffected.

## Useful queries (for 9C dashboards)

PromQL — nodes by state: `sum by (state) (thesis_nodes_total)`
PromQL — mTLS failure rate: `rate(thesis_mtls_auth_total{result!="success"}[5m])`
LogQL — rejections: `{container="thesis-controller", audit_result="rejected"}`
LogQL — nginx 4xx/5xx: `{container="thesis-nginx"} |~ " (4\\d\\d|5\\d\\d) "`

## Pending for Step 9C

- Grafana service in compose
- Nginx `/grafana/` location with mTLS gating + Grafana root_url subpath
- Provisioned datasources (Prometheus + Loki) and dashboards
- Three dashboards: Lab Overview, PKI & mTLS, Audit Trail
