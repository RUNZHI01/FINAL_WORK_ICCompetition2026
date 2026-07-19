# 现场启动配置与文档统一设计

## 目标

让 Windows 推荐入口的实际行为、现场 runbook 和交接文档保持一致，同时消除密码默认值和启动参数优先级隐患。

本轮只处理此前审查项 1、2、3、4、6。演示图像和 latent 的仓库外/忽略目录问题暂缓，不改变资产发现与打包方式。

## 已确认口径

- `Semantic-Communication/cockpit_desktop/start-demo.ps1` 是 Windows 现场推荐入口。
- `start-demo.ps1` 与底层 `start-dev.sh` 默认使用 USRP QPSK。
- `docker/run-demo-tailscale.*` 是兼容入口，继续默认使用 `iq-direct`。
- 默认板卡地址保留为 `100.121.87.73`，默认用户名保留为 `user`，默认 SSH 端口保留为 `22`。
- 不再在脚本中提供默认密码。
- Electron 界面仍在板卡会话、安全服务、常驻 USRP TX/RX 和控制面探活完成后显示。
- Cockpit 内的板卡密码输入框继续用于换板、重认证或会话更新，不改变为 UI-first 启动。

## 启动参数解析

地址、用户名和端口使用以下优先级：

1. 显式 PowerShell 参数 `-BoardHost`、`-BoardUser`、`-BoardPort`；
2. 对应的进程环境变量；
3. 脚本内的公开演示默认值。

密码使用以下优先级：

1. 显式 `-BoardPassword`；
2. `REMOTE_PASS`、`REMOTE_PASSWORD`、`PHYTIUM_PI_PASS`、`PHYTIUM_PI_PASSWORD`、`BOARD_PASS` 中第一个非空值；
3. `Read-Host -AsSecureString` 交互输入。

解析完成后，脚本必须把同一组 host/user/port/password 写入当前进程使用的 `REMOTE_*` 和 `PHYTIUM_PI_*` 环境变量。板端网口恢复和后续 `start-dev.sh` 必须消费同一组值，不能因旧环境变量产生“恢复一块板、后端连接另一块板”的分裂状态。

密码不得写入仓库、日志或命令输出。默认 IP 和用户名是本次演示环境的明确约定，允许保留并在文档中标明可覆盖。

## 代码边界

把纯配置解析放入 `Semantic-Communication/cockpit_desktop/start-demo-config.ps1`：

- 输入 PowerShell 参数是否显式绑定、参数值和当前进程环境变量；
- 输出最终 host/user/port 与候选密码；
- 不启动 Docker、SSH、USRP 或 Electron；
- 不读取交互输入。

`start-demo.ps1` 负责：

- 调用配置解析；
- 候选密码为空时安全提示；
- 统一写入子进程环境；
- 恢复板端 USRP 网口；
- 调用 Git Bash 执行 `start-dev.sh`。

这个拆分使参数优先级可用普通 PowerShell 断言测试，不需要连接硬件。

## 测试

新增无硬件 PowerShell 测试，至少覆盖：

- 显式参数覆盖旧环境变量；
- 环境变量覆盖公开的 host/user/port 默认值；
- 显式密码覆盖环境变量密码；
- 未显式提供密码时读取环境变量候选；
- 没有任何密码来源时返回空候选，由入口脚本进入安全提示；
- 推荐入口和 `start-dev.sh` 的默认链路均为 `qpsk`；
- 兼容 `run-demo-tailscale.*` 的默认链路仍为 `iq-direct`。

保留并运行现有 `test_start_dev_startup_readiness.sh`，确认服务 readiness 仍发生在前端启动之前。

## 文档修改

- `docs/README.md`：明确推荐入口默认 QPSK，IQ-direct 是可切换路径；修正从 cockpit 子目录调用旧 Docker 入口的错误相对路径。
- `docs/HANDOFF.md`：更新日期和主线表述，参数表分别说明推荐入口与兼容入口。
- `docs/runbooks/STARTUP.md`：保留当前 QPSK 口径，补充密码来源与终端提示。
- `docs/USRP_IQ_RUNTIME.md`、`docs/USRP_LINK_BRIEFING.md`：把“默认链路”改成“IQ-direct 路径说明”，避免与现场 QPSK 默认冲突。
- `docker/README.md`：明确这里只描述兼容容器入口的 IQ-direct 默认值；将质量门限统一为脚本当前的 `sync_metric >= 0.75` 和 `pilot_gain_min_over_initial >= 0.85`；拆分超长参数段。

文档不再复制多份完整参数长串。现场最短步骤放在 runbook，参数真值集中到 HANDOFF，其他文档只说明入口差异并链接过去。

## 不在本轮范围

- 不移动、追踪或重新打包演示图像与 latent。
- 不改为 Electron 先显示、保存密码后再启动真机服务。
- 不改变 QPSK/IQ 传输实现、射频参数、质量门限或性能指标。
- 不改变板端账号、Tailscale 地址或 USRP 网口拓扑。
