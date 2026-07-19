# Remote resource profile

## Run
- run_id: resource_profile_smoke_20260312_002
- command_mode: remote_command
- trusted_variant: current
- env_file: session_bootstrap/tmp/inference_real_reconstruction_compare_run_20260311_212301.env
- remote_host: 100.121.87.73:22
- vmstat_interval_seconds: 1
- target_exit_code: 0
- command_started_at: 2026-03-12T15:21:27+08:00
- command_ended_at: 2026-03-12T15:21:33+08:00
- wall_time_seconds: 6
- target_description: `remote:bash -lc 'echo smoke-host=$(hostname); echo started=$(date -Iseconds); sleep 3; echo finished=$(date -Iseconds)'`

## Tool Probe
- vmstat: /usr/bin/vmstat
- free: /usr/bin/free
- top: /usr/bin/top
- pidstat: missing
- mpstat: missing
- perf: missing
- sar: missing
- /usr/bin/time: missing

## Resource Summary
- free -m parsing: unavailable
- vmstat interval samples: 11
- avg cpu user/system/idle/wait: 6.273 / 2.545 / 91.727 / 0.0 %
- avg/max runnable tasks: 0.545 / 4
- avg/max blocked tasks: 0.0 / 0
- min free memory seen by vmstat: 409992 KB

## Top Snapshots
- pre top header: top - 15:21:26 up 1 day, 16 min,  1 user,  load average: 0.01, 0.02, 0.00
- pre top cpu line: %Cpu(s):  1.4 us,  2.9 sy,  0.0 ni, 95.7 id,  0.0 wa,  0.0 hi,  0.0 si,  0.0 st
- post top header: top - 15:21:40 up 1 day, 16 min,  1 user,  load average: 0.31, 0.08, 0.02
- post top cpu line: %Cpu(s):  0.0 us,  2.8 sy,  0.0 ni, 95.8 id,  0.0 wa,  0.0 hi,  1.4 si,  0.0 st

## Artifacts
- raw_dir: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_smoke_20260312_002
- wrapper log: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/resource_profile_smoke_20260312_002.log
- target log: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_smoke_20260312_002/target.command.log
- vmstat log: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_smoke_20260312_002/vmstat.log
- free pre/post: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_smoke_20260312_002/free_pre_h.txt, /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_smoke_20260312_002/free_post_h.txt
- top pre/post: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_smoke_20260312_002/top_pre.txt, /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_smoke_20260312_002/top_post.txt
- tool probe: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_smoke_20260312_002/tool_probe.txt

## Limitations
- Resource evidence is based on free, top, vmstat, and shell wall time only.
- vmstat is system-wide and does not provide per-process RSS or per-core attribution.
- Power still needs an external board-level meter if the paper requires watt data.
