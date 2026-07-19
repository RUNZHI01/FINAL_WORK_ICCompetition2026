# Remote resource profile

## Run
- run_id: resource_profile_big_little_current_20260318_052922
- command_mode: trusted
- trusted_variant: current
- env_file: ./session_bootstrap/config/big_little_pipeline.current.runtime_20260318_050239.env
- remote_host: 100.121.87.73:22
- vmstat_interval_seconds: 1
- target_exit_code: 0
- command_started_at: 2026-03-18T05:29:25+08:00
- command_ended_at: 2026-03-18T05:30:49+08:00
- wall_time_seconds: 84
- target_description: `bash ./session_bootstrap/scripts/run_big_little_pipeline.sh --variant current`

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
- vmstat interval samples: 85
- avg cpu user/system/idle/wait: 53.812 / 2.706 / 43.435 / 0.129 %
- avg/max runnable tasks: 2.165 / 6
- avg/max blocked tasks: 0.012 / 1
- min free memory seen by vmstat: 217480 KB

## Top Snapshots
- pre top header: top - 05:29:23 up  9:11,  1 user,  load average: 0.00, 0.08, 0.22
- pre top cpu line: %Cpu(s):  5.2 us,  6.9 sy,  0.0 ni, 87.9 id,  0.0 wa,  0.0 hi,  0.0 si,  0.0 st
- post top header: top - 05:30:50 up  9:13,  1 user,  load average: 1.34, 0.50, 0.36
- post top cpu line: %Cpu(s):  1.8 us,  5.5 sy,  0.0 ni, 92.7 id,  0.0 wa,  0.0 hi,  0.0 si,  0.0 st

## Target JSON Summary
- status: ok

## Artifacts
- raw_dir: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_big_little_current_20260318_052922
- wrapper log: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/logs/resource_profile_big_little_current_20260318_052922.log
- target log: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_big_little_current_20260318_052922/target.command.log
- vmstat log: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_big_little_current_20260318_052922/vmstat.log
- free pre/post: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_big_little_current_20260318_052922/free_pre_h.txt, /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_big_little_current_20260318_052922/free_post_h.txt
- top pre/post: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_big_little_current_20260318_052922/top_pre.txt, /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_big_little_current_20260318_052922/top_post.txt
- tool probe: /home/tianxing/tvm_metaschedule_execution_project/./session_bootstrap/reports/resource_profile_big_little_current_20260318_052922/tool_probe.txt

## Limitations
- Resource evidence is based on free, top, vmstat, and shell wall time only.
- vmstat is system-wide and does not provide per-process RSS or per-core attribution.
- Power still needs an external board-level meter if the paper requires watt data.
