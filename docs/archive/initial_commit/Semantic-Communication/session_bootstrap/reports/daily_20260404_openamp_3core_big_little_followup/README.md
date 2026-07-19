# 2026-04-04 日报：OpenAMP 三核复测与 big.LITTLE 跟进

- 日期：2026-04-04
- 主题：先把板子恢复到目标 OpenAMP 三核态，解释 candidate 线结果为什么与四核态记忆不一致；随后确认 big.LITTLE 历史证据范围，并切到 handwritten / ACL 两条 candidate 的异构流水线 compare
- 状态：已完成

## 一、今天已完成

### 1. 板子已恢复到目标 OpenAMP 三核态

- bring-up 路径：
  - `sudo /home/user/open-amp/set_env.sh`
  - `sudo timeout 15s /home/user/open-amp/rpmsg-demo`
- 板态收口：
  - `remoteproc0=running`
  - `cpu online=0-2`
  - `nproc=3`
  - `/dev/rpmsg0` 与 `/dev/rpmsg_ctrl0` 均存在

### 2. 在同一三核板态下重跑了三条 current candidate 线

结果汇总：

| Line | SHA | Payload Median ms | Reconstruction Mean ms/image |
|---|---|---:|---:|
| Trusted Current | `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1` | `242.628` | `350.059` |
| Handwritten final | `2aa25d2ba2ea3f76533b6c40809521e19ade5c8798160b369c3527834e0ae216` | `242.044` | `345.267` |
| ACL integration line | `602371c27826d44a39bbfc2eb01c45e7d866d4f968c8cb2ddc4dd91c354fedba` | `246.820` | `353.408` |

这轮的直接结论：

- 当前“和印象里不一样”主要是板态变化造成的。
- 之前记忆中的明显差距对应的是非 OpenAMP 四核态。
- 在目标 OpenAMP 三核态下，三条线已经非常接近，`Handwritten final` 略快于 Trusted Current，ACL 线也只慢几毫秒。

对应报告：

- `session_bootstrap/reports/handwritten_acl_retest_under_openamp_3core_boardstate_2026-04-04.md`

### 3. big.LITTLE 历史谱系已重新核过

当前可以确认：

- trusted current SHA `6f236b07...6dc1` 明确进过 big.LITTLE 流水线，并且已有正式 compare：
  - `session_bootstrap/reports/big_little_compare_20260318_123300.md`
  - serial `231.522 ms/image`
  - pipeline `134.617 ms/image`
  - throughput uplift `56.077%`
- `Handwritten final`（SHA `2aa25d2b...e216`）与 ACL integration line（SHA `602371c2...edba`）目前都还没有 repo 内正式 big.LITTLE compare 证据。

这意味着：

- 不能直接把 trusted current 的 big.LITTLE uplift 外推到另外两条 candidate。
- 这两条线要不要进答辩或主叙事，必须自己补一轮同口径 compare。

## 二、当前已锁定的 artifact 入口

- Trusted Current：
  - `/home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so`
  - SHA `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`
- Handwritten final：
  - `/home/user/Downloads/jscc-test/jscc_opus_final_retest/tvm_tune_logs/optimized_model.so`
  - SHA `2aa25d2ba2ea3f76533b6c40809521e19ade5c8798160b369c3527834e0ae216`
- ACL integration line：
  - `/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose_add6/tvm_tune_logs/optimized_model.so`
  - SHA `602371c27826d44a39bbfc2eb01c45e7d866d4f968c8cb2ddc4dd91c354fedba`

## 三、三条线的详细调用方式（本轮已补齐）

三条线本轮统一的板态前提都是：

- `sudo /home/user/open-amp/set_env.sh`
- `sudo timeout 15s /home/user/open-amp/rpmsg-demo`
- 板侧状态应收口到 `remoteproc0=running / cpu online=0-2 / nproc=3`

三条线 current-only / serial rerun 的共同 runner 都是：

- `bash ./session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current --max-inputs 300`

三条线 big.LITTLE compare 的共同 wrapper 都是：

- `bash ./session_bootstrap/scripts/run_big_little_compare.sh --env <对应 env>`

逐条可复现入口如下：

- Trusted Current：
  - env：`session_bootstrap/reports/daily_20260404_openamp_3core_big_little_followup/trusted_current_big_little_compare.env`
  - current archive：`/home/user/Downloads/jscc-test/jscc`
  - current artifact：`/home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so`
  - current-only / serial 复现：
    ```bash
    set -a
    source ./session_bootstrap/reports/daily_20260404_openamp_3core_big_little_followup/trusted_current_big_little_compare.env
    set +a
    bash ./session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current --max-inputs 300
    ```
  - big.LITTLE compare 复现：
    ```bash
    bash ./session_bootstrap/scripts/run_big_little_compare.sh \
      --env ./session_bootstrap/reports/daily_20260404_openamp_3core_big_little_followup/trusted_current_big_little_compare.env
    ```

- Handwritten final：
  - env：`session_bootstrap/reports/daily_20260404_openamp_3core_big_little_followup/handwritten_big_little_compare.env`
  - current archive：`/home/user/Downloads/jscc-test/jscc_opus_final_retest`
  - current artifact：`/home/user/Downloads/jscc-test/jscc_opus_final_retest/tvm_tune_logs/optimized_model.so`
  - current-only / serial 复现：
    ```bash
    set -a
    source ./session_bootstrap/reports/daily_20260404_openamp_3core_big_little_followup/handwritten_big_little_compare.env
    set +a
    bash ./session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current --max-inputs 300
    ```
  - big.LITTLE compare 复现：
    ```bash
    bash ./session_bootstrap/scripts/run_big_little_compare.sh \
      --env ./session_bootstrap/reports/daily_20260404_openamp_3core_big_little_followup/handwritten_big_little_compare.env
    ```

- ACL integration line：
  - env：`session_bootstrap/reports/daily_20260404_openamp_3core_big_little_followup/acl_big_little_compare.env`
  - current archive：`/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose_add6`
  - current artifact：`/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose_add6/tvm_tune_logs/optimized_model.so`
  - current-only / serial 复现：
    ```bash
    set -a
    source ./session_bootstrap/reports/daily_20260404_openamp_3core_big_little_followup/acl_big_little_compare.env
    set +a
    bash ./session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current --max-inputs 300
    ```
  - big.LITTLE compare 复现：
    ```bash
    bash ./session_bootstrap/scripts/run_big_little_compare.sh \
      --env ./session_bootstrap/reports/daily_20260404_openamp_3core_big_little_followup/acl_big_little_compare.env
    ```
  - 额外说明：
    - 这条线当前不是 stock ACL kernel 真正入图。
    - 现用 env 会显式注入：
      - `TVM_RUNTIME_PRELOAD_PY=/home/user/Downloads/jscc-test/acl_ab/preload_transpose_add6_tvm_proxy.py`
      - `TVM_TRANSPOSE_ADD6_PROXY_SO=/home/user/Downloads/jscc-test/acl_ab/transpose_add6_tvm_v1/fused_conv2d_transpose_add6_v1_standalone.so`
    - 因而它当前更准确的定义仍然是：`packed-call shim + TVM standalone proxy line`。

## 四、今晚新增完成：三线 big.LITTLE compare

三条 compare 都在同一 OpenAMP 三核板态下完成，板端快照一致保持：

- `remoteproc0=running`
- `cpu online=0-2`
- `nproc=3`
- `big_cores=2`
- `little_cores=0,1`

结果汇总：

| Line | Compare Run | Serial Median ms | Pipeline ms/image | Serial img/s | Pipeline img/s | Throughput Uplift |
|---|---|---:|---:|---:|---:|---:|
| Trusted Current | `big_little_compare_20260404_200243` | `360.218` | `251.913` | `2.755` | `3.970` | `44.102%` |
| Handwritten final | `big_little_compare_20260404_195323` | `342.927` | `252.584` | `2.922` | `3.959` | `35.489%` |
| ACL integration line | `big_little_compare_20260404_195647` | `349.374` | `258.933` | `2.867` | `3.862` | `34.705%` |

这轮 compare 给出的最重要信息是：

- `Handwritten final` 在 current-only / serial 口径下仍然很强，但进 pipeline 后并没有继续拉开，而是与 trusted current 几乎打平。
- `Trusted Current` 虽然 serial median 不是三者里最低，但它在 big.LITTLE pipeline 下拿到最大的吞吐 uplift（`44.102%`），最终 pipeline `ms/image` 反而成为三者最佳。
- ACL integration line 也拿到了明确正 uplift（`34.705%`），说明它不是“进不了流水线”的坏线；但当前端到端 pipeline 结果仍慢于另外两条。

## 五、当晚口径（`2026-04-04` 快照）

- 就 `2026-04-04` 当晚这轮 compare 而言，三核 OpenAMP demo mode 会明显改写三条线在 current-only 口径下的相对差距；当晚切到 big.LITTLE pipeline 后，trusted current 仍然是当时的最佳整体 reference。
- 当晚更准确的结论不是“另外两条线没价值”，而是：`Handwritten final` 与 ACL line 都能在目标板态下稳定进入 pipeline，并拿到约 `35%` 的吞吐提升，但 uplift 仍低于 trusted current 的 `44.102%`。
- 这也是为什么当晚的后续重点会转向“解释为什么另外两条线在 pipeline 下的 uplift 少了大约 `8.6~9.4` 个百分点”。
- 后续 `2026-04-06` 的 handwritten `mean4 v7` follow-up 已继续把这一结论往前推进；最新 same-day 三线口径见本文档第九节。

## 六、相关工件

- current-only 三线复测：
  - `session_bootstrap/reports/handwritten_acl_retest_under_openamp_3core_boardstate_2026-04-04.md`
- trusted current compare：
  - `session_bootstrap/reports/daily_20260404_openamp_3core_big_little_followup/big_little_compare_20260404_200243.md`
- handwritten final compare：
  - `session_bootstrap/reports/daily_20260404_openamp_3core_big_little_followup/big_little_compare_20260404_195323.md`
- ACL integration line compare：
  - `session_bootstrap/reports/daily_20260404_openamp_3core_big_little_followup/big_little_compare_20260404_195647.md`

## 七、今晚补充：单算子公平复核

为了修正旧的 `transpose_add6 standalone ACL +33.9%` 口径，今晚又补了一轮更接近真实部署条件的单算子复核，原则是：

- 板态固定为 OpenAMP 三核
- 证据优先用 **当前计算图内的 runtime profiling**
- 只把 stock ACL 当前能直接对位的三段 transpose 热点拿去和 ACL library standalone 结果比较

本轮最重要的新结论是：

- 旧的 `transpose_add6 ACL +33.9%` standalone 结论不能再引用；同一天、同板子、切到 OpenAMP 三核后，ACL asym benchmark 三次重跑已经明显漂移。
- 当前 repo 里口头叫“ACL integration line”的 `602371c2...edba`，按 env 和 preload 脚本看，实际上是 `packed-call shim + TVM standalone proxy`，还不是真正的 stock ACL kernel 入图。
- 因此，当前最可 defend 的算子级证据应改成：**Handwritten final 在真实图内 profiling 中的收益是成立的，而 ACL 单热点替换仍处在探索态。**

对应报告：

- `session_bootstrap/reports/fair_singleop_handwritten_vs_acl_under_openamp3_graph_20260404.md`

## 八、今晚补充：论文图工件

为避免三条路线在原始绝对值柱状图里“看起来太接近”，本轮又补了三张论文风格中文图，统一放在：

- `session_bootstrap/reports/figures/paper_fig1_operator_performance_cn_20260404.png`
- `session_bootstrap/reports/figures/paper_fig2_e2e_payload_reconstruction_cn_20260404.png`
- `session_bootstrap/reports/figures/paper_fig3_big_little_pipeline_cn_20260404.png`

对应渲染脚本：

- `session_bootstrap/scripts/render_paper_figures_cn_v2_20260404.py`

## 九、2026-04-06 跟进：same-day 三线 big.LITTLE compare

这轮 follow-up 不再跨天引用 `2026-04-04` 的 trusted current / ACL compare，而是把
三条 active line 在同一天同板态下全部补齐：

| Line | Compare Run | Artifact SHA | Serial reconstruction median (ms/image) | big.LITTLE pipeline total wall / 300 (ms/image) | Pipeline run median (ms) | Throughput uplift |
|---|---|---|---:|---:|---:|---:|
| `Handwritten mean4 v7 line` | `big_little_compare_20260406_191650` | `bf255cd4...edecb` | `345.609` | `249.393` | `240.885` | `38.706%` |
| `Trusted Current` | `big_little_compare_20260406_192859` | `6f236b07...6dc1` | `347.341` | `257.388` | `248.851` | `34.569%` |
| `ACL integration line` | `big_little_compare_20260406_193231` | `602371c2...edba` | `352.158` | `262.922` | `250.790` | `33.814%` |

这轮给出的最重要信息是：

- 这次已经不是“`v7` 只对历史 handwritten final 更好”，而是同日同板态下直接打赢另外两条项目级 comparison line。
- `mean4 v7` handwritten line 在 same-day compare 下同时拿到三项最优：最低 serial reconstruction、最低 pipeline endpoint、最高 uplift ratio。
- 相对 trusted current，`v7` 领先 `-1.732 ms/image` serial、`-7.995 ms/image` pipeline、`+4.137` 个百分点 uplift。
- 相对 ACL line，`v7` 领先 `-6.549 ms/image` serial、`-13.530 ms/image` pipeline、`+4.892` 个百分点 uplift。

对应工件：

- `session_bootstrap/reports/daily_20260404_openamp_3core_big_little_followup/big_little_compare_20260406_191650.md`
- `session_bootstrap/reports/daily_20260404_openamp_3core_big_little_followup/big_little_compare_20260406_192859.md`
- `session_bootstrap/reports/daily_20260404_openamp_3core_big_little_followup/big_little_compare_20260406_193231.md`
- `session_bootstrap/reports/handwritten_mean4_v7_vs_trusted_current_acl_big_little_compare_20260406_1935.md`
