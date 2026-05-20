# 04 — FastAPI Controller (Step 7A + 7B + 7C)

**Date:** 2026-05-21
**Step:** 7
**Status:** ✅ Complete — controller API live behind Nginx mTLS, 10/10 tests green

## Цел

Application layer на контролера — REST API за управление на nodes, audit trail
на всички действия, mTLS identity-based authorization. Седи зад Nginx mTLS
proxy от Стъпка 6.

## Архитектурни решения

### Identity extraction (Decision 1 — Подход A)

CN-only extraction от `X-Client-DN` header, set-нат от Nginx. FastAPI security
dependency (`get_mtls_identity`) парсва CN regex-ом и връща typed dataclass
`MTLSIdentity` с computed properties (`is_controller`, `is_node`, `node_id`).

Без mTLS headers → 401. С невалидни → 403. Спасява срещу bypass scenarios
където някой би могъл да удари FastAPI директно on container network (защитен
още с `--forwarded-allow-ips 172.28.0.20` за Uvicorn).

### Database (Decision 2)

- SQLite + SQLModel + WAL + aiosqlite
- File: `/app/data/thesis.db` в named volume `thesis-controller-data`
- Foreign keys enforced via SQLAlchemy connect event listener (per-connection pragma)
- WAL + synchronous=NORMAL за read-mostly workload performance

**Implementation gotcha #1:** SQLite URL за async absolute path трябва четири
slashes: `sqlite+aiosqlite:////app/data/thesis.db` (три slashes = relative от CWD,
което резолва грешно до `/app/app/data/...` → "unable to open database file").

**Implementation gotcha #2:** `PRAGMA foreign_keys=ON` е per-connection в SQLite.
Setting го само в `init_db()` го прилага само за init connection-а. SQLAlchemy
connection pool отваря множество връзки — затова event listener на `connect`.

**Implementation note #3 (enum storage):** SQLAlchemy съхранява `str`-Enum
членовете по ИМЕ (`NODE_REGISTER`, `ACTIVE`), не по value (`node.register`,
`active`). ORM-ът превежда прозрачно — API сериализира values, а audit
`action` filter-ът работи и с двете форми (тествано). Единственият ефект е,
че raw DB dump-ът (`audit-events-dump.json`) показва имена, докато API/глава
показват values. Документирано за да не обърка reviewer. (Ако трябва пълна
консистентност по-късно — `Column(sa.Enum(..., values_callable=...))` + wipe.)

### API surface

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/v1/health` | GET | none | Liveness probe |
| `/api/v1/whoami` | GET | mTLS | Identity verification |
| `/api/v1/nodes` | GET | mTLS | List nodes |
| `/api/v1/nodes` | POST | mTLS+self | Register node (self or controller-driven) |
| `/api/v1/nodes/{id}` | GET | mTLS | Single node |
| `/api/v1/nodes/{id}/heartbeat` | POST | mTLS+self | Check-in |
| `/api/v1/audit` | GET | mTLS | Audit log (filterable by actor_cn, action) |

### Audit logging (Decision 4)

Double-write pattern:
1. DB row (queryable via `/api/v1/audit`)
2. Structured JSON log line on stdout (Loki ingestion in Стъпка 9)

Every state-changing action goes through `core/audit.py:record_event()`.
Включва AUTH_FAILURE events за rejected requests — критично за thesis Сценарий 4.

### Lateral movement defense

Pi-test cannot register pi-01 (Test 7) — proven empirically. Nodes can only
register/heartbeat as themselves (CN must match payload `common_name`).
Controller-issued certs bypass this rule (allows admin operations).

## Container

- Image: `thesis-controller:0.1.0` (custom multi-stage build)
- Base: `python:3.12-slim`, user `thesis` (UID 1000, non-root)
- Exposed: 8000 (Docker network only, NOT host) → reachable only via Nginx
- Network: `thesis-lab-net` 172.28.0.30 (static)
- Volume: `thesis-controller-data:/app/data` (SQLite DB)
- Healthcheck: HTTP GET `/api/v1/health` via Python urllib (no curl in image)

## Nginx integration (Step 7C)

`location /api/` → `proxy_pass http://controller_backend` (`server controller:8000`)
Headers forwarded: `X-Client-Verify`, `X-Client-DN`, standard X-Forwarded-*
`/docs` and `/openapi.json` also proxied for thesis demo.
`ssl_client_certificate` = `ca-trust.crt` (Root + Intermediate) — plan said
`ca-root.crt` which doesn't exist in this deployment (Step 6 used different names).

## Verification results (Step 7C, 10 tests)

Controller-cert tests (1-4): Nginx /health echo, proxied /api/v1/health,
whoami (role=controller), empty nodes list — all pass.

Pi-test-cert tests (5-10):
- whoami → role=node, node_id=pi-test
- self-registration → 201, state=onboarding
- register pi-01 → **403 (lateral movement defense)**
- heartbeat → state onboarding→active
- list nodes → pi-test active
- audit log → 3 events (register success, auth.failure rejected, heartbeat success)

Evidence captured in `docs/evidence/step-7c/`:
- `nginx-mtls-access.log` — Nginx access entries
- `controller-stdout.log` — structlog JSON output
- `audit-events-dump.json` — raw DB dump of audit table

## Plan deviations / fixes applied

1. **SQLite URL slash count** — fourth slash for absolute path
2. **Foreign keys pragma** — SQLAlchemy connect event listener (per-connection)
3. **Cert renewal hardening** — `renew-controller-cert.sh` self-heals from expired
   state (re-issues via admin provisioner if `step ca renew` fails). Triggered by
   a real expiry while the lab box was off during a break (2026-05-20).
4. **Uvicorn log-config** — removed `--log-config /dev/null` (crashes; uvicorn
   parses it as INI/JSON config) — using default logger output
5. **nginx ssl_client_certificate** — `ca-trust.crt` not `ca-root.crt`

## Pending за Стъпка 8

- Real Pi-01 enrollment (replace pi-test with first physical node)
- Ansible playbook за node bootstrap
- Cert renewal automation на ноди (cron/systemd + X5C provisioner)
- Stale heartbeat detection (background task, marks nodes STALE after threshold)
