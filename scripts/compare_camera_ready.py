#!/usr/bin/env python3
"""
scripts/compare_camera_ready.py

Compare camera-ready rerun measurements (results/camera_ready_rerun/, produced
by rerun_camera_ready.sh on the v2 branch) against the published
numbers (data/paper_published_numbers.json, extracted from the accepted PDF).

Emits results/camera_ready_rerun/camera_ready_diff.md — one section per table,
old vs new vs delta, with per-table caveats (trial counts, definitions).
Tables whose rerun CSV is missing are listed as "not re-measured yet".

Deterministic columns (communication MB, rounds, static preprocessing counts)
are expected to shift by the small constant cost of the security-alignment changes
(one secure comparison, N_F multiplications, K exact truncations).
Timing columns additionally carry machine noise: judge them by relative delta.

Usage:  python3 scripts/compare_camera_ready.py
"""
import csv
import json
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RERUN = os.path.join(ROOT, "results", "camera_ready_rerun")
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
def parse_t8_raw():
    """Parse t8_preprocessing_raw.txt: handles 'inf' and 'loose edabits' forms."""
    import re
    p = os.path.join(RERUN, "t8_preprocessing_raw.txt")
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


def main():
    os.makedirs(RERUN, exist_ok=True)
    MD.append("# Camera-ready cost diff — v2 vs published\n")
    MD.append(f"Rerun dir: `results/camera_ready_rerun/` · Paper baseline: `data/paper_published_numbers.json`\n")
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


if __name__ == "__main__":
    sys.exit(main())
