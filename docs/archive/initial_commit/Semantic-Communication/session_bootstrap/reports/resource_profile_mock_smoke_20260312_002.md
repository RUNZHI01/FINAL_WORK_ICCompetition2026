# Remote resource profile

## Run
- run_id: resource_profile_mock_smoke_20260312_002
- command_mode: smoke
- trusted_variant: current
- env_file: session_bootstrap/tmp/inference_real_reconstruction_compare_run_20260311_212301.env
- remote_host: 100.121.87.73:22
- vmstat_interval_seconds: 1
- target_exit_code: 0
- command_started_at: 2026-03-12T15:22:51+08:00
- command_ended_at: 2026-03-12T15:22:54+08:00
- wall_time_seconds: 3
- target_description: `remote:bash -lc 'echo resource-profile-smoke host=$(hostname); echo started=$(date -Iseconds); sleep 3; echo finished=$(date -Iseconds)'`

## Tool Probe
- vmstat: /usr/bin/vmstat
- free: /usr/bin/free
- top: /usr/bin/top
- pidstat: missing
- mpstat: missing
- perf: missing
- sar: missing
- /usr/bin/time: /usr/bin/time

## Resource Summary
- pre free -m: total=15738 used=2501 free=12788 available=13236 MiB
- post free -m: total=15738 used=2502 free=12787 available=13235 MiB
- delta available memory: -1 MiB
- vmstat interval samples: 4
- avg cpu user/system/idle/wait: 0.5 / 0.5 / 98.5 / 0.25 % (guest 0.0 %)
- avg/max runnable tasks: 1.25 / 3
- avg/max blocked tasks: 0.25 / 1
- min free memory seen by vmstat: 13093684 KB

## Top Snapshots
- pre top header: top - 15:22:50 up  1:04,  1 user,  load average: 0.06, 0.10, 0.06
- pre top cpu line: %Cpu(s):  0.8 us,  0.0 sy,  0.0 ni, 99.2 id,  0.0 wa,  0.0 hi,  0.0 si,  0.0 st
- post top header: top - 15:22:54 up  1:04,  1 user,  load average: 0.06, 0.09, 0.06
- post top cpu line: %Cpu(s):  0.8 us,  1.6 sy,  0.0 ni, 97.6 id,  0.0 wa,  0.0 hi,  0.0 si,  0.0 st

## Artifacts
- raw_dir: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_mock_smoke_20260312_002
- wrapper log: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/resource_profile_mock_smoke_20260312_002.log
- target log: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_mock_smoke_20260312_002/target.command.log
- vmstat log: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_mock_smoke_20260312_002/vmstat.log
- free pre/post: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_mock_smoke_20260312_002/free_pre_h.txt, /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_mock_smoke_20260312_002/free_post_h.txt
- top pre/post: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_mock_smoke_20260312_002/top_pre.txt, /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_mock_smoke_20260312_002/top_post.txt
- tool probe: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_mock_smoke_20260312_002/tool_probe.txt

## Limitations
- Resource evidence is based on free, top, vmstat, and shell wall time only.
- vmstat is system-wide and does not provide per-process RSS or per-core attribution.
- Power still needs an external board-level meter if the paper requires watt data.
