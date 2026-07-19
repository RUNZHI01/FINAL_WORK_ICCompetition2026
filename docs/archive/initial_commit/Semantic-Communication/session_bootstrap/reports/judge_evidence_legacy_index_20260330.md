# Judge Evidence Legacy Index（2026-03-30）

用途：明确哪些 `judge_*` 产物属于**历史中间版本**，保留是为了追溯，但**不应再作为默认引用入口**。

## 当前唯一默认入口

如果当前只开一个 judge-facing 文件，默认开：

- `session_bootstrap/reports/judge_evidence_pack_20260330_current_chunk4_lpips_full.md`

与之配套的 latest 入口：

- `session_bootstrap/reports/judge_quality_formal_report_20260330_lpips_full.md`
- `session_bootstrap/reports/judge_snr_robustness_20260330_current_chunk4.md`
- `session_bootstrap/reports/defense_quick_reference_card_20260330_current_chunk4.md`

## 历史中间版本（保留，但不要默认引用）

### 第一代本地整理包（旧）

这些文件反映的是最早一轮本地整理状态，仍带有旧口径或不完整 SNR / LPIPS 信息：

- `session_bootstrap/reports/judge_evidence_pack_20260330.md`
- `session_bootstrap/reports/judge_evidence_pack_20260330.json`
- `session_bootstrap/reports/judge_quality_formal_report_20260330.md`
- `session_bootstrap/reports/judge_quality_formal_report_20260330.json`
- `session_bootstrap/reports/judge_snr_robustness_20260330.md`
- `session_bootstrap/reports/judge_snr_robustness_20260330.json`
- `session_bootstrap/reports/judge_snr_robustness_20260330_latency.svg`

不再默认引用原因：
- 仍是早期 quality / SNR 版本
- 没有 latest chunk4 资源画像
- 没有 full LPIPS
- 仍保留旧的 latency-only / partial 叙述

### current_chunk4 过渡版（旧）

这些文件已经切到 current chunk4，但仍停留在 LPIPS partial 或 profiling 过渡态：

- `session_bootstrap/reports/judge_evidence_pack_20260330_current_chunk4.md`
- `session_bootstrap/reports/judge_evidence_pack_20260330_current_chunk4.json`
- `session_bootstrap/reports/judge_evidence_pack_20260330_current_chunk4_lpips_partial.md`
- `session_bootstrap/reports/judge_evidence_pack_20260330_current_chunk4_lpips_partial.json`
- `session_bootstrap/reports/judge_evidence_pack_20260330_current_chunk4_lpips_profiled.md`
- `session_bootstrap/reports/judge_evidence_pack_20260330_current_chunk4_lpips_profiled.json`
- `session_bootstrap/reports/judge_quality_formal_report_20260330_lpips_partial.md`
- `session_bootstrap/reports/judge_quality_formal_report_20260330_lpips_partial.json`

不再默认引用原因：
- `lpips_partial` 阶段尚未补齐三组 LPIPS
- `lpips_profiled` 阶段还没升级到 full LPIPS 质量矩阵
- 这些文件保留是为了追溯“补证是怎么逐步补齐的”

## 如何处理这些 legacy 文件

- **不要删除**：它们是可追溯历史
- **不要在 README / workflow / deck 里继续引用**
- **答辩 / 写稿默认只引用 latest full**

## 一句话规则

> 同名 judge 产物如果同时存在 `base / current_chunk4 / lpips_partial / lpips_profiled / lpips_full` 多个版本，默认只认 `lpips_full`。
