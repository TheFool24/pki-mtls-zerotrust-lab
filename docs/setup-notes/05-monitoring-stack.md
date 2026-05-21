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

## Step 9C — Grafana (done: 9C-i + 9C-ii.1)

### 9C-i — Grafana behind mTLS

- `grafana/grafana:11.4.0` at 172.28.0.60, proxied via nginx `location /grafana/`.
- **nginx proxy_pass MUST have no trailing slash** (`http://grafana:3000;`).
  Grafana runs `serve_from_sub_path=true` and expects the `/grafana/` prefix;
  a trailing slash strips it → infinite 301 loop. (Confirmed via Location header;
  the protocol-mismatch theory was a red herring.)
- Admin password via Docker file secret; **chmod 644** required because Compose
  file-secrets bind-mount the source as-is and Grafana runs as uid 472
  (uid/mode secret options are Swarm-only). Still gitignored.
- Datasources auto-provisioned (Prometheus default + Loki).
- nginx access logs converted to JSON (`log_format mtls_json`) → /dev/stdout;
  Promtail promotes `ssl_protocol`, `ssl_client_verify`, `status`, `method` to
  Loki labels. Closed the 9B file-based-logs gap.
- **Air-gap caveat:** Grafana 11.4 auto-installs `grafana-lokiexplore-app` by
  phoning grafana.com on first boot. Disable plugin preinstall or pre-seed the
  volume before the air-gapped defense.

### 9C-ii.1 — Lab Overview dashboard

7 panels: service health (4 jobs), host CPU, host memory, host disk (root fs),
host network I/O, controller request rate by endpoint, controller latency p50/p95.

**cAdvisor container-attribution limitation (important finding):**
The original plan's container CPU/memory panels used
`container_*{name=~"thesis-.*"}` — these return **no data** here. Root cause:
Docker uses the **containerd-snapshotter** storage driver
(`overlayfs / io.containerd.snapshotter.v1`), and cAdvisor's Docker integration
expects the classic `overlay2` layerdb layout. cAdvisor logs:
`Failed to create existing container: /system.slice/docker-<id>.scope: failed to
identify the read-write layer ID ... layerdb/mounts/<id>/mount-id: no such file`.
Result: cAdvisor emits host/system-slice cgroup metrics but **no per-Docker-
container series** (no `name` label at all).

Decision: keep cAdvisor for host/cgroup/machine metrics; replaced the two
container-by-name panels with node-exporter panels (disk usage, network I/O).
Real per-container CPU/mem would require switching Docker to the `overlay2`
storage driver (recreates the whole stack — not worth it for the lab) or
pointing cAdvisor at containerd directly. Documented as a Гл. 3 implementation
finding.

**Metric-name corrections applied vs plan:**
- HTTP request counter is `http_requests_total{handler,method,status}`
  (status values like `2xx`, not a `status_code` label). Panel 6 uses `handler`.
- Latency histogram `http_request_duration_seconds_bucket{handler,le}` — works.

### Pending for 9C-ii (next)

- Dashboard 2: PKI & mTLS Security (custom thesis_* metrics + nginx ssl labels)
- Dashboard 3: Audit Trail Explorer (Loki-based log exploration)
