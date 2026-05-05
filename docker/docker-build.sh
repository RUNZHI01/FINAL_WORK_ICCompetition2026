#!/usr/bin/env bash
# 编译 Tongsuo 并拷贝产物到宿主机
#
# 用法：
#   ./docker/docker-build.sh          # 默认 x86_64
#   ./docker/docker-build.sh arm64    # 飞腾派交叉编译（需 QEMU binfmt）
#
# 产物输出到仓库根 ./tongsuo-dist/

set -euo pipefail

ARCH="${1:-amd64}"
IMAGE_NAME="tongsuo-build"
DIST_DIR="$(dirname "$0")/../tongsuo-dist"
TORCH_VERSION="${TORCH_VERSION:-2.6.0}"
INSTALL_TORCH="${INSTALL_TORCH:-1}"
BASE_IMAGE="${BASE_IMAGE:-ubuntu:22.04}"
UV_INSTALL_SCRIPT_URL="${UV_INSTALL_SCRIPT_URL:-https://astral.sh/uv/install.sh}"
UV_VERSION="${UV_VERSION:-0.6.14}"
BUILD_RETRIES="${BUILD_RETRIES:-3}"

echo "=== Tongsuo Docker Build ==="
echo "Architecture: ${ARCH}"
echo "Output: ${DIST_DIR}"
echo "Torch install: ${INSTALL_TORCH}"
echo "Torch version: ${TORCH_VERSION}"
echo "Base image: ${BASE_IMAGE}"
echo "UV installer: ${UV_INSTALL_SCRIPT_URL}"
echo "UV version: ${UV_VERSION}"
echo "Build retries: ${BUILD_RETRIES}"
echo ""

if ! [[ "$BUILD_RETRIES" =~ ^[0-9]+$ ]] || [[ "$BUILD_RETRIES" -lt 1 ]]; then
    echo "ERROR: BUILD_RETRIES must be a positive integer (got: ${BUILD_RETRIES})" >&2
    exit 1
fi

# 构建（默认重试 3 次，缓解 registry EOF 等临时网络故障）
build_ok=0
for attempt in $(seq 1 "$BUILD_RETRIES"); do
    echo "--- docker build attempt ${attempt}/${BUILD_RETRIES} ---"
    if docker build \
            --platform "linux/${ARCH}" \
            --build-arg "BASE_IMAGE=${BASE_IMAGE}" \
            --build-arg "UV_INSTALL_SCRIPT_URL=${UV_INSTALL_SCRIPT_URL}" \
            --build-arg "UV_VERSION=${UV_VERSION}" \
            --build-arg "ICCOMP_INSTALL_TORCH=${INSTALL_TORCH}" \
            --build-arg "ICCOMP_TORCH_VERSION=${TORCH_VERSION}" \
            -t "${IMAGE_NAME}:${ARCH}" \
            -f docker/Dockerfile \
            "$(dirname "$0")/.."; then
        build_ok=1
        break
    fi
    if [[ "$attempt" -lt "$BUILD_RETRIES" ]]; then
        echo "Build failed on attempt ${attempt}, retrying..."
    fi
done

if [[ "$build_ok" -ne 1 ]]; then
    echo "ERROR: docker build failed after ${BUILD_RETRIES} attempts." >&2
    echo "Hint: try a mirror, e.g." >&2
    echo "  BASE_IMAGE=docker.m.daocloud.io/library/ubuntu:22.04 UV_INSTALL_SCRIPT_URL=https://astral.sh/uv/install.sh ./docker/docker-build.sh ${ARCH}" >&2
    exit 1
fi

# 拷贝产物
rm -rf "${DIST_DIR}"
docker create --name tongsuo-export "${IMAGE_NAME}:${ARCH}" /bin/true
docker cp tongsuo-export:/usr/local/tongsuo "${DIST_DIR}"
docker rm tongsuo-export

echo ""
echo "=== 编译完成 ==="
echo "产物位置: ${DIST_DIR}"
echo ""
echo "验证："
echo "  LD_LIBRARY_PATH=${DIST_DIR}/lib64:\$LD_LIBRARY_PATH ${DIST_DIR}/bin/openssl version"
echo "  LD_LIBRARY_PATH=${DIST_DIR}/lib64:\$LD_LIBRARY_PATH ${DIST_DIR}/bin/openssl list -kem-algorithms"
