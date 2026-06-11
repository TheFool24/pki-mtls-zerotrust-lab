# Step 14 — L2 isolation between Pi nodes (Cisco switchport protected)

**Captured:** 2026-06-11
**Hardware:** Cisco Catalyst 3560, IOS 12.2 (thesis-switch, mgmt SVI 10.50.10.2)
**Triggered by:** Review of Гл. 2.3 / Таблица 2.3 / Раздел 2.3.3 — the documented
"VLAN 30 → VLAN 30: DENY" claim is enforced at the MikroTik forward chain, but
intra-VLAN frames between Pi nodes never reach the MikroTik (they switch at L2
inside the Cisco). Gap discovered during chapter review; fix shipped before
defense.

## Files

| # | File | What it shows | State |
|---|------|---------------|-------|
| 01 | `01-baseline-l2-gap.txt` | Six tests from each Pi via SSH from master-lab: Pi↔Pi pings (intra-VLAN), Pi→gateway, Pi→controller ICMP, Pi→controller mTLS heartbeat, controller DB heartbeat ages. Pre-fix state. | **Before** |
| 02 | `02-switchport-protected-applied.txt` | Cisco config commands + per-port verification (`show interfaces fa0/X switchport \| include Protected` → `Protected: true` on all four Pi access ports). | **Change** |
| 03 | `03-after-pings.txt` | Same six tests as `01`, post-fix. Documents that intra-VLAN is blocked while trunk/application paths are unaffected. | **After** |
| 04 | `04-post-fix-running-config.txt` | Full `show running-config` after the change. Feeds Приложение Б re-extract. | **After** |

## Before / after results

| Test | Pre-fix | Post-fix | Verdict |
|------|---------|----------|---------|
| Pi-01 → Pi-02 (intra-VLAN) | 0% loss | **100% loss** | Gap CLOSED at L2 |
| Pi-02 → Pi-01 (intra-VLAN reverse) | 0% loss | **100% loss** | Symmetric block confirmed |
| Pi-01 → Pi-03 retired (intra-VLAN) | 0% loss | **100% loss** | Even retired host unreachable |
| Pi-01 → 10.50.30.1 gateway (trunk path) | 0% loss | **0% loss** | Trunk port Fa0/8 unaffected ✓ |
| Pi-01 → controller ICMP | 100% loss | 100% loss | Unchanged (MikroTik already enforces) |
| Pi-01 → controller mTLS heartbeat | HTTP 200 | **HTTP 200** | Application path unaffected ✓ |
| Pi-01 last_heartbeat age in controller DB | 2s | **33s** | Continuous heartbeating throughout |
| Pi-02 last_heartbeat age in controller DB | 29s | **29s** | Continuous heartbeating throughout |

## Why the fix works

`switchport protected` (Cisco PVLAN edge) is a local-port rule that prevents L2
forwarding **between protected ports**, while allowing forwarding to/from
non-protected ports freely. Applied to Fa0/2-5 (Pi access ports), it blocks
Pi↔Pi without touching the trunk port Fa0/8, which is the path for:

1. Pi → MikroTik (gateway 10.50.30.1) — routed traffic via trunk
2. controller → Pi (Prometheus scrape, SSH) — routed via MikroTik via trunk
3. Pi heartbeat HTTPS POST → controller — routed via MikroTik via trunk

All three flows traverse Fa0/8, which is not protected → they continue to work.
Only direct Pi↔Pi L2 frames are dropped.

## Honest scope: bonus Zero Trust observation

The baseline (file 01) also documents that Pi → controller **ICMP** is 100% lost.
This is not a new observation from this fix — it is the **MikroTik forward chain
already enforcing** that VLAN 30 → VLAN 20 only permits TCP 443 (mTLS) and TCP
9000 (step-ca enrollment); everything else (including ICMP) falls through to
rule 33 `DROP-FORWARD` default-deny. Worth noting in the thesis chapter: this
is a stronger Zero Trust posture than "VLAN segmentation" implies — not just
"some traffic allowed", but "only the specific service ports needed cross the
VLAN boundary".

## What this affects in the thesis

Updates needed in Гл. 2.3.3, Таблица 2.3, Раздел 3.2.2, and Приложение Б
(re-extract Cisco running-config). The "VLAN 30 → VLAN 30: DENY" claim becomes
truthful: at L2 via switchport protected, AND at L3 via the MikroTik default-deny
forward chain (which never sees the intra-VLAN traffic anyway, but now also has
nothing to block because Cisco does it first).

Historical scenario evidence (Сц. 1-4 in `docs/evidence/step-9c..12`) was captured
when the gap existed. None of those scenarios depend on Pi↔Pi isolation
specifically — they validate controller-side authorization (Сц. 1 mTLS, Сц. 2
revocation, Сц. 3 compromise rejected at API/identity layer, Сц. 4 lateral
movement rejected at controller authorization). So Сц. 1-4 findings are
unchanged; the L2 fix complements them rather than contradicting.

## Cross-references

- Related: Сц. 6 (MikroTik air-gap activation, `docs/evidence/step-13/`) — same
  empirical-engineering pattern: gap found via review, fix shipped, before/after
  captured.
