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

- x86-64 Linux; 4 vCPU and 16 GB RAM are enough for every stage, including the
  N=8192 compiles (an independent evaluation ran the full LAN set on that
  configuration; MP-SPDZ's compiler peaked at 30–63 MB RSS at N=8192). 20 GB
  free disk.
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

No GPU, no GUI, no paid APIs or API keys, no proprietary data or commercial
software; everything is MIT-licensed (`LICENSE`) or open source (MP-SPDZ,
VolePSI). No external network access at experiment run time (both parties
talk over loopback). Installation needs network access for apt packages and
the MP-SPDZ / VolePSI sources unless pre-provisioned.

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
bash scripts/rerun_camera_ready.sh                 # LAN: stages t4 t5 t8 t13 (≤4 h)
bash scripts/rerun_camera_ready.sh rtt             # scaled-down WAN (≤2 h, needs sudo)
python3 scripts/compare_camera_ready.py --baseline shipped   # must-match check
python3 scripts/compare_camera_ready.py                      # diff vs. published numbers
```

Reruns are written to `results/rerun/` (override with `RERUN_OUT=<dir>`); the
shipped expected results in `results/camera_ready_rerun/` are never modified,
so the baseline stays intact however often you re-run.

All stages are resumable: re-running the same command skips completed
trials/stages. A stage that recorded a failed compile or run is reported as
failed and left unstamped, so re-running retries it rather than skipping it.

`--baseline shipped` is the one-command form of the exactness claim below: it
prints PASS/MISMATCH per cell, writes `results/rerun/shipped_vs_rerun.md`, and
exits non-zero if any deterministic value disagrees. Without the flag the
comparison is against the accepted paper's numbers and writes
`results/rerun/camera_ready_diff.md` — every cell as `published → reproduced`
with deltas (these differ from the shipped CSVs by the <1% v2 cost).

Wall-clock figures in this section are upper bounds measured on the reference
server; an independent evaluation on 4 vCPU / 16 GB finished the LAN set and
the `rtt` stage several times faster. Treat them as a budget, not an estimate.

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
  identical across match densities (Table 14, optional stage). Check this in
  one command with `compare_camera_ready.py --baseline shipped`. For Table 8,
  `t8_preprocessing_raw.txt` is authoritative: the edaBits column of the
  shipped `t8_preprocessing.csv` reads `-` because of a parser bug in the
  driver (corrected; see the change log), and the comparison reads the raw log.
- **Deterministic at the protocol level, with small runtime variation:**
  round counts. MP-SPDZ's VM reports rounds as executed, and its runtime
  batching can shift the reported figure between runs (the published tables
  themselves show this, e.g. 24,466 vs 24,475 P3 rounds); the absolute drift
  grows with the round count, so the tolerance is relative: **±0.1% of the
  shipped value, with a floor of ±8 rounds** (±36 at N=256, ±8 on the small
  P1-only rows). `--baseline shipped` applies exactly this rule; anything
  outside it is a real discrepancy.
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

## Known limitations, nondeterminism, and reduced-scale alternatives

- **Timing is host-dependent.** Absolute wall-clock values are not a
  reproduction target (see "What should match"); the shipped LAN timings came
  from a lightly loaded server and may differ by a constant factor on yours.
  Relative trends across variants / N / RTT are the target.
- **LAN variant ordering at large N can depend on core count.** On a 4 vCPU
  host, B-Sort has been observed to fall behind H-Queue and H-Select at
  N=8192, while the shipped tables — measured on a many-core server — place it
  ahead. B-Queue remains the fastest variant under LAN in both settings, which
  is the comparison the reported LAN gaps rest on.
- **Round counts carry jitter** from MP-SPDZ's runtime batching, growing with
  the round count (tolerance ±0.1%, floor ±8; see "What should match");
  communication volumes and preprocessing counts are exact.
- **The nominal 25 ms RTT row of Table 15 is 24 ms effective.** The driver sets
  a one-way `netem` delay of RTT/2 in integer milliseconds, so 25 ms halves to
  12 ms per pass. The shipped data was measured this way and the driver reports
  the effective value; the round-dominance conclusion is unaffected by the 1 ms.
- **Tie tags are random by design** (`sint.get_random_int` per candidate) and
  are never revealed; Top-K order among exactly tied scores is therefore not
  reproducible run-to-run. The shipped test inputs have distinct scores, so
  the S2 agreement check is unaffected.
- **Table 14 (density sweep) needs the real VolePSI frontend** (optional
  `WITH_VOLEPSI=1` install); its expected results ship in
  `results/camera_ready_rerun/t14_density.csv` so the claim can be checked
  against data without the C++ build.
- **WAN experiments need root** for `tc netem`; a reviewer without root can
  still validate every claim except the WAN rows of C5 using the LAN stages.
- **Reduced-scale path:** the `rtt` stage (≤2 h) replaces the ≤30 h full WAN
  sweep; justification above. N=8192 can be skipped by running
  `rerun_camera_ready.sh t4 t8 t13` (≤1 h) if the N=8192 compile and run time is
  a problem; this drops only the N=8192 points of Tables 5 and 12.
- **Not yet exercised on CloudLab/Chameleon/SPHERE**; developed and verified on
  a private Ubuntu 22.04 server, and independently reproduced on a 4 vCPU /
  16 GB cloud VM running Ubuntu 24.04 with Python 3.12 (install, the functional
  checks, the LAN stages, and the scaled-down WAN stage).

## Change log

- v2.1 (2026-10-15): corrections from artifact evaluation. `rerun_camera_ready.sh`:
  a recorded COMPILE_FAIL/RUN_FAIL row now makes the stage fail and leaves it
  unstamped (a plain re-run retries it, and the stale row is replaced on
  success); reruns write to `results/rerun/` instead of the shipped
  expected-results directory, which the driver now refuses to write into; the
  Table 8 edaBits pattern matches MP-SPDZ's `N loose edabits of length 64`
  (the column previously read `-`); `wan_on` reports the effective RTT.
  `compare_camera_ready.py`: new `--baseline shipped` / `--rerun-dir` /
  `--shipped-dir`, making the README's exactness claim a single command with a
  non-zero exit on disagreement. README: corrected hardware requirements
  (4 vCPU / 16 GB verified), timings relabelled as upper bounds, relative round
  tolerance, and the 24 ms effective RTT disclosed; testing status now records
  independent reproduction on a 4 vCPU / 16 GB Ubuntu 24.04 cloud VM. No change
  to the MPC programs, the protocol, or the shipped measurement data.
- v2 (2026-10-06): documentation only — added this limitations section and the
  GUI/API/licensing statement in Requirements. No code, script, or data changes
  since the originally submitted version.

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
- **Testing status:** developed and verified on a private Ubuntu 22.04 server,
  and independently reproduced on a 4 vCPU / 16 GB cloud VM (Ubuntu 24.04,
  Python 3.12); CloudLab / Chameleon bare-metal Ubuntu 22.04 nodes meet the
  requirements (`docs/artifact/INFRASTRUCTURE.md`).
- **No tracking:** the artifact contains no analytics, telemetry, or network
  calls beyond the installer's package/source downloads.

## Provenance and integrity

`MANIFEST.sha256` (in the packaged artifact) lists the SHA-256 of every file.
The expected-results CSVs carry the git revision and UTC timestamp of the
runs that produced them.
