# Remote resource profile

## Run
- run_id: resource_profile_trusted_current_20260312_001
- command_mode: trusted
- trusted_variant: current
- env_file: session_bootstrap/tmp/inference_real_reconstruction_compare_run_20260311_212301.env
- remote_host: 100.121.87.73:22
- vmstat_interval_seconds: 1
- target_exit_code: 0
- command_started_at: 2026-03-12T15:22:28+08:00
- command_ended_at: 2026-03-12T15:24:06+08:00
- wall_time_seconds: 98
- target_description: `bash ./session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current`

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
- vmstat interval samples: 94
- avg cpu user/system/idle/wait: 67.266 / 11.83 / 20.16 / 0.83 %
- avg/max runnable tasks: 3.755 / 8
- avg/max blocked tasks: 0.117 / 3
- min free memory seen by vmstat: 115408 KB

## Top Snapshots
- pre top header: top - 15:22:27 up 1 day, 17 min,  1 user,  load average: 0.13, 0.07, 0.02
- pre top cpu line: %Cpu(s):  0.0 us,  4.2 sy,  0.0 ni, 95.8 id,  0.0 wa,  0.0 hi,  0.0 si,  0.0 st
- post top header: top - 15:24:12 up 1 day, 18 min,  1 user,  load average: 2.85, 1.10, 0.40
- post top cpu line: %Cpu(s):  1.3 us,  4.0 sy,  0.0 ni, 94.7 id,  0.0 wa,  0.0 hi,  0.0 si,  0.0 st

## Target JSON Summary
- run_median_ms: 264.912
- run_mean_ms: 268.442
- run_count: 300
- artifact_sha256_match: True
- output_shape: [1, 3, 256, 256]

## Artifacts
- raw_dir: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_trusted_current_20260312_001
- wrapper log: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/resource_profile_trusted_current_20260312_001.log
- target log: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_trusted_current_20260312_001/target.command.log
- vmstat log: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_trusted_current_20260312_001/vmstat.log
- free pre/post: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_trusted_current_20260312_001/free_pre_h.txt, /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_trusted_current_20260312_001/free_post_h.txt
- top pre/post: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_trusted_current_20260312_001/top_pre.txt, /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_trusted_current_20260312_001/top_post.txt
- tool probe: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_trusted_current_20260312_001/tool_probe.txt

## Limitations
- Resource evidence is based on free, top, vmstat, and shell wall time only.
- vmstat is system-wide and does not provide per-process RSS or per-core attribution.
- Power still needs an external board-level meter if the paper requires watt data.
