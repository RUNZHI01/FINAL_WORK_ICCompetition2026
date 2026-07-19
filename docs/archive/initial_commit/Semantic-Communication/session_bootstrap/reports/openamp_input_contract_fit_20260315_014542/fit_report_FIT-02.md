# OpenAMP FIT Report

- generated_at: `2026-03-15T01:47:41+0800`
- fit_id: `FIT-02`
- run_id: `openamp_input_contract_fit_20260315_014542`
- scenario: `illegal expected_outputs JOB_REQ on real board path`
- tc_id: `TC-004`

## Fault Injection

- injected_fault: Set `JOB_REQ.expected_outputs=2`, which is outside the current allowed set `(1, 300)`.
- risk_item: input contract / param range violation

## Expected

Receive `JOB_ACK(DENY, F009)`, keep guard in `READY`, and do not start the runner.

## Actual

Board-backed FIT-02 passed: firmware returned `JOB_ACK(DENY, ILLEGAL_PARAM_RANGE)`, wrapper ended as `denied_by_control_hook`, runner marker stayed absent, and follow-up `STATUS_RESP` remained `READY/active_job_id=0` with `last_fault=ILLEGAL_PARAM_RANGE` and `total_fault_count=1`.

## Evidence Bundle

`run_manifest.json`, `pre_status/status_snapshot.json`, `hook/job_req/bridge_summary.json`, `wrapper/job_manifest.json`, `wrapper/control_trace.jsonl`, `wrapper/wrapper_summary.json`, `post_status/status_snapshot.json`, `fit_summary.json`, `coverage_matrix.md`
