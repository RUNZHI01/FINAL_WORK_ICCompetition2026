# Demo Startup

1. 上电板卡，等 2 分钟。确认 Docker Desktop 已启动。
2. 在仓库根目录打开 PowerShell：

```powershell
cd E:\Main\Career\集创赛\FINAL_WORK_ICCompetition2026\FINAL_WORK_ICCompetition2026
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
.\Semantic-Communication\cockpit_desktop\start-demo.ps1 -BoardHost 100.121.87.73 -BoardUser user -BoardPassword user
```

默认会启用 USRP IQ 直传、ML-KEM+SM4、ML-DSA+SM2，并在显示界面前静默预热 5 张。

5. 界面出现后检查：

- 输入来源：`USRP-IQ直传`
- 安全信道：加密和认证已启用
- 板卡密码：板卡就绪
- 右侧硬件遥测在更新

6. 演示测试：

```text
点击 TVM 300 张批量测试
确认进入有效重建链路，传输/解包和推理侧总计有数值。
```

7. 图片对比目录：

- 发送原图（上位机）：`E:\Main\Career\集创赛\jscc-test\smallTest`
- 预录 latent 输入（板端）：`/home/user/Downloads/jscc-test/简化版latent`
- USRP IQ 接收解包（板端）：`/home/user/cockpit_usrp_rx/cockpit_usrp_*_rx`
- 预录 TVM 重建（板端）：`/home/user/Downloads/jscc-test/jscc/infer_outputs/openamp3_handwritten_mean4_v7_big_little_current/reconstructions`
- USRP TVM 重建（板端）：`/home/user/Downloads/jscc-test-usrp/tvm/openamp3_usrp_*_current/reconstructions`
- 本地抽查结果（上位机）：`Semantic-Communication\session_bootstrap\reports\reconstruction_error_audit_tvm_current_300_20260714_153238`

现场展示时优先打开“发送原图”和当前 run 的 `reconstructions` 目录；最新 run 的准确输出目录以 Cockpit 报告里的 `output_dir` 为准。

若出现 `board status endpoint unavailable`，先重新保存板卡密码或重启 Cockpit；不要切到 WSL。
