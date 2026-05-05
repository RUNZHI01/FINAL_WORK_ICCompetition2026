# 2026-03-31 手写算子材料归档索引

- 日期：2026-04-01 整理
- 作用：把 2026-03-31 这一轮“手写算子 / handwritten / post-db scheduled-form”工作的关键材料集中成一个入口，避免后续答辩、论文、复盘和继续开发时丢失上下文。
- 项目：`/home/tianxing/tvm_metaschedule_execution_project`

---

## 一句话结论

2026-03-31 这轮工作并不是只优化了一个算子，而是**围绕 runtime hotspot 批量建立了多个手写算子候选 lane**。其中：

- `fused_conv2d_transpose1_add9`：推进最深，已经从“旧 raw replacement 误导路径”修正到“schedule-preserving / post-db scheduled-form”工作流，并进入真实候选改写阶段；
- `fused_conv2d_transpose2_add12`、`fused_conv2d_transpose_add6`、`fused_conv2d3_add15`：已建立完整的 scheduled-form handwritten lane，并完成本地 post-db swap/build/export 证明；
- `fused_mean4_subtract4_divide4_multiply4_add14_relu3`：已建立 reduction/norm 类 lane，并完成本地 swap/build/export 证明，但当前 best staging 上没有直接 DB schedule 命中，现阶段更偏“可编辑工作面已就位”。

因此，**3.31 的珍贵之处不只是“想到要手写算子”，而是已经把多算子的工程落点、参考 seed、working copy、局部 proof、runbook 和证据文件都铺出来了。**

---

## 总入口：为什么会启动这一轮

主入口：

- `session_bootstrap/reports/handwritten_hotspot_candidates_20260331.md`
- `session_bootstrap/reports/current_best_staging_candidate_20260331.md`

关键信息：

- 当前最佳 staging 候选：
  - run id：`phytium_runtime_joint_top6_targeted_staging_search_20260330_2315`
  - artifact sha256：`5bd14b9f97d1d06f04a484cd8b1b3f57a955d65711ed65a22f9925dcec44698d`
  - staging payload：`159.943 ms`
- 3.31 的 handwritten 候选波次来自 runtime reprobe 的热点排序。

当时的 curated top ops：

1. `fused_conv2d_transpose1_add9`
2. `fused_conv2d_transpose2_add12`
3. `fused_conv2d_transpose_add6`
4. `fused_conv2d3_add15`
5. `fused_mean4_subtract4_divide4_multiply4_add14_relu3`
6. `fused_variance4_add13_tir_sqrt4`
7. `fused_mean3_subtract3_divide3_multiply3_add11_relu2`
8. `fused_variance3_add10_tir_sqrt3`

其中 Wave 1 主要是 conv/deconv，Wave 2 主要是 norm/reduction。

---

## 逐算子归档

### 1) `fused_conv2d_transpose1_add9`

核心报告：

- `session_bootstrap/reports/transpose1_handwritten_work_review_20260331.md`
- `session_bootstrap/reports/transpose1_schedule_preserving_seam_note_20260331.md`
- `session_bootstrap/reports/transpose1_handwritten_v0_regression_diagnosis_20260331.md`
- `session_bootstrap/reports/transpose1_v1_local_evidence_20260331.md`
- `session_bootstrap/reports/transpose1_p2_local_prep_20260331_192414.md`
- `session_bootstrap/reports/transpose1_p2_remote_benchmark_20260331_192521.md`
- `session_bootstrap/reports/transpose1_p3_local_prep_20260331_1110.md`
- `session_bootstrap/reports/transpose1_p3_remote_benchmark_20260331_191638.md`
- `session_bootstrap/reports/transpose1_p4_local_prep_20260331_193115.md`
- `session_bootstrap/reports/transpose1_p4_remote_benchmark_20260331_193220.md`

代码 / 脚手架入口：

- `session_bootstrap/handwritten/fused_conv2d_transpose1_add9/`
- `session_bootstrap/scripts/run_transpose1_post_db_local_build.py`
- `session_bootstrap/scripts/run_transpose1_post_db_local_build_and_sync.py`
- `session_bootstrap/scripts/sync_transpose1_post_db_local_build_result.py`
- `session_bootstrap/scripts/probe_transpose1_schedule_preserving_seam.py`

状态判断：

- 这是 3.31 推进最深的一条线；
- 已明确否定旧 `v0` raw pre-compile replacement 作为性能结论依据；
- 已转到 post-db scheduled-form / schedule-preserving 语义；
- 已有“真实手写候选改写 + 本地验证 + 远端 benchmark 尝试”的整套痕迹；
- 但**还没有形成可以对外宣称的明确性能提升结论**。

---

### 2) `fused_conv2d_transpose2_add12`

核心报告：

- `session_bootstrap/reports/transpose2_local_handwritten_lane_summary_20260331.md`
- `session_bootstrap/reports/transpose2_hotspot_next_step_report_20260331.md`
- `session_bootstrap/reports/transpose2_v1_remote_benchmark_20260331_201239.md`
- `session_bootstrap/reports/transpose2_p2_local_prep_20260331_201923.md`
- `session_bootstrap/reports/transpose2_p2_remote_benchmark_20260331_202602.md`
- `session_bootstrap/reports/transpose2_p4_local_prep_20260331_203049.md`
- `session_bootstrap/reports/transpose2_p4_remote_benchmark_20260331_203415.md`

代码 / 脚手架入口：

- `session_bootstrap/handwritten/fused_conv2d_transpose2_add12/`
- `session_bootstrap/scripts/refresh_fused_conv2d_transpose2_add12_post_db_scheduled_seed.py`
- `session_bootstrap/scripts/refresh_fused_conv2d_transpose2_add12_scheduled_form_working_copy.py`
- `session_bootstrap/scripts/run_transpose2_post_db_local_build.py`
- `session_bootstrap/runbooks/handwritten_fused_conv2d_transpose2_add12_runbook_2026-03-31.md`

已知 proof：

- tuning DB / schedule 命中：`true`
- standalone scheduled task build：`built`
- post-db scheduled swap：`swap_succeeded = true`
- local build/export：成功
- artifact sha256：`7f7c13d44a392cf2dce8b3281fee3170b1781b25368944bb933c8c8775317858`

状态判断：

- lane 已完整建立；
- 证明了可以在 post-db scheduled 语义层进行局部替换并成功 build/export；
- 这不是空想方案，而是已经能落地到可继续编辑的 operator lane。

---

### 3) `fused_conv2d_transpose_add6`

核心报告：

- `session_bootstrap/reports/transpose_add6_local_handwritten_lane_summary_20260331.md`
- `session_bootstrap/reports/transpose_add6_v1_remote_benchmark_20260331_210152.md`
- `session_bootstrap/reports/transpose_add6_p2_local_prep_20260331_211556.md`
- `session_bootstrap/reports/transpose_add6_p2_remote_benchmark_20260331_212249.md`
- `session_bootstrap/reports/transpose_add6_p4_local_prep_20260331_213321.md`
- `session_bootstrap/reports/transpose_add6_p4_remote_benchmark_20260331_213628.md`

代码 / 脚手架入口：

- `session_bootstrap/handwritten/fused_conv2d_transpose_add6/`
- `session_bootstrap/scripts/refresh_fused_conv2d_transpose_add6_post_db_scheduled_seed.py`
- `session_bootstrap/scripts/refresh_fused_conv2d_transpose_add6_scheduled_form_working_copy.py`
- `session_bootstrap/scripts/run_transpose_add6_post_db_local_build.py`
- `session_bootstrap/runbooks/handwritten_fused_conv2d_transpose_add6_runbook_2026-03-31.md`

已知 proof：

- tuning DB / schedule 命中：`true`
- standalone scheduled task build：`built`
- post-db scheduled swap：`swap_succeeded = true`
- local build/export：成功
- artifact sha256：`8e629c0d2905165283e43fd527292f0bea1ba3f74f4158e1e819b10338eb97d6`

状态判断：

- 与 transpose2 一样，属于已建立完整局部 handwritten lane 的 deconv 热点；
- 是 3.31 多算子批量推进的重要一环。

---

### 4) `fused_conv2d3_add15`

核心报告：

- `session_bootstrap/reports/conv2d3_add15_local_handwritten_lane_summary_20260331.md`
- `session_bootstrap/reports/conv2d3_add15_v1_local_prep_20260331_220554.md`
- `session_bootstrap/reports/conv2d3_add15_v1_remote_benchmark_20260331_221417.md`
- `session_bootstrap/reports/conv2d3_add15_p2_local_prep_20260331_222242.md`
- `session_bootstrap/reports/conv2d3_add15_p2_remote_benchmark_20260331_223100.md`
- `session_bootstrap/reports/conv2d3_add15_p4_local_prep_20260331_224047.md`
- `session_bootstrap/reports/conv2d3_add15_p4_remote_benchmark_20260331_224339.md`

代码 / 脚手架入口：

- `session_bootstrap/handwritten/fused_conv2d3_add15/`
- `session_bootstrap/scripts/refresh_fused_conv2d3_add15_post_db_scheduled_seed.py`
- `session_bootstrap/scripts/refresh_fused_conv2d3_add15_scheduled_form_working_copy.py`
- `session_bootstrap/scripts/run_conv2d3_add15_post_db_local_build.py`
- `session_bootstrap/runbooks/handwritten_fused_conv2d3_add15_runbook_2026-03-31.md`

已知 proof：

- tuning DB / schedule 命中：`true`
- standalone scheduled task build：`built`
- post-db scheduled swap：`swap_succeeded = true`
- local build/export：成功
- artifact sha256：`bcfb7d6fe54da7edc4517cd669c3244788ee6d4ea866c3817ab766d7abb5db07`

状态判断：

- 这是 Wave 1 里唯一明确进入 conv 侧的热点；
- 说明 3.31 的工作不是只在 transpose/deconv 上打转，而是已经向 conv kernel 本体延伸。

---

### 5) `fused_mean4_subtract4_divide4_multiply4_add14_relu3`

核心报告：

- `session_bootstrap/reports/mean4_local_handwritten_lane_summary_20260331.md`

代码 / 脚手架入口：

- `session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/`
- `session_bootstrap/scripts/refresh_fused_mean4_subtract4_divide4_multiply4_add14_relu3_post_db_scheduled_seed.py`
- `session_bootstrap/scripts/refresh_fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_working_copy.py`
- `session_bootstrap/scripts/run_mean4_post_db_local_build.py`
- `session_bootstrap/runbooks/handwritten_fused_mean4_subtract4_divide4_multiply4_add14_relu3_runbook_2026-03-31.md`

已知 proof：

- direct DB schedule 命中：`false`
- post-database apply 后 operator 仍存在：`true`
- post-db scheduled swap：`swap_succeeded = true`
- local build/export：成功
- artifact sha256：`de429fe2d2be48696c740aa4b279a9da6337fc469d2d05d6061f874e6702bbc9`

状态判断：

- 这是从 conv/deconv 扩展到 norm/reduction 的关键证据；
- 当前更像“局部工作面已搭好、可继续编辑”，而不是已完成 schedule-backed 等价复现；
- 但它能证明 3.31 已经不止关注卷积类热点，开始往 reduction/epilogue 类热点扩展。

---

## 应如何理解这些材料的价值

这批 3.31 材料的价值，不是简单一句“手写算子优化了几个点”，而是包含了完整的工程化链条：

1. **热点选择有依据**：来自 reprobe/runtime hotspot，而不是拍脑袋；
2. **对照基线有冻结**：基于 `5bd14b9f...` staging candidate；
3. **评估语义被修正过**：至少 `transpose1` 明确从错误的 raw replacement 评估，修正到 schedule-preserving 语义；
4. **多算子 lane 已落仓**：每个 lane 都有 seed、manifest、working copy、runbook、build 脚本；
5. **局部 proof 不是空白**：多个算子已完成 post-db swap/build/export 验证；
6. **远端 benchmark 痕迹存在**：多个算子已有 local prep + remote benchmark 报告；
7. **结论边界清楚**：目前多数 lane 仍属于 staging/local-only/diagnostic-only，不宜偷换成“已拿到正式全局提速结论”。

---

## 推荐后续用法

如果后面要继续沿 3.31 这批材料推进，建议按下面顺序：

1. 先把本索引与各 operator lane 一起视为“手写算子材料总入口”；
2. 继续优先从：
   - `fused_conv2d_transpose1_add9`
   - `fused_conv2d_transpose2_add12`
   - `fused_conv2d_transpose_add6`
   - `fused_conv2d3_add15`
   这四条 Wave 1 线里选一个恢复推进；
3. 每次只推进一个 operator，并在 staging archive 上复验；
4. 只有当 local proof -> remote payload -> runtime reprobe 三层都成立，才考虑 promote；
5. `mean4` 这类 Wave 2 reduction/norm lane 作为第二梯队继续补强。

---

## 最简入口清单

如果只想快速找回 3.31 这批材料，优先打开：

- `session_bootstrap/reports/handwritten_hotspot_candidates_20260331.md`
- `session_bootstrap/reports/current_best_staging_candidate_20260331.md`
- `session_bootstrap/reports/transpose1_handwritten_work_review_20260331.md`
- `session_bootstrap/reports/transpose2_local_handwritten_lane_summary_20260331.md`
- `session_bootstrap/reports/transpose_add6_local_handwritten_lane_summary_20260331.md`
- `session_bootstrap/reports/conv2d3_add15_local_handwritten_lane_summary_20260331.md`
- `session_bootstrap/reports/mean4_local_handwritten_lane_summary_20260331.md`

以及对应目录：

- `session_bootstrap/handwritten/fused_conv2d_transpose1_add9/`
- `session_bootstrap/handwritten/fused_conv2d_transpose2_add12/`
- `session_bootstrap/handwritten/fused_conv2d_transpose_add6/`
- `session_bootstrap/handwritten/fused_conv2d3_add15/`
- `session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/`
