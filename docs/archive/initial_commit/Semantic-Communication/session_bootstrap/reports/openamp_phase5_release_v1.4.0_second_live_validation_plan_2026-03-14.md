# Phase 5 `release_v1.4.0` 第二轮 live 验证执行计划

> 日期：2026-03-14  
> 目标：在当前已恢复到官方健康状态的飞腾板上，做一轮比首轮更干净的 `release_v1.4.0` 候选 live 验证，重点回答“候选是否不仅能 bring-up，还能在板载官方用户态路径下复现 `/dev/rpmsg0` + `rpmsg-demo` echo”。  
> 本报告只定义下一轮人工执行步骤，不在本轮 Codex 任务里触板。  
> 依据：
> - `session_bootstrap/reports/openamp_phase5_release_v1.4.0_live_swap_trial_2026-03-14.md`
> - `session_bootstrap/reports/openamp_phase4_runtime_channel_success_2026-03-14.md`
> - `session_bootstrap/runbooks/openamp_status_req_resp_runbook_2026-03-14.md`
> - `session_bootstrap/runbooks/phytium_openamp_for_linux_status_req_resp_patch_runbook_2026-03-14.md`

## 1. 本轮相对首轮的收敛点

首轮已经证明两件事：

1. 候选固件可被 `remoteproc0` 拉起。
2. dmesg 可见 `Booting fw image openamp_core0.elf, size 1627224` 与 `creating channel rpmsg-openamp-demo-channel`。

首轮的主要 confounder 也已经明确：

1. 先手工 `echo start > /sys/class/remoteproc/remoteproc0/state`，再跑 `set_env.sh`，导致 `set_env.sh` 内部重复 `start`，出现 `设备或资源忙`。
2. `rpmsg-demo` 首次不是用 `sudo` 跑，出现 `open rpmsg_ctrl0 failed.: Permission denied`。
3. 回滚阶段同一轮内再次 `start remoteproc0` 命中 `EINTR / Boot failed: -4`，说明“同一轮 stop/start 干净恢复”不应再作为默认收尾路径。

因此，第二轮必须遵守三条约束：

1. 候选验证阶段只允许一条 bring-up 路径：`sudo /home/user/open-amp/set_env.sh`。  
2. `rpmsg-demo` 只允许用 `sudo` 执行：`sudo timeout 15s /home/user/open-amp/rpmsg-demo`。  
3. 试后恢复默认按“恢复官方固件 + reboot + 官方路径复验”收口，不再把同一轮内的重复 `start` 当成可靠恢复方式。

## 2. 试前门槛与备份

执行前先记录并确认：

1. 板上 live 官方固件仍是 `/lib/firmware/openamp_core0.elf`，大小应为 `1650448`。
2. 候选固件路径仍是 `/home/user/phytium-dev/release_v1.4.0/example/system/amp/openamp_for_linux/phytiumpi_aarch64_firefly_openamp_core0.elf`，大小应为 `1627224`。
3. 对 live 官方固件、候选固件、以及即将生成的备份文件，至少各记录一次 `stat` 和 `sha256sum`。
4. 备份 live 官方固件到时间戳路径，例如 `/tmp/openamp_core0.elf.backup.<timestamp>`。
5. 读取 `/sys/class/remoteproc/remoteproc0/state`。
6. 如果当前是 `running`，只允许先执行一次 `stop`，并确认状态回到 `offline` 后再继续。
7. 如果 `remoteproc0` 无法稳定回到 `offline`，本轮直接终止，不进行候选替换。

建议同时记录试前只读快照：

1. `remoteproc0` 的 `state`、`firmware`、`name`。
2. `/dev/rpmsg_ctrl0`、`/dev/rpmsg0` 是否存在。
3. 一段试前 dmesg 时间戳或标记，便于后续只截候选 bring-up 的新日志。

## 3. 候选验证步骤

### 3.1 替换与 bring-up

按下面顺序做，且不要插入额外 `start`：

1. 用备份好的官方固件留底后，把候选固件安装到 `/lib/firmware/openamp_core0.elf`。
2. 重新确认 live 固件大小已变为 `1627224`。
3. 记录 bring-up 起始时间。
4. 直接运行 `sudo /home/user/open-amp/set_env.sh`。
5. 不要在这之前或之后手工执行 `echo start > /sys/class/remoteproc/remoteproc0/state`。

`set_env.sh` 执行后立即记录：

1. 退出码。
2. `/sys/class/remoteproc/remoteproc0/state` 是否为 `running`。
3. dmesg 是否出现以下关键行：
   - `Booting fw image openamp_core0.elf, size 1627224`
   - `rpmsg host is online`
   - `creating channel rpmsg-openamp-demo-channel`
4. `/dev/rpmsg_ctrl0` 是否出现。

注意：

1. 基于 Phase 4 记录，`/dev/rpmsg0` 不要求在 `set_env.sh` 之后立刻存在。
2. 如果此时再次出现 `设备或资源忙`，应把本轮记为“流程被 confound”，而不是直接解释成“候选固件失败”。

### 3.2 用户态 demo 验证

在 `set_env.sh` 之后，只跑一次：

```bash
sudo timeout 15s /home/user/open-amp/rpmsg-demo
```

本步骤要求：

1. 必须用 `sudo`。
2. 不允许先用非 sudo 试一次。
3. 不允许在同一轮里重复多次试跑来“碰运气”。

记录以下结果：

1. `rpmsg-demo` 退出码。
2. `/dev/rpmsg0` 是否在运行后出现。
3. 输出中是否出现 `received message: Hello World! No:`。
4. 至少保存前 10 行输出，或至少保存 3 条连续 echo 行。

## 4. 成功 / 失败 / 无效判据

### 4.1 通过

只有同时满足以下条件，才把第二轮记为“候选用户态路径验证通过”：

1. live 固件已确认是候选大小 `1627224`。
2. `set_env.sh` 是本轮唯一的 bring-up 动作。
3. `remoteproc0` 最终为 `running`。
4. dmesg 明确出现候选大小 `1627224` 的启动记录。
5. dmesg 明确出现 `creating channel rpmsg-openamp-demo-channel`。
6. `/dev/rpmsg_ctrl0` 出现。
7. `sudo timeout 15s /home/user/open-amp/rpmsg-demo` 成功打开设备。
8. `/dev/rpmsg0` 出现。
9. `rpmsg-demo` 输出至少 3 条连续 `received message: Hello World! No:`。

### 4.2 部分通过

满足下面条件时，应记为“bring-up 通过，但用户态等价性未确认”：

1. `remoteproc0=running`。
2. dmesg 已出现 `size 1627224` 和 demo channel 创建记录。
3. 但 `sudo rpmsg-demo` 没有在本轮拿到稳定 echo 证据。

这类结果可以延续首轮结论，但不能升级成“候选已可替代官方 demo 固件”。

### 4.3 失败

出现以下任一情况，应记为候选验证失败：

1. 候选固件安装后，`remoteproc0` 不能进入 `running`。
2. dmesg 没有出现 `size 1627224` 的启动记录。
3. dmesg 没有出现 `creating channel rpmsg-openamp-demo-channel`。
4. `sudo rpmsg-demo` 仍然报设备打开失败，且不是 sudo/流程问题导致。
5. 恢复官方固件并 reboot 后，官方路径无法恢复到已知健康状态。

### 4.4 无效

出现以下任一情况，应记为“本轮无效，需要另起一轮”，不要把结果解释为候选失败：

1. 在 `set_env.sh` 前又手工执行了 `start`。
2. `rpmsg-demo` 先被非 sudo 执行，触发权限错误。
3. `set_env.sh` 命中了重复 `start` 的 `设备或资源忙`。
4. 同一轮里对 bring-up 或 demo 做了多次重试，导致日志无法区分哪次对应候选真实行为。

## 5. 恢复与收尾

无论候选结果如何，恢复都按下面顺序做：

1. 用试前备份文件把 `/lib/firmware/openamp_core0.elf` 恢复为官方固件。
2. 重新确认 live 官方固件大小回到 `1650448`，并与试前官方 `sha256sum` 一致。
3. 不把“同一轮 stop/start 再拉起官方固件”当成默认恢复步骤。
4. 直接执行一次 `sudo reboot`。
5. 等待 SSH 回连。
6. 回连后按官方已验证路径复验：
   - `sudo /home/user/open-amp/set_env.sh`
   - `sudo timeout 15s /home/user/open-amp/rpmsg-demo`
7. 只有当以下证据全部回来，才把整轮试验关闭：
   - live 官方固件大小 `1650448`
   - `remoteproc0=running`
   - dmesg 出现官方大小 `1650448` 的启动记录
   - `creating channel rpmsg-openamp-demo-channel`
   - `/dev/rpmsg_ctrl0`
   - `/dev/rpmsg0`
   - `rpmsg-demo` 再次稳定打印 echo

如果官方恢复失败，本轮优先级立刻切回“恢复官方健康状态”，不再继续候选测试。

## 6. 本轮最小落证清单

建议把以下项目完整落盘到新的执行报告：

1. 试前官方 live 文件 `stat`、`sha256sum`、备份路径。
2. 候选文件 `stat`、`sha256sum`。
3. 候选阶段 `set_env.sh` 的退出码。
4. 候选阶段 `remoteproc0/state`。
5. 候选阶段 dmesg 关键摘录，至少包含 `size 1627224` 和 channel 创建。
6. 候选阶段 `/dev/rpmsg_ctrl0` 与 `/dev/rpmsg0` 的存在性结果。
7. 候选阶段 `sudo rpmsg-demo` 的退出码与关键输出。
8. 恢复后的官方 `stat`、`sha256sum`、dmesg、设备节点与 `rpmsg-demo` 复验证据。

## 7. 建议执行流

最简洁、最干净的第二轮 flow 应该是：

1. 确认官方健康基线与备份。
2. 若 `remoteproc0` 正在跑，只做一次 `stop`，等到 `offline`。
3. 替换候选固件。
4. 只运行一次 `sudo /home/user/open-amp/set_env.sh` 完成 bring-up。
5. 只运行一次 `sudo timeout 15s /home/user/open-amp/rpmsg-demo` 完成用户态验证。
6. 恢复官方固件。
7. `sudo reboot`。
8. 用官方路径再验证一次，确认板子健康收尾。

这轮如果通过，结论就可以从“候选已证明能 bring-up”升级到“候选在板载官方 demo 用户态路径下也已跑通”；如果只到部分通过，结论边界也会比首轮更干净，不再混入重复 `start` 和 sudo 权限问题。
