# Runbook — manual node re-enrollment

## When this is needed

The node was powered off **longer than its certificate lifetime (7 days)**, so the
cert expired. `step ca renew` (the routine renewal path) authenticates with the
*existing valid* cert and therefore **cannot recover an expired cert**. By design
the node stores **no enrollment secret**, so there is no automatic recovery — this
is the intended security trade-off (a stolen node yields no credential to mint new
node identities). Recovery is deliberate, manual, and **controller-mediated**.

Symptoms: `thesis-node-agent.service` fails to start; journal shows
`cert_expired` / `cert_unreadable` with `MANUAL RE-ENROLLMENT REQUIRED`; and/or
`renew-cert.sh` logs `FATAL: 'step ca renew' FAILED`.

## Procedure (run from the CONTROLLER, which holds the enrollment password)

The enrollment password is transferred over the trusted SSH channel, used once,
and shredded — all in a **single SSH session** (systemd-logind `RemoveIPC=yes`
wipes `/dev/shm` between separate logins, so it must be one session).

```bash
# From the controller (master-lab). Pipes node-enrollment password via stdin.
ssh pi-01 'umask 077
cat > /dev/shm/ne-pw
cd /dev/shm
/usr/local/bin/step ca certificate "pi-01.thesis.local" pi-01.crt pi-01.key \
    --san pi-01.thesis.local --san pi-01 --san 10.50.30.11 \
    --provisioner node-enrollment \
    --provisioner-password-file /dev/shm/ne-pw \
    --ca-url https://ca.thesis.local:9000 \
    --root /etc/thesis-lab/certs/ca-root.crt \
    --not-after 168h --force
# Install (cert jojo:jojo 644, key jojo:jojo 600 — matches the renewal-as-jojo model)
sudo install -o jojo -g jojo -m 644 pi-01.crt /etc/thesis-lab/certs/pi-01.crt
sudo install -o jojo -g jojo -m 600 pi-01.key /etc/thesis-lab/certs/pi-01.key
shred -u /dev/shm/ne-pw pi-01.crt pi-01.key
' < /opt/thesis-lab/step-ca/secrets/node-enrollment-password.txt
```

```bash
# Restart the agent (it re-registers idempotently and resumes heartbeats):
ssh pi-01 'sudo systemctl restart thesis-node-agent.service && \
           sleep 3 && sudo systemctl status thesis-node-agent.service --no-pager | head -5'
```

## Verify

```bash
# New cert validity window is fresh:
ssh pi-01 '/usr/local/bin/step certificate inspect /etc/thesis-lab/certs/pi-01.crt --short'
# Controller sees the node active again (operator cert from the controller):
curl -s --cacert /opt/thesis-lab/nginx/certs/ca-trust.crt \
     --cert /opt/thesis-lab/step-ca/issued/operator/operator.crt \
     --key  /opt/thesis-lab/step-ca/issued/operator/operator.key \
     https://controller.thesis.local/api/v1/nodes/pi-01 | jq '{node_id,state,last_heartbeat_at}'
```

## Note

This is rare under normal operation. The 7-day cert lifetime is sized so that a
power-on at least once per week lets `step ca renew` (timer + renew-on-boot) keep
the cert alive indefinitely without ever reaching this runbook.
