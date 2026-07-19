# Phase 4 bring-up 根因探查报告（飞腾板 OpenAMP）

> 日期：2026-03-13
> 范围：只基于本地已回收证据收口，不新增远端探测结果
> 关联证据：
> - `session_bootstrap/reports/openamp_phase4_bringup_probe_phytium_20260313_232022.json`
> - `session_bootstrap/reports/openamp_platform_audit_phytium_20260313_231014.md`
> - `session_bootstrap/reports/openamp_phase4_remote_audit_summary_2026-03-13.md`
> - `paper/OpenAMP最小闭环接口设计与测试矩阵_2026-03-13.md`

## 1. 结论摘要

当前 Phase 4 的 blocker 已从“板端 runtime bring-up 未完成”进一步收敛为：

1. 当前 live device tree 只看到 `mailbox@32a00000`，未看到 `remoteproc`、`rpmsg`、`openamp` 相关节点。
2. `/boot` 下同时存在 `phytium-pi-board-v3-openamp.dtb`，且该 DTB 字符串中明确包含 `rproc@b0100000`、`homo_rproc@0`、`homo,rproc`、`openamp_core0.elf`。
3. `/boot/phytium-pi-board.dtb` 还是一个通用软链，并且当前明确指向 `phytium-pi-board-v3.dtb`。
4. live DT 与 `phytium-pi-board.dtb`（默认 dtb）一致只包含 `mailbox@32a00000`，而与 `phytium-pi-board-v3-openamp.dtb` 不一致：后者独有 `homo_rproc`、`rproc@b0100000`、`openamp_core0.elf`、`reserved-memory`。
5. `/lib/firmware` 与 `/usr/lib/firmware` 都存在 `openamp_core0.elf`。
6. platform driver 已存在 `homo-rproc` 与 `phytium-mbox`，但 platform device 只有 `32a00000.mailbox`。

基于以上证据，最可能的 blocker 排序是：

1. 当前 boot 链大概率仍在使用默认 `phytium-pi-board.dtb -> phytium-pi-board-v3.dtb`，而不是 `phytium-pi-board-v3-openamp.dtb`；或者等效 OpenAMP overlay 未生效。
2. 即使 boot 目标本应包含 OpenAMP 节点，`homo-rproc` 对应的 remoteproc 节点也没有被枚举/绑定。
3. 从核固件 `openamp_core0.elf` 虽已落盘，但尚未真正接入 remoteproc 启动链。

这里第 1 条仍然属于高置信度推断而不是直接的 bootloader 日志证明；但它已经不只是“候选 dtb 中有节点而 live DT 中没有”的弱对照，而是“live DT 与默认 dtb 命中完全一致、与 openamp dtb 命中显著不同”的强对照。

## 2. 已确认事实

### 2.1 live DT 只暴露 mailbox

`openamp_phase4_bringup_probe_phytium_20260313_232022.json` 中：

- `/proc/device-tree` 关键路径只命中 `__symbols__/mbox`、`firmware/scmi/mboxes`、`soc/mailbox@32a00000`
- `/sys/firmware/devicetree/base` 关键路径同样只命中 `mailbox@32a00000`
- `dt_keyword_props` 里只提取到 `compatible = "phytium,mbox"`

这说明当前运行中的 live DT 没有把 `remoteproc`、`rpmsg`、`openamp` 相关节点带到内核可见视图中。

### 2.2 /boot 存在 openamp DTB，且内容与 live DT 明显不同

同一份 probe 证据显示：

- `/boot/phytium-pi-board-v3-openamp.dtb` 存在于 boot 候选文件列表
- 该 DTB 字符串命中：
  - `reserved-memory`
  - `rproc@b0100000`
  - `homo_rproc@0`
  - `homo,rproc`
  - `openamp_core0.elf`

而 live DT 侧没有出现这些节点/关键字。

### 2.2.1 默认 dtb 软链与 live DT 高度一致

新增只读比对进一步确认：

- `/boot/phytium-pi-board.dtb -> phytium-pi-board-v3.dtb`
- live DT / default DTB / openamp DTB 的关键节点对比为：
  - `homo_rproc`: live=`no` / default=`no` / openamp=`yes`
  - `rproc@b0100000`: live=`no` / default=`no` / openamp=`yes`
  - `openamp_core0.elf`: live=`no` / default=`no` / openamp=`yes`
  - `reserved-memory`: live=`no` / default=`no` / openamp=`yes`
  - `mailbox@32a00000`: live=`yes` / default=`yes` / openamp=`yes`

这组对比比“仅仅看到 `/boot` 下有 openamp dtb”更强：它说明当前 live DT 与默认 dtb 同步，而不是与 openamp dtb 同步。

### 2.3 固件文件已落盘

同一份 probe 证据显示：

- `/lib/firmware/openamp_core0.elf`
- `/usr/lib/firmware/openamp_core0.elf`

因此当前问题不能简化为“固件文件根本不存在”。

### 2.4 driver 在，device 不在

同一份 probe 证据显示：

- platform drivers:
  - `homo-rproc`
  - `phytium-mbox`
- platform devices:
  - `32a00000.mailbox`

再结合平台审计报告可知：

- `/sys/class/remoteproc` 存在但没有 `remoteprocX`
- `/sys/bus/rpmsg` 存在但无 channel/device
- dmesg 摘录只有 `phytium-mbox 32a00000.mailbox: Phytium SoC Mailbox registered`

这说明 remoteproc 驱动代码路径存在，但其前置 platform device/DT 绑定链没有真正建立起来。

## 3. 根因优先级排序

### P1. 更可能是 boot/DTB 选择问题导致 remoteproc 实例未枚举

推断依据：

- `/boot` 中存在单独的 `phytium-pi-board-v3-openamp.dtb`
- 该 DTB 明确包含 `homo_rproc`、`rproc@b0100000`、`openamp_core0.elf`
- 当前 live DT 完全没有这些节点

因此，最高概率是当前启动链仍使用普通板级 DTB，或者本应启用的 OpenAMP overlay 没有被实际应用。

### P2. remoteproc 节点未枚举/未绑定

推断依据：

- `homo-rproc` driver 已存在
- 但 platform device 只有 `32a00000.mailbox`

这通常意味着 DT 节点没有生成对应 platform device，或者生成后未完成匹配绑定。

### P3. 从核固件未接入启动链

推断依据：

- `openamp_core0.elf` 已存在于常见 firmware 路径
- 但没有 `remoteprocX`，也没有可读的 `firmware`/`state` sysfs

这说明固件文件本身不是首要缺项，但其装载入口尚未被运行态消费。

### P4. RPMsg 用户态节点未出现是后续表征，不是首要根因

推断依据：

- 设计文档要求真实通道阶段先具备 `rpmsg_char` 用户态端点，再打 `STATUS_REQ/RESP`
- 当前连 `remoteprocX` 都没有出现

因此 `/dev/rpmsg*` 缺失更像是前序 remoteproc/DT bring-up 未完成后的连锁表现，而不是最前面的 blocker。

## 4. 对 Phase 4 / Phase 5 的直接影响

`paper/OpenAMP最小闭环接口设计与测试矩阵_2026-03-13.md` 明确要求：

1. 阶段 B 先接 `rpmsg_char`
2. 再先跑 `STATUS_REQ/RESP`
3. 然后才是 `JOB_REQ/ACK`

当前由于 remoteproc 实例未枚举，真实 `STATUS_REQ/RESP` 还不具备进入条件；因此 Phase 5 的 wrapper 只能停留在 mock 或 dry-run 层，不能宣称已形成真机异构控制闭环。

## 5. 下一步动作

### 5.1 无需 root 可验证

1. 导出并比对 live DT 与 `/boot/phytium-pi-board-v3-openamp.dtb`：
   - `dtc -I fs -O dts /proc/device-tree > live.dts`
   - `dtc -I dtb -O dts /boot/phytium-pi-board-v3-openamp.dtb > openamp.dts`
   - 重点 grep `homo_rproc|rproc@b0100000|openamp_core0.elf|reserved-memory|mbox`
2. 检查 boot 配置文件是否显式指向普通 DTB 或缺失 OpenAMP overlay：
   - `cat /boot/overlay/cmd.txt`
   - 如存在，再检查板上实际使用的 boot 配置文件（例如 extlinux/uEnv/vendor boot config）
3. 继续读取只读 sysfs 证据，确认是否仍只有 mailbox 设备：
   - `ls -l /sys/bus/platform/devices`
   - `ls -l /sys/bus/platform/drivers/homo-rproc`
   - `find /proc/device-tree /sys/firmware/devicetree/base -iname '*rproc*' -o -iname '*openamp*' -o -iname '*rpmsg*'`

验证通过标准：

- live DT 中能看到 `homo_rproc`/`rproc@...`
- 或明确证明 boot 配置当前没有选中 `phytium-pi-board-v3-openamp.dtb`

### 5.2 可能需要 root / 改 boot 才能验证

1. 将 boot 目标切换到 `phytium-pi-board-v3-openamp.dtb` 或启用等效 OpenAMP overlay，并重启。
2. 重启后检查是否出现：
   - `/sys/class/remoteproc/remoteproc0`
   - `/sys/bus/platform/devices/*homo*` 或等价 remoteproc 设备
   - `/sys/bus/rpmsg/devices/*`
   - `/dev/rpmsg_ctrl*`、`/dev/rpmsg*`
3. 若 `remoteproc0` 已出现但仍未生成 RPMsg 入口，再继续：
   - 查看 `name/state/firmware/recovery/coredump`
   - 必要时补 `modprobe rpmsg_char`
   - 必要时通过 sysfs 手动 `start` remoteproc
4. 若切到 openamp DTB 后仍只有 mailbox，则继续排查：
   - `homo-rproc` bind 规则
   - DT 节点 `status`
   - reserved-memory / mailbox / firmware-name 属性是否满足驱动预期

验证通过标准：

- `remoteprocX` 实例出现，且 `firmware` 指向 `openamp_core0.elf` 或等价固件名
- 至少出现一个 RPMsg 用户态入口
- 才进入真实 `STATUS_REQ/RESP` bring-up

## 6. 建议作为下一轮 bring-up 的执行顺序

1. 先做 live DT vs openamp DTB 对比，尽快确认是不是 boot 选择问题。
2. 若确认 boot 目标不对，优先修 boot/DTB，而不是先在 Linux 用户态反复试 `rpmsg_char`。
3. 只有在 `remoteprocX` 已出现后，才继续推进 `STATUS_REQ/RESP` 和 wrapper 接线。
