# OpenAMP Demo 任务完成判定矩阵（2026-04-03）

## 目的

把当前任务板里仍挂着的 Demo 类条目，统一改写成：

- **口径是否已冻结**
- **要勾完成还差什么真实验证**
- **彩排后应回填到哪里**

这样后续不会再出现“文档都写完了，但没人知道什么时候可以真的把任务勾掉”的状态。

---

## 1. 判定规则

### Rule A：docs frozen ≠ task done

如果一项只是完成了：

- 口径冻结
- 入口索引补齐
- checklist / template 就绪

但还没经过真实 presentation-day UI / 板侧彩排，**不能直接勾完成**。

### Rule B：只有真实彩排结果才允许改任务状态

如果要把任务板里的 Demo 项从 `[ ]` 改成 `[x]`，必须至少满足：

1. 已按 `openamp_demo_presentation_day_checklist_2026-04-03.md` 做逐项核对
2. 已用 `openamp_demo_rehearsal_go_nogo_template_2026-04-03.md` 回填结果
3. 结论不是纯文档推断，而是基于真实 UI / operator flow / 板侧环境

---

## 2. 当前核心 Demo 未完成项

| 任务板条目 | docs frozen? | 真正完成还差什么 | 彩排后回填入口 |
|---|---|---|---|
| 四幕 Demo 重构 | Yes | 最终演示构建中，`Act 1 -> 4` 是否能按 operator flow 稳定走完；若不走完，是否已有诚实降级路径 | `openamp_demo_rehearsal_go_nogo_template_2026-04-03.md` |
| Demo 首屏显示（飞腾派在线 / 从核在线 / SHA / target / runtime） | Yes | 最终 build 中这些字段是否稳定露出，且没有与第三幕 compare / 历史 live / mode boundary 混写 | `openamp_demo_rehearsal_go_nogo_template_2026-04-03.md` |
| Demo 对比页只展示两条正式口径 | Yes | Scene 3 实测中是否真的只出现 `1846.9 -> 130.219 ms` 与 `1850.0 -> 230.339 ms/image`，且未混入 drift / degraded-board 数字 | `openamp_demo_rehearsal_go_nogo_template_2026-04-03.md` |
| Demo 三个故障注入按钮 | Partially | 最终 demo build 中，三个 fault 入口是否存在、文案是否诚实、replay/live 边界是否清晰、是否值得上台展示 | `openamp_demo_rehearsal_go_nogo_template_2026-04-03.md` |
| 半离线降级 Demo | Yes | 在真实彩排中，是否已明确最终 chosen mode（`L0/L1/L2`），并验证降级路径足够支撑完整 defense | `openamp_demo_rehearsal_go_nogo_template_2026-04-03.md` |
| 视频脚本同步更新 | Yes | 彩排时口播是否实际遵守 frozen wording，而不是又回到旧叙事 | `openamp_demo_rehearsal_go_nogo_template_2026-04-03.md` |

---

## 3. 建议如何修改任务板状态

### 可以改成完成的条件

某项只有在满足下面两类条件后，才建议改成完成：

- **文档条件**：对应 acceptance / checklist / scope note 已存在
- **彩排条件**：真实 UI / operator flow / 板侧彩排已通过，并已回填结果

### 仍应保持未完成的条件

如果只是文档冻结，但出现以下任一情况，仍建议保持未完成：

- 还没真实彩排
- 真实彩排还没回填记录
- UI build 与文档口径仍可能漂移
- 只能猜“应该可以”，没有实测证据

---

## 4. 一句话执行方式

后续真正要勾任务板时，按这个顺序：

1. 用 `openamp_demo_presentation_day_checklist_2026-04-03.md` 做彩排
2. 用 `openamp_demo_rehearsal_go_nogo_template_2026-04-03.md` 回填结果
3. 再按这份矩阵决定哪些项能勾完成

---

## 5. 关联文档

- `session_bootstrap/reports/openamp_demo_presentation_day_checklist_2026-04-03.md`
- `session_bootstrap/reports/openamp_demo_rehearsal_go_nogo_template_2026-04-03.md`
- `session_bootstrap/reports/openamp_demo_open_items_split_2026-04-03.md`
- `session_bootstrap/reports/openamp_demo_docs_closure_summary_2026-04-03.md`
