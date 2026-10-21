# Expected results — provenance and how to read them

The CSVs in this directory are the artifact's expected results: per-trial rows (the
comparison takes medians) produced by `scripts/rerun_camera_ready.sh` on the
artifact's code with MP-SPDZ `58d2739a`, on a single Ubuntu 22.04 server.
`scripts/compare_camera_ready.py --baseline shipped` diffs a fresh rerun
against these CSVs (the exactness target); without the flag it diffs against
the paper's numbers (`data/paper_published_numbers.json`) and writes
`camera_ready_diff.md`.

## Deterministic columns

Communication volumes, round counts and compile-time preprocessing counts are
fixed by the compiled program and the public parameters. The paper's tables
carry exactly the values in these CSVs, so `data/paper_published_numbers.json`
agrees with them on every deterministic column. A reproduction should match
the shipped CSVs: communication and preprocessing counts exactly, rounds
within ±50 (round counts are identical across trials on one host and differ by
a few tens across hosts or MP-SPDZ builds).

## Timing columns

Wall-clock timings depend on the host and on co-tenant load. The server that
produced the paper's timings was under heavier load than at the time
of the artifact runs; the shipped LAN timings are therefore 30–70% lower than
the paper's while the deterministic columns are identical. WAN timings are
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
| `camera_ready_diff.md` | generated: paper value → reproduced value per cell |
