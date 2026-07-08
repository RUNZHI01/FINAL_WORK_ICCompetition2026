#!/usr/bin/env bash
# ===========================================================================
# 一次性初始化：从板端或本地拷贝 latent 到容器
#
# 用法:
#   # 从板端拉取预生成的 latent
#   bash scripts/init_usrp_data.sh board
#
#   # 从本地 Fedora 拷贝图片
#   bash scripts/init_usrp_data.sh local /path/to/images
#
#   # 从本地拷贝预生成的 NPZ latent
#   bash scripts/init_usrp_data.sh local-npz /path/to/*.npz
#
# 只需要执行一次。后续日常使用 start_all.sh。
# ===========================================================================

set -euo pipefail

SOURCE="${1:-board}"
SOURCE_PATH="${2:-}"
CONTAINER="iccomp-usrp-tx"
BOARD_IP="100.121.87.73"
BOARD_USER="user"
BOARD_PASS="user"
BOARD_LATENT_DIR="/home/user/Downloads/jscc-test/简化版latent"
DOCKER_LATENT_DIR="/workspace/Semantic-Communication/host_pic_to_latent/encoder_outputs_airfield300"

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'
ok()  { echo -e "${GREEN}[OK]${NC} $*"; }
fail(){ echo -e "${RED}[FAIL]${NC} $*"; exit 1; }

echo "============================================"
echo " USRP 数据初始化"
echo "============================================"

case "${SOURCE}" in
    board)
        echo "从板端拉取 latent: ${BOARD_LATENT_DIR}"
        LOCAL_LATENT_DIR="$(cd "$(dirname "$0")/.." && pwd)/usrp_latent_input"
        echo "本地暂存: ${LOCAL_LATENT_DIR}"
        echo ""

        # 1. SFTP 下载到本地
        python3 << PYEOF
import paramiko, os, sys

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('${BOARD_IP}', username='${BOARD_USER}', password='${BOARD_PASS}', timeout=15)
sftp = ssh.open_sftp()

remote = '${BOARD_LATENT_DIR}'
local = r'${LOCAL_LATENT_DIR}'
os.makedirs(local, exist_ok=True)

files = sorted(sftp.listdir(remote))
count = 0
for f in files:
    src = f'{remote}/{f}'
    dst = os.path.join(local, f)
    try:
        sftp.get(src, dst)
        count += 1
        if count % 60 == 0:
            print(f'  {count}/{len(files)}')
    except Exception as e:
        print(f'  SKIP {f}: {e}')

sftp.close()
ssh.close()
print(f'Downloaded {count}/{len(files)} files')
PYEOF

        # 2. Docker cp 到容器
        echo ""
        docker exec "${CONTAINER}" bash -c "mkdir -p ${DOCKER_LATENT_DIR}" 2>/dev/null
        docker cp "${LOCAL_LATENT_DIR}/." "${CONTAINER}:${DOCKER_LATENT_DIR}/"
        ok "已拷贝到容器: ${DOCKER_LATENT_DIR}"

        # 3. Verify
        COUNT=$(docker exec "${CONTAINER}" bash -c "ls ${DOCKER_LATENT_DIR}/*.pt ${DOCKER_LATENT_DIR}/*.npz 2>/dev/null | wc -l")
        ok "容器内 latent: ${COUNT} 个"
        ;;

    local)
        if [ -z "${SOURCE_PATH}" ] || [ ! -d "${SOURCE_PATH}" ]; then
            fail "请提供图片目录: bash scripts/init_usrp_data.sh local /path/to/images"
        fi
        echo "从本地拷贝图片: ${SOURCE_PATH} -> ${DOCKER_LATENT_DIR}"
        docker exec "${CONTAINER}" bash -c "mkdir -p ${DOCKER_LATENT_DIR}" 2>/dev/null
        docker cp "${SOURCE_PATH}/." "${CONTAINER}:${DOCKER_LATENT_DIR}/"
        COUNT=$(docker exec "${CONTAINER}" bash -c "ls ${DOCKER_LATENT_DIR}/*.png ${DOCKER_LATENT_DIR}/*.jpg 2>/dev/null | wc -l")
        ok "已拷贝 ${COUNT} 张图片到容器"
        ;;

    local-npz)
        if [ -z "${SOURCE_PATH}" ]; then
            fail "请提供 latent 目录: bash scripts/init_usrp_data.sh local-npz /path/to/*.npz"
        fi
        echo "从本地拷贝 NPZ: ${SOURCE_PATH} -> ${DOCKER_LATENT_DIR}"
        docker exec "${CONTAINER}" bash -c "mkdir -p ${DOCKER_LATENT_DIR}" 2>/dev/null
        for f in ${SOURCE_PATH}/*.npz; do
            [ -f "$f" ] || continue
            docker cp "$f" "${CONTAINER}:${DOCKER_LATENT_DIR}/"
        done
        COUNT=$(docker exec "${CONTAINER}" bash -c "ls ${DOCKER_LATENT_DIR}/*.npz 2>/dev/null | wc -l")
        ok "已拷贝 ${COUNT} 个 NPZ 到容器"
        ;;

    *)
        fail "未知数据源: ${SOURCE} (可选: board, local, local-npz)"
        ;;
esac

echo ""
echo "============================================"
echo " 初始化完成"
echo " 现在可以运行: bash scripts/start_all.sh usrp"
echo "============================================"
