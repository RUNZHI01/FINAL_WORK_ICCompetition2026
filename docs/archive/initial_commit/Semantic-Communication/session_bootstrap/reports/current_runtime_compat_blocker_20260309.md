# Current Artifact Runtime Compatibility Blocker (2026-03-09)

## Executive summary

Round1 真机 RPC tuning 已经成功：
- tuning 本体跑通
- quick benchmark 跑通
- 产出新的 current artifact：
  - local path: `session_bootstrap/tmp/rpc_tune_output_20260309_real_round1/optimized_model.so`
  - size: ~2.0 MB
  - sha256: `9478c8277b013ccbcae9dabaf72dd123efc7908405a359b951d7c85f780b8df8`

但是，**真实 inference 当前仍被 runtime compatibility 阻断**：
- baseline artifact 可在飞腾派现有可运行 runtime (`venv + tvm_compat_20260306`) 下直接 `load_module -> relax.VirtualMachine -> run`
- round1 current artifact **不能** 在这套 runtime 下进入 `relax.VirtualMachine`
- 失败错误稳定为：
  - `AttributeError: Module has no function 'vm_load_executable'`

结论：
> 当前 round1 产物不是“调优失败”，而是“导出/运行时协议与飞腾派现有可运行 TVM runtime 不兼容”。

---

## Confirmed facts

### 1) 真机 tuning 链路已跑通
- 远端 tracker + 远端 runner + 本地 builder/orchestrator 拓扑可用
- 8-trial smoke 已成功
- 500-trial round1 已成功完成，并新增了少量 tuning records（实际新增约 5 条）

### 2) quick benchmark 已成功，但不能代表 realcmd compatibility
quick 使用的是 payload 路径，主要证明：
- tracker / runner / artifact deploy /远端执行链条正常
- current round1 产物可参与 quick 路径

quick **不等于** legacy realcmd 路径，因为 legacy realcmd 依赖：
- `tvm_002.py`
- 飞腾派上的 legacy/compat runtime
- 该 runtime 对 `.so` / VMExecutable 的解释方式

### 3) baseline/current realcmd 旧实现曾经不可信
`run_remote_legacy_tvm_compat.sh` 原先存在两个严重问题：
1. 不会真的按 baseline/current 切 artifact
2. 没有先 probe `load_module -> relax.VirtualMachine`

现已修复：
- 支持 `REMOTE_BASELINE_ARTIFACT` / `REMOTE_CURRENT_ARTIFACT`
- 真正按 variant 切换远端 artifact
- 先 probe，probe 失败立即退出
- 补了 `tvm.runtime.tensor -> tvm.nd.array` 的 compat shim

### 4) baseline artifact 在飞腾派 compat runtime 下是可执行 VMExecutable
远端（飞腾派）使用：
- `/home/user/venv/bin/tvm_compat_python.sh`
- `PYTHONPATH=/home/user/tvm_compat_20260306/python`
- `TVM_LIBRARY_PATH=/home/user/tvm_compat_20260306/build`

观测到：
- baseline path: `/home/user/Downloads/5.1TVM优化结果/tvm_tune_logs/optimized_model.so`
- `type_key=relax.VMExecutable`
- `imports=1`, imported module type `library`
- `relax.VirtualMachine(lib, dev)` 成功
- legacy realcmd baseline 实测单样本约 `2.7 ~ 3.3 s`

### 5) round1 current artifact 在飞腾派 compat runtime 下不可执行
真正重新部署 round1 current `.so` 后：
- remote current path: `/home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so`
- size: ~2.0 MB
- sha256: `9478c8277b013ccbcae9dabaf72dd123efc7908405a359b951d7c85f780b8df8`

legacy compat probe 明确失败：

```text
[legacy-compat] probe_failed artifact=/home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so
AttributeError: Module has no function 'vm_load_executable'
```

这说明：
- `tvm.runtime.load_module(current_so)` 能加载文件
- 但返回的模块在当前 compat runtime 看来**不是可直接 VM load 的 Executable**
- 因而无法 `relax.VirtualMachine(lib, dev)`

### 6) 本地 TVM 0.24 对同一份 current `.so` 的解释与远端不同
在本地 TVM 0.24 (`.venvs/tvm-ms`) 下，针对同一份 round1 current `.so`：
- `load_module(optimized_model.so)` 后可查询到：
  - `vm_load_executable=True`
  - `stats=True`
  - `as_text=True`
- 也就是说，本地 0.24 明确认它是 VMExecutable 风格对象

但在飞腾派 compat runtime 下：
- baseline `.so` -> `type_key=relax.VMExecutable`
- current `.so` -> 不能走 `vm_load_executable`

这基本坐实：
> 本地 0.24 与远端 compat runtime 对 current artifact 的加载协议/ABI/序列化解释不一致。

---

## Important false-positive we ruled out

曾出现过一次看似“current realcmd 跑得比 baseline 快”的结果（约 `1.84 ~ 1.85 s/sample`）。

后来核对 sha256 发现：
- 远端 baseline `.so` 与远端 current `.so` 当时 hash 完全相同
- 两者都变成了 baseline 的 1.4 MB 版本

原因：
- 中途 legacy baseline 测试把 baseline artifact 复制进了 `jscc/tvm_tune_logs/optimized_model.so`
- 在一次中断/污染后没有及时恢复原 current 文件

因此这次“current 变快”是伪像，不可采信。

---

## What this means

当前阶段已经可以明确区分三个层面：

### A. MetaSchedule tuning 本身
不是 blocker。
- 真机 tuning 已经完成
- round1 current artifact 已成功生成

### B. quick / payload benchmarking
不是 blocker。
- quick 闭环已跑通
- 说明 tracker/runner/deploy/path 都基本正常

### C. realcmd inference on Phytium Pi
**这里才是 blocker。**
- baseline artifact + compat runtime：可运行
- current round1 artifact + compat runtime：不可运行

所以当前问题不是：
- “trial 不够”
- “tune 根本没跑”
- “benchmark 脚本写错了而已”

而是：
> current artifact export format / runtime expectation 与飞腾派现有能稳定运行的 TVM runtime 不匹配。

---

## Most likely root cause

最可信的解释是：
1. 本地 tuning/build 使用的是较新的 TVM 0.24-style Relax/VM toolchain；
2. 飞腾派上唯一稳定可运行的环境是 `tvm_compat_20260306`；
3. 这套 compat runtime 能跑 legacy baseline artifact，但**不能正确解释 round1 current artifact**；
4. 飞腾派上更“新”的 TVM runtime / FFI 组合虽然更接近 current artifact，但一旦真正加载到 compiled core 就触发 `Illegal instruction`，无法成为生产可用运行时。

---

## Recommended next actions

### Option 1 (recommended): rebuild a compatible newer runtime on the Phytium Pi
目标：在飞腾派上得到一套既：
- 不触发 `Illegal instruction`
- 又能正确加载 round1 current artifact

这将是最直接的解法。

建议方向：
- 从与本地 `.venvs/tvm-ms` / `tvm-src` 更匹配的源码出发
- 在飞腾派上重新构建 aarch64 runtime + python bindings + tvm_ffi
- 编译参数尽量保守（避免触发当前 `tvm310` 那套非法指令）
- 验证最小测试：
  - `import tvm`
  - `load_module(current_so)`
  - `relax.VirtualMachine(lib, tvm.cpu(0))`
  - `vm['main'](zero_input)`

### Option 2: attempt compatibility re-export from an older matching TVM toolchain
目标：把 round1 current 调优结果重新导出成 baseline-style、可被 compat runtime 接受的 artifact。

风险：
- 现有 DB / artifact / runtime 版本跨代差异较大
- 这条路未必可行
- 很可能最终仍要回到 Option 1

### Option 3: stop using realcmd current comparisons until runtime is fixed
在 runtime compatibility 修好前：
- quick current/baseline 可继续做 smoke
- 但 realcmd current 结论必须标记为 **blocked by runtime incompatibility**

---

## Current status

- 真机 tuning：**done**
- quick validation：**done**
- legacy baseline realcmd：**works**
- round1 current realcmd：**blocked by runtime incompatibility**

That is the current ground truth.
