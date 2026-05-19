# PKI / mTLS / Zero Trust Laboratory

Bachelor thesis lab implementation — Master Controller infrastructure for
secure machine-to-machine communication using PKI, mTLS and Zero Trust principles.

**Author:** jojo
**Institution:** ВУТП (Висше училище по телекомуникации и пощи), 2026
**Specialty:** Cybersecurity of Communication Technologies

## Architecture overview

- **Network**: 3 VLANs on MikroTik hAP ax3 + Cisco Catalyst 3560
  - VLAN 10 — Management (10.50.10.0/24)
  - VLAN 20 — Controller (10.50.20.0/24)
  - VLAN 30 — Nodes (10.50.30.0/24)
- **Controller**: HP Z2 Tower G9, Ubuntu Server 24.04 LTS, 10.50.20.200
- **Nodes**: 4× Raspberry Pi 4 with distinct certificate roles
- **PKI**: Smallstep step-ca with JWK + X5C provisioners
- **Transport**: bidirectional mTLS via Nginx reverse proxy
- **Monitoring**: Prometheus + Grafana + Loki (PLG stack)

## Project structure

| Path | Purpose |
|------|---------|
| `docker-compose.yml` | Main service orchestration |
| `step-ca/` | PKI Certificate Authority (Smallstep step-ca) |
| `nginx/` | mTLS reverse proxy configuration |
| `controller/` | FastAPI controller application |
| `scripts/` | Helper / operational scripts |
| `docs/setup-notes/` | Step-by-step setup log (for thesis Chapter 3) |
| `docs/architecture/` | Architecture decisions (ADRs) |

## Setup notes

See `docs/setup-notes/` for the chronological build log:
- `01-base-system.md` — Ubuntu, Docker, fail2ban, NTP
- `02-step-ca-init.md` — Root CA initialization
- (more as we progress)

## Status

🚧 **Work in progress** — actively being built as part of thesis work.
