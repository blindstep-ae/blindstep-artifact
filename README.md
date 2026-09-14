# BlindStep — Artifact

Artifact for **"BlindStep: A Secure One-Step Kernel for Privacy-Preserving
Collaborative Reasoning"** (ACSAC 2026).

Badges requested: Artifacts Available · Artifacts Functional · Results Reproduced.

The artifact contains the six MP-SPDZ realizations of BlindStep's fixed-shape
MPC-online kernel (hybrid and all-Boolean sharing styles × Queue / Select /
Sort Top-K strategies), the VolePSI-based CPSI frontend patch that generates
the bounded-slot secret shares the kernel consumes, a Python simulator that
reproduces the frontend's share-file format byte-for-byte, and self-checking
drivers that verify functionality and re-measure the paper's cost tables with
an automated comparison against the published numbers.

## Layout

```
mpc/                      MPC programs (six variants + module tests) and
                          shared Python modules (bs_core.py, module1_backend.py)
scripts/                  drivers, checkers, oracles, simulator (see below)
patches/volepsi_blindstep_frontend_ec76012.patch
                          frontend patch vs. upstream VolePSI commit ec76012
external_backend/         build notes for the VolePSI frontend
data/paper_published_numbers.json
                          machine-readable published table values (diff baseline)
docs/protocol_notes/      frozen protocol design documents
docs/share_file_contract.md
                          the share-file format both writer and kernel obey
docs/artifact/REGISTRATION_ABSTRACT.md
                          AE registration abstract, claims C1–C5, checklists
results/camera_ready_rerun/
                          expected results: measurement CSVs + analysis
results/functional_verify/SUMMARY.txt
                          reference output of the functional verification
MANIFEST.sha256           (package only) SHA-256 of every file
```

Paper-name ↔ program mapping used throughout:

| Paper | Program (`mpc/`) | Driver slug |
|---|---|---|
| H-Queue | `blindstep_full` | `hybrid_queue` |
| H-Select | `baseline_hybrid_partial_select` | `hybrid_partial_select` |
| H-Sort | `baseline_hybrid_batcher_sort` | `hybrid_batcher_sort` |
| B-Queue | `blindstep_full_ab_queue` | `ab_queue` |
| B-Select | `blindstep_full_ab_partial_select` | `ab_partial_select` |
| B-Sort | `baseline_ab_batcher_sort` | `ab_batcher_sort` |

## Requirements

- x86-64 Linux; ~8 cores, 32 GB RAM (MP-SPDZ compilation at N=8192 is the
  peak), 20 GB free disk.
- [MP-SPDZ](https://github.com/data61/MP-SPDZ) at commit `58d2739ac251262c0bd6034f7fc7d0666a6b1e2c`
  (`v0.4.2-13-g58d2739a`, 13 commits after the v0.4.2 release), built with the **semi2k**
  protocol (`semi2k-party.x`). This is the exact build behind the shipped
  expected results; `scripts/install.sh` checks out this commit. All scripts
  locate it via the `MPSPDZ_DIR` environment variable and set
  `LD_LIBRARY_PATH` themselves.
- Python ≥ 3.8 (standard library only).
- Optional (density sweep, Table 14, and the real-frontend path): CMake ≥ 3.15
  (Ubuntu 22.04's apt package, 3.22, suffices) to build VolePSI/libOTe. Every other experiment uses the simulator, whose
  output is byte-aligned with the frontend (machine-checked, see below).
- WAN stages only: root, for `tc netem` on the loopback interface. The driver
  injects and removes it itself, including on interruption.

No GPUs, no proprietary data, and no external network access at experiment
run time (both parties talk over loopback). Installation needs network access
for apt packages and the MP-SPDZ / VolePSI sources unless pre-provisioned.

## Setup

Scripted (Ubuntu 22.04; installs apt packages, clones and builds MP-SPDZ with
semi2k into `$MPSPDZ_DIR`, copies the MPC sources, runs a smoke check):

```bash
bash scripts/install.sh                     # ~20–40 min, mostly the MP-SPDZ build
export MPSPDZ_DIR=$HOME/MP-SPDZ             # or wherever install.sh put it
```

The drivers derive everything else from `MPSPDZ_DIR`. If you run MP-SPDZ or
the frontend by hand, also export:

```bash
export LD_LIBRARY_PATH="$MPSPDZ_DIR:$MPSPDZ_DIR/local/lib:${LD_LIBRARY_PATH:-}"
export BLINDSTEP_DATA_DIR="$MPSPDZ_DIR/Player-Data"   # where the frontend writes share files
```

`WITH_VOLEPSI=1 bash scripts/install.sh` additionally builds the CPSI
frontend (only needed for Table 14). If you already have MP-SPDZ, just export
`MPSPDZ_DIR` and copy `mpc/*` into `$MPSPDZ_DIR/Programs/Source/`.

Manual frontend build, if preferred (only needed for Table 14):

```bash
git clone https://github.com/Visa-Research/volepsi external_backend/volepsi
git -C external_backend/volepsi checkout ec76012
git -C external_backend/volepsi apply "$(pwd)/patches/volepsi_blindstep_frontend_ec76012.patch"
# then build per external_backend/README_linux_build.md
```

## Kick-the-tires (≈5 minutes, no MP-SPDZ needed)

```bash
python3 scripts/verify_key_encoding.py --quick     # F.3 injectivity, reduced
python3 scripts/check_share_alignment.py           # writer/kernel share-format alignment
```

Expected: both end with an `OK`/`INJECTIVE` conclusion and exit code 0.
The full F.3 check (`python3 scripts/verify_key_encoding.py`, ~10 min) runs
33,554,432 exhaustive cases plus 10^6 random trials per production width.

## Functional verification (≈1 hour, needs MP-SPDZ)

```bash
bash scripts/verify_functional.sh
```

One command; it compiles all 13 programs, runs the kernel on generated share
files, and checks:

- S1 compile smoke for every program;
- S2 Top-K output `(rank, valid, score)` on a fixed share file;
- S3 fail-closed overflow injection — expected: a
  `[FATAL] Global overflow triggered` abort and **zero** `TOPK_CSV` lines;
- S4 bounded one-to-many aggregation — expected rows `CSV,3,1,321`,
  `CSV,6,1,657`, `CSV,9,1,139` (Table 9's two-/three-/one-hit cases);
- S5 a cost snapshot.

Expected final line: `ALL CHECKS PASSED`. A reference transcript is in
`results/functional_verify/SUMMARY.txt`. Logs land in
`results/functional_verify/`.

## Reproducing the paper's results

### Recommended one-day path

```bash
bash scripts/rerun_camera_ready.sh                 # LAN: stages t4 t5 t8 t13 (2–4 h)
bash scripts/rerun_camera_ready.sh rtt             # scaled-down WAN (~2 h, needs sudo)
python3 scripts/compare_camera_ready.py            # diff vs. published numbers
```

All stages are resumable: re-running the same command skips completed
trials/stages. The comparison writes
`results/camera_ready_rerun/camera_ready_diff.md` — every cell as
`published → reproduced` with deltas.

**Why the scaled-down WAN experiment suffices.** The paper's WAN claim (C5)
is that under high RTT runtime is dominated by round count, so the
lowest-round variant (H-Sort) overtakes the lowest-communication variant
(B-Queue) even though it sends ~100× more data. The `rtt` stage runs exactly
these two variants at 25 ms and 50 ms RTT (3 trials each, ~2 h); observing
H-Sort faster than B-Queue at both RTTs, with unchanged rounds/communication,
demonstrates the high-RTT ordering. Combined with the LAN result from the
preceding stages — where B-Queue is faster than H-Sort — this establishes the
reported crossover and supports the round-dominance explanation, without the
~30 h full sweep. The full sweep only adds the remaining variants and the
N=2048 point of the same trend.

### Full path (optional, ~30 h)

```bash
bash scripts/rerun_camera_ready.sh wan6 wan2048    # full WAN tables (needs sudo)
python3 scripts/compare_camera_ready.py
```

### What should match, and how closely

- **Exact (hardware-independent):** communication (MB) and compile-time
  preprocessing estimates (Table 8) must equal the values in the shipped
  expected-results CSVs (`results/camera_ready_rerun/t*.csv`), and must be
  identical across match densities (Table 14, optional stage).
- **Deterministic at the protocol level, with small runtime variation:**
  round counts. MP-SPDZ's VM reports rounds as executed, and its runtime
  batching can shift the reported figure by a few rounds between runs (the
  published tables themselves show this, e.g. 24,466 vs 24,475 P3 rounds).
  Expect the shipped values ± a few rounds; a difference of tens or more is
  a real discrepancy.
- **Environment-dependent:** wall-clock timings. The reproduction target is
  the paper's relative trends: variant ordering under LAN (Tables 4, 5, 12),
  WAN round-dominance and the fastest-variant crossover from B-Queue to
  H-Sort (Tables 6, 15, 16), and the M_max / RTT / density trends (Tables 13,
  14, 15). Absolute seconds vary with host and load;
  `results/camera_ready_rerun/NOTES.md` documents this and the measured
  v2 overhead (<1% rounds/communication).

## Claim → component → table mapping

| Claim | What it states | Verified by | Paper tables |
|---|---|---|---|
| C1 | bounded one-to-many aggregation correct; cross-variant Top-K agreement | `verify_functional.sh` S2+S4; oracles `scripts/oracle_*.py` | Table 9 |
| C2 | fail-closed overflow: global overflow indicator revealed, no retained Top-K entries released | `verify_functional.sh` S3 | §F.2 |
| C3 | packed ranking-value injectivity | `scripts/verify_key_encoding.py` | §F.3 |
| C4 | fixed-shape deterministic cost, density-invariant | `rerun_camera_ready.sh` t4 t5 t8 t13 (+ optional `t14`, needs the frontend) + `compare_camera_ready.py` | 4, 5, 8, 13; 12 = the N=8192 point of t5; 14 = optional t14 |
| C5 | relative performance: LAN ordering; WAN round-dominance & crossover | `rerun_camera_ready.sh` (LAN stages; `rtt` scaled / `wan6 wan2048` full) | 4, 5, 6, 15, 16; 12 = N=8192 point of t5 |

## Troubleshooting

- **`MPSPDZ_DIR: Set MPSPDZ_DIR ...`** — export the variable; every script
  requires it explicitly (no hardcoded paths anywhere in the artifact).
- **`libboost... / libSPDZ.so cannot open shared object`** — you invoked
  MP-SPDZ outside the drivers; they set
  `LD_LIBRARY_PATH=$MPSPDZ_DIR:$MPSPDZ_DIR/local/lib` themselves. For manual
  runs export the three variables listed under Setup.
- **`ModuleNotFoundError: bs_core` / `module1_backend` at compile time** — the
  drivers set `PYTHONPATH=$MPSPDZ_DIR/Programs/Source` for `compile.py`; if you
  compile by hand, do the same (MP-SPDZ does not add that directory itself).
- **Stale Python module shadowing** — if your MP-SPDZ tree carries old copies
  of `bs_core.py`/`module1_backend.py` (e.g. in `Compiler/`), the drivers
  detect and re-sync them automatically (reported as "shadow module copies
  detected").
- **Long WAN runs pause at a sudo prompt** — the netem teardown re-prompts
  after sudo's timestamp expires; run inside `tmux`/`screen` and answer, or
  pre-authorize `tc` via sudoers.
- **Interrupted stage** — re-run the same command; completed trials are
  recovered from their logs, only unfinished ones re-execute.

## Public release, access, and external components

- **Public release:** the entire artifact as evaluated is released publicly
  under the MIT license (see `LICENSE`) and will be archived with a DOI
  (Zenodo) by the camera-ready deadline. No part is withheld.
- **Special access:** none. No live services, private cloud, or restricted
  hardware; everything runs on a single Linux node.
- **External components (not bundled, fetched by `scripts/install.sh`):**
  MP-SPDZ (https://github.com/data61/MP-SPDZ, semi2k) and, optionally,
  VolePSI at upstream commit `ec76012`
  (https://github.com/Visa-Research/volepsi) plus the patch in `patches/`.
  No datasets: all inputs are generated (simulator or frontend).
- **Testing status:** developed and verified on a private Ubuntu 22.04 server;
  CloudLab / Chameleon bare-metal Ubuntu 22.04 nodes meet the requirements
  (`docs/artifact/INFRASTRUCTURE.md`).
- **No tracking:** the artifact contains no analytics, telemetry, or network
  calls beyond the installer's package/source downloads.

## Provenance and integrity

`MANIFEST.sha256` (in the packaged artifact) lists the SHA-256 of every file.
The expected-results CSVs carry the git revision and UTC timestamp of the
runs that produced them.
