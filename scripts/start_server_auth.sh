#!/bin/bash
set -e
cd /workspace
export MLKEM_AUTH_ENABLED=1
export MLKEM_AUTH_SIG_POLICY=DUAL_REQUIRED
export MLKEM_AUTH_SERVER_ID=phytium-board
export MLKEM_AUTH_SERVER_SM2_KEY=/home/user/keys/server_sm2_identity.key
export MLKEM_AUTH_SERVER_SM2_PUB=/home/user/keys/server_sm2_identity.pub
export MLKEM_AUTH_SERVER_MLDSA_KEY=/home/user/keys/server_mldsa_identity.key
export MLKEM_AUTH_SERVER_MLDSA_PUB=/home/user/keys/server_mldsa_identity.pub
export MLKEM_AUTH_PEER_SM2_PUB=/workspace/keys/server_sm2_identity.pub
export MLKEM_AUTH_PEER_MLDSA_PUB=/workspace/keys/server_mldsa_identity.pub
export MLKEM_REMOTE_TONGSUO_SIG_BRIDGE=/home/user/libtongsuo_sig_bridge.so
export TONGSUO_SIG_BRIDGE=/home/user/libtongsuo_sig_bridge.so
export MLKEM_REMOTE_OQS_INSTALL=/home/user/liboqs-dist
export OQS_INSTALL_PATH=/opt/liboqs
export MLKEM_STATUS_STARTUP_WAIT_SEC=60
export MLKEM_REMOTE_RUN_LOGGER_DIR=/home/user/artifacts/evidence/logs
export OPENAMP_DEMO_INPUT_SOURCE_MODE=prerecorded
export COCKPIT_SKIP_PYTHON=1
exec python /workspace/Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/server.py
