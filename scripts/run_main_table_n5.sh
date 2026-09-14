#!/usr/bin/env bash
# scripts/run_main_table_n5.sh
# Supplemental runs for Main Table (N=5 trials)

set -euo pipefail

# --- Configuration & Paths ---
PROJECT_ROOT=$(pwd)
MPSPDZ_DIR="${MPSPDZ_DIR:?Set MPSPDZ_DIR to your MP-SPDZ checkout, e.g. export MPSPDZ_DIR=\$HOME/MP-SPDZ}"
VOLEPSI_DIR="${PROJECT_ROOT}/external_backend/volepsi"

LAN_RESULTS_DIR="${PROJECT_ROOT}/results/fullpipeline_repeat"
WAN_RESULTS_DIR="${PROJECT_ROOT}/results/wan_repeat"

LAN_CSV="${LAN_RESULTS_DIR}/summary.csv"
WAN_CSV="${WAN_RESULTS_DIR}/summary.csv"

# 6 Variants
declare -A VARIANT_MAP=(
    ["hybrid_queue"]="blindstep_full"
    ["hybrid_partial_select"]="baseline_hybrid_partial_select"
    ["hybrid_batcher_sort"]="baseline_hybrid_batcher_sort"
    ["ab_queue"]="blindstep_full_ab_queue"
    ["ab_partial_select"]="blindstep_full_ab_partial_select"
    ["ab_batcher_sort"]="baseline_ab_batcher_sort"
)
VARIANTS=("hybrid_queue" "hybrid_partial_select" "hybrid_batcher_sort" "ab_queue" "ab_partial_select" "ab_batcher_sort")

MODE=""
DRY_RUN=0

for arg in "$@"; do
    if [[ "$arg" == "--lan" ]]; then
        MODE="--lan"
    elif [[ "$arg" == "--wan" ]]; then
        MODE="--wan"
    elif [[ "$arg" == "--dry-run" ]]; then
        DRY_RUN=1
    fi
done

if [[ "$MODE" != "--lan" && "$MODE" != "--wan" ]]; then
    echo "Usage: $0 [--lan | --wan] [--dry-run]"
    echo "  --lan     : Run LAN N=256 (trials 4,5) and N=2048 (trials 1-5)"
    echo "  --wan     : Run WAN N=256 (trials 4,5). Please inject netem manually before running."
    echo "  --dry-run : Print commands without executing them."
    exit 1
fi

if [ "$DRY_RUN" = "1" ]; then
    echo "[!] DRY RUN MODE ENABLED - No actual execution will occur"
fi

export LD_LIBRARY_PATH="${MPSPDZ_DIR}/local/lib:${LD_LIBRARY_PATH:-}"
cd "${MPSPDZ_DIR}"

run_trials() {
    local N=$1
    local trial_start=$2
    local trial_end=$3
    local out_dir=$4
    local out_csv=$5
    local is_lan=$6
    
    if [ "$DRY_RUN" != "1" ]; then
        mkdir -p "${out_dir}"
        if [ ! -f "${out_csv}" ]; then
            echo "variant,trial,timer_m1_s,timer_m2_s,timer_m3_s,total_s,comm_MB,rounds,timestamp" > "${out_csv}"
        fi
    fi

    echo "=========================================================="
    echo " Running N=${N} from trial ${trial_start} to ${trial_end}"
    echo " Output DIR: ${out_dir}"
    echo "=========================================================="

    # Set parameters and compile
    for v in "${VARIANTS[@]}"; do
        base_stem="${VARIANT_MAP[$v]}"
        stem="${base_stem}"
        if [ "${N}" -ne 256 ]; then
            stem="${base_stem}_n${N}"
        else
            stem="${base_stem}"
        fi
        
        if [ "$DRY_RUN" != "1" ]; then
            # ALWAYS enforce N with sed, even for N=256, to protect against polluted base files
            sed -e "s/^N_F = .*/N_F = ${N}/" -e "s/^N_E = .*/N_E = ${N}/" -e "s/^N_MAX = .*/N_MAX = ${N}/" "${PROJECT_ROOT}/mpc/${base_stem}.mpc" > "${MPSPDZ_DIR}/Programs/Source/${stem}.mpc"
        else
            echo "[DRY-RUN] Would generate: ${MPSPDZ_DIR}/Programs/Source/${stem}.mpc with N=${N}"
        fi
        
        if [ "$DRY_RUN" = "1" ]; then
            echo "[DRY-RUN] Would run: ./compile.py -R 64 ${stem}"
        else
            ./compile.py -R 64 "${stem}"
        fi
    done

    # Run
    for trial in $(seq ${trial_start} ${trial_end}); do
        for v in "${VARIANTS[@]}"; do
            base_stem="${VARIANT_MAP[$v]}"
            stem="${base_stem}"
            
            # Use a variant suffix if N is not 256 to distinguish in CSV and use correct executable
            if [ "${N}" -ne 256 ]; then
                csv_variant="${v}_n${N}"
                stem="${base_stem}_n${N}"
            else
                csv_variant="${v}"
            fi
            
            log_file="${out_dir}/${csv_variant}_trial${trial}.log"
            ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
            
            echo "[+] Running ${csv_variant} Trial ${trial} ..."
            
            if [ "$DRY_RUN" = "1" ]; then
                echo "[DRY-RUN] Would run: ./Scripts/semi2k.sh ${stem}"
                continue
            fi
            
            ./Scripts/semi2k.sh "${stem}" 2>&1 | tee "${log_file}"
            
            RT=$(grep -oP "Time\s*=\s*\K[\d.]+" "${log_file}" | tail -1 || echo "0")
            CM=$(grep -oP "Global data sent\s*=\s*\K[\d.]+" "${log_file}" | tail -1 || echo "0")
            RD=$(grep -oP "in ~\K\d+(?=\s*rounds)" "${log_file}" | tail -1 || echo "0")
            T1=$(grep -oP "Time1\s*=\s*\K[\d.]+" "${log_file}" | tail -1 || echo "0")
            T2=$(grep -oP "Time2\s*=\s*\K[\d.]+" "${log_file}" | tail -1 || echo "0")
            T3=$(grep -oP "Time3\s*=\s*\K[\d.]+" "${log_file}" | tail -1 || echo "0")
            
            echo "${csv_variant},${trial},${T1},${T2},${T3},${RT},${CM},${RD},${ts}" >> "${out_csv}"
            echo "    Result: Total=${RT}s, Comm=${CM}MB, Rounds=${RD}"
        done
    done
}

if [[ "$MODE" == "--lan" ]]; then
    # LAN N=256 (Trials 4, 5)
    # Assumes share file for N=256 (nn=7 or 9) already exists correctly.
    run_trials 256 4 5 "${LAN_RESULTS_DIR}" "${LAN_CSV}" true

    # LAN N=2048 (Trials 1,2,3,4,5)
    echo "=========================================================="
    echo " Generating Share file for N=2048 (nn=11) ..."
    echo "=========================================================="
    
    if [ "$DRY_RUN" = "1" ]; then
        echo "[DRY-RUN] Would run: ./frontend -perf -cpsi -nn 11"
    else
        cd "${VOLEPSI_DIR}/out/build/linux/frontend" || exit 1
        export BLINDSTEP_DATA_DIR="${MPSPDZ_DIR}/Player-Data"
        export BLINDSTEP_M_MAX=3
        export BLINDSTEP_PSI_DENSITY=33
        export BLINDSTEP_INJECT_OVERFLOW=0
        ./frontend -perf -cpsi -nn 11 2>&1 | grep "Writer OK" || true
        cd "${MPSPDZ_DIR}"
        
        expected=18432
        actual=$(wc -l < "${MPSPDZ_DIR}/Player-Data/Input-P0-0")
        if [ "$actual" != "$expected" ]; then
          echo "ERROR: share file has $actual lines, expected $expected"
          exit 1
        fi
    fi
    
    run_trials 2048 1 5 "${LAN_RESULTS_DIR}" "${LAN_CSV}" true
fi

if [[ "$MODE" == "--wan" ]]; then
    # WAN N=256 (Trials 4, 5)
    echo "WARNING: Ensure you have MANUALLY injected netem before proceeding."
    
    echo "=========================================================="
    echo " Generating Share file for N=256 (nn=8) ..."
    echo "=========================================================="
    if [ "$DRY_RUN" = "1" ]; then
        echo "[DRY-RUN] Would run: ./frontend -perf -cpsi -nn 8"
    else
        cd "${VOLEPSI_DIR}/out/build/linux/frontend" || exit 1
        export BLINDSTEP_DATA_DIR="${MPSPDZ_DIR}/Player-Data"
        export BLINDSTEP_M_MAX=3
        export BLINDSTEP_PSI_DENSITY=33
        export BLINDSTEP_INJECT_OVERFLOW=0
        ./frontend -perf -cpsi -nn 8 2>&1 | grep "Writer OK" || true
        cd "${MPSPDZ_DIR}"
        
        expected=2304
        actual=$(wc -l < "${MPSPDZ_DIR}/Player-Data/Input-P0-0")
        if [ "$actual" != "$expected" ]; then
          echo "ERROR: share file has $actual lines, expected $expected"
          exit 1
        fi
    fi
    
    run_trials 256 4 5 "${WAN_RESULTS_DIR}" "${WAN_CSV}" false
fi

echo "[+] Done."
