# PyTorch Default Reference Source Note（2026-03-19）

## 当前固定口径

- PyTorch default reference: `484.183 ms/image`

## 当前状态

本仓库在 `2026-03-19` 这次冲奖救援文档整理时，**没有检索到可直接引用该数值的本地原始 benchmark 报告路径**。  
因此，本 note 的作用只有两个：

1. 先把 `484.183 ms/image` 固定为当前已验证救援事实，供 `award_rescue_execution_checklist_20260319.md`、`defense_deck_outline_20260319.md`、`project_reframing_for_feiteng_cup_20260319.md` 在本轮文档收口中统一引用；
2. 明确提醒：**在正式对外导出 PPT / PDF 前，必须把这条 PyTorch default benchmark 的原始报告或原始导出记录补归档到 `session_bootstrap/reports/`，然后用真实路径替换本 note 作为主引用。**

## 允许怎么用

- 可以把它作为当前 rescue pack 的占位事实说明；
- 可以在 speaker note 中说明“原始报告归档补齐中”；
- 可以在内部排练中使用该数值做 story framing。

## 不允许怎么用

- 不要把本 note 当成最终原始 benchmark 证据；
- 不要在外部提交版里只保留本 note 而不补原始来源；
- 不要把 `484.183 ms/image` 与 `231.522 / 134.617` 混写成同一种 operating mode，而不标 mode 与来源。

## 下一步动作

- 从当前已验证的 PyTorch default benchmark 记录中补回原始报告；
- 将原始报告路径写入本 note，或直接让 deck 改为引用原始报告；
- 完成后，本 note 可以保留为索引页，也可以降级为补充说明页。
