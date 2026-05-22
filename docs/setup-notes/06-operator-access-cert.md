# 06 — Operator access certificate (long-lived browser client cert)

**Date:** 2026-05-22
**Trigger:** Browser access to Grafana broke with `400 No required SSL certificate
was sent` after a multi-day break.

## Problem

The browser's imported client cert was a *copy* of the controller leaf cert,
which is a **24h auto-renewing machine cert**. After the break it had long
expired; Firefox won't present an expired client cert, so nginx received none
and returned 400. Re-importing the controller cert every day is impractical and
conflates the human operator's identity with the controller service identity.

## Decision

Issue a **dedicated, long-lived operator client certificate** for human/browser
access, separate from machine identities:

- CN/SAN: `operator.thesis.local`
- Validity: **90 days** (2026-05-22 → 2026-08-20)
- Distinct provisioner with relaxed cert-duration claims
- NOT auto-renewed (machine certs stay 24h+auto-renew — thesis narrative intact;
  the human operator simply re-issues + re-imports when it expires)

The controller's authz treats this CN as `role=unknown` (not `controller.`/`pi-`),
which is correct: the operator cert is for passing the nginx mTLS gate to reach
Grafana, not for machine API operations. Admin API ops still use the controller
cert via curl.

## Implementation

step-ca's default provisioner claims cap `maxTLSCertDuration` at 24h, so a new
provisioner with relaxed claims was added (same offline `ca.json`-edit method as
Step 5.7, since Remote Management is not enabled).

### New provisioner: `operator-access` (JWK)

```json
{
  "type": "JWK",
  "name": "operator-access",
  "key": { ...ES256 public JWK... },
  "encryptedKey": "<compact JWE>",
  "claims": {
    "maxTLSCertDuration": "2160h",
    "defaultTLSCertDuration": "2160h"
  }
}
```

- Provisioner password: `step-ca/secrets/operator-access-password.txt` (chmod 600,
  gitignored, save to password manager).
- JWK keypair generated with `step crypto jwk create ... --alg ES256`.
- Injected into `ca.json` provisioners array, step-ca restarted. Now 4
  provisioners total (thesis-admin, node-enrollment, node-renewal, operator-access).

### Issue the operator cert

```bash
docker run --rm --network thesis-lab-net \
    -v /opt/thesis-lab/step-ca/secrets:/secrets:ro \
    -v /opt/thesis-lab/step-ca/issued/operator:/workdir \
    -v "$HOME/.step:/home/step/.step" -e STEPPATH=/home/step/.step -w /workdir \
    smallstep/step-cli:0.28.1 step ca certificate \
        "operator.thesis.local" operator.crt operator.key \
        --san "operator.thesis.local" \
        --provisioner "operator-access" \
        --provisioner-password-file /secrets/operator-access-password.txt \
        --not-after 2160h
```

### Package for the browser (PKCS#12)

```bash
docker run --rm \
    -v /opt/thesis-lab/step-ca/issued/operator:/workdir \
    -v /opt/thesis-lab/step-ca/secrets:/secrets:ro -w /workdir \
    smallstep/step-cli:0.28.1 step certificate p12 \
        operator.p12 operator.crt operator.key \
        --password-file /secrets/operator-p12-password.txt
```

- p12 transport password: `step-ca/secrets/operator-p12-password.txt` (gitignored).
- Files in `step-ca/issued/operator/` (gitignored): operator.crt, operator.key,
  operator.p12.

## Verification

- `operator.crt` → nginx mTLS gate → `/grafana/api/health` = HTTP 200
- `whoami` = `{verified:true, role:unknown}` (expected)
- no cert = HTTP 400 (gate still enforced)

## Renewal (manual, every ~90 days)

When `operator.thesis.local` expires (2026-08-20), re-run the issue + p12 steps
above and re-import into the browser. No daemon — humans renew on demand.

## Browser import (Windows / Firefox)

1. `scp jojo@10.50.20.200:/opt/thesis-lab/step-ca/issued/operator/operator.p12 .`
2. Import into Firefox (Settings → Privacy & Security → Certificates → View
   Certificates → Your Certificates → Import) OR Windows Personal store (with
   `security.osclientcerts.autoload=true` in Firefox). Password = contents of
   `operator-p12-password.txt`.
3. The Root CA is already trusted from Step 9C-i. Browse to
   `https://controller.thesis.local/grafana/` and pick the operator cert.
