# Demo Startup

日常启动只执行下面 1-7 步。仅首次部署或 IQ 源码更新后执行一次同步：

```powershell
pwsh -File .\docker\prepare-iq-board-sync.ps1 -Deploy -Verify -BoardHost 100.121.87.73 -BoardUser user
```

1. 上电板卡，等 2 分钟。确认 Docker Desktop 已启动。
2. 在仓库根目录打开 PowerShell：

```powershell
cd E:\Main\Career\集创赛\FINAL_WORK_ICCompetition2026
```

3. 检查 USRP 网口：

```powershell
.\USRP292x\ConfigureUsrp2922DemoNetwork.ps1 -Target Status
```

如果 `192.168.10.2` 不通，用管理员 PowerShell 配上位机网口：

```powershell
.\USRP292x\ConfigureUsrp2922DemoNetwork.ps1 -Target UpperHost -InterfaceAlias "以太网"
```

板端/RX 网口正常由 `usrp2922-board-autostart.service` 开机自恢复，当前固定使用 `eth0`。如果断电后仍不通，先跑快速兜底：

```powershell
.\USRP292x\ConfigureUsrp2922DemoNetwork.ps1 -Target Board -BoardHost 100.121.87.73 -Fast
```

仍不通时再去掉 `-Fast` 做完整恢复和 UHD 探测。

4. 拉起 Cockpit Desktop：

```powershell
.\Semantic-Communication\cockpit_desktop\start-demo.ps1 -BoardHost 100.121.87.73 -BoardUser user
```

脚本没有默认密码。可传 `-BoardPassword` 或预先设置 `REMOTE_PASS`；两者都没有时，PowerShell 会安全询问一次。默认启用 USRP QPSK、ML-KEM+SM4 和 ML-DSA+SM2。界面显示前，脚本会建立板卡会话，拉起安全服务和常驻 USRP TX/RX，再检查状态端点与控制端口；启动阶段不发送图片，也不创建隐藏重建任务。Windows 下 TX 容器使用 bridge 并发布 `127.0.0.1:29221`；原生 Linux 使用 host network。无需手工启动 TX 容器或控制代理。

5. 界面出现后检查：

- 输入来源：`USRP-QPSK`
- 安全信道：加密和认证已启用
- 板卡密码：板卡就绪
- 右侧硬件遥测在更新

6. 演示测试：

```text
点击 TVM 300 张批量测试
确认进入有效重建链路，传输/解包和推理侧总计有数值。
```

7. 图片对比目录：

- 发送原图（上位机，展示 Top 300）：`E:\Main\Career\集创赛\原始图像`
- Top 300 latent 缓存（上位机）：`host_pic_to_latent/encoder_outputs_top300`
- 完整原始图像回退目录：`E:\Main\Career\集创赛\原始图像_备份_20260718_213714`
- 预录 latent 输入（板端）：`/home/user/Downloads/jscc-test/简化版latent`
- USRP IQ 接收解包（板端）：`/home/user/cockpit_usrp_rx/cockpit_usrp_*_rx`
- 预录 TVM 重建（板端）：`/home/user/Downloads/jscc-test/jscc/infer_outputs/openamp3_handwritten_mean4_v7_big_little_current/reconstructions`
- USRP IQ TVM 重建（板端）：`/home/user/Downloads/jscc-test-usrp/iq-direct/tvm/openamp3_usrp_*_current/reconstructions`
- USRP QPSK TVM 重建（板端）：`/home/user/Downloads/jscc-test-usrp/qpsk/tvm/openamp3_usrp_*_current/reconstructions`
- 本地抽查结果（上位机）：`Semantic-Communication\session_bootstrap\reports\reconstruction_error_audit_tvm_current_300_20260714_153238`

现场首选：在 Cockpit 的“板端输出目录”下点击“本次重建对比图”。浏览器会打开 `http://127.0.0.1:8786/`；选择倒序排列的 job，再点击“拉取”查看当前序号。需要筛查异常图时再打开质量辅助。该页面只在上位机运行，板端不部署 Web 服务。

Cockpit 不可用时，使用离线兜底脚本拉取最新板端 USRP TVM 图片：

```powershell
.\scripts\pull_board_images.ps1
```

默认输出到 `artifacts\board_images\<timestamp>_usrp-tvm_...\index.html`。若要拉指定板端目录：

```powershell
.\scripts\pull_board_images.ps1 -RemotePath "/home/user/Downloads/jscc-test-usrp/iq-direct/tvm/openamp3_usrp_xxx_current/reconstructions"
```

若需要临时本地 Web 访问，加 `-Serve`：

```powershell
.\scripts\pull_board_images.ps1 -Serve -Port 8765
```

若出现 `board status endpoint unavailable`，先重新保存板卡密码或重启 Cockpit；不要切到 WSL。

USRP 分阶段说明和汇报口径见 [`../USRP_LINK_BRIEFING.md`](../USRP_LINK_BRIEFING.md)。
