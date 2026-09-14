# Expected results — provenance and how to read them

The CSVs in this directory are the artifact's expected results: medians over
repeated trials produced by `scripts/rerun_camera_ready.sh` on the artifact's
own code (v2) with MP-SPDZ `58d2739a`, on a single Ubuntu 22.04 server.
`scripts/compare_camera_ready.py` diffs a fresh rerun against the numbers in
the accepted paper (`data/paper_published_numbers.json`) and writes
`camera_ready_diff.md`.

## Deterministic columns vs. the accepted paper

The accepted paper's tables were measured with an earlier revision of the
kernel. The artifact (v2) additionally enforces three properties the paper
states — a single-bit global overflow reveal (Definition 5.2), the A-side
validity conjunction (Definition 3.1), and a tie-tag-free Top-K output
(§6.1) — and consumes the frontend's share-file prefix in the Module 1 test
program. These are constant-shaped additions, so the deterministic columns
differ from the accepted paper by a small fixed amount:

| Quantity | v2 vs. accepted paper |
|---|---|
| rounds, hybrid variants | +160 (≈+0.5%) |
| rounds, all-Boolean variants | +16 (≈+0.05%) |
| communication, hybrid variants | +2.2–2.3 MB (≈+0.5%) |
| communication, all-Boolean variants | +0.8 MB (5–8% on a ~10 MB base) |
| integer triples (Table 8) | +830 (hybrid), +256 (all-Boolean) |
| Table 14 (density sweep) | re-measured; comm/rounds still identical across densities |

The camera-ready version of the paper carries the v2 values. A reproduction
should match the shipped CSVs: communication and preprocessing counts
exactly, rounds up to a few units of MP-SPDZ runtime batching variation.

## Timing columns

Wall-clock timings depend on the host and on co-tenant load. The server that
produced the accepted paper's timings was under heavier load than at the time
of the artifact runs; the shipped LAN timings are therefore 30–70% lower than
the paper's while the deterministic columns move by <1%. WAN timings are
round-dominated and reproduce the paper's within about 1%. The reproduction
targets for timing are the paper's relative trends (variant ordering, WAN
round-dominance and the B-Queue→H-Sort crossover, M_max and RTT trends), not
absolute seconds. Under a WAN emulation the totals should track round counts
closely; under LAN, expect host-dependent absolute values with the same
ordering.

## Files

| File | Content |
|---|---|
| `t4_main_table.csv` | N=256 LAN breakdown, 6 variants × 5 trials |
| `t5_nsweep.csv` | N ∈ {128, 512, 2048, 8192} × 6 variants × 5 trials |
| `t8_preprocessing.csv`, `t8_preprocessing_raw.txt` | compile-time preprocessing estimates |
| `t13_mmax.csv` | M_max ∈ {1,2,3,5,10}, H-Queue, 3 trials (+ module1 static rounds) |
| `t14_density.csv` | density ∈ {0,10,50,90}%, single runs (real frontend) |
| `t6_wan.csv` | 6 variants, 100 ms RTT, 3 trials |
| `t15_rtt25.csv`, `t15_rtt50.csv` | B-Queue / H-Sort at 25 / 50 ms RTT, 3 trials |
| `t16_wan2048.csv` | B-Queue / H-Sort, N=2048, 100 ms RTT, 3 trials |
| `camera_ready_diff.md` | generated: accepted-paper value → reproduced value per cell |
