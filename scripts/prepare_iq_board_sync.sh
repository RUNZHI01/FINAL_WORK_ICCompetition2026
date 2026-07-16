#!/bin/bash
# 准备 IQ 直传所需的板端文件包（仅打包，不推送）。
#
# 真机实测前需要把 IQ runner + 测试套件 + 现代口径 test_model.py 同步到板端。
# 本脚本在容器内 /workspace 下打包所需文件到 /tmp/iq_board_sync.tar.gz，
# 然后用户可以用运行时输入的 SSHPASS 手工 scp 到板端解压（解压脚本见末尾注释）。
#
# 用法（容器内）：
#   bash /workspace/scripts/prepare_iq_board_sync.sh
#
# 输出：
#   /tmp/iq_board_sync.tar.gz
#   /tmp/iq_board_sync_manifest.txt

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/workspace}"
OUT_TAR="${OUT_TAR:-/tmp/iq_board_sync.tar.gz}"
OUT_MANIFEST="${OUT_MANIFEST:-/tmp/iq_board_sync_manifest.txt}"

if [ ! -f "$REPO_ROOT/USRP292x/RunAnalogLatentBatch.py" ]; then
    echo "ERROR: $REPO_ROOT/USRP292x/RunAnalogLatentBatch.py 不存在" >&2
    exit 1
fi

# 备用源（容器内 /workspace 可能只有部分文件，bind-mount 在 /repo 下有完整源）
ALT_ROOTS=("${ALT_ROOTS:-/repo/FINAL_WORK_ICCompetition2026}")

# 待同步文件清单（相对 REPO_ROOT）
FILES=(
    # IQ 直传 runner + PHY + 测试
    "USRP292x/RunAnalogLatentBatch.py"
    "USRP292x/AnalogLatentLink.py"
    "USRP292x/test_analog_latent_link.py"
    "USRP292x/OtaRxPersistentServer.cpp"
    "USRP292x/OtaRxPersistentServer.sh"
    "USRP292x/OtaTxPersistentServer.cpp"
    "USRP292x/OtaTxPersistentServer.sh"
    "USRP292x/BuildOtaTools.sh"
    # 现代口径 encoder（带 raw 'latent' 字段）
    "host_pic_to_latent/jscc/src/test_model.py"
    # 推理辅助 + wire blob 辅助（板端可能已有，覆盖以确保最新）
    "scripts/tvm_inference_helper.py"
    "scripts/latent_transport.py"
)

# 解析文件实际路径：先查 REPO_ROOT，找不到就查 ALT_ROOTS
resolve_source() {
    local rel="$1"
    if [ -f "$REPO_ROOT/$rel" ]; then
        echo "$REPO_ROOT/$rel"
        return 0
    fi
    for alt in "${ALT_ROOTS[@]}"; do
        if [ -f "$alt/$rel" ]; then
            echo "$alt/$rel"
            return 0
        fi
    done
    return 1
}

# 校验所有源文件存在
echo "[1/3] checking source files..."
declare -A RESOLVED
for rel in "${FILES[@]}"; do
    src=$(resolve_source "$rel") || {
        echo "MISSING: $rel (searched $REPO_ROOT + ${ALT_ROOTS[*]})" >&2
        exit 1
    }
    RESOLVED["$rel"]="$src"
done
echo "  all ${#FILES[@]} files present"

# 打包（保留相对路径）
echo "[2/3] writing tarball..."
tmp_stage="$(mktemp -d)"
trap 'rm -rf "$tmp_stage"' EXIT
mkdir -p "$tmp_stage/stage"
for rel in "${FILES[@]}"; do
    src="${RESOLVED[$rel]}"
    mkdir -p "$tmp_stage/stage/$(dirname "$rel")"
    cp "$src" "$tmp_stage/stage/$rel"
done
tar -czf "$OUT_TAR" -C "$tmp_stage/stage" .

# 写 manifest
echo "[3/3] writing manifest..."
{
    echo "# IQ 直传板端同步清单"
    echo "# 生成时间: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "# 源: $REPO_ROOT (fallback: ${ALT_ROOTS[*]})"
    echo "# 包: $OUT_TAR"
    echo ""
    echo "## 文件列表（${#FILES[@]} 个）"
    for rel in "${FILES[@]}"; do
        src="${RESOLVED[$rel]}"
        size=$(stat -c '%s' "$src")
        echo "  $rel  ($size bytes)  ← $src"
    done
    echo ""
    echo "## 板端目标路径"
    echo "  /home/user/USRP292x/RunAnalogLatentBatch.py"
    echo "  /home/user/USRP292x/AnalogLatentLink.py"
    echo "  /home/user/USRP292x/test_analog_latent_link.py"
    echo "  /home/user/USRP292x/OtaRxPersistentServer.cpp"
    echo "  /home/user/USRP292x/OtaRxPersistentServer.sh"
    echo "  /home/user/USRP292x/OtaTxPersistentServer.cpp"
    echo "  /home/user/USRP292x/OtaTxPersistentServer.sh"
    echo "  /home/user/USRP292x/BuildOtaTools.sh"
    echo "  /home/user/host_pic_to_latent/jscc/src/test_model.py  (新建)"
    echo "  /home/user/tvm_inference_helper.py  (覆盖)"
    echo "  /home/user/latent_transport.py  (覆盖)"
    echo ""
    echo "## 板端解压命令（用户授权后执行）"
    echo "  read -rsp 'Board SSH password: ' SSHPASS; echo; export SSHPASS"
    echo "  sshpass -e scp -O $OUT_TAR user@100.121.87.73:/tmp/"
    echo "  sshpass -e ssh user@100.121.87.73 \\"
    echo "    'cd /home/user && tar -xzf /tmp/iq_board_sync.tar.gz \\"
    echo "       --transform=\"s|^USRP292x/|USRP292x/|;s|^host_pic_to_latent/jscc/src/|host_pic_to_latent/jscc/src/|;s|^scripts/||\" \\"
    echo "       USRP292x/RunAnalogLatentBatch.py USRP292x/AnalogLatentLink.py USRP292x/test_analog_latent_link.py \\"
    echo "       USRP292x/OtaRxPersistentServer.cpp USRP292x/OtaRxPersistentServer.sh \\"
    echo "       USRP292x/OtaTxPersistentServer.cpp USRP292x/OtaTxPersistentServer.sh USRP292x/BuildOtaTools.sh \\"
    echo "       host_pic_to_latent/jscc/src/test_model.py \\"
    echo "       scripts/tvm_inference_helper.py scripts/latent_transport.py'"
    echo ""
    echo "## 同步后板端验证（在板端执行）"
    echo "  cd /home/user/USRP292x"
    echo "  source /home/user/anaconda3/etc/profile.d/conda.sh"
    echo "  conda activate tvm310_safe"
    echo "  python -m pytest test_analog_latent_link.py -v"
    echo "  python /home/user/USRP292x/RunAnalogLatentBatch.py --help | head -3"
    echo "  OTA_TARGETS='OtaRxPersistentServer OtaTxPersistentServer' bash BuildOtaTools.sh"
} > "$OUT_MANIFEST"

echo ""
echo "OK: tar=$OUT_TAR manifest=$OUT_MANIFEST"
echo "Manifest 内容："
cat "$OUT_MANIFEST"
