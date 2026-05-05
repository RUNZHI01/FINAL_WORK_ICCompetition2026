# Handwritten Candidate: fused_conv2d_transpose1_add9（2026-03-31）

## 目的

为 wave-1 priority-1 的手写热点候选 `fused_conv2d_transpose1_add9` 提供一个最小但可执行的 staging-safe 脚手架。

这个 runbook 不负责直接写出手写 TIR kernel；它负责把“候选 artifact 如何落 staging、如何做 payload / reprobe、如何避免污染 trusted current”固化下来。

## 为什么先做它

根据当前 best staging candidate 的 runtime reprobe：

- `session_bootstrap/reports/profiling_runtime_joint_top6_staging_artifact_reprobe_20260331_0010.md`
- `fused_conv2d_transpose1_add9` 仍是 runtime top-1
  - `24275.261 us`
  - `14.60%`

而且它已经跨越多轮 retarget：

- runtime-top2
- runtime-shifted-top3
- runtime-joint-top5
- runtime-joint-top6

都没有从关键热点列表中退出，所以它是当前最合理的第一个手写 TIR / NEON 候选。

## 固定基线

- trusted current mainline SHA：`6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`
- current best staging candidate SHA：`5bd14b9f97d1d06f04a484cd8b1b3f57a955d65711ed65a22f9925dcec44698d`
- 当前最佳 staging 冻结记录：
  - `session_bootstrap/reports/current_best_staging_candidate_20260331.md`

## 最小缺口

现有 operator-specific scaffold 已经能做一件事：

- 当手写候选 artifact SHA 已知时，生成一个 reprobe 用的 profile env

但 engineer 还缺少第一版真正可落地的 validation bundle：

- 一个从 current best staging candidate 派生的 `manual_rebuild.env`
- 一个 payload validate 用的 `manual_validate_inference.env`
- 一个 reprobe 用的 `manual_profile.env`
- 一个记录 candidate SHA / payload / reprobe / decision 的短模板

所以这一步补的是“第一次验证手写候选”所需的最小闭环，而不是新的调优子系统。

## 推荐 staging 归档

手写候选不要进入 `jscc` 或 `jscc_staging`，而是使用单独归档：

```text
/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose1_add9
```

## 最小工作流

### 1) 先生成 validation bundle

先用 current best staging candidate 的冻结证据生成一份最小 bundle：

```bash
python3 ./session_bootstrap/scripts/prepare_fused_conv2d_transpose1_add9_handwritten_scaffold.py
```

默认输出：

```text
session_bootstrap/tmp/handwritten_fused_conv2d_transpose1_add9_scaffold
```

生成内容：

- `manual_rebuild.env`
- `manual_validate_inference.env`
- `manual_profile.env`
- `validation_report_template.md`
- `bookkeeping.json`
- `README.md`

### 2) 只 patch 生成出来的文件

只改 bundle 内文件，不改 trusted-current env：

- 在 `manual_rebuild.env` 里补上启用 `fused_conv2d_transpose1_add9` 手写实现的 env 开关或实现路径
- 本地 rebuild 出 `optimized_model.so` 后，用 `sha256sum` 回填 `manual_validate_inference.env` 与 `manual_profile.env` 里的 `INFERENCE_CURRENT_EXPECTED_SHA256`
- 把 payload / reprobe / final decision 记到 `validation_report_template.md`

### 3) 用 rebuild-only one-shot 跑 payload 验证

这里不再优先走 `run_phytium_current_safe_staging_validate.sh`，因为手写候选的第一版验证更接近 rebuild-only staging validate，而不是再开一轮增量调优。

```bash
bash ./session_bootstrap/scripts/run_phytium_current_safe_one_shot.sh \
  --rebuild-env ./session_bootstrap/tmp/handwritten_fused_conv2d_transpose1_add9_scaffold/manual_rebuild.env \
  --inference-env ./session_bootstrap/tmp/handwritten_fused_conv2d_transpose1_add9_scaffold/manual_validate_inference.env \
  --remote-archive-dir /home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose1_add9 \
  --report-id phytium_handwritten_fused_conv2d_transpose1_add9_$(date +%Y%m%d_%H%M%S)
```

### 4) 再做 runtime reprobe

```bash
python3 ./session_bootstrap/scripts/run_task_5_1_operator_profile.py \
  --run-id profiling_handwritten_fused_conv2d_transpose1_add9_$(date +%Y%m%d_%H%M%S) \
  --hotspot-mode reuse \
  --runtime-mode attempt \
  --trusted-env ./session_bootstrap/tmp/handwritten_fused_conv2d_transpose1_add9_scaffold/manual_profile.env \
  --trusted-variant current \
  --max-inputs 1 \
  --profile-samples 1
```

### 5) 仅在需要时，继续复用旧 helper

如果你已经有了候选 SHA，只想单独刷新 reprobe env，仍然可以继续使用：

```bash
python3 ./session_bootstrap/scripts/prepare_handwritten_fused_conv2d_transpose1_add9_env.py \
  --expected-sha256 <candidate_sha256>
```

## 必须同时满足的保留条件

这个手写候选只有在下面条件都满足时，才值得保留：

1. `artifact_sha256_match = true`
2. safe runtime payload 不劣于当前 best staging candidate（`5bd14b9f...`）
3. reprobe 中 `fused_conv2d_transpose1_add9` 的时间 / 占比显著下降
4. 没有制造新的 dominating hotspot snapback

如果任何一项不满足：

- 保留报告
- 终止这版候选
- 不覆盖 trusted current
- 也不覆盖 current best staging candidate

## Scope Guard

这个 runbook 是 `fused_conv2d_transpose1_add9` 的 operator-specific 脚手架：

- 它只服务于这个 op 的手写验证路径；
- 不引入新 tuning subsystem；
- 不自动生成手写 TIR；
- 不会改写 trusted current 主线。
