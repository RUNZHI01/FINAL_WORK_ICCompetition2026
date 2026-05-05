# OpenAMP FIT-01 wrong-SHA remote probe blocked

> Date: 2026-03-15  
> Scope: execute the first formal P1 FIT-01 wrong-SHA probe from the Snapdragon workspace at `/home/tianxing/tvm_metaschedule_execution_project`.

## 1. Result

This run did not reach the board. The very first SSH connect probe from this workspace to `100.121.87.73:22` failed with:

```text
socket: Operation not permitted
ssh: connect to host 100.121.87.73 port 22: failure
```

Therefore, no board-side `STATUS_REQ`, `JOB_REQ`, or follow-up `STATUS_REQ` was actually transmitted in this run. The blocker is at the workspace network boundary, not inside the OpenAMP control path itself.

## 2. Evidence bundle

This run still produced a structured FIT-01 bundle instead of ad-hoc notes:

- bundle root: `session_bootstrap/reports/openamp_wrong_sha_fit_20260315_010828/`
- key artifacts:
  - `run_manifest.json`
  - `ssh_probe/connect_probe.json`
  - `pre_status/status_snapshot.json`
  - `wrapper/job_manifest.json`
  - `wrapper/control_trace.jsonl`
  - `wrapper/wrapper_summary.json`
  - `post_status/status_snapshot.json`
  - `fit_summary.json`
  - `fit_report_FIT-01.md`
  - `coverage_matrix.md`
  - `blocked_report.md`

The bundle explicitly records the expected FIT-01 semantics, the exact board commands that should run once SSH is available, and the real blocker observed in this workspace.

## 3. New reusable entrypoint

The board-run orchestration is now captured in:

- `session_bootstrap/scripts/run_openamp_fit_wrong_sha.py`

Its contract is:

1. try a minimal SSH reachability probe
2. if reachable, execute the existing board-side sequence:
   - pre `STATUS_REQ`
   - wrapper-backed wrong-SHA `JOB_REQ`
   - post `STATUS_REQ`
3. if unreachable, emit the same bundle layout with explicit `BLOCKED` status

## 4. Next step

Re-run the same script from an execution context that can actually open outbound SSH sockets to the Phytium Pi. Once FIT-01 can run cleanly, reuse the same bundle layout for FIT-02 and FIT-03.
