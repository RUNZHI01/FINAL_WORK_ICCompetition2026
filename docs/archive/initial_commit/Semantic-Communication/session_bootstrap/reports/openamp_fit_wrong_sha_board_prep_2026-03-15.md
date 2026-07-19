# OpenAMP FIT-01 wrong-SHA board prep

> Date: 2026-03-15  
> Scope: prepare the first formal P1 FIT board run for `FIT-01` only. No firmware change, no board probe execution in this step.

## 1. Intended FIT semantics

This FIT targets the existing firmware-backed admission path, not a new protocol variant.

- Fault under test: `JOB_REQ.expected_sha256` is a valid 32-byte SHA-256 value, but it does not match the firmware's built-in trusted current SHA `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`.
- Expected firmware decision:
  - `JOB_ACK.decision = DENY`
  - `JOB_ACK.fault_code = 1` (`ARTIFACT_SHA_MISMATCH`, `F001`)
  - `JOB_ACK.guard_state = 1` (`READY`)
- Expected wrapper effect:
  - `openamp_control_wrapper.py` exits with `result=denied_by_control_hook`
  - the wrapped runner never starts
- Expected follow-up state:
  - `STATUS_RESP.guard_state = READY`
  - `STATUS_RESP.active_job_id = 0`
  - `STATUS_RESP.last_fault_code = 1`
  - `STATUS_RESP.heartbeat_ok = 0`
  - `STATUS_RESP.sticky_fault = 0`
  - `STATUS_RESP.total_fault_count = pre_status.total_fault_count + 1`

The run should stay on the already working `release_v1.4.0`-based board baseline. No firmware swap is needed for this FIT.

## 2. Smallest repeatable board path

The highest-value easy path is:

1. Real `STATUS_REQ` before injection, to confirm the board is in a usable baseline state.
2. One wrapper-backed wrong-SHA admission attempt, with the wrapper hooked to the real bridge.
3. One real follow-up `STATUS_REQ`, to prove the denial did not start a job and that `F001` became observable state.

Why this path is preferred:

- It reuses the already proven live bridge/wrapper/firmware stack.
- It proves both halves that matter for FIT:
  - firmware returned a real `JOB_ACK(DENY, F001)`
  - Linux did not start the runner
- It does not require reboot, redeploy, or a wider control-loop sequence.

Use a one-nibble-mutated SHA instead of malformed input. Recommended test SHA:

```text
6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc0
```

That keeps the payload structurally valid while making the admission decision unambiguously "wrong trusted artifact".

## 3. Evidence bundle to capture

Recommended run root:

```text
session_bootstrap/reports/openamp_wrong_sha_fit_<timestamp>/
```

Minimum files:

- `pre_status/bridge_summary.json`
- `post_status/bridge_summary.json`
- `wrapper/job_manifest.json`
- `wrapper/control_trace.jsonl`
- `wrapper/wrapper_summary.json`
- `hook/status_req/bridge_summary.json`
- `hook/job_req/bridge_summary.json`
- `hook/job_req/stdin_event.json`
- `hook/job_req/job_req_tx.bin`
- `hook/job_req/job_req_tx.hex`
- `hook/job_req/job_req_tx.json`
- `hook/job_req/job_ack_rx.bin`
- `hook/job_req/job_ack_rx.hex`
- `hook/job_req/job_ack_rx.json`

Useful negative evidence:

- `wrapper/runner_should_not_run.txt` must be absent
- optional board console or `dmesg` excerpt if available, but this is not required for the first FIT proof

## 4. Minimum success criteria

The run counts as a valid `FIT-01` board proof only if all of the following are true:

1. `pre_status/bridge_summary.json` shows a sane baseline:
   - `transport_status=status_resp_received`
   - `guard_state=READY`
   - `active_job_id=0`
2. `hook/job_req/bridge_summary.json` proves a real firmware denial:
   - `decision=DENY`
   - `fault_code=1`
   - `fault_name=ARTIFACT_SHA_MISMATCH`
   - `guard_state=READY`
   - `source=firmware_job_ack`
   - `transport_status=job_ack_received`
   - `protocol_semantics=implemented`
3. `wrapper/wrapper_summary.json` proves Linux honored the denial:
   - `result=denied_by_control_hook`
   - `job_req_response.response.decision=DENY`
   - `job_req_response.response.source=firmware_job_ack`
   - `runner_exit_code=null`
4. `wrapper/runner_should_not_run.txt` is absent.
5. `post_status/bridge_summary.json` shows the job never became active and `F001` is now observable:
   - `guard_state=READY`
   - `active_job_id=0`
   - `last_fault_code=1`
   - `heartbeat_ok=0`
   - `total_fault_count = pre + 1`

If the board is not `READY` in the pre-status step, stop and clear the baseline first. Do not force the wrong-SHA FIT onto a dirty runtime state.

## 5. Exact command sequence for the next board run

The helper below is only a phase router; it does not alter protocol semantics:

- `session_bootstrap/scripts/openamp_wrong_sha_fit_hook.py`

Recommended board-side probe:

```bash
OUT=./session_bootstrap/reports/openamp_wrong_sha_fit_$(date +%Y%m%d_%H%M%S)
JOB_ID=9301
WRONG_SHA=6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc0

python3 ./session_bootstrap/scripts/openamp_rpmsg_bridge.py \
  --phase STATUS_REQ \
  --job-id "$JOB_ID" \
  --rpmsg-ctrl /dev/rpmsg_ctrl0 \
  --rpmsg-dev /dev/rpmsg0 \
  --output-dir "$OUT/pre_status"

python3 ./session_bootstrap/scripts/openamp_control_wrapper.py \
  --job-id "$JOB_ID" \
  --variant wrong_sha_fit \
  --runner-cmd "touch '$OUT/wrapper/runner_should_not_run.txt'" \
  --expected-sha256 "$WRONG_SHA" \
  --deadline-ms 60000 \
  --expected-outputs 1 \
  --job-flags smoke \
  --output-dir "$OUT/wrapper" \
  --transport hook \
  --control-hook-cmd "python3 ./session_bootstrap/scripts/openamp_wrong_sha_fit_hook.py --output-root $OUT/hook --rpmsg-ctrl /dev/rpmsg_ctrl0 --rpmsg-dev /dev/rpmsg0"

python3 ./session_bootstrap/scripts/openamp_rpmsg_bridge.py \
  --phase STATUS_REQ \
  --job-id "$JOB_ID" \
  --seq 2 \
  --rpmsg-ctrl /dev/rpmsg_ctrl0 \
  --rpmsg-dev /dev/rpmsg0 \
  --output-dir "$OUT/post_status"
```

This is the recommended first formal board-side `FIT-01` probe because it is small, firmware-backed, and leaves the working baseline untouched apart from a single rejected `JOB_REQ`.
