# Judge Evidence Insert Plan（current chunk4）

更新时间：`2026-03-30`
适用范围：把本轮新补齐的 judge-facing 证据直接落到技术文档 / PPT / 答辩附录。

## 1. 当前可直接引用的总入口

优先引用顺序：

1. `session_bootstrap/reports/judge_evidence_pack_20260330_current_chunk4_lpips_full_profiled.md`
2. `session_bootstrap/reports/judge_quality_formal_report_20260330_lpips_full.md`
3. `session_bootstrap/reports/judge_snr_robustness_20260330_current_chunk4.md`
4. `session_bootstrap/reports/resource_profile_trusted_current_chunk4_20260330_151728.md`
5. `session_bootstrap/reports/profiling_judge_refresh_20260330_170808.md`

## 2. 技术文档正文建议插入位置

### 2.1 结果总表页（性能 headline）

直接沿用当前 trusted headline：

- payload：`1846.9 -> 130.219 ms`（`92.95%`）
- real reconstruction：`1850.0 -> 230.339 ms/image`（`87.55%`）

来源：
- `session_bootstrap/reports/inference_compare_currentsafe_chunk4_refresh_20260313_1758.md`
- `session_bootstrap/reports/inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md`

### 2.2 图像质量页

建议表格直接引用：
- `session_bootstrap/reports/judge_quality_formal_report_20260330_lpips_full.md`

可直接写成：
- `PyTorch vs TVM baseline`：`PSNR 34.4244 dB`，`SSIM 0.970454`，`LPIPS 0.025883`
- `PyTorch vs TVM current`：`PSNR 35.6633 dB`，`SSIM 0.972751`，`LPIPS 0.025124`
- `TVM baseline vs TVM current`：`PSNR 34.4464 dB`，`SSIM 0.970427`，`LPIPS 0.025850`

正文解释建议：
- current 相比 baseline，在同一 PyTorch reference 下平均 `+1.2389 dB PSNR`
- current 的 LPIPS 也略优于 baseline（`0.025124 < 0.025883`）
- 说明 current 提速并未以明显牺牲重建质量为代价
- 脚注注明：涉及 baseline 的 LPIPS 采用 remote crop249 对齐口径（与历史 baseline 249×249 输出保持一致）

### 2.3 资源画像页

建议直接引用：
- `session_bootstrap/reports/resource_profile_trusted_current_chunk4_20260330_151728.md`

正文可直接写：
- current trusted chunk4 `run_median_ms = 230.466 ms/image`
- `artifact_sha256_match = true`
- 平均 CPU `user/system/idle/wait = 32.283 / 9.065 / 58.348 / 0.250 %`
- `min_free_kb = 88340`
- trusted artifact size `1651136 bytes`（`1.575 MiB`）

解释建议：
- 当前资源瓶颈主要不是 I/O wait（平均 wait 很低）
- 资源画像可支撑“系统可运行、可部署、可控 footprint”这条答辩口径

### 2.4 多 SNR 鲁棒性页

建议直接引用：
- `session_bootstrap/reports/judge_snr_robustness_20260330_current_chunk4.md`
- `session_bootstrap/reports/judge_snr_robustness_20260330_current_chunk4_latency.svg`
- `session_bootstrap/reports/judge_snr_robustness_20260330_current_chunk4_quality.svg`

建议展示两张图：
1. `Latency vs SNR`
2. `Mean PSNR vs SNR`

正文可直接引用的数据点：

| SNR | median ms/image | PSNR mean | SSIM mean |
|---:|---:|---:|---:|
| 1 | 228.223 | 29.1452 | 0.900039 |
| 4 | 228.595 | 31.8047 | 0.939559 |
| 7 | 233.509 | 34.0185 | 0.961243 |
| 10 | 231.893 | 35.6644 | 0.972735 |
| 13 | 234.018 | 36.8695 | 0.978757 |

解释建议：
- 速度随 SNR 变化不大，基本稳定在 `228~234 ms/image`
- 图像质量随 SNR 提升呈单调改善趋势
- 这支持“系统在不同信道条件下保持稳定延迟，同时重建质量可随信道改善而提升”的口径

### 2.5 算子热点 / profiling 页

建议直接引用：
- `session_bootstrap/reports/profiling_judge_retry_parse_20260330_184026.md`

当前建议写法：
- 不再需要说“remote per-op profiler 仍不支持”
- 应写成：
  - 已完成可信 stage-weight hotspot evidence
  - 也已拿到 remote runtime per-op profiling 的 sample 级结果
  - 当前 runtime hotspot candidates 为：
    - `fused_conv2d_transpose2_add12`
    - `fused_conv2d_transpose1_add9`
  - 若需要再展开，可补一句 raw top ops 还包括：
    - `fused_conv2d_transpose_add6`
    - `fused_conv2d3_add15`
  - 需要诚实说明：当前已取得 `3 samples` 的小样本稳定 runtime profile，后续仍可继续补更多样本做统计增强

## 3. PPT 页结构建议

推荐新增/替换 4 页：

### 页 A：质量不掉队
标题建议：`加速同时保持重建质量`

放：
- `judge_quality_formal_report_20260330_lpips_full.md` 里的 aggregate matrix
- 一句结论：`current 相比 baseline 平均 +1.2389 dB PSNR，LPIPS 也略优`

### 页 B：资源可控
标题建议：`资源画像与部署 footprint`

放：
- CPU / memory / artifact size 三个核心 bullet
- 引用 `resource_profile_trusted_current_chunk4_20260330_151728.md`

### 页 C：多 SNR 鲁棒性
标题建议：`不同信道条件下的稳定性与质量趋势`

放：
- `judge_snr_robustness_20260330_current_chunk4_latency.svg`
- `judge_snr_robustness_20260330_current_chunk4_quality.svg`

### 页 D：热点与下一步优化方向
标题建议：`当前热点定位与后续深挖方向`

放：
- top hotspot task 列表
- 明确：当前已有 stage-level hotspot evidence，后续再补 profiler-capable runtime per-op trace

## 4. 答辩口头版一句话模板

### 质量
“我们不只看延迟，也补了和 PyTorch reference 对齐的重建质量指标；在同一参考下，current 的平均 PSNR 比 baseline 还高约 1.24 dB，SNR10 这一组 LPIPS 也略优于 baseline，说明这轮优化不是单纯拿质量换速度。”

### 资源
“我们还补了板端 CPU、内存和产物大小画像；当前 trusted chunk4 产物只有 1.575 MiB，运行时平均 I/O wait 很低，说明系统已经具备比较稳定的部署形态。”

### 多 SNR
“在 `SNR=1/4/7/10/13` 五个点上，current 的延迟基本稳定在 `228~234 ms/image`，而 PSNR/SSIM 随 SNR 提升呈稳定改善趋势，这说明系统的时延稳定性和质量趋势都可以 defend。”

## 5. 当前仍需诚实说明的边界

- `LPIPS` 现已补齐三组正式比较，但其中涉及 baseline 的两组采用 remote crop249 对齐口径，应在答辩里用脚注说明
- 远端 runtime per-op profiling 已在 latest probe 中打通，但当前仍是 `1 sample` 级别，不宜过度外推成完整统计结论
- 以上边界不会推翻已有 judge-facing 结论，但答辩时应主动说明为“核心证据已补齐，剩余是增强项”
