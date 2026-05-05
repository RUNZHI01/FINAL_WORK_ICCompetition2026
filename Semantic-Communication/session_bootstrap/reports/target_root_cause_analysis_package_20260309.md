# Target 根因分析包（2026-03-09）

## 1) 当前 target 在项目里的所有关键位置
当前真机调优相关配置基本都在使用同一个 target 家族：

```json
{"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"generic","mattr":["+neon"],"num-cores":4}
```

关键位置：
- `session_bootstrap/config/rpc_tune_real.2026-03-09.phytium_pi.env`
- `session_bootstrap/config/rpc_armv8.phytium_rpc_tune.env`
- `session_bootstrap/config/rpc_tune_local.2026-03-08.phytium_pi.env`
- `session_bootstrap/scripts/rpc_tune.py` 只做 `tvm.target.Target(args.target)` 后原样传给 `tune_relax/compile_relax`

结论：当前没有任何设备端自动校准 target 的逻辑。

## 2) baseline/current artifact 可提取的 target / runtime 线索
### 飞腾派 `venv + tvm_compat_20260306`
- baseline:
  - `type_key = relax.VMExecutable`
  - `vm_load_executable = True`
- current:
  - `type_key = library`
  - 缺少 `vm_load_executable`
  - 报错：`Module has no function 'vm_load_executable'`

### 本地 TVM 0.24 (`.venvs/tvm-ms`)
对 round1 current `.so`：
- `vm_load_executable = True`
- `stats = True`
- `as_text = True`

结论：同一份 current artifact，在不同 runtime 栈里被解释成不同对象。问题不能粗暴归因为“0.24dev 版本不稳”，更像是 runtime/ffi/libtvm 栈不一致。

## 3) 飞腾派 CPU / GCC / LLVM 能力探测
### CPU 事实
- `aarch64`
- `4 CPU`
- `1.8GHz`

### `/proc/cpuinfo` features
实际 feature：
- `fp`
- `asimd`
- `aes`
- `pmull`
- `sha1`
- `sha2`
- `crc32`
- `cpuid`
- `sha3`
- `sha512`

并且 CPU part 同时出现：
- `0x303`
- `0x664`

这说明飞腾派并不是一个特别干净、LLVM 直接有专名的同构核配置。

### GCC 默认 target 倾向（飞腾派本机）
- `-march=armv8-a`
- `-mcpu=generic`
- `-mtune=generic`

### 本地 LLVM 18 `-mcpu=help`
可用候选包括：
- `generic`
- `cortex-a53/a55/a72/a76/...`
- `neoverse-n1/n2/...`

但没有明显的 `phytium/ftc664/ftc310` 专名。

## 4) 新的 target 实验矩阵
### 实验 A：当前 control
```json
{"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"generic","mattr":["+neon"],"num-cores":4}
```

### 实验 B：generic + full ISA attrs
```json
{"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"generic","mattr":["+neon","+aes","+pmull","+sha1","+sha2","+crc","+sha3","+sha512"],"num-cores":4}
```
目的：不乱猜具体 `mcpu`，先把飞腾派已确认具备的 ISA 能力显式告诉 LLVM/TVM。

### 实验 C：surrogate microarchitecture
优先先试：
1. `cortex-a55`
2. `neoverse-n1`

不建议一上来全量大跑，而是先做小预算 smoke，观察：
- task 数
- 新增 records
- artifact 大小/形态
- `vm_load_executable` / `type_key`
- quick payload 行为

## 5) 明确下一轮该先试哪两个 target
### 第一优先
`generic + full ISA attrs`

### 第二优先
`cortex-a55`

原因：
- `generic + full ISA attrs` 是最低风险、信息增量最大的第一步
- `cortex-a55` 是 LLVM 已支持的更具体 surrogate，比直接猜 vendor 私有 `mcpu` 更稳

## 6) 我已经落下来的可跑配置
- `session_bootstrap/config/rpc_tune_target_fullisa.2026-03-09.phytium_pi.env`
- `session_bootstrap/config/rpc_tune_target_cortex_a55.2026-03-09.phytium_pi.env`

这两份都是小预算 smoke：
- `TUNE_TOTAL_TRIALS=64`
- `TUNE_MAX_TRIALS_PER_TASK=16`
- `TUNE_NUM_TRIALS_PER_ITER=8`

目标是先回答：
1. task / records / artifact 形态会不会因为 target 改变而明显变化
2. `generic + full ISA attrs` 与 `cortex-a55` 哪个更值得进入下一轮正式调优

## 7) 建议的执行顺序
1. 先用这两份 env 跑两轮小预算 smoke
2. 对比：
   - task 数
   - 新增 records
   - 输出 `.so` 大小
   - `vm_load_executable` / `type_key`
   - quick 行为
3. 如果 `full ISA attrs` 已明显改变 artifact / records 行为，再决定要不要继续更具体的 surrogate 或重回 runtime 栈排查
