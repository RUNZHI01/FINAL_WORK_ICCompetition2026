# Blocked Recheck Handoff

- generated_at: 2026-03-08T09:49:00+08:00
- project: tvm_metaschedule_execution_project
- blocker: SSH to `100.121.87.73:22` keeps timing out
- latest_probe_result: `code 124` / `ssh: connect to host 100.121.87.73 port 22: Connection timed out`

## Current Conclusion

The remaining blocker is external connectivity to the Phytium-Pi runner. Local script-side cleanup is largely complete; online quick recheck has not restarted because the host is still unreachable.

## Local Fixes Already Landed

1. `run_quick.sh`
   - Refuses to overwrite existing `RUN_ID` artifacts unless `ALLOW_REPORT_OVERWRITE=1`.
2. `run_full_placeholder.sh`
   - Same overwrite guard as quick.
3. `run_rpc_tune.sh`
   - Writes `quick_status` / `full_status` into orchestrator summary.
   - Uses fallback status strings when report/status is missing.
4. `summarize_to_daily.sh`
   - De-duplicates same-day reports by `mode + execution_id`.
   - Chooses the latest report by report `timestamp` first, then file mtime as fallback.
5. `rerun_quick_after_ssh_recovery.sh`
   - One-shot helper to probe SSH once, mint a fresh `EXECUTION_ID`, run quick, then regenerate a dedicated daily report.
   - Now passes `REMOTE_SSH_PORT` explicitly.

## Resume Command After SSH Recovery

```bash
bash /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/scripts/rerun_quick_after_ssh_recovery.sh \
  --env /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/config/rpc_tune_local.2026-03-08.phytium_pi.env \
  --prefix quick_rpc_tune_recheck \
  --ssh-timeout-sec 12
```

## Expected Outputs After Recovery

- fresh run env under `session_bootstrap/tmp/recheck_envs/`
- quick report under `session_bootstrap/reports/quick_rpc_tune_recheck_<STAMP>.md`
- dedicated daily report under `session_bootstrap/reports/daily_quick_rpc_tune_recheck_<STAMP>.md`

## What To Check First When Host Comes Back

1. Whether SSH probe succeeds at all.
2. Whether quick baseline still completes 3/3.
3. Whether quick current still stalls on iteration 2/3.
4. If current still fails, compare the new quick report/log/raw trio before touching scripts again.
