# RPC 真机首轮执行状态（lenovo，2026-03-01）

## 1) 本机专用 env

- env 文件：`session_bootstrap/config/rpc_armv8.lenovo.2026-03-01.env`
- 生成方式：基于 `rpc_armv8.example.env` 新建，不覆盖样例。

## 2) 参数盘点（实值 / 待补）

### 已是实值（可直接使用）

- `TARGET=llvm -mtriple=aarch64-linux-gnu -mattr=+neon`
- `SHAPE_BUCKETS=1x3x224x224,1x3x256x256`
- `THREADS=4`
- `RPC_TRACKER_BIND_HOST=0.0.0.0`
- `RPC_TRACKER_PORT=9190`
- `RPC_SERVER_HOST=0.0.0.0`
- `RPC_SERVER_PORT=9090`
- `RPC_SERVER_PORT_END=9099`
- `TVM_PYTHON=python3`
- `TUNING_DB_DIR=./session_bootstrap/tmp/rpc_armv8_lenovo_db`
- `LOG_DIR=./session_bootstrap/logs`
- `REPORT_DIR=./session_bootstrap/reports`
- `QUICK_* / FULL_*` 已替换为“可执行 mock 命令”（用于最小闭环，不是实机 TVM payload）
- `DAILY_*` 字段已填写。

### 仍需用户补充（真机闭环必需）

- `MODEL_NAME=replace_with_model_name`（需替换为真实模型名）
- `DEVICE_KEY=replace_with_device_key`（需与 ARMv8 真机 `rpc_server --key` 一致）
- `RPC_TRACKER_HOST=127.0.0.1` 当前是本机默认值：
  - 若 tracker 不在本机，需改为开发机可达 IP/域名。
- `QUICK_BASELINE_CMD / QUICK_CURRENT_CMD` 需改为真实 TVM RPC quick 命令。
- `FULL_BASELINE_CMD / FULL_CURRENT_CMD` 需改为真实 TVM RPC full/hotspot 命令。

## 3) Readiness 检查结果

- 检查命令：
  - `bash session_bootstrap/scripts/check_rpc_readiness.sh --env session_bootstrap/config/rpc_armv8.lenovo.2026-03-01.env --output session_bootstrap/reports/readiness_rpc_armv8_lenovo_2026-03-01.md`
- 结果：`PASS`（脚本语义下可执行）。
- 说明：该 `PASS` 不代表“已完成真机实测”，因为 `DEVICE_KEY/MODEL_NAME` 仍为占位值，且 payload 仍为 mock。

## 4) RPC 命令模板

- 模板文件：`session_bootstrap/reports/rpc_commands_armv8_lenovo_2026-03-01.md`
- 已输出 tracker/server/client（quick/full/一键首轮）命令。

## 5) 真实执行尝试与阻断

- 尝试命令（真机模式）：
  - `bash session_bootstrap/scripts/run_rpc_first_round.sh --env session_bootstrap/config/rpc_armv8.lenovo.2026-03-01.env`
- 结果：失败。
- 阻断项：`tracker is unreachable at 127.0.0.1:9190`
- 阻断归因：当前未启动可达 tracker（且未接入真机 server）。

## 6) 最小闭环执行（可执行到哪一步就执行到哪一步）

- 执行命令（离线最小闭环）：
  - `bash session_bootstrap/scripts/run_rpc_first_round.sh --env session_bootstrap/config/rpc_armv8.lenovo.2026-03-01.env --simulate`
- 结果：完成 `quick + full + daily + experiment`，但标记为“离线模拟（非真机）”。
- 核心产物：
  - `session_bootstrap/reports/readiness_rpc_2026-03-01.md`
  - `session_bootstrap/reports/rpc_run_env_20260301_144456.env`
  - `session_bootstrap/reports/rpc_commands_20260301_144456.md`
  - `session_bootstrap/reports/quick_rpc_armv8_lenovo_round1.md`
  - `session_bootstrap/reports/full_rpc_armv8_lenovo_round1.md`
  - `session_bootstrap/reports/daily_rpc_armv8_lenovo_round1.md`
  - `session_bootstrap/reports/experiment_record_full_rpc_armv8_lenovo_round1.md`

## 7) 结论

- 真机首轮闭环：`否`
- 当前完成度：已完成“本仓库编排与落盘”的最小闭环；真机阻断点已定位并可复现。
