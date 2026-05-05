#!/usr/bin/env bash
# demo_one_click.sh — 一键启动 ML-KEM 安全语义通信演示
#
# 用法:
#   ./scripts/demo_one_click.sh                      # 本地模拟模式
#   ./scripts/demo_one_click.sh 100.121.87.73        # 真机模式
#
# 真机模式下会:
#   1. SSH 检查板卡可达性 + Tongsuo 环境
#   2. 在板卡上后台启动 tcp_server (TVM 推理模式)
#   3. 启动上位机 TUI 演示界面

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BOARD_USER="user"
BOARD_PORT=9527
SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=5"

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

ok()   { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
fail() { echo -e "${RED}[✗]${NC} $1"; exit 1; }
info() { echo -e "${CYAN[i]${NC} $1"; }

cleanup() {
    if [ -n "${BOARD_PID:-}" ]; then
        info "清理板卡 tcp_server (PID: $BOARD_PID)..."
        sshpass -p "$BOARD_USER" ssh $SSH_OPTS "$BOARD_USER@$BOARD_HOST" \
            "kill $BOARD_PID 2>/dev/null" || true
    fi
}
trap cleanup EXIT

# ── 参数 ──
BOARD_HOST="${1:-}"
MODE="sim"

if [ -n "$BOARD_HOST" ] && [ "$BOARD_HOST" != "127.0.0.1" ] && [ "$BOARD_HOST" != "localhost" ]; then
    MODE="board"
fi

cd "$PROJECT_DIR"

# 激活 .venv
if [ ! -d ".venv" ]; then
    fail ".venv 不存在，先运行: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
fi
source .venv/bin/activate

# 设置 liboqs 路径
export OQS_INSTALL_PATH="${OQS_INSTALL_PATH:-$PROJECT_DIR/liboqs-dist}"

echo "============================================================"
echo "  ML-KEM 安全语义通信 — 一键演示"
echo "============================================================"
echo ""

# ── 检查本地环境 ──
info "检查本地环境..."
python3 -c "from mlkem_link.kem import get_backend; b = get_backend('768'); print(f'KEM 后端: {b.name}')" || fail "mlkem_link 导入失败"
python3 -c "from textual.app import App" || fail "textual 未安装"
ok "本地环境就绪"

# ── 分模式 ──
if [ "$MODE" = "sim" ]; then
    echo ""
    info "模式: 本地模拟（无板卡）"
    echo ""
    ok "启动 TUI 演示界面..."
    echo "  操作提示:"
    echo "    c = 连接（自动启动本地模拟 server）"
    echo "    s = 发送测试数据"
    echo "    q = 退出"
    echo ""
    exec python3 scripts/demo_tui.py
fi

# ── 真机模式 ──
info "模式: 真机 ($BOARD_HOST)"
echo ""

# 检查 SSH 可达
info "检查板卡 SSH 连通性..."
sshpass -p "$BOARD_USER" ssh $SSH_OPTS "$BOARD_USER@$BOARD_HOST" "echo ok" &>/dev/null || fail "SSH 连接失败 ($BOARD_USER@$BOARD_HOST)"
ok "板卡可达"

# 检查板卡环境
info "检查板卡环境..."
BOARD_INFO=$(sshpass -p "$BOARD_USER" ssh $SSH_OPTS "$BOARD_USER@$BOARD_HOST" '
echo "===CHECK==="
# Tongsuo
test -f /usr/local/tongsuo/lib/libtongsuo_kem_bridge.so && echo "tongsuo:ok" || echo "tongsuo:missing"
# remoteproc
cat /sys/class/remoteproc/remoteproc0/state 2>/dev/null || echo "rproc:unknown"
# CPU
cat /sys/devices/system/cpu/offline 2>/dev/null || echo "cpu_off:?"
# conda mlkem
source ~/anaconda3/etc/profile.d/conda.sh 2>/dev/null && conda activate mlkem 2>/dev/null && python3 -c "from mlkem_link.kem import get_backend; print(\"kem:\" + get_backend(\"768\").name)" 2>/dev/null || echo "kem:failed"
# tcp_server 是否已在运行
ps aux | grep -c "[t]cp_server" || echo "tcp:0"
' 2>/dev/null)

TONGSUO=$(echo "$BOARD_INFO" | grep "tongsuo:" | cut -d: -f2)
RPROC=$(echo "$BOARD_INFO" | grep -v "tongsuo\|kem\|tcp\|cpu\|CHECK" | head -1)
KEM=$(echo "$BOARD_INFO" | grep "kem:" | cut -d: -f2)
TCP_COUNT=$(echo "$BOARD_INFO" | grep -oP "tcp:\K\d+" || echo "0")

[ "$TONGSUO" = "ok" ] && ok "Tongsuo 已安装" || fail "Tongsuo 未安装"
[ -n "$RPROC" ] && ok "RTOS 状态: $RPROC" || warn "无法读取 RTOS 状态"
[ -n "$KEM" ] && ok "KEM 后端: $KEM" || warn "板卡 mlkem_link 不可用"

# 启动板卡 tcp_server
if [ "$TCP_COUNT" != "0" ]; then
    warn "tcp_server 已在运行 ($TCP_COUNT 个)，跳过启动"
else
    info "在板卡上启动 tcp_server..."
    sshpass -p "$BOARD_USER" ssh $SSH_OPTS "$BOARD_USER@$BOARD_HOST" '
source ~/anaconda3/etc/profile.d/conda.sh
conda activate mlkem
export LD_LIBRARY_PATH="/usr/local/tongsuo/lib:$LD_LIBRARY_PATH"
export TONGSUO_KEM_BRIDGE="/usr/local/tongsuo/lib/libtongsuo_kem_bridge.so"
nohup python3 ~/tcp_server.py --tvm --host 0.0.0.0 --port '"$BOARD_PORT"' > /tmp/tcp_server.log 2>&1 &
echo $!
' | tail -1 > /tmp/board_tcp_pid
    BOARD_PID=$(cat /tmp/board_tcp_pid)
    info "tcp_server 已启动 (PID: $BOARD_PID)"
    sleep 1
    # 验证启动成功
    TCP_CHECK=$(sshpass -p "$BOARD_USER" ssh $SSH_OPTS "$BOARD_USER@$BOARD_HOST" "ps aux | grep -c '[t]cp_server'" 2>/dev/null || echo "0")
    [ "$TCP_CHECK" != "0" ] && ok "tcp_server 运行中" || fail "tcp_server 启动失败，检查 /tmp/tcp_server.log"
fi

echo ""
ok "启动 TUI 演示界面..."
echo "  操作提示:"
echo "    c = 连接到板卡"
echo "    s = 发送测试数据（真实 ML-KEM + TVM 推理）"
echo "    q = 退出"
echo ""
exec python3 scripts/demo_tui.py --host "$BOARD_HOST" --port "$BOARD_PORT"
