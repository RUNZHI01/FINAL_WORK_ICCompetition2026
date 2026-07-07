#!/bin/bash
# launches tcp_server detached via setsid with full ML-KEM auth env
pkill -f 'tcp_server.py' 2>/dev/null
sleep 1

export MLKEM_AUTH_ENABLED="${MLKEM_AUTH_ENABLED:-1}"
export MLKEM_AUTH_SIG_POLICY="${MLKEM_AUTH_SIG_POLICY:-DUAL_REQUIRED}"
export MLKEM_AUTH_SERVER_ID="${MLKEM_AUTH_SERVER_ID:-phytium-board}"
export MLKEM_AUTH_SERVER_SM2_KEY="${MLKEM_AUTH_SERVER_SM2_KEY:-/home/user/keys/server_sm2_identity.key}"
export MLKEM_AUTH_SERVER_SM2_PUB="${MLKEM_AUTH_SERVER_SM2_PUB:-/home/user/keys/server_sm2_identity.pub}"
export MLKEM_AUTH_SERVER_MLDSA_KEY="${MLKEM_AUTH_SERVER_MLDSA_KEY:-/home/user/keys/server_mldsa_identity.key}"
export MLKEM_AUTH_SERVER_MLDSA_PUB="${MLKEM_AUTH_SERVER_MLDSA_PUB:-/home/user/keys/server_mldsa_identity.pub}"
export TONGSUO_SIG_BRIDGE="${TONGSUO_SIG_BRIDGE:-/home/user/libtongsuo_sig_bridge.so}"
export OQS_INSTALL_PATH="${OQS_INSTALL_PATH:-/home/user/liboqs-dist}"
export LD_LIBRARY_PATH="/home/user/liboqs-dist/lib:${LD_LIBRARY_PATH:-}"

setsid bash -c "/home/user/anaconda3/envs/mlkem/bin/python -u /home/user/tcp_server.py --host 0.0.0.0 --port 9527 --status-port 8080 --suite SM4_GCM >/tmp/ts_manual.log 2>&1" </dev/null >/dev/null 2>&1
disown 2>/dev/null
sleep 4
echo ALIVE=$(pgrep -fc tcp_server.py)
pgrep -af tcp_server.py | head -2
echo ---status---
curl -s http://127.0.0.1:8080/status
echo
echo ---log---
tail -5 /tmp/ts_manual.log
