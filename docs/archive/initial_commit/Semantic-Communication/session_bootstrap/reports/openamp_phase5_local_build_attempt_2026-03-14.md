# Phase 5 `openamp_for_linux` 本地构建尝试记录

> 日期：2026-03-14
> 目标：把 `STATUS_REQ/RESP` patch 真正应用到本地官方 SDK 工作副本 `/tmp/phytium-standalone-sdk`，并在本机尽最大努力完成 `example/system/amp/openamp_for_linux` 的本地构建。

## 1. 结论摘要

- patch 状态：已确认原始 SDK 尚未应用该 patch，本轮已成功 `git apply`
- 构建状态：未成功生成 `pe2204_aarch64_phytiumpi_openamp_core0.elf`
- `make image`：未执行，因为前置 ELF 未生成
- 是否建议继续部署远端 firmware：**不建议**。当前没有可部署的新 ELF

## 2. patch 应用状态

使用的 patch：

- `session_bootstrap/patches/phytium_openamp_for_linux_status_req_resp_2026-03-14.patch`

检查与应用结果：

1. `git -C /tmp/phytium-standalone-sdk apply --reverse --check <patch>`
   - 失败，说明 patch 不是“已应用”状态
2. `git -C /tmp/phytium-standalone-sdk apply --check <patch>`
   - 成功，说明 patch 可干净应用
3. `git -C /tmp/phytium-standalone-sdk apply <patch>`
   - 成功

本轮真正改入 SDK 的源码文件：

- `example/system/amp/openamp_for_linux/src/slaver_00_example.c`

本轮结束时，SDK 工作树相关状态为：

- `M example/system/amp/openamp_for_linux/src/slaver_00_example.c`
- `M example/system/amp/openamp_for_linux/sdkconfig`
- `M example/system/amp/openamp_for_linux/sdkconfig.h`

后两项来自本轮 `load_kconfig` / `olddefconfig` / `gen_kconfig` 的配置展开。

## 3. 构建命令与真实结果

工作目录：

- `/tmp/phytium-standalone-sdk/example/system/amp/openamp_for_linux`

### 3.1 按 runbook 的直接尝试

执行：

```bash
make load_kconfig LOAD_CONFIG_NAME=pe2204_aarch64_phytiumpi_openamp_core0
make clean
make all -j"$(nproc)"
```

结果：

- `make load_kconfig ...` 在非交互终端里失败，报错来自 `menuconfig_autosave.py` 的 curses 初始化：
  - `_curses.error: cbreak() returned ERR`
  - `_curses.error: nocbreak() returned ERR`
- 但该命令在失败前已经把
  - `configs/pe2204_aarch64_phytiumpi_openamp_core0.config`
  - 复制到了当前目录的 `sdkconfig`
- 随后直接 `make all` 时，因配置未完全展开，出现：
  - `arch///arch_compiler.mk: No such file or directory`

对应日志：

- `/tmp/phytium_openamp_build_logs/load_kconfig.log`
- `/tmp/phytium_openamp_build_logs/make_all.log`

### 3.2 非交互配置展开后的重试

为了在当前无 TTY 环境下继续排障，额外执行：

```bash
SDK_DIR=/tmp/phytium-standalone-sdk \
KCONFIG_CONFIG=sdkconfig \
python3 /tmp/phytium-standalone-sdk/tools/build/Kconfiglib/olddefconfig.py Kconfig

make gen_kconfig
make clean
make all -j"$(nproc)"
```

结果：

- `olddefconfig.py` 成功将 preset 展开为完整 `sdkconfig`
- 关键配置项已出现：
  - `CONFIG_ARCH_NAME="armv8"`
  - `CONFIG_ARCH_EXECUTION_STATE="aarch64"`
  - `CONFIG_SOC_NAME="pe220x"`
  - `CONFIG_BOARD_NAME="phytiumpi"`
  - `CONFIG_TARGET_NAME="openamp_core0"`
- 之后 `make all` 进入真实编译阶段，但失败于工具链缺失：
  - `/bin/aarch64-none-elf-gcc: not found`

对应日志：

- `/tmp/phytium_openamp_build_logs/olddefconfig.log`
- `/tmp/phytium_openamp_build_logs/gen_kconfig_after_olddefconfig.log`
- `/tmp/phytium_openamp_build_logs/make_all_after_olddefconfig.log`

### 3.3 为尽量推进构建做的本机兜底尝试

由于本机存在 `aarch64-linux-gnu-*`，但不存在官方预期的 `aarch64-none-elf-*`，本轮额外尝试了两层临时兜底，均只放在 `/tmp`，未改 SDK 源码：

1. 临时工具链 wrapper：
   - `/tmp/aarch64-none-elf-wrap/bin/aarch64-none-elf-* -> /usr/bin/aarch64-linux-gnu-*`
   - 通过 `AARCH64_CROSS_PATH=/tmp/aarch64-none-elf-wrap` 传入构建
2. 临时 newlib include 增强：
   - `/tmp/phytium_enhance_newlib_include.mk`
   - 通过 `ENHANCE_DIR_INCLUDE=/tmp/phytium_enhance_newlib_include.mk` 传入构建

对应结果分三步：

1. 仅使用 wrapper：
   - 编译推进，但失败于 `reent.h: No such file or directory`
2. 仅补一层 `lib/newlib/libc/include`：
   - 失败于 `newlib.h: No such file or directory`
3. 复用 SDK 自带 `lib/newlib/include.mk` 补齐 include：
   - 编译和归档基本完成
   - 最终链接失败于 bare-metal C runtime/newlib 相关符号缺失：
     - `undefined reference to '__errno'`
     - `undefined reference to '__assert_func'`

说明：

- 这证明 patch 本身没有在编译前期引入新的明显语法错误
- 真正阻塞本机构建的是 **官方 bare-metal 工具链 / newlib 运行时缺失**
- 用 Linux 交叉链 `aarch64-linux-gnu-*` 做 wrapper 只能把问题推迟到链接期，不能替代官方 `aarch64-none-elf-*`

对应日志：

- `/tmp/phytium_openamp_build_logs/make_all_with_wrapper.log`
- `/tmp/phytium_openamp_build_logs/make_all_with_wrapper_and_newlib_include.log`
- `/tmp/phytium_openamp_build_logs/make_all_with_wrapper_and_full_newlib_include.log`

## 4. 产物情况

预期 ELF：

- `/tmp/phytium-standalone-sdk/example/system/amp/openamp_for_linux/pe2204_aarch64_phytiumpi_openamp_core0.elf`

实际结果：

- ELF：**未生成**

额外生成的 map 文件：

- 路径：`/tmp/phytium-standalone-sdk/example/system/amp/openamp_for_linux/pe2204_aarch64_phytiumpi_openamp_core0.map`
- 大小：`1476438` bytes
- mtime：`2026-03-14 01:26:56.795903940 +0800`

由于 ELF 未生成，本轮**没有执行**：

```bash
make image USR_BOOT_DIR=/tmp/phytium_openamp_out
```

因此也**没有**产出部署名：

- `/tmp/phytium_openamp_out/openamp_core0.elf`

## 5. blocker 与最小下一步

### 当前 blocker

1. `make load_kconfig` 在当前非交互 shell 中依赖 curses/TTY
2. 本机缺少官方预期的 bare-metal AArch64 工具链：
   - `aarch64-none-elf-gcc`
   - 以及同前缀配套 binutils
3. 本机缺少与该 bare-metal 工具链匹配的 C runtime / newlib 链接环境
   - 现象为最终链接缺失 `__errno`、`__assert_func`

### 最小下一步

最小可行下一步不是部署远端，而是先在本机补齐官方 bare-metal 构建环境后重跑：

```bash
cd /tmp/phytium-standalone-sdk/example/system/amp/openamp_for_linux
make load_kconfig LOAD_CONFIG_NAME=pe2204_aarch64_phytiumpi_openamp_core0
make clean
make all -j"$(nproc)"
make image USR_BOOT_DIR=/tmp/phytium_openamp_out
```

如果仍然只能在无 TTY 环境里跑，可沿用本轮验证过的非交互替代：

```bash
SDK_DIR=/tmp/phytium-standalone-sdk \
KCONFIG_CONFIG=sdkconfig \
python3 /tmp/phytium-standalone-sdk/tools/build/Kconfiglib/olddefconfig.py Kconfig
make gen_kconfig
```

但这不能替代官方 bare-metal 工具链本身。

## 6. 本轮边界

- 本轮**没有**修改远端飞腾派 `/lib/firmware/openamp_core0.elf`
- 本轮**没有**宣称构建成功
- 本轮结果只能说明：
  - patch 已成功应用到本地 SDK
  - `openamp_for_linux` 已尽最大努力在本机推进到链接阶段
  - 目前仍缺可部署的新 ELF
