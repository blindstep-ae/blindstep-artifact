#!/usr/bin/env bash
# scripts/install.sh
# -------------------------------------------------------------------
# One-shot installer for the BlindStep artifact on Ubuntu 22.04 (x86-64).
#
#   bash scripts/install.sh                 # MP-SPDZ (semi2k) + artifact sources
#   WITH_VOLEPSI=1 bash scripts/install.sh  # additionally build the CPSI frontend
#
# Environment:
#   MPSPDZ_DIR   where MP-SPDZ is (or will be) checked out   [default ~/MP-SPDZ]
#   MPSPDZ_REF   MP-SPDZ git ref to build                      [default: see below]
#   WITH_VOLEPSI 1 to build VolePSI + apply the BlindStep frontend patch
#
# Idempotent: re-running skips completed steps. Needs sudo for apt packages.
# -------------------------------------------------------------------
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MPSPDZ_DIR="${MPSPDZ_DIR:-$HOME/MP-SPDZ}"
MPSPDZ_REF="${MPSPDZ_REF:-58d2739ac251262c0bd6034f7fc7d0666a6b1e2c}"   # v0.4.2-13-g58d2739a: the build behind the shipped expected results
WITH_VOLEPSI="${WITH_VOLEPSI:-0}"
JOBS="$(nproc 2>/dev/null || echo 4)"

say() { echo "[install] $*"; }

# ---------------------------------------------------------------- 1. deps --
say "installing build dependencies (sudo apt-get)"
sudo apt-get update -y
sudo apt-get install -y \
    automake build-essential clang cmake git libboost-dev \
    libboost-filesystem-dev libboost-iostreams-dev libboost-thread-dev \
    libgmp-dev libntl-dev libsodium-dev libssl-dev libtool python3 \
    ninja-build autoconf pkg-config iproute2

# ------------------------------------------------------------- 2. MP-SPDZ --
if [ ! -d "$MPSPDZ_DIR/.git" ]; then
    say "cloning MP-SPDZ into $MPSPDZ_DIR (ref $MPSPDZ_REF)"
    git clone https://github.com/data61/MP-SPDZ "$MPSPDZ_DIR"
fi
git -C "$MPSPDZ_DIR" checkout -q "$MPSPDZ_REF"

# Ubuntu 22.04 ships Boost 1.74; MP-SPDZ 0.4.x needs >= 1.75. `make boost`
# downloads Boost, runs its bootstrap.sh/b2, and installs it under local/.
if ! ls "$MPSPDZ_DIR"/local/lib/libboost_filesystem.so* >/dev/null 2>&1; then
    say "building local Boost for MP-SPDZ (make boost; ~5-10 min)"
    ( cd "$MPSPDZ_DIR" && make -j"$JOBS" boost )
else
    say "local Boost already present — skipping"
fi

# Rebuild whenever the binary is missing OR was built from a different commit
# than the one just checked out (the exact commit is part of the
# reproducibility contract; a pre-existing binary from another commit must
# not be silently reused).
BUILT_MARK="$MPSPDZ_DIR/.blindstep_built_commit"
WANT_COMMIT="$(git -C "$MPSPDZ_DIR" rev-parse HEAD)"
if [ ! -x "$MPSPDZ_DIR/semi2k-party.x" ] || [ "$(cat "$BUILT_MARK" 2>/dev/null)" != "$WANT_COMMIT" ]; then
    say "building MP-SPDZ semi2k at $WANT_COMMIT (this takes a while)"
    ( cd "$MPSPDZ_DIR" && make -j"$JOBS" setup && make -j"$JOBS" semi2k-party.x )
    echo "$WANT_COMMIT" > "$BUILT_MARK"
else
    say "semi2k-party.x already built from $WANT_COMMIT — skipping"
fi

if [ ! -f "$MPSPDZ_DIR/Player-Data/P0.pem" ]; then
    say "generating player certificates"
    ( cd "$MPSPDZ_DIR" && Scripts/setup-ssl.sh 2 )
fi
mkdir -p "$MPSPDZ_DIR/Player-Data" "$MPSPDZ_DIR/Programs/Source"

# ---------------------------------------------------- 3. artifact sources --
say "installing artifact MPC sources into $MPSPDZ_DIR/Programs/Source"
cp "$ROOT"/mpc/*.mpc "$ROOT"/mpc/*.py "$MPSPDZ_DIR/Programs/Source/"

# ---------------------------------------------- 4. optional VolePSI frontend --
if [ "$WITH_VOLEPSI" = 1 ]; then
    VP="$ROOT/external_backend/volepsi"
    if [ ! -d "$VP/.git" ]; then
        say "cloning VolePSI (upstream ec76012)"
        git clone --recursive https://github.com/Visa-Research/volepsi.git "$VP"
    fi
    git -C "$VP" checkout -q ec76012
    git -C "$VP" submodule update --init --recursive
    if ! git -C "$VP" apply --check -R "$ROOT/patches/volepsi_blindstep_frontend_ec76012.patch" >/dev/null 2>&1; then
        say "applying BlindStep frontend patch"
        git -C "$VP" apply "$ROOT/patches/volepsi_blindstep_frontend_ec76012.patch"
    else
        say "frontend patch already applied"
    fi
    say "building VolePSI (python3 build.py --setup && python3 build.py)"
    ( cd "$VP" && python3 build.py --setup && python3 build.py )
    [ -x "$VP/out/build/linux/frontend/frontend" ] && say "frontend built OK" \
        || { say "ERROR: frontend binary not found after build"; exit 1; }
fi

# ------------------------------------------------------------ 5. smoke --
say "smoke: share-file alignment + reduced injectivity check"
python3 "$ROOT/scripts/check_share_alignment.py"
python3 "$ROOT/scripts/verify_key_encoding.py" --quick --samples 10000 | tail -1

cat <<EOF

[install] done.
  export MPSPDZ_DIR=$MPSPDZ_DIR
  bash scripts/verify_functional.sh              # functional verification (~1 h)
  bash scripts/rerun_camera_ready.sh             # LAN reproduction (2-4 h)
EOF
