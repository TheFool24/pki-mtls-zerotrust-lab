# Pre-defense / air-gap checklist

Running list of dev-mode shortcuts and deferred items to address before the
thesis defense (and before running the lab air-gapped). Each entry notes the
file/command so nothing is forgotten on defense day.

Status legend: ☐ todo · ☑ done · ⏳ deferred-by-design

---

## A. Air-gap blockers (things that reach the public internet)

- ☐ **Public NTP fallback.** `/etc/chrony/conf.d/thesis-lab.conf` has
  `pool 2.bg.pool.ntp.org iburst`. For air-gap, remove it so only the MikroTik
  (`server 10.50.20.1 iburst prefer`) is used, then `sudo systemctl restart chrony`
  and confirm `chronyc sources` shows only `10.50.20.1`. (Addresses ОИ-5.)
- ☐ **Grafana plugin auto-install.** Grafana 11.4 fetches `grafana-lokiexplore-app`
  from grafana.com on first boot. For air-gap, disable preinstall
  (`GF_INSTALL_PLUGINS=""` / preinstall-disabled env) or pre-seed the plugin into
  the `thesis-grafana-data` volume while still online.
- ☐ **All container images pre-pulled.** Every image is version-pinned; confirm
  all are present locally (`docker images`) before disconnecting — air-gap means
  no registry pulls. (step-ca, step-cli, nginx, prometheus, node-exporter,
  cadvisor, loki, promtail, grafana, controller[built], alpine, python:3.12-slim.)
- ☐ **GitHub repo fully pushed.** The repo is source of truth; `git push` all
  commits while online (push needs internet/PAT).

## B. Security posture to revert / harden

- ☐ **NOPASSWD sudo for jojo.** `/etc/sudoers.d/90-jojo-nopasswd` grants
  passwordless root. Intentional lab convenience; for a production-like posture,
  remove it (or scope it). Note: removing it means interactive sudo again.
- ☐ **Grafana admin password file is chmod 644.** `monitoring/grafana/admin-password.txt`
  is world-readable on the host (required because Grafana runs as uid 472 and
  Compose file-secrets bind-mount as-is). Acceptable for single-user lab; mention
  as a known trade-off, or move to a proper secret store.
- ☑ **Encrypted CA backup exists.** `~/thesis-ca-backups/*.tar.gz.enc` — refresh
  before defense (`docs/setup-notes/07-ca-backup-restore.md`) and keep a copy
  off-box.
- ☐ **Confirm `THESIS_ALLOW_UNAUTHENTICATED` is not set / False.** Dev escape
  hatch in `controller/app/core/config.py` (default False). Must stay False.

## C. Deferred-by-design items to complete

- ⏳ **Root extraction ceremony.** Root CA key still lives in the
  `thesis-step-ca-data` volume. Plan: export + encrypt to USB/sealed envelope,
  delete from volume, verify step-ca still serves (uses Intermediate). Demo this
  live at defense — strong evidence of two-tier offline-Root design.
- ⏳ **Node cert renewal automation.** The `node-renewal` X5C provisioner exists
  but isn't wired to anything. Bake `step ca renew` (systemd timer, X5C auth) into
  the Pi bootstrap (Step 8) so all node certs self-renew — otherwise 24h node
  certs expire between sessions (already a recurring pain with pi-test).
- ⏳ **MikroTik internal DNS.** Currently using `/etc/hosts` on the controller for
  `*.thesis.local`. Set up MikroTik DNS (or Ansible-managed `/etc/hosts`) so Pi
  nodes resolve names without manual edits.
- ☐ **Clean up test artifacts.** `pi-test` node + cert are scaffolding. Decide
  whether to keep as a reference identity or remove before the real fleet demo.

## D. Defense-day verification (run the morning of)

- ☐ All 9 containers healthy: `cd /opt/thesis-lab && docker compose ps`
- ☐ Controller leaf cert valid (auto-renew working): check
  `step certificate inspect step-ca/issued/controller/controller.crt --short`
- ☐ Operator browser cert valid (expires **2026-08-20**) — re-issue if defense is
  after that date (`docs/setup-notes/06-operator-access-cert.md`).
- ☐ mTLS gate works end-to-end: no-cert → 400; valid cert → 200.
- ☐ All 3 Grafana dashboards render with live data.
- ☐ Fresh CA backup taken and copied off-box.
- ☐ Time synced to MikroTik: `chronyc tracking` (`Leap status: Normal`).
