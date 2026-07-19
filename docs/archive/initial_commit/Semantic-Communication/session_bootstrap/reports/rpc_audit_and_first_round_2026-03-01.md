# RPC 审查与首轮执行记录（2026-03-01）

- 审查目标：按手册进入 ARMv8 真机 RPC 调优闭环
- 执行时间：2026-03-01
- 执行范围：仅本仓库 `session_bootstrap/`（未修改 `/home/tianxing/tvm-src`）

## 1) Readiness Checklist（满足/不满足/证据）

### A. 真机模板配置（`rpc_armv8.example.env`）

- 结果：`BLOCKED`
- 证据文件：`session_bootstrap/reports/readiness_rpc_armv8_example_2026-03-01.md`

结论：
- 满足：目标场景字段、Top3-8、DB 路径、单变量字段、验收字段、模板、入口脚本。
- 不满足：`QUICK_*`、`FULL_*` 仍是占位命令。

### B. 可执行闭环配置（`rpc_armv8_smoke.env`）

- 结果：`PASS`
- 证据文件：`session_bootstrap/reports/readiness_rpc_armv8_smoke_2026-03-01.md`

结论：
- 已满足：ARMv8 目标表达、quick/full 命令可执行、热点 Top3、DB 路径可写、单变量字段、验收字段、日报模板、RPC 入口脚本。

## 2) 阻断项清单与最小修复

阻断项：
1. 缺少真机 RPC 闭环入口脚本（tracker/server/client 命令模板与一键执行）。
2. 缺少 RPC 配置模板与离线最小验证配置。
3. 日报缺“有效样本”字段，不满足验收要素全量映射。

最小修复（已完成）：
1. 新增 `scripts/check_rpc_readiness.sh`、`scripts/rpc_print_cmd_templates.sh`、`scripts/run_rpc_first_round.sh`。
2. 新增 `config/rpc_armv8.example.env`、`config/rpc_armv8_smoke.env`。
3. `run_full_placeholder.sh` 新增 `baseline_count/current_count`。
4. `summarize_to_daily.sh` 新增“有效样本（baseline/current）”聚合。
5. 新增 `runbooks/rpc_first_round_runbook.md` 与 `templates/daily_field_mapping_rpc.md`。

## 3) 首轮闭环执行（离线模拟）

执行命令：

```bash
bash ./session_bootstrap/scripts/run_rpc_first_round.sh \
  --env ./session_bootstrap/config/rpc_armv8_smoke.env \
  --simulate
```

执行结果：成功

产物：
- readiness：`session_bootstrap/reports/readiness_rpc_2026-03-01.md`
- run env 快照：`session_bootstrap/reports/rpc_run_env_20260301_131806.env`
- RPC 命令模板：`session_bootstrap/reports/rpc_commands_20260301_131806.md`
- quick：`session_bootstrap/reports/quick_rpc_smoke_first_round.md`
- full：`session_bootstrap/reports/full_rpc_smoke_first_round.md`
- daily：`session_bootstrap/reports/daily_rpc_smoke_first_round.md`
- experiment：`session_bootstrap/reports/experiment_record_full_rpc_smoke_first_round.md`

## 4) 真机必需步骤标注

以下步骤在本次仅为模板/模拟，实际执行需真机与 TVM 环境：
1. `python3 -m tvm.exec.rpc_tracker ...`（开发机）
2. `python3 -m tvm.exec.rpc_server ...`（ARMv8 真机）
3. `QUICK_*`、`FULL_*` 替换为真实 TVM RPC 调优/评测命令
