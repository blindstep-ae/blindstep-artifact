# VolePSI external backend Build Documentation

**Source Repo:** https://github.com/Visa-Research/volepsi.git
**Path:** `external_backend/volepsi`

## Required Toolchain
- **cmake** (3.15+): Mandatory for VolePSI and libOTe. 
- **compiler**: Clang++ (macOS default) or G++.
- **ninja/make**: Build systems.
- **Python 3**: Used by VolePSI's `build.py` wrapper.

## Current Environment Status
- **OS**: macOS (Darwin)
- **cmake**: **Locally injected via `.bin` directory download** (System-wide missing)
- **clang++**: Found
- **make**: Found
- **ninja**: Not Found
- **python3**: Found
- **git**: Found

## Build Instructions
1. Clone the repository: `git clone --recursive https://github.com/Visa-Research/volepsi.git`
2. Run setup: `python3 build.py --setup`
3. Build: `python3 build.py`

## Current Status
**Local Workaround Applied**: 本地 Mac 环境缺少了 `cmake`，我们已通过下载 CMake 预编译包放置在 `.bin/` 目录下临时补齐了局部构建工具链，使得 `setup_volepsi_backend.sh` 脚本得以向深测试。不过由于 macOS ARM 架构及缺失配套工具的深层问题，探针在构建核心组件 `libOTe` 时，仍然遭遇了硬链接断层（`make: *** No rule to make target Makefile.` / `libOTe Build failed (2)`），导致本地编译仍然中断。

**【服务器部署与 git pull 关键提醒】**：
未来在服务端（Linux 机器如 Ubuntu/Debian）上 `git pull` 后准备重启开发线时，服务器运维人员**必须**在全系统空间安装以下工具：
```bash
sudo apt update
sudo apt install -y build-essential cmake libssl-dev python3 git ninja-build
```
绝不可以直接依赖 macOS 环境带走的局部 `.bin` 补丁，只有保证 Linux 工作站上的 C++ 原生构建环境全量就绪，VolePSI 的原装代码才能成功走过 `build.py`。
