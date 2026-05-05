# 3.31 手写算子材料总索引（补整理）

- 整理日期：2026-04-02
- 对应工作日：2026-03-31
- 项目：`tvm-飞腾派项目`
- 工作区：`/home/tianxing/tvm_metaschedule_execution_project`

## 一句话结论

2026-03-31 不是单点试验，而是围绕 **best staging candidate (`5bd14b9f...`)** 对多个 runtime hotspot 建立了系统性的 handwritten / scheduled-form 优化材料：

- 至少 **8 个算子** 被纳入 handwritten hotspot shortlist；
- 至少 **5 条算子线** 已形成 operator-specific lane / runbook / local proof artifact；
- 其中 **`fused_conv2d_transpose1_add9`** 已经从“流程搭建”推进到“真实手写算子改写 + schedule-preserving 本地消费”，其余多条线已完成 post-db scheduled-form seed / working copy / local build proof。

## 总入口

- 热点候选总表：`session_bootstrap/reports/handwritten_hotspot_candidates_20260331.md`
- 最佳 staging 候选冻结：`session_bootstrap/reports/current_best_staging_candidate_20260331.md`
- 当前 best staging SHA：`5bd14b9f97d1d06f04a484cd8b1b3f57a955d65711ed65a22f9925dcec44698d`
- 当前 best staging payload：`159.943 ms`

## 3.31 纳入手写优化主清单的算子

### Wave 1：Conv / Deconv

1. `fused_conv2d_transpose1_add9`
2. `fused_conv2d_transpose2_add12`
3. `fused_conv2d_transpose_add6`
4. `fused_conv2d3_add15`

### Wave 2：Norm / Reduction

5. `fused_mean4_subtract4_divide4_multiply4_add14_relu3`
6. `fused_variance4_add13_tir_sqrt4`
7. `fused_mean3_subtract3_divide3_multiply3_add11_relu2`
8. `fused_variance3_add10_tir_sqrt3`

来源：`session_bootstrap/reports/handwritten_hotspot_candidates_20260331.md`

---

## 已形成独立材料的算子线

### 1) `fused_conv2d_transpose1_add9`

状态：**最深入的一条线**，已经不只是 lane scaffolding，而是完成了：

- handwritten 旧路径回归诊断；
- raw pre-compile 路径降级为 diagnostic-only；
- schedule-preserving seam 设计与探针；
- post-db scheduled reference seed 导出；
- scheduled-form working copy；
- 本地 build / sync / scaffold bookkeeping。

关键证据：

- 工作审查稿：`session_bootstrap/reports/transpose1_handwritten_work_review_20260331.md`
- 方案 note：`session_bootstrap/reports/transpose1_schedule_preserving_seam_note_20260331.md`
- v0 回归诊断：`session_bootstrap/reports/transpose1_handwritten_v0_regression_diagnosis_20260331.md`
- 本地证据：
  - `session_bootstrap/reports/transpose1_handwritten_v1_local_evidence_20260331.md`
  - `session_bootstrap/reports/transpose1_v1_local_evidence_20260331.md`
- 远端基准：
  - `session_bootstrap/reports/transpose1_v1_remote_benchmark_20260331_185155.md`
  - `session_bootstrap/reports/transpose1_v1_remote_benchmark_20260331_185804.md`
  - `session_bootstrap/reports/transpose1_p2_remote_benchmark_20260331_192521.md`
  - `session_bootstrap/reports/transpose1_p4_remote_benchmark_20260331_193220.md`

代码与脚本：

- lane root：`session_bootstrap/handwritten/fused_conv2d_transpose1_add9/`
- seam probe：`session_bootstrap/scripts/probe_transpose1_schedule_preserving_seam.py`
- 本地 build：
  - `session_bootstrap/scripts/run_transpose1_post_db_local_build.py`
  - `session_bootstrap/scripts/sync_transpose1_post_db_local_build_result.py`
  - `session_bootstrap/scripts/run_transpose1_post_db_local_build_and_sync.py`

### 2) `fused_conv2d_transpose2_add12`

状态：**已建立完整 local-only post-db scheduled-form lane，并完成 local proof build**。

关键证据：

- lane summary：`session_bootstrap/reports/transpose2_local_handwritten_lane_summary_20260331.md`
- runbook：`session_bootstrap/runbooks/handwritten_fused_conv2d_transpose2_add12_runbook_2026-03-31.md`

代码与脚本：

- lane root：`session_bootstrap/handwritten/fused_conv2d_transpose2_add12/`
- seed refresh：`session_bootstrap/scripts/refresh_fused_conv2d_transpose2_add12_post_db_scheduled_seed.py`
- working copy refresh：`session_bootstrap/scripts/refresh_fused_conv2d_transpose2_add12_scheduled_form_working_copy.py`
- local build：`session_bootstrap/scripts/run_transpose2_post_db_local_build.py`

local proof artifact：

- `.so`：`session_bootstrap/tmp/transpose2_post_db_swap_local_build_proof_20260331/fused_conv2d_transpose2_add12_post_db_swap.so`
- report：`session_bootstrap/tmp/transpose2_post_db_swap_local_build_proof_20260331/fused_conv2d_transpose2_add12_post_db_swap_report.json`

### 3) `fused_conv2d_transpose_add6`

状态：**已建立完整 local-only post-db scheduled-form lane，并完成 local proof build**。

关键证据：

- lane summary：`session_bootstrap/reports/transpose_add6_local_handwritten_lane_summary_20260331.md`
- runbook：`session_bootstrap/runbooks/handwritten_fused_conv2d_transpose_add6_runbook_2026-03-31.md`

代码与脚本：

- lane root：`session_bootstrap/handwritten/fused_conv2d_transpose_add6/`
- seed refresh：`session_bootstrap/scripts/refresh_fused_conv2d_transpose_add6_post_db_scheduled_seed.py`
- working copy refresh：`session_bootstrap/scripts/refresh_fused_conv2d_transpose_add6_scheduled_form_working_copy.py`
- local build：`session_bootstrap/scripts/run_transpose_add6_post_db_local_build.py`

local proof artifact：

- `.so`：`session_bootstrap/tmp/transpose_add6_post_db_swap_local_build_proof_20260331/fused_conv2d_transpose_add6_post_db_swap.so`
- report：`session_bootstrap/tmp/transpose_add6_post_db_swap_local_build_proof_20260331/fused_conv2d_transpose_add6_post_db_swap_report.json`

### 4) `fused_conv2d3_add15`

状态：**已建立完整 local-only post-db scheduled-form lane，并完成 local proof build**。

关键证据：

- lane summary：`session_bootstrap/reports/conv2d3_add15_local_handwritten_lane_summary_20260331.md`
- runbook：`session_bootstrap/runbooks/handwritten_fused_conv2d3_add15_runbook_2026-03-31.md`

代码与脚本：

- lane root：`session_bootstrap/handwritten/fused_conv2d3_add15/`
- seed refresh：`session_bootstrap/scripts/refresh_fused_conv2d3_add15_post_db_scheduled_seed.py`
- working copy refresh：`session_bootstrap/scripts/refresh_fused_conv2d3_add15_scheduled_form_working_copy.py`
- local build：`session_bootstrap/scripts/run_conv2d3_add15_post_db_local_build.py`

local proof artifact：

- `.so`：`session_bootstrap/tmp/conv2d3_add15_post_db_swap_local_build_proof_20260331/fused_conv2d3_add15_post_db_swap.so`
- report：`session_bootstrap/tmp/conv2d3_add15_post_db_swap_local_build_proof_20260331/fused_conv2d3_add15_post_db_swap_report.json`

### 5) `fused_mean4_subtract4_divide4_multiply4_add14_relu3`

状态：**已建立 local-only handwritten lane，并完成 post-db swap / local build proof**；但当前 best staging 上没有直接 mean4 DB schedule record，因此这条线当前更偏“edit surface ready + diagnostic proof”，不是 schedule-backed equivalence claim。

关键证据：

- lane summary：`session_bootstrap/reports/mean4_local_handwritten_lane_summary_20260331.md`
- runbook：`session_bootstrap/runbooks/handwritten_fused_mean4_subtract4_divide4_multiply4_add14_relu3_runbook_2026-03-31.md`

代码与脚本：

- lane root：`session_bootstrap/handwritten/fused_mean4_subtract4_divide4_multiply4_add14_relu3/`
- seed refresh：`session_bootstrap/scripts/refresh_fused_mean4_subtract4_divide4_multiply4_add14_relu3_post_db_scheduled_seed.py`
- working copy refresh：`session_bootstrap/scripts/refresh_fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_working_copy.py`
- local build：`session_bootstrap/scripts/run_mean4_post_db_local_build.py`

local proof artifact：

- `.so`：`session_bootstrap/tmp/mean4_post_db_swap_local_build_proof_20260331/fused_mean4_subtract4_divide4_multiply4_add14_relu3_post_db_swap.so`
- report：`session_bootstrap/tmp/mean4_post_db_swap_local_build_proof_20260331/fused_mean4_subtract4_divide4_multiply4_add14_relu3_post_db_swap_report.json`

---

## 需要特别注意的边界

1. 这批 3.31 材料大多是 **staging / local proof / operator lane construction**，不是都已经形成“正式远端性能提升结论”。
2. 真正走到“真实手写算子改写 + 评估语义修正 + 多轮证据”的，当前最完整的是：
   - `fused_conv2d_transpose1_add9`
3. 其余几条线已经非常有价值，因为它们把后续继续做 handwritten TIR 所需的：
   - reference seed
   - working copy
   - runbook
   - local build proof
   - artifact/report path
   已经搭好了。
4. 项目正式对外口径仍应区分：
   - trusted current：`6f236b07...`（正式主线）
   - best staging candidate：`5bd14b9f...`（3.31 手写算子工作的主要固定对照）

## 建议的后续使用方式

1. 把这份索引作为 3.31 handwritten 材料统一入口；
2. 若补答辩 / 论文 / 复盘，优先引用：
   - `handwritten_hotspot_candidates_20260331.md`
   - `current_best_staging_candidate_20260331.md`
   - `transpose1_handwritten_work_review_20260331.md`
   - 各 operator lane summary
3. 若继续工程推进，优先顺序建议：
   - `transpose1`（最成熟）
   - `transpose2`
   - `transpose_add6`
   - `conv2d3_add15`
   - `mean4`

## 最后一句

3.31 的价值，不只是“调快了几个算子”，而是把 **从 runtime hotspot 识别 -> 候选冻结 -> handwritten lane 建立 -> post-db scheduled-form proof -> 局部远端验证** 这条方法链完整地落了下来。
