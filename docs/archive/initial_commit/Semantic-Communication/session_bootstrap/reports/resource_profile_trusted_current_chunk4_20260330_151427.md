# Remote resource profile

## Run
- run_id: resource_profile_trusted_current_chunk4_20260330_151427
- command_mode: trusted
- trusted_variant: current
- env_file: session_bootstrap/tmp/resource_profile_trusted_current_chunk4_20260330_151427.env
- remote_host: 100.121.87.73:22
- vmstat_interval_seconds: 1
- target_exit_code: 1
- command_started_at: 2026-03-30T15:14:47+08:00
- command_ended_at: 2026-03-30T15:15:05+08:00
- wall_time_seconds: 18
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
- vmstat interval samples: 18
- avg cpu user/system/idle/wait: 10.778 / 2.167 / 77.167 / 10.278 %
- avg/max runnable tasks: 0.667 / 3
- avg/max blocked tasks: 0.444 / 1
- min free memory seen by vmstat: 92380 KB

## Top Snapshots
- pre top header: top - 15:14:45 up 11 days, 21:14,  1 user,  load average: 0.00, 0.00, 0.00
- pre top cpu line: %Cpu(s):  1.3 us,  5.1 sy,  0.0 ni, 92.3 id,  0.0 wa,  0.0 hi,  1.3 si,  0.0 st
- post top header: top - 15:15:15 up 11 days, 21:14,  1 user,  load average: 0.24, 0.06, 0.02
- post top cpu line: %Cpu(s):  2.8 us,  2.8 sy,  0.0 ni, 94.4 id,  0.0 wa,  0.0 hi,  0.0 si,  0.0 st

## Artifacts
- raw_dir: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_trusted_current_chunk4_20260330_151427
- wrapper log: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/resource_profile_trusted_current_chunk4_20260330_151427.log
- target log: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_trusted_current_chunk4_20260330_151427/target.command.log
- vmstat log: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_trusted_current_chunk4_20260330_151427/vmstat.log
- free pre/post: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_trusted_current_chunk4_20260330_151427/free_pre_h.txt, /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_trusted_current_chunk4_20260330_151427/free_post_h.txt
- top pre/post: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_trusted_current_chunk4_20260330_151427/top_pre.txt, /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_trusted_current_chunk4_20260330_151427/top_post.txt
- tool probe: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_trusted_current_chunk4_20260330_151427/tool_probe.txt

## Limitations
- Resource evidence is based on free, top, vmstat, and shell wall time only.
- vmstat is system-wide and does not provide per-process RSS or per-core attribution.
- Power still needs an external board-level meter if the paper requires watt data.
