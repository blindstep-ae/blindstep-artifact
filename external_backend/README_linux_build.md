# VolePSI Linux Build Instructions

**Target Environment:** Ubuntu 20.04/22.04 LTS (x86_64) or Debian equivalent.

## 1. Server Dependencies

Operating VolePSI natively demands a complete, standard C++ cryptographic compilation stack. Ensure the node has these global packages via APT:

```bash
sudo apt update
sudo apt install -y build-essential cmake ninja-build git python3 \
    clang g++ libssl-dev autoconf libtool pkg-config
```

## 2. Integration Script Execution

For full automation of the clone + submodule sync + python setup loop, we recommend simply running our centralized shell script:

```bash
bash scripts/setup_volepsi_backend_linux.sh
```

## 3. Manual Clone & Build Commands

If you elect to build manually without the helper wrapper:

```bash
# 1. Clone with submodules
git clone --recursive https://github.com/Visa-Research/volepsi.git external_backend/volepsi
cd external_backend/volepsi

# 2. Let the Python wrapper handle CMake & ThirdParty downloads
python3 build.py --setup
python3 build.py
```

## 4. Expected Output Artifacts

Upon a successful 0-error exit code from the builder, the final C++ output binaries and linked `.a`/`.so` library files will normally manifest under:
- `external_backend/volepsi/out/build/linux/frontend/frontend` (or similar depending on your build dir e.g., `linux` vs `osx` vs `ubuntu`)

This `frontend` executable file proves the foundation for moving into the Phase B smoke-testing and Phase C custom data integration layer.
