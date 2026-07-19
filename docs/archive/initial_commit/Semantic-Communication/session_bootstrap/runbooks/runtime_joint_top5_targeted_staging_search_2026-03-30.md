# Runtime-Joint-Top5 Targeted Staging Search（2026-03-30）

## 目的

在 `runtime-top2` 和 `runtime-shifted-top3` 两轮定向深搜后，已经明确：

- 只保护原 top-2，会把热点转移到 shifted-top3；
- 只保护 shifted-top3，又会把热点弹回原 top-2；
- 因此下一轮更合理的做法不是继续 blind retarget，而是先试一个 **联合目标集**，并且只在 staging archive 验证，不污染 trusted current 主线。

## 当前 joint-top5 目标

- `fused_conv2d_transpose2_add12`
- `fused_conv2d_transpose1_add9`
- `fused_conv2d_transpose_add6`
- `fused_conv2d3_add15`
- `fused_conv2d2_add2`

对应 env / wrapper：

- env:
  - `session_bootstrap/config/rpc_tune_current_safe.baseline_seeded_warm_start.runtime_joint_top5_targeted.recommended_cortex_a72_neon.2026-03-30.phytium_pi.env`
- wrapper:
  - `session_bootstrap/scripts/run_phytium_runtime_joint_top5_targeted_staging_search.sh`

## 默认执行入口

```bash
bash ./session_bootstrap/scripts/run_phytium_runtime_joint_top5_targeted_staging_search.sh
```

特点：

- 仍复用既有 baseline-seeded warm-start incremental 路径；
- 但默认 remote archive 是 staging：
  - `/home/user/Downloads/jscc-test/jscc_staging`
- 因此即使新 artifact 回归，也不会覆盖 current 主线。

## 参数选择

- `TUNE_TOTAL_TRIALS=500`
- `TUNE_MAX_TRIALS_PER_TASK=100`
- 目标是避免再次出现“对单个子集进攻过猛、整体 balance 失衡”的问题。

## 何时允许 promote

只有当下面条件都满足，才考虑把 staging candidate promote 到 current archive：

1. safe runtime payload 至少回到 trusted current 同量级；
2. runtime reprobe 不再出现“旧 top-2 ↔ shifted-top3”来回弹跳；
3. SHA / report / DB 路径齐全可追溯。

在这之前，staging candidate 只能当候选，不得覆盖 trusted current。
