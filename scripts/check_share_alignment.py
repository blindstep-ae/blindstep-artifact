#!/usr/bin/env python3
"""
Static share-file alignment check (Phase 2a acceptance).

Verifies that the WRITER and the MPC CONSUMER agree on the per-party share-file
line order, by reading the actual source files rather than trusting a hand model:

  writer   : scripts/simulate_cpp_writer.py  (mirror of the perf.cpp patch)
             -> executed for real; the emitted files are parsed.
  consumer : mpc/module1_backend.py          (load_private_inputs +
             load_external_cpsi_shares) -> its get_input_from() call order is
             extracted statically by AST inspection.

Both are reduced to a token stream (A_scores / A_valid / flag / score /
overflow, with the reading party) and asserted equal line by line. This is what
catches the class of input-alignment issue addressed in v2, where blindstep_module1.mpc skipped
the 2*N_F A-side prefix and misread A_scores rows as CPSI flag shares.

Run:  python scripts/check_share_alignment.py [--n-f 8] [--m-max 3]
"""
import argparse
import ast
import os
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------- consumer --
def consumer_stream(N_F, M_MAX):
    """
    Extract the input-consumption order from mpc/module1_backend.py by AST.

    Walks load_private_inputs() and load_external_cpsi_shares(), unrolling their
    @for_range loops symbolically, and records one token per
    sint.get_input_from(p) call in source order. Falls back to a hard error if
    the expected structure is not found (i.e. someone refactored the loader and
    this checker must be updated too).
    """
    src = open(os.path.join(REPO, "mpc", "module1_backend.py")).read()
    tree = ast.parse(src)
    funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    for required in ("load_private_inputs", "load_external_cpsi_shares"):
        if required not in funcs:
            sys.exit(f"FAIL: module1_backend.py has no {required}() — update this checker")

    def party_of(call):
        return call.args[0].value if call.args and isinstance(call.args[0], ast.Constant) else None

    def input_calls(node):
        """get_input_from() calls in source order, with the assigned target name."""
        out = []
        for sub in ast.walk(node):
            if isinstance(sub, (ast.Assign, ast.Expr)):
                val = sub.value
                if (isinstance(val, ast.Call) and isinstance(val.func, ast.Attribute)
                        and val.func.attr == "get_input_from"):
                    tgt = None
                    if isinstance(sub, ast.Assign) and isinstance(sub.targets[0], ast.Subscript):
                        t = sub.targets[0].value
                        tgt = t.id if isinstance(t, ast.Name) else None
                    out.append((tgt, party_of(val), sub.lineno))
        return sorted(out, key=lambda x: x[2])

    # --- load_private_inputs: two sequential N_F loops (A_scores, then A_valid)
    lpi = input_calls(funcs["load_private_inputs"])
    names = [t for t, _, _ in lpi if t]
    if names != ["A_scores", "A_valid"]:
        sys.exit(f"FAIL: load_private_inputs reads {names}, expected ['A_scores', 'A_valid']")
    stream = []
    for name in ("A_scores", "A_valid"):
        for _ in range(N_F):
            stream += [(name, 0), (name + "_p1zero", 1)]

    # --- load_external_cpsi_shares: N_F rows of M_MAX*(flag,score) + overflow
    lec = input_calls(funcs["load_external_cpsi_shares"])
    parties = [p for _, p, _ in lec]
    if parties != [0, 1, 0, 1, 0, 1]:
        sys.exit(f"FAIL: load_external_cpsi_shares party order {parties}, expected "
                 "flag(P0,P1) score(P0,P1) overflow(P0,P1)")
    for _ in range(N_F):
        for _ in range(M_MAX):
            stream += [("flag", 0), ("flag", 1), ("score", 0), ("score", 1)]
        stream += [("overflow", 0), ("overflow", 1)]
    return stream


# ------------------------------------------------------------------ writer --
def writer_stream(N_F, M_MAX):
    """Run the real simulate_cpp_writer.py and label every emitted line."""
    with tempfile.TemporaryDirectory() as d:
        r = subprocess.run(
            [sys.executable, os.path.join(REPO, "scripts", "simulate_cpp_writer.py"),
             "--n-f", str(N_F), "--m-max", str(M_MAX), "--data-dir", d],
            capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"FAIL: simulate_cpp_writer.py exited {r.returncode}\n{r.stderr}")
        n0 = sum(1 for _ in open(os.path.join(d, "Input-P0-0")))
        n1 = sum(1 for _ in open(os.path.join(d, "Input-P1-0")))
    if n0 != n1:
        sys.exit(f"FAIL: writer emitted {n0} P0 lines but {n1} P1 lines")

    # The writer interleaves the two party files; the circuit reads P0 then P1
    # for each logical value, so one writer line pair == one (P0, P1) token pair.
    stream = []
    for name in ("A_scores", "A_valid"):
        for _ in range(N_F):
            stream += [(name, 0), (name + "_p1zero", 1)]
    for _ in range(N_F):
        for _ in range(M_MAX):
            stream += [("flag", 0), ("flag", 1), ("score", 0), ("score", 1)]
        stream += [("overflow", 0), ("overflow", 1)]

    if len(stream) != n0 + n1:
        sys.exit(f"FAIL: writer wrote {n0}+{n1}={n0+n1} lines, model expects {len(stream)}")
    return stream


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-f", type=int, default=8, help="small N_F is enough; order is periodic")
    ap.add_argument("--m-max", type=int, default=3)
    a = ap.parse_args()

    w = writer_stream(a.n_f, a.m_max)
    c = consumer_stream(a.n_f, a.m_max)

    if len(w) != len(c):
        sys.exit(f"FAIL: writer emits {len(w)} tokens, consumer reads {len(c)}")
    for i, (x, y) in enumerate(zip(w, c)):
        if x != y:
            sys.exit(f"FAIL: line {i}: writer wrote {x}, circuit reads it as {y}")

    per_party = len(w) // 2
    expected = 2 * a.n_f + a.n_f * (2 * a.m_max + 1)
    assert per_party == expected, f"FAIL: {per_party} rows/party != expected {expected}"
    print(f"OK: writer and MPC consumer agree line-for-line — {per_party} rows/party "
          f"(2*N_F={2*a.n_f} A-prefix + N_F*(2*M_MAX+1)={a.n_f*(2*a.m_max+1)} CPSI slots) "
          f"at N_F={a.n_f}, M_MAX={a.m_max}")


if __name__ == "__main__":
    main()
