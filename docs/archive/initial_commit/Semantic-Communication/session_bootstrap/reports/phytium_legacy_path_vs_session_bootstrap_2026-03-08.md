# Phytium-Pi：旧 JSCC TVM 路径 vs 当前 session_bootstrap MetaSchedule（2026-03-08）

## 结论

- **当前本地 artifact generation 不应再被理解为“错误地过于 generic”**。
- 在本地 LLVM 18 / TVM 0.24 builder 下，`mcpu=phytium` / `mcpu=ft2000plus` 对 `aarch64-linux-gnu` **并不真正可用**，因此 `mcpu=generic` 是当前环境里可落地的选择。
- 真正需要修正的不是 `generic` 本身，而是旧 2026-03-06 本地产物配置里额外写入的 `+crypto,+crc`：
  - 旧 JSCC Phytium compile 配置本来就是 **`generic + neon`**；
  - 当前 repo 的目标复核报告也明确要求 **去掉无现场证据的 `+crypto,+crc`**；
  - 因此本轮将仍会被使用的 Phytium env 收敛为 **`generic + neon`**。
- 本地重建新 artifact **成功**；远端 deploy / quick **未执行到有效 payload**，阻断点是当前 sandbox 对 SSH socket 的拦截，而不是 TVM 编译失败。

## 对比结果

| 维度 | 旧路径 | 当前 session_bootstrap | 结论 |
|---|---|---|---|
| 远端运行入口 | `tvm_001.py` 直接加载 `./tvm_tune_logs/optimized_model.so` | `run_rpc_tune.sh` 生成 `.so + DB`，再部署到 `REMOTE_TVM_JSCC_BASE_DIR/{tvm_tune_logs,tuning_logs}` | 两边 archive 结构是对得上的 |
| 旧 Phytium compile target | `llvm -mtriple=aarch64-unknown-linux-gnu -mcpu=generic -mattr=+neon` | 2026-03-06 一度写成 `generic + neon + crypto + crc`；2026-03-08 已收敛到 `generic + neon + num-cores=4` | 当前需要向旧路径对齐 `+neon` 证据子集 |
| `mcpu` 具体化 | 旧代码没有使用 `phytium` / `ft2000plus` | 当前 builder 实测也不支持这两个 `mcpu` | 保留 `mcpu=generic` 是合理的 |
| 快测阻断 | 旧 realcmd 曾成功运行 | 本轮 deploy / quick 卡在 SSH socket 被 sandbox 拦截 | 本轮不是 target 编译错误 |

## 关键证据

### 1) 旧 JSCC TVM 运行路径只依赖 `.so`

文件：`/home/tianxing/TVM_LAST/finalWork/服务端/jscc-test/jscc/tvm_001.py`

- 直接从 `./tvm_tune_logs/optimized_model.so` 加载模块；
- 在 JSCC 目录内执行 `relax.VirtualMachine(lib, dev)`；
- 不负责本地 compile / target 决策。

这说明当前 pipeline 只要把新 `.so` 部署回 `REMOTE_TVM_JSCC_BASE_DIR/tvm_tune_logs/optimized_model.so`，就与旧 JSCC 目录结构兼容。

### 2) 旧 JSCC Phytium compile target 已是 `generic + neon`

文件：`/home/tianxing/TVM_LAST/finalWork/服务端/jscc-test/jscc/tvm_optimizer/utils/phytium_config.py`

```python
"llvm -mtriple=aarch64-unknown-linux-gnu -mcpu=generic -mattr=+neon"
```

这与当前 2026-03-08 复核结论一致：

- 保留 `generic`
- 保留 `+neon`
- 不额外声称 `+crypto,+crc`

### 3) 2026-03-06 的本地产物曾使用更激进的 mattr

文件：`session_bootstrap/tmp/rpc_tune_output_20260306_195752/tune_report.json`

记录 target：

```json
{"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"generic","mattr":["+neon","+crypto","+crc"],"num-cores":4}
```

这证明“当前本地产物曾经不是 generic 不够具体，而是 generic 之外还附带了未经本轮 live 取证确认的扩展位”。

### 4) 2026-03-08 的本地重建已切到 evidence-backed target

文件：`session_bootstrap/config/rpc_tune_local.2026-03-08.phytium_pi.env`

```bash
TARGET='{"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"generic","mattr":["+neon"],"num-cores":4}'
```

重建结果文件：`session_bootstrap/tmp/rpc_tune_output_20260308_phytium_target/tune_report.json`

本轮重建命令：

```bash
bash ./session_bootstrap/scripts/run_rpc_tune.sh \
  --env ./session_bootstrap/config/rpc_tune_local.2026-03-08.phytium_pi.env \
  --skip-services \
  --skip-full \
  --runner local
```

结果：

- `optimized_model.so` 重建成功；
- target 落盘为 `generic + neon + num-cores=4`；
- deploy 阶段因 SSH socket 被 sandbox 拦截而失败。

### 5) 本地 LLVM 18 仍不支持 Phytium 专用 `mcpu`

本轮本地验证命令：

```bash
clang --target=aarch64-linux-gnu -mcpu=help
/home/tianxing/.venvs/tvm-ms/bin/python - <<'PY'
import tvm
for s in [
  '{"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"phytium","mattr":["+neon"],"num-cores":4}',
  '{"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"ft2000plus","mattr":["+neon"],"num-cores":4}',
]:
    print(tvm.target.Target(s).export())
PY
```

观察：

- `clang --target=aarch64-linux-gnu -mcpu=help` 列表中没有 `phytium` / `ft2000plus`；
- TVM 同时打印 LLVM 18 警告：这两个 `mcpu` 在 `aarch64-linux-gnu` 下无效，会退回默认 `generic`。

因此：

- **本轮不能合理地把 target 改成更“像飞腾”的伪具体 `mcpu` 名称**；
- 现阶段最稳妥的配置仍是：

```json
{"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"generic","mattr":["+neon"],"num-cores":4}
```

## 本轮修复

### 1) 对齐仍会被使用的 Phytium env

已更新：

- `session_bootstrap/config/rpc_armv8.phytium_pi.2026-03-01.env`
- `session_bootstrap/config/rpc_armv8.phytium_pi.snr_sweep.env`

更新内容：

- 从 `llvm -mtriple=aarch64-linux-gnu -mcpu=generic -mattr=+neon,+crypto,+crc`
- 收敛到 `llvm -mtriple=aarch64-linux-gnu -mcpu=generic -mattr=+neon`

### 2) 修复 `run_rpc_tune.sh` 的 deploy 假成功

文件：`session_bootstrap/scripts/run_rpc_tune.sh`

问题：

- 在 `if deploy_tune_artifacts ...; then` 的上下文中，bash 的 `set -e` 不会帮忙中止函数内部失败命令；
- 导致 SSH 已经失败时，脚本仍打印 `step=deploy_tune_artifacts success`。

修复：

- 对远端 `mkdir` / `cat > dst` 显式检查返回码；
- 三个 artifact copy 任一失败即返回非零；
- 现在会在真实 blocker 处中止，而不是误报 deploy 成功。

## 本轮执行结果

### 本地 artifact 重建

成功文件：

- `session_bootstrap/tmp/rpc_tune_output_20260308_phytium_target/optimized_model.so`
- `session_bootstrap/tmp/rpc_tune_output_20260308_phytium_target/tune_report.json`

最新一次闭环日志：

- `session_bootstrap/logs/rpc_tune_20260308_025045.log`

状态：

- `tune_rc=0`
- `deploy_tune_artifacts failed rc=1`

### 远端 quick 尝试

执行：

```bash
set -a
source ./session_bootstrap/tmp/rpc_tune_output_20260308_phytium_target/rpc_tune_run_20260308_025045.env
set +a
REMOTE_PAYLOAD_LOAD_DB=0 bash ./session_bootstrap/scripts/run_remote_tvm_payload.sh --profile quick --variant current
```

结果：

```text
socket: Operation not permitted
ssh: connect to host 100.121.87.73 port 22: failure
```

结论：

- 本轮**没有跑到飞腾派上的 payload 本体**；
- 已完成到“本地 compile 成功 + 远端第一跳 SSH 明确失败”为止。

## 下一步

拿到可用网络后按下列顺序继续：

1. 先补远端取证：

```bash
bash ./session_bootstrap/scripts/ssh_with_password.sh \
  --host 100.121.87.73 --user user --pass user -- \
  'hostname; whoami; lscpu; echo ---; cat /proc/cpuinfo'
```

2. 再执行当前闭环：

```bash
bash ./session_bootstrap/scripts/run_rpc_tune.sh \
  --env ./session_bootstrap/config/rpc_tune_local.2026-03-08.phytium_pi.env \
  --skip-services \
  --skip-full \
  --runner local
```

3. 若 deploy 成功，再单独补 quick：

```bash
set -a
source ./session_bootstrap/tmp/rpc_tune_output_20260308_phytium_target/rpc_tune_run_<timestamp>.env
set +a
REMOTE_PAYLOAD_LOAD_DB=0 bash ./session_bootstrap/scripts/run_remote_tvm_payload.sh --profile quick --variant current
```
