# 首轮真机 RPC 闭环 Runbook（ARMv8 runner）

目标：开发机作为 builder/orchestrator，ARMv8 边缘设备作为 runner，完成 `quick + full(热点)` 首轮闭环并落盘日报。

## 0. 准备环境（开发机）

1. 复制配置模板并填写真实参数：

```bash
cp ./session_bootstrap/config/rpc_armv8.example.env ./session_bootstrap/config/rpc_armv8.local.env
```

2. 至少填完这些字段：
- `MODEL_NAME`
- `TARGET`（需为 ARMv8/aarch64）
- `DEVICE_KEY`
- `RPC_TRACKER_HOST`、`RPC_TRACKER_PORT`
- `QUICK_BASELINE_CMD`、`QUICK_CURRENT_CMD`
- `FULL_HOTSPOT_TASKS`（Top3-8）
- `FULL_BASELINE_CMD`、`FULL_CURRENT_CMD`
- `DAILY_SINGLE_CHANGE`

## 1. 启动 Tracker（开发机）[真机必需]

```bash
python3 -m tvm.exec.rpc_tracker --host 0.0.0.0 --port 9190
```

说明：端口与 host 以 env 实际值为准；建议该进程独立终端常驻。

## 2. 启动 RPC Server（ARMv8 设备）[真机必需]

```bash
python3 -m tvm.exec.rpc_server --tracker <tracker_ip>:9190 --key <device_key> --host 0.0.0.0 --port 9090 --port-end 9099
```

说明：`<tracker_ip>`、`<device_key>` 必须与开发机 env 对齐。

## 3. 开发机 readiness 审查

```bash
bash ./session_bootstrap/scripts/check_rpc_readiness.sh \
  --env ./session_bootstrap/config/rpc_armv8.local.env
```

产物：`session_bootstrap/reports/readiness_rpc_<date>.md`

## 4. 生成命令模板（便于抄用）

```bash
bash ./session_bootstrap/scripts/rpc_print_cmd_templates.sh \
  --env ./session_bootstrap/config/rpc_armv8.local.env
```

## 5. 执行首轮闭环（quick + full + daily）

```bash
bash ./session_bootstrap/scripts/run_rpc_first_round.sh \
  --env ./session_bootstrap/config/rpc_armv8.local.env
```

执行顺序：
1. readiness 再检查
2. quick
3. full（热点）
4. daily summary
5. experiment record

## 6. 离线模拟验证（无真机时）

```bash
bash ./session_bootstrap/scripts/run_rpc_first_round.sh \
  --env ./session_bootstrap/config/rpc_armv8_smoke.env \
  --simulate
```

说明：该模式仅验证脚手架链路，不代表真机性能结论。

## 7. 验收对照

- baseline/current：看 quick/full 报告字段。
- 有效样本：看 `baseline_count/current_count`。
- 稳定性：quick 报告方差字段 + 日报稳定性条目。
- 日报与实验记录：`daily_*.md` + `experiment_record_*.md`。

## 8. 常见失败优先排查

1. tracker 不可达：先检查 IP/端口、防火墙、NAT。
2. device_key 不匹配：server 与 client env 必须一致。
3. target 漂移：必须保持 ARMv8 target 固定。
4. 非热点任务混入 full：`FULL_HOTSPOT_TASKS` 保持 Top3-8。
5. 命令仍是占位符：readiness 会直接拦截。
