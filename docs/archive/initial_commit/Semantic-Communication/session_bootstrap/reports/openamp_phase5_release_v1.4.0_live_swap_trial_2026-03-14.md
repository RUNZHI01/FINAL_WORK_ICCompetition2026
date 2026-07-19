# Phase 5 `release_v1.4.0` 候选 live swap 试车记录

> 日期：2026-03-14  
> 目标：在真实飞腾板上，把当前官方 `/lib/firmware/openamp_core0.elf` 暂时替换为 `release_v1.4.0` 候选固件，验证 `remoteproc0` / RPMsg bring-up 是否仍能成立；随后无论结果如何都恢复到原官方固件。  
> 边界：本轮是一次**受控试车**，不是长期切换。

## 1. 试车前基线

板上当前官方固件：

- 路径：`/lib/firmware/openamp_core0.elf`
- 大小：`1650448`

候选固件：

- 路径：`/home/user/phytium-dev/release_v1.4.0/example/system/amp/openamp_for_linux/phytiumpi_aarch64_firefly_openamp_core0.elf`
- 大小：`1627224`

## 2. 试车步骤

本轮实际执行的是：

1. 备份当前官方固件到 `/tmp/openamp_core0.elf.backup.20260314_150850`
2. 若 `remoteproc0` 处于 `running`，先停掉
3. 把候选固件安装到 `/lib/firmware/openamp_core0.elf`
4. `echo start > /sys/class/remoteproc/remoteproc0/state`
5. 检查 `dmesg`
6. 尝试沿用板上既有 `set_env.sh` 与 `rpmsg-demo` 路径验证用户态通路
7. 无论结果如何，回滚到原官方固件

## 3. 候选固件试车结果

### 3.1 明确成功的部分

候选固件 **确实成功被 remoteproc 拉起**，而且不只是“文件被替换了”，而是出现了真实运行态证据：

```text
remoteproc remoteproc0: powering up homo_rproc
remoteproc remoteproc0: Booting fw image openamp_core0.elf, size 1627224
virtio_rpmsg_bus virtio0: rpmsg host is online
remoteproc remoteproc0: remote processor homo_rproc is now up
virtio_rpmsg_bus virtio0: creating channel rpmsg-openamp-demo-channel addr 0x0
```

这说明：

- `release_v1.4.0` 候选固件并没有在 remoteproc 启动阶段立刻崩掉
- RPMsg demo channel 仍被创建
- 至少在 **从核启动 + virtio/rpmsg bring-up** 这一层，它是能跑起来的

### 3.2 未完成 / 未确认的部分

候选固件试车时，用户态验证没有完整跑通：

- `set_env.sh` 返回 `0`，但其内部再次执行 `echo start > remoteproc0/state` 时出现：
  - `写错误: 设备或资源忙`
- `/dev/rpmsg_ctrl0` 出现了
- `/dev/rpmsg0` **没有**出现
- 第一次直接跑 `rpmsg-demo` 因权限问题失败：
  - `open rpmsg_ctrl0 failed.: Permission denied`

因此，本轮对候选固件的 live 结论应写成：

> **候选固件已证明能够把 `remoteproc0` 拉到 `running` 并创建 `rpmsg-openamp-demo-channel`；但本轮没有把用户态 `/dev/rpmsg0` 路径完整验证到位。**

也就是说：

- 它已经明显强于“可能直接起不来”的风险判断
- 但还不足以宣称“和当前官方固件一样稳，一样能完整复现板上用户态 demo 路径”

## 4. 回滚与恢复情况

### 4.1 回滚阶段遇到的问题

试车脚本在回滚时，重新 `start remoteproc0` 遇到了内核侧 `EINTR` / `Boot failed: -4`，导致板子短时间内处于：

- 官方固件文件已恢复
- 但 `remoteproc0` 留在 `offline`

这意味着：

- 回滚逻辑中的“恢复文件”成功了
- 但“在同一轮不重启的情况下把 remoteproc 重新拉稳”不够可靠

### 4.2 最终恢复方式

为确保板子回到稳定官方状态，本轮进一步执行了：

1. 确认 `/lib/firmware/openamp_core0.elf` 已恢复为官方大小 `1650448`
2. 对飞腾板执行 `sudo reboot`
3. 等待 SSH 回连
4. 重新执行官方路径验证：
   - `sudo /home/user/open-amp/set_env.sh`
   - `sudo timeout 15s /home/user/open-amp/rpmsg-demo`

最终恢复成功证据：

- `final_state=running`
- `rpmsg-demo` 重新打印大量：
  - `received message: Hello World! No:...`

因此，本轮结束时板子状态应视为：

> **已恢复到官方固件 + 官方 demo 路径可用。**

## 5. 本轮更新后的风险判断

这次真实试车把风险判断往上抬了一档：

### 先前判断

- 我对“现在就换候选固件是否能跑起来”的把握，只给到中等偏上

### 本轮后判断

现在可以更具体地说：

1. **remoteproc bring-up 成功的概率显著高于我之前的保守估计**
   - 因为它已经在真机上成功启动并创建过 channel
2. **用户态路径是否完全等价，仍未被本轮证明**
   - 本轮没有把 `/dev/rpmsg0 + rpmsg-demo` 在候选固件下完整跑通
3. **受控替换是可做的，但自动回滚脚本不应假设“无需重启就能 100% 干净恢复”**
   - 本轮实际上是靠“恢复官方固件 + 重启 + 官方路径复验”收口的

## 6. 当前最合理的工程结论

本轮 live 试车后的最合理结论是：

> **`release_v1.4.0` 候选已经不只是“离线最像”，而且在真机上证明了自己能把 `remoteproc0` 和 `rpmsg-openamp-demo-channel` 拉起来。**

但同时：

> **它还没有被证明在用户态 RPMsg demo 行为上与当前官方固件完全等价。**

所以，当前阶段最准确的口径不是：

- “它已经完全等于官方固件”

而是：

- “它已经通过了最关键的一次 live bring-up 试车，但用户态通路等价性还需要更干净的一轮验证。”

## 7. 下一步建议

基于本轮试车，最值钱的下一步不再是单纯问“敢不敢换”，而是：

1. 再做一轮**更干净的候选固件 live 用户态验证**：
   - 候选固件启动后
   - 直接用 `sudo` 运行板上已验证路径
   - 把 `/dev/rpmsg_ctrl0` / `/dev/rpmsg0` / `rpmsg-demo` 结果完整落证
2. 如果还要继续减少不确定性，仍建议补拿：
   - 真实候选的 final link map

这样就能把“候选能 bring-up”进一步推进到“候选是否已足够接近到可替代当前官方 demo 固件”。
