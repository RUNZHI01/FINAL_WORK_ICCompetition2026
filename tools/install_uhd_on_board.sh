#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════
# 飞腾板端一键编译安装 UHD 4.6.0.0
#
# 用法:
#   bash tools/install_uhd_on_board.sh          # 默认完整安装
#   bash tools/install_uhd_on_board.sh --skip-deps  # 跳过 apt install
#   bash tools/install_uhd_on_board.sh --clean     # 安装前清理旧 build
#
# 目标环境: Ubuntu 20.04 + Linux 5.10 (aarch64)
# ══════════════════════════════════════════════════════════════════════

set -euo pipefail

UHD_VERSION="v4.6.0.0"
UHD_REPO="https://github.com/EttusResearch/uhd.git"
UHD_DIR="uhd"
BUILD_DIR="build"

SKIP_DEPS=false
CLEAN_BUILD=false

for arg in "$@"; do
    case "$arg" in
        --skip-deps) SKIP_DEPS=true ;;
        --clean)     CLEAN_BUILD=true ;;
        -h|--help)
            echo "用法: $0 [--skip-deps] [--clean]"
            echo "  --skip-deps   跳过 apt install 系统依赖"
            echo "  --clean       安装前清理旧 build 目录"
            exit 0
            ;;
        *)
            echo "未知参数: $arg"
            exit 1
            ;;
    esac
done

# ── 环境检查 ──

echo "═══════════════════════════════════════"
echo " UHD ${UHD_VERSION} 板端编译安装"
echo "═══════════════════════════════════════"

ARCH=$(uname -m)
if [ "$ARCH" != "aarch64" ]; then
    echo "[警告] 当前架构: ${ARCH}（本脚本目标为 aarch64）"
    echo "  如果你在 x86_64 主机上运行，请先 SSH 到飞腾板"
    echo "  用法: bash tools/install_uhd_on_board.sh"
    echo ""
    read -rp "确认继续在 ${ARCH} 上编译? [y/N] " confirm
    [ "$confirm" != "y" ] && [ "$confirm" != "Y" ] && exit 1
fi

echo "[信息] 架构: ${ARCH}"
echo "[信息] 内核: $(uname -r)"
echo "[信息] CPU 核数: $(nproc)"

# ── 安装系统依赖 ──

if [ "$SKIP_DEPS" = false ]; then
    echo ""
    echo "[1/4] 安装系统依赖..."
    sudo apt update
    sudo apt install -y \
        build-essential cmake git \
        libboost-all-dev \
        libusb-1.0-0-dev
    echo "[完成] 系统依赖安装完毕"
else
    echo ""
    echo "[1/4] 跳过系统依赖安装（--skip-deps）"
fi

# ── 下载 UHD 源码 ──

echo ""
echo "[2/4] 下载 UHD 源码 (${UHD_VERSION})..."

if [ -d "$UHD_DIR" ]; then
    echo "[信息] 目录 ${UHD_DIR} 已存在，跳过下载"
    cd "$UHD_DIR"
    CURRENT_BRANCH=$(git describe --tags 2>/dev/null || git rev-parse --short HEAD)
    echo "[信息] 当前版本: ${CURRENT_BRANCH}"
else
    git clone --depth 1 --branch "$UHD_VERSION" "$UHD_REPO" "$UHD_DIR"
    cd "$UHD_DIR"
fi

# ── 配置与编译 ──

if [ "$CLEAN_BUILD" = true ] && [ -d "$BUILD_DIR" ]; then
    echo ""
    echo "[信息] 清理旧 build 目录..."
    rm -rf "$BUILD_DIR"
fi

mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

echo ""
echo "[3/4] CMake 配置..."
cmake .. \
    -DCMAKE_INSTALL_PREFIX=/usr/local \
    -DENABLE_UTILS=ON \
    -DENABLE_EXAMPLES=ON \
    -DENABLE_TESTS=OFF \
    -DENABLE_MANUAL=OFF \
    -DENABLE_PYTHON_API=OFF

echo ""
echo "[3/4] 编译中... (-j$(nproc))"
make -j"$(nproc)"

# ── 安装 ──

echo ""
echo "[4/4] 安装到 /usr/local..."
sudo make install
sudo ldconfig

echo ""
echo "═══════════════════════════════════════"
echo " UHD ${UHD_VERSION} 安装完成"
echo "═══════════════════════════════════════"
echo ""
echo " 验证:"
echo "   uhd_config_info --version"
echo "   uhd_find_devices"
echo ""
echo " 下载 FPGA 固件镜像:"
echo "   sudo uhd_images_downloader"
echo ""
