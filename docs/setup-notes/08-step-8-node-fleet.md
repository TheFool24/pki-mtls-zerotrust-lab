# Step 8 — Node fleet (Pi enrollment + agent + mTLS scraping)

**Status:** 8A/8B/8C ✅ complete · 8D (cert renewal automation) deferred
**Node:** pi-01 (Raspberry Pi 4, Ubuntu 24.04 arm64, 10.50.30.11, VLAN 30)

This note consolidates the whole node-lifecycle chapter: base provisioning (8A),
PKI enrollment (8B), and the live agent + observability integration (8C). It
also records the architectural decisions that diverged from the original plan,
with rationale — these feed Гл. 2.6 and Гл. 3.

---

## 8A — Base system (recap)

- Pi 4 + Ubuntu 24.04 arm64, static IP `10.50.30.11` (MikroTik DHCP reservation).
- SSH hardening drop-in, NOPASSWD sudo for `jojo` (lab convenience, documented).
- Python venv at `/opt/thesis-node/venv`.
- `/etc/cloud/cloud.cfg.d/99-thesis-hosts.cfg` sets `manage_etc_hosts: false` so
  hand-added `/etc/hosts` entries survive reboots (cloud-init was regenerating
  the file and wiping them).
- Windows PC reaches the Pi only via `ProxyJump` through the controller
  (VLAN10→VLAN30 is denied by design).

## 8B — Enrollment (recap)

- 7-day node leaf cert issued via the `node-enrollment` JWK provisioner,
  installed at `/etc/thesis-lab/certs/{pi-01.crt(644 root), pi-01.key(600 jojo),
  ca-root.crt(644 root)}`.
- Enrollment password transferred, used once, and **shredded** in a single SSH
  session (systemd-logind `RemoveIPC=yes` wipes `/dev/shm` between logins, so
  transfer+issue+install+shred must happen in one session).
- Milestone verified: `whoami` returns `verified:true, role:node, node_id:pi-01`;
  no-cert control returns HTTP 400.

---

## 8C — Node agent + mTLS metrics scraping

The agent (`/opt/thesis-lab/node-agent/`, deployed to `/opt/thesis-node/app/`)
runs as a single systemd service with two concurrent asyncio tasks:

1. **Heartbeat loop** — idempotent self-registration on startup, then a
   `POST /api/v1/nodes/pi-01/heartbeat` every 30 s ±5 s jitter.
2. **Metrics server** — aiohttp HTTPS listener on `:9100`, mTLS-terminated,
   exposing psutil-derived node metrics for Prometheus.

### Scraper identity: `service-scraper` provisioner

A fifth provisioner was added (role-based taxonomy: node-enrollment, node-renewal,
operator-access, thesis-admin, **service-scraper**). It issues the cert Prometheus
presents when scraping nodes.

- **24h TTL** (matches the controller leaf — even infra services use short-lived
  certs; renewal automation already battle-tested).
- **CN restriction via the policy engine, NOT a name template.** step-ca's
  `text/template` engine does not expose `regexMatch`, and triple-escaping a
  regex through shell→jq→JSON→template is unworkable. The declarative
  `policy.x509.allow` block is the supported mechanism:
  ```json
  "policy": { "x509": { "allow": {
      "commonNames": ["prometheus.thesis.local"],
      "dnsNames": ["prometheus.thesis.local", "prometheus", "*-scraper.thesis.local"]
  }}}
  ```
  Blast radius: a compromised `service-scraper` key can only issue scraper-tier
  identities, never arbitrary CNs (unlike `thesis-admin`).

### Defense-in-depth: allowed-CN check on the node

`ssl.CERT_REQUIRED` ensures the scraper presents *a* valid CA-signed leaf, but
that alone would let any valid leaf (e.g. a compromised neighbor node) scrape
metrics. The agent's aiohttp middleware additionally checks the peer cert CN
against `THESIS_ALLOWED_SCRAPER_CNS` (config, comma-separated). Verified:

| Client cert | Result |
|---|---|
| `prometheus.thesis.local` (allowed) | **200** |
| `pi-01.thesis.local` (valid chain, not allowlisted) | **403** + `metrics_scrape_rejected` log |
| no client cert | TLS handshake refused |

### Audit log scope: security events only

The heartbeat endpoint was refactored so the audit table stays a *security*
artifact, not a fleet-telemetry log:

| Event | Audit row? |
|---|---|
| `node.register` first success / CN-mismatch rejection | ✅ |
| `node.register` idempotent retry (same CN, 409) | ❌ (structlog only) |
| heartbeat causing a state transition (onboarding→active) | ✅ `node.state_change` |
| routine heartbeat (no state change) | ❌ (structlog + `last_heartbeat_at` + metric) |
| heartbeat from non-matching identity | ✅ `auth.failure` |

Verified clean sequence on pi-01: `id=58 node.register success`,
`id=59 node.state_change (onboarding→active)`, then silence while heartbeats flow
(`thesis_node_heartbeats_total` climbs, no further audit rows).

### MikroTik

One new permanent rule: `forward accept, in=vlan20-ctrl out=vlan30-nodes
tcp/9100` (the controller→node scrape path). This is the only new attack surface;
it is bounded by mTLS + the CN allowlist above.

### Renewal

`scripts/renew-controller-cert.sh` was refactored to `scripts/renew-certs.sh`:
a `renew_cert()` function driven by a cert registry, so one systemd timer
(`thesis-cert-renew.timer`, every 8h) now renews both the controller leaf and
the Prometheus scraper cert. Each cert has a `post_<name>` hook (nginx reload /
Prometheus SIGHUP). Fallback re-issue uses the cert's own provisioner — the
scraper provisioner password lives **only on the controller** (trusted infra),
never on nodes.

---

## Architectural decisions (feeds Гл. 2.6 / Гл. 3)

### 7-day node cert lifetime (revision of the 24h plan)

The lab operates intermittently — powered off for days between sessions. A 24h
node cert would strand a node after >24h offline: the X5C renewal path can't
authenticate with an expired cert. 7 days preserves the "short-lived cert"
principle while accommodating the real operational rhythm. A production
deployment with continuous operation would retain 24h.

### No JWK enrollment password persisted on nodes

A compromised node must not yield an enrollment credential (which would let an
attacker enroll arbitrary node CNs). The enrollment password is used once at 8B
and shredded. Consequence for 8D: renewal must be **X5C-only** (authenticates
with the existing cert, no secret). A node offline >7 days (cert expired) requires
**manual re-enrollment** — rare, and the operator is physically present anyway.
There is deliberately **no automated JWK re-enrollment fallback**, because that
would reintroduce the secret onto the node and silently undo this property.

### 8D plan (next)

- systemd timer (every ~8h) + **renew-on-boot** unit: `step ca renew` via X5C
  when inside the renewal window. Renew-on-boot is the *resilience* pattern
  (covers gaps between timer fires across power cycles).
- **No** JWK fallback — on expired cert the agent logs a structured error and
  exits (systemd will keep restarting; recovery is the manual re-enroll runbook).
- Verification must include a **negative test**: wreck the cert, confirm the
  agent fails loudly and does *not* self-recover (proves the absence of fallback).

---

## Gotchas found this session

- **httpx 0.28 silently drops the `cert=(crt,key)` tuple form** → nginx returns
  400 ("No required SSL certificate was sent"). Fix: build an explicit
  `ssl.SSLContext` (`create_default_context(cafile=...)` + `load_cert_chain(...)`)
  and pass it as `verify=ctx`. curl with the same files worked, which isolated
  the bug to the client library, not the cert/PKI.
- **Graceful shutdown:** the register-retry loop ignored SIGTERM, so `systemd
  stop` would hang until SIGKILL. Fix: a `stopper` task on the shutdown event +
  `asyncio.wait(..., FIRST_COMPLETED)`, then cancel workers. Now exits in ~0.3s.
- **Controller code is baked into the image** (no source bind-mount), so editing
  `controller/app/**` requires `docker compose build controller`, not just
  `restart`. A plain restart silently runs the old code.
- **Prometheus `/etc/prometheus` is bind-mounted read-only**, so cert files can't
  be mounted into a `certs/` subdir of it — mounted at `/etc/thesis-certs/` instead.
- **Pi can't resolve `controller.thesis.local`** until an `/etc/hosts` entry is
  added (persists now because `manage_etc_hosts: false`). Pi also doesn't resolve
  its own FQDN — local mTLS tests need `curl --resolve`.
- **psutil `cpu_percent(interval=None)`** returns 0.0 on the first call (no
  baseline); real values appear from the second scrape on.

## Pre-defense follow-ups

- Clean evidence capture: the audit table still has test rows (ids 55–57) from
  pre-rebuild runs and synthetic nodes (pi-test, demo-alpha, demo-beta). Decide
  whether to reset before the Гл. 5 capture.
- `curlimages/curl` image was pulled for a one-off test — not part of the stack;
  remove or ignore for air-gap.
