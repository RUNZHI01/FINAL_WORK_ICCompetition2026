# Runtime-Joint-Top6 Targeted Staging Search（2026-03-30）

## 目的

joint-top5 staging 候选已经把 integrated payload 从秒级灾难拉回到 `223.182 ms` 的正常量级，并且 runtime reprobe 不再出现极端双热点 snapback；但 reprobe 里新的 top-1 已经变成：

- `fused_conv2d_add2`

因此下一轮最合理的继续对象不是 blind 扩预算，而是把这个新的 top-1 也纳入联合保护集，形成 joint-top6。

## 当前 joint-top6 目标

- `fused_conv2d_add2`
- `fused_conv2d_transpose2_add12`
- `fused_conv2d_transpose1_add9`
- `fused_conv2d_transpose_add6`
- `fused_conv2d3_add15`
- `fused_conv2d2_add2`

对应 env / wrapper：

- env:
  - `session_bootstrap/config/rpc_tune_current_safe.baseline_seeded_warm_start.runtime_joint_top6_targeted.recommended_cortex_a72_neon.2026-03-30.phytium_pi.env`
- wrapper:
  - `session_bootstrap/scripts/run_phytium_runtime_joint_top6_targeted_staging_search.sh`

## 默认执行入口

```bash
bash ./session_bootstrap/scripts/run_phytium_runtime_joint_top6_targeted_staging_search.sh
```

特点：

- 仍然只在 staging archive 中验证：
  - `/home/user/Downloads/jscc-test/jscc_staging`
- 不覆盖 trusted current 主线；
- 目标是验证“再把 `fused_conv2d_add2` 纳入保护后，payload / reprobe 是否继续改善”。

## 参数选择

- `TUNE_TOTAL_TRIALS=500`
- `TUNE_MAX_TRIALS_PER_TASK=84`

思路是：

- 继续保护前一轮已知关键点；
- 但避免对任一子集过猛进攻；
- 在 staging 中先看 integrated artifact 是否进一步稳定。

## Promote 条件

只有下面条件同时满足，才考虑把 joint-top6 staging 候选升级为 promote 候选：

1. staging payload 优于当前 joint-top5 staging（至少方向继续改善）；
2. runtime reprobe 不再出现新的 dominating hotspot；
3. 仍然优于前两轮坏候选，并且接近 trusted current 主线口径。
