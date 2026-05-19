# 03 — Nginx mTLS reverse proxy

**Date:** 2026-05-19
**Step:** 6
**Status:** ✅ Complete

## Цел

Първа имплементация на mTLS termination layer-а. Nginx седи на ръба на
контролера, представя server cert на инициатора и налага задължителна
проверка на client cert, преди да допусне трафик до downstream FastAPI
приложението (което идва в Стъпка 7).

## Архитектурно решение: cert reuse

Server identity на Nginx използва същия `controller.thesis.local` leaf cert
като FastAPI ще използва за идентификация на host-а. За production двата
компонента биха имали отделни идентичности (controller vs `nginx.thesis.local`),
но за лаб scope-а на тезата това е acceptable simplification.

Future work mention в Гл. 6: separate Nginx cert with own SAN + own
private key (защитава controller's key ако Nginx process е компрометиран).

## Cert chain & trust bundle

`step ca certificate` записва leaf+intermediate в крайния файл по подразбиране —
не е нужна допълнителна конкатенация. Файлове в `/opt/thesis-lab/nginx/certs/`:

| File | Contents | Purpose |
|------|----------|---------|
| `server.crt` | leaf + intermediate (full chain) | TLS server identity |
| `server.key` | leaf private key | TLS server identity |
| `ca-trust.crt` | Root + Intermediate concat | Trust anchors за client cert verification |
| `root_ca.crt` | Root only | Reference (also used for client `--cacert` testing) |
| `intermediate_ca.crt` | Intermediate only | Reference / debugging |

`nginx/certs/` е в `.gitignore` (runtime artefacts).

## Конфигурация highlights

| Setting | Value | Reasoning |
|---------|-------|-----------|
| `ssl_protocols` | `TLSv1.3` only | ИС-4 from Гл. 2.1.2 |
| `http2 on` | enabled | modern syntax (nginx 1.25+); avoids deprecated `listen ... http2` |
| `ssl_verify_client` | `on` (not `optional`) | enforces mTLS strictly |
| `ssl_verify_depth` | `2` | covers Root → Intermediate → leaf with headroom |
| `ssl_client_certificate` | `ca-trust.crt` (Root + Intermediate) | accepts certs anchored to either |
| `ssl_session_tickets` | `off` | full handshake visibility for testing |
| Server names | `controller.thesis.local`, `10.50.20.200`, `master-lab` | matches cert SANs |
| HTTP→HTTPS redirect | port 80 → 301 https | defense in depth |
| Localhost health endpoint | `127.0.0.1:8080 /nginx-alive` | container healthcheck (no client cert needed) |
| Healthcheck command | `nginx -t` | validates config + cert file accessibility (busybox wget can't do client certs) |

Client cert info exposed via `$ssl_client_s_dn` and `$ssl_client_verify`
nginx variables. Will be forwarded to FastAPI upstream as
`X-Client-DN` and `X-Client-Verify` headers in Step 7.

## Verification tests (2026-05-19, immediately after deploy)

### Test 1 — No client cert

```bash
curl -k https://10.50.20.200/health
```

Result: **HTTP 400** with body `No required SSL certificate was sent`.
This is the expected Nginx behavior with `ssl_verify_client on` —
TLS handshake completes (server doesn't strictly require cert in handshake),
then Nginx returns the 400 at HTTP layer. Access denied. ✓

### Test 2 — Valid client cert (controller.crt)

```bash
curl -v \
    --cacert nginx/certs/root_ca.crt \
    --cert step-ca/issued/controller/controller.crt \
    --key step-ca/issued/controller/controller.key \
    --resolve controller.thesis.local:443:10.50.20.200 \
    https://controller.thesis.local/health
```

Result:
```
* TLSv1.3 (OUT), TLS handshake, Client hello (1):
* TLSv1.3 (IN), TLS handshake, Server hello (2):
* TLSv1.3 (IN), TLS handshake, Request CERT (13):       ← Nginx requests client cert
* TLSv1.3 (IN), TLS handshake, Certificate (11):
* TLSv1.3 (OUT), TLS handshake, Certificate (11):       ← curl presents client cert
* TLSv1.3 (OUT), TLS handshake, Finished (20):
* SSL connection using TLSv1.3 / TLS_AES_256_GCM_SHA384 / X25519 / id-ecPublicKey
* using HTTP/2
< HTTP/2 200
{"status":"ok","mtls":"verified","client_cn":"CN=controller.thesis.local"}
```

Full TLS 1.3 handshake including both server and client `Certificate` and
`CERT verify` messages, ECDSA P-256 (X25519 key exchange, ECDSA cert), HTTP/2,
200 response with the verified client CN echoed back. ✓

### Test 3 — HTTP → HTTPS redirect

```bash
curl -sI http://10.50.20.200/
HTTP/1.1 301 Moved Permanently
Server: nginx/1.27.5
```

✓

### Test 4 — _TODO в Стъпка ~10._

**Revoked cert**: cert from revoked Pi attempts handshake → rejected.
Requires Сценарий 2 setup with Pi-02 and `step ca revoke` flow.

## Docker Compose service

- Container: `thesis-nginx`
- Image: `nginx:1.27-alpine` (pinned)
- Bound: `10.50.20.200:443` (mTLS) and `:80` (HTTP→HTTPS redirect)
- Network: `thesis-lab-net` at `172.28.0.20`, alias `nginx.thesis.local`
- `depends_on: step-ca → service_healthy` — starts only after CA is reachable
- Volumes:
  - `./nginx/conf.d → /etc/nginx/conf.d:ro` (config)
  - `./nginx/certs → /etc/nginx/certs:ro` (server + CA bundle)
  - named volume `thesis-nginx-logs → /var/log/nginx`
- Healthcheck: `nginx -t` every 30s (validates config + cert paths)
- Labels: `thesis.role=mtls-proxy`, `thesis.tier=edge`

## Auto-renewal of the controller leaf cert

Independent of nginx itself, a systemd timer was added in the same step to
renew the controller leaf cert before it expires (24h validity):

- `/opt/thesis-lab/scripts/renew-controller-cert.sh` — runs `step certificate
  needs-renewal --expires-in=8h`; if true, runs `step ca renew --force` and
  refreshes the nginx server.crt/server.key copies, then `nginx -s reload`.
- `/etc/systemd/system/thesis-cert-renew.service` — oneshot, runs as jojo.
- `/etc/systemd/system/thesis-cert-renew.timer` — `OnBootSec=5min`,
  `OnUnitActiveSec=8h`, `Persistent=true`.
- Log file: `/var/log/thesis-cert-renew.log`.

The script `cd`s to the cert directory and uses relative filenames because
the `step` wrapper container mounts `$(pwd)` as `/workdir` — passing host
paths into the container fails (those paths don't exist inside).

## Pending

- Replace placeholder `location /` with `proxy_pass` to FastAPI after Стъпка 7.
- Add OCSP stapling once revocation testing is wired up (Сценарий 2 / Step ~10).
- Consider rate limiting via `limit_req_zone` once production patterns are clearer.
- Production-grade: separate `nginx.thesis.local` server cert with its own key
  (currently reusing controller cert).
