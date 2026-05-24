# 07 — CA backup & restore

**Date:** 2026-05-24
**Why:** The entire PKI (Root + Intermediate private keys) lived only in the
`thesis-step-ca-data` Docker volume on a single disk. The Root extraction
ceremony is still deferred, so a disk failure would make the CA unrecoverable
and orphan every issued cert/node. This adds an encrypted, off-box backup.

## What is backed up

Full contents of the `thesis-step-ca-data` volume:
- `secrets/root_ca_key`, `secrets/intermediate_ca_key` (encrypted with `ca-password`)
- `certs/root_ca.crt`, `certs/intermediate_ca.crt`
- `config/ca.json` (+ historical `.bak` copies) — provisioners, claims
- `db/` (badger DB — issued-certificate records / revocation state)

Confidentiality: the private keys are already encrypted with `ca-password`;
the whole archive is additionally encrypted with the same secret (AES-256,
PBKDF2). One secret (`ca-password`, in the password manager) protects both the
live keys and the backup. Restore needs only that secret.

## Backup location

Off the git repo, in `~/thesis-ca-backups/` (chmod 700):
`step-ca-volume-<TIMESTAMP>.tar.gz.enc` (chmod 600)

**Off-box step (do manually):** copy the `.enc` file somewhere physically
separate (USB stick / another machine), e.g. from the Windows PC:
```powershell
scp jojo@10.50.20.200:~/thesis-ca-backups/step-ca-volume-*.tar.gz.enc $env:USERPROFILE\Desktop\
```

## Create a fresh backup

```bash
TS=$(date +%Y%m%d-%H%M%S)
mkdir -p ~/thesis-ca-backups && chmod 700 ~/thesis-ca-backups
docker run --rm -v thesis-step-ca-data:/data:ro -v ~/thesis-ca-backups:/backup \
    alpine:latest tar czf /backup/step-ca-volume-$TS.tar.gz -C /data .
sudo chown jojo:jojo ~/thesis-ca-backups/step-ca-volume-$TS.tar.gz
openssl enc -aes-256-cbc -salt -pbkdf2 \
    -in  ~/thesis-ca-backups/step-ca-volume-$TS.tar.gz \
    -out ~/thesis-ca-backups/step-ca-volume-$TS.tar.gz.enc \
    -pass file:/opt/thesis-lab/step-ca/secrets/ca-password.txt
rm ~/thesis-ca-backups/step-ca-volume-$TS.tar.gz
chmod 600 ~/thesis-ca-backups/step-ca-volume-$TS.tar.gz.enc
```

## Verify a backup (without restoring)

```bash
openssl enc -d -aes-256-cbc -pbkdf2 \
    -in ~/thesis-ca-backups/step-ca-volume-<TS>.tar.gz.enc \
    -pass file:/opt/thesis-lab/step-ca/secrets/ca-password.txt \
    | tar tzf - | grep -E "root_ca_key|intermediate_ca_key|ca.json"
```

## Restore (disaster recovery)

Requires `ca-password` (from the password manager) written to a file.

```bash
cd /opt/thesis-lab
docker compose stop step-ca               # if running

# Recreate the named volume (if the old one is gone):
docker volume create thesis-step-ca-data

# Decrypt + extract straight into the volume via a helper container:
openssl enc -d -aes-256-cbc -pbkdf2 \
    -in ~/thesis-ca-backups/step-ca-volume-<TS>.tar.gz.enc \
    -pass file:/path/to/ca-password.txt \
  | docker run --rm -i -v thesis-step-ca-data:/data alpine:latest \
        tar xzf - -C /data

docker compose up -d step-ca
curl -sk https://10.50.20.200:9000/health        # {"status":"ok"}
curl -sk https://10.50.20.200:9000/provisioners | jq '.provisioners[].name'
```

The restored CA keeps the same Root/Intermediate keys, so all previously issued
certs remain valid and new certs chain correctly — no node re-enrollment needed.

## Cadence

Re-run the backup after any CA-state change (new provisioner, claims edit) and
periodically (the `db/` accumulates issued-cert records). The archive is tiny
(~15 KB), so frequent backups are cheap.

## Note

This is an interim safeguard. The planned **Root extraction ceremony** (move the
Root key offline to USB/sealed envelope, delete from the volume) is the stronger
long-term posture and is still on the roadmap after Pi enrollment is validated.
