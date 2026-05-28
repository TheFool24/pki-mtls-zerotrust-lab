# Сценарий 2 — Certificate revocation (revoke → lockout → recovery)

Captured 2026-05-28. Pi-02 is the revoked-cert scenario node. This is the full
lifecycle (operational-after): a valid node is revoked, locked out, then
recovered via controller-mediated re-enrollment.

## Timeline

| # | Artifact | What it shows |
|---|----------|---------------|
| 01 | `01-baseline-healthy.txt` | Pi-02 enrolled + heartbeating `200`, `state=active`. |
| 02 | `02-revoke-command.txt` | Operator revokes Pi-02's cert from the controller via an **admin-provisioner revoke token** (`step ca revoke --token`). Serial `235076…629781`. |
| 03 | `03-rejection-window.txt` | ~75 s later (CRL regen 30 s + controller refresh 60 s), Pi-02's heartbeats return **403 Forbidden**; the agent logs `heartbeat_failed`. |
| 04 | `04-audit-row.json` | Controller audit row `auth.failure / rejected / "certificate revoked"` (serial `b0da2b15…`) — dashboard-visible via Audit Trail Explorer (`result=rejected`). |
| 05 | `05-dashboard-rejection.png` | *(capture at defense / from Grafana)* Audit Trail Explorer showing the live rejection. |
| 06 | `06-reenroll.txt` | Controller-mediated recovery: re-run the CSR-sign play → **new** serial `140769…848575` (key regenerated on the node, never leaves it). |
| 07 | `07-recovery-healthy.txt` | Agent restart → `cert_valid` → `already_registered` (409 handled gracefully) → heartbeat **200**; `state=active`. |

## Key properties demonstrated

- **Active revocation is enforced** (not just chain+expiry): a revoked-but-unexpired
  cert is rejected at the controller, per request (Zero Trust), with audit evidence.
  Old serial is in the CRL; new serial is not.
- **No self-recovery / controller-mediated recovery**: the node cannot un-revoke
  itself; recovery requires the controller re-issuing a fresh identity (CSR-sign).
- **Metrics vs. identity split**: Prometheus keeps scraping Pi-02 throughout (the
  scraper presents its own, non-revoked cert) — only Pi-02's *own* outbound calls
  (heartbeat, using its revoked cert) are rejected. So the dashboards show the
  heartbeat going stale + the audit rejection, while the metrics target stays up.

## How it's shown at defense

- **Live re-demo** (Pi-02 is operational): revoke → wait ~1–2 min → show 403 +
  audit rejection → re-enroll → show recovery. Repeatable any number of times.
- **Fallback**: these captured artifacts + the persisted audit row.

## Mechanism notes (Гл. 3.8)

- step-ca CRL must be tuned for prompt propagation: `generationInterval: 30s` /
  `cacheDuration: 1m` (default ~24 h cache would delay revocation by a day).
- Controller fetches `/crl` every 60 s, caches revoked serials, rejects matches
  (nginx forwards `$ssl_client_serial`; serial normalized hex→int).
