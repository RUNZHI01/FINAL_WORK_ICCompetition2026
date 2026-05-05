# 手写线与 ACL 复测说明（OpenAMP 三核板状态）

- 日期: 2026-04-04
- 范围: 在目标 OpenAMP / 3-core Linux + RTOS 板状态下，重新比较 `Trusted Current`、`Handwritten final`、`ACL integration line`
- 对照报告: `session_bootstrap/reports/handwritten_acl_retest_under_non_openamp_boardstate_2026-04-04.md`
- 结论级别: 本 session 三核态实测记录，可直接用于解释“为什么这次结果和四核态记忆不一致”

## 一、板状态收口

本轮开始前，板子处于非 OpenAMP 状态：

- `remoteproc0=offline`
- `cpu online=0-3`
- `nproc=4`

随后按板上既有 bring-up 路径执行：

```bash
sudo /home/user/open-amp/set_env.sh
sudo timeout 15s /home/user/open-amp/rpmsg-demo
```

bring-up 后与全部复测结束后的板端状态一致：

- `remoteproc0=running`
- `cpu online=0-2`
- `nproc=3`
- `/dev/rpmsg0` 与 `/dev/rpmsg_ctrl0` 均存在

因此，本报告中的所有结果都来自同一目标板状态：`3-core Linux + RTOS demo mode`。

## 二、本轮执行口径

- 只跑三条 `current` 线，不重复跑相同 baseline
- payload 取 `run_median_ms`
- reconstruction 取 300 张图的 `run_mean_ms`
- 三条线都显式注入：
  - `OMP_NUM_THREADS=3`
  - `TVM_NUM_THREADS=3`
- 本轮 env 与 run id 落在：
  - `session_bootstrap/tmp/openamp_3core_retest_20260404_192313/`

## 三、三核态最新结果

| Line | SHA | Payload Median ms | Reconstruction Mean ms/image | 相对三核态 Trusted Current |
|---|---|---:|---:|---|
| Trusted Current | `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1` | `242.628` | `350.059` | 基线 |
| Handwritten final | `2aa25d2ba2ea3f76533b6c40809521e19ade5c8798160b369c3527834e0ae216` | `242.044` | `345.267` | payload `-0.584 ms`，reconstruction `-4.792 ms` |
| ACL integration line | `602371c27826d44a39bbfc2eb01c45e7d866d4f968c8cb2ddc4dd91c354fedba` | `246.820` | `353.408` | payload `+4.192 ms`，reconstruction `+3.349 ms` |

本轮三核态下的排序是：

1. `Handwritten final`
2. `Trusted Current`
3. `ACL integration line`

但三者已经非常接近，差异量级只有几毫秒，而不再是四核态报告里的几十毫秒。

## 四、与旧四核态报告的直接对照

旧报告 `session_bootstrap/reports/handwritten_acl_retest_under_non_openamp_boardstate_2026-04-04.md` 记录的是非 OpenAMP 四核态结果：

- Trusted Current: payload `124.808 ms`, reconstruction `236.616 ms`
- Handwritten final: payload `152.779 ms`, reconstruction `257.251 ms`
- ACL integration line: payload `161.003 ms`, reconstruction `264.927 ms`

与本轮三核态结果对照如下：

| Line | Payload: 4-core -> 3-core | Reconstruction: 4-core -> 3-core |
|---|---:|---:|
| Trusted Current | `124.808 -> 242.628` (`+117.820 ms`, `+94.40%`) | `236.616 -> 350.059` (`+113.443 ms`, `+47.94%`) |
| Handwritten final | `152.779 -> 242.044` (`+89.265 ms`, `+58.43%`) | `257.251 -> 345.267` (`+88.016 ms`, `+34.21%`) |
| ACL integration line | `161.003 -> 246.820` (`+85.817 ms`, `+53.30%`) | `264.927 -> 353.408` (`+88.481 ms`, `+33.40%`) |

可以直接看到：

- 三条线在切回 OpenAMP 三核态后都整体变慢了
- `Trusted Current` 受板态变化的影响最大，尤其 payload 从 `124.808 ms` 上升到 `242.628 ms`
- 这会直接改变三条线之间的相对排名和相对差距

## 五、对“为什么和印象不一样”的解释

如果你的印象来自更早的非 OpenAMP / 四核态 session，那么这次看到的结果不一样是正常的，因为比较前提已经变了：

- 四核态下，`Trusted Current` 明显领先
- 三核态下，`Trusted Current` 的领先优势基本消失
- `Handwritten final` 在三核态下已经和 `Trusted Current` 基本打平，且略快
- `ACL integration line` 在三核态下只比 `Trusted Current` 略慢，不再像四核态记录里那样落后很多

更直接地说，本轮异常并不是“手写线 / ACL 线突然坏了”，而是：

- 之前看到的是 `4-core Linux performance mode`
- 本轮复测的是 `3-core Linux + RTOS demo mode`

两种 operating mode 本来就不应混写成同一口径。

## 六、保守结论

- 如果问题是“为什么当前测出来的结果和我印象里不一样”，答案是：板状态确实变了，而且这个变化足以重排三条线的相对差距。
- 在目标 OpenAMP 三核态下，三条线目前是近距离竞争，不是四核态报告里那种明显拉开。
- 当前三核态的更稳妥表述应是：
  - `Handwritten final` 与 `Trusted Current` 基本打平，手写线略快
  - `ACL integration line` 略慢于这两条线，但差距很小
  - 四核态结果与三核态结果不能直接混为一个结论

## 七、相关工件

- env: `session_bootstrap/tmp/openamp_3core_retest_20260404_192313/`
- logs:
  - `session_bootstrap/logs/openamp_3core_trusted_current_payload_20260404_192313.current_only.log`
  - `session_bootstrap/logs/openamp_3core_trusted_current_reconstruction_20260404_192313.current_only.log`
  - `session_bootstrap/logs/openamp_3core_handwritten_payload_20260404_192313.current_only.log`
  - `session_bootstrap/logs/openamp_3core_handwritten_reconstruction_20260404_192313.current_only.log`
  - `session_bootstrap/logs/openamp_3core_acl_payload_20260404_192313.current_only.log`
  - `session_bootstrap/logs/openamp_3core_acl_reconstruction_20260404_192313.current_only.log`
