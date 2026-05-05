# 优化路线图与阶段指导

更新时间：`2026-03-12`
适用范围：飞腾派 current-safe / MetaSchedule 持续优化、稳定性验证、端到端继续提速

## 0. 当前状态（不是从零开始了）

阶段 A（流程打通）和阶段 B 的第一轮关键突破都已经完成。

当前已经确认的事实：

- **payload 级 current-safe 已显著快于 baseline**
  - 报告：`session_bootstrap/reports/inference_compare_baseline_vs_currentsafe_rerun_20260311_114828.md`
  - 结果：`1844.1 ms -> 153.778 ms`，提升 `91.66%`
- **真实端到端重建 current 也已显著快于 baseline**
  - 报告：`session_bootstrap/reports/inference_real_reconstruction_compare_run_20260311_212301.md`
  - 结果：`1830.3 ms -> 255.931 ms`，提升 `86.02%`
- **baseline-seeded warm-start incremental 已经不是概念验证，而是有效工程路径**
  - 报告：`session_bootstrap/reports/current_scheme_b_compare_20260311_195303.md`
  - 结果：incremental 相比 rebuild-only 再快 `16.272x`
- **当前 trusted current artifact**
  - local: `session_bootstrap/tmp/phytium_baseline_seeded_warm_start_current_incremental_20260311_094548/optimized_model.so`
  - SHA256: `1946b08e6cf20a1259fa43f9e849a06f50ae1230c08d4df7081fba1edae4c644`

所以现在的目标不再是“证明 current 能跑”，而是：

1. 稳住这条 trusted artifact 线；
2. 在这条线上继续拿边际收益；
3. 把 payload 优势更多地转化为真实端到端优势。

---

## 1. 第一优先级：把 trusted SHA 稳住

先别急着大改搜索空间。最值钱的下一步，是确认当前这条线足够稳定，能当后续所有 A/B 的基准。

### 1.1 要做什么

对同一个 trusted SHA：
- 至少再跑 `2–3` 次 payload benchmark；
- 至少再跑 `1–2` 次真实端到端重建 benchmark；
- 所有复跑都必须带 SHA guard；
- 报告里要看 median，也要看 variance 和 max tail。

### 1.2 推荐入口

```bash
# payload current-safe / baseline 对比
bash session_bootstrap/scripts/run_inference_benchmark.sh \
  --env session_bootstrap/config/inference_tvm310_safe.2026-03-10.phytium_pi.env
```

如果要复用上次真实端到端配置：

```bash
bash session_bootstrap/scripts/run_inference_benchmark.sh \
  --env session_bootstrap/tmp/inference_real_reconstruction_compare_run_20260311_212301.env
```

### 1.3 稳定性判定建议

| 指标 | 建议 |
|---|---|
| `current_artifact_sha256_match` | 必须始终为 `True` |
| payload median | 应稳定在 `~154 ms` 邻域 |
| payload variance | 应显著小于 baseline variance |
| 端到端 median | 应持续明显低于 baseline |
| max tail | 如果偶发尖峰明显，要单独定位 pipeline 非 payload 开销 |

如果 trusted SHA 连续复跑稳定，再把它正式视为：
- 当前默认基准；
- 下一轮 tuning 的 warm-start 起点；
- 汇报和论文中的主参考 current artifact。

---

## 2. 第二优先级：继续做 warm-start incremental，而不是回到零开始

现在已经知道：
- rebuild-only current 很慢（约 `2479 ms` 量级）；
- incremental current 很快（约 `152 ms` 量级）；
- 所以继续优化，应该沿着 **baseline-seeded warm-start incremental** 线推进。

### 2.1 推荐预算阶梯

| 轮次 | `TUNE_TOTAL_TRIALS` | warm-start 来源 | 目标 |
|---|---:|---|---|
| 当前已验证 | 500 | 历史 DB | 建立 trusted breakthrough |
| 下一轮 | 1000 | 500-trial DB | 看是否还有明显收益 |
| 再下一轮 | 2000 | 1000-trial DB | 判断收益是否开始收敛 |

### 2.2 推荐入口

```bash
bash session_bootstrap/scripts/run_phytium_baseline_seeded_warm_start_current_incremental.sh
```

或明确覆盖预算：

```bash
bash session_bootstrap/scripts/run_phytium_baseline_seeded_warm_start_current_incremental.sh \
  --total-trials 1000
```

### 2.3 决策规则

- 如果 `500 -> 1000` 还能带来 **>3%** 稳定收益：继续到 `2000`
- 如果 `1000 -> 2000` 收益已经 **<2%**：说明单纯堆预算开始接近平坦
- 如果性能变好但 SHA 复跑不稳定：优先查稳定性，不要立刻扩大预算

### 2.4 资产管理规则

每一轮增量调优后，至少记录三样东西：
- `.so` 路径
- `SHA256`
- `对应 benchmark 报告`

绝对不要只记“这一轮好像更快”。没有 SHA 和报告绑定，就不算可信资产。

---

## 3. 第三优先级：从“全局调优”切到“热点定向调优”

如果再加预算，收益开始变缓，下一步就不是继续盲目扩大 trial，而是把预算集中到最值钱的 task 上。

### 3.1 先做热点提取

```bash
python session_bootstrap/scripts/extract_hotspot_tasks.py \
  --help
```

目标：
- 导出 task 权重排序；
- 找到前 `3–8` 个真正吃时间的 task；
- 让后续实验围绕热点 task 展开，而不是平均撒预算。

### 3.2 接下来重点看什么

- 哪些 task 权重最高；
- 哪些 task 在 rebuild-only 和 incremental 之间变化最大；
- 最优 trace 是否表现出稳定的 NEON / cache 友好模式；
- 是否存在少数 task 决定了大部分收益。

### 3.3 一旦确认热点，就优先实验这些变量

| 优先级 | 变量 | 目的 |
|---|---|---|
| 1 | `TUNE_MAX_TRIALS_PER_TASK` | 防止预算被非关键 task 吃掉 |
| 2 | `TUNE_NUM_TRIALS_PER_ITER` | 调整搜索节奏 |
| 3 | target | 看热点 task 是否对 ISA/并行策略敏感 |
| 4 | 自定义 rule/postproc | 减少明显无效候选 |

---

## 4. 第四优先级：target A/B 要继续，但要更严谨

当前推荐默认 target 仍然是：

```bash
{"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon"],"num-cores":4}
```

继续实验 target：

```bash
{"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon","+crypto","+crc"],"num-cores":4}
```

### 4.1 但这里有个重要原则

target A/B 不能只看配置名字，必须同时看：
- 编译出的 `.so` SHA 是否不同；
- safe runtime benchmark 是否真的不同；
- 结果是否连续复跑仍成立。

如果 target 不同，但产物 SHA 一样，那这轮对比只能算 **workflow smoke**，不能算 target 证据。

### 4.2 推荐入口

```bash
bash session_bootstrap/scripts/run_phytium_current_safe_target_compare.sh
```

---

## 5. 第五优先级：把 payload 优势继续转化成端到端优势

现在 payload 已经到 `152 ms` 左右，但真实端到端还是 `255 ms` 左右。
这说明仍有几十到上百毫秒不在 payload 核心里，而在 pipeline 其他部分。

### 5.1 重点排查对象

1. 图片读写 / decode / resize
2. numpy / tensor 变换与内存拷贝
3. 前后处理是否有重复分配
4. 输出保存是否同步阻塞
5. Python 侧循环和文件系统开销
6. 线程绑核 / CPU 频率 / 后台进程干扰

### 5.2 建议做法

- 把 `current_real_reconstruction.py` 分段计时：
  - load artifact
  - VM init
  - preprocess
  - model run
  - postprocess
  - image save
- 每段单独落盘，不再只看总时间
- 对高方差段做定向优化，而不是继续盲调 TVM payload

### 5.3 这条线最容易出收益的地方

按性价比排序，我更建议：
1. **内存复用 / 预分配 buffer**
2. **减少中间格式转换**
3. **避免每张图重复创建昂贵对象**
4. **绑核 + 降低后台干扰**
5. **只在必要时落盘图片**

---

## 6. 当 MetaSchedule 边际收益变平之后，怎么继续冲性能

如果出现下面任一情况，就要开始考虑转向：
- 连续两轮预算翻倍，收益都很小；
- 热点 task 的 best trace 基本不再变化；
- payload 已很快，但端到端差距主要来自模型外开销；
- 同一 target 下不同 tuning 结果逐渐收敛。

### 6.1 转向优先级

| 方向 | 预期收益 | 难度 | 备注 |
|---|---|---|---|
| 端到端部署优化 | 5–20% | 低 | 线程、绑核、I/O、内存复用 |
| INT8 量化 | 2–4x | 中 | 收益最大，但要处理精度验证 |
| 算子融合 / graph 改写 | 10–30% | 中 | 降低中间搬运 |
| 模型剪枝 / 蒸馏 | 20–60% | 高 | 需要训练链配合 |
| MNN / TVM 双路线协同 | 视模型而定 | 中 | 针对不同场景选最优引擎 |

### 6.2 我建议的顺序

先做：
1. **端到端部署优化**
2. **继续 incremental + 热点定向**
3. **INT8 量化预研**

原因很简单：
- 这三件事最容易在现有工程栈上直接累积收益；
- 不会把当前已经稳定的 current-safe 路线打散；
- 对比赛和文档产出也更友好。

---

## 7. 每轮实验的最小记录要求

每跑完一轮，至少补齐：

- 改了哪个变量；
- 使用了哪个脚本；
- 使用了哪个 env；
- 新 `.so` 的本地路径；
- 新 `.so` 的 SHA256；
- 远端部署路径；
- benchmark 报告路径；
- 结论：更快 / 持平 / 更慢 / 不可信。

建议统一落到：
- `session_bootstrap/runbooks/artifact_registry.md`
- `session_bootstrap/reports/<report_id>.md`

---

## 8. 一句话版行动建议

如果现在只做一件最值钱的事，我建议：

> 先围绕 `1946b08e6cf20a1259fa43f9e849a06f50ae1230c08d4df7081fba1edae4c644` 这条 trusted current artifact 做 2–3 次稳定性复跑；如果稳定，再把增量预算从 `500` 提到 `1000`，并同步开始做热点 task 提取。
