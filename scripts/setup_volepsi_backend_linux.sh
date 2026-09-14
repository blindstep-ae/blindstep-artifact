#!/usr/bin/env bash
# scripts/setup_volepsi_backend_linux.sh
# Target: Linux x86_64 servers (Ubuntu/Debian)

set -e

PROJECT_ROOT=$(pwd)
EXT_DIR="$PROJECT_ROOT/external_backend"
VOLEPSI_DIR="$EXT_DIR/volepsi"

echo "======================================"
echo " VolePSI Build Script (Linux x86_64)  "
echo "======================================"

echo "[+] Checking critical toolchain existence..."
for cmd in cmake python3 clang++ git ninja; do
    if ! command -v $cmd &> /dev/null; then
        echo "[ERROR] Missing command: $cmd"
        echo "Please execute: sudo apt install build-essential cmake ninja-build git python3 clang g++ libssl-dev"
        exit 1
    fi
done
echo "[+] Toolchain verification passed."

# 1. Directory Checks
mkdir -p "$EXT_DIR"
cd "$EXT_DIR"

# 2. Repository Sync
if [ ! -d "volepsi" ]; then
    echo "[+] Cloning VolePSI..."
    git clone https://github.com/Visa-Research/volepsi.git
else
    echo "[!] VolePSI directory exists. Syncing updates..."
fi

cd volepsi

# 3. Submodule Sync
echo "[+] Updating submodules..."
git submodule update --init --recursive

# 4. Compilation Phases
echo "[+] Starting C++ Environment Configuration (build.py --setup)..."
if ! python3 build.py --setup; then
    echo "[FAIL] The backend dependency setup phase failed!"
    exit 1
fi

echo "[+] Starting Main Build Pipeline (build.py)..."
if ! python3 build.py; then
    echo "[FAIL] VolePSI failed to compile. Please check the logs above."
    exit 1
fi

echo "[+] Build finished with Exit 0. Attempting to locate executable..."
find . -type f -executable | grep -E "frontend|volepsi|vole-psi" || echo "[WARNING] Could not locate output binaries despite exit 0."

echo "======================================"
echo " Linux Build Pipeline Completed       "
echo "======================================"
