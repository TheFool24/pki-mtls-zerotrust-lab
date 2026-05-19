# 02 — step-ca initialization

**Date:** 2026-05-19
**Status:** ✅ Complete — Root CA init + provisioners + Compose service + first leaf cert

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

## Step 5.7 — Provisioners (2026-05-19)

### Deviation from original plan: ca.json edit instead of CLI

Original plan used `step ca provisioner add` via step-ca's Admin API, but
Remote Management was NOT enabled at init time (the `--remote-management`
flag was not passed). The Admin API path is gated on RM. Switched to direct
`ca.json` editing, which is the canonical fallback for standalone deployments
without RM.

The plan also had a password-file mix-up that we corrected: it referenced
`/secrets/ca-password.txt` for admin auth, but the `thesis-admin@vutp.bg`
JWK provisioner was encrypted with `provisioner-password.txt` during init.
The CA password file only encrypts the CA root/intermediate keys, not the
provisioner JWK.

### Provisioners configured

| Name | Type | Purpose | Encryption password |
|------|------|---------|---------------------|
| `thesis-admin@vutp.bg` | JWK | Admin operations (manual) | provisioner-password.txt |
| `node-enrollment` | JWK | First-time Pi enrollment | node-enrollment-password.txt |
| `node-renewal` | X5C | Auto 24h renewal | _N/A_ (uses existing leaf cert) |

### How node-enrollment was added

```bash
# Generate the JWK keypair (encrypted with node-enrollment-password.txt):
docker run --rm \
    -v /opt/thesis-lab/step-ca/secrets:/secrets \
    -w /secrets \
    smallstep/step-cli:0.28.1 \
    step crypto jwk create node-enrollment-pub.json node-enrollment-key.json \
        --use sig --alg ES256 \
        --password-file=/secrets/node-enrollment-password.txt

# Convert the JWE JSON serialization to compact form (5 dot-separated parts):
COMPACT_JWE=$(jq -r '"\(.protected).\(.encrypted_key).\(.iv).\(.ciphertext).\(.tag)"' \
    secrets/node-enrollment-key.json)

# Build the provisioner JSON object and append to ca.json's provisioners array
# (read ca.json out via alpine container, edit on host with jq, write back via container).
```

### How node-renewal X5C was added

The X5C provisioner's `roots` field accepts base64-encoded PEM. Used the
Root CA cert as the trust anchor (any cert signed by the Root—including
controller and node leaf certs—can authenticate to this provisioner).

```bash
ROOT_PEM=$(docker run --rm -v thesis-step-ca-data:/home/step alpine \
    cat /home/step/certs/root_ca.crt)
ROOT_B64=$(echo -n "$ROOT_PEM" | base64 -w 0)
# Then jq-append {type: "X5C", name: "node-renewal", roots: $ROOT_B64} to provisioners.
```

### Backup

Pre-edit `ca.json` backup retained inside the volume:
`/home/step/config/ca.json.bak-20260519-033805` (visible only via container mount).

## Step 5.8 — Docker Compose service (2026-05-19)

step-ca migrated from ad-hoc `docker run` to a Compose service defined in
`/opt/thesis-lab/docker-compose.yml`.

Key config decisions:

- **Image pinned** to `smallstep/step-ca:0.28.1` (reproducibility for thesis)
- **Host bind** `10.50.20.200:9000:9000` — only VLAN 20 interface, not 0.0.0.0
- **Static IP** `172.28.0.10` on `thesis-lab-net` (172.28.0.0/24, bridge)
- **Network alias** `ca.thesis.local` (so other Compose services on the same
  network can address the CA by its DNS name, matching the cert SANs)
- **External volume** `thesis-step-ca-data` (preserves CA state across restarts)
- **Healthcheck** — `wget --no-check-certificate -qO- /health | grep ok`
  (step-ca's `/health` returns `{"status":"ok"}` over HTTPS with self-signed
  cert from its own Intermediate, so cert verification is skipped)

### Password mount detail

The smallstep/step-ca image's entrypoint reads the CA password from a fixed
path: `/home/step/secrets/password`. Bind-mounted our host
`ca-password.txt` directly onto that path so the password lives on the host
filesystem (NOT inside the volume that also contains the encrypted keys —
co-locating both would defeat the encryption).

### Verify output

```
$ docker compose ps
thesis-step-ca   smallstep/step-ca:0.28.1   Up (healthy)   10.50.20.200:9000->9000/tcp

$ curl -sk https://10.50.20.200:9000/health
{"status":"ok"}

$ curl -sk https://10.50.20.200:9000/provisioners | jq '.provisioners[].name'
"thesis-admin@vutp.bg"
"node-enrollment"
"node-renewal"
```

## Step 5.9 — First leaf certificate for the controller (2026-05-19)

Smoke test for the full issuance pipeline using the admin JWK provisioner.

### /etc/hosts entry

Added a hosts entry on the controller so the SAN names resolve locally:

```
10.50.20.200    ca.thesis.local controller.thesis.local master-lab
```

(MikroTik DNS setup is deferred — `/etc/hosts` covers the controller for now,
Ansible will manage the Pi nodes' hosts files when they come online.)

### step CLI wrapper

A wrapper at `/usr/local/bin/step` runs `smallstep/step-cli:0.28.1` in the
thesis-lab network with the host's `~/.step` directory mounted as STEPPATH.
Lets `step` work on the host as if it were a native CLI.

### Bootstrap + issue

```bash
step ca bootstrap \
    --ca-url https://ca.thesis.local:9000 \
    --fingerprint $(cat /opt/thesis-lab/step-ca/CA-FINGERPRINT.txt)

cd /opt/thesis-lab/step-ca/issued/controller
step ca certificate \
    "controller.thesis.local" controller.crt controller.key \
    --san "controller.thesis.local" \
    --san "10.50.20.200" \
    --san "master-lab" \
    --provisioner "thesis-admin@vutp.bg" \
    --provisioner-password-file /secrets/provisioner-password.txt \
    --not-after 24h
```

### Cert details

| Field | Value |
|---|---|
| Subject | `controller.thesis.local` |
| SANs | `controller.thesis.local`, `master-lab`, `10.50.20.200` |
| Issuer | Thesis Lab CA Intermediate CA |
| Provisioner | `thesis-admin@vutp.bg` (JWK) |
| Validity | 24 hours |
| Key | ECDSA P-256 |
| Chain verify | `openssl verify -CAfile root_ca.crt -untrusted intermediate_ca.crt controller.crt` → `OK` |

The cert files are at `/opt/thesis-lab/step-ca/issued/controller/` (gitignored).

## Pending decisions / future steps

- **Root extraction ceremony** — defer until Nginx mTLS proxy works end-to-end.
  Root CA private key currently lives in the volume alongside the Intermediate.
  Move to USB / sealed envelope only after the full chain is validated.
- **MikroTik internal DNS** — currently using `/etc/hosts` on the controller.
  Pi nodes will need either MikroTik DNS or Ansible-managed `/etc/hosts`.
- **Cert renewal automation** — controller cert expires in 24h. Will need
  `step ca renew` via systemd timer (or step-renewer sidecar) when the
  Nginx mTLS proxy is up and depending on this cert.
