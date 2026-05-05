#!/usr/bin/env bash
set -euo pipefail

# Prepared on 2026-03-15T01:09:03+0800 from /home/tianxing/tvm_metaschedule_execution_project
export REMOTE_HOST=100.121.87.73
export REMOTE_USER=user
export REMOTE_PORT=22
export REMOTE_PROJECT_ROOT=/home/user/tvm_metaschedule_execution_project
export REMOTE_OUTPUT_DIR=/tmp/openamp_wrong_sha_fit/openamp_wrong_sha_fit_20260315_010828
export JOB_ID=9301
export TRUSTED_SHA=6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1
export WRONG_SHA=6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc0

cd "$REMOTE_PROJECT_ROOT"
OUT="$REMOTE_OUTPUT_DIR"

python3 ./session_bootstrap/scripts/openamp_rpmsg_bridge.py --phase STATUS_REQ --job-id 9301 --rpmsg-ctrl /dev/rpmsg_ctrl0 --rpmsg-dev /dev/rpmsg0 --output-dir /tmp/openamp_wrong_sha_fit/openamp_wrong_sha_fit_20260315_010828/pre_status --response-timeout-sec 2.0 --settle-timeout-sec 0.05 --max-rx-bytes 4096
python3 ./session_bootstrap/scripts/openamp_control_wrapper.py --job-id 9301 --variant wrong_sha_fit --runner-cmd 'touch /tmp/openamp_wrong_sha_fit/openamp_wrong_sha_fit_20260315_010828/wrapper/runner_should_not_run.txt' --expected-sha256 6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc0 --deadline-ms 60000 --expected-outputs 1 --job-flags smoke --output-dir /tmp/openamp_wrong_sha_fit/openamp_wrong_sha_fit_20260315_010828/wrapper --transport hook --control-hook-cmd 'python3 ./session_bootstrap/scripts/openamp_wrong_sha_fit_hook.py --output-root /tmp/openamp_wrong_sha_fit/openamp_wrong_sha_fit_20260315_010828/hook --rpmsg-ctrl /dev/rpmsg_ctrl0 --rpmsg-dev /dev/rpmsg0 --response-timeout-sec 2.0 --settle-timeout-sec 0.05 --max-rx-bytes 4096'
python3 ./session_bootstrap/scripts/openamp_rpmsg_bridge.py --phase STATUS_REQ --job-id 9301 --seq 2 --rpmsg-ctrl /dev/rpmsg_ctrl0 --rpmsg-dev /dev/rpmsg0 --output-dir /tmp/openamp_wrong_sha_fit/openamp_wrong_sha_fit_20260315_010828/post_status --response-timeout-sec 2.0 --settle-timeout-sec 0.05 --max-rx-bytes 4096
