#!/usr/bin/env python3
"""
scripts/compare_camera_ready.py

Diff a rerun produced by rerun_camera_ready.sh against one of two baselines:

  --baseline paper    (default) data/paper_published_numbers.json, extracted from
                      the accepted PDF. Deterministic columns are expected to
                      differ by the small constant cost of the security-alignment
                      changes (one secure comparison, N_F multiplications, K exact
                      truncations). Writes <rerun-dir>/camera_ready_diff.md.

  --baseline shipped  the shipped expected-results CSVs in
                      results/camera_ready_rerun/, which is the exactness target
                      stated in the README: communication (MB) and the Table 8
                      preprocessing counts must be equal, round counts must agree
                      within ±0.1% (floor ±8) of the shipped value, and wall-clock
                      times are reported but never judged. Prints a PASS/MISMATCH
                      table, writes <rerun-dir>/shipped_vs_rerun.md, and exits
                      non-zero if any deterministic value disagrees.

Tables whose rerun CSV is missing are reported as not re-measured, not as failures.

Usage:  python3 scripts/compare_camera_ready.py --baseline shipped
        python3 scripts/compare_camera_ready.py --rerun-dir results/rerun
"""
import argparse
import csv
import json
import os
import re
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHIPPED_DEFAULT = os.path.join("results", "camera_ready_rerun")
RERUN_DEFAULT = os.path.join("results", "rerun")
RERUN = os.path.join(ROOT, RERUN_DEFAULT)       # set from --rerun-dir in main()
PAPER = json.load(open(os.path.join(ROOT, "data", "paper_published_numbers.json")))
OUT_MD = os.path.join(RERUN, "camera_ready_diff.md")

VNAMES = {v: k for k, v in PAPER["_meta"]["variant_key"].items()}  # slug -> paper name


def read_rows(fname):
    p = os.path.join(RERUN, fname)
    if not os.path.exists(p):
        return None
    with open(p) as f:
        return [r for r in csv.DictReader(f)]


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def med(rows, key):
    vals = [fnum(r[key]) for r in rows]
    vals = [v for v in vals if v is not None]
    return statistics.median(vals) if vals else None


def fmt(v, nd=3):
    if v is None:
        return "—"
    if isinstance(v, float) and v.is_integer() and abs(v) >= 100:
        return f"{int(v):,}"
    return f"{v:,.{nd}f}" if isinstance(v, float) else f"{v:,}"


def delta_cell(old, new, pct_warn=5.0):
    if old is None or new is None:
        return "—"
    if old == 0:
        return f"{new - old:+.3f}"
    pct = 100.0 * (new - old) / old
    flag = " ⚠" if abs(pct) > pct_warn else ""
    return f"{new - old:+,.3f} ({pct:+.2f}%){flag}"


MD = []


def section(title, caveat=None):
    MD.append(f"\n## {title}\n")
    if caveat:
        MD.append(f"> {caveat}\n")


def table(header, rows):
    MD.append("| " + " | ".join(header) + " |")
    MD.append("|" + "---|" * len(header))
    for r in rows:
        MD.append("| " + " | ".join(r) + " |")
    MD.append("")


def variant_medians(rows, variant, N, m_max="3"):
    sel = [r for r in rows
           if r["variant"] == variant and r["N"] == str(N) and r["m_max"] == str(m_max)
           and r["trial"] not in ("COMPILE_FAIL",) and r["P1_s"] != "RUN_FAIL"]
    if not sel:
        return None
    return {k: med(sel, k) for k in ("P1_s", "P2_s", "P3_s", "total_s", "global_MB", "rounds")}, len(sel)


# ---------------------------------------------------------------- Table 4 --
def do_t4():
    rows = read_rows("t4_main_table.csv")
    section("Table 4 — full-pipeline breakdown (N=256, LAN)",
            "Paper medians over n=7 trials; rerun medians over n=5. H-variant P2 published as <0.01 (stored 0.01).")
    if rows is None:
        MD.append("_not re-measured yet (t4_main_table.csv missing)_\n")
        return
    hdr = ["Variant", "P1 old→new", "P3 old→new", "Total old→new", "ΔTotal", "MB old→new", "ΔMB", "Rounds old→new", "ΔRounds"]
    body = []
    for slug, old in PAPER["table4"]["rows"].items():
        got = variant_medians(rows, slug, 256)
        if not got:
            body.append([VNAMES[slug], "no data", "", "", "", "", "", "", ""])
            continue
        m, n = got
        body.append([
            VNAMES[slug],
            f"{fmt(old[0])}→{fmt(m['P1_s'])}",
            f"{fmt(old[2])}→{fmt(m['P3_s'])}",
            f"{fmt(old[3])}→{fmt(m['total_s'])}",
            delta_cell(old[3], m["total_s"]),
            f"{fmt(old[4], 1)}→{fmt(m['global_MB'], 1)}",
            delta_cell(old[4], m["global_MB"], pct_warn=2.0),
            f"{fmt(float(old[5]), 0)}→{fmt(m['rounds'], 0)}",
            delta_cell(float(old[5]), m["rounds"], pct_warn=2.0),
        ])
    table(hdr, body)


# ---------------------------------------------------------------- Table 5 --
def do_t5():
    t4 = read_rows("t4_main_table.csv")
    t5 = read_rows("t5_nsweep.csv")
    section("Table 5 — total runtime across N (LAN)",
            "Paper: n=5 per cell (n=10 at N=2048, n=7 at N=256); rerun: n=5 everywhere.")
    if t5 is None:
        MD.append("_not re-measured yet (t5_nsweep.csv missing)_\n")
        return
    Ns = PAPER["table5"]["columns"]
    hdr = ["Variant"] + [f"N={n}" for n in Ns]
    body = []
    for slug, olds in PAPER["table5"]["rows"].items():
        cells = [VNAMES[slug]]
        for N, old in zip(Ns, olds):
            src = t4 if (N == 256 and t4 is not None) else t5
            got = variant_medians(src, slug, N) if src else None
            if not got:
                cells.append(f"{fmt(old, 2)}→—")
            else:
                m, _ = got
                cells.append(f"{fmt(old, 2)}→{fmt(m['total_s'], 2)} ({delta_cell(old, m['total_s'])})")
        body.append(cells)
    table(hdr, body)


# ---------------------------------------------------------------- Table 8 --
def parse_t8_raw(d=None):
    """Parse t8_preprocessing_raw.txt: handles 'inf' and 'loose edabits' forms.

    The raw log is authoritative for Table 8: t8_preprocessing.csv carried an
    unqualified 'edabits' pattern that never matched MP-SPDZ's
    'N loose edabits of length 64', so its edaBits column may read '-'.
    """
    p = os.path.join(d or RERUN, "t8_preprocessing_raw.txt")
    if not os.path.exists(p):
        return None
    out, cur = {}, None
    for line in open(p):
        m = re.match(r"=====\s+(\S+)\s+=====", line)
        if m:
            cur = m.group(1)
            out[cur] = {"integer_triples": None, "edabits": None, "bit_triples": None}
            continue
        if cur is None:
            continue
        m = re.match(r"\s*(inf|[0-9]+)\s+(loose\s+)?(integer triples|edabits|bit triples)", line)
        if m:
            v = "inf" if m.group(1) == "inf" else float(m.group(1))
            key = m.group(3).replace(" ", "_")
            out[cur][key] = v
    return out


def do_t8():
    raw = parse_t8_raw()
    section("Table 8 — compile-time preprocessing estimates (N=256)",
            "Deterministic: any change is exactly the added cost of changes 1a/1b/1c. 'inf' rows: MP-SPDZ static analyzer reports unbounded for Select variants.")
    if raw is None:
        MD.append("_not re-measured yet (t8_preprocessing_raw.txt missing)_\n")
        return
    by = {v: {"integer_triples": d["integer_triples"], "edabits": d["edabits"],
              "bit_triples": d["bit_triples"]} for v, d in raw.items()}
    hdr = ["Variant", "int. triples old→new", "Δ", "edaBits old→new", "bit triples old→new", "Δ"]
    body = []
    for slug, old in PAPER["table8"]["rows"].items():
        r = by.get(slug)
        it_o, eb_o, bt_o = old

        def show(o, n):
            os_ = fmt(o, 0) if isinstance(o, (int, float)) else (o or "—")
            ns_ = fmt(n, 0) if isinstance(n, (int, float)) else (n or "—")
            return f"{os_}→{ns_}"

        def dc(o, n):
            return delta_cell(o, n, 1.0) if isinstance(o, (int, float)) and isinstance(n, (int, float)) else "—"

        if r is None:
            body.append([VNAMES[slug], "no data", "", "", "", ""])
            continue
        it_n, eb_n, bt_n = r["integer_triples"], r["edabits"], r["bit_triples"]
        body.append([VNAMES[slug], show(it_o, it_n), dc(it_o, it_n),
                     show(eb_o, eb_n), show(bt_o, bt_n), dc(bt_o, bt_n)])
    table(hdr, body)


# --------------------------------------------------------------- Table 13 --
def do_t13():
    rows = read_rows("t13_mmax.csv")
    section("Table 13 — M_max sensitivity (H-Queue, N=256, LAN)",
            "Paper 'P1 Rds.' comes from runtime profiling; rerun provides a module1-only static VM-rounds estimate (module1_static rows) — compare trends, not absolutes. n=3 both.")
    if rows is None:
        MD.append("_not re-measured yet (t13_mmax.csv missing)_\n")
        return
    hdr = ["M_max", "P1 old→new", "P3 old→new", "Total old→new", "ΔTotal", "P1 rounds old / static-est new"]
    body = []
    for m, old in PAPER["table13"]["rows"].items():
        got = variant_medians(rows, "hybrid_queue", 256, m)
        est = [r for r in rows if r["variant"] == "module1_static" and r["m_max"] == m]
        est_v = est[0]["P1_s"] if est else "—"
        if not got:
            body.append([m, "no data", "", "", "", f"{fmt(float(old[1]),0)} / {est_v}"])
            continue
        mm, _ = got
        body.append([
            m,
            f"{fmt(old[0])}→{fmt(mm['P1_s'])}",
            f"{fmt(old[2])}→{fmt(mm['P3_s'])}",
            f"{fmt(old[3])}→{fmt(mm['total_s'])}",
            delta_cell(old[3], mm["total_s"]),
            f"{fmt(float(old[1]),0)} / {est_v}",
        ])
    table(hdr, body)


# --------------------------------------------------------------- Table 14 --
def do_t14():
    rows = read_rows("t14_density.csv")
    section("Table 14 — Module 1 density sweep (N=256, single runs)",
            "MUST-RERUN table: change 2a changed blindstep_module1's input consumption. Paper P1 ≈ rerun (P1a ingress + P1b aggregation). Comm/rounds shift by changes 1a/1b.")
    if rows is None:
        MD.append("_not re-measured yet (t14_density.csv missing)_\n")
        return
    by = {r["density_pct"]: r for r in rows}
    hdr = ["δ", "P1 old→new(P1a+P1b)", "ΔP1", "MB old→new", "Rounds old→new"]
    body = []
    for d, old in PAPER["table14"]["rows"].items():
        r = by.get(d)
        if r is None:
            body.append([f"{d}%", "no data", "", "", ""])
            continue
        p1n = (fnum(r["P1a_ingress_s"]) or 0) + (fnum(r["P1b_agg_s"]) or 0)
        body.append([
            f"{d}%",
            f"{fmt(old[1])}→{fmt(p1n)}",
            delta_cell(old[1], p1n),
            f"{fmt(old[2],1)}→{fmt(fnum(r['global_MB']),1)}",
            f"{fmt(float(old[3]),0)}→{fmt(fnum(r['rounds']),0)}",
        ])
    table(hdr, body)


# ------------------------------------------------------- WAN tables 6/15/16 --
def wan_table(title, caveat, csv_name, paper_key, N, row_iter):
    """Generic P1/P3/Total/MB/Rounds comparison for the unified-schema WAN CSVs.

    row_iter yields (paper_row_key, variant_slug, display_label)."""
    rows = read_rows(csv_name)
    section(title, caveat)
    if rows is None:
        MD.append(f"_not re-measured yet ({csv_name} missing)_\n")
        return
    hdr = ["Row", "P1 old→new", "P3 old→new", "Total old→new", "ΔTotal", "MB old→new", "Rounds old→new", "ΔRounds"]
    body = []
    for paper_row, slug, label in row_iter:
        old = PAPER[paper_key]["rows"][paper_row]
        cols = PAPER[paper_key]["columns"]

        def o(name, default=None):
            return old[cols.index(name)] if name in cols else default

        got = variant_medians(rows, slug, N)
        if not got:
            body.append([label, "no data", "", "", "", "", "", ""])
            continue
        m, _ = got
        o_tot, o_mb, o_rd = (o("Total"), o("MB"), o("Rounds"))
        body.append([
            label,
            f"{fmt(o('P1'), 1)}→{fmt(m['P1_s'], 1)}" if o("P1") is not None else "—",
            f"{fmt(o('P3'), 1)}→{fmt(m['P3_s'], 1)}" if o("P3") is not None else "—",
            f"{fmt(o_tot, 1)}→{fmt(m['total_s'], 1)}",
            delta_cell(o_tot, m["total_s"]),
            f"{fmt(o_mb, 1)}→{fmt(m['global_MB'], 1)}",
            f"{fmt(float(o_rd), 0)}→{fmt(m['rounds'], 0)}",
            delta_cell(float(o_rd), m["rounds"], pct_warn=2.0),
        ])
    table(hdr, body)


def do_wan():
    wan_table("Table 6 — WAN main table (N=256, 100ms RTT)",
              "Timing dominated by rounds under WAN; expect ΔTotal to track ΔRounds "
              "(~+0.5% H / ~+0.05% B), plus environment noise. n=3 both.",
              "t6_wan.csv", "table6", 256,
              [(slug, slug, VNAMES[slug]) for slug in PAPER["table6"]["rows"]])
    for rtt in (25, 50):
        wan_table(f"Table 15 — RTT sweep ({rtt}ms rows)",
                  "100ms rows of Table 15 are Table 6 entries (see above). n=3 both.",
                  f"t15_rtt{rtt}.csv", "table15", 256,
                  [(f"{rtt}ms_{slug}", slug, f"{rtt}ms {VNAMES[slug]}")
                   for slug in ("ab_queue", "hybrid_batcher_sort")])
    wan_table("Table 16 — large-N WAN (N=2048, 100ms RTT)",
              "Published note gives no trial count; rerun uses n=3.",
              "t16_wan2048.csv", "table16", 2048,
              [(slug, slug, VNAMES[slug]) for slug in PAPER["table16"]["rows"]])


# ------------------------------------------- shipped-baseline exactness check --
# The unified-schema stage CSVs, in the order the README presents the tables.
UNIFIED = [
    ("Table 4 (N=256, LAN)", "t4_main_table.csv"),
    ("Table 5/12 (N sweep, LAN)", "t5_nsweep.csv"),
    ("Table 13 (M_max sweep)", "t13_mmax.csv"),
    ("Table 6 (WAN, N=256)", "t6_wan.csv"),
    ("Table 15 (RTT 25 ms)", "t15_rtt25.csv"),
    ("Table 15 (RTT 50 ms)", "t15_rtt50.csv"),
    ("Table 16 (WAN, N=2048)", "t16_wan2048.csv"),
]

MB_TOL = 1e-6        # communication is deterministic: equality, not tolerance
ROUND_TOL_REL = 0.001  # MP-SPDZ runtime batching shifts the reported count ...
ROUND_TOL_MIN = 8.0    # ... by a few units; floor keeps small P1-only rows sane


def round_tol(shipped):
    return max(ROUND_TOL_MIN, ROUND_TOL_REL * abs(shipped))


def rows_from(d, fname):
    p = os.path.join(d, fname)
    if not os.path.exists(p):
        return None
    with open(p) as f:
        return [r for r in csv.DictReader(f)]


def unified_cells(rows):
    """(variant, N, m_max) -> per-column medians, skipping recorded failures."""
    grouped = {}
    for r in rows:
        if r.get("trial") == "COMPILE_FAIL" or r.get("P1_s") == "RUN_FAIL":
            continue
        grouped.setdefault((r["variant"], r["N"], r["m_max"]), []).append(r)
    return {k: {c: med(v, c) for c in ("total_s", "global_MB", "rounds")}
            for k, v in grouped.items()}


def judge(shipped, rerun):
    """-> (status, detail) for one cell's deterministic columns."""
    bits, status = [], "PASS"
    mb_s, mb_r = shipped["global_MB"], rerun["global_MB"]
    if mb_s is not None and mb_r is not None:
        if abs(mb_r - mb_s) > MB_TOL:
            status = "MISMATCH"
            bits.append(f"MB {mb_s:,.3f}→{mb_r:,.3f} ({mb_r - mb_s:+,.3f})")
        else:
            bits.append(f"MB {mb_s:,.3f} exact")
    rd_s, rd_r = shipped["rounds"], rerun["rounds"]
    if rd_s is not None and rd_r is not None:
        d, tol = rd_r - rd_s, round_tol(rd_s)
        bits.append(f"rounds {rd_s:,.0f}→{rd_r:,.0f} ({d:+,.0f}, tol ±{tol:,.0f})")
        if abs(d) > tol:
            status = "MISMATCH" if status == "MISMATCH" else "OUT-OF-TOL"
    t_s, t_r = shipped["total_s"], rerun["total_s"]
    if t_s and t_r:
        bits.append(f"time {t_s:,.2f}→{t_r:,.2f}s ({100.0 * (t_r - t_s) / t_s:+.1f}%, not judged)")
    return status, "; ".join(bits)


def check_unified(label, fname, shipped_dir, rerun_dir, report):
    s_rows = rows_from(shipped_dir, fname)
    r_rows = rows_from(rerun_dir, fname)
    if s_rows is None:
        report.append((label, "—", "SKIP", "no shipped baseline for this table"))
        return 0
    if r_rows is None:
        report.append((label, "—", "SKIP", "not re-measured"))
        return 0
    s, r = unified_cells(s_rows), unified_cells(r_rows)
    bad = 0
    for key in sorted(s):
        name = "{0} N={1} M={2}".format(*key)
        if key not in r:
            report.append((label, name, "SKIP", "not in rerun"))
            continue
        status, detail = judge(s[key], r[key])
        report.append((label, name, status, detail))
        if status != "PASS":
            bad += 1
    return bad


def check_t8(shipped_dir, rerun_dir, report):
    label = "Table 8 (preprocessing, N=256)"
    s, r = parse_t8_raw(shipped_dir), parse_t8_raw(rerun_dir)
    if s is None:
        report.append((label, "—", "SKIP", "no shipped t8_preprocessing_raw.txt"))
        return 0
    if r is None:
        report.append((label, "—", "SKIP", "not re-measured"))
        return 0
    bad = 0
    for v in sorted(s):
        if v not in r:
            report.append((label, v, "SKIP", "not in rerun"))
            continue
        diffs = [f"{k} {s[v][k]}→{r[v][k]}" for k in ("integer_triples", "edabits", "bit_triples")
                 if s[v][k] != r[v][k]]
        if diffs:
            report.append((label, v, "MISMATCH", "; ".join(diffs)))
            bad += 1
        else:
            report.append((label, v, "PASS", "all three counts equal"))
    return bad


def check_t14(shipped_dir, rerun_dir, report):
    label = "Table 14 (density sweep)"
    s_rows = rows_from(shipped_dir, "t14_density.csv")
    r_rows = rows_from(rerun_dir, "t14_density.csv")
    if s_rows is None:
        report.append((label, "—", "SKIP", "no shipped baseline for this table"))
        return 0
    if r_rows is None:
        report.append((label, "—", "SKIP", "not re-measured (optional stage t14)"))
        return 0
    r_by = {x["density_pct"]: x for x in r_rows}
    bad = 0
    for x in s_rows:
        d = x["density_pct"]
        y = r_by.get(d)
        if y is None:
            report.append((label, f"δ={d}%", "SKIP", "not in rerun"))
            continue
        cell = {"global_MB": fnum(x["global_MB"]), "rounds": fnum(x["rounds"]),
                "total_s": fnum(x["total_s"])}
        got = {"global_MB": fnum(y["global_MB"]), "rounds": fnum(y["rounds"]),
               "total_s": fnum(y["total_s"])}
        status, detail = judge(cell, got)
        report.append((label, f"δ={d}%", status, detail))
        if status != "PASS":
            bad += 1
    return bad


def do_shipped(shipped_dir, rerun_dir):
    report = []
    bad = sum(check_unified(label, fname, shipped_dir, rerun_dir, report)
              for label, fname in UNIFIED)
    bad += check_t8(shipped_dir, rerun_dir, report)
    bad += check_t14(shipped_dir, rerun_dir, report)

    rel = lambda p: os.path.relpath(p, ROOT)
    MD.append("# Rerun vs shipped expected results\n")
    MD.append(f"Shipped baseline: `{rel(shipped_dir)}/` · Rerun: `{rel(rerun_dir)}/`\n")
    MD.append("Communication (MB) and the Table 8 preprocessing counts must be equal; "
              f"round counts must agree within ±{ROUND_TOL_REL * 100:g}% of the shipped "
              f"value (floor ±{ROUND_TOL_MIN:g}); wall-clock times are reported but not judged.\n")
    table(["Table", "Cell", "Status", "Detail"], report)
    counts = {}
    for _, _, status, _ in report:
        counts[status] = counts.get(status, 0) + 1
    summary = ", ".join(f"{n} {k}" for k, n in sorted(counts.items()))
    MD.append(f"**{summary or 'nothing compared'}**\n")

    os.makedirs(rerun_dir, exist_ok=True)
    out = os.path.join(rerun_dir, "shipped_vs_rerun.md")
    with open(out, "w") as f:
        f.write("\n".join(MD))
    for row in report:
        if row[2] != "PASS":
            print(f"{row[2]:<10} {row[0]} · {row[1]} · {row[3]}")
    print(f"wrote {out}")
    print(summary or "nothing compared")
    if bad:
        print(f"FAIL: {bad} cell(s) disagree with the shipped expected results")
        return 1
    print("PASS: deterministic columns match the shipped expected results")
    return 0


def do_paper():
    os.makedirs(RERUN, exist_ok=True)
    MD.append("# Camera-ready cost diff — v2 vs published\n")
    MD.append(f"Rerun dir: `{os.path.relpath(RERUN, ROOT)}/` · Paper baseline: `data/paper_published_numbers.json`\n")
    MD.append("Expected v2 cost (1a+1b+1c): ~+0.5% comm / ~+0.5% rounds at N=256 "
              "(verified S5 snapshot: +2.1 MB, +155 rounds on H-Queue). "
              "A content-dependent or large delta is a red flag — investigate before updating the paper.\n")
    do_t4()
    do_t5()
    do_t8()
    do_t13()
    do_t14()
    do_wan()
    with open(OUT_MD, "w") as f:
        f.write("\n".join(MD))
    print(f"wrote {OUT_MD}")
    missing = [s for s in MD if s.startswith("_not re-measured")]
    print(f"{len(missing)} table(s) still waiting for rerun data" if missing else "all tables compared")
    return 0


def main():
    global RERUN, OUT_MD
    ap = argparse.ArgumentParser(
        description="Diff a rerun against the accepted-paper numbers or the shipped CSVs.")
    ap.add_argument("--baseline", choices=("paper", "shipped"), default="paper",
                    help="paper: data/paper_published_numbers.json (default); "
                         "shipped: the expected-results CSVs, the README's exactness target")
    ap.add_argument("--rerun-dir", default=RERUN_DEFAULT,
                    help=f"rerun output directory (default: {RERUN_DEFAULT})")
    ap.add_argument("--shipped-dir", default=SHIPPED_DEFAULT,
                    help=f"shipped expected results (default: {SHIPPED_DEFAULT})")
    a = ap.parse_args()

    def abspath(p):
        return p if os.path.isabs(p) else os.path.join(ROOT, p)

    RERUN = abspath(a.rerun_dir)
    OUT_MD = os.path.join(RERUN, "camera_ready_diff.md")
    if a.baseline == "shipped":
        return do_shipped(abspath(a.shipped_dir), RERUN)
    return do_paper()


if __name__ == "__main__":
    sys.exit(main())
