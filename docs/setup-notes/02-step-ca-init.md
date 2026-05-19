# 02 — step-ca initialization

**Date:** 2026-05-19
**Status:** ✅ Init complete — provisioners + service start still pending (Step 5.7+)

## Plan

1. Pull `smallstep/step-ca:0.28.x` Docker image
2. Generate strong CA password and store in `step-ca/secrets/`
3. Initialize Root CA with `step ca init` via one-shot container
4. Capture and securely store CA fingerprint (critical for node onboarding)
5. Configure JWK provisioner — for node enrollment
6. Configure X5C provisioner — for certificate renewal
7. Start step-ca as Docker Compose service
8. Issue first certificate (for the controller itself)

## Decisions for thesis Chapter 2.4 / 3.3

- Root CA validity: **10 years** (standard for organizational Root CA) — confirmed in actual cert (2026-05-19 → 2036-05-16)
- Leaf certificate validity: **24 hours** with auto-renewal at 2/3 lifetime — _to be configured_
- Key algorithm: **ECDSA P-256** — confirmed (both Root and Intermediate use P-256)
- Hierarchy: **two-tier** — Root CA → Intermediate CA → leaf certs
  - ⚠️ Revised from original plan ("single-tier"). step-ca's `step ca init`
    creates an Intermediate CA by default in `standalone` deployment, and
    online signing uses the Intermediate so the Root key stays cold.
    Updating Гл. 2.4 to reflect this — more conventional and safer (Root key
    is only used to sign the Intermediate, then can be archived offline).

## Execution log

### 5.1 — Image pull (2026-05-19)

Pinned versions for reproducibility:

```
smallstep/step-ca:0.28.1    (digest a8308bddba86)
smallstep/step-cli:0.28.1   (digest 98a4efae1a8c)
```

### 5.2 — Password generation (2026-05-19)

- CA password: `openssl rand -base64 32` → `/opt/thesis-lab/step-ca/secrets/ca-password.txt` (chmod 600)
- Provisioner password: `openssl rand -base64 24` → `/opt/thesis-lab/step-ca/secrets/provisioner-password.txt` (chmod 600)
- Both saved to password manager (Bitwarden / 1Password / KeePass).

### 5.3 — `step ca init` (2026-05-19)

Non-interactive init via one-shot container:

```bash
docker volume create thesis-step-ca-data

docker run --rm \
    -v thesis-step-ca-data:/home/step \
    -v /opt/thesis-lab/step-ca/secrets:/secrets:ro \
    smallstep/step-ca:0.28.1 \
    step ca init \
        --name="Thesis Lab CA" \
        --dns="ca.thesis.local,10.50.20.200" \
        --address=":9000" \
        --provisioner="thesis-admin@vutp.bg" \
        --password-file="/secrets/ca-password.txt" \
        --provisioner-password-file="/secrets/provisioner-password.txt" \
        --deployment-type="standalone"
```

Output (extract):

- Root certificate: `/home/step/certs/root_ca.crt` (in volume `thesis-step-ca-data`)
- Root private key: `/home/step/secrets/root_ca_key` (encrypted with CA password)
- Intermediate certificate: `/home/step/certs/intermediate_ca.crt`
- Intermediate private key: `/home/step/secrets/intermediate_ca_key` (encrypted with CA password)
- Default CA config: `/home/step/config/ca.json`

### 5.4 — Root CA fingerprint

Public reference value (committed to git for node onboarding):

```
996fa2b9fe43dcf59b280b0b60d9e4017e765bb528b54c770dcc4524dbaead52
```

Stored at: `/opt/thesis-lab/step-ca/CA-FINGERPRINT.txt`

### 5.5 — Verify Root CA structure (output)

```
X.509v3 Root CA Certificate (ECDSA P-256) [Serial: 1893...0486]
  Subject:     Thesis Lab CA Root CA
  Issuer:      Thesis Lab CA Root CA              ← self-signed
  Valid from:  2026-05-19T00:14:10Z
          to:  2036-05-16T00:14:10Z              ← 10 years

X.509v3 Intermediate CA Certificate (ECDSA P-256) [Serial: 2269...1007]
  Subject:     Thesis Lab CA Intermediate CA
  Issuer:      Thesis Lab CA Root CA              ← signed by Root
  Valid from:  2026-05-19T00:14:11Z
          to:  2036-05-16T00:14:11Z
```

Default provisioner (created by `step ca init`):

| Field | Value |
|---|---|
| Type | JWK |
| Name | `thesis-admin@vutp.bg` |
| Key alg | ES256 (EC P-256) |
| Encryption | PBES2-HS256+A128KW (provisioner password protects private key) |

## Бележки за Глава 3

- step-ca's `--deployment-type=standalone` puts Root + Intermediate + online API
  all on the controller. For a production deployment the Root key would be
  generated offline and stored in an HSM; for the lab this is acceptable but
  worth calling out as a deviation from production best practice.
- The JWK provisioner created by `init` is the default admin provisioner — it
  has full authority over the CA. Node enrollment will use **separate** JWK
  and X5C provisioners (Step 5.7) with narrower scope.

## Next steps (Step 5.7+)

1. Create node-enrollment JWK provisioner (separate from admin)
2. Create X5C provisioner for certificate renewal
3. Start step-ca as Docker Compose service (move from one-shot to persistent)
4. Issue first leaf certificate for the controller itself
