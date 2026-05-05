# OpenAMP FIT Report

- generated_at: `2026-03-15T01:09:03+0800`
- fit_id: `FIT-01`
- run_id: `openamp_wrong_sha_fit_20260315_010828`
- scenario: `wrong expected_sha256 JOB_REQ on real board path`
- tc_id: `TC-003`

## Fault Injection

- injected_fault: Mutate JOB_REQ.expected_sha256 to a valid but untrusted SHA-256 value.
- risk_item: unknown artifact execution risk

## Expected

Receive JOB_ACK(DENY, F001), keep guard in READY, and do not start the runner.

## Actual

blocked_before_board_execution due to ssh connect failure; no STATUS_REQ or JOB_REQ reached the board.

## Evidence Bundle

run_manifest.json, ssh_probe/connect_probe.json, pre_status/status_snapshot.json, wrapper/job_manifest.json, wrapper/control_trace.jsonl, wrapper/wrapper_summary.json, post_status/status_snapshot.json
