# `fused_conv2d_transpose1_add9` 手写算子深度优化方案

- 日期：2026-03-31
- 项目：tvm-飞腾派项目
- 工作区：`/home/tianxing/tvm_metaschedule_execution_project`
- 目标算子：`fused_conv2d_transpose1_add9`
- 本文档用途：**给后续 agent 执行的完整操作规格书**，每一阶段都有明确的输入/输出/验证标准

---

## 0. 核心事实总表（agent 必须先读）

### 0.1 硬件平台

| 属性 | 值 |
|---|---|
| 平台 | 飞腾派（Phytium Pi） |
| CPU | Cortex-A72 × 2 (big) + Cortex-A55 × 2 (LITTLE) |
| SIMD | NEON 128-bit（4 × float32） |
| L1 数据缓存 | 32 KB / 核（Cortex-A72） |
| L2 缓存 | 512 KB — 1 MB（共享） |
| num-cores | 4 |
| TVM target | `{"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon"],"num-cores":4}` |
| TVM 版本 | 0.24.dev0 |
| Python | 3.10 (conda `tvm310_safe`) |

### 0.2 算子规格

| 参数 | 名称 | 形状 | dtype |
|---|---|---|---|
| 输入 | `lv318` | `(1, 48, 64, 64)` | float32 |
| 权重 | `param_0` | `(48, 24, 3, 3)` | float32 |
| 偏置 | `lv320` | `(1, 24, 1, 1)` | float32 |
| 输出 | `T_add_intermediate` | `(1, 24, 128, 128)` | float32 |

**语义：** 这是一个 transposed convolution (stride=2, padding=1, kernel=3×3) + bias add 的融合算子。

### 0.3 当前性能基线

| 基线 | payload | e2e | SHA |
|---|---|---|---|
| trusted current（正式最优） | 130.219 ms | 230.339 ms/image | `6f236b07...` |
| best staging candidate（handwritten 线对照） | 159.943 ms | — | `5bd14b9f...` |

### 0.4 该算子在 profiling 中的地位

| rank | 算子名 | 耗时 (μs) | 占比 |
|---|---|---|---|
| **1** | **fused_conv2d_transpose1_add9** | **24275** | **14.6%** |
| 2 | fused_conv2d_transpose2_add12 | 20234 | 12.2% |
| 3 | fused_conv2d_transpose_add6 | 17385 | 10.5% |
| 4 | fused_conv2d3_add15 | 11800 | 7.1% |
| 5 | fused_mean4_subtract4...relu3 | 11066 | 6.7% |

**Top-3 算子全部是 conv2d_transpose 类型，合计占比 37.2%。** 本算子是单个最大热点。

### 0.5 算子计算流程（原始 unscheduled TIR）

```
Step 1: data_dilate    (1,48,64,64) → (1,48,127,127)    上采样：偶数位填原值，奇数位填 0
Step 2: data_pad       (1,48,127,127) → (1,48,130,130)  四周各补 1 行/列 padding=0
Step 3: kernel_transform (48,24,3,3) → (24,48,3,3)      转置+翻转 weight
Step 4: compute        卷积累加 → (1,24,128,128)         24 out_ch × 48 in_ch × 3×3 kernel
Step 5: T_add          加偏置 → (1,24,128,128)           output += bias
```

### 0.6 当前已有 v1 改动总结

v1 working copy 已做的改动（从 scheduled reference seed 出发）：
- `compute_init` 中直接写入 `bias` 值（而非 0.0）
- `compute_update` 直接累加到最终输出 `T_add_intermediate`
- **删除** `compute_intermediate` buffer 分配（省 ~1.5 MB）
- **删除** 尾部 `T_add` pass（省一次完整输出遍历）

v1 状态：**本地 build 成功，未经远端性能验证**

### 0.7 关键文件路径

| 用途 | 路径 |
|---|---|
| 原始 unscheduled seed | `session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_editable_seed_tir.py` |
| post-db scheduled reference seed（冻结） | `session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_post_db_scheduled_reference_seed_tir.py` |
| v1 working copy TIR（可编辑） | `session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v1_working_copy_tir.py` |
| v1 working copy manifest | `session_bootstrap/handwritten/fused_conv2d_transpose1_add9/scheduled_form_candidate_v1_working_copy_manifest.json` |
| v1 candidate entrypoint | `session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v1.py` |
| 本地 build 脚本 | `session_bootstrap/scripts/run_transpose1_post_db_local_build.py` |
| 本地 build+sync 脚本 | `session_bootstrap/scripts/run_transpose1_post_db_local_build_and_sync.py` |
| schedule-preserving seam 探针 | `session_bootstrap/scripts/probe_transpose1_schedule_preserving_seam.py` |
| best staging task summary | `session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/task_summary.json` |
| best staging tuning DB | `session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/tuning_logs` |
| TVM Python venv | `/home/tianxing/.venvs/tvm-ms/bin/python` |

---

## 1. 优化策略总览

按**风险递增、收益递增**的顺序排列：

| 阶段 | 名称 | 核心思路 | 预期收益 | 风险 |
|---|---|---|---|---|
| P0 | v1 性能验证 | 先把已有 v1 的性能数字拿到 | 确认 bias fusion 收益 | 极低 |
| P1 | dilate+pad 融合 | 合并两个中间 buffer 为一个 | 省 ~1.5 MB 内存 + 1 遍扫描 | 低 |
| P2 | tiling 调优 | 按 Cortex-A72 L1/L2 调 tile 因子 | 提升缓存命中率 | 中 |
| P3 | 跳过 dilate 物化 | 在 compute 中直接用 stride 索引读原始输入 | 省 ~6.3 MB 中间 buffer + 2 遍扫描 | 中高 |
| P4 | NEON intrinsic 微优化 | 手动 4-wide 向量化关键路径 | 提升 SIMD 利用率 | 中 |

**建议执行顺序：P0 → P1 → P3 → P2 → P4**

每个阶段**必须**经过：本地 build 验证 → 远端部署 → payload benchmark → 结果记录，才能进入下一阶段。

---

## 2. 阶段 P0：v1 性能验证

### 2.1 目标

拿到 v1（bias fusion）的真实远端 payload 数字，确认 v1 是否比 reference staging (`5bd14b9f...`) 更快或至少持平。

### 2.2 前置条件

- v1 本地 build 已成功（`swap_succeeded=true`, `build_status=built`）
- artifact SHA: `4f0986e4806bece9801ab38b4ec121870406476c3d9a1c870bbc0453e18ef2fc`

### 2.3 操作步骤

```bash
# Step 1: 确认本地 build 仍然通过
python3 ./session_bootstrap/scripts/run_transpose1_post_db_local_build.py \
  --output-dir ./session_bootstrap/tmp/transpose1_post_db_swap_local_build_v1

# Step 2: 部署到飞腾派远端并运行 payload benchmark
# 需要把 v1 artifact (.so) 通过 SCP 传到飞腾派
# 然后在远端跑 benchmark，参照现有的 run_remote_current_real_reconstruction.sh

# Step 3: 记录结果
```

### 2.4 判定标准

| 条件 | 动作 |
|---|---|
| v1 payload ≤ reference staging (159.943 ms) | 继续 P1 |
| v1 payload 在 staging ±5% 以内 | 继续 P1（bias fusion 本身不增加计算量，持平合理） |
| v1 payload 明显高于 staging (>10%) | 排查 build path 是否有问题，暂停推进 |

### 2.5 输出文件

- benchmark report: `session_bootstrap/reports/transpose1_v1_remote_benchmark_YYYYMMDD_HHMM.md`
- 记录 v1 artifact SHA, payload median, payload variance

---

## 3. 阶段 P1：dilate + pad 融合

### 3.1 问题分析

当前 scheduled form 中，`data_dilate` 和 `data_pad` 是两个**独立物化**的中间 buffer：

```
data_dilate: (1, 48, 127, 127) = 387,096 floats ≈ 1.51 MB
data_pad:    (1, 48, 130, 130) = 811,200 floats ≈ 3.17 MB
```

`data_pad` 的计算仅依赖 `data_dilate`，语义是：在 dilated 数据的四周各补 1 行/列的 0。

两者可以合并为一个 `data_dilate_pad` buffer，直接从原始输入 `lv318` 计算得到 padded-dilated 结果。

### 3.2 融合后的语义

新 buffer: `data_dilate_pad: (1, 48, 130, 130)`

对于位置 `(b, c, h, w)`，值为：

```python
# h, w 的有效范围: [0, 130)
# 去掉外围 pad 后 dilated 坐标: dh = h - 1, dw = w - 1
# dh, dw 的有效范围: [0, 127)
# 只有 dh % 2 == 0 且 dw % 2 == 0 时，映射回原始输入的 (dh // 2, dw // 2)
# 其余位置（pad 区域 / 奇数位 dilate）= 0.0

if 1 <= h < 128 and 1 <= w < 128:
    dh, dw = h - 1, w - 1
    if dh % 2 == 0 and dw % 2 == 0:
        value = lv318[b, c, dh // 2, dw // 2]
    else:
        value = 0.0
else:
    value = 0.0
```

### 3.3 需要改动的 TIR 代码

在 v1 working copy TIR 中：

1. **删除** `data_dilate = T.alloc_buffer((1, 48, 127, 127))` 行
2. **替换** `data_pad = T.alloc_buffer((1, 48, 130, 130))` 为 `data_dilate_pad = T.alloc_buffer((1, 48, 130, 130))`
3. **删除**整个 `data_dilate` 的计算 sblock
4. **替换**整个 `data_pad` 的计算 sblock 为融合版本
5. **更新** compute 中所有对 `data_pad` 的读取为 `data_dilate_pad`

### 3.4 融合后的 sblock TIR 模板

下面是融合后 `data_dilate_pad` sblock 的核心逻辑（需适配到当前 scheduled tile 结构中）：

```python
# 替换原来的 data_dilate + data_pad 两个 sblock 为单个 sblock
for ax0, ax1, ax2 in T.grid(T.int64(1), T.int64(48), T.int64(66)):
    for ax3_fused in T.vectorized(T.int64(10)):
        with T.sblock("data_dilate_pad"):
            v_i0 = T.axis.spatial(T.int64(1), ax0)
            v_i1 = T.axis.spatial(T.int64(48), ax1)
            v_i2 = T.axis.spatial(T.int64(130),
                b_0_c_0_h_0_w_0_fused_fused_fused // T.int64(16) * T.int64(64) + ax2)
            v_i3 = T.axis.spatial(T.int64(130),
                b_0_c_0_h_0_w_0_fused_fused_fused % T.int64(16) * T.int64(8) + ax3_fused)
            T.reads(lv318[v_i0, v_i1, ...])  # 条件读取
            T.writes(data_dilate_pad[v_i0, v_i1, v_i2, v_i3])
            # 融合条件：pad 边界 + dilate 奇偶
            dh = v_i2 - T.int64(1)
            dw = v_i3 - T.int64(1)
            data_dilate_pad[v_i0, v_i1, v_i2, v_i3] = T.if_then_else(
                T.int64(1) <= v_i2 and v_i2 < T.int64(128)
                and T.int64(1) <= v_i3 and v_i3 < T.int64(128)
                and dh % T.int64(2) == T.int64(0)
                and dw % T.int64(2) == T.int64(0),
                lv318[v_i0, v_i1, dh // T.int64(2), dw // T.int64(2)],
                T.float32(0.0)
            )
```

### 3.5 风险与验证

**风险：**
- tile 边界条件可能需要调整 `T.where` guard
- 原 scheduled form 中 `data_dilate` 和 `data_pad` 的 tile 循环结构不同，需要对齐

**验证：**
1. 本地 build 成功
2. 用随机输入对比 reference seed 输出是否 bitwise identical（或 allclose with atol=0）
3. 远端 benchmark

### 3.6 预期收益

- 省 1 个 ~1.5 MB 中间 buffer（`data_dilate`）
- 省 1 次完整遍历（原来 dilate 的 48 × 127 × 127 ≈ 387K 写 + 387K 读）
- 对缓存压力有直接改善

### 3.7 输出文件

- 新 TIR: 更新 `fused_conv2d_transpose1_add9_scheduled_form_candidate_v1_working_copy_tir.py`
- 新 manifest: 更新 `scheduled_form_candidate_v1_working_copy_manifest.json`（sha + change description）
- benchmark report

---

## 4. 阶段 P2：Cortex-A72 感知 tiling 调优

### 4.1 问题分析

当前 scheduled form 的 tile 结构：

```
outer parallel:  32 tiles (b_0_c_0_h_0_w_0_fused_fused_fused)
  → h_tile = 2 groups (上半/下半各 64 行)
  → w_tile = 16 groups (每组 8 列)

c_1 = 6 (output channel split: 24 / 6 = 每批 4 channel)

compute tile:
  h_1 × w_1 = 2 × 2 (子 tile)
  h_2 = 16, h_3 = 2 → 每子 tile 32 行
  c_3 = 4 → 每批 4 output channel
  w_3 = 4 (vectorized) → 4 float32 = 128-bit NEON

reduction:
  dc_0 = 12, dc_1 = 4 → 48 input channels
  dh_1 = 3, dw_1 = 3 → 3×3 kernel
```

### 4.2 缓存分析

**当前每个 compute tile 的工作集估算：**

每次 compute_update 内层 (h_2=16, h_3=2, w_3=4, c_3=4):
- 输出 tile: 4 ch × 32 rows × 4 cols = 512 floats = 2 KB
- data_pad 读取 tile: 1 ch × (32+2) rows × (4+2) cols = 204 floats/ch, × 4 ch (dc_1=4) = 816 floats ≈ 3.2 KB
- kernel 读取: 4 × 4 × 3 × 3 = 144 floats = 576 B

单次内层工作集 ≈ 5.8 KB，**可以放入 L1 (32 KB)**。

但 dc_0=12 的循环意味着 12 轮 reduction，每轮换 4 个 input channel → data_pad 访问跨度大。

### 4.3 可调优项

| 参数 | 当前值 | 调优方向 | 理由 |
|---|---|---|---|
| `pragma_auto_unroll_max_step` | 32 | 试 64 或 16 | 平衡指令缓存 vs 循环开销 |
| w_3 (vectorized width) | 4 | 保持 4 | 已匹配 NEON 128-bit |
| h_2 × h_3 (空间 tile) | 16 × 2 = 32 行 | 试缩小到 16 或 8 | 减小 data_pad 读取跨度 |
| dc_0 × dc_1 (channel reduction split) | 12 × 4 | 试 6 × 8 或 16 × 3 | 改变 channel 访问局部性 |
| c_1 × c_3 (output channel split) | 6 × 4 | 试 3 × 8 | 增大输出 tile 提高写入效率 |

### 4.4 操作方法

**不需要改动算子语义**，只需要调整 scheduled TIR 中的 tile 因子和 loop 注解。这属于 "schedule-level" 改动。

具体做法：在 v1 working copy TIR 中修改以下常量：
- `T.parallel(T.int64(32))` 中的 32（并行 tile 数）
- `c_1` 的 `T.int64(6)` / `c_3` 的 `T.int64(4)` 等 grid 尺寸
- `h_2` 的 `T.int64(16)` / `h_3` 的 `T.int64(2)` 等空间 tile
- `dc_0` 的 `T.int64(12)` / `dc_1` 的 `T.int64(4)` 等 reduction split
- `pragma_auto_unroll_max_step` 的值

### 4.5 约束条件

改 tile 因子时必须保证：
1. **因子乘积不变**：c_1 × c_3 = 24, dc_0 × dc_1 = 48, h tile factors 覆盖 128 行, w tile factors 覆盖 128 列
2. **并行度合理**：outer parallel tiles 不应小于核数 (4)，也不应大到导致 tile 过小
3. **vectorized width** 必须是 4 的倍数（NEON float32）

### 4.6 风险与验证

风险较低：tile 改动不影响计算正确性，只影响访存模式。验证方法同 P1。

---

## 5. 阶段 P3：跳过 dilate 物化，直接 stride 索引

### 5.1 核心思路

transposed convolution 的 dilate+pad+conv 等价于一个**直接在原始输入上以 stride 索引**的卷积。当前的 3 步（dilate → pad → conv）可以压缩为 1 步。

关键洞察：在 `data_pad` 的 (1, 48, 130, 130) 中，75% 的值是 0（dilate 填充 + pad 填充）。对这些 0 值做乘加是完全浪费的。

### 5.2 数学等价变换

原始 compute:
```
output[b, oc, oh, ow] = bias[oc] + Σ_{ic,kh,kw} data_pad[b, ic, oh+kh, ow+kw] * kernel[oc, ic, kh, kw]
```

其中 `data_pad[b, ic, h, w]` 只在 `h-1` 和 `w-1` 都是偶数时非零，等于 `lv318[b, ic, (h-1)//2, (w-1)//2]`。

因此可以改写为：只遍历使 `data_pad` 非零的 `(kh, kw)` 组合：

```
对于 oh, ow, kh, kw:
  padded_h = oh + kh          # [0, 130) 中的坐标
  dilated_h = padded_h - 1    # [0, 127) 中的坐标，需要在 [0, 126] 范围内
  如果 dilated_h >= 0 且 dilated_h < 127 且 dilated_h % 2 == 0:
    input_h = dilated_h // 2  # 原始输入行号
    （类似处理 w 方向）
    output[b, oc, oh, ow] += lv318[b, ic, input_h, input_w] * kernel[oc, ic, kh, kw]
```

对于 3×3 kernel 和 stride=2，每个输出位置 `(oh, ow)` 实际上只有 `ceil(3/2) × ceil(3/2) = 4` 个非零乘加（而非 9 个）。

### 5.3 预期收益

- **消除** `data_dilate` buffer (1.5 MB) 和 `data_pad` buffer (3.2 MB)
- **消除** 两次完整的 data 前处理遍历
- **减少** compute 中 ~56% 的无效乘加（9 → 4 per output element）
- 总内存节省 ~4.7 MB，计算量减少约一半

### 5.4 实现方式

这是最激进的改动。有两种实现路径：

**路径 A：保持 scheduled loop nest，只替换 data 读取逻辑**
- 在 `compute_update` sblock 中，将 `data_pad[..., v_h + v_dh, v_w + v_dw]` 替换为条件表达式
- 条件：判断 `(v_h + v_dh - 1)` 和 `(v_w + v_dw - 1)` 是否偶数且在范围内
- 满足时读 `lv318[..., (v_h + v_dh - 1) // 2, (v_w + v_dw - 1) // 2]`
- 不满足时跳过（乘 0）
- **优点**：改动最小，保持现有 tile 结构
- **缺点**：仍然遍历所有 9 个 kernel 位置，只是把乘加变成条件操作

**路径 B：重写 compute 循环，只遍历有效 kernel 位置**
- 将 3×3 kernel 的遍历改为只访问非零位置
- 需要对 oh/ow 的奇偶性分别处理
- **优点**：真正减少计算量
- **缺点**：改动大，需要重新设计 tile 结构

**推荐：先用路径 A 验证正确性和基本收益，再考虑路径 B。**

### 5.5 路径 A 的具体 TIR 改动

```python
# 在 compute_update sblock 中：
# 原来：data_pad[v_b, v_dc, v_h + v_dh, v_w + v_dw] * kernel_transform[v_c, v_dc, v_dh, v_dw]
# 改为：
ph = v_h + v_dh          # padded 坐标
pw = v_w + v_dw
dh = ph - T.int64(1)     # dilated 坐标
dw = pw - T.int64(1)
# 非零条件
valid = (T.int64(0) <= dh) and (dh < T.int64(127)) and (dh % T.int64(2) == T.int64(0)) \
    and (T.int64(0) <= dw) and (dw < T.int64(127)) and (dw % T.int64(2) == T.int64(0))

T_add_intermediate[v_b, v_c, v_h, v_w] += T.if_then_else(
    valid,
    lv318[v_b, v_dc, dh // T.int64(2), dw // T.int64(2)] * kernel_transform[v_c, v_dc, v_dh, v_dw],
    T.float32(0.0)
)
```

同时删除 `data_dilate` 和 `data_pad` 的 buffer 分配和计算 sblock。

### 5.6 风险与验证

**风险：**
- 条件分支可能影响 NEON 向量化效率
- 原 scheduled tile 结构中 data_pad 的 tile 边界预计算将失去意义
- 路径 A 中 `T.if_then_else` 仍然会执行乘法（只是乘 0），编译器可能/可能不会优化掉

**验证：**
1. 本地 build 成功
2. 数值正确性（与 reference seed 输出逐元素比较）
3. 远端 benchmark

---

## 6. 阶段 P4：NEON 微优化

### 6.1 思路

在 P1-P3 的结构优化之后，如果仍有收益空间，可以：

1. **调整 vectorized width**：当前 w_3=4 已经是 NEON float32 的自然宽度，但可以试 8（两个 NEON 寄存器背靠背）
2. **调整 unroll 深度**：在内层 reduction 循环上尝试不同的 unroll step
3. **数据预取**：在 TIR 中添加 `T.prefetch` hint（如果 TVM 支持的话）

### 6.2 操作

这些是参数级调整，在前序阶段完成后根据 benchmark 数据决定是否需要。

---

## 7. 执行流程规范（agent 必须遵循）

### 7.1 每个阶段的标准流程

```
1. 在 v1 working copy TIR 上做改动
2. 更新 manifest JSON（sha256 + change description）
3. 本地 build 验证：
   python3 ./session_bootstrap/scripts/run_transpose1_post_db_local_build.py \
     --output-dir ./session_bootstrap/tmp/transpose1_post_db_swap_local_build_<version>
4. 确认 build 成功（swap_succeeded=true, build_status=built）
5. [如有条件] 数值正确性验证
6. [如有条件] 远端部署 + benchmark
7. 写 report 到 session_bootstrap/reports/
8. 提交到 git
```

### 7.2 文件命名规范

- working copy TIR 只有一份，原地更新
- 每个阶段的 build 产物放到独立目录（加版本后缀）
- benchmark report 命名：`transpose1_<version>_<what>_YYYYMMDD_HHMM.md`

### 7.3 回退规范

- scheduled reference seed（`*_post_db_scheduled_reference_seed_tir.py`）**始终冻结不动**
- 如果某个阶段改动导致 build 失败或性能退步，从 reference seed 重新派生 working copy
- 使用 `refresh_fused_conv2d_transpose1_add9_scheduled_form_working_copy.py --allow-overwrite` 回退

### 7.4 Git 提交规范

每个阶段完成后提交一次，message 格式：

```
Apply transpose1 scheduled-form <version> edit: <one-line summary>
```

---

## 8. 优先级排序与时间估算

| 阶段 | 预计工作量 | 预计收益 | 优先级 |
|---|---|---|---|
| P0: v1 benchmark | 0.5h（主要等远端跑） | 确认方向 | **最高** |
| P1: dilate+pad 融合 | 1-2h | 内存 -1.5 MB, 一次遍历 | **高** |
| P3: 跳过 dilate (路径 A) | 2-3h | 内存 -4.7 MB, 两次遍历, ~56% 无效 MAC | **高** |
| P2: tiling 调优 | 1-2h（参数搜索） | 缓存命中率提升 | **中** |
| P4: NEON 微优化 | 1h | SIMD 利用率 | **低** |

**注意：P1 和 P3 可以合并执行** — 如果直接做 P3（路径 A），就自动包含了 P1 的收益（因为 P3 直接消除了 dilate 和 pad 两个 buffer）。

---

## 9. 给执行 agent 的一句话总结

> 从 P0 开始：先验证已有 v1 的远端 benchmark；然后做 P3 路径 A（在 compute 中用条件索引直接读原始输入、消除 dilate+pad buffer）；成功后做 P2（微调 tile 因子适配 A72 缓存）。每步都必须先本地 build 验证，再远端 benchmark，再 git 提交。

---

## 10. 附录：reference seed vs v1 working copy 的精确 diff

### 10.1 删除的内容

```python
# reference seed 中有，v1 中已删除：
compute_intermediate = T.alloc_buffer((T.int64(1), T.int64(24), T.int64(128), T.int64(128)))

# compute_init 中的初始化（reference seed 写 0.0 到 compute_intermediate）：
T.writes(compute_intermediate[v_b, v_c, v_h, v_w])
compute_intermediate[v_b, v_c, v_h, v_w] = T.float32(0.0)

# compute_update 中的累加（reference seed 写到 compute_intermediate）：
T.reads(compute_intermediate[v_b, v_c, v_h, v_w], ...)
T.writes(compute_intermediate[v_b, v_c, v_h, v_w])
compute_intermediate[v_b, v_c, v_h, v_w] = compute_intermediate[...] + data_pad[...] * kernel_transform[...]

# 整个 T_add sblock（reference seed 遍历输出做 output = compute_intermediate + bias）：
for ax0, ax1, ax2 in T.grid(T.int64(1), T.int64(24), T.int64(64)):
    for ax3_fused in T.vectorized(T.int64(8)):
        with T.sblock("T_add"):
            ...
            T_add_intermediate[...] = compute_intermediate[...] + lv320[..., 0, 0]
```

### 10.2 v1 中的替换

```python
# compute_init 改为直接写 bias 到最终输出：
T.reads(lv320[v_b, v_c, T.int64(0), T.int64(0)])
T.writes(T_add_intermediate[v_b, v_c, v_h, v_w])
T_add_intermediate[v_b, v_c, v_h, v_w] = lv320[v_b, v_c, T.int64(0), T.int64(0)]

# compute_update 改为直接累加到最终输出：
T.reads(T_add_intermediate[v_b, v_c, v_h, v_w], data_pad[...], kernel_transform[...])
T.writes(T_add_intermediate[v_b, v_c, v_h, v_w])
T_add_intermediate[v_b, v_c, v_h, v_w] = T_add_intermediate[...] + data_pad[...] * kernel_transform[...]
```

### 10.3 后续 P3 改动预览

在 v1 基础上进一步：
- 删除 `data_dilate = T.alloc_buffer(...)` 和 `data_pad = T.alloc_buffer(...)`
- 删除 `data_dilate` sblock 和 `data_pad` sblock
- 在 `compute_update` 中将 `data_pad[v_b, v_dc, v_h + v_dh, v_w + v_dw]` 替换为条件表达式直接读 `lv318`
