#!/usr/bin/env python3
# scripts/simulate_cpp_writer.py
# Replicates the logic of patched perf.cpp (Phase F1) to generate bit-identical
# shares on Mac.
#
# M_MAX resolution order (mirrors perf.cpp BLINDSTEP_M_MAX env var logic):
#   1. --m-max CLI argument   (highest priority)
#   2. BLINDSTEP_M_MAX env var
#   3. hardcoded default: 3
#
# Share-file row layout (per party):
#   Lines 0   .. 2*N_F-1          : A_scores (N_F) then A_valid (N_F)
#   Lines 2*N_F .. end             : for each A[i]: M_MAX*(flag,score) + overflow
#   Total rows per party = 2*N_F + N_F*(2*M_MAX + 1)
#
# Usage:
#   python scripts/simulate_cpp_writer.py                  # M_MAX=3
#   python scripts/simulate_cpp_writer.py --m-max 5        # M_MAX=5
#   BLINDSTEP_M_MAX=5 python scripts/simulate_cpp_writer.py

import argparse
import os
import sys


def parse_args():
    parser = argparse.ArgumentParser(
        description="BlindStep share-file simulator (mirrors perf.cpp writer logic)"
    )
    parser.add_argument(
        "--m-max", type=int, default=None,
        help="CPSI slot budget per A-row. Overrides BLINDSTEP_M_MAX env var. Default: 3."
    )
    parser.add_argument(
        "--n-f", type=int, default=256,
        help="Frontier table size N_F. Must match the .mpc N_F constant. Default: 256."
    )
    parser.add_argument(
        "--data-dir", type=str, default=None,
        help="Output directory for share files. Overrides BLINDSTEP_DATA_DIR env var. Default: Player-Data."
    )
    return parser.parse_args()


def resolve_m_max(cli_val):
    """Resolve M_MAX with priority: CLI > BLINDSTEP_M_MAX env > 3."""
    if cli_val is not None:
        m = cli_val
        src = "CLI --m-max"
    elif os.environ.get("BLINDSTEP_M_MAX"):
        raw = os.environ["BLINDSTEP_M_MAX"]
        try:
            m = int(raw)
        except ValueError:
            print(f"[BLINDSTEP WARNING] BLINDSTEP_M_MAX={raw!r} is not an integer; using default 3.", file=sys.stderr)
            m = 3
            src = "default (env parse error)"
        else:
            src = "BLINDSTEP_M_MAX env var"
    else:
        m = 3
        src = "default"

    if not (1 <= m <= 64):
        print(f"[BLINDSTEP WARNING] M_MAX={m} out of range [1,64]; clamping to 3.", file=sys.stderr)
        m = 3
    return m, src


def main():
    args = parse_args()
    M_MAX, m_src = resolve_m_max(args.m_max)
    N_F = args.n_f

    data_dir = args.data_dir or os.environ.get("BLINDSTEP_DATA_DIR", "Player-Data")
    os.makedirs(data_dir, exist_ok=True)

    path0 = os.path.join(data_dir, "Input-P0-0")
    path1 = os.path.join(data_dir, "Input-P1-0")

    total_rows = 2 * N_F + N_F * (2 * M_MAX + 1)
    print(f"[BLINDSTEP] M_MAX={M_MAX} (source: {m_src})")
    print(f"[BLINDSTEP] N_F={N_F}  share_rows_per_party={total_rows}"
          f"  (2*N_F={2*N_F} A-side + N_F*(2*M_MAX+1)={N_F*(2*M_MAX+1)} CPSI slots)")
    print(f"[SIMULATOR] Writing shares to {data_dir} ...")

    with open(path0, "w") as f0, open(path1, "w") as f1:
        # --- A_scores: P0 writes real data, P1 writes zeros ---
        for i in range(N_F):
            f0.write(f"{3 * (i + 1)}\n")
            f1.write("0\n")
        # --- A_valid: P0 writes 1, P1 writes zeros ---
        for i in range(N_F):
            f0.write("1\n")
            f1.write("0\n")

        # --- CPSI slots ---
        for b in range(N_F):
            # Simulation of matched_bin logic from perf.cpp
            # b % 3 == 0 → natural match from PSI
            natural_match = (b % 3 == 0)
            flag_p0_natural = 1 if natural_match else 0
            flag_p1_natural = 0
            score_p0_natural = (b + 100) if natural_match else 0
            score_p1_natural = 0

            inject = os.environ.get("BLINDSTEP_F1_INJECT") == "1"

            for m in range(M_MAX):
                f0_v, f1_v, s0_v, s1_v = 0, 0, 0, 0

                if m == 0:
                    f0_v = flag_p0_natural
                    f1_v = flag_p1_natural
                    s0_v = score_p0_natural
                    s1_v = score_p1_natural
                elif b == 3 and m == 1 and inject:
                    f0_v, f1_v = 1, 0
                    s0_v, s1_v = (b + 100) * (m + 1), 0
                elif b == 6 and (m == 1 or m == 2) and inject:
                    f0_v, f1_v = 0, 1
                    s0_v, s1_v = 0, (b + 100) * (m + 1)

                f0.write(f"{f0_v}\n")
                f1.write(f"{f1_v}\n")
                f0.write(f"{s0_v}\n")
                f1.write(f"{s1_v}\n")

            # Overflow share
            inject_overflow = os.environ.get("BLINDSTEP_INJECT_OVERFLOW") == "1"
            overflow_val = 1 if (inject_overflow and b == N_F - 1) else 0
            f0.write(f"{overflow_val}\n")
            f1.write("0\n")

    print(f"[SIMULATOR] Done. Wrote {total_rows} rows per file.")
    print(f"[SIMULATOR] Verify: wc -l {path0}  →  expected {total_rows}")


if __name__ == "__main__":
    main()
