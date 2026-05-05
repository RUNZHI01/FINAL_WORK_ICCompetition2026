#!/usr/bin/env bash
# dev.sh — Docker 开发环境入口
#
# 用法:
#   ./docker/dev.sh build              # 构建镜像
#   ./docker/dev.sh pytest mlkem_link/tests/ -v   # 跑测试
#   ./docker/dev.sh python scripts/demo_e2e.py    # 跑 demo
#   ./docker/dev.sh bash                # 进入容器 shell
#
# 队友只需: git clone + Semantic-Communication clone + ./docker/dev.sh build

set -euo pipefail

IMAGE_NAME="iccomp-dev"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ── 颜色 ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[dev]${NC} $*"; }
warn()  { echo -e "${YELLOW}[dev]${NC} $*"; }
error() { echo -e "${RED}[dev]${NC} $*"; exit 1; }

# ── build ──
cmd_build() {
    info "构建开发环境镜像: ${IMAGE_NAME}"
    docker build \
        -t "${IMAGE_NAME}" \
        -f "${SCRIPT_DIR}/dev.Dockerfile" \
        "${PROJECT_ROOT}"
    info "构建完成。运行 ./docker/dev.sh bash 进入容器"
}

# ── run ──
cmd_run() {
    # 检查镜像是否存在
    if ! docker image inspect "${IMAGE_NAME}" &>/dev/null; then
        warn "镜像 ${IMAGE_NAME} 不存在，先构建..."
        cmd_build
    fi

    # 检查 Semantic-Communication 子模块
    SC_DIR="${PROJECT_ROOT}/Semantic-Communication"
    if [ ! -f "${SC_DIR}/session_bootstrap/demo/openamp_control_plane_demo/server.py" ]; then
        warn "Semantic-Communication 子模块不完整（缺少 server.py）"
        warn "请手动 clone 并 checkout feat/ML-KEM 分支"
        warn "  cd Semantic-Communication && git clone <repo-url> . && git checkout feat/ML-KEM"
        warn "将继续启动容器，但部分功能可能不可用"
    fi

    # 确保挂载目录存在
    mkdir -p "${PROJECT_ROOT}/artifacts/evidence"

    # 自动检测 TTY
    if [ -t 0 ]; then TTY_FLAG="-it"; else TTY_FLAG="-i"; fi

    info "启动容器: ${IMAGE_NAME}"
    exec docker run --rm \
        ${TTY_FLAG} \
        -v "${PROJECT_ROOT}:/workspace" \
        -w /workspace \
        "${IMAGE_NAME}" \
        "$@"
}

# ── main ──
case "${1:-}" in
    build)
        cmd_build
        ;;
    *)
        cmd_run "$@"
        ;;
esac
