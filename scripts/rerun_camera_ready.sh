#!/usr/bin/env bash
# scripts/rerun_camera_ready.sh
# -------------------------------------------------------------------
# Camera-ready cost re-measurement on the v2 branch.
# Reproduces the measurements behind the paper's cost tables so they can
# be diffed against the published numbers (see compare_camera_ready.py).
#
# Stages (LAN set runs by default; WAN stages must be named explicitly):
#   t4      Table 4  : 6 variants, N=256, 5 trials, per-phase breakdown
#   t5      Table 5/12: N sweep {128,512,2048,8192} x 6 variants, 5 trials
#   t8      Table 8  : compile-time preprocessing estimates (from t4 logs)
#   t13     Table 13 : M_max sweep {1,2,3,5,10} on H-Queue, 3 trials
#   t14     Table 14 : Module 1 density sweep {0,10,50,90}%, single runs
#             (OPTIONAL: needs the real VolePSI frontend, WITH_VOLEPSI=1 install;
#              not in the default set)
#   wan6    Table 6  : 6 variants, N=256, 100ms RTT, 3 trials  (~long; hours)
#   rtt     Table 15 : B-Queue/H-Sort at 25+50ms RTT, 3 trials (~1-2 h)
#   wan2048 Table 16 : B-Queue/H-Sort, N=2048, 100ms RTT, 3 trials (LONGEST;
#                      published totals suggest many hours — run overnight)
#   WAN stages inject tc netem on lo themselves (sudo needed) and always
#   clean it up on exit; interrupted stages resume at trial granularity.
#
# Usage:
#   export MPSPDZ_DIR=/path/to/MP-SPDZ
#   bash scripts/rerun_camera_ready.sh              # LAN set: t4 t5 t8 t13
#   bash scripts/rerun_camera_ready.sh t14          # density sweep (frontend required)
#   bash scripts/rerun_camera_ready.sh t4 t8        # just these stages
#   bash scripts/rerun_camera_ready.sh wan6         # WAN main table (needs netem)
#   bash scripts/rerun_camera_ready.sh --force t4   # redo a completed stage
#
# Output: results/camera_ready_rerun/*.csv (+ per-run .txt logs).
# Completed stages leave a .done_<stage> stamp and are skipped on re-run,
# so an interrupted invocation resumes where it stopped.
# -------------------------------------------------------------------
set -uo pipefail

MPSPDZ_DIR="${MPSPDZ_DIR:?Set MPSPDZ_DIR to your MP-SPDZ checkout, e.g. export MPSPDZ_DIR=\$HOME/MP-SPDZ}"
export LD_LIBRARY_PATH="${MPSPDZ_DIR}:${MPSPDZ_DIR}/local/lib:${LD_LIBRARY_PATH:-}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${PROJECT_ROOT}/results/camera_ready_rerun"
SRC_DST="${MPSPDZ_DIR}/Programs/Source"
PDATA="${MPSPDZ_DIR}/Player-Data"
FRONTEND="${PROJECT_ROOT}/external_backend/volepsi/out/build/linux/frontend/frontend"
mkdir -p "$OUT" "$PDATA"

REV=$(git -C "$PROJECT_ROOT" rev-parse --short HEAD)
TS() { date -u +%Y-%m-%dT%H:%M:%SZ; }
say() { echo "[$(TS)] $*"; }

declare -A VARIANT_MAP=(
    ["hybrid_queue"]="blindstep_full"
    ["hybrid_partial_select"]="baseline_hybrid_partial_select"
    ["hybrid_batcher_sort"]="baseline_hybrid_batcher_sort"
    ["ab_queue"]="blindstep_full_ab_queue"
    ["ab_partial_select"]="blindstep_full_ab_partial_select"
    ["ab_batcher_sort"]="baseline_ab_batcher_sort"
)
VARIANTS=(hybrid_queue hybrid_partial_select hybrid_batcher_sort ab_queue ab_partial_select ab_batcher_sort)
CSV_HDR="variant,N,m_max,trial,P1_s,P2_s,P3_s,total_s,global_MB,rounds,rev,timestamp"

safe_cp() { [ -e "$2" ] && [ "$1" -ef "$2" ] && return 0; cp "$1" "$2"; }

sync_sources() {   # v2-side sources + shadow-copy sync (same logic as verify driver)
    local f d mod
    for f in "$PROJECT_ROOT"/mpc/*.mpc; do safe_cp "$f" "$SRC_DST/$(basename "$f")"; done
    for mod in module1_backend bs_core; do
        safe_cp "$PROJECT_ROOT/mpc/$mod.py" "$SRC_DST/$mod.py"
        for d in "$MPSPDZ_DIR" "$MPSPDZ_DIR/Compiler"; do
            [ -f "$d/$mod.py" ] && cp "$PROJECT_ROOT/mpc/$mod.py" "$d/$mod.py"
        done
        find "$MPSPDZ_DIR" -maxdepth 3 -path "*__pycache__/${mod}.*" -delete 2>/dev/null
    done
}

gen_shares() {     # $1 = N, $2 = M_MAX
    python3 "$PROJECT_ROOT/scripts/simulate_cpp_writer.py" \
        --n-f "$1" --m-max "$2" --data-dir "$PDATA" > /dev/null
}

make_stem() {      # $1 = base .mpc, $2 = stem, $3 = N, $4 = M_MAX  -> Programs/Source/<stem>.mpc
    sed -e "s/^N_F = .*/N_F = $3/" -e "s/^N_E = .*/N_E = $3/" -e "s/^N_MAX = .*/N_MAX = $3/" \
        -e "s/^M_MAX = .*/M_MAX = $4/" \
        "$PROJECT_ROOT/mpc/$1.mpc" > "$SRC_DST/$2.mpc"
}

compile_stem() {   # $1 = stem, $2 = logfile
    # PYTHONPATH so `import bs_core` / `import module1_backend` resolve on a fresh
    # MP-SPDZ tree (compile.py does not add Programs/Source to the import path).
    ( cd "$MPSPDZ_DIR" && PYTHONPATH="$SRC_DST:${PYTHONPATH:-}" ./compile.py -R 64 "$1" ) > "$2" 2>&1
}

parse_run() {      # $1 = runlog -> "P1,P2,P3,total,MB,rounds"
    local l="$1" t1 t2 t3 tt mb rd
    t1=$(grep -oE 'Time1 = [0-9.e-]+' "$l" | tail -1 | grep -oE '[0-9.e-]+$')
    t2=$(grep -oE 'Time2 = [0-9.e-]+' "$l" | tail -1 | grep -oE '[0-9.e-]+$')
    t3=$(grep -oE 'Time3 = [0-9.e-]+' "$l" | tail -1 | grep -oE '[0-9.e-]+$')
    tt=$(grep -oE 'Time = [0-9.e-]+'  "$l" | tail -1 | grep -oE '[0-9.e-]+$')
    mb=$(grep -oE 'Global data sent = [0-9.]+' "$l" | tail -1 | grep -oE '[0-9.]+$')
    rd=$(grep -oE '~?[0-9]+ rounds' "$l" | tail -1 | grep -oE '[0-9]+')
    echo "${t1:-NA},${t2:-NA},${t3:-NA},${tt:-NA},${mb:-NA},${rd:-NA}"
}

run_matrix() {     # $1 = csv, $2 = N, $3 = M_MAX, $4 = trials, $5 = tag, $6... = variants
    local csv="$1" N="$2" MM="$3" TRIALS="$4" TAG="$5"; shift 5
    gen_shares "$N" "$MM"
    for v in "$@"; do
        local base="${VARIANT_MAP[$v]}" stem
        stem="${base}_cr_${TAG}"
        make_stem "$base" "$stem" "$N" "$MM"
        say "compile ${stem} (N=$N M_MAX=$MM)"
        if ! compile_stem "$stem" "$OUT/compile_${stem}.txt"; then
            say "COMPILE FAIL ${stem} — recorded, skipping runs"
            echo "$v,$N,$MM,COMPILE_FAIL,NA,NA,NA,NA,NA,NA,$REV,$(TS)" >> "$csv"
            continue
        fi
        for t in $(seq 1 "$TRIALS"); do
            local rl="$OUT/run_${stem}_t${t}.txt"
            # trial-level resume: keep a completed log from an interrupted stage
            if [ -f "$rl" ] && grep -q 'Global data sent' "$rl" && grep -qE 'CSV|TOPK_CSV' "$rl"; then
                say "skip ${stem} trial $t (complete log exists)"
                grep -q ",$MM,$t," <<< "$(grep "^$v,$N," "$csv" 2>/dev/null)" \
                    || echo "$v,$N,$MM,$t,$(parse_run "$rl"),$REV,$(TS)" >> "$csv"
                continue
            fi
            say "run ${stem} trial $t/$TRIALS"
            ( cd "$MPSPDZ_DIR" && ./Scripts/semi2k.sh "$stem" ) > "$rl" 2>&1 || true
            if grep -qE 'CSV|TOPK_CSV' "$rl"; then
                echo "$v,$N,$MM,$t,$(parse_run "$rl"),$REV,$(TS)" >> "$csv"
            else
                say "RUN FAIL ${stem} t$t"
                echo "$v,$N,$MM,$t,RUN_FAIL,NA,NA,NA,NA,NA,$REV,$(TS)" >> "$csv"
            fi
        done
    done
}

stage_done() { [ -f "$OUT/.done_$1" ] && [ "$FORCE" != 1 ]; }
mark_done()  { touch "$OUT/.done_$1"; say "stage $1 complete"; }

# ------------------------------------------------------------------ stages --
stage_t4() {
    local csv="$OUT/t4_main_table.csv"
    echo "$CSV_HDR" > "$csv"
    run_matrix "$csv" 256 3 5 "n256" "${VARIANTS[@]}"
}

stage_t5() {
    local csv="$OUT/t5_nsweep.csv"
    echo "$CSV_HDR" > "$csv"
    for N in 128 512 2048 8192; do
        run_matrix "$csv" "$N" 3 5 "n${N}" "${VARIANTS[@]}"
    done
}

stage_t8() {
    local csv="$OUT/t8_preprocessing.csv" raw="$OUT/t8_preprocessing_raw.txt"
    echo "variant,integer_triples,edabits,bit_triples,rev" > "$csv"
    : > "$raw"
    for v in "${VARIANTS[@]}"; do
        local log="$OUT/compile_${VARIANT_MAP[$v]}_cr_n256.txt"
        [ -f "$log" ] || { say "t8: missing $log (run t4 first)"; return 1; }
        {
            echo "===== $v ====="
            sed -n '/Program requires at most/,$p' "$log"
            echo
        } >> "$raw"
        local it eb bt
        it=$(grep -oE '[0-9]+ integer triples' "$log" | tail -1 | grep -oE '^[0-9]+')
        eb=$(grep -oiE '[0-9]+ edabits' "$log" | tail -1 | grep -oE '^[0-9]+')
        bt=$(grep -oE '[0-9]+ bit triples' "$log" | tail -1 | grep -oE '^[0-9]+')
        echo "$v,${it:--},${eb:--},${bt:--},$REV" >> "$csv"
    done
}

stage_t13() {
    local csv="$OUT/t13_mmax.csv"
    echo "$CSV_HDR" > "$csv"
    for m in 1 2 3 5 10; do
        run_matrix "$csv" 256 "$m" 3 "m${m}" hybrid_queue
        # static P1-rounds estimate: module1-only program at this M_MAX
        make_stem blindstep_module1 "blindstep_module1_cr_m${m}" 256 "$m"
        compile_stem "blindstep_module1_cr_m${m}" "$OUT/compile_module1_m${m}.txt" || true
        vmr=$(grep -oE '[0-9]+ virtual machine rounds' "$OUT/compile_module1_m${m}.txt" | tail -1 | grep -oE '^[0-9]+')
        echo "module1_static,256,$m,vm_rounds,${vmr:-NA},NA,NA,NA,NA,NA,$REV,$(TS)" >> "$csv"
    done
}

stage_t14() {
    local csv="$OUT/t14_density.csv"
    [ -x "$FRONTEND" ] || { say "t14: frontend binary not found/executable at $FRONTEND — build volepsi first"; return 1; }
    echo "density_pct,P1a_ingress_s,P1b_agg_s,total_s,global_MB,rounds,rev,timestamp" > "$csv"
    make_stem blindstep_module1 "blindstep_module1_cr_n256" 256 3
    compile_stem "blindstep_module1_cr_n256" "$OUT/compile_module1_n256.txt" || { say "t14 compile FAIL"; return 1; }
    for d in 0 10 50 90; do
        say "t14 density ${d}%"
        ( cd "$(dirname "$FRONTEND")" && \
          BLINDSTEP_DATA_DIR="$PDATA" BLINDSTEP_M_MAX=3 BLINDSTEP_PSI_DENSITY="$d" \
          ./frontend -perf -cpsi -nn 8 ) > "$OUT/frontend_d${d}.txt" 2>&1
        local rl="$OUT/run_module1_d${d}.txt"
        ( cd "$MPSPDZ_DIR" && ./Scripts/semi2k.sh blindstep_module1_cr_n256 ) > "$rl" 2>&1 || true
        local t1 t11 tt mb rd
        t1=$(grep -oE 'Time1 = [0-9.e-]+' "$rl" | tail -1 | grep -oE '[0-9.e-]+$')
        t11=$(grep -oE 'Time11 = [0-9.e-]+' "$rl" | tail -1 | grep -oE '[0-9.e-]+$')
        tt=$(grep -oE 'Time = [0-9.e-]+' "$rl" | tail -1 | grep -oE '[0-9.e-]+$')
        mb=$(grep -oE 'Global data sent = [0-9.]+' "$rl" | tail -1 | grep -oE '[0-9.]+$')
        rd=$(grep -oE '~?[0-9]+ rounds' "$rl" | tail -1 | grep -oE '[0-9]+')
        echo "$d,${t1:-NA},${t11:-NA},${tt:-NA},${mb:-NA},${rd:-NA},$REV,$(TS)" >> "$csv"
    done
}

# WAN stages are self-contained (no delegation to the legacy scripts: those
# run pre-compiled stems whose bytecode may predate the v2 changes). Each stage
# injects tc netem on lo itself (needs sudo), compiles fresh _cr_ stems from
# the current sources via run_matrix, and always removes netem on exit.
# Paper WAN profile: 100 ms RTT, 100 Mbit/s => netem delay RTT/2 per pass.
NETEM_ON=0
wan_on() {   # $1 = RTT ms
    local half=$(( $1 / 2 ))
    sudo tc qdisc replace dev lo root netem delay "${half}ms" rate 100mbit \
        || { say "FATAL: could not inject netem (sudo tc failed)"; return 1; }
    tc qdisc show dev lo | grep -q netem || { say "FATAL: netem not active"; return 1; }
    NETEM_ON=1
    say "netem ON: RTT=$1 ms (delay ${half}ms/pass), 100mbit — load: $(uptime)"
}
wan_off() {
    [ "$NETEM_ON" = 1 ] && sudo tc qdisc del dev lo root 2>/dev/null
    NETEM_ON=0
    say "netem OFF"
}
trap 'wan_off' EXIT

stage_wan6() {
    local csv="$OUT/t6_wan.csv"
    [ -f "$csv" ] || echo "$CSV_HDR" > "$csv"
    sudo -v || return 1
    wan_on 100 || return 1
    run_matrix "$csv" 256 3 3 "wan100_n256" "${VARIANTS[@]}"
    wan_off
}

stage_rtt() {
    sudo -v || return 1
    local rtt csv
    for rtt in 25 50; do   # 100 ms rows of Table 15 come from Table 6 (wan6)
        csv="$OUT/t15_rtt${rtt}.csv"
        [ -f "$csv" ] || echo "$CSV_HDR" > "$csv"
        wan_on "$rtt" || return 1
        run_matrix "$csv" 256 3 3 "rtt${rtt}_n256" ab_queue hybrid_batcher_sort
        wan_off
    done
}

stage_wan2048() {
    local csv="$OUT/t16_wan2048.csv"
    [ -f "$csv" ] || echo "$CSV_HDR" > "$csv"
    sudo -v || return 1
    wan_on 100 || return 1
    run_matrix "$csv" 2048 3 3 "wan100_n2048" ab_queue hybrid_batcher_sort
    wan_off
}

# -------------------------------------------------------------------- main --
FORCE=0
STAGES=()
for a in "$@"; do
    case "$a" in
        --force) FORCE=1 ;;
        t4|t5|t8|t13|t14|wan6|rtt|wan2048) STAGES+=("$a") ;;
        *) echo "unknown arg: $a"; exit 2 ;;
    esac
done
[ ${#STAGES[@]} -eq 0 ] && STAGES=(t4 t5 t8 t13)

say "camera-ready rerun @ $REV — stages: ${STAGES[*]}"
sync_sources
FAILED=0
for s in "${STAGES[@]}"; do
    if stage_done "$s"; then say "stage $s already done (use --force to redo)"; continue; fi
    say "===== stage $s ====="
    if "stage_$s"; then mark_done "$s"; else say "stage $s FAILED"; FAILED=$((FAILED+1)); fi
done
say "done — ${FAILED} stage failure(s). Results in results/camera_ready_rerun/"
say "Push back with: git add -f results/camera_ready_rerun && git commit -m 'results: camera-ready rerun' && git push"
exit "$FAILED"
