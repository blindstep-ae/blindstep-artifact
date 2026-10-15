# Infrastructure resources

## What the artifact needs

| Resource | Requirement | Why |
|---|---|---|
| Node | 1 × x86-64 Linux node (bare-metal or VM) | both MPC parties run on the same host over loopback |
| CPU | 4 vCPU (more only shortens wall-clock) | MP-SPDZ compilation and two party processes |
| RAM | 16 GB, all stages including N=8192 | the N=8192 compile peaks at 30–63 MB RSS; disk, not RAM, holds the bytecode |
| Disk | 20 GB free | MP-SPDZ build (~5 GB) + compiled bytecode for all N |
| OS | Ubuntu 22.04 LTS and 24.04 LTS (both tested); other recent Linux should work | MP-SPDZ toolchain |
| Root | required only for the WAN stages | `tc netem` on the loopback interface |
| Network | none beyond localhost | no downloads at run time after install |
| GPU | none | — |

## Recommended public infrastructure

**CloudLab** (https://www.cloudlab.us/): any general-purpose bare-metal
node type with Ubuntu 22.04 — e.g. a single `c6525-25g`, `xl170`, or `m510`
node — provides root and comfortably exceeds the 4 vCPU / 16 GB need. Chameleon
(https://chameleoncloud.org/) bare-metal `compute_cascadelake` or similar
instances are equivalent.

Requesting one node for the one-day evaluation path is sufficient; the
optional full WAN rerun (~30 h) needs the same node for longer.

## Time budget

| Path | Wall-clock | Notes |
|---|---|---|
| Install (`scripts/install.sh`) | ~20–40 min | MP-SPDZ build dominates |
| Kick-the-tires | ~5 min | no MP-SPDZ needed |
| Functional verification | ~1 h | `verify_functional.sh` |
| LAN reproduction | 2–4 h | unattended; resumable |
| Scaled-down WAN (`rtt`) | ~2 h | root; resumable |
| Full WAN (optional) | ~30 h | root; resumable at trial granularity; sudo may re-prompt |

## Testing status

The artifact was developed and verified on a private Ubuntu 22.04 server
meeting the requirements above. It has not yet been exercised on CloudLab or
Chameleon; the requirements are standard and no site-specific configuration
is needed.
