# Phytium Pi 真机 RPC 调优 Round 1

更新时间：`2026-03-09`
适用范围：把当前流程从“复用旧 DB 重编译”切换到真正的 MetaSchedule 真机调优。

## 1. 这一轮的目标

这轮不是证明 baseline/current 谁更快，而是先回答两个更基础的问题：

1. `current` 这条 Relax + VM 路线上，**真机 MetaSchedule** 还能不能继续把自己调快；
2. 如果继续加 trial 后收益依然很小，问题更可能在 **runtime / artifact 形态**，而不只是 schedule 搜索预算。

## 2. 这轮和之前最大的区别

之前那套 `rpc_tune_local.2026-03-08.phytium_pi.env` 是：
- `TUNE_TOTAL_TRIALS=0`
- `TUNE_RUNNER=local`

那本质上只是：
- 复用旧 DB
- 本地重编译
- 再做验证

**它不是新的 device-guided tuning。**

这轮改成：
- `TUNE_RUNNER=rpc`
- `TUNE_TOTAL_TRIALS=500`
- `TUNE_MAX_TRIALS_PER_TASK=64`
- `TUNE_NUM_TRIALS_PER_ITER=32`
- `TUNE_SESSION_TIMEOUT=180`
- `TUNE_REQUIRE_REAL=1`

配置文件：
- `session_bootstrap/config/rpc_tune_real.2026-03-09.phytium_pi.env`

当前已验证的可用拓扑不是“本地 tracker + 飞腾派 runner”，而是：
- **远端 tracker（飞腾派）**
- **远端 runner（飞腾派）**
- **本地 builder/orchestrator（笔记本）**

原因：当前 WSL/Tailscale 入站回连不稳定，飞腾派到本地 tracker 的 TCP 建连会超时；改成远端 tracker 后，这个阻断被绕开。

## 3. 推荐执行顺序

### Step 1：先起服务（远端 tracker + 远端 runner）

```bash
bash ./session_bootstrap/scripts/manage_rpc_services.sh \
  --env ./session_bootstrap/config/rpc_tune_real.2026-03-09.phytium_pi.env \
  start-all
```

### Step 2：过 readiness

```bash
bash ./session_bootstrap/scripts/check_rpc_readiness.sh \
  --env ./session_bootstrap/config/rpc_tune_real.2026-03-09.phytium_pi.env
```

重点确认：
- ONNX 文件存在
- 本机 TVM 可用
- tracker 端口可达
- `TUNE_REQUIRE_REAL=1` 与 `runner=rpc / trials>0` 一致
- warm-start DB 路径有效

### Step 3：抽热点 task，不再黑箱调

```bash
/home/tianxing/.venvs/tvm-ms/bin/python \
  ./session_bootstrap/scripts/extract_hotspot_tasks.py \
  --env ./session_bootstrap/config/rpc_tune_real.2026-03-09.phytium_pi.env \
  --top-k 8
```

输出：
- 一个 markdown 报告
- 一个 json 报告
- 一行 `recommended_full_hotspot_tasks=...`

这一步的意义不是马上改 `rpc_tune.py`，而是让后续 full / report / decision 不再完全盲飞。

### Step 4：先跑一轮真实 tune（建议先跳过 full）

```bash
bash ./session_bootstrap/scripts/run_rpc_tune.sh \
  --env ./session_bootstrap/config/rpc_tune_real.2026-03-09.phytium_pi.env \
  --skip-full
```

这轮应该产出：
- 新的 `optimized_model.so`
- 新的 `tuning_logs/`
- `tune_report.json`
- quick 对比结果
- orchestrator summary

## 4. 结果怎么判

### 这是“有效调优”的最低标准

不是只看 baseline/current 比较，而是先看：

1. 这轮是否真的发生了新的 trial；
2. `current_new` 相比 `current_old` 是否有可观提升；
3. quick 是否稳定，不再被 repeated `load_module()` 误导。

### 两种后续分叉

#### 分叉 A：`current` 自己明显变快
说明 MetaSchedule 还有继续挖的空间。

下一步：
- 把总预算从 `500` 增到 `1000 / 2000`
- 用 task extractor 结果收缩热点任务分析
- 比较 round1 / round2 best trace 是否继续变化

#### 分叉 B：`current` 自己几乎不变
说明问题大概率已经不是“trial 不够”。

下一步：
- 转向 runtime / artifact / driver 路径优化
- 做统一 driver 的 phase breakdown
- 判定问题主要在 `vm_run` 还是 host-side pre/post-processing

## 7. 2026-03-09 新 blocker：realcmd runtime compatibility

当前已确认：
- round1 tuning 已成功
- quick 已成功
- legacy baseline realcmd 可运行
- 但 round1 current artifact 在飞腾派现有可运行 runtime (`venv + tvm_compat_20260306`) 下无法进入 `relax.VirtualMachine`
- 稳定错误：`Module has no function 'vm_load_executable'`

因此，**realcmd current 现在的 blocker 不是 tuning budget，而是 runtime compatibility**。

详细证据与后续建议见：
- `session_bootstrap/reports/current_runtime_compat_blocker_20260309.md`

## 5. 当前已知的热点可见性结论

本地样例抽取里，目前模型只提取出 3 个任务：
- `mirror_pad1`（weight=10）
- `mirror_pad2`（weight=1）
- `mirror_pad`（weight=1）

这说明当前模型在这条 Relax 提取路径上，可见任务数本身不多。
**这不是坏消息，反而说明后续分析可以更聚焦。**

## 6. 注意事项

- `TUNE_REQUIRE_REAL=1` 会阻止误用 `runner=local` 或 `trials=0`。
- 如果 readiness 失败在 tracker / runner 可达性，先修服务，不要把失败误判成 tune 无效。
- 如果 round1 完成后 quick 仍然极差，先看 `current_old -> current_new` 的相对变化，再决定是否继续堆 trial。
