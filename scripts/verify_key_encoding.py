#!/usr/bin/env python3
# scripts/verify_key_encoding.py
# Paper Appendix F.3: key-encoding injectivity check.
#
# The encode/decode implementations are NOT duplicated here: they are imported
# from mpc/bs_core.py, so this test exercises exactly the code the MPC programs
# run. bs_core imports MP-SPDZ's Compiler package at module load; the three
# functions used here (get_tuple_shifts / encode_tuple / decode_tuple) are pure
# integer arithmetic and never touch sint, so a minimal stub is installed when
# MP-SPDZ is absent, letting this test run on any machine.
#
# Two layers of testing:
#   1. Exhaustive, at the historical F.3 width T=8 (2 * 2^16 * 256 =
#      33,554,432 triples) — matches the count reported in the paper.
#   2. Randomized sampling at the PRODUCTION widths that bs_core.get_tuple_shifts
#      actually derives (T=36 for N=256, T=46 for N=8192), 10^6 triples each.
#
# Run:  python scripts/verify_key_encoding.py [--samples 1000000] [--quick]

import argparse
import os
import random
import sys
import types

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)


def _install_compiler_stub():
    """Allow importing mpc.bs_core without a local MP-SPDZ checkout."""
    try:
        import Compiler.types  # noqa: F401
        return False
    except ImportError:
        pass
    pkg = types.ModuleType("Compiler")
    pkg.__path__ = []
    tmod = types.ModuleType("Compiler.types")
    lmod = types.ModuleType("Compiler.library")
    for name in ("sint", "Array", "MemValue"):
        setattr(tmod, name, type(name, (), {}))
    for name in ("for_range", "for_range_opt", "print_ln", "crash", "if_"):
        setattr(lmod, name, lambda *a, **k: None)
    sys.modules["Compiler"] = pkg
    sys.modules["Compiler.types"] = tmod
    sys.modules["Compiler.library"] = lmod
    return True


STUBBED = _install_compiler_stub()

from mpc.bs_core import get_tuple_shifts, encode_tuple, decode_tuple  # noqa: E402


def local_shifts(TIE_BITS, SCORE_BITS):
    """
    Layout parameters for an explicitly chosen tie width.

    Used for the exhaustive pass, which keeps the historical F.3 width T=8 so
    the enumerated case count stays 33,554,432. The layout formula mirrors
    bs_core.get_tuple_shifts; only the width source differs (set here vs.
    derived there). encode/decode themselves are always bs_core's.
    """
    PACKED_BITS = 1 + SCORE_BITS + TIE_BITS
    SCORE_SHIFT = TIE_BITS
    VALID_SHIFT = TIE_BITS + SCORE_BITS
    MAX_TIE = (2 ** TIE_BITS) - 1
    return TIE_BITS, PACKED_BITS, SCORE_SHIFT, VALID_SHIFT, MAX_TIE


def roundtrip_ok(v, s, t, V_SHIFT, S_SHIFT, SCORE_BITS, T_BITS, M_TIE):
    enc = encode_tuple(v, s, t, V_SHIFT, S_SHIFT, M_TIE)
    return (v, s, t) == decode_tuple(enc, V_SHIFT, S_SHIFT, SCORE_BITS, T_BITS, M_TIE), enc


def sample_cases(SCORE_BITS):
    N_F = 256
    T_BITS, PACKED_BITS, S_SHIFT, V_SHIFT, M_TIE = local_shifts(8, SCORE_BITS)
    print("\n--- Injective check (sample cases, T=8) ---")
    ok = True
    seen = {}
    for v, s, t in [(1, 0, 0), (1, 12345, 255), (0, 0, 100),
                    (1, (1 << SCORE_BITS) - 1, N_F - 1), (0, 42, 0)]:
        good, enc = roundtrip_ok(v, s, t, V_SHIFT, S_SHIFT, SCORE_BITS, T_BITS, M_TIE)
        print(f"Input: (v={v}, s={s:5}, t={t:3}) -> Encoded: {enc:15} [{'PASS' if good else 'FAIL'}]")
        ok &= good
        if enc in seen and seen[enc] != (v, s, t):
            print(f"[COLLISION DETECTED] {enc} maps to both {seen[enc]} and {(v, s, t)}")
            ok = False
        seen[enc] = (v, s, t)
    return ok


def exhaustive(SCORE_BITS, quick=False):
    """
    Exhaustive round-trip over the full (valid, score, tie) domain at T=8.
    Count: 2 * 2^SCORE_BITS * 256 = 33,554,432 for SCORE_BITS=16 (paper F.3).
    """
    N_F = 256
    T_BITS, PACKED_BITS, S_SHIFT, V_SHIFT, M_TIE = local_shifts(8, SCORE_BITS)
    score_range = 256 if quick else (2 ** SCORE_BITS)
    total = 2 * score_range * N_F
    print(f"\n--- Exhaustive check (T={T_BITS}, {total:,} triples{' [QUICK]' if quick else ''}) ---")

    failure = None
    for v in (0, 1):
        for s in range(score_range):
            for t in range(N_F):
                good, _ = roundtrip_ok(v, s, t, V_SHIFT, S_SHIFT, SCORE_BITS, T_BITS, M_TIE)
                if not good:
                    failure = (v, s, t)
                    break            # break out of all three loops, not just this one
            if failure:
                break
        if failure:
            break

    if failure:
        print(f"[FAIL] Collision/corruption at (v={failure[0]}, s={failure[1]}, t={failure[2]})")
        return False, total
    print(f"[OK] {total:,} cases tested, 0 collisions.")
    return True, total


def production_widths(SCORE_BITS, samples):
    """
    Randomized round-trip at the widths bs_core.get_tuple_shifts really derives
    (2*ceil(log2 N) + 20), which the exhaustive T=8 pass does not cover.
    """
    print(f"\n--- Production-width sampling ({samples:,} triples per config) ---")
    ok = True
    rng = random.Random(20260713)   # fixed seed: reproducible
    for N in (256, 8192):
        T_BITS, PACKED_BITS, S_SHIFT, V_SHIFT, M_TIE = get_tuple_shifts(N, SCORE_BITS)
        print(f"N={N:5}: TIE_BITS={T_BITS}, PACKED_BITS={PACKED_BITS}, MAX_TIE={M_TIE}")
        if PACKED_BITS >= 64:
            print(f"[FAIL] PACKED_BITS={PACKED_BITS} does not fit the 64-bit ring")
            ok = False
            continue
        bad = None
        for _ in range(samples):
            v = rng.randint(0, 1)
            s = rng.randrange(1 << SCORE_BITS)
            t = rng.randrange(M_TIE + 1)
            good, _ = roundtrip_ok(v, s, t, V_SHIFT, S_SHIFT, SCORE_BITS, T_BITS, M_TIE)
            if not good:
                bad = (v, s, t)
                break
        if bad:
            print(f"[FAIL] round-trip failed at (v={bad[0]}, s={bad[1]}, t={bad[2]})")
            ok = False
        else:
            print(f"[OK] {samples:,} random triples round-tripped exactly.")
    return ok


def main():
    ap = argparse.ArgumentParser(description="F.3 key-encoding injectivity check")
    ap.add_argument("--samples", type=int, default=1_000_000,
                    help="random triples per production-width config (default 10^6)")
    ap.add_argument("--quick", action="store_true",
                    help="shrink the exhaustive pass (smoke test; not the paper's count)")
    a = ap.parse_args()

    SCORE_BITS = 16
    print("=== Appendix F.3: key-encoding injectivity ===")
    print(f"encode/decode imported from mpc.bs_core"
          f"{' (MP-SPDZ absent: Compiler stubbed)' if STUBBED else ''}")
    print(f"SCORE_BITS: {SCORE_BITS}")

    ok_samples = sample_cases(SCORE_BITS)
    ok_exhaustive, total = exhaustive(SCORE_BITS, a.quick)
    ok_production = production_widths(SCORE_BITS, a.samples)

    all_pass = ok_samples and ok_exhaustive and ok_production
    print("\n[CONCLUSION] Key encoding is INJECTIVE across all tested ranges."
          if all_pass else "\n[CONCLUSION] Key encoding has ISSUES.")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
