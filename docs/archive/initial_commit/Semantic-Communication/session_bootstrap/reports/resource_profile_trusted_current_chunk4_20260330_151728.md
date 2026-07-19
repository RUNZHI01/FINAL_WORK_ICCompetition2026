# Remote resource profile

## Run
- run_id: resource_profile_trusted_current_chunk4_20260330_151728
- command_mode: trusted
- trusted_variant: current
- env_file: session_bootstrap/tmp/resource_profile_trusted_current_chunk4_20260330_151728.env
- remote_host: 100.121.87.73:22
- vmstat_interval_seconds: 1
- target_exit_code: 0
- command_started_at: 2026-03-30T15:17:31+08:00
- command_ended_at: 2026-03-30T15:19:03+08:00
- wall_time_seconds: 92
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
- vmstat interval samples: 92
- avg cpu user/system/idle/wait: 32.283 / 9.065 / 58.348 / 0.25 %
- avg/max runnable tasks: 1.685 / 5
- avg/max blocked tasks: 0.022 / 1
- min free memory seen by vmstat: 88340 KB

## Top Snapshots
- pre top header: top - 15:17:30 up 11 days, 21:17,  1 user,  load average: 0.19, 0.09, 0.03
- pre top cpu line: %Cpu(s):  1.4 us,  1.4 sy,  0.0 ni, 95.8 id,  0.0 wa,  1.4 hi,  0.0 si,  0.0 st
- post top header: top - 15:19:36 up 11 days, 21:19,  1 user,  load average: 0.80, 0.50, 0.19
- post top cpu line: %Cpu(s):  1.4 us,  2.8 sy,  0.0 ni, 95.8 id,  0.0 wa,  0.0 hi,  0.0 si,  0.0 st

## Target JSON Summary
- run_median_ms: 230.466
- run_mean_ms: 231.548
- run_count: 300
- artifact_sha256_match: True
- output_shape: [1, 3, 256, 256]

## Artifacts
- raw_dir: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_trusted_current_chunk4_20260330_151728
- wrapper log: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/resource_profile_trusted_current_chunk4_20260330_151728.log
- target log: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_trusted_current_chunk4_20260330_151728/target.command.log
- vmstat log: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_trusted_current_chunk4_20260330_151728/vmstat.log
- free pre/post: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_trusted_current_chunk4_20260330_151728/free_pre_h.txt, /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_trusted_current_chunk4_20260330_151728/free_post_h.txt
- top pre/post: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_trusted_current_chunk4_20260330_151728/top_pre.txt, /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_trusted_current_chunk4_20260330_151728/top_post.txt
- tool probe: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_trusted_current_chunk4_20260330_151728/tool_probe.txt

## Limitations
- Resource evidence is based on free, top, vmstat, and shell wall time only.
- vmstat is system-wide and does not provide per-process RSS or per-core attribution.
- Power still needs an external board-level meter if the paper requires watt data.
