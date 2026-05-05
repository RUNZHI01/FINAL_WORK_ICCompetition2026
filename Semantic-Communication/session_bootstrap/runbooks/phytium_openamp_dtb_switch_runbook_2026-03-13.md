# 飞腾板 OpenAMP DTB 切换执行手册

> 日期：2026-03-13  
> 目标：为后续把飞腾板从默认 DTB 切到 OpenAMP DTB 提供正式、最小改动、可回滚的执行预案。  
> 本轮边界：只落地 runbook 和脚本骨架，不在本轮执行 `apply`、`rollback` 或 reboot。

## 1. 当前证据总结

综合以下证据：

- `session_bootstrap/reports/openamp_phase4_remote_audit_summary_2026-03-13.md`
- `session_bootstrap/reports/openamp_phase4_bringup_root_cause_2026-03-13.md`
- `session_bootstrap/reports/openamp_platform_audit_phytium_20260313_231014.md`

当前高概率不是 Python 依赖、用户代码或 OpenAMP wrapper 本身的问题，而是**飞腾板当前 live DT 仍停留在默认 DTB**：

1. live DT 只看到 `mailbox@32a00000`，没有 `remoteproc`、`rpmsg`、`openamp` 相关节点。
2. `/boot/phytium-pi-board.dtb -> phytium-pi-board-v3.dtb` 已被只读比对确认。
3. `/boot/phytium-pi-board-v3-openamp.dtb` 明确包含 `homo_rproc`、`rproc@b0100000`、`openamp_core0.elf`、`reserved-memory` 等关键线索。
4. live DT 与默认 `phytium-pi-board-v3.dtb` 命中一致，而与 `phytium-pi-board-v3-openamp.dtb` 明显不一致。
5. `homo-rproc` 驱动和 `openamp_core0.elf` 固件都已存在，但运行态没有 `remoteprocX`，说明更像是 DT/boot 选择链没有生效。

基于以上对照，Phase 4 当前最小、最值得先验证的改动是：

- 把 `/boot/phytium-pi-board.dtb` 从 `phytium-pi-board-v3.dtb` 切到 `phytium-pi-board-v3-openamp.dtb`
- 重启后重新检查 `remoteproc0`、RPMsg bus 和 `/dev/rpmsg*`

## 2. 最小改动方案

目标切换仅包含一个动作：

```text
/boot/phytium-pi-board.dtb
  from -> phytium-pi-board-v3.dtb
  to   -> phytium-pi-board-v3-openamp.dtb
```

约束：

- 只改 `/boot/phytium-pi-board.dtb` 软链，不改其他 boot 配置。
- 不改用户代码。
- 不改 Python 依赖。
- 不自动 reboot，重启步骤保留为显式人工批准动作。
- apply/rollback 前都先检查当前软链并做远端备份。

对应脚本骨架：

- `session_bootstrap/scripts/plan_switch_phytium_openamp_dtb.sh`

默认行为是 `plan-only`，只打印计划；只有显式 `--apply` 才会真正远端执行。

## 3. 执行前检查

在真正批准 `--apply` 前，至少确认以下项目：

1. SSH 仍可登录飞腾板，且已准备好登录配置：
   - 推荐：`session_bootstrap/config/phytium_pi_login.env`
   - 模板：`session_bootstrap/config/phytium_pi_login.example.env`
2. 先运行 plan-only，不改远端：

```bash
bash ./session_bootstrap/scripts/plan_switch_phytium_openamp_dtb.sh \
  --env ./session_bootstrap/config/phytium_pi_login.env
```

3. 确认远端具备对 `/boot` 的修改权限：
   - 最稳妥是 root 登录，或
   - 非 root 但 `sudo -n true` 可通过
4. 确认本轮目标文件存在：
   - `/boot/phytium-pi-board.dtb`
   - `/boot/phytium-pi-board-v3.dtb`
   - `/boot/phytium-pi-board-v3-openamp.dtb`

## 4. 批准后的 apply 步骤

apply 命令本身只做备份和软链切换，不会自动重启：

```bash
bash ./session_bootstrap/scripts/plan_switch_phytium_openamp_dtb.sh \
  --env ./session_bootstrap/config/phytium_pi_login.env \
  --apply
```

脚本预期执行顺序：

1. 检查当前 `/boot/phytium-pi-board.dtb` 是否仍是软链。
2. 检查默认 DTB 与 OpenAMP DTB 都存在。
3. 备份当前软链到 `/boot/phytium-pi-board.dtb.backup.<timestamp>`。
4. 把软链改成 `phytium-pi-board-v3-openamp.dtb`。
5. 输出新旧软链信息。
6. 停止，不自动 reboot。

reboot 必须单独批准并人工触发。可按当时实际权限选择现有远端 SSH 入口执行；runbook 本身只定义切换预案，不把 reboot 隐含到脚本里。

## 5. 执行后验证点

重启并重新连板后，至少检查以下几点：

1. 软链结果：

```bash
ls -l /boot/phytium-pi-board.dtb
```

预期应指向：

```text
phytium-pi-board-v3-openamp.dtb
```

2. remoteproc 实例：

```bash
ls -l /sys/class/remoteproc
test -d /sys/class/remoteproc/remoteproc0
```

3. RPMsg bus 设备：

```bash
ls -l /sys/bus/rpmsg/devices
```

4. 用户态字符设备：

```bash
ls -l /dev/rpmsg* /dev/rpmsg_ctrl* 2>/dev/null || true
```

5. 辅助日志：

```bash
dmesg | grep -Ei 'remoteproc|rpmsg|homo-rproc|mailbox'
```

成功标准：

- 至少出现 `remoteproc0`
- 最好还能看到 `/sys/bus/rpmsg/devices/*`
- 进一步理想状态是出现 `/dev/rpmsg_ctrl*` 或 `/dev/rpmsg*`

只有满足这些条件后，才继续真实 `STATUS_REQ/RESP` 和 `JOB_REQ/JOB_ACK` 接线。

## 6. 风险说明

本方案的风险边界比较清楚：

- 最大风险是 reboot 后板子短时间内 SSH 不可达，或者新的 DTB 仍未把 `remoteproc` 带起来。
- 本方案不修改用户代码、不改 Python 依赖、不碰 trusted current 现有 runner 数据面。
- 变更只集中在 `/boot/phytium-pi-board.dtb` 软链，影响范围可控且可回滚。
- 若 reboot 后 SSH 长时间不可达，可能需要串口或其他带外方式做人工回退。

## 7. 回滚方案

rollback 同样默认先走 plan-only：

```bash
bash ./session_bootstrap/scripts/plan_switch_phytium_openamp_dtb.sh \
  --env ./session_bootstrap/config/phytium_pi_login.env \
  --rollback
```

真正执行回滚：

```bash
bash ./session_bootstrap/scripts/plan_switch_phytium_openamp_dtb.sh \
  --env ./session_bootstrap/config/phytium_pi_login.env \
  --rollback \
  --apply
```

rollback 目标是把软链恢复为：

```text
/boot/phytium-pi-board.dtb -> phytium-pi-board-v3.dtb
```

回滚步骤与 apply 对称：

1. 再次检查当前软链和候选 DTB。
2. 先备份当前软链。
3. 恢复指向 `phytium-pi-board-v3.dtb`。
4. 人工 reboot。
5. reboot 后确认 SSH、软链和系统基本功能恢复。

## 8. 本轮结论

当前已经具备：

- 根因证据收口
- 正式 runbook
- 可直接进入下一轮真实执行的脚本骨架

当前还缺：

- 用户明确批准 `--apply`
- 用户明确批准 reboot
- reboot 后的 `remoteproc0` / RPMsg 真实验证结果
