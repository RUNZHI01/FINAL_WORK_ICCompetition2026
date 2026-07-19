# Phase 5 从核源码入口定位记录

> 日期：2026-03-14
> 目标：确认 `openamp_core0.elf` 的官方源码与构建入口，给后续把 echo demo 替换为 `STATUS_REQ/RESP` 处理器提供明确起点。

## 1. 关键结论

已确认飞腾官方源码入口真实存在，并且不再是猜测：

- 官方仓库：`https://gitee.com/phytium_embedded/phytium-standalone-sdk.git`
- 文档明确给出的 OpenAMP 例程路径：
  - `example/system/amp/openamp`
  - `example/system/amp/openamp_for_linux`
- 对应当前飞腾派 Linux + remoteproc 装载 `openamp_core0.elf` 的最相关目录是：
  - `example/system/amp/openamp_for_linux`

## 2. 与当前飞腾派现状的直接映射

当前飞腾派上实际运行的现象：

- DTB：`phytium-pi-board-v3-openamp.dtb`
- firmware：`openamp_core0.elf`
- remoteproc：`remoteproc0`
- rpmsg service：`rpmsg-openamp-demo-channel`
- Linux 用户态设备：`/dev/rpmsg_ctrl0`、`/dev/rpmsg0`

在官方 `phytium-standalone-sdk` 中，最贴近这套链路的源码位置是：

- `example/system/amp/openamp_for_linux/main.c`
- `example/system/amp/openamp_for_linux/src/slaver_00_example.c`
- `example/system/amp/openamp_for_linux/configs/pe2204_aarch64_phytiumpi_openamp_core0.config`
- `third-party/openamp/ports/rpmsg_service.h`

## 3. 已确认的关键源码/配置点

### 3.1 PhytiumPi aarch64 对应配置存在

已确认以下配置文件存在：

- `example/system/amp/openamp_for_linux/configs/pe2204_aarch64_phytiumpi_openamp_core0.config`
- `example/system/amp/openamp/device_core/configs/pe2204_aarch64_phytiumpi_openamp_device_core.config`
- `example/system/amp/openamp/driver_core/configs/pe2204_aarch64_phytiumpi_openamp_driver_core.config`

这意味着官方 SDK 直接支持 PhytiumPi aarch64 的 OpenAMP 例程编译，不需要从零猜平台配置。

### 3.2 `openamp_core0.elf` 对应源码入口

`openamp_for_linux/main.c` 当前入口：

- `main()` -> `slave00_rpmsg_echo_process()`

这说明当前 `openamp_core0.elf` 的核心行为就是：

- 启动 OpenAMP transport
- 跑一个 **rpmsg echo** 流程

### 3.3 当前 service name 的源码定义

已确认：

- `third-party/openamp/ports/rpmsg_service.h`
- 其中定义：
  - `#define RPMSG_SERVICE_NAME "rpmsg-openamp-demo-channel"`

这和飞腾派当前运行态看到的：

- `rpmsg-openamp-demo-channel`

完全一致，说明我们已经对上了真正的从核源码来源。

### 3.4 现有 demo 的角色划分

官方 README 明确说明：

- `driver_core`：管理核（模拟）
- `device_core`：性能核（模拟）
- `openamp_for_linux`：兼容 Linux `remoteproc/rpmsg/virtio` 路径的版本

因此，当前飞腾派实际跑 Linux remoteproc 的时候，应该优先以：

- `openamp_for_linux`

作为下一步修改 `STATUS_REQ/RESP` 的起点，而不是优先改 `openamp/driver_core` 或 `device_core` 的裸机对裸机示例。

## 4. 现在不再缺什么

现在已经不缺：

- OpenAMP 上游项目来源
- 飞腾官方 SDK 仓库来源
- PhytiumPi 对应配置名
- 当前 service name 的源码位置
- `openamp_core0.elf` 对应入口函数所在目录

## 5. 现在真正还缺什么

当前还缺的是：

1. 一个可修改、可编译的本地工作副本（现在官方 SDK 只在 `/tmp/phytium-standalone-sdk` 临时克隆）
2. 决定如何最小改造 `openamp_for_linux`：
   - 路线 A：保持 `RPMSG_SERVICE_NAME` 不变，只替换 echo 逻辑为 `STATUS_REQ/RESP`
   - 路线 B：改 service name，同步修改 Linux 侧 bridge / 绑定逻辑
3. 确认构建产物如何重新部署回飞腾派：
   - 重新生成 `openamp_core0.elf`
   - 覆盖 `/lib/firmware/openamp_core0.elf`
   - 重新 `start remoteproc0`

## 6. 推荐下一步

推荐优先走：

### 路线 A（风险更低）

- 保持：`RPMSG_SERVICE_NAME = "rpmsg-openamp-demo-channel"`
- 修改：`openamp_for_linux/src/slaver_00_example.c`
- 目标：把现有 echo 逻辑改成最小 `STATUS_REQ -> STATUS_RESP`

这样做的好处：

- 不需要同步改 Linux 侧 channel 绑定逻辑
- 不会破坏当前已经打通的 `/dev/rpmsg0` 路径
- 风险明显小于“改 service name + 改全链”

### 应优先改的文件

1. `example/system/amp/openamp_for_linux/src/slaver_00_example.c`
   - 当前 echo 处理逻辑主入口
2. `third-party/openamp/ports/rpmsg_service.h`
   - 若后续决定改 service name，再动这里
3. `example/system/amp/openamp_for_linux/main.c`
   - 视是否需要替换入口函数
4. `example/system/amp/openamp_for_linux/configs/pe2204_aarch64_phytiumpi_openamp_core0.config`
   - 若要调整构建配置，再动这里

## 7. 一句话结论

**`openamp_core0.elf` 的官方源码入口已经找到，下一步不再是“找源码”，而是“基于 `openamp_for_linux` 最小改造 echo 逻辑为 `STATUS_REQ/RESP`”。**
