#!/usr/bin/env bash
# ── 清理 start.sh 遗留的本地进程；可选清理板端 demo 服务 ──
# 用法: bash cleanup.sh [--restart] [--remote|--all]
#   默认: 清理本机 server.py / cockpit / 本机 ML-KEM daemon，并关闭 USRP persistent TX/RX
#   --remote: 额外通过 SSH 清理板端 tcp_server.py 与 USRP292x 控制进程
#   --all: 等价于 --remote
#   --restart: 清理后自动重新启动本机 server.py（后台）
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$REPO_ROOT/.start_sh_pids"
VENV="$REPO_ROOT/.venv/bin/activate"
SERVER_PY="$REPO_ROOT/Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/server.py"
DEFAULT_REMOTE_USRP_RX_DIR="/home/user/cockpit_usrp_rx"
DEFAULT_RX_CONTROL_HOST="${REMOTE_HOST:-${PHYTIUM_PI_HOST:-100.121.87.73}}"
DEFAULT_REMOTE_RX_SSH_TARGET="${REMOTE_USER:-${PHYTIUM_PI_USER:-user}}@${DEFAULT_RX_CONTROL_HOST}"
DEFAULT_LOCAL_USRP_LATENT_DIR=""
for _candidate in \
    "$REPO_ROOT/host_pic_to_latent/encoder_outputs_airfield300" \
    "$REPO_ROOT/host_pic_to_latent/encoder_outputs" \
    "$REPO_ROOT/artifacts/host_pic_to_latent_300_smoke/encoder_outputs" \
    "$REPO_ROOT/artifacts/host_pic_to_latent_smoke/encoder_outputs"; do
    if [ -z "$DEFAULT_LOCAL_USRP_LATENT_DIR" ] && find "$_candidate" -maxdepth 1 \( -name '*.npz' -o -name '*.pt' \) -print -quit 2>/dev/null | grep -q .; then
        DEFAULT_LOCAL_USRP_LATENT_DIR="$_candidate"
    fi
done
unset _candidate
DEFAULT_MLKEM_REMOTE_PYTHON="/home/user/anaconda3/envs/mlkem/bin/python"
API_BASE="${START_SH_API_BASE:-http://127.0.0.1:8079}"
G='\033[0;32m'; Y='\033[0;33m'; R='\033[0;31m'; N='\033[0m'

DO_RESTART=false
DO_REMOTE=false
for arg in "$@"; do
    case "$arg" in
        --restart)
            DO_RESTART=true
            ;;
        --remote|--all)
            DO_REMOTE=true
            ;;
        "")
            ;;
        *)
            echo -e "${R}[错误] 不支持的参数: $arg${N}"
            echo "用法: bash cleanup.sh [--restart] [--remote|--all]"
            exit 2
            ;;
    esac
done

killed=0

kill_pid() {
    local pid="$1"
    local label="$2"
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        echo -e "${Y}[清理] 杀 ${label} (PID: $pid)${N}"
        kill "$pid" 2>/dev/null || true
        killed=$((killed + 1))
    fi
}

stop_usrp_control_via_api() {
    if ! command -v curl >/dev/null 2>&1; then
        return 0
    fi
    local payload
    echo -e "${Y}[清理] 尝试通过后端接口关闭 USRP persistent TX/RX ...${N}"
    payload="$(curl --connect-timeout 2 --max-time 5 -fsS -X POST -H 'Content-Type: application/json' -d '{}' "${API_BASE%/}/api/usrp-control/stop" 2>/dev/null || true)"
    if [ -n "$payload" ]; then
        printf '%s\n' "$payload"
    else
        echo -e "${Y}[跳过] 后端接口关闭 USRP 无响应，继续执行本地/强制清理${N}"
    fi
}

stop_local_usrp_control_fallback() {
    if [ -x "$REPO_ROOT/.venv/bin/python" ]; then
        echo -e "${Y}[清理] 尝试本地关闭 TX persistent server ...${N}"
        timeout 3 "$REPO_ROOT/.venv/bin/python" "$REPO_ROOT/USRP292x/OtaTxControl.py" \
            --host "${TX_CONTROL_HOST:-127.0.0.1}" \
            --port "${TX_CONTROL_PORT:-29221}" \
            quit >/dev/null 2>&1 || true
    fi
}

remote_cleanup() {
    local host="${REMOTE_HOST:-${PHYTIUM_PI_HOST:-100.121.87.73}}"
    local user="${REMOTE_USER:-${PHYTIUM_PI_USER:-user}}"
    local port="${REMOTE_SSH_PORT:-${PHYTIUM_PI_PORT:-22}}"
    local password="${REMOTE_PASS:-${PHYTIUM_PI_PASSWORD:-}}"

    if [ -z "$password" ]; then
        echo -e "${Y}[跳过] 未设置 REMOTE_PASS/PHYTIUM_PI_PASSWORD，不清理板端进程${N}"
        return 0
    fi
    if ! command -v sshpass >/dev/null 2>&1; then
        echo -e "${Y}[跳过] 未检测到 sshpass，不清理板端进程${N}"
        return 0
    fi

    echo -e "${Y}[清理] 板端 demo 服务: ${user}@${host}:${port}${N}"
    (
        unset LD_LIBRARY_PATH
        timeout 12 env SSHPASS="$password" sshpass -e ssh \
            -o StrictHostKeyChecking=no \
            -o UserKnownHostsFile=/dev/null \
            -o ConnectTimeout=6 \
            -p "$port" \
            "$user@$host" \
            'set -e
             pkill -f "[t]cp_server.py" 2>/dev/null || true
             pkill -f "[O]taRxControl.py|[O]taTxControl.py|[O]taRxPersistentServer|[O]taTxPersistentServer|[Q]pskFileDecode|[Q]pskFileLink.py|[R]unQpskFileBatchSpoolArq.py" 2>/dev/null || true
             echo "remote demo processes cleaned"
            '
    ) || {
            echo -e "${Y}[警告] 板端清理命令未成功完成${N}"
            return 0
        }
}

# 0. 优先通过仍在运行的后端接口优雅关闭 USRP persistent TX/RX
stop_usrp_control_via_api
stop_local_usrp_control_fallback

# 1. 从 PID 文件读取 start.sh 启动的 server.py PID
if [ -f "$PID_FILE" ]; then
    SERVER_PID=$(sed -n 's/^server=//p' "$PID_FILE" | head -1)
    if [ -z "$SERVER_PID" ]; then
        SERVER_PID=$(head -1 "$PID_FILE" | awk '{print $1}')
    fi
    kill_pid "$SERVER_PID" "server.py"
    rm -f "$PID_FILE"
fi

# 2. 兜底：pgrep 扫描可能残留的 server.py
for pid in $(pgrep -f "openamp_control_plane_demo/server.py" 2>/dev/null || true); do
    kill_pid "$pid" "残留 server.py"
done

# 3. 清理 server.py 拉起的 daemon 子进程（tcp_client --daemon）
for pid in $(pgrep -af "tcp_client.*--daemon" 2>/dev/null | grep -v grep | awk '{print $1}'); do
    kill_pid "$pid" "ML-KEM daemon"
done

# 4. 清理本地 USRP runner 子进程
for pid in $(pgrep -af "RunQpskFileBatchSpoolArq.py|OtaRxControl.py|OtaTxControl.py|QpskFileLink.py|QpskFileDecode" 2>/dev/null | grep -v grep | awk '{print $1}'); do
    kill_pid "$pid" "本地 USRP runner"
done

# 5. 清理 electron / vite 残留
for pid in $(pgrep -af "electron-vite|cockpit_desktop" 2>/dev/null | grep -v grep | awk '{print $1}'); do
    kill_pid "$pid" "electron"
done

# 6. 可选清理板端服务
if $DO_REMOTE; then
    remote_cleanup
fi

# 7. 等待退出
if [ "$killed" -gt 0 ]; then
    sleep 1
    # 强杀还在的
    for pid in $(pgrep -f "openamp_control_plane_demo/server.py|tcp_client.*--daemon|RunQpskFileBatchSpoolArq.py|OtaRxControl.py|OtaTxControl.py|QpskFileLink.py|QpskFileDecode|electron-vite|cockpit_desktop" 2>/dev/null || true); do
        echo -e "${R}[清理] 强杀 (PID: $pid)${N}"
        kill -9 "$pid" 2>/dev/null || true
    done
    echo -e "${G}[OK] 已清理 $killed 个进程${N}"
else
    echo -e "${G}[OK] 无残留进程${N}"
fi

# 8. 可选：重新启动 server.py
if $DO_RESTART; then
    if [ ! -f "$VENV" ]; then
        echo -e "${R}[错误] venv 不存在: $VENV${N}"
        exit 1
    fi
    source "$VENV"
    OQS_INSTALL_PATH="$REPO_ROOT/liboqs-dist"
    if [ ! -d "$OQS_INSTALL_PATH" ] && [ -d "$REPO_ROOT/liboqs/liboqs-dist" ]; then
        OQS_INSTALL_PATH="$REPO_ROOT/liboqs/liboqs-dist"
    fi
    export OQS_INSTALL_PATH
    TONGSUO_SIG_BRIDGE="$REPO_ROOT/tongsuo-dist/lib64/libtongsuo_sig_bridge.so"
    if [ ! -f "$TONGSUO_SIG_BRIDGE" ] && [ -f "$REPO_ROOT/tongsuo-dist/tongsuo/lib/libtongsuo_sig_bridge.so" ]; then
        TONGSUO_SIG_BRIDGE="$REPO_ROOT/tongsuo-dist/tongsuo/lib/libtongsuo_sig_bridge.so"
    fi
    TONGSUO_KEM_BRIDGE="$REPO_ROOT/tongsuo-dist/lib64/libtongsuo_kem_bridge.so"
    if [ ! -f "$TONGSUO_KEM_BRIDGE" ] && [ -f "$REPO_ROOT/tongsuo-dist/tongsuo/lib/libtongsuo_kem_bridge.so" ]; then
        TONGSUO_KEM_BRIDGE="$REPO_ROOT/tongsuo-dist/tongsuo/lib/libtongsuo_kem_bridge.so"
    fi
    AUTH_PEER_DIR="$REPO_ROOT/artifacts/mlkem_auth/peer"
    if [ -f "$TONGSUO_KEM_BRIDGE" ]; then
        export TONGSUO_KEM_BRIDGE="${TONGSUO_KEM_BRIDGE:-$TONGSUO_KEM_BRIDGE}"
        export MLKEM_LOCAL_TONGSUO_KEM_BRIDGE="${MLKEM_LOCAL_TONGSUO_KEM_BRIDGE:-$TONGSUO_KEM_BRIDGE}"
    fi
    if [ -f "$TONGSUO_SIG_BRIDGE" ]; then
        export TONGSUO_SIG_BRIDGE="${TONGSUO_SIG_BRIDGE:-$TONGSUO_SIG_BRIDGE}"
        export MLKEM_LOCAL_TONGSUO_SIG_BRIDGE="${MLKEM_LOCAL_TONGSUO_SIG_BRIDGE:-$TONGSUO_SIG_BRIDGE}"
    fi
    if [ -d "$REPO_ROOT/tongsuo-dist/lib64" ]; then
        export MLKEM_LOCAL_LD_LIBRARY_PATH="${MLKEM_LOCAL_LD_LIBRARY_PATH:-$REPO_ROOT/tongsuo-dist/lib64:$OQS_INSTALL_PATH/lib64:$OQS_INSTALL_PATH/lib}"
    fi
    if [ -f "$AUTH_PEER_DIR/server_sm2_identity.pub" ]; then
        export MLKEM_AUTH_PEER_SM2_PUB="${MLKEM_AUTH_PEER_SM2_PUB:-$AUTH_PEER_DIR/server_sm2_identity.pub}"
    fi
    if [ -f "$AUTH_PEER_DIR/server_mldsa_identity.pub" ]; then
        export MLKEM_AUTH_PEER_MLDSA_PUB="${MLKEM_AUTH_PEER_MLDSA_PUB:-$AUTH_PEER_DIR/server_mldsa_identity.pub}"
    fi
    export MLKEM_AUTH_ENABLED="${MLKEM_AUTH_ENABLED:-1}"
    export MLKEM_AUTH_SERVER_ID="${MLKEM_AUTH_SERVER_ID:-phytium-board}"
    export MLKEM_AUTH_SIG_POLICY="${MLKEM_AUTH_SIG_POLICY:-DUAL_REQUIRED}"
    export MLKEM_STATUS_PORT="${MLKEM_STATUS_PORT:-8080}"
    export MLKEM_REMOTE_PYTHON="${MLKEM_REMOTE_PYTHON:-$DEFAULT_MLKEM_REMOTE_PYTHON}"
    export MLKEM_REMOTE_OQS_INSTALL_PATH="${MLKEM_REMOTE_OQS_INSTALL_PATH:-/home/user/liboqs-dist}"
    export MLKEM_REMOTE_LD_LIBRARY_PATH="${MLKEM_REMOTE_LD_LIBRARY_PATH:-/home/user/liboqs-dist/lib}"
    export MLKEM_REMOTE_TONGSUO_SIG_BRIDGE="${MLKEM_REMOTE_TONGSUO_SIG_BRIDGE:-/home/user/libtongsuo_sig_bridge.so}"
    export MLKEM_REMOTE_TONGSUO_KEM_BRIDGE="${MLKEM_REMOTE_TONGSUO_KEM_BRIDGE:-/usr/local/tongsuo/lib/libtongsuo_kem_bridge.so}"
    export MLKEM_REMOTE_RUN_LOGGER_DIR="${MLKEM_REMOTE_RUN_LOGGER_DIR:-/home/user/artifacts/evidence/logs}"
    export MLKEM_AUTH_SERVER_SM2_KEY="${MLKEM_AUTH_SERVER_SM2_KEY:-/home/user/keys/server_sm2_identity.key}"
    export MLKEM_AUTH_SERVER_SM2_PUB="${MLKEM_AUTH_SERVER_SM2_PUB:-/home/user/keys/server_sm2_identity.pub}"
    export MLKEM_AUTH_SERVER_MLDSA_KEY="${MLKEM_AUTH_SERVER_MLDSA_KEY:-/home/user/keys/server_mldsa_identity.key}"
    export MLKEM_AUTH_SERVER_MLDSA_PUB="${MLKEM_AUTH_SERVER_MLDSA_PUB:-/home/user/keys/server_mldsa_identity.pub}"
    export REMOTE_USRP_RX_DIR="${REMOTE_USRP_RX_DIR:-$DEFAULT_REMOTE_USRP_RX_DIR}"
    export RX_CONTROL_HOST="${RX_CONTROL_HOST:-$DEFAULT_RX_CONTROL_HOST}"
    export RX_CONTROL_PORT="${RX_CONTROL_PORT:-29220}"
    export TX_CONTROL_HOST="${TX_CONTROL_HOST:-127.0.0.1}"
    export TX_CONTROL_PORT="${TX_CONTROL_PORT:-29221}"
    export RX_CAPTURE_MODE="${RX_CAPTURE_MODE:-remote-decode}"
    export REMOTE_RX_SSH_TARGET="${REMOTE_RX_SSH_TARGET:-$DEFAULT_REMOTE_RX_SSH_TARGET}"
    export REMOTE_RX_RUN_ROOT="${REMOTE_RX_RUN_ROOT:-/tmp/usrp292x_remote_runs}"
    export REMOTE_USRP_PROJECT_ROOT="${REMOTE_USRP_PROJECT_ROOT:-/home/user}"
    export USRP_AUTO_START_CONTROL="${USRP_AUTO_START_CONTROL:-0}"
    export BATCH_SIZE="${BATCH_SIZE:-6}"
    export BATCH_DECODE_WORKERS="${BATCH_DECODE_WORKERS:-2}"
    export USRP_WIRE_PREPARE_WORKERS="${USRP_WIRE_PREPARE_WORKERS:-2}"
    export USRP_WIRE_CACHE_ENABLED="${USRP_WIRE_CACHE_ENABLED:-1}"
    export OPENAMP_DEMO_USRP_SHUTDOWN_AFTER_TRANSPORT="${OPENAMP_DEMO_USRP_SHUTDOWN_AFTER_TRANSPORT:-0}"
    export OPENAMP_DEMO_INPUT_SOURCE_MODE="${OPENAMP_DEMO_INPUT_SOURCE_MODE:-prerecorded}"
    if [ -n "$DEFAULT_LOCAL_USRP_LATENT_DIR" ]; then
        export OPENAMP_DEMO_LOCAL_LATENT_DIR="${OPENAMP_DEMO_LOCAL_LATENT_DIR:-$DEFAULT_LOCAL_USRP_LATENT_DIR}"
    fi
    if [ -d "$REPO_ROOT/host_pic_to_latent/airfield300" ]; then
        export OPENAMP_DEMO_LOCAL_IMAGE_DIR="${OPENAMP_DEMO_LOCAL_IMAGE_DIR:-$REPO_ROOT/host_pic_to_latent/airfield300}"
    elif [ -d "$REPO_ROOT/host_pic_to_latent/airfield" ]; then
        export OPENAMP_DEMO_LOCAL_IMAGE_DIR="${OPENAMP_DEMO_LOCAL_IMAGE_DIR:-$REPO_ROOT/host_pic_to_latent/airfield}"
    fi
    export MLKEM_LOCAL_REPO_ROOT="${MLKEM_LOCAL_REPO_ROOT:-$REPO_ROOT}"
    unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
    cd "$REPO_ROOT"
    echo -e "${G}[INFO] 重启 server.py ...${N}"
    python "$SERVER_PY" &
    NEW_PID=$!
    {
        echo "server=$NEW_PID"
        echo "launcher=$$"
    } > "$PID_FILE"
    echo -e "${G}[OK] server.py 已重启 (PID: $NEW_PID)${N}"
    echo -e "${G}[INFO] 主 demo USRP RX 目录: ${REMOTE_USRP_RX_DIR}${N}"
    echo -e "${G}[INFO] 主 demo USRP 控制端: RX ${RX_CONTROL_HOST}:${RX_CONTROL_PORT}, TX ${TX_CONTROL_HOST}:${TX_CONTROL_PORT}, capture=${RX_CAPTURE_MODE}${N}"
    echo -e "${G}[INFO] 主 demo USRP batch size: ${BATCH_SIZE}${N}"
    echo -e "${G}[INFO] 主 demo USRP decode workers: ${BATCH_DECODE_WORKERS}${N}"
    echo -e "${G}[INFO] 主 demo USRP wire prepare: workers=${USRP_WIRE_PREPARE_WORKERS}, cache=${USRP_WIRE_CACHE_ENABLED}${N}"
    echo -e "${G}[INFO] 主 demo USRP 控制策略: 会话级常驻，cleanup.sh 统一关闭${N}"
    echo -e "${G}[INFO] 主 demo 输入源模式: ${OPENAMP_DEMO_INPUT_SOURCE_MODE}${N}"
    if [ -n "${OPENAMP_DEMO_LOCAL_LATENT_DIR:-}" ]; then
        echo -e "${G}[INFO] 主 demo 本机 latent 目录: ${OPENAMP_DEMO_LOCAL_LATENT_DIR}${N}"
    fi
    if [ -n "${OPENAMP_DEMO_LOCAL_IMAGE_DIR:-}" ]; then
        echo -e "${G}[INFO] 主 demo 本机图片目录: ${OPENAMP_DEMO_LOCAL_IMAGE_DIR}${N}"
    fi
    echo -e "${G}[INFO] 板端 ML-KEM 状态端口: ${MLKEM_STATUS_PORT}${N}"
fi
