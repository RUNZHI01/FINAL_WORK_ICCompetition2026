# Phase 5 OpenAMP 固件剩余大小差分类结论

> 日期：2026-03-14  
> 目标：比较板上官方 `openamp_core0.elf`（`1650448` bytes）与当前最接近的官方原版重建候选 `release_v1.4.0`（`1627224` bytes），判断剩余 `23224` bytes 差值主要来自 debug 区域还是 runtime/resource 区域，并把过程固化到仓库。  
> 更新说明：本文件已纳入同一会话后续在 Codex 之外取得的 live ELF 对比证据，因此不再只依赖早先的 size-composition / sandbox SSH fallback 推断。

## 1. 最终结论

最终结论需要写得更精确：

- 剩余 `23224` bytes **仍然更像 `.debug_*` / 符号表 / 其他非装载元数据差异**，而不是“大块 runtime/resource 布局还没对齐”。
- 但 `release_v1.4.0` **并不是 runtime payload 字节级一致的同一份固件**，因为 `load0`、`.text`、`.data`、`.rodata` 的内容仍有差异。

直接证据如下：

1. 两边两个 `PT_LOAD` segment 的 `FileSiz` 完全一致：
   - `load0 filesz = 114688`
   - `load1 filesz = 4096`
2. `.resource_table` 区域 hash 完全一致，`sha256 = 1b2083096dcd01a3a0855015c37b7e6d50dc71f4336d5c68d7c99236ff379794`。
3. 但 runtime 字节内容并未完全一致：
   - `load0` hash 不同
   - `.text` hash 不同
   - `.data` hash 不同
   - `.rodata` 不但 hash 不同，而且大小也有轻微差异（官方 `11217`，候选 `10801`）

因此，当前最稳妥的定性是：

**剩余 `23224` bytes 仍明显更符合 debug / 非装载元数据差异；但 `release_v1.4.0` 不是 byte-identical runtime match。**

## 2. 板上官方 ELF 的大小构成

原始文件：

- `session_bootstrap/reports/old_fw_compare_20260314/openamp_core0_official.elf`
- 文件大小：`1650448`

基于 `readelf -SW`、`readelf -lW`、`size -A -d` 与临时 `objcopy` 结果，板上官方 ELF 的构成为：

| 项目 | 大小（bytes） | 说明 |
| --- | ---: | --- |
| `.debug_*` 合计 | `1413392` | 主体是 `.debug_info`、`.debug_line`、`.debug_loc` |
| runtime/resource section 落盘合计 | `116305` | `.text=92800`、`.rodata=11217`、`.data=8192`、`.resource_table=4096` |
| `LOAD` segment `FileSiz` 合计 | `118784` | 比上面多出 `2479` bytes 的段内对齐/填充 |
| 其他非装载元数据 | `34861` | `.symtab`、`.strtab`、`.comment`、`.shstrtab` |
| 其他文件级开销/填充 | `85890` | ELF 头、program header、section header、对齐空洞等 |
| `objcopy --strip-debug` 后大小 | `232136` | 用于估算“去掉 debug 后”的整体量级 |
| `objcopy --strip-all` 后大小 | `201672` | 说明符号/字符串表本身也不是零开销 |

同时还要注意：

- `.bss + .heap + .stack + .le_shell` 的 **内存**总量是 `6659776` bytes
- 但这些 section 中大部分是 `NOBITS`，**不计入 ELF 文件大小差值**

所以，“核运行时占用很大”与“ELF 文件还差 `23 KB`”不是同一个问题。

## 3. 后续 live ELF-to-ELF 证据

### 3.1 Program header 对齐情况

后续 live 比较表明，板上官方 ELF 与 `release_v1.4.0` 候选的两个 `PT_LOAD` segment 落盘长度完全一致：

| Segment | 官方 `FileSiz` | 候选 `FileSiz` | 结论 |
| --- | ---: | ---: | --- |
| `load0` | `114688` | `114688` | 完全一致 |
| `load1` | `4096` | `4096` | 完全一致 |

这点很关键：它直接排除了“剩余 `23224` bytes 主要还卡在 `PT_LOAD` 级别的大块落盘尺寸不匹配”这一解释。

### 3.2 `resource_table` 已经字节级一致

`load1` 对应的 `.resource_table` 区域 hash 完全一致：

| 区域 | 大小 | 官方 sha256 | 候选 sha256 | 结论 |
| --- | ---: | --- | --- | --- |
| `.resource_table` | `4096` | `1b2083096dcd01a3a0855015c37b7e6d50dc71f4336d5c68d7c99236ff379794` | `1b2083096dcd01a3a0855015c37b7e6d50dc71f4336d5c68d7c99236ff379794` | 完全一致 |

这说明剩余 `23 KB` 差值 **不是** 由 resource table 布局或其落盘内容引起。

### 3.3 runtime payload 仍存在内容差异

虽然 `PT_LOAD` 尺寸对齐、`.resource_table` 也一致，但 `load0` 内部内容并不相同：

| 区域 | 官方 | 候选 | 结论 |
| --- | --- | --- | --- |
| `load0` sha256 | `fcca5482c78753e412cd9f849996e98e9092fbe451e9d7896fa16319ba428581` | `80aecca80e44afac452809dbc8297b73601103a24e0bebd501023c8cadcdbc76` | 不同 |
| `.text` sha256 | `9c2773f50deb6705096443054b5deb44f0a0a361ddfaef4de1dd0e0fa102758e` | `db5ffe9be8c8b673a3090e12e04f89501cd12f766bf28c54172253083b531db2` | 不同 |
| `.data` sha256 | `7e2c039d4a5f3e437ed6c1edcd76d21cf38901ef8c5068cb27011d678b3fcf92` | `77863a0402a83183118fb7d03afa213dbdd58ca851961336aa750b453c72589a` | 不同 |
| `.rodata` 大小 / sha256 | `11217` / `2be5ecce03e2de8896f233f5156e471be93b304a689afd0ad0a8a0b2d3ca9fc1` | `10801` / `a1f065414f8d2f5e941ecd40f68dc9abc5cc95be801e855447924334a71eb6ad` | 大小与内容都不同 |

所以，`release_v1.4.0` 的确仍有 runtime 级差异；只是这个差异表现为：

- **在已经对齐的 `load0` 包络之内，内容不同**
- 而不是 **`PT_LOAD` 尺寸本身还差出大块空间**

## 4. 对 `23224`-byte gap 的精炼解释

把 `23224` 分别投到官方 ELF 的几个关键桶里看：

| 比较基准 | 占比 |
| --- | ---: |
| 相对 `.debug_*` 总量 `1413392` | `1.64%` |
| 相对 runtime/resource 落盘总量 `116305` | `19.97%` |
| 相对 `LOAD` segment `FileSiz` 总量 `118784` | `19.55%` |
| 相对 debug-stripped 总大小 `232136` | `10.00%` |

结合第 3 节的直接证据，最终应这样理解这 `23224` bytes：

1. 它**仍然更符合** debug / symbol / 其他非装载元数据差异，因为两个 `PT_LOAD` 的 `FileSiz` 已经完全对齐，`.resource_table` 也已经字节级一致。
2. 它**不能再被表述为**“runtime 部分已经完全一样，只差 debug”，因为 `load0`、`.text`、`.data`、`.rodata` 的 hash 仍不同。
3. 更准确的说法是：**文件总大小上的剩余 `23 KB` gap 主要像 debug / 非装载元数据差；同时还存在较小但真实的 runtime 内容差异，这些差异发生在已对齐的 loadable payload 内部。**

## 5. 持久化产物

相关脚本与原始产物：

- `session_bootstrap/scripts/compare_openamp_firmware_delta.py`
- `session_bootstrap/reports/old_fw_compare_20260314/official.sections.txt`
- `session_bootstrap/reports/old_fw_compare_20260314/official.segments.txt`
- `session_bootstrap/reports/old_fw_compare_20260314/release_v1.4.0.sections.txt`
- `session_bootstrap/reports/old_fw_compare_20260314/release_v1.4.0.segments.txt`
- `session_bootstrap/reports/old_fw_compare_20260314/official_vs_release_v1.4.0.summary.json`

为避免后续又回退成“只有 size 推断”的表述，本次额外固化：

- `session_bootstrap/reports/old_fw_compare_20260314/live_segment_hash_evidence_2026-03-14.json`

该 sidecar 明确记录：

- 两个 `PT_LOAD` 的 `FileSiz` 对齐结果
- `.resource_table` 的相同 hash
- `load0` / `.text` / `.data` / `.rodata` 的差异 hash

## 6. 历史说明

早先草稿里提到的 sandbox SSH 失败信息仍然是事实，但它只解释了**为什么最初版本主要写成 size-composition fallback 推断**。  
本次更新后，最终结论已经不再只依赖那条 fallback 链路，而是纳入了后续同一会话取得的直接 ELF 对比证据。
