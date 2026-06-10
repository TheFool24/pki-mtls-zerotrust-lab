# Step 13 — Сценарий 6 evidence: network segmentation + air-gap activation

**Captured:** 2026-06-02, 14:37–15:00 UTC
**Router:** thesis-router (MikroTik RouterOS 7.19.6, model C53UiG+5HPaxD2HPaxD, S/N HM50B420CZY)
**Captured from:** Windows PC (VLAN 10 mgmt) via SSH to router and ProxyJump to Pi-01

This evidence directory captures Сценарий 6 in full — the segmentation topology AND the live transition from "air-gap-capable" to "air-gap-active". Both states are preserved as artifacts so the chapter can cite the change as observed, not pending.

## Files

| # | File | What it shows | State |
|---|------|---------------|-------|
| 01 | `firewall-filter-export.rsc` | Full `/ip firewall filter export` (RouterOS script). Doubles as Приложение Г deliverable. | **Before** — 35 rules, provisioning rule active |
| 02 | `firewall-filter-print.txt` | Numbered `/ip firewall filter print`, 35 rules (indices 0–34). | **Before** |
| 03 | `mgmt-to-node-direct-blocked.txt` | `ssh -o ConnectTimeout=5 jojo@10.50.30.11` from Windows → Connection timed out. Direct mgmt→node forwarding has no allow rule; falls through to default-deny. | Invariant (both states) |
| 04 | `mgmt-to-node-via-proxyjump.txt` | `ssh -J jojo@10.50.20.200 jojo@10.50.30.11 "curl ports.ubuntu.com"` → HTTP 200 with directory listing. ProxyJump works; Pi has WAN. | **Before** |
| 05 | `rule-23-removed-filter-print.txt` | `/ip firewall filter print` after removing the provisioning rule. 34 rules (indices 0–33). Forward-chain rules shift down by one; DROP-NODES-WAN is now at index 23 and is first-match for vlan30-nodes → ether1. | **After** |
| 06 | `node-to-wan-blocked.txt` | Same curl command as file 04, run after rule removal → `curl: (28) Connection timed out after 8002 milliseconds`. Single firewall rule change is the only variable. | **After** |
| 07 | `drop-nodes-wan-log.txt` | Router `/log print where message~"DROP-NODES-WAN"` showing 8 SYN drops over 14:59:27–14:59:34 UTC, source `10.50.30.11` MAC `d8:3a:dd:21:5d:09`, destinations `104.20.28.246`/`172.66.152.176` (Cloudflare-fronted ports.ubuntu.com). | **After** |

## Topology and what each artifact proves

### Segmentation: default-deny between mgmt and nodes (files 02, 03)

The forward chain has **no allow rule** for `vlan10-mgmt → vlan30-nodes` and **no allow rule** for `vlan30-nodes → vlan10-mgmt`. Traffic between mgmt and nodes — in either direction — falls through to the terminal `Drop all other forward` rule (post-removal index 33, log-prefix `DROP-FORWARD`).

File 03 demonstrates this directly: `ssh jojo@10.50.30.11` from Windows times out. Pi-01's SSH daemon is up (proven by the ProxyJump test in file 04 succeeding through controller), so the timeout is firewall-side, not Pi-side. The implicit deny is real.

### Sanctioned mgmt → node path: ProxyJump through controller (file 04, top half)

- Rule 24 (post-removal): mgmt → controller SSH (port 22) — accept
- Rule 31 (post-removal): controller → node SSH (port 22) — accept
- Net effect: `ssh -J controller node` works; `ssh node` directly does not.

### Air-gap mechanism for VLAN 30 nodes (files 04, 05, 06, 07)

**Before the change** (file 04): the provisioning rule (formerly index 23, comment `PROVISIONING: VLAN 30 to WAN - REMOVE BEFORE DEPLOYMENT`) accepted `vlan30-nodes → ether1` traffic. Because MikroTik filter is first-match-wins, this ACCEPT preceded and neutralized the DROP-NODES-WAN rule below it. Pi-01's curl to ports.ubuntu.com returned HTTP 200.

**The change** (one command):
```
/ip firewall filter remove [find comment="PROVISIONING: VLAN 30 to WAN - REMOVE BEFORE DEPLOYMENT"]
```

**After the change**:
- File 05: rule count drops to 34; DROP-NODES-WAN renumbers to index 23 and is now the first matching forward rule for node → WAN traffic.
- File 06: same curl from Pi-01 → exit 28, 0 bytes received, 8-second timeout.
- File 07: router log shows the actual drop events — 8 SYN packets dropped over 14:59:27–14:59:34, matching curl's `-m8` window. Source MAC `d8:3a:dd:21:5d:09` ties the drops to Pi-01 specifically.

The before/after pair is the strongest possible evidence: same command, same Pi, same destination, single rule change between runs, opposite outcomes — both captured.

## Honest scope of ИС-6 (air-gap)

The air-gap property applies to **VLAN 30 (nodes)** — the segment holding cryptographic identities and serving the heartbeat/metrics path. It does **not** claim air-gap for the controller (VLAN 20), which retains curated WAN access (rule 22, post-removal index 22, `Allow controller to internet (dev mode)`) for image pulls and package updates. This scoping is deliberate: nodes are the security boundary; the controller is a managed admin host with its own posture. Should a reviewer ask "but the controller can reach the internet" — yes, by design, and it is documented as such.

A residual WAN reach from the controller (`curl https://...`) is acceptable within this model because (a) the controller does not hold node private keys, (b) the controller's CA trust store is independent of WAN reachability, and (c) the agents on the nodes only talk back to the controller's internal mTLS endpoint (rule 29, controller-side address). Compromising the controller's WAN egress does not put nodes' identities at risk.

## Defense-day implications

The pre-defense checklist (`docs/PRE-DEFENSE-CHECKLIST.md`) section A previously listed the provisioning-rule removal as a TODO. With the removal now executed and captured, that item is done — air-gap is the steady state for VLAN 30 going forward.

**Caveat for Сценарий 5 (Pi-04 live onboarding):** the Ansible playbook that onboarded Pi-01/02/03 needed WAN for `pip install` of node-agent dependencies. With the provisioning rule gone, Pi-04 onboarding will require one of:
- Pre-staging Pi-04's base + venv before defense (during a brief temporary re-allow), then only cert enrollment + registration happen live, OR
- Offline wheel cache (controller serves wheels to nodes via `pip --no-index --find-links`), OR
- Brief temporary re-add of the provisioning rule during the Pi-04 onboarding step at defense.

This is a Сц. 5 design call, not a Сц. 6 evidence issue.

## Cross-references

- Pre-defense checklist: [docs/PRE-DEFENSE-CHECKLIST.md](../../PRE-DEFENSE-CHECKLIST.md) — section A, rule-23 item.
- Setup note: [docs/setup-notes/08-step-8-node-fleet.md](../../setup-notes/08-step-8-node-fleet.md) — mentions VLAN10→VLAN30 denial and ProxyJump pattern; predates this air-gap activation.
- Гл. 2 ИС-2: rule-count claim must be corrected (was "31", actual was 35 before air-gap activation, **34 after**).
- Гл. 5.7 (Сценарий 6): primary citation source for all artifacts above.
