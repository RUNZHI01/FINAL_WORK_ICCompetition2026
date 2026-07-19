# TVM Handwritten 算子优化经验教训

> 本文档总结了 2026-03-31 ~ 2026-04-03 期间在飞腾派 (Phytium Pi) 上对 TVM Relax 端到端模型做 handwritten post-db 算子替换的全部经验教训。
> 用途：作为 Codex 执行同类任务时的 prompt 上下文来源。

---

## 1. 硬件参数（不可省略）

| 参数 | 值 |
|---|---|
| SoC | Phytium Pi (飞腾派) |
| CPU | FTC663, Cortex-A72 兼容, 4 核 |
| ISA | aarch64, NEON (ASIMD) |
| L1d | **32 KB**（关键瓶颈） |
| L1i | 48 KB |
| L2 | 1 MB (shared) |
| 内存 | 4 GB LPDDR4 |
| TVM target | `{"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon"],"num-cores":4}` |
| 编译主机 | Snapdragon aarch64（本机编译，非交叉编译） |
| 板端 TVM | `tvm_samegen_20260307`（source-only build，无 LLVM codegen，只能 load 预编译 .so） |

### 对优化决策的影响
- L1d 仅 32KB：任何超过 32KB 的中间数组都会溢出到 L2
- 算子 input shape 中 `256×256 = 256KB/channel` 远超 L1d → 必须考虑内存流量
- `128×128 = 64KB/channel` 刚好超过 L1d → 处于边界
- `32×32 = 4KB/channel` 完全在 L1d → 可以激进优化计算密度

---

## 2. 工程流水线（必须遵守的安全规则）

### 2.1 编译流水线
```
ONNX → load_onnx_to_relax → preprocess_for_meta_schedule
→ [替换 PrimFunc] → compile_relax(database=MS_DB) → export_library(.so)
```

关键 API：
- `preprocess_for_meta_schedule()` 会暴露所有 PrimFunc 为 GlobalVar（`LegalizeOps → FuseOps → FuseTIR`）
- `compile_relax()` 接受预处理后的 IRModule + MS database
- PrimFunc 替换必须在 `preprocess_for_meta_schedule` **之后**、`compile_relax` **之前**
- 替换方法：`mod.update_func(mod.get_global_var(op_name), new_func)`

### 2.2 @I.ir_module 加载限制
TVM 0.24 的 `@I.ir_module` 装饰器需要：
- `__file__` 在 exec 的 globals 中
- `sys.modules[mod.__module__]` 已注册

正确加载方式：
```python
mod_name = f'_load_{op_name}'
with open(tir_path) as f:
    src = f.read()
ns = {"__file__": str(tir_path.resolve()), "__name__": mod_name}
sys.modules[mod_name] = type(sys)("tir_loader")
sys.modules[mod_name].__file__ = str(tir_path.resolve())
exec(compile(src, str(tir_path), "exec"), ns)
ir_mod = ns["Module"]
```

`importlib` 和 `runpy` **不可用**（@I.ir_module 会检查 module 注册）。

### 2.3 板端 API 差异
板端 TVM (`tvm_samegen_20260307`) 是较新版本，API 与本地不同：
- ❌ `tvm.nd.array()` → 用 `tvm.runtime.tensor()`
- ❌ `result.asnumpy()` → 用 `result.numpy()`
- ❌ `tvm.build()` 板端不可用（无 LLVM） → 必须本地编译后上传 .so
- ✅ `tvm.runtime.load_module(so_path)` 加载预编译 .so
- ✅ `relax.VirtualMachine(lib, dev)` 创建推理 VM

### 2.4 安全规则（不可违反）
1. **永不修改 Trusted Current** — 编译前后必须 SHA-256 验证
2. 所有输出到独立时间戳目录
3. SSH 凭据只通过 `ssh_with_password.sh` 传递，不硬编码
4. 板端 benchmark 通过 wrapper 脚本上传执行（避免 shell quoting 问题）

---

## 3. 核心经验教训

### 3.1 ⚠️ Welford 在大 shape 上是陷阱

**教训**：Welford 单遍方差算法在 microbenchmark 中看起来很好（32×32: -73.7%），但在全模型 e2e 中灾难性回退（+4.6%）。

**根因**：Welford 的逐元素除法 `delta / count` 阻止了 LLVM 的 NEON 自动向量化。在大 shape（128×128+）上，向量化带来的收益远超内存流量节省。

| Shape | 每通道大小 vs L1d | Welford microbenchmark | 全模型 e2e |
|---|---|---|---|
| 32×32 (4KB) | 远小于 32KB | -73.7% ✅ | **+4.6% ❌** |
| 128×128 (64KB) | 2× L1d | +49% ❌ | — |
| 256×256 (256KB) | 8× L1d | +291% ❌ | — |

**规则**：Welford **不应用于**空间维度 ≥ 128 的 reduction 算子。两遍扫描虽然内存流量大，但 LLVM 可以自动 NEON vectorize。

### 3.2 scope="local" 是低风险高回报

**教训**：给累加器 buffer 标注 `scope="local"` 让 TVM/LLVM 将其保持在寄存器或栈上，避免全局内存往返。

效果：variance3 v1.1 仅添加 `scope="local"` → microbenchmark -22.2%，e2e +0.39%（中性偏正）。

**规则**：所有 reduction 算子的中间累加器（sum、M2、count 等）都应标注 `scope="local"`。这是零风险改动。

### 3.3 循环融合在 memory-bound 算子上有效

**教训**：mean4 将 5 个独立 elementwise 循环融合为 1 个，内存流量从 ~31MB 降到 ~6MB。

效果：microbenchmark -8.8%，e2e **-3.26%**（本次最佳单算子收益）。

**实现方式**：
- 将 per-channel 参数（mean, std, weight, bias）stage 到 `scope="local"` 缓冲区
- 在 channel 维度外循环中加载参数一次
- 内循环做 `((input - mean) / std) * weight + bias, relu` 一步完成

**规则**：当连续 5+ 个 elementwise 操作处理同一 tensor 时，融合循环。前提是 per-channel 参数可以 stage 到 local buffer。

### 3.4 ⚠️ Microbenchmark 不能直接预测 e2e 收益

**教训**：单个算子的 microbenchmark 百分比收益会被全模型稀释甚至反转。

本次案例：
- variance1 microbenchmark -73.7% → e2e +4.6%
- mean4 microbenchmark -8.8% → e2e -3.26%

**根因**：
1. 单算子时间占比小（全模型 250ms 中 variance/mean 可能只占 10-15ms）
2. 替换后的代码模式可能影响 LLVM 对上下游算子的调度/向量化
3. Microbenchmark 用随机输入，不触发真实数据分布

**规则**：microbenchmark 用于**淘汰**明显差的候选（> +10% 回退），但不能作为**选择**依据。最终决策必须基于逐算子 A/B e2e 测试。

### 3.5 逐算子 A/B 测试是必须的

**教训**：3 个算子一起集成时 e2e +1.99%，但逐个测试发现只有 variance1 是罪魁祸首。去掉后变成 -1.22%。

**规则**：每引入一个新算子替换，必须单独做 A/B e2e 测试，不能只看 microbenchmark 或全部一起测。

---

## 4. 正确的优化决策流程

```
1. 识别 hotspot → 选择 reduction/elementwise 算子
2. 创建 TIR scheduled-form 候选（@I.ir_module class Module）
3. 本地编译为 cortex-a72 .so（importlib 不可用，用 exec+sys.modules hack）
4. 上传板端做 microbenchmark（30 样本，对比默认 schedule）
5. 淘汰 microbenchmark 回退 > +10% 的候选
6. 对剩余候选做逐算子 A/B e2e 测试
7. 只保留 e2e 正收益的候选
8. 组合所有正收益候选做最终 e2e 验证
9. SHA-256 记录，独立目录，可随时回退
```

---

## 5. TIR 编写注意事项

### 5.1 Buffer 命名必须与原始 scheduled form 一致
全模型中 PrimFunc 的 buffer 名称（如 `lv335`, `lv340`, `compute_intermediate`）是在 `preprocess_for_meta_schedule` 阶段由 TVM 自动生成的。替换时函数签名必须匹配这些名称。

**获取方法**：
```python
from relax_ms_utils import load_onnx_to_relax, preprocess_for_meta_schedule
mod = preprocess_for_meta_schedule(load_onnx_to_relax(...))
func = mod[mod.get_global_var("target_op_name")]
print(func)  # 查看完整签名和 buffer 名称
```

### 5.2 division 常量必须精确
- variance3: `16384.0` (= 128×128)
- variance4: `65536.0` (= 256×256)
- variance1: `1024.0` (= 32×32)
- mean4: `65536.0` (= 256×256)
- eps: `9.9999997473787516e-06`（float32 精度的 1e-5）

### 5.3 axis.remap 的 S/R 标注
- `S` = spatial（绑定到外层循环）
- `R` = reduction（绑定到内层循环，参与 init/update）
- `SSSSRR` = 4 个 spatial + 2 个 reduction

### 5.4 sblock 是 TVM 0.24 的调度原语
`with T.sblock("name")` 用于标记调度块，替代旧版 TVM 的 `compute_at`/`rfactor`。每个 reduction 或 elementwise 操作都应包在 sblock 中。

---

## 6. 不要做的事

1. **不要用 Welford 替代大 shape 的两遍 variance**（≥128×128）
2. **不要用 importlib 加载 @I.ir_module 文件**（用 exec + sys.modules）
3. **不要在板端做 TVM 编译**（板端无 LLVM codegen）
4. **不要修改 Trusted Current**（SHA 验证前后必须一致）
5. **不要跳过逐算子 A/B 测试**（microbenchmark 会骗人）
6. **不要用 `tvm.nd.array()` 在板端**（用 `tvm.runtime.tensor()`）
7. **不要用 `result.asnumpy()` 在板端**（用 `result.numpy()`）
8. **不要在 shell heredoc 中传递复杂环境变量到 SSH**（上传 wrapper 脚本到板端执行）

---

*最后更新：2026-04-03*
*Commits: 353696f, 4a79ccb, c5cf3d5*
*报告: session_bootstrap/reports/opus_candidate_microbenchmark_results_20260403.md*
*Opus 方案: session_bootstrap/reports/opus_optimization_breakthrough_plan_20260403.md*
