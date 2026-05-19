# 02 — step-ca initialization

**Date:** _to be filled_
**Status:** 🚧 In progress (Step 5 of master controller setup)

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

- Root CA validity: **10 years** (standard for organizational Root CA)
- Leaf certificate validity: **24 hours** with auto-renewal at 2/3 lifetime
- Key algorithm: **ECDSA P-256** (vs RSA-3072 — performance for RPi)
- Hierarchy: **single-tier** (Root CA → leaf certs; no Intermediate CA for lab)

## Execution log

_To be filled during Step 5._
