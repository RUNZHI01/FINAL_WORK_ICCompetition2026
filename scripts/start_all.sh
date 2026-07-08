#!/usr/bin/env bash
# ===========================================================================
# 一键启动脚本：USRP / 预录 模式全链路
#
# 用法:
#   预录模式:  bash scripts/start_all.sh
#   USRP 模式: bash scripts/start_all.sh usrp
#   USRP + 图库: bash scripts/start_all.sh usrp /path/to/images
#
# 前置条件:
#   - Docker Desktop 已启动
#   - Tailscale 已连接（板端 IP: 100.121.87.73）
#   - USRP 硬件上电
#
# 启动后打开 cockpit: http://localhost:5173
# ===========================================================================

set -euo pipefail

MODE="${1:-prerecorded}"
CONTAINER="iccomp-usrp-tx"
BOARD_IP="100.121.87.73"
BOARD_USER="user"
BOARD_PASS="user"
REPO="/workspace/Semantic-Communication"

# ── 颜色 ──
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'
ok()  { echo -e "${GREEN}[OK]${NC} $*"; }
warn(){ echo -e "${YELLOW}[WARN]${NC} $*"; }
fail(){ echo -e "${RED}[FAIL]${NC} $*"; }

echo "============================================"
echo " 全链路启动脚本 (mode=${MODE})"
echo "============================================"

# ── 1. 检查 Docker 容器 ──
echo ""
echo "--- 1. Docker 容器 ---"
if docker ps --filter "name=${CONTAINER}" --format "{{.ID}}" 2>/dev/null | grep -q .; then
    ok "容器 ${CONTAINER} 已运行"
else
    warn "容器未运行，正在启动..."
    docker start "${CONTAINER}" 2>/dev/null || {
        fail "无法启动容器，请检查 Docker Desktop"
        exit 1
    }
    sleep 3
    ok "容器已启动"
fi

# ── 2. 检查板端连通性 ──
echo ""
echo "--- 2. 板端连通性 ---"
python3 -c "
import socket
s = socket.socket()
s.settimeout(5)
try:
    s.connect(('${BOARD_IP}', 22))
    print('SSH OK')
    s.close()
except Exception as e:
    print(f'SSH FAIL: {e}')
    exit(1)
" || { fail "板端 SSH 不可达"; exit 1; }

python3 -c "
import socket
s = socket.socket()
s.settimeout(5)
try:
    s.connect(('${BOARD_IP}', 8080))
    s.close()
    print('status 8080 OK')
except Exception:
    print('status 8080 not ready (will start)')
"

# ── 3. 启动板端 tcp_server + TVM daemon ──
echo ""
echo "--- 3. 板端 tcp_server ---"
python3 << PYEOF
import paramiko, time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('${BOARD_IP}', username='${BOARD_USER}', password='${BOARD_PASS}', timeout=15, banner_timeout=15)

# Check existing
stdin, stdout, stderr = ssh.exec_command('pgrep -f tcp_server.py', timeout=5)
existing = stdout.read().decode().strip()

if existing:
    print(f'tcp_server already running: {existing}')
    # Check if it has daemon flag
    stdin, stdout, stderr = ssh.exec_command('pgrep -af tcp_server.py | grep -c "tvm-daemon"', timeout=5)
    daemon_count = stdout.read().decode().strip()
    if daemon_count == '0':
        print('tcp_server running WITHOUT daemon flag, restarting...')
        ssh.exec_command('sudo pkill -9 -f tcp_server.py', timeout=5)
        time.sleep(2)
        existing = ''
    else:
        print('daemon mode confirmed')

if not existing:
    print('Starting board tcp_server with daemon mode...')
    # Kill zombies
    ssh.exec_command('sudo pkill -9 -f tcp_server.py 2>/dev/null; sudo pkill -9 -f tvm_inference 2>/dev/null', timeout=5)
    ssh.exec_command('sudo fuser -k 8080/tcp 2>/dev/null; sudo fuser -k 9527/tcp 2>/dev/null', timeout=5)
    time.sleep(2)

    # Start with all env vars
    channel = ssh.get_transport().open_session()
    channel.exec_command('bash /home/user/launch_ts.sh')
    time.sleep(8)

    output = b''
    while channel.recv_ready():
        output += channel.recv(4096)

    # Verify
    stdin, stdout, stderr = ssh.exec_command('pgrep -f tcp_server.py', timeout=5)
    pid = stdout.read().decode().strip()
    if pid:
        print(f'tcp_server started: {pid}')
    else:
        print('FAILED to start tcp_server')

    stdin, stdout, stderr = ssh.exec_command('pgrep -f tvm_inference', timeout=5)
    daemon_pid = stdout.read().decode().strip()
    if daemon_pid:
        print(f'TVM daemon started: {daemon_pid}')
    else:
        print('WARNING: TVM daemon not found')

ssh.close()
PYEOF

# ── 4. 启动 TX USRP (容器) ──
echo ""
echo "--- 4. TX USRP ---"
MSYS_NO_PATHCONV=1 docker exec "${CONTAINER}" bash -c '
if pgrep -f OtaTxPersistentServer > /dev/null 2>&1; then
    echo "TX USRP already running"
    echo ping | timeout 3 bash -c "exec 3<>/dev/tcp/127.0.0.1/29221; echo ping >&3; cat <&3" 2>/dev/null || echo "WARNING: TX not responding"
else
    echo "Starting TX USRP..."
    chrt -r 1 bash /workspace/docker/start-usrp-tx.sh 2>&1 | tail -3
    sleep 2
    echo ping | timeout 3 bash -c "exec 3<>/dev/tcp/127.0.0.1/29221; echo ping >&3; cat <&3" 2>/dev/null && echo "TX OK" || echo "TX FAIL"
fi
'

# ── 5. 启动 RX USRP (板端) ──
echo ""
echo "--- 5. RX USRP ---"
if [ "${MODE}" = "usrp" ]; then
    python3 << PYEOF
import paramiko, time
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('${BOARD_IP}', username='${BOARD_USER}', password='${BOARD_PASS}', timeout=10)
stdin, stdout, stderr = ssh.exec_command('pgrep -f OtaRxPersistentServer', timeout=5)
existing = stdout.read().decode().strip()
if existing:
    print(f'RX USRP already running: {existing}')
else:
    print('Starting RX USRP...')
    ssh.exec_command('cd /home/user/USRP292x && nohup ./OtaRxPersistentServer --args addr=192.168.10.22 --bind 0.0.0.0 --port 29220 > /tmp/ota-rx.log 2>&1 &', timeout=5)
    time.sleep(4)
    stdin, stdout, stderr = ssh.exec_command('pgrep -f OtaRxPersistentServer', timeout=5)
    pid = stdout.read().decode().strip()
    print(f'RX USRP started: {pid}' if pid else 'RX USRP FAILED')
    stdin, stdout, stderr = ssh.exec_command('ss -tlnp | grep 29220', timeout=5)
    print(stdout.read().decode().strip()[:100])
ssh.close()
PYEOF
else
    echo "跳过 (预录模式不需要 RX USRP)"
fi

# ── 6. 检查图库 (USRP 模式) ──
echo ""
echo "--- 6. 图库 ---"
if [ "${MODE}" = "usrp" ]; then
    COUNT=$(MSYS_NO_PATHCONV=1 docker exec "${CONTAINER}" bash -c "ls ${REPO}/host_pic_to_latent/encoder_outputs_airfield300/*.pt ${REPO}/host_pic_to_latent/encoder_outputs_airfield300/*.npz 2>/dev/null | wc -l" 2>/dev/null || echo "0")
    if [ "${COUNT}" -gt 0 ] 2>/dev/null; then
        ok "容器内 latent: ${COUNT} 个"
    else
        warn "容器内无 latent 文件。请先运行初始化:"
        warn "  bash scripts/init_usrp_data.sh board    # 从板端拉取"
        warn "  bash scripts/init_usrp_data.sh local /path/to/images  # 从本地拷贝"
    fi
else
    echo "跳过 (预录模式)"
fi

# ── 7. 启动容器 server.py ──
echo ""
echo "--- 7. 容器 server.py ---"
MSYS_NO_PATHCONV=1 docker exec "${CONTAINER}" bash -c "
# Kill old server
pkill -f server.py 2>/dev/null || true
sleep 2

# Start with full env
nohup env \
  MLKEM_AUTH_ENABLED=1 \
  MLKEM_AUTH_SIG_POLICY=DUAL_REQUIRED \
  MLKEM_AUTH_PEER_SM2_PUB=/workspace/keys/server_sm2_identity.pub \
  MLKEM_AUTH_PEER_MLDSA_PUB=/workspace/keys/server_mldsa_identity.pub \
  TONGSUO_SIG_BRIDGE=/workspace/artifacts/crypto/libtongsuo_sig_bridge.so \
  TONGSUO_KEM_BRIDGE=/usr/local/tongsuo/lib64/libtongsuo_kem_bridge.so \
  OPENAMP_DEMO_INPUT_SOURCE_MODE=${MODE} \
  JSCC_LINK_MODE=qpsk \
  COCKPIT_SKIP_PYTHON=1 \
  OQS_INSTALL_PATH=/opt/liboqs \
  LD_LIBRARY_PATH="/opt/liboqs/lib:/opt/liboqs/lib64:/usr/local/tongsuo/lib64" \
  REMOTE_PASS=user \
  PHYTIUM_PI_PASSWORD=user \
  python /workspace/Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/server.py \
  > /workspace/artifacts/logs/server-prod.log 2>&1 &

# Wait for startup
for i in \$(seq 1 15); do
    curl -s --max-time 2 http://localhost:8079/api/crypto-status >/dev/null 2>&1 && { echo \"Server UP after \${i}s\"; exit 0; }
    sleep 1
done
echo 'WARNING: Server did not start within 15s'
" || fail "server.py 启动失败"

# ── 8. 启用加密 ──
echo ""
echo "--- 8. 加密通道 ---"
MSYS_NO_PATHCONV=1 docker exec "${CONTAINER}" bash -c "curl -s -X POST http://localhost:8079/api/crypto-toggle -H 'Content-Type: application/json' -d '{\"enabled\":true}' > /dev/null; sleep 3; curl -s http://localhost:8079/api/crypto-status | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d.get(\"channel_state\",\"?\"),d.get(\"session_count\",0))'"

# ── 9. 检查 USRP 控制 (USRP 模式) ──
if [ "${MODE}" = "usrp" ]; then
    echo ""
    echo "--- 9. USRP 控制 ---"
    MSYS_NO_PATHCONV=1 docker exec "${CONTAINER}" bash -c "curl -s http://localhost:8079/api/usrp-control | python3 -c 'import sys,json;d=json.load(sys.stdin);tx=d.get(\"tx_control\",{});rx=d.get(\"rx_control\",{});print(f\"TX {tx.get(\\\"ready\\\",False)} RX {rx.get(\\\"ready\\\",False)}\")'"
fi

# ── 10. 启动 Cockpit Desktop ──
echo ""
echo "--- 10. Cockpit Desktop ---"
COCKPIT_DIR="$(dirname "$(dirname "$(readlink -f "$0")")")/Semantic-Communication/cockpit_desktop"
if [ -d "${COCKPIT_DIR}" ]; then
    taskkill //F //IM electron.exe 2>/dev/null || true
    echo "启动 cockpit (后端跳过，连容器 localhost:8079)..."
    cd "${COCKPIT_DIR}" && COCKPIT_SKIP_PYTHON=1 npx electron-vite dev > /dev/null 2>&1 &
    sleep 15
    ok "Cockpit 前端已启动: http://localhost:5173"
else
    warn "找不到 cockpit 目录: ${COCKPIT_DIR}"
fi

# ── 完成 ──
echo ""
echo "============================================"
echo " 全链路就绪！"
echo ""
if [ "${MODE}" = "usrp" ]; then
    echo " 模式: USRP / QPSK OTA"
    echo " 默认批处理: 20 张"
else
    echo " 模式: 预录 / TCP"
    echo " 默认批处理: 300 张"
fi
echo ""
echo " Cockpit: http://localhost:5173"
echo " API:     http://localhost:8079"
echo "============================================"
