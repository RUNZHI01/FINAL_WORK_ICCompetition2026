# 当前正式发布基线 + 历史优化谱系总览（2026-04-03）

## 目的

把任务板里“固化当前正式发布基线 + 历史优化谱系”这项，真正落成一个可直接引用的单页入口：

- 当前**默认 trusted artifact** 是什么
- 当前**正式 env / benchmark / guard 规则**是什么
- 历史几次关键版本跃迁分别带来了什么变化
- 哪些历史结果现在仍保留，但只应视为谱系证据而非默认 headline

---

## 1. 当前正式发布基线（default release baseline）

### 1.1 当前默认 trusted artifact

- trusted current SHA：`6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`
- 当前默认本地产物入口：
  - `session_bootstrap/tmp/phytium_baseline_seeded_warm_start_current_incremental_chunk4_20260313_131545/optimized_model.so`

### 1.2 当前默认正式口径

- payload 正式口径：`1846.9 -> 130.219 ms`
- 真实端到端正式口径：`1850.0 -> 230.339 ms/image`
- 这两条口径是当前对外默认引用的正式 benchmark

### 1.3 当前默认 env / guard 规则

- 推荐 current-safe env：
  - `session_bootstrap/config/inference_tvm310_safe.2026-03-10.phytium_pi.env`
- 必须维护：
  - `INFERENCE_CURRENT_EXPECTED_SHA256=6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`
- 规则：
  - 只要远端 `.so` 变了，就必须同步 expected SHA
  - 没有 SHA guard 的 current-safe benchmark，不算最终可信结论

### 1.4 当前默认正式报告入口

- payload：
  - `session_bootstrap/reports/inference_compare_currentsafe_chunk4_refresh_20260313_1758.md`
- real reconstruction：
  - `session_bootstrap/reports/inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md`
- 正式基线口径：
  - `session_bootstrap/runbooks/赛题对齐正式基线口径_2026-03-13.md`

---

## 2. 历史优化谱系（lineage）

### Phase A：current-safe 执行链真正打通

关键阶段：2026-03-10 ~ 2026-03-11

这一步解决的不是“更快多少”，而是：

- safe runtime 是否真正可用
- target 是否收敛
- current-safe rebuild / warm-start incremental 是否能在飞腾派上跑通
- SHA guard 是否能把 artifact 身份校验纳入正式流程

代表性里程碑：

- `d8e801...`：current-safe guard 首次真机验证成功
- `1946b08e...c644`：第一代真正显著突破 baseline 的 incremental current

### Phase B：trusted current 第一轮正式升级

关键阶段：2026-03-13 00:00 左右

- trusted current 切到：`65747fb3...b6377`
- payload 正式结果推进到：`131.343 ms`
- 真实端到端推进到：`234.219 ms/image`

这一步的意义是：

- 不再只是“跑通 current-safe”
- 而是进入“新一代 trusted current 可正式替换旧 trusted current”的阶段

### Phase C：chunk4 fresh current 成为当前正式默认基线

关键阶段：2026-03-13 18:00 左右

- trusted current 最终切到：`6f236b07...6dc1`
- payload 正式结果推进到：`130.219 ms`
- 真实端到端推进到：`230.339 ms/image`

这一步之后，当前仓库的正式对外默认基线正式收敛到：

- SHA：`6f236b07...6dc1`
- payload：`130.219 ms`
- real reconstruction：`230.339 ms/image`

---

## 3. 历史结果现在怎么用

### 仍应保留的历史结果

- `1946b08e...c644` 对应的首次突破阶段
- `65747fb3...b6377` 对应的第一轮 trusted current 升级阶段
- 更早 `249x249 / 256x256` output-shape caveat 调查
- degraded-board 与 healthy-board 的 big.LITTLE 结果差异
- failure -> fix -> pass 的故障修复链

### 但不应再作为默认主口径使用的历史结果

- 旧 SHA 对应的旧 payload / reconstruction headline
- degraded-board apples-to-apples compare 数字
- 旧 artifact lineage 的阶段性 benchmark
- 未带 SHA guard 的 current-safe 结果

也就是说：

> 历史结果继续保留，但角色是“版本演进证据”，不是“今天默认 headline”。

---

## 4. 一页版本演进链

| 代际 | trusted SHA | payload 代表值 | real reconstruction 代表值 | 当前角色 |
|---|---|---:|---:|---|
| 第一代显著突破 | `1946b08e...c644` | `153.778 ms` | `255.931 ms/image` | 历史突破节点 |
| 第一代 trusted current 升级 | `65747fb3...b6377` | `131.343 ms` | `234.219 ms/image` | 历史 trusted 版本 |
| 当前正式默认基线 | `6f236b07...6dc1` | `130.219 ms` | `230.339 ms/image` | 当前对外默认口径 |

---

## 5. 对外怎么讲这条谱系

推荐说法：

> 当前正式发布基线已经固定到 trusted current SHA `6f236b07...6dc1`，默认对外只引用 payload `130.219 ms` 与 real reconstruction `230.339 ms/image`。更早的 `1946...` 与 `65747...` 等版本不删除，但只保留为工程演进证据：它们说明 current-safe 路线是如何从“首次突破 baseline”逐步收敛成今天这条正式 trusted baseline 的。

---

## 6. 关联入口

- `session_bootstrap/PROGRESS_LOG.md`
- `session_bootstrap/runbooks/artifact_registry.md`
- `session_bootstrap/runbooks/赛题对齐正式基线口径_2026-03-13.md`
- `session_bootstrap/reports/inference_compare_currentsafe_chunk4_refresh_20260313_1758.md`
- `session_bootstrap/reports/inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md`
- `session_bootstrap/reports/project_dual_layer_narrative_and_wording_system_2026-04-03.md`
