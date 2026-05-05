# `fused_conv2d_transpose1_add9` 手写算子工作审查稿

- 日期：2026-03-31
- 项目：`tvm-飞腾派项目`
- 工作区：`/home/tianxing/tvm_metaschedule_execution_project`
- 审查对象：`session_bootstrap/handwritten/fused_conv2d_transpose1_add9/` 这条 handwritten / scheduled-form `transpose1` 试验线
- 当前结论一句话：**这条线已经从“流程搭建”推进到“真实手写算子改写 + 本地 schedule-preserving 消费”，但目前还没有可以对外宣称的性能提升结论。**

---

## 1. 为什么会启动这条手写算子线

`transpose1` 是当前 runtime hotspot 之一，目标是针对：

- `fused_conv2d_transpose1_add9`

做最小、可审阅、可回滚的手写算子尝试。

但这条线一开始就有一个大坑：

- 旧 handwritten 路径走的是 **raw pre-compile replacement**
- 这会破坏当前 best staging 候选的 MetaSchedule schedule 上下文
- 所以“改了算子以后变快/变慢”很容易被评估路径本身污染

因此，这条线实际分成了两段：

1. **先修评估路径**
2. **再做真正的算子改写**

---

## 2. 作为对照的基线到底是谁

这条 handwritten 线里，曾经主要拿下面这版做局部对照：

### 2.1 handwritten 线的局部参考 staging

文件：
- `session_bootstrap/reports/current_best_staging_candidate_20260331.md`
- `session_bootstrap/reports/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315.md`

关键事实：
- run id: `phytium_runtime_joint_top6_targeted_staging_search_20260330_2315`
- artifact sha256: `5bd14b9f97d1d06f04a484cd8b1b3f57a955d65711ed65a22f9925dcec44698d`
- **payload / safe runtime**: `159.943 ms`

注意：
- 这个 `159.943 ms` 是 **payload 推理时间**
- **不是端到端 reconstruction 时间**

### 2.2 项目正式最优 trusted current

文件：
- `session_bootstrap/reports/inference_compare_currentsafe_chunk4_refresh_20260313_1758.md`
- `session_bootstrap/reports/inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md`

关键事实：
- trusted current sha: `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`
- **payload**: `130.219 ms`
- **真实端到端 reconstruction**: `230.339 ms/image`

也就是说：

- `5bd14b9f...` 这版 staging 其实**比正式最优 trusted current 慢**
- 之所以还用它做 handwritten 线对照，不是因为它是全局最优，而是因为：
  - 它有完整的 tuning DB
  - task summary 完整
  - post-db scheduled context 可复用
  - 更适合做 local schedule-preserving 试验

---

## 3. 我在仓库里具体做了什么

下面按阶段讲，不只说结论，也给具体路径。

---

## 4. 阶段 A：先修 handwritten 评估路径

### 4.1 修正 handwritten 模块导入链

提交：
- `360b881` — `Fix handwritten module loading for TVM script import`

涉及路径：
- `session_bootstrap/scripts/rpc_tune.py`

作用：
- 修复 TVM Script 动态导入时 `sys.modules` 缺失导致的 `KeyError`
- 让 checked-in handwritten candidate 模块能被稳定加载

### 4.2 记录 `v0` 回归诊断

提交：
- `d4c6c24` — `tvm: record transpose1 handwritten v0 diagnosis`

核心报告：
- `session_bootstrap/reports/transpose1_handwritten_v0_regression_diagnosis_20260331.md`
- `session_bootstrap/reports/phytium_handwritten_fused_conv2d_transpose1_add9_20260331_044114.md`

结论：
- `v0` 并不是没命中目标算子
- 而是命中了错误的评估语义层：**pre-compile raw replacement**
- 它改动后 workload 结构变了，但 warm-start tuning records 还是旧结构学到的记录
- 所以很可能掉到了没有 history-best schedule reuse 的慢路径

已知结果：
- reference staging artifact: `5bd14b9f...`
- reference staging payload: `159.943 ms`
- handwritten `v0` artifact: `b654d550...`
- handwritten `v0` safe runtime payload: `655.693 ms`

最终处理：
- `v0 = drop / not for reprobe`

### 4.3 把旧 handwritten 路径正式降级为 diagnostic-only

提交：
- `758e4bf` — `Tighten transpose1 handwritten evaluation semantics`

涉及：
- `session_bootstrap/scripts/rpc_tune.py`
- `session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_manual_candidate.py`
- 对应 README / tests

作用：
- 明确旧 raw pre-compile handwritten 路径只用于：
  - hook wiring
  - 结构验证
- 不再把它默认为性能证据

---

## 5. 阶段 B：建立 schedule-preserving 本地验证路径

目标：
- 不再让 handwritten 试验直接绑定到 raw pre-compile replacement
- 而是尽量站在 **post-db scheduled** 这层做本地验证

### 5.1 设计 note 与 seam 探针

关键提交：
- `8b627ad` — `Document transpose1 schedule-preserving seam`
- `104fe46` — `Enhance transpose1 seam probe coverage`
- `18cb4ae` — `Add transpose1 scheduled-task comparison probe`
- `533ca9c` — `Probe transpose1 post-db scheduled swap`
- `84df193` — `Export transpose1 post-db local build artifacts`

关键文件：
- `session_bootstrap/reports/transpose1_schedule_preserving_seam_note_20260331.md`
- `session_bootstrap/scripts/probe_transpose1_schedule_preserving_seam.py`

这部分做成了什么：
- 验证 best staging DB 可以恢复 `transpose1` 的 scheduled task/module
- 验证 `MetaScheduleApplyDatabase` 之后 full module 里还能定位到该 global
- 验证可以对这个 scheduled `PrimFunc` 做 post-db swap
- 验证 swapped full module 能本地 build/export

### 5.2 把这条路径接进一套 local-first workflow

关键提交：
- `073be0a` — `Integrate transpose1 local schedule-preserving build path`
- `feb61e2` — `Align transpose1 scaffold to local-first workflow`
- `dc4b92e` — `Surface transpose1 local build artifact paths`
- `f4caac2` — `Clarify transpose1 overlay local build next step`
- `c4fb7c1` — `Sync transpose1 local build results into scaffold`
- `d2b7716` — `Add transpose1 local build-and-sync wrapper`
- `bbe2992` — `Show transpose1 latest local build snapshot`

关键脚本：
- `session_bootstrap/scripts/run_transpose1_post_db_local_build.py`
- `session_bootstrap/scripts/sync_transpose1_post_db_local_build_result.py`
- `session_bootstrap/scripts/run_transpose1_post_db_local_build_and_sync.py`

关键 scaffold 目录：
- `session_bootstrap/tmp/handwritten_fused_conv2d_transpose1_add9_scaffold/`

关键本地产物目录：
- `session_bootstrap/tmp/transpose1_post_db_swap_local_build/`

这部分做成了什么：
- 一键跑本地 post-db build
- 一键把 artifact/report/sha 回填到 scaffold bookkeeping/template/env
- scaffold 目录里可直接看到：
  - latest snapshot
  - artifact path
  - report path
  - sha256
  - build/swap/export 状态

---

## 6. 阶段 C：建立 scheduled-form 参考 seed

### 6.1 导出 post-db scheduled reference seed

提交：
- `9bf0cda` — `Add transpose1 scheduled-form seed handoff`

新增文件：
- `session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_post_db_scheduled_reference_seed_tir.py`
- `session_bootstrap/handwritten/fused_conv2d_transpose1_add9/post_db_scheduled_reference_seed_manifest.json`

新增脚本：
- `session_bootstrap/scripts/refresh_fused_conv2d_transpose1_add9_post_db_scheduled_seed.py`

作用：
- 从 post-db scheduled 形态导出一份**冻结的参考 seed**
- 明确把它和旧 raw pre-compile seed 区分开

真实导出结果：
- reference TIR SHA：`fa109a892d37c1a49821e42cda754941e785de3fe9cb4d29e1f6aaef6a1da708`
- manifest SHA：`30f153aba44fc0608fcd8c6de27670e56a0edc1a277fc78c4edd4632da4dd5be`

---

## 7. 阶段 D：建立 scheduled-form `v1` working copy

### 7.1 从 reference seed 派生 editable working copy

提交：
- `8f30cd2` — `Add transpose1 scheduled-form v1 working copy`

新增文件：
- `session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v1_working_copy_tir.py`
- `session_bootstrap/handwritten/fused_conv2d_transpose1_add9/scheduled_form_candidate_v1_working_copy_manifest.json`

新增脚本：
- `session_bootstrap/scripts/refresh_fused_conv2d_transpose1_add9_scheduled_form_working_copy.py`

作用：
- 让后续真正的 `v1` 不再从 raw pre-compile seed 起手
- 而是从更诚实的 scheduled-form seed 起手

真实导出结果：
- working copy TIR SHA：`93df0a3ff023474812dbe2015fac3001808382da56988d0f436273a523f69097`
- working copy manifest SHA：`8e0d882e0b5d2faafbd046933f5b2abd728710e31646e2c5a2e2d68674c752df`

---

## 8. 阶段 E：第一版真实 `v1` 算子改写

### 8.1 真实改动内容

提交：
- `1e1f4a6` — `Apply first transpose1 scheduled-form v1 edit`

改动文件：
- `session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v1_working_copy_tir.py`
- `session_bootstrap/handwritten/fused_conv2d_transpose1_add9/scheduled_form_candidate_v1_working_copy_manifest.json`

这版 `v1` 改了什么：
- bias 直接写入 scheduled `compute_init / compute_update` 路径
- 删除全尺寸 `compute_intermediate`
- 删除尾部 `T_add` pass

这是这条 handwritten 线里第一版真正的 operator-side 改写，不再只是 workflow / seed / manifest。

### 8.2 当前 `v1` working copy 的角色

它现在不是：
- hook-facing module
- 性能结论
- 远端验证结论

它现在是：
- **editable scheduled-form v1 surface**
- local-only
- diagnostic-only

---

## 9. 阶段 F：把 `v1` 接进本地 schedule-preserving 消费路径

提交：
- `9a3f8f4` — `Wire transpose1 v1 into local build path`

新增文件：
- `session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v1.py`

更新文件：
- `session_bootstrap/scripts/run_transpose1_post_db_local_build.py`
- `session_bootstrap/scripts/run_transpose1_post_db_local_build_and_sync.py`

作用：
- 默认 local schedule-preserving path 不再吃旧 candidate
- 而是默认消费：
  - `fused_conv2d_transpose1_add9_scheduled_form_candidate_v1.py`
  - 再由它指向：
    - `fused_conv2d_transpose1_add9_scheduled_form_candidate_v1_working_copy_tir.py`

### 9.1 真实本地消费结果

真实运行：
- `python3 ./session_bootstrap/scripts/run_transpose1_post_db_local_build.py --output-dir ./session_bootstrap/tmp/transpose1_post_db_swap_local_build_v1`

结果：
- `candidate_impl = .../fused_conv2d_transpose1_add9_scheduled_form_candidate_v1.py`
- `candidate_version = v1_working_copy`
- `candidate_status = first_local_operator_side_v1_edit_applied`
- `swap_succeeded = true`
- `build_status = built`
- artifact SHA：`4f0986e4806bece9801ab38b4ec121870406476c3d9a1c870bbc0453e18ef2fc`

这说明：
- `v1` 不只是存在于仓库里
- 它已经能被现有 post-db local path 真实消费

---

## 10. 结果汇总：我到底做成了什么

### 10.1 已做成的

我已经做成了以下闭环：

1. `transpose1` handwritten 旧评估路径的问题被确认并写清楚
2. raw pre-compile handwritten 路径被降为 diagnostic-only
3. post-db schedule-preserving 本地验证路径已打通
4. scaffold / bookkeeping / snapshot / wrapper 已可用
5. post-db scheduled reference seed 已 checked-in
6. scheduled-form `v1` working copy 已 checked-in
7. 第一版真实 `v1` operator-side 改写已落地
8. `v1` 已能被本地 schedule-preserving 路径真实消费

### 10.2 还没做成的

还没做成的是：

- **没有可信 runtime / payload / e2e 性能结论**
- 也就是说，当前还不能说：
  - `v1` 加速了
  - `v1` 比 `5bd14b9f...` 更好
  - `v1` 比正式 trusted current `6f236b07...` 更好

---

## 11. 当前结果到底如何

### 11.1 已确认失败的：`v0`

- safe runtime payload：`655.693 ms`
- 对照 staging：`159.943 ms`
- 结论：**明显回退，已 drop**

### 11.2 已确认可消费的：`v1`

- 本地 schedule-preserving path 已能真实消费
- `swap_succeeded = true`
- `build_status = built`
- artifact SHA：`4f0986e4806bece9801ab38b4ec121870406476c3d9a1c870bbc0453e18ef2fc`

### 11.3 还不知道的：`v1` 是否真的更快

目前未知：
- `v1` payload 是否更快
- `v1` e2e 是否更快
- `v1` 是否能超过 handwritten 参考 staging `5bd14b9f...`
- 更别提是否能超过正式 trusted current `6f236b07...`

---

## 12. 审查时我建议你重点看什么

### 12.1 看我是否真的在“改算子”而不是“只改流程”

优先看：
- `session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v1_working_copy_tir.py`
- `session_bootstrap/handwritten/fused_conv2d_transpose1_add9/scheduled_form_candidate_v1_working_copy_manifest.json`

### 12.2 看我现在的 edit surface 是否合理

看：
- post-db reference seed 和 working copy 是否分离清楚
- old raw seed 是否仍保留作回退/对照
- 现在的 bias fold + remove `compute_intermediate` / `T_add` 是否合理

### 12.3 看我是不是在拿错误基线自嗨

我现在没有宣称性能提升，原因就是：
- handwritten 线对照 staging：`5bd14b9f...`（payload `159.943 ms`）
- 项目正式最优 trusted current：`6f236b07...`（payload `130.219 ms`，e2e `230.339 ms/image`）

所以这条线现在最多只能说：
- **local schedule-preserving `v1` 已可消费**
- **未证明加速**

---

## 13. 我认为的下一步（供你拍板）

如果你认可我这条线的方向，下一步我建议二选一：

### 方案 A：先补 `v1` 的 local evidence / compare note
优点：
- 更稳
- 不急着上远端
- 先把“已知 / 未知 / 是否值得更强验证”写清楚

### 方案 B：继续做第二处 scheduled-form v1 改写
优点：
- 更快进入真实算子优化

我个人目前倾向：
- **先做 A，再决定要不要继续 B**

因为现在 `v1` 虽然已经可本地消费，但还没有任何可信性能结论。

---

## 14. 关键仓库路径总表

### 14.1 旧 raw handwritten 路径
- `session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_manual_candidate.py`
- `session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_candidate_v0_tir.py`
- `session_bootstrap/reports/phytium_handwritten_fused_conv2d_transpose1_add9_20260331_044114.md`
- `session_bootstrap/reports/transpose1_handwritten_v0_regression_diagnosis_20260331.md`

### 14.2 schedule-preserving 路径
- `session_bootstrap/scripts/probe_transpose1_schedule_preserving_seam.py`
- `session_bootstrap/scripts/run_transpose1_post_db_local_build.py`
- `session_bootstrap/scripts/sync_transpose1_post_db_local_build_result.py`
- `session_bootstrap/scripts/run_transpose1_post_db_local_build_and_sync.py`

### 14.3 scheduled reference / working copy
- `session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_post_db_scheduled_reference_seed_tir.py`
- `session_bootstrap/handwritten/fused_conv2d_transpose1_add9/post_db_scheduled_reference_seed_manifest.json`
- `session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v1_working_copy_tir.py`
- `session_bootstrap/handwritten/fused_conv2d_transpose1_add9/scheduled_form_candidate_v1_working_copy_manifest.json`
- `session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v1.py`

### 14.4 scaffold / bookkeeping / snapshot
- `session_bootstrap/tmp/handwritten_fused_conv2d_transpose1_add9_scaffold/bookkeeping.json`
- `session_bootstrap/tmp/handwritten_fused_conv2d_transpose1_add9_scaffold/validation_report_template.md`
- `session_bootstrap/tmp/handwritten_fused_conv2d_transpose1_add9_scaffold/latest_local_build_sync_snapshot.md`

---

## 15. 最后的审查提示

如果你要审我这条线，我建议你直接围绕三个问题看：

1. **我是不是已经真的开始手写算子？**
   - 是，`v1 working copy` 已有第一版真实改写

2. **我是不是还在拿不可信的评估路径骗自己？**
   - 没有，我现在已经尽量切到 post-db schedule-preserving local path

3. **我有没有证据证明它更快？**
   - 还没有
   - 现在最诚实的结论仍然是：
     - `v0` 变慢
     - `v1` 可本地消费
     - **性能未知**
