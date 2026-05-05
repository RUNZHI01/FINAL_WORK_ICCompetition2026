#!/usr/bin/env bash
# ── 一键启动：激活 venv → 杀旧进程 → 启 server.py + cockpit ──
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$REPO_ROOT/.venv/bin/activate"
SERVER_PY="$REPO_ROOT/Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/server.py"
COCKPIT_DIR="$REPO_ROOT/Semantic-Communication/cockpit_desktop"
OQS_INSTALL_PATH="$REPO_ROOT/liboqs-dist"
if [ ! -d "$OQS_INSTALL_PATH" ] && [ -d "$REPO_ROOT/liboqs/liboqs-dist" ]; then
    OQS_INSTALL_PATH="$REPO_ROOT/liboqs/liboqs-dist"
fi
TONGSUO_SIG_BRIDGE="$REPO_ROOT/tongsuo-dist/lib64/libtongsuo_sig_bridge.so"
if [ ! -f "$TONGSUO_SIG_BRIDGE" ] && [ -f "$REPO_ROOT/tongsuo-dist/tongsuo/lib/libtongsuo_sig_bridge.so" ]; then
    TONGSUO_SIG_BRIDGE="$REPO_ROOT/tongsuo-dist/tongsuo/lib/libtongsuo_sig_bridge.so"
fi
TONGSUO_KEM_BRIDGE="$REPO_ROOT/tongsuo-dist/lib64/libtongsuo_kem_bridge.so"
if [ ! -f "$TONGSUO_KEM_BRIDGE" ] && [ -f "$REPO_ROOT/tongsuo-dist/tongsuo/lib/libtongsuo_kem_bridge.so" ]; then
    TONGSUO_KEM_BRIDGE="$REPO_ROOT/tongsuo-dist/tongsuo/lib/libtongsuo_kem_bridge.so"
fi
PID_FILE="$REPO_ROOT/.start_sh_pids"
LOG_DIR="$REPO_ROOT/artifacts/logs"
ELECTRON_LOG_FILE="$LOG_DIR/cockpit_desktop_dev.log"
API_BASE="${START_SH_API_BASE:-http://127.0.0.1:8079}"
BOOTSTRAP_TIMEOUT_SEC="${START_SH_BOOTSTRAP_TIMEOUT_SEC:-30}"
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
AUTH_PEER_DIR="$REPO_ROOT/artifacts/mlkem_auth/peer"
DEFAULT_REMOTE_KEYS_DIR="/home/user/keys"
DEFAULT_MLKEM_REMOTE_PYTHON="/home/user/anaconda3/envs/mlkem/bin/python"

configure_local_crypto_env() {
    export OQS_INSTALL_PATH
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
}

# ── 清除系统代理，避免 localhost 请求被拦截导致 502 ──
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY

# ── 当前开发环境下 chrome-sandbox 未配置为 setuid，需关闭 Electron sandbox ──
ELECTRON_NO_SANDBOX_ARGS=(--no-sandbox --disable-setuid-sandbox)
export ELECTRON_DISABLE_SANDBOX=1
export COCKPIT_OPEN_DEVTOOLS="${COCKPIT_OPEN_DEVTOOLS:-0}"
export COCKPIT_UI_ZOOM="${COCKPIT_UI_ZOOM:-0.85}"
export MLKEM_AUTH_ENABLED="${MLKEM_AUTH_ENABLED:-1}"
export MLKEM_AUTH_SERVER_ID="${MLKEM_AUTH_SERVER_ID:-phytium-board}"
export MLKEM_AUTH_SIG_POLICY="${MLKEM_AUTH_SIG_POLICY:-DUAL_REQUIRED}"
export MLKEM_STATUS_PORT="${MLKEM_STATUS_PORT:-8080}"
export MLKEM_REMOTE_PYTHON="${MLKEM_REMOTE_PYTHON:-$DEFAULT_MLKEM_REMOTE_PYTHON}"
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
configure_local_crypto_env
if [ -f "$AUTH_PEER_DIR/server_sm2_identity.pub" ]; then
    export MLKEM_AUTH_PEER_SM2_PUB="${MLKEM_AUTH_PEER_SM2_PUB:-$AUTH_PEER_DIR/server_sm2_identity.pub}"
fi
if [ -f "$AUTH_PEER_DIR/server_mldsa_identity.pub" ]; then
    export MLKEM_AUTH_PEER_MLDSA_PUB="${MLKEM_AUTH_PEER_MLDSA_PUB:-$AUTH_PEER_DIR/server_mldsa_identity.pub}"
fi
export MLKEM_REMOTE_OQS_INSTALL_PATH="${MLKEM_REMOTE_OQS_INSTALL_PATH:-/home/user/liboqs-dist}"
export MLKEM_REMOTE_LD_LIBRARY_PATH="${MLKEM_REMOTE_LD_LIBRARY_PATH:-/home/user/liboqs-dist/lib}"
export MLKEM_REMOTE_TONGSUO_SIG_BRIDGE="${MLKEM_REMOTE_TONGSUO_SIG_BRIDGE:-/home/user/libtongsuo_sig_bridge.so}"
export MLKEM_REMOTE_TONGSUO_KEM_BRIDGE="${MLKEM_REMOTE_TONGSUO_KEM_BRIDGE:-/usr/local/tongsuo/lib/libtongsuo_kem_bridge.so}"
export MLKEM_REMOTE_RUN_LOGGER_DIR="${MLKEM_REMOTE_RUN_LOGGER_DIR:-/home/user/artifacts/evidence/logs}"
export MLKEM_AUTH_SERVER_SM2_KEY="${MLKEM_AUTH_SERVER_SM2_KEY:-$DEFAULT_REMOTE_KEYS_DIR/server_sm2_identity.key}"
export MLKEM_AUTH_SERVER_SM2_PUB="${MLKEM_AUTH_SERVER_SM2_PUB:-$DEFAULT_REMOTE_KEYS_DIR/server_sm2_identity.pub}"
export MLKEM_AUTH_SERVER_MLDSA_KEY="${MLKEM_AUTH_SERVER_MLDSA_KEY:-$DEFAULT_REMOTE_KEYS_DIR/server_mldsa_identity.key}"
export MLKEM_AUTH_SERVER_MLDSA_PUB="${MLKEM_AUTH_SERVER_MLDSA_PUB:-$DEFAULT_REMOTE_KEYS_DIR/server_mldsa_identity.pub}"

# ── 颜色 ──
G='\033[0;32m'; Y='\033[0;33m'; R='\033[0;31m'; N='\033[0m'

wait_for_local_demo() {
    python - <<'PY' "$API_BASE" "$BOOTSTRAP_TIMEOUT_SEC"
from __future__ import annotations
import json
import sys
import time
import urllib.request

base, timeout_sec = sys.argv[1:3]
deadline = time.monotonic() + float(timeout_sec)
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
request = urllib.request.Request(
    base.rstrip("/") + "/api/health",
    headers={"Accept": "application/json"},
    method="GET",
)

while time.monotonic() < deadline:
    try:
        with opener.open(request, timeout=2.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if str(payload.get("status") or "") == "ok":
            raise SystemExit(0)
    except Exception:
        time.sleep(0.5)

raise SystemExit(1)
PY
}

bootstrap_board_runtime() {
    local password="${REMOTE_PASS:-${PHYTIUM_PI_PASSWORD:-}}"
    if [ -z "$password" ]; then
        echo -e "${Y}[跳过] 未提供板卡密码，start.sh 仅启动上位机；板端服务可稍后在 Cockpit 中手动配置${N}"
        return 0
    fi

    if ! wait_for_local_demo; then
        echo -e "${Y}[警告] 本地 demo 后端未在 ${BOOTSTRAP_TIMEOUT_SEC}s 内就绪，跳过板端 auto-start${N}"
        return 1
    fi

    echo -e "${G}[INFO] 本地 demo 已就绪，开始同步板端会话并拉起板端服务 ...${N}"
    python - <<'PY' "$API_BASE"
from __future__ import annotations
import json
import os
import shlex
import shutil
import subprocess
import sys
import urllib.request

base = sys.argv[1].rstrip("/")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

def first_env(*keys: str) -> str:
    for key in keys:
        value = str(os.environ.get(key, "") or "").strip()
        if value:
            return value
    return ""

def request_json(method: str, path: str, payload: dict[str, object]) -> dict[str, object]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        base + path,
        data=data,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method=method,
    )
    with opener.open(request, timeout=12.0) as response:
        return json.loads(response.read().decode("utf-8"))

board_payload: dict[str, object] = {}
for field, keys in (
    ("host", ("REMOTE_HOST", "PHYTIUM_PI_HOST")),
    ("user", ("REMOTE_USER", "PHYTIUM_PI_USER")),
    ("port", ("REMOTE_SSH_PORT", "PHYTIUM_PI_PORT")),
):
    value = first_env(*keys)
    if value:
        board_payload[field] = value

password = first_env("REMOTE_PASS", "PHYTIUM_PI_PASSWORD")
if password:
    board_payload["password"] = password

board_result = request_json("POST", "/api/session/board-access", board_payload)
board_access = board_result.get("board_access") if isinstance(board_result, dict) else {}
remote_usrp_rx_dir = first_env("REMOTE_USRP_RX_DIR") or "/home/user/cockpit_usrp_rx"
usrp_rx_dir_result: dict[str, object] = {
    "status": "skipped",
    "remote_usrp_rx_dir": remote_usrp_rx_dir,
}
if isinstance(board_access, dict):
    host = str(board_access.get("host") or "").strip()
    user = str(board_access.get("user") or "").strip()
    port = str(board_access.get("port") or "22").strip() or "22"
    password = first_env("REMOTE_PASS", "PHYTIUM_PI_PASSWORD")
    if host and user and password and shutil.which("sshpass"):
        remote_cmd = (
            f"mkdir -p {shlex.quote(remote_usrp_rx_dir)} "
            f"&& chmod 700 {shlex.quote(remote_usrp_rx_dir)} "
            f"&& printf %s {shlex.quote(remote_usrp_rx_dir)}"
        )
        env = os.environ.copy()
        env["SSHPASS"] = password
        env.pop("LD_LIBRARY_PATH", None)
        proc = subprocess.run(
            [
                "sshpass",
                "-e",
                "ssh",
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "UserKnownHostsFile=/dev/null",
                "-p",
                port,
                f"{user}@{host}",
                remote_cmd,
            ],
            env=env,
            text=True,
            capture_output=True,
            timeout=12.0,
            check=False,
        )
        usrp_rx_dir_result = {
            "status": "ok" if proc.returncode == 0 else "error",
            "remote_usrp_rx_dir": remote_usrp_rx_dir,
            "message": (proc.stdout or proc.stderr or "").strip(),
        }
    elif host and user and password:
        usrp_rx_dir_result["message"] = "sshpass not available; skip remote mkdir"
try:
    openamp_result = request_json("POST", "/api/openamp-bringup", {})
except Exception as exc:
    openamp_result = {
        "status": "error",
        "message": f"openamp bring-up request failed: {exc}",
    }
try:
    usrp_control_result = request_json("POST", "/api/usrp-control/start", {})
except Exception as exc:
    usrp_control_result = {
        "status": "error",
        "message": f"usrp control start request failed: {exc}",
    }
crypto_result = request_json("POST", "/api/crypto-toggle", {"enabled": True})
print(
    json.dumps(
        {
            "board_access": board_result,
            "usrp_rx_dir": usrp_rx_dir_result,
            "openamp_bringup": openamp_result,
            "usrp_control": usrp_control_result,
            "crypto_toggle": crypto_result,
        },
        ensure_ascii=False,
    )
)
PY
}

start_remote_bootstrap_async() {
    (
        set +e
        bootstrap_board_runtime
    ) &
}

# ── 0. 询问板卡 SSH 密码（无回显） ──
echo -e "${Y}请输入飞腾派 SSH 密码（直接回车可跳过，跳过后需在 Cockpit 界面手动填写）:${N}"
read -r -s -p "  板卡密码: " _BOARD_PASS
echo  # 换行
if [ -n "$_BOARD_PASS" ]; then
    export REMOTE_PASS="$_BOARD_PASS"
    echo -e "${G}[OK] 板卡密码已记录，server.py 启动后将自动连接板端${N}"
else
    echo -e "${Y}[跳过] 未输入密码，请稍后在 Cockpit 界面「板卡连接」中填写${N}"
fi
unset _BOARD_PASS

# ── 1. 激活 venv ──
if [ ! -f "$VENV" ]; then
    echo -e "${R}[错误] venv 不存在: $VENV${N}"
    echo "请先运行: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi
source "$VENV"
configure_local_crypto_env
echo -e "${G}[OK] venv 已激活: $(python --version)${N}"
if [ "$MLKEM_AUTH_ENABLED" = "1" ]; then
    echo -e "${G}[INFO] 已启用 ML-DSA / SM2 认证握手 (${MLKEM_AUTH_SIG_POLICY})${N}"
    if [ ! -f "${MLKEM_AUTH_PEER_SM2_PUB:-}" ] || [ ! -f "${MLKEM_AUTH_PEER_MLDSA_PUB:-}" ]; then
        echo -e "${Y}[警告] 未找到板端认证公钥，建议先运行: ./init.sh --board${N}"
    fi
fi
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

# ── 2. 验证 SM4 可用 ──
if python -c "from cryptography.hazmat.primitives.ciphers.algorithms import SM4" 2>/dev/null; then
    echo -e "${G}[OK] SM4 可用 (cryptography $(python -c 'import cryptography; print(cryptography.__version__)'))${N}"
else
    echo -e "${Y}[警告] SM4 不可用，将使用 AES-256-GCM${N}"
fi

# ── 3. 杀旧的本地 demo 进程 ──
OLD_PIDS=$(pgrep -f "openamp_control_plane_demo/server.py" 2>/dev/null || true)
if [ -n "$OLD_PIDS" ]; then
    echo -e "${Y}[INFO] 杀旧 server.py (PID: $OLD_PIDS)${N}"
    kill $OLD_PIDS 2>/dev/null || true
    sleep 1
fi
for pid in $(pgrep -af "tcp_client.*--daemon|electron-vite|cockpit_desktop" 2>/dev/null | grep -v grep | awk '{print $1}'); do
    echo -e "${Y}[INFO] 杀旧本地 demo 子进程 (PID: $pid)${N}"
    kill "$pid" 2>/dev/null || true
done

# ── 4. 启动 server.py（后台）+ cockpit（前台） ──
echo -e "${G}[INFO] 启动 server.py ...${N}"
export OQS_INSTALL_PATH
cd "$REPO_ROOT"
mkdir -p "$LOG_DIR"

python "$SERVER_PY" &
SERVER_PID=$!
echo -e "${G}[OK] server.py PID=$SERVER_PID${N}"

# 记录 PID 供 cleanup.sh 使用
{
    echo "server=$SERVER_PID"
    echo "launcher=$$"
} > "$PID_FILE"
trap 'rm -f "$PID_FILE"' EXIT

start_remote_bootstrap_async

if [[ "${1:-}" == "--server-only" ]]; then
    # 纯 server 模式：保持 server 常驻，同时仍执行一次板端 auto-start 引导
    echo -e "${Y}提示: 默认同时启动 Cockpit，加 --server-only 仅启 server.py${N}"
    echo ""
    wait "$SERVER_PID"
else
    # 默认：后台 server + 前台 cockpit
    echo -e "${G}[INFO] 启动 cockpit_desktop ...${N}"
    echo -e "${G}[INFO] Electron 日志写入: ${ELECTRON_LOG_FILE}${N}"
    cd "$COCKPIT_DIR"
    : > "$ELECTRON_LOG_FILE"
    npx electron-vite dev -- "${ELECTRON_NO_SANDBOX_ARGS[@]}" >>"$ELECTRON_LOG_FILE" 2>&1
fi
