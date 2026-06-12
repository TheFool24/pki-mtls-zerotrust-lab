# PKI / mTLS / Zero Trust Laboratory

Bachelor thesis lab implementation — Master Controller infrastructure for
secure machine-to-machine communication using PKI, mTLS, and Zero Trust principles.

**Author:** Georgi Dinkov
**Institution:** ВУТП (Висше училище по телекомуникации и пощи), 2026
**Specialty:** Cybersecurity of Communication Technologies

## Status

✅ **Lab build complete — thesis defense upcoming.** Six experimental scenarios
evaluated; evidence and configuration captured for the defense artifact set.
The thesis document and appendices have been finalized against this codebase.

## Architecture overview

- **Network** — 3 VLANs over MikroTik hAP ax³ (L3 router/firewall) +
  Cisco Catalyst 3560 (L2 switch with `switchport protected` on Pi access
  ports for intra-VLAN isolation):
  - VLAN 10 — Management (10.50.10.0/24, mgmt PC)
  - VLAN 20 — Controller (10.50.20.0/24, master-lab host)
  - VLAN 30 — Nodes (10.50.30.0/24, Raspberry Pi fleet)
- **Controller** — HP Z2 Tower G9, Ubuntu Server 24.04 LTS, 10.50.20.200.
  Runs the 9-container thesis stack via Docker Compose.
- **Node fleet** — 4× Raspberry Pi 4 with distinct certificate roles
  (Pi-01..04). Pi-03 retired as part of Scenario 3 compromise evidence;
  Pi-04 reserved for live onboarding demonstration at defense.
- **PKI** — Smallstep step-ca with two-tier hierarchy (offline Root + online
  Intermediate). Five provisioners: thesis-admin (JWK), node-enrollment (JWK,
  CSR-sign), operator-access (JWK, 90-day human cert), service-scraper (JWK,
  CN-policied), node-renewal (X5C).
- **Transport** — bidirectional mTLS via nginx reverse proxy on
  `controller.thesis.local`. TLS 1.3 only, AEAD ciphers, full
  `ssl_verify_client on` at the server level.
- **Observability** — PLG stack: Prometheus + Grafana 11.4 (behind the
  mTLS gate) + Loki 3.3 + Promtail. Three dashboards: Lab Overview,
  PKI & mTLS Security, Audit Trail Explorer.

## Project structure

| Path | Purpose |
|------|---------|
| `docker-compose.yml` | 9-container service orchestration (step-ca, controller, nginx, prometheus, node-exporter, cadvisor, loki, promtail, grafana) |
| `step-ca/` | Smallstep step-ca data, secrets references, issued certs (gitignored where sensitive) |
| `nginx/` | mTLS reverse proxy config (`conf.d/mtls.conf`) |
| `controller/` | FastAPI controller app — `app/api/` endpoints, `app/core/` auth/audit/metrics, SQLite audit DB |
| `node-agent/` | Python agent installed on each Pi — heartbeat loop + mTLS metrics server, structlog → Loki |
| `ansible/` | Node provisioning playbooks (10-base, 20-enroll CSR-sign, 30-agent, 40-renew); CSR-sign enrollment keeps the private key on the node and the enrollment password on the controller |
| `monitoring/` | Prometheus + Loki + Promtail + Grafana configs and provisioned dashboards |
| `scripts/` | Operational scripts (cert auto-renew + post-renewal hooks) |
| `docs/setup-notes/` | Chronological build log (steps 01–08) — source material for thesis Chapter 3 |
| `docs/evidence/` | Experimental scenario captures — see _Defense artifacts_ below |
| `docs/PRE-DEFENSE-CHECKLIST.md` | Air-gap blockers, posture-revert items, defense-day verification |

## Defense artifacts

The six experimental scenarios from Chapter 5 are backed by captured evidence
in `docs/evidence/`:

| Scenario | Evidence directory | What it proves |
|----------|--------------------|----------------|
| Сц. 1 — Valid connectivity & registration | `step-7c/`, `step-8d/`, `step-9c/` | TLS 1.3 = 462/462 (100%), AEAD ciphers, `ssl_client_verify=SUCCESS` for all identities |
| Сц. 2 — Certificate revocation (Pi-02) | `step-11/scenario-2-revocation/` | Full lifecycle: healthy → revoke (serial 235076…781) → ~75 s block window → re-issue (new serial 140769…575) → recovery |
| Сц. 3 — Compromise & isolation (Pi-03) | `step-12/scenario-3-compromise/` | 4 attack vectors: 1 control success + 3 rejected (pi-99 register, pi-01 impersonate, pi-01 metrics scrape) |
| Сц. 4 — Lateral-movement defense | `step-9c/` (audit trail) | 6× `AUTH_FAILURE` events: pi-test → pi-fake-1..6 register, all rejected |
| Сц. 5 — Live onboarding | — | Live demo at defense (Pi-04). Mechanism proven by Pi-02 + Pi-03 first-shot Ansible provisioning |
| Сц. 6 — Network segmentation & air-gap | `step-13/scenario-6-segmentation/` | Before/after pair: provisioning rule active (curl HTTP 200) → rule removed → 8× DROP-NODES-WAN log entries + curl timeout |
| Step 14 — L2 isolation (Cisco PVLAN edge) | `step-14-l2-isolation/` | Before/after pair: Pi↔Pi pings 0% loss → `switchport protected` on Fa0/2-5 → Pi↔Pi 100% loss, all legitimate flows unaffected |

## Build / setup notes

Chronological build log under `docs/setup-notes/`:

- `01-base-system.md` — Ubuntu, Docker, fail2ban, NTP
- `02-step-ca-init.md` — Root + Intermediate CA initialization, provisioners
- `03-nginx-mtls.md` — mTLS reverse proxy (server-level `ssl_verify_client on`)
- `04-fastapi-controller.md` — Controller app, audit DB, mTLS identity parsing
- `05-monitoring-stack.md` — PLG stack bring-up
- `06-operator-access-cert.md` — 90-day human browser cert (operator-access provisioner)
- `07-ca-backup-restore.md` — Encrypted CA backup procedure
- `08-step-8-node-fleet.md` — Node fleet provisioning (8A base, 8B enrollment, 8C agent, 8D renewal)

## License / scope

This codebase is the lab artifact backing a bachelor's thesis. It is published
for academic transparency and reproducibility of the defense evidence; it is
not maintained as a general-purpose product.
