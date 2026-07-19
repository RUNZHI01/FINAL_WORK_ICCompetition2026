# GitHub 发布检查清单

更新时间：`2026-03-25`

本清单针对当前仓库的真实情况编写：它不是一个“纯源码仓库”，而是混合了源码、脚本、论文材料、实验报告、答辩证据、运行日志和本地运行产物。发布前不要直接 `git push`，先按下面的检查表分层处理。

## 1. 发布前先做的三件事

- [ ] 明确这次 GitHub 仓库的公开定位
  建议在三种定位里先选一个，否则很容易把内容混着发：
  - `源码 + 精选证据`
  - `源码 + 全部历史报告`
  - `只发源码，不发大部分运行/演示产物`

- [ ] 明确哪些内容要保留为公开证据，哪些只在本地保留
  当前仓库里很多 `reports/` 文件 technically 是生成物，但已经被当作正式证明材料使用。

- [ ] 在真正推送前，至少跑一次：

```bash
git status --short
git diff --stat
```

## 2. 按类别检查内容

### 2.1 建议保留的核心源码/文档

- [ ] 顶层文档
  - `README.md`
  - `EXPERT_HANDOFF.md`
  - `GITHUB_PUBLISH_CHECKLIST.md`

- [ ] 核心工程代码
  - `session_bootstrap/scripts/`
  - `session_bootstrap/demo/openamp_control_plane_demo/`
  - `openamp_mock/`
  - `cockpit_native/`

- [ ] 核心索引文档
  - `session_bootstrap/README.md`
  - `session_bootstrap/runbooks/artifact_registry.md`
  - `session_bootstrap/PROGRESS_LOG.md`

- [ ] 公开叙事材料
  - `paper/` 下准备公开的文档
  - `session_bootstrap/runbooks/` 下准备公开的 runbook

### 2.2 必须逐项审查的敏感或易泄露内容

- [ ] `session_bootstrap/config/*.env`
  检查是否包含：
  - 真实主机/IP
  - 用户名
  - 端口
  - 远端路径
  - 凭据

- [ ] `session_bootstrap/config/phytium_pi_login.example.env`
  当前样例里直接给了默认 host/user。发布前应决定是否改成占位值。

- [ ] `README.md`、`session_bootstrap/README.md`、`session_bootstrap/demo/openamp_control_plane_demo/README.md`
  检查是否公开了不应公开的主机地址、内部路径、账号名。

- [ ] `session_bootstrap/reports/`
  很多报告可能包含：
  - 真实板侧路径
  - 真实 SSH 地址
  - 运行截图或日志片段
  - 提交哈希、内部时间线、人员操作痕迹

- [ ] `cockpit_native/runtime/`
  检查是否包含本地截图、打包产物、运行日志，是否真的要公开。

- [ ] `cicc_tech_doc/`
  检查是否只保留源 `.tex/.bib/.cls`，还是误把 LaTeX 中间件和 PDF 都带上了。

### 2.3 一般应视为生成物/本地产物的目录

这些内容通常应该忽略、移出版本控制，或至少在首次发布前重新决策：

- [ ] `.codex_tmp/`
- [ ] `session_bootstrap/tmp/`
- [ ] `session_bootstrap/logs/`
- [ ] `session_bootstrap/demo/openamp_control_plane_demo/runtime/`
- [ ] `cockpit_native/runtime/`
- [ ] `__pycache__/`
- [ ] `cockpit_native/.venv/`
- [ ] `cicc_tech_doc/*.aux`
- [ ] `cicc_tech_doc/*.log`
- [ ] `cicc_tech_doc/*.fdb_latexmk`
- [ ] `cicc_tech_doc/*.fls`
- [ ] `cicc_tech_doc/*.out`
- [ ] `cicc_tech_doc/*.run.xml`
- [ ] `cicc_tech_doc/*.toc`
- [ ] `cicc_tech_doc/*.xdv`
- [ ] `cicc_tech_doc/*.bcf`
- [ ] `cicc_tech_doc/*.blg`

### 2.4 不要一刀切删除的“证据型生成物”

以下内容虽是实验产物，但当前仓库已经把它们当成正式证据资产，发布前应筛选，不要盲删：

- [ ] `session_bootstrap/reports/inference_*`
- [ ] `session_bootstrap/reports/big_little_*`
- [ ] `session_bootstrap/reports/openamp_*`
- [ ] `session_bootstrap/reports/*fit*`
- [ ] `session_bootstrap/reports/*delivery*`
- [ ] `session_bootstrap/reports/*readiness*`

建议做法：

- 如果仓库定位是“源码 + 精选证据”，则只保留索引页和最核心的正式结论页
- 如果仓库定位是“源码 + 全部历史报告”，则要在 README 中明确说明 `reports/` 内含历史过程、不同阶段口径和运行痕迹

## 3. 发布前的内容一致性检查

- [ ] README、handoff、runbook 是否引用同一代 headline
  当前已知风险：
  - 顶层 README 默认 headline 已指向 `2026-03-13` 的 trusted current
  - `cockpit_native` 讲稿/packet index 仍引用 `2026-03-11` 的 `1844.1 -> 153.778 ms`

- [ ] 是否明确区分以下几类数据
  - payload benchmark
  - real reconstruction benchmark
  - big.LITTLE healthy-board compare
  - degraded-board drift evidence

- [ ] 是否明确说明 OpenAMP live baseline 的历史快照与默认 operator branch 不完全相同

- [ ] 是否在公开文档里解释 `openamp_mock` 不是板侧真固件源码

## 4. 推荐的本地清理动作

如果你准备做“较干净的首次公开版本”，建议先手工确认并处理以下内容：

- [ ] 删除或移出仅本机有效的 runtime 截图、deliverable 包、临时日志
- [ ] 删除或移出 LaTeX 中间件，只保留源文件和必要 PDF
- [ ] 审查所有 `.env` 快照是否要公开
- [ ] 决定是否保留整个 `session_bootstrap/reports/`，或只保留精选结论
- [ ] 决定是否保留 `TVM_LAST_understanding/` 这类个人理解笔记
- [ ] 决定是否保留 `.codex_tmp/` 及 agent/自动化相关痕迹

## 5. 检查远端和分支状态

先确认当前状态：

```bash
git branch --show-current
git remote -v
git status --short
```

如果已有 `origin`，先确认它是不是目标仓库。
如果不是，先改 URL，不要直接推。

## 6. 创建 GitHub 远端并推送

不要假设 GitHub 认证已经配置好。推荐两种方式：

### 6.1 方式 A：先在网页创建仓库，再本地添加 remote

1. 在 GitHub 网页创建空仓库，不勾选自动生成 README。
2. 本地执行：

HTTPS：

```bash
git remote add origin https://github.com/<owner>/<repo>.git
git push -u origin <branch>
```

SSH：

```bash
git remote add origin git@github.com:<owner>/<repo>.git
git push -u origin <branch>
```

如果本地已经有 `origin`：

```bash
git remote set-url origin https://github.com/<owner>/<repo>.git
# 或
git remote set-url origin git@github.com:<owner>/<repo>.git
```

### 6.2 方式 B：如果本机已配置 `gh`

只有当你确认 `gh auth status` 正常时再用：

```bash
gh repo create <owner>/<repo> --private --source . --remote origin --push
```

或公开仓库：

```bash
gh repo create <owner>/<repo> --public --source . --remote origin --push
```

如果 `gh` 未认证，不要在这里卡住，直接退回方式 A。

## 7. 首次发布建议

### 7.1 建议的第一次公开版本内容

- [ ] 一个简洁 README
- [ ] 一个专家接手文档
- [ ] 一个发布检查清单
- [ ] 核心源码目录
- [ ] 精选证据索引，而不是所有运行产物

### 7.2 建议的首个 tag / release 做法

先确认：

- [ ] 工作树干净到你能解释每个改动
- [ ] 文档口径统一
- [ ] 敏感信息已处理

然后：

```bash
git tag -a v0.1.0 -m "Initial public handoff release"
git push origin v0.1.0
```

Release 页面建议附上：

- 项目一句话定位
- 仓库结构说明
- `EXPERT_HANDOFF.md` 链接
- 关键验证结果的来源文档
- 对外诚实边界说明

## 8. 发布前最后一轮命令

建议在准备 push 之前手工跑一遍：

```bash
git status --short
git diff --stat
git remote -v
git branch --show-current
```

如果你决定做“精选证据公开版”，还建议额外检查：

```bash
git ls-files | rg '^(session_bootstrap/reports/|session_bootstrap/config/|cockpit_native/runtime/|session_bootstrap/tmp/|session_bootstrap/logs/|cicc_tech_doc/)'
```

目标不是把输出清零，而是确保每一类被公开的内容，你都能解释为什么保留。
