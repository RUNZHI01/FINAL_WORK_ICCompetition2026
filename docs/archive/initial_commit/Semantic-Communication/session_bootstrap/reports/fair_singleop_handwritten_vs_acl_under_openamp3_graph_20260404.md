# OpenAMP 三核 + 当前计算图下的手写算子 / ACL 单算子公平复核（2026-04-04）

- date: `2026-04-04`
- board state: `OpenAMP enabled`, `remoteproc0=running`, `cpu online=0-2`, `nproc=3`
- purpose: replace the earlier unstable `transpose_add6 standalone ACL +33.9%` claim with evidence that is closer to the real deployment condition: **same 3-core board state + current JSCC graph context**

## 1. Scope

这次“更公平”的比对分两层：

1. **图内 runtime profiling**
   - 直接在当前 JSCC 计算图里跑：
     - `Trusted Current` (`6f236b07...6dc1`)
     - `Handwritten final` (`2aa25d2b...e216`)
     - `602371c2...edba` 这条 `transpose_add6` packed-call line
   - 命令统一为：
     - `bash ./session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current --max-inputs 3 --profile-ops --profile-samples 3`
   - 对应 env：
     - `session_bootstrap/reports/daily_20260404_openamp_3core_big_little_followup/trusted_current_big_little_compare.env`
     - `session_bootstrap/reports/daily_20260404_openamp_3core_big_little_followup/handwritten_big_little_compare.env`
     - `session_bootstrap/reports/daily_20260404_openamp_3core_big_little_followup/acl_big_little_compare.env`

2. **ACL library standalone rerun**
   - 在同一 OpenAMP 三核板态下，直接重跑板上的：
     - `/tmp/acl_deconv_f32_bench_asym`
   - 每个 case 连续跑 `3` 次，取 `median_of_medians`

## 2. Important Boundary

### 2.1 当前 repo 里能和 stock ACL 直接对位的，只有三段 transpose 热点

- `fused_conv2d_transpose1_add9`
- `fused_conv2d_transpose_add6`
- `fused_conv2d_transpose2_add12`

`variance3` 和 `mean4` 当前没有 repo 内现成的 stock ACL 对位实验，因此这两项只能做 **图内手写 A/B**，不能做“手写 vs ACL library”一一对应。

### 2.2 之前口头叫“ACL integration line”的 `602371c2...edba`，当前其实不是真 ACL kernel 入图

`acl_big_little_compare.env` 当前显式设置了：

- `TVM_RUNTIME_PRELOAD_PY=/home/user/Downloads/jscc-test/acl_ab/preload_transpose_add6_tvm_proxy.py`
- `TVM_TRANSPOSE_ADD6_PROXY_SO=/home/user/Downloads/jscc-test/acl_ab/transpose_add6_tvm_v1/fused_conv2d_transpose_add6_v1_standalone.so`

而本地脚本 [`session_bootstrap/scripts/preload_transpose_add6_tvm_proxy.py`](../scripts/preload_transpose_add6_tvm_proxy.py) 做的是：

- preload 一个 TVM standalone `.so`
- 注册 `jscc.acl.transpose_add6`
- 在 packed-call 里直接转调 TVM standalone kernel

所以，`602371c2...edba` 当前更准确的定义是：

- **`transpose_add6 packed-call shim + TVM proxy line`**

而不是“stock ACL kernel 已经真实入图”的证据。

## 3. Graph-Real Per-Op Results

下表取 `3` 个 profile samples 的 `median_duration_us`，统一换算为 `ms`：

| Operator | Trusted Current | Handwritten final | Handwritten vs Trusted | `602...` packed-call proxy | Proxy vs Trusted |
|---|---:|---:|---:|---:|---:|
| `fused_conv2d_transpose1_add9` | `55.016` | `48.025` | `-12.707%` | `47.858` | `-13.011%` |
| `fused_conv2d_transpose2_add12` | `43.912` | `38.701` | `-11.867%` | `38.599` | `-12.100%` |
| `fused_conv2d_transpose_add6` | `40.916` | `34.973` | `-14.526%` | `35.452` | `-13.355%` |
| `fused_variance3_add10_tir_sqrt3` | `3.581` | `2.744` | `-23.376%` | `3.766` | `+5.167%` |
| `fused_mean4_subtract4_divide4_multiply4_add14_relu3` | `3.102` | `4.548` | `+46.602%` | `11.254` | `+262.758%` |

对应整图本轮 `run_median_ms`：

| Line | Artifact SHA | Graph run median |
|---|---|---:|
| Trusted Current | `6f236b07...6dc1` | `358.450 ms` |
| Handwritten final | `2aa25d2b...e216` | `353.335 ms` |
| `602...` packed-call proxy | `602371c2...edba` | `358.105 ms` |

## 3.1 Why The End-to-End Direction Flips

如果问题是：

> 为什么之前看起来像“`transpose_add6` 单算子 ACL 更快”，但到了端到端却没有自然导出 “ACL line 更优”？

这轮图内差分已经能给出更具体的答案。

### Handwritten final vs `602...` packed-call proxy

三条线里，最值得直接比较的是：

- `Handwritten final`：`352.693 ms`
- `602...` packed-call proxy：`358.430 ms`

两者整图中位数差约：

- **`-5.737 ms`**（handwritten 更快）

而这 `5.737 ms` 的 gap，图内 profile 的主要贡献项是：

| Operator | Handwritten final | `602...` packed-call proxy | Delta |
|---|---:|---:|---:|
| `fused_mean4_subtract4_divide4_multiply4_add14_relu3` | `4.648 ms` | `11.178 ms` | **`-6.530 ms`** |
| `fused_variance3_add10_tir_sqrt3` | `2.736 ms` | `3.678 ms` | **`-0.942 ms`** |
| `fused_conv2d_transpose_add6` | `34.790 ms` | `35.303 ms` | `-0.513 ms` |
| `fused_conv2d_transpose1_add9` | `48.249 ms` | `48.705 ms` | `-0.455 ms` |
| `fused_conv2d_transpose2_add12` | `39.143 ms` | `38.672 ms` | `+0.470 ms` |

这张表说明了一件很关键的事：

- **Handwritten vs “ACL 单点替换 line” 的主要差距，根本不在 `transpose_add6` 本身。**
- 真正把结果拉开的，是 **`mean4` 和 `variance3` 这两段非 ACL 单点覆盖区**。
- transpose 三热点两边其实已经很接近，`transpose2` 上甚至是 proxy 略快一点点。

因此，端到端没有自然导出 “ACL line 更优”，原因现在已经可以更准确地写成：

> 因为当前单点替换路线只触达了 transpose seam，而手写整合路线真正吃到的收益并不止这一个点；在 OpenAMP 三核和当前 JSCC 图里，`mean4 + variance3` 这两段差异，足以覆盖掉 transpose 单点的任何局部优势。

### Handwritten final vs Trusted Current

`Handwritten final` 相比 `Trusted Current` 也不是“所有手写项都更快”，而是**多个 gain 和多个 regression 的净结果**。

本轮图内差分里，主要正贡献包括：

- `fused_conv2d2_add2`: `-9.613 ms`
- `fused_conv2d_transpose_add6`: `-7.109 ms`
- `fused_conv2d_transpose1_add9`: `-6.202 ms`
- `fused_conv2d3_add15`: `-5.400 ms`
- `fused_conv2d_transpose2_add12`: `-1.403 ms`
- `fused_variance3_add10_tir_sqrt3`: `-0.803 ms`

主要负贡献包括：

- `fused_variance1_add3_tir_sqrt1`: `+9.459 ms`
- `fused_mean3_subtract3_divide3_multiply3_add11_relu2`: `+4.481 ms`
- `fused_mean1_subtract1_divide1_multiply1_add4`: `+4.177 ms`
- `fused_mean4_subtract4_divide4_multiply4_add14_relu3`: `+1.546 ms`

这进一步说明：

- 手写整合线本身就是**整图 tradeoff**，不是“某一个单算子赢了，所以整图就必然赢”。
- 也正因为如此，孤立 standalone benchmark 本来就不够支撑端到端结论。

## 4. ACL Standalone Rerun Under The Same 3-Core Board State

旧报告 [`acl_replaceable_hotspots_asym_padding_probe_20260404.md`](./acl_replaceable_hotspots_asym_padding_probe_20260404.md) 给出的 asym-padding 结果是：

- `transpose1_asym = 34.996 ms`
- `transpose_add6_asym = 11.581 ms`
- `transpose2_asym = 33.029 ms`

但同一天、同板子、OpenAMP 三核态下直接重跑 `3` 次后，结果变成：

| ACL case | old asym report | rerun samples | rerun median_of_medians | delta vs old |
|---|---:|---|---:|---:|
| `transpose1_asym` | `34.996` | `27.993, 26.611, 24.065` | `26.611` | `-23.960%` |
| `transpose_add6_asym` | `11.581` | `16.771, 16.704, 20.993` | `16.771` | `+44.815%` |
| `transpose2_asym` | `33.029` | `45.431, 52.072, 51.505` | `51.505` | `+55.939%` |

这说明旧的 standalone ACL 数字本身就不稳，尤其：

- `transpose_add6` 不再是稳定的 `11.581 ms`
- `transpose2` 在当前 3-core 板态下比旧值慢了一个很大的量级

因此，旧报告里那句“ACL 在 `transpose_add6` standalone 上快约 `33.9%`”不能继续作为当前主叙事里的强证据。

## 5. What The Fairer Evidence Actually Supports

### 5.1 可以安全说的

1. **旧的 `transpose_add6 ACL +33.9%` 结论不稳，不能再当主证据。**
   - 它建立在旧的 standalone ACL 数字上
   - 而这些数字在同一天、同板、切到 OpenAMP 三核态后已经明显漂移

2. **最可 defend 的算子级证据，现在应该优先用图内 runtime profiling。**
   - 这才是真正处在“当前 3 核 + 当前 JSCC 图”条件下的证据

3. **在图内证据里，Handwritten final 的收益不是假象。**
   - 三个 transpose 热点都比 trusted current 更快
   - `variance3` 也明确更快
   - 虽然 `mean4` 这一段更慢，但净结果仍然让整图 median 从 `358.450 ms` 降到 `353.335 ms`

4. **当前 repo 里并没有“stock ACL kernel 已公平入图”的图内证据。**
   - `602371c2...edba` 这条线当前是 `packed-call shim + TVM proxy`
   - 它不是 stock ACL kernel 的 graph-real proof

5. **端到端方向反转的直接原因，现在已经能量化到具体 op。**
   - handwritten 相对 proxy line 的主要优势来自 `mean4` 和 `variance3`
   - 而不是来自“`transpose_add6` 单点一定绝对压过 ACL”

### 5.2 更适合写进正文的自然结论

当前最自然、也最不容易被反问击穿的写法应当是：

> 在 OpenAMP 三核与当前 JSCC 计算图条件下，现阶段最可信的算子级证据来自图内 runtime profiling，而不是孤立 standalone benchmark。按这套更公平的证据口径，手写优化路线的端到端优势并不是由某一个 transpose 单点决定，而是由多处算子共同作用形成，其中 handwritten 相对单点替换路线最主要的领先项来自 `mean4` 与 `variance3`。相对地，ACL 单热点替换目前仍停留在“standalone 信号不稳、stock ACL 尚未真实入图验证”的阶段。因此，当前项目里**更成熟、更可 defend 的优化路线是手写多算子优化整合，而不是 ACL 单热点替换**。

## 6. Writing Guidance

建议正文不要再写：

- “`transpose_add6` 单算子上 ACL 比 TVM 快 `33.9%`，所以 ACL 理应端到端更优”

建议改写成：

1. 先说明旧 standalone ACL 数字在 2026-04-04 OpenAMP 三核复测下出现明显漂移，不能继续作为强结论。
2. 再把证据切到图内 runtime profiling。
3. 强调当前图内最扎实的正收益来自 `Handwritten final` 这条已落地路线。
4. 最后自然引出：ACL 路线目前更像“值得继续探索的 seam”，而不是已经完成验证的主优化结论。
