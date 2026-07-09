#!/usr/bin/env bash
# 在 cockpit container 内启动 OtaTxPersistentServer（控制机本地调 TX USRP）。
#
# 用法（容器外）：
#   docker exec -it <container_name> bash /workspace/docker/start-usrp-tx.sh
# 或在 start-electron-prod-demo.sh 之前预启动：
#   OPENAMP_DEMO_INPUT_SOURCE_MODE=usrp bash /workspace/docker/start-usrp-tx.sh
#
# 环境变量（与 OtaTxPersistentServer.sh 对齐）：
#   DEVICE_ARGS  默认 addr=192.168.10.2   ← TX USRP IP
#   BIND_ADDR    默认 0.0.0.0
#   PORT         默认 29221
#   RATE/FREQ/GAIN/ANT/SPB/WIREFMT/SETUP 见 OtaTxPersistentServer.sh
#
# 启动失败（USRP 不可达）会写诊断到 ${OTA_TX_LOG} 并退出非零；
# 启动成功后台等端口监听后返回 PID 文件路径。

set -euo pipefail

OTA_TX_BIN="${OTA_TX_BIN:-/workspace/USRP292x/OtaTxPersistentServer}"
OTA_TX_LOG="${OTA_TX_LOG:-/workspace/artifacts/logs/ota-tx.log}"
OTA_TX_PIDFILE="${OTA_TX_PIDFILE:-/workspace/artifacts/logs/ota-tx.pid}"
mkdir -p "$(dirname "${OTA_TX_LOG}")"

if [ ! -x "${OTA_TX_BIN}" ]; then
    echo "[start-usrp-tx] missing ${OTA_TX_BIN}; image build was incomplete" >&2
    exit 1
fi

# Already running?
if [ -f "${OTA_TX_PIDFILE}" ] && kill -0 "$(cat "${OTA_TX_PIDFILE}")" 2>/dev/null; then
    echo "[start-usrp-tx] OtaTx already running, pid=$(cat "${OTA_TX_PIDFILE}")"
    exit 0
fi

# Sanity: TX USRP reachable from container?
TX_USRP_IP="${TX_USRP_IP:-192.168.10.2}"
if ! curl -s -o /dev/null --connect-timeout 2 "telnet://${TX_USRP_IP}:7" 2>/dev/null \
    && ! timeout 2 bash -c "echo > /dev/tcp/${TX_USRP_IP}/7" 2>/dev/null; then
    # ICMP ping might not be available; fall through — USRP opens TCP on actual UHD call
    echo "[start-usrp-tx] warning: cannot reach ${TX_USRP_IP}:7 (ICMP/TCP probe), continuing anyway" >&2
fi

# Default UHD args if not overridden
export DEVICE_ARGS="${DEVICE_ARGS:-addr=${TX_USRP_IP}}"
export BIND_ADDR="${BIND_ADDR:-0.0.0.0}"
export PORT="${PORT:-29221}"
export RATE="${RATE:-5000000}"
export FREQ="${FREQ:-500000000}"
export GAIN="${GAIN:-25}"
export ANT="${ANT:-TX/RX}"
export SPB="${SPB:-1000}"
export WIREFMT="${WIREFMT:-sc16}"
export SETUP="${SETUP:-0.5}"

echo "[start-usrp-tx] starting OtaTxPersistentServer: ${DEVICE_ARGS} bind=${BIND_ADDR}:${PORT}"
nohup bash /workspace/USRP292x/OtaTxPersistentServer.sh > "${OTA_TX_LOG}" 2>&1 &
OTA_PID=$!
echo "${OTA_PID}" > "${OTA_TX_PIDFILE}"

# Wait up to 15s for port to come up
for _ in $(seq 1 30); do
    if timeout 0.5 bash -c "echo > /dev/tcp/127.0.0.1/${PORT}" 2>/dev/null; then
        echo "[start-usrp-tx] OtaTx ready, pid=${OTA_PID}, port=${PORT}"
        echo "[start-usrp-tx] log: ${OTA_TX_LOG}"
        exit 0
    fi
    if ! kill -0 "${OTA_PID}" 2>/dev/null; then
        echo "[start-usrp-tx] OtaTx died during startup; log:" >&2
        tail -30 "${OTA_TX_LOG}" >&2 || true
        rm -f "${OTA_TX_PIDFILE}"
        exit 1
    fi
    sleep 0.5
done

echo "[start-usrp-tx] timeout waiting for port ${PORT}; log tail:" >&2
tail -30 "${OTA_TX_LOG}" >&2 || true
exit 1
