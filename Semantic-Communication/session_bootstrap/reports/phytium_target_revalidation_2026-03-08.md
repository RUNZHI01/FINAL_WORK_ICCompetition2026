# Phytium-Pi Target Revalidation（2026-03-08）

## 结论摘要

- **本次未能直接 SSH 复查 `100.121.87.73` 的实时 `lscpu` / `/proc/cpuinfo`**：当前 Codex sandbox 禁止创建外部 socket，SSH 在本地即被拦截。
- 结合 **Phytium-Pi 官方板卡资料** 与 **Phytium E2000Q 官方 SoC 资料**，当前设备应为：
  - **E2000Q**
  - **4× ARMv8 cores**
  - **2× FTC664 + 2× FTC310**
  - 公开确认能力至少包含 **ASIMD / NEON**
- 本地 LLVM 18 / TVM 0.24 builder 进一步验证：`mcpu=phytium` 与 `mcpu=ft2000plus` 在 `aarch64-linux-gnu` 下 **不是有效 LLVM `mcpu` 值**，TVM 会回退到 `mcpu=generic`。
- 因此，本项目本轮采用的修正目标不是“伪装成某个 Cortex/Neoverse”，而是使用**证据约束后的 generic AArch64 target**：

```json
{"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"generic","mattr":["+neon"],"num-cores":4}
```

- 与旧配置相比，主要修正点是：
  1. **保留 `mcpu=generic`**（因为当前 LLVM toolchain 不接受更具体的 Phytium `mcpu` 名）；
  2. **删除无现场证据支持的 `+crypto,+crc`**；
  3. **显式保留 `+neon` 与 `num-cores=4`**。

## 证据

### A. 实时远端复查命令与 blocker

执行命令：

```bash
bash ./session_bootstrap/scripts/ssh_with_password.sh \
  --host 100.121.87.73 --user user --pass user -- \
  'hostname && whoami && date && uname -a'
```

结果：

```text
socket: Operation not permitted
ssh: connect to host 100.121.87.73 port 22: failure
```

结论：

- 不是“密码错误”或“主机拒绝”；
- 是**当前执行环境禁止外部 socket**，因此本轮无法做 live `lscpu` 取证。

### B. 板卡 / SoC 官方资料

- Phytium-Pi 官方板卡页：说明该板卡基于 **E2000Q**。
- E2000Q 官方页：给出 **4 核 Armv8**、**2×FTC664 + 2×FTC310**，并列出 **ASIMD / 浮点**等能力。

参考：

- Phytium-Pi: <https://www.phytium.com.cn/product/show/395.html>
- E2000Q: <https://www.phytium.com.cn/product/show/392.html>

> 以上两条是本轮关于“Phytium-Pi 真实 CPU 族系”的主要依据；
> 由于 live SSH 被 sandbox 拦截，本轮无法补到 `lscpu` 原始输出。

### C. LLVM / TVM 本地证据

#### 1) LLVM 18 支持的 AArch64 `mcpu` 列表里没有 Phytium

执行：

```bash
llc -mtriple=aarch64-linux-gnu -mcpu=help
clang --target=aarch64-linux-gnu -mcpu=help
```

观察：

- 列表包含 `generic`、`cortex-a55`、`cortex-a72`、`neoverse-n1` 等；
- **不包含** `phytium` / `ft2000plus`。

#### 2) TVM 尝试解析 Phytium `mcpu` 时会回退到 generic

执行：

```python
import tvm
for s in [
    '{"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"ft2000plus"}',
    '{"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"phytium"}',
]:
    print(tvm.target.Target(s).export())
```

TVM/LLVM 日志：

```text
Error: Using LLVM 18.1.3 with `-mcpu=ft2000plus` is not valid in `-mtriple=aarch64-linux-gnu`, using default `-mcpu=generic`
Error: Using LLVM 18.1.3 with `-mcpu=phytium` is not valid in `-mtriple=aarch64-linux-gnu`, using default `-mcpu=generic`
```

结论：

- 当前 builder toolchain 下，**“更具体的 Phytium `mcpu` 字符串”并不会真的生效**；
- 若强行写入，只会误导配置阅读者。

## 本轮目标选择

最终采用：

```bash
TARGET='{"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"generic","mattr":["+neon"],"num-cores":4}'
```

原因：

- `mcpu=generic`：是当前 LLVM 18 下的**真实有效值**；
- `+neon`：与官方 E2000Q 资料中的 **ASIMD** 一致；
- `num-cores=4`：与 E2000Q 公开规格一致；
- 不再保留 `+crypto,+crc`：本轮没有 live `lscpu` / `/proc/cpuinfo` 证据支撑，先去掉猜测性特征。

## 本轮脚本 / 配置更新

### 1) warm-start DB 兼容修复

文件：`session_bootstrap/scripts/rpc_tune.py`

问题：

- 旧 tuning DB 中残留 `feature.has_asimd` 等 `feature.*` 字段；
- 在当前 TVM 0.24 / target config 解析链路下，若先 warm-start 再 `tune_relax`，会在 JSONDatabase 初始化前报错。

修复：

- warm-start 复制完 `database_tuning_record.json` 后，**立刻做一次 sanitize**；
- 这样即使 `--total-trials 0`，也能直接基于旧 DB 重编当前 artifact。

### 2) `run_rpc_tune.sh` 增补 current artifact deploy

文件：`session_bootstrap/scripts/run_rpc_tune.sh`

之前的问题：

- 脚本会生成 `TUNE_SO_PATH` / `TUNE_DB_PATH`；
- 但 quick/full 实际探测的仍是 `REMOTE_TVM_JSCC_BASE_DIR` 下的远端工件；
- **没有把新生成的 `.so + database` 部署进去**。

修复后：

- 在 quick/full 之前，自动把：
  - `optimized_model.so`
  - `database_workload.json`
  - `database_tuning_record.json`
- 部署到 `REMOTE_TVM_JSCC_BASE_DIR/{tvm_tune_logs,tuning_logs}`。

### 3) 新配置文件

- `session_bootstrap/config/rpc_armv8.phytium_rpc_tune.env`
- `session_bootstrap/config/rpc_tune_local.2026-03-08.phytium_pi.env`

## 本轮本地工件重建

执行命令：

```bash
set -a && source ./session_bootstrap/config/rpc_tune_local.2026-03-08.phytium_pi.env && set +a
rm -rf "$TUNE_OUTPUT_DIR"
"$LOCAL_TVM_PYTHON" ./session_bootstrap/scripts/rpc_tune.py \
  --onnx-path "$ONNX_MODEL_PATH" \
  --output-dir "$TUNE_OUTPUT_DIR" \
  --target "$TARGET" \
  --tracker-host "$RPC_TRACKER_HOST" \
  --tracker-port "$RPC_TRACKER_PORT" \
  --device-key "$DEVICE_KEY" \
  --total-trials "$TUNE_TOTAL_TRIALS" \
  --input-shape "$TUNE_INPUT_SHAPE" \
  --input-name "$TUNE_INPUT_NAME" \
  --input-dtype "$TUNE_INPUT_DTYPE" \
  --existing-db "$TUNE_EXISTING_DB" \
  --runner local
```

结果：

- output dir: `session_bootstrap/tmp/rpc_tune_output_20260308_phytium_target`
- output so: `session_bootstrap/tmp/rpc_tune_output_20260308_phytium_target/optimized_model.so`
- tuning logs: `session_bootstrap/tmp/rpc_tune_output_20260308_phytium_target/tuning_logs`
- elapsed: **3.6 s**
- sanitized records: **5** 条

说明：

- 本轮是**基于 2026-03-06 旧 Phytium tuning DB 的重编译**；
- 不是一次新的真机测量回合；
- 原因是 live RPC / SSH 被当前 sandbox 拦截。

## quick 结果

### 1) 本轮 remote quick

执行命令：

```bash
set -a && source ./session_bootstrap/config/rpc_tune_local.2026-03-08.phytium_pi.env && set +a
REMOTE_PAYLOAD_LOAD_DB=0 bash ./session_bootstrap/scripts/run_remote_tvm_payload.sh --profile quick --variant current
```

结果：

```text
socket: Operation not permitted
ssh: connect to host 100.121.87.73 port 22: failure
```

状态：**未执行成功（sandbox blocker）**

### 2) 最近一条历史成功 quick（供对照）

文件：`session_bootstrap/reports/quick_rpc_armv8_phytium_realcmd_round1.md`

- baseline: **173616.079 ms**
- current: **256881.177 ms**
- delta: **+83265.098 ms**
- improvement: **-47.96%**

注意：

- 这是 **2026-03-01** 的真实机 quick 结果；
- 使用的还是旧 target：`generic + neon + crypto + crc`；
- 因此它只能作为“最近一次 live quick 参考”，**不是本轮新 target 的验证结果**。

## 下一步（拿到网络后）

1. 先补 live 取证：

```bash
bash ./session_bootstrap/scripts/ssh_with_password.sh --host 100.121.87.73 --user user --pass user -- \
  'hostname; whoami; lscpu; echo ---; cat /proc/cpuinfo'
```

2. 再用新 env 跑闭环：

```bash
bash ./session_bootstrap/scripts/run_rpc_tune.sh \
  --env ./session_bootstrap/config/rpc_tune_local.2026-03-08.phytium_pi.env \
  --skip-full
```

3. 重点确认：

- remote live flags 是否真的包含 `crc` / `crypto`；
- 新 target 下 quick baseline/current 是否优于旧 target；
- deploy 后 remote current archive 是否确实加载的是本轮新 `.so` 与新 DB。
