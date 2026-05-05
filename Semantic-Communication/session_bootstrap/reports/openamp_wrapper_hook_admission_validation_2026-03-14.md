# OpenAMP wrapper hook admission validation

> Date: 2026-03-14
> Goal: validate that `openamp_control_wrapper.py` can consume a firmware-style `JOB_ACK(ALLOW)` through the existing hook flow, and record any blocker that prevents a fresh board-backed smoke from this workspace.
> Related evidence:
> - `session_bootstrap/reports/openamp_phase5_release_v1.4.0_job_req_job_ack_success_2026-03-14.md`
> - `session_bootstrap/reports/openamp_job_req_job_ack_real_probe_20260314_001.json`
> - `session_bootstrap/scripts/openamp_control_wrapper.py`
> - `session_bootstrap/scripts/openamp_rpmsg_bridge.py`

## 1. Current repo state

- `openamp_rpmsg_bridge.py` already forwards hook-mode `JOB_REQ` as a real binary frame and classifies a decodable firmware `JOB_ACK` as:
  - `decision=ALLOW|DENY`
  - `source=firmware_job_ack`
  - `transport_status=job_ack_received`
  - `protocol_semantics=implemented`
- Existing board evidence already proves the firmware side of the minimal admission path:
  - real `JOB_REQ -> JOB_ACK(ALLOW)`
  - follow-up `STATUS_REQ -> STATUS_RESP`
  - `guard_state=JOB_ACTIVE`
  - `active_job_id=<job_id>`

## 2. Wrapper-side fix needed before any smoke is trustworthy

Inspection of `openamp_control_wrapper.py` found a fail-open behavior in hook mode:

- before this change, the wrapper only blocked execution on an explicit `decision=DENY`
- if the hook returned no JSON, invalid JSON, or otherwise omitted an explicit decision, the wrapper still emitted local `JOB_ACK(ALLOW)` and started the runner

This was not safe enough for a real wrapper-backed admission proof.

The wrapper was updated so that:

1. In `--transport hook` mode, execution proceeds only when the hook returns an explicit `ALLOW`.
2. Any missing or unparseable admission decision is converted into a local deny before the runner starts.
3. The wrapper’s emitted `JOB_ACK` trace now carries the hook metadata needed to distinguish:
   - `source=firmware_job_ack`
   - `fault_code` / `fault_name`
   - `guard_state` / `guard_state_name`
   - `transport_status`
   - `protocol_semantics`

## 3. Local bounded validation

Because a fresh board run was not reachable from this sandbox, validation was done with two tiny hook-mode wrapper smokes using bounded local runner commands.

### 3.1 Positive replay: explicit firmware-style `ALLOW`

Command outcome:

- output dir: `session_bootstrap/reports/openamp_wrapper_hook_replay_allow_20260314_001`
- wrapper result: `success`
- runner side effect: `runner_executed.txt` exists and contains `runner-ok`

Key evidence:

- `wrapper_summary.json` records:
  - `job_req_response.response.decision = ALLOW`
  - `job_req_response.response.source = firmware_job_ack`
  - `job_req_response.response.guard_state_name = JOB_ACTIVE`
- `control_trace.jsonl` records:
  - `JOB_REQ`
  - wrapper-emitted `JOB_ACK` with:
    - `decision = ALLOW`
    - `source = firmware_job_ack`
    - `guard_state_name = JOB_ACTIVE`
    - `transport_status = job_ack_received`
    - `protocol_semantics = implemented`
  - `JOB_DONE(success)`

This proves the wrapper can consume a firmware-style positive admission decision and preserve that provenance in its own trace.

### 3.2 Negative replay: no explicit `ALLOW`

Command outcome:

- output dir: `session_bootstrap/reports/openamp_wrapper_hook_missing_allow_20260314_001`
- wrapper result: `denied_by_control_hook`
- runner side effect: `runner_executed.txt` is absent

Key evidence:

- `job_req_response.response = null`
- `control_trace.jsonl` records wrapper-emitted:
  - `JOB_ACK`
  - `decision = DENY`
  - `note = control hook did not return an explicit ALLOW`

This proves the wrapper now fails closed instead of false-starting the runner.

## 4. Why no fresh board-backed smoke was run here

Two environment blockers were confirmed in this workspace:

1. Local device nodes are absent:
   - `/dev/rpmsg0` not present
   - `/dev/rpmsg_ctrl0` not present
2. The repo’s remote-board entrypoint could not connect from this sandbox:
   - command: `timeout 10 bash ./session_bootstrap/scripts/connect_phytium_pi.sh -- env | sed -n '1,12p'`
   - result:
     - `socket: Operation not permitted`
     - `ssh: connect to host 100.121.87.73 port 22: failure`

So the missing piece here is not wrapper logic and not the already-proven firmware admission path. The blocker is sandboxed board access from the current execution environment.

## 5. Updated conclusion

The wrapper-backed admission conclusion should now be stated more precisely:

- `openamp_control_wrapper.py` is now safe to use as a real hook-mode admission gate because it requires an explicit `ALLOW` instead of failing open.
- The wrapper now preserves `firmware_job_ack` provenance in its `JOB_ACK` trace, which is the minimal durable evidence needed to distinguish a real firmware decision from a local skeleton response.
- A fresh board-backed smoke was not executed from this sandbox because RPMsg devices are absent locally and outbound SSH to the Phytium board is blocked here.
- Combining this wrapper fix with the already captured board evidence in `openamp_phase5_release_v1.4.0_job_req_job_ack_success_2026-03-14.md`, the engineering conclusion is:
  - the wrapper side is ready to consume a real firmware `JOB_ACK(ALLOW)`
  - the remaining step is to run the existing hook command on a board-reachable host and capture a new wrapper report there
