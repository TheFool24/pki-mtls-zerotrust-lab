"""Prometheus metrics — custom business metrics for thesis observability.

Combines:
- Automatic HTTP metrics via prometheus-fastapi-instrumentator
  (request count, latency histogram, in-flight)
- Custom business metrics specific to controller domain
  (nodes by state, audit events by action, mTLS auth outcomes)
"""
from prometheus_client import Counter, Gauge, Histogram

# ── Nodes ──
nodes_total = Gauge(
    "thesis_nodes_total",
    "Total registered nodes",
    labelnames=["state", "role"],
)

# ── mTLS authentication outcomes ──
mtls_auth_total = Counter(
    "thesis_mtls_auth_total",
    "mTLS authentication attempts",
    labelnames=["result"],  # success | missing_headers | verify_failed | cn_parse_failed
)

# ── Audit events ──
audit_events_total = Counter(
    "thesis_audit_events_total",
    "Audit events recorded",
    labelnames=["action", "result"],
)

# ── Heartbeat freshness ──
node_last_heartbeat_seconds = Gauge(
    "thesis_node_last_heartbeat_seconds",
    "Seconds since node's last heartbeat",
    labelnames=["node_id"],
)

# ── Cert issuance (will be populated in Step 8 when nodes self-enroll) ──
cert_issued_total = Counter(
    "thesis_cert_issued_total",
    "Certificates issued by step-ca (observed via audit events)",
    labelnames=["provisioner"],
)

# ── DB operation latency (sanity check that SQLite isn't bottleneck) ──
db_operation_duration = Histogram(
    "thesis_db_operation_duration_seconds",
    "Database operation duration",
    labelnames=["operation"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)
