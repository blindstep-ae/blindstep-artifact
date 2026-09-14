#!/usr/bin/env bash
# scripts/verify_functional.sh
# -------------------------------------------------------------------
# One-shot functional verification of the BlindStep artifact (v2).
# Runs, in order:
#   [S0] python module shadow check (stale bs_core/module1_backend copies)
#   [S1] compile smoke test for every program
#   [S2] cross-variant Top-K agreement: all six variants on one share file
#        must produce identical (rank, valid, score) rows          -> claim C1
#   [S3] overflow injection: fail-closed abort, no Top-K output     -> claim C2
#   [S4] bounded one-to-many aggregation: A[3]=321 A[6]=657 A[9]=139 -> C1
#   [S5] cost snapshot of blindstep_full (N=256)
#
# Usage:
#   export MPSPDZ_DIR=/path/to/MP-SPDZ
#   bash scripts/verify_functional.sh
#
# Logs land under results/functional_verify/; console output ends with a
# PASS/FAIL summary; exit code != 0 iff any step failed.
# -------------------------------------------------------------------
set -uo pipefail

MPSPDZ_DIR="${MPSPDZ_DIR:?Set MPSPDZ_DIR to your MP-SPDZ checkout, e.g. export MPSPDZ_DIR=\$HOME/MP-SPDZ}"
export LD_LIBRARY_PATH="${MPSPDZ_DIR}:${MPSPDZ_DIR}/local/lib:${LD_LIBRARY_PATH:-}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${PROJECT_ROOT}/results/functional_verify"
SUMMARY="${OUT}/SUMMARY.txt"
SRC_DST="${MPSPDZ_DIR}/Programs/Source"
PDATA="${MPSPDZ_DIR}/Player-Data"
mkdir -p "$OUT" "$PDATA"
: > "$SUMMARY"

FAILS=0
say()  { echo "$*" | tee -a "$SUMMARY"; }
pass() { say "PASS: $*"; }
fail() { say "FAIL: $*"; FAILS=$((FAILS + 1)); }
step() { say ""; say "==================== $* ===================="; }

[ -d "$SRC_DST" ] || { say "FATAL: $SRC_DST not found — is MPSPDZ_DIR correct?"; exit 2; }

REV=$(git -C "$PROJECT_ROOT" rev-parse --short HEAD 2>/dev/null || echo "no-git")
say "artifact rev (v2)  : ${REV}"
say "MPSPDZ_DIR         : ${MPSPDZ_DIR}"
say "output dir         : ${OUT}"

declare -A VARIANT_MAP=(
    ["hybrid_queue"]="blindstep_full"
    ["hybrid_partial_select"]="baseline_hybrid_partial_select"
    ["hybrid_batcher_sort"]="baseline_hybrid_batcher_sort"
    ["ab_queue"]="blindstep_full_ab_queue"
    ["ab_partial_select"]="blindstep_full_ab_partial_select"
    ["ab_batcher_sort"]="baseline_ab_batcher_sort"
)
VARIANTS=(hybrid_queue hybrid_partial_select hybrid_batcher_sort ab_queue ab_partial_select ab_batcher_sort)

safe_cp() {  # cp that tolerates symlinked-identical targets ("same file")
    [ -e "$2" ] && [ "$1" -ef "$2" ] && return 0
    cp "$1" "$2"
}

# ------------------------------------------------------------------
# Backend module synchronization.
# Programs/Source may not be the import winner: stale copies of
# module1_backend.py / bs_core.py higher up sys.path (MP-SPDZ root,
# Compiler/) shadow it. sync_backend copies the requested tree's modules
# to Programs/Source AND over every detected shadow copy, then clears
# their bytecode caches, so compile.py always sees exactly one version.
# ------------------------------------------------------------------
SHADOW_DIRS=""
detect_shadows() {
    local d probe
    for d in "$MPSPDZ_DIR" "$MPSPDZ_DIR/Compiler"; do
        if [ -f "$d/module1_backend.py" ] || [ -f "$d/bs_core.py" ]; then
            SHADOW_DIRS="$SHADOW_DIRS $d"
        fi
    done
    probe=$(cd "$MPSPDZ_DIR" && python3 -c \
        "import importlib.util as u; s=u.find_spec('module1_backend'); print(s.origin or '' if s else '')" 2>/dev/null)
    if [ -n "$probe" ] && [ -f "$probe" ]; then
        local pdir; pdir="$(cd "$(dirname "$probe")" && pwd)"
        case " $SHADOW_DIRS " in *" $pdir "*) ;; *)
            [ "$pdir" != "$(cd "$SRC_DST" && pwd)" ] && SHADOW_DIRS="$SHADOW_DIRS $pdir" ;;
        esac
    fi
    if [ -n "$SHADOW_DIRS" ]; then
        say "shadow module copies detected in:${SHADOW_DIRS} (kept in sync)"
    else
        say "no shadow module copies detected"
    fi
}

sync_backend() {  # $1 = source tree providing mpc/{module1_backend,bs_core}.py
    local mod d
    for mod in module1_backend bs_core; do
        safe_cp "$1/mpc/$mod.py" "$SRC_DST/$mod.py"
        for d in $SHADOW_DIRS; do
            cp "$1/mpc/$mod.py" "$d/$mod.py"
        done
        find "$MPSPDZ_DIR" -maxdepth 3 -path "*__pycache__/${mod}.*" -delete 2>/dev/null
    done
}

compile_one() {    # $1 = flag (-R/-B), $2 = program, $3 = logfile
    # PYTHONPATH: MP-SPDZ's compile.py does not put Programs/Source on the import
    # path, so `import bs_core` / `import module1_backend` only resolve if the
    # modules are reachable explicitly (a fresh MP-SPDZ tree has no shadow copies).
    ( cd "$MPSPDZ_DIR" && PYTHONPATH="$SRC_DST:${PYTHONPATH:-}" ./compile.py "$1" 64 "$2" ) > "$3" 2>&1
}

run_one() {        # $1 = program, $2 = logfile
    ( cd "$MPSPDZ_DIR" && ./Scripts/semi2k.sh "$1" ) > "$2" 2>&1
}

gen_shares() {     # $1..: extra env assignments, e.g. BLINDSTEP_INJECT_OVERFLOW=1
    env "$@" python3 "$PROJECT_ROOT/scripts/simulate_cpp_writer.py" --n-f 256 --m-max 3 \
        --data-dir "$PDATA" >> "$SUMMARY" 2>&1
}

rm -f "$OUT"/run_*.log "$OUT"/topk_*.csv "$OUT"/*_diff.txt   # never reuse a previous run's logs

# ==================================================================
step "S0: python module shadow check"
# ==================================================================
detect_shadows

# ==================================================================
step "S1: compile smoke test (all programs)"
# ==================================================================
for f in "$PROJECT_ROOT"/mpc/*.mpc; do safe_cp "$f" "$SRC_DST/$(basename "$f")"; done
sync_backend "$PROJECT_ROOT"

R64_PROGS="blindstep_full blindstep_module1 blindstep_module2 \
           blindstep_full_ab_queue blindstep_full_ab_partial_select \
           baseline_hybrid_queue baseline_hybrid_partial_select \
           baseline_hybrid_batcher_sort baseline_hybrid_batcher_sort_m2only \
           baseline_hybrid_sort baseline_ab_batcher_sort"
for p in $R64_PROGS; do
    if compile_one -R "$p" "$OUT/compile_${p}.log"; then
        pass "compile -R 64 $p"
    else
        fail "compile -R 64 $p (see results/functional_verify/compile_${p}.log)"
    fi
done
for p in baseline_ab_queue baseline_ab_sort; do   # pure-Boolean legacy pair
    if compile_one -B "$p" "$OUT/compile_${p}.log"; then
        pass "compile -B 64 $p"
    else
        fail "compile -B 64 $p (legacy mock program; see log)"
    fi
done

# ==================================================================
step "S2: cross-variant Top-K agreement (six variants, one share file)"
# ==================================================================
gen_shares
cp "$PDATA/Input-P0-0" "$OUT/shares-Input-P0-0"
cp "$PDATA/Input-P1-0" "$OUT/shares-Input-P1-0"
ref_csv=""
for v in "${VARIANTS[@]}"; do
    prog="${VARIANT_MAP[$v]}"
    cp "$OUT/shares-Input-P0-0" "$PDATA/Input-P0-0"
    cp "$OUT/shares-Input-P1-0" "$PDATA/Input-P1-0"
    run_one "$prog" "$OUT/run_${v}.log" || true
    grep '^TOPK_CSV' "$OUT/run_${v}.log" | cut -d, -f2,3,4 > "$OUT/topk_${v}.csv"
    if [ ! -s "$OUT/topk_${v}.csv" ]; then
        fail "S2: no TOPK_CSV output from $v (see run_${v}.log)"; continue
    fi
    if [ -z "$ref_csv" ]; then
        ref_csv="$OUT/topk_${v}.csv"; ref_v="$v"
        say "reference Top-K from $v:"; sed 's/^/    /' "$ref_csv" | tee -a "$SUMMARY"
    elif diff -q "$ref_csv" "$OUT/topk_${v}.csv" >/dev/null; then
        pass "S2: $v agrees with $ref_v"
    else
        diff -u "$ref_csv" "$OUT/topk_${v}.csv" > "$OUT/topk_${v}_diff.txt"
        fail "S2: $v differs from $ref_v (see topk_${v}_diff.txt)"
    fi
done

# ==================================================================
step "S3: overflow injection — fail-closed abort, no Top-K output"
# ==================================================================
gen_shares BLINDSTEP_INJECT_OVERFLOW=1
run_one blindstep_full "$OUT/run_overflow.log" || true       # crash() is expected
if ! grep -q '^===== BlindStep' "$OUT/run_overflow.log"; then
    fail "S3: program did not run (VM/env error — see run_overflow.log)"
fi
topk_n=$(grep -c '^TOPK_CSV' "$OUT/run_overflow.log" || true)
if grep -q 'FATAL.*[Oo]verflow' "$OUT/run_overflow.log"; then
    pass "S3: fail-closed abort message present"
else
    fail "S3: no fail-closed abort message (see run_overflow.log)"
fi
if [ "${topk_n:-0}" -eq 0 ]; then
    pass "S3: zero TOPK_CSV lines after abort"
else
    fail "S3: ${topk_n} TOPK_CSV lines released after overflow"
fi

# ==================================================================
step "S4: bounded one-to-many aggregation — A[3]=321, A[6]=657, A[9]=139"
# ==================================================================
gen_shares BLINDSTEP_F1_INJECT=1
run_one blindstep_module1 "$OUT/run_f1.log" || true
for want in "CSV,3,1,321" "CSV,6,1,657" "CSV,9,1,139"; do
    if grep -q "^${want}\$" "$OUT/run_f1.log"; then
        pass "S4: ${want}"
    else
        got=$(grep "^CSV,${want:4:1}," "$OUT/run_f1.log" | head -1)
        fail "S4: expected ${want}, got '${got:-<no row>}'"
    fi
done

# ==================================================================
step "S5: cost snapshot (blindstep_full, N=256, single LAN run)"
# ==================================================================
snap() {  # $1 = label, $2 = runlog
    local log="$2" t c r
    [ -f "$log" ] || { echo "$1,NA,NA,NA"; return; }
    t=$(grep -oE 'Time = [0-9.]+' "$log" | tail -1 | grep -oE '[0-9.]+')
    c=$(grep -oE 'Global data sent = [0-9.]+' "$log" | tail -1 | grep -oE '[0-9.]+' | tail -1)
    r=$(grep -oE '~?[0-9]+ rounds' "$log" | tail -1 | grep -oE '[0-9]+')
    echo "$1,${t:-NA},${c:-NA},${r:-NA}"
}
{
    echo "side,time_s,global_MB,rounds"
    snap v2 "$OUT/run_hybrid_queue.log"
} | tee "$OUT/cost_snapshot.csv" | column -t -s, | sed 's/^/    /' | tee -a "$SUMMARY"
say "    (indicative only; use rerun_camera_ready.sh for table numbers)"

# ==================================================================
step "RESULT"
# ==================================================================
if [ "$FAILS" -eq 0 ]; then
    say "ALL CHECKS PASSED  (v2=${REV})"
else
    say "${FAILS} CHECK(S) FAILED — details above and in results/functional_verify/"
fi
say "Summary saved to results/functional_verify/SUMMARY.txt"
exit "$FAILS"
