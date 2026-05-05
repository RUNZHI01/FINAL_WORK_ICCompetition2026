# RPC Command Templates

- generated_at: 2026-03-01T13:18:45+08:00
- env_file: /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/config/rpc_armv8.example.env

## 1) Tracker（开发机，builder/orchestrator 侧）

```bash
python3 -m tvm.exec.rpc_tracker --host "0.0.0.0" --port "9190"
```

## 2) RPC Server（ARMv8 真机，runner 侧）

```bash
python3 -m tvm.exec.rpc_server --tracker "replace_with_tracker_ip:9190" --key "replace_with_device_key" --host "0.0.0.0" --port "9090" --port-end "9099"
```

## 3) Client（开发机，quick/full 触发）

```bash
bash "/home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/scripts/run_quick.sh" --env "/home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/config/rpc_armv8.example.env"
bash "/home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/scripts/run_full_placeholder.sh" --env "/home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/config/rpc_armv8.example.env"
```

## 4) Client（一键首轮闭环入口）

```bash
bash "/home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/scripts/run_rpc_first_round.sh" --env "/home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/config/rpc_armv8.example.env"
```

## 5) 当前 env 中的 quick/full payload 命令

```bash
# quick
echo "replace QUICK_BASELINE_CMD with real TVM RPC tuning/eval command" && exit 1
echo "replace QUICK_CURRENT_CMD with real TVM RPC tuning/eval command" && exit 1

# full
echo "replace FULL_BASELINE_CMD with real TVM RPC hotspot command" && exit 1
echo "replace FULL_CURRENT_CMD with real TVM RPC hotspot command" && exit 1
```
