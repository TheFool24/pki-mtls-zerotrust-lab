# PKI / mTLS / Zero Trust Laboratory

A fully working Zero Trust architecture for secure machine-to-machine
communication, built on physical, air-gapped hardware and validated against
real adversarial scenarios - not a diagram or a simulation. A management
controller issues short-lived X.509 identities to a fleet of Raspberry Pi
nodes and enforces mutual TLS on every connection, with network
microsegmentation and full audit logging on top.

Designed, built, and defended as a bachelor's thesis at the University of
Telecommunications and Post (Sofia), 2026.

**Author:** Georgi Dinkov
**Institution:** University of Telecommunications and Post (UTP), Sofia, 2026
**Specialty:** Cybersecurity of Communication Technologies

## Status

Complete. Designed, built, and defended as a bachelor's thesis (June 2026),
graded Excellent on both the written review and the oral defense. Six
adversarial scenarios validated the Zero Trust design on real hardware; all
supporting evidence and configuration are versioned in this repository
alongside the thesis document.

## What this demonstrates

- Machine identity via a self-hosted PKI (Smallstep step-ca), with short-lived
  X.509 certificates and automated renewal - no long-lived shared secrets.
- Mutual TLS (TLS 1.3 only) on every controller-to-node connection, verified
  in both directions, with CN-based authorization on top of certificate
  validity.
- Zero Trust enforcement at three layers: L2 port isolation, L3 default-deny
  segmentation, and application-layer mTLS with identity checks.
- Empirical validation: every security claim is backed by a captured artifact -
  a timestamp, serial number, HTTP code, or log line - across six scenarios.

## Results

| Scenario | What it tests | Result |
|----------|---------------|--------|
| 1 - Valid connectivity and registration | Legitimate node handshake and enrollment | 462 of 462 handshakes on TLS 1.3 (100%), AEAD ciphers, `ssl_client_verify=SUCCESS` for all identities |
| 2 - Certificate revocation and recovery | Revoke a live node, then re-issue | Full lifecycle: healthy, revoke, block within seconds, re-issue with new serial, recover |
| 3 - Compromise and isolation | Stolen key used from a compromised node | 4 vectors: 1 legitimate control success, 3 rejected (register, impersonate, cross-node scrape) |
| 4 - Lateral-movement defense | Repeated unauthorized registration attempts | 6 of 6 `AUTH_FAILURE` events, all rejected at the identity layer |
| 5 - Live onboarding | Enroll a new node on demand | Demonstrated live; mechanism proven by first-shot Ansible provisioning of earlier nodes |
| 6 - Network segmentation and air-gap | Node reach to the internet | Before/after: provisioning rule active (HTTP 200), rule removed, traffic dropped (DROP-NODES-WAN) with timeout |
| L2 isolation (Cisco PVLAN edge) | Direct node-to-node traffic | Before/after: Pi-to-Pi 0% loss, `switchport protected` applied, Pi-to-Pi 100% loss, legitimate flows unaffected |

## Architecture overview

- **Network** - 3 VLANs over MikroTik hAP ax3 (L3 router/firewall) plus Cisco
  Catalyst 3560 (L2 switch with `switchport protected` on the Pi access ports
  for intra-VLAN isolation):
  - VLAN 10 - Management (10.50.10.0/24, management workstation)
  - VLAN 20 - Controller (10.50.20.0/24, master-lab host)
  - VLAN 30 - Nodes (10.50.30.0/24, Raspberry Pi fleet)
- **Controller** - HP Z2 Tower G9, Ubuntu Server 24.04 LTS, 10.50.20.200.
  Runs the nine-container thesis stack via Docker Compose.
- **Node fleet** - 4x Raspberry Pi 4 with distinct certificate roles
  (Pi-01 to Pi-04). Pi-03 retired as part of Scenario 3 compromise evidence;
  Pi-04 used for the live onboarding demonstration.
- **PKI** - Smallstep step-ca with a two-tier hierarchy (offline Root, online
  Intermediate). Five provisioners: thesis-admin (JWK), node-enrollment (JWK,
  CSR-sign), operator-access (JWK, 90-day human cert), service-scraper (JWK,
  CN-policied), node-renewal (X5C).
- **Transport** - bidirectional mTLS via an nginx reverse proxy on
  `controller.thesis.local`. TLS 1.3 only, AEAD ciphers, server-level
  `ssl_verify_client on`.
- **Observability** - PLG stack: Prometheus, Grafana 11.4 (behind the mTLS
  gate), Loki 3.3, and Promtail. Three dashboards: Lab Overview, PKI and mTLS
  Security, Audit Trail Explorer.

## Project structure

| Path | Purpose |
|------|---------|
| `docker-compose.yml` | Nine-container service orchestration (step-ca, controller, nginx, prometheus, node-exporter, cadvisor, loki, promtail, grafana) |
| `step-ca/` | Smallstep step-ca data, secret references, issued certs (gitignored where sensitive) |
| `nginx/` | mTLS reverse proxy config (`conf.d/mtls.conf`) |
| `controller/` | FastAPI controller app - `app/api/` endpoints, `app/core/` auth/audit/metrics, SQLite audit DB |
| `node-agent/` | Python agent installed on each Pi - heartbeat loop and mTLS metrics server, structlog to Loki |
| `ansible/` | Node provisioning playbooks (10-base, 20-enroll CSR-sign, 30-agent, 40-renew); CSR-sign enrollment keeps the private key on the node and the enrollment password on the controller |
| `monitoring/` | Prometheus, Loki, Promtail, and Grafana configs and provisioned dashboards |
| `scripts/` | Operational scripts (certificate auto-renew and post-renewal hooks) |
| `docs/setup-notes/` | Chronological build log (steps 01 to 08) - source material for thesis Chapter 3 |
| `docs/evidence/` | Experimental scenario captures - see Results above |
| `docs/PRE-DEFENSE-CHECKLIST.md` | Air-gap blockers, posture-revert items, defense-day verification |

## Build and setup notes

Chronological build log under `docs/setup-notes/`:

- `01-base-system.md` - Ubuntu, Docker, fail2ban, NTP
- `02-step-ca-init.md` - Root and Intermediate CA initialization, provisioners
- `03-nginx-mtls.md` - mTLS reverse proxy (server-level `ssl_verify_client on`)
- `04-fastapi-controller.md` - Controller app, audit DB, mTLS identity parsing
- `05-monitoring-stack.md` - PLG stack bring-up
- `06-operator-access-cert.md` - 90-day human browser cert (operator-access provisioner)
- `07-ca-backup-restore.md` - Encrypted CA backup procedure
- `08-step-8-node-fleet.md` - Node fleet provisioning (8A base, 8B enrollment, 8C agent, 8D renewal)

## Limitations and production path

This is a prototype built to validate the security architecture, not a
production system. The scope choices are deliberate, and each has a clean
upgrade path that does not touch the security design:

- **SQLite audit database** - zero-configuration single-writer store, ideal for
  a four-node lab. Production path: PostgreSQL, a connection-string change
  rather than a redesign (the application already uses an async database URL).
- **Static name resolution via `/etc/hosts`** - deterministic for a small
  air-gapped environment with no internet DNS. Production path: an internal DNS
  server, which also strengthens Zero Trust by adding a controlled audit point.
- **Provisioning window** - a temporary, explicitly flagged firewall rule opens
  WAN access only during initial node provisioning, then is removed (Scenario 6
  documents the air-gap activation). Production path: an internal package mirror
  on the controller, so provisioning never requires internet access.

## Security note

This is a teaching and lab artifact. All secrets, password hashes, and private
keys are redacted or gitignored; the certificate material that remains is public
key material only. Do not reuse any configuration here as-is in a real
environment.

## License and scope

This codebase is the lab artifact backing a bachelor's thesis. It is published
for academic transparency and reproducibility of the defense evidence; it is not
maintained as a general-purpose product.
