# 飞腾杯答辩附录页（Page 9-12）—— Judge Evidence

- 用途：承接评委追问，不打乱当前 Page 1-8 主叙事
- 使用原则：主答辩先讲 1-8 页；被追问“质量 / 资源 / SNR / profiling”时，再切到本附录
- 最新综合入口：`session_bootstrap/reports/judge_evidence_pack_20260330_current_chunk4_lpips_full.md`

## Page 9

- 页标题：`质量补证：加速没有以牺牲重建质量为代价`
- 页核心信息：在同一 PyTorch reference 下，current 的 PSNR / SSIM / LPIPS 均不差于 baseline。
- 页内文案：
  - `PyTorch vs TVM baseline`：`PSNR 34.4244 dB`，`SSIM 0.970454`，`LPIPS 0.025883`
  - `PyTorch vs TVM current`：`PSNR 35.6633 dB`，`SSIM 0.972751`，`LPIPS 0.025124`
  - `TVM baseline vs current`：`PSNR 34.4464 dB`，`SSIM 0.970427`，`LPIPS 0.025850`
  - 因此 current 相比 baseline：
    - 平均 `+1.2389 dB PSNR`
    - 平均 `+0.002297 SSIM`
    - LPIPS 也略优（`0.025124 < 0.025883`）
- 讲者备注：
  - 如果评委问“是不是拿质量换速度”，这一页直接回答：不是。
  - 需要口头补一句：涉及 baseline 的 LPIPS 使用了与其 `249×249` 输出对齐的 remote crop249 口径。
- 引用证据：
  - `session_bootstrap/reports/judge_quality_formal_report_20260330_lpips_full.md`

## Page 10

- 页标题：`资源画像：当前 trusted chunk4 的部署 footprint`
- 页核心信息：current 不只是“能跑得快”，而且 footprint 可描述、资源占用可解释。
- 页内文案：
  - trusted artifact size：`1651136 bytes`（`1.575 MiB`）
  - trusted current chunk4：`run_median_ms = 230.466 ms/image`
  - avg CPU `user/system/idle/wait = 32.283 / 9.065 / 58.348 / 0.250 %`
  - `min_free_kb = 88340`
  - `artifact_sha256_match = true`
- 讲者备注：
  - 重点不是绝对功耗值，而是“系统并非高 wait / 高抖动 / 不可控状态”。
  - 如果评委问功耗，就主动说明：当前没有板级功率计，正式资源画像以 CPU / memory / artifact size 为准。
- 引用证据：
  - `session_bootstrap/reports/resource_profile_trusted_current_chunk4_20260330_151728.md`

## Page 11

- 页标题：`多 SNR 鲁棒性：延迟稳定，质量随信道改善单调提升`
- 页核心信息：current trusted chunk4 在 `SNR=1/4/7/10/13` 五个点上延迟基本稳定，而质量随 SNR 改善呈单调上升。
- 页内文案：
  - latency：
    - `SNR=1 -> 228.223 ms/image`
    - `SNR=4 -> 228.595 ms/image`
    - `SNR=7 -> 233.509 ms/image`
    - `SNR=10 -> 231.893 ms/image`
    - `SNR=13 -> 234.018 ms/image`
  - PSNR：
    - `29.1452 -> 31.8047 -> 34.0185 -> 35.6644 -> 36.8695 dB`
  - SSIM：
    - `0.900039 -> 0.939559 -> 0.961243 -> 0.972735 -> 0.978757`
- 讲者备注：
  - 这页最适合回答“弱网变化下系统稳不稳”。
  - 结论要讲成：速度对 SNR 不敏感，质量对 SNR 呈合理单调趋势。
- 引用证据：
  - `session_bootstrap/reports/judge_snr_robustness_20260330_current_chunk4.md`
  - `session_bootstrap/reports/judge_snr_robustness_20260330_current_chunk4_latency.svg`
  - `session_bootstrap/reports/judge_snr_robustness_20260330_current_chunk4_quality.svg`

## Page 12

- 页标题：`热点与边界：知道瓶颈在哪，也知道当前不该 overclaim 什么`
- 页核心信息：我们已经完成热点定位，也拿到了 remote runtime per-op profiling 的 sample 级结果，但不会把它夸大成大样本统计结论。
- 页内文案：
  - 可信 stage-weight hotspot 入口已固定：
    - `reshape2`
    - `fused_variance1_add3_tir_sqrt1`
    - `reshape1`
    - `fused_mean1_subtract1_divide1_multiply1_add4`
  - latest remote runtime profiling 已打通：
    - `runtime_operator_profile`
    - 当前 runtime hotspot candidates：
      - `fused_conv2d_transpose2_add12`
      - `fused_conv2d_transpose1_add9`
    - raw top ops 还包括：
      - `fused_conv2d_transpose_add6`
      - `fused_conv2d3_add15`
  - 因此当前口径应为：
    - **stage-weight hotspot evidence 已有**
    - **remote runtime per-op profiling 也已可用**
    - **且当前已达到 3 samples 的小样本稳定结论，但还不是完整大样本统计画像**
- 讲者备注：
  - 这页的价值仍然是防止 overclaim。
  - 现在要主动讲的边界，已经从“没有 per-op profile”变成“有 sample 级 per-op profile，但还没做大样本统计”。
- 引用证据：
  - `session_bootstrap/reports/profiling_judge_retry_parse_20260330_184026.md`
  - `session_bootstrap/reports/judge_evidence_pack_20260330_current_chunk4_lpips_full_profiled.md`

## 使用建议

- 如果评委先追问“画质有没有掉”，先切 Page 9。
- 如果评委追问“资源和部署代价”，切 Page 10。
- 如果评委追问“弱网变化下稳不稳”，切 Page 11。
- 如果评委追问“你到底定位到什么瓶颈、是不是拿到了 per-op profile”，切 Page 12。
