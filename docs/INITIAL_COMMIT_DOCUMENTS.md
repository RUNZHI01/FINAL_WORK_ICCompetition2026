# 最初提交文档清单

最初提交为 `d787901`（2026-05-06，`chore: prepare reproducible competition submission`）。为避免旧口径重新混入当前说明，原文档按原相对路径恢复到 [`archive/initial_commit/`](./archive/initial_commit/)，不覆盖当前文件。

## 数量

- 原始文档共 `937` 份：Markdown `803`、TXT `133`、PDF `1`。
- 文件总大小 `7,098,611` bytes，约 `6.77 MiB`。
- 当前树中仍保留原路径的有 `48` 份；其余 `889` 份已在归档目录恢复。
- 已逐文件核对路径、大小和 Git blob 哈希，`937/937` 与 `d787901` 一致。
- 完整逐文件清单见 [`MANIFEST.tsv`](./archive/initial_commit/MANIFEST.tsv)，包含原路径、大小、分类和当前路径状态。

## 分类清单

| 类别 | 文件数 | 主要内容 |
|---|---:|---|
| 历史实验与验收证据 | 757 | session bootstrap 的运行报告、验收记录和阶段证据 |
| 第三方 liboqs 文档 | 72 | liboqs 自带 README、算法说明和测试资料 |
| 项目与模块说明 | 34 | 根目录及 USRP、ML-KEM、Docker、latent 模块说明 |
| 运行手册 | 32 | 环境恢复、演示、板端和容器操作手册 |
| Cockpit 设计与审计记录 | 15 | 早期界面设计、审计与交付记录 |
| 其他文本资料 | 14 | 配置说明、依赖清单和辅助文本 |
| OpenAMP 补丁说明 | 6 | 固件补丁、协议和部署说明 |
| TVM 交接资料 | 4 | TVM 优化路径和历史理解记录 |
| 技术设计 | 3 | 系统架构与赛题对齐设计 |

## 重点入口

- 根目录：`README.md`、`AGENTS.md`。
- 模块说明：`USRP292x/`、`mlkem_link/`、`host_pic_to_latent/`、`docker/` 下的 README。
- 安全与控制：`Semantic-Communication/session_bootstrap/` 下的 README、runbooks、技术设计和历史报告。
- Cockpit：`Semantic-Communication/cockpit_desktop/` 下的 README 与设计记录。
- TVM：根目录历史 `TVM_LAST_*` 交接文件。

归档文件只用于追溯最初提交，不代表当前实现。加密和 USRP 的现行口径以 [`PPT_USRP_SECURITY_UPDATES.md`](./PPT_USRP_SECURITY_UPDATES.md)、[`DOCUMENT_USRP_SECURITY_UPDATES.md`](./DOCUMENT_USRP_SECURITY_UPDATES.md) 和 [`USRP_LINK_BRIEFING.md`](./USRP_LINK_BRIEFING.md) 为准。
