# OpenAMP FIT Report

- generated_at: `2026-03-15T01:28:29+0800`
- fit_id: `FIT-01`
- run_id: `openamp_wrong_sha_fit_20260315_012403`
- scenario: `wrong expected_sha256 JOB_REQ on real board path`
- tc_id: `TC-003`

## Fault Injection

- injected_fault: Mutate `JOB_REQ.expected_sha256` to a valid but untrusted SHA-256 value.
- risk_item: unknown artifact execution risk

## Expected

Receive `JOB_ACK(DENY, F001)`, keep guard in `READY`, and do not start the runner.

## Actual

Board-backed FIT-01 passed: firmware returned `JOB_ACK(DENY, ARTIFACT_SHA_MISMATCH)`, wrapper ended as `denied_by_control_hook`, runner marker stayed absent, and follow-up `STATUS_RESP` remained `READY/active_job_id=0` with `last_fault=ARTIFACT_SHA_MISMATCH` and `total_fault_count=1`.

## Evidence Bundle

`run_manifest.json`, `pre_status/status_snapshot.json`, `hook/job_req/bridge_summary.json`, `wrapper/job_manifest.json`, `wrapper/control_trace.jsonl`, `wrapper/wrapper_summary.json`, `post_status/status_snapshot.json`, `fit_summary.json`, `coverage_matrix.md`
