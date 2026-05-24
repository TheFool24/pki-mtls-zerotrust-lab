# Step 9C evidence — observability stack

Machine-readable evidence backing the three Grafana dashboards, captured
2026-05-24. These are reproducible textual artifacts for the thesis appendix;
pair them with browser screenshots of the dashboards for the Chapter 5 figures.

## Files

| File | Contents | Thesis use |
|------|----------|-----------|
| `dashboards-list.json` | The 3 provisioned dashboards (uid, folder) | Гл. 4 — observability setup |
| `prometheus-targets.json` | All Prometheus scrape targets `up` | Гл. 4 — metrics pipeline health |
| `pki-mtls-evidence.txt` | TLS 1.3 = 100%, protocol/cipher distribution, verified client identities, mTLS auth outcomes | Гл. 5 — Сценарий 1 (valid auth), Сценарий 5 (ИС-4 compliance) |
| `audit-trail-evidence.txt` | Audit event breakdown, activity by actor, sample rejected events | Гл. 5 — Сценарий 4 (lateral-movement defense) |
| `audit-events-dump.json` | Full raw dump of the `audit_events` table | Приложение Б — complete audit trail |

## Headline numbers (at capture time)

- **TLS 1.3 compliance: 100%** (462/462 handshakes) — no fallback, ИС-4 satisfied
- **Cipher suites:** TLS_AES_128_GCM_SHA256, TLS_AES_256_GCM_SHA384 (both AEAD)
- **Verified identities:** controller, operator, pi-test — all `ssl_client_verify=SUCCESS`
- **Lateral-movement defense:** 5+ `AUTH_FAILURE` events where pi-test tried to
  register other nodes — all rejected ("actor not authorized to register this node")

## Browser screenshots still needed (visual figures)

Capture from `https://controller.thesis.local/grafana/` (operator cert):
1. **Thesis Lab — Overview** — service health + resource panels
2. **Thesis Lab — PKI & mTLS Security** — TLS 1.3 = 100% stat, identities table,
   cipher distribution (the centerpiece Chapter 5 figure)
3. **Thesis Lab — Audit Trail Explorer** — with the Result filter set to
   `rejected` (shows the lateral-movement defense live)

## Note on enum casing

The raw DB dump shows action/result as enum NAMES (`AUTH_FAILURE`, `REJECTED`)
while the API/dashboards show enum VALUES (`auth.failure`, `rejected`). This is
SQLAlchemy's default str-enum storage; the ORM translates transparently (see
`docs/setup-notes/04-fastapi-controller.md`).
