# Сценарий 3 — Compromise & Containment (Pi-03)

## Compromise premise

We simulate compromise by using **pi-03's own cert + key directly**, modeling an
attacker who has extracted the node's private key (physical access, disk imaging,
memory dump). The thesis claim is **not** "we prevent key theft" — no PKI system
physically can. The claim is:

> A stolen key authenticates as exactly **one** least-privilege-scoped identity
> (pi-03), and the layered authorization confines the attacker to pi-03's
> legitimate operations. Compromise of one node does **not** cascade.

The four-vector evidence below proves this: one in-scope action succeeds (200),
every out-of-scope action is rejected at its corresponding defense layer (403).

## Design decision (Option A dismissed as a thesis point)

Source IP is deliberately **not** an authentication factor. In Zero Trust, the
**certificate is the identity**, independent of network location. Binding identity
to source IP would reintroduce the perimeter assumptions the model explicitly
rejects (a legitimate node on a changed/roaming IP would falsely fail). This is a
deliberate architectural stance, not a gap.

## Evidence sequence

| # | Artifact | What it shows |
|---|----------|---------------|
| 01 | `01-baseline-healthy.txt` | Pi-03 enrolled (Ansible-provisioned, third node, playbook first-shot), heartbeating `200`, `state=active`. |
| 02 | `02-control-legitimate.txt` | **Control vector** — pi-03 heartbeats AS pi-03 → **200**. *Successful heartbeats are deliberately silent in the audit table* (8C audit-as-security-artifact design), so the 200 in this file *is* the evidence. |
| 03a | `03a-attack-register-pi99.txt` | **Vector A** — register fabricated `pi-99` → **403** `Cannot register a node on behalf of another identity` (**identity layer**, audited). |
| 03b | `03b-attack-impersonate-pi01.txt` | **Vector B** — heartbeat impersonating pi-01 → **403** `Cannot heartbeat on behalf of another node` (**authorization / CN-mismatch**, audited). |
| 03c | `03c-attack-scrape-pi01-metrics.txt` | **Vector C** — scrape pi-01's `:9100` with pi-03's cert → **403** + pi-01's agent logs `metrics_scrape_rejected peer_cn=pi-03.thesis.local` (**CN allowlist at the node** — distributed enforcement, not in controller audit). |
| 04 | `04-audit-snapshot-pi03.txt` | Controller audit for `actor_cn=pi-03`: two `auth.failure` rows (A + B) with distinct per-layer reasons. Vector C lives at pi-01; control vector success is silent by design. |
| 05 | `05-revoke-command.txt` | Operator revokes pi-03 via admin-provisioner revoke token (proven Pi-02 recipe). |
| 06 | `06-post-revoke-heartbeat.txt` | ~75 s later: **same control-vector heartbeat** that was `200` pre-revoke is now **403 "Client certificate has been revoked"** — **uniform reason** regardless of vector. Audit row reflects it. |
| 07 | `07-agent-retired.txt` | `thesis-node-agent.service` + `thesis-cert-renew.timer` stopped + **disabled**. Host left up for forensics. |
| 08 | `08-final-state.txt` | DB row retained (history); `last_heartbeat_at` frozen at last legitimate heartbeat before retirement; Prometheus target `down` (retirement signal); old serial in CRL. |

## Four evidence channels, one consistent claim

The evidence is *intentionally* distributed across multiple channels, each
corroborating the same precise-scoping claim:

1. **HTTP response codes** at the attacker — 200 for in-scope (vector control), 403 for each out-of-scope vector.
2. **Controller audit table** — `auth.failure` rows with **distinct** per-layer reasons for A and B (and a single uniform `certificate revoked` row post-revoke).
3. **Node agent journal** (pi-01) — `metrics_scrape_rejected` for vector C (defense enforced *at the node*).
4. **CRL state** — revoked serial present after step 05; old identity void.

That multi-channel redundancy is itself a Zero-Trust property: defense in depth,
no single point of enforcement, no single point of evidence.

## Progression

```
scoped-authz       (diverse per-layer rejections; cert still valid)
   ↓
detection          (audit trail is the signal — honest for the lab;
                    automated anomaly alerting → Гл.6 future work)
   ↓
revocation         (cert void; uniform "certificate revoked" reason)
   ↓
retirement         (agent stopped + disabled; identity out of service)
```

The pre-vs-post-revocation **reason diversity** matters: pre-revoke shows the
scoped authorization layers each catching the right thing; post-revoke shows
revocation as a *separate* mechanism that supersedes scope checks (the revoked
cert never even reaches the authz logic — `require_live_identity` rejects first).
Two distinct mechanisms, cleanly sequenced.

## Distinction from Сценарий 2 (Pi-02)

- **Pi-02:** revoke → **recover** (operational control; identity restored via
  re-enrollment under the **same** node_id).
- **Pi-03:** compromise → **retire** (incident response; identity *void*; if the
  workload is still needed, a fresh node_id is provisioned). A compromised
  identity is not "un-compromised."

This is also why Pi-03 ends with the agent **stopped** while Pi-02's stays running:
Pi-02 was revoked-then-recovered (agent kept running between); Pi-03 is retired
(agent off, `last_heartbeat_at` frozen at retirement, Prometheus target down).
The retired state is self-evident, not noisy 403-loop telemetry.

## Precise least-privilege, not blanket-blocking

The control vector (200) is essential to the claim. Without it, the three
rejections could be read as "the system blocks everything from pi-03 after
flagging it." With it, the evidence reads correctly: **the same identity** can
do *exactly* its authorized work, and **only** that. Zero Trust scoping, not
paranoid denial.
