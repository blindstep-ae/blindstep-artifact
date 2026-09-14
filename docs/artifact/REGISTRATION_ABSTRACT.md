# ACSAC Artifact Evaluation — Registration Abstract

Paper: **BlindStep: A Secure One-Step Kernel for Privacy-Preserving
Collaborative Reasoning** (ACSAC 2026, accepted)

Badges requested: Artifacts Available · Artifacts Functional · Results Reproduced
<!-- adjust to the exact badge names on this year's form -->

---

## Artifact abstract (paste into the form)

This artifact provides the implementation and measurement pipeline used for
BlindStep's evaluation. It includes six MP-SPDZ realizations of the
fixed-shape MPC-online kernel, spanning hybrid and all-Boolean sharing styles
and Queue, Select, and Sort Top-K strategies. It also includes the
VolePSI-based CPSI frontend that generates the bounded-slot secret shares
consumed by the kernel, together with a Python simulator that reproduces the
frontend's share-file format byte-for-byte; their alignment is
machine-checked.

The artifact provides self-checking scripts for both functionality and
performance reproduction. The functionality checks compile and exercise all
protocol variants, validate bounded one-to-many aggregation and fail-closed
overflow handling, and verify the injectivity of the packed ranking
representation. The measurement pipeline reruns the paper's LAN, WAN, and
parameter-sweep experiments in resumable stages and automatically compares
reproduced results against the published data.

Reproducibility targets are layered. Communication volumes and
compile-time preprocessing estimates reproduce exactly and are independent
of hardware load; round counts are deterministic at the protocol level, up to
the small runtime batching variation introduced by MP-SPDZ. Runtime measurements
are environment-dependent; for these, the artifact targets the paper's
relative performance trends across protocol variants, network conditions,
\(M_{\max}\), and RTT.

Artifact type and scope: source code, driver scripts, and measurement data
with expected results; submitted as source code (no proprietary components).
It supports the paper's experimental evaluation: the correctness and
security-behavior checks and the LAN, WAN, and parameter-sweep cost tables of
Section 6 and the appendices. We request the Available, Functional, and
Reproduced badges.

Requirements and effort: an x86-64 Linux host with about 8 cores, 32 GB RAM,
and 20 GB disk; MP-SPDZ (semi2k protocol) and Python 3.8+; optionally a CMake
toolchain to build the bundled VolePSI frontend (a byte-aligned simulator
covers all other experiments). WAN experiments emulate latency via tc netem
on the loopback interface and therefore require root; no GPUs, proprietary
data, or other special hardware or access restrictions apply. Any bare-metal
or VM instance with root suffices; among public research infrastructures we
recommend CloudLab or Chameleon. The recommended one-day evaluation path —
functional verification (about 1 hour), full LAN reproduction (2–4 hours,
unattended), and a scaled-down WAN reproduction via the RTT sweep (about
2 hours) — exercises every claim; a full WAN rerun (about 30 hours, in
resumable stages) is optional and reproduces the remaining WAN tables in
full.

## Claims supported

- C1 Correctness: bounded one-to-many aggregation over injected multi-hit
  rows (Table 9; expected values A[3]=321, A[6]=657, A[9]=139);
  cross-variant Top-K agreement on identical share files.
- C2 Fail-closed overflow handling with a single-bit global reveal (§F.2).
- C3 Injectivity of the packed (valid, score, tie) encoding (§F.3;
  33,554,432 exhaustive cases plus 10^6 random trials per production
  width — this check runs on any machine, no MP-SPDZ needed).
- C4 Fixed-shape cost: communication and compile-time preprocessing
  estimates reproduce exactly, round counts up to small runtime batching
  variation, per compiled program and public parameters (Tables 4, 6, 8, 12,
  13, 15, 16); independent of match density (Table 14, optional stage).
- C5 Relative performance: LAN variant ordering and scaling (Tables 4, 5, 12),
  WAN round-dominance and fastest-variant crossover (Tables 6, 15, 16).

## Hardware / software requirements

- x86-64 Linux server; ≥8 cores and ≥32 GB RAM recommended (MP-SPDZ
  compilation at N=8192 is the memory peak); ~20 GB free disk (compiled
  bytecode for large N).
- MP-SPDZ at commit `58d2739a` (`v0.4.2-13-g58d2739a`) with the semi2k protocol built
  (`semi2k-party.x`); the artifact addresses it via the `MPSPDZ_DIR`
  environment variable and `scripts/install.sh` checks out this commit.
- Python ≥ 3.8 (standard library only).
- Optional, for the density sweep (Table 14) and the real-frontend path:
  CMake ≥ 3.15 toolchain (Ubuntu 22.04's apt cmake 3.22 suffices) to build the bundled VolePSI/libOTe; every other
  experiment uses the byte-aligned Python simulator.
- WAN stages only: root access for `tc netem` on the loopback interface
  (injected and removed by the driver itself).

## Estimated effort (two-tier)

**Recommended one-day AE path** (exercises claims C1–C5):

- Functional verification (`verify_functional.sh` + F.3 check): ~1 hour.
- LAN reproduction (`rerun_camera_ready.sh`, stages t4 t5 t8 t13):
  2–4 hours unattended → C4 deterministic columns + LAN trends (C5).
  Optional `t14` (Table 14 density sweep) needs the VolePSI frontend
  (`WITH_VOLEPSI=1 scripts/install.sh`); its expected results ship in the package.
- Scaled-down WAN: `rerun_camera_ready.sh rtt` (~2 hours) → B-Queue vs H-Sort
  at 25/50 ms RTT demonstrates WAN round-dominance and the fastest-variant
  crossover (C5) without the full sweep.

**Full reproduction path** (optional): `rerun_camera_ready.sh wan6 wan2048`
(~30 hours, round-dominated; all stages resume at trial
granularity after interruption) → complete WAN tables (6, 15-100ms rows, 16).

## Security, privacy, and ethical concerns

All inputs are synthetic or public benchmark data; no PII. The only
privileged operation is optional `tc netem` on `lo` for WAN emulation; the
driver installs it with sudo, verifies it, and removes it on exit (including
on interruption). No other system state is modified outside the repository,
`$MPSPDZ_DIR/Programs`, and `$MPSPDZ_DIR/Player-Data`.

## Availability

The submitted artifact is a curated package (56 files, ~100 KB source +
evidence tables) built by `scripts/package_artifact.sh` from an explicit
whitelist: the MPC programs, the two drivers plus checkers and oracles, the
byte-aligned share-file simulator, the VolePSI frontend patch (against
upstream commit `ec76012`), the frozen protocol notes and share-file
contract, and the verification evidence (measurement CSVs and analysis; a
SHA-256 manifest covers every file). Development history — paper drafts,
plotting one-offs, raw server logs — is deliberately excluded.
It will be archived with a DOI
<!-- TODO: mint Zenodo/figshare DOI before the Available badge deadline -->.
Public-release intent: the exact package evaluated by the AEC will be released
in full to a permanent repository before camera-ready (no reduced public
variant).

## Submission checklist (do not rely on memory)

**By Sep 14 (registration)** at https://artifacts.submit.acsac.org/:
- [ ] Create submission, enter accepted paper title.
- [ ] Badges: Available + Functional + Reproduced.
- [ ] Paste the abstract above (it already carries type/scope, requirements,
      public-infrastructure recommendation, runtime, and the netem/root note).
- [x] MP-SPDZ pinned: v0.4.2-13-g58d2739a / 58d2739ac251262c0bd6034f7fc7d0666a6b1e2c.

**By Sep 16 (full submission):**
- [ ] Accepted paper PDF.
- [ ] Artifact package / repository link + access instructions.
- [ ] AE-facing README: build / install / run / expected output, and the
      component → claim/table mapping (claims C1–C5 are the source material).
- [ ] Scaled-down (one-day) vs full reproduction paths documented.
- [ ] `metadata.toml` — generate with the artmeta tool
      (https://github.com/jelenamirkovic/artmeta), NOT hand-written.
- [ ] Public-release statement (which parts become public: all of it).
- [ ] **Mark the submission "ready for review"** — without this it is not
      considered submitted.

**Sep 17–23 (kick-the-tires):** at least one contact author responsive on
HotCRP throughout the evaluation period; v2 changes during AE are expected and
allowed.
