# Phase 5 `release_v1.4.0` 候选冷启动 + 官方 RPMsg demo 路径验证成功

> 日期：2026-03-14  
> 目标：记录刚完成的真机验证结果，确认 `release_v1.4.0` 候选固件已经通过飞腾板上的“冷启动 + 官方 userspace RPMsg demo 路径”关键门禁。  
> 关联前置：
> - `session_bootstrap/reports/openamp_phase5_release_v1.4.0_live_swap_trial_2026-03-14.md`
> - `session_bootstrap/reports/openamp_phase5_release_v1.4.0_second_live_validation_plan_2026-03-14.md`
> - `session_bootstrap/reports/openamp_phase5_firmware_delta_classification_2026-03-14.md`

## 1. 本轮结论

本轮已确认以下事实同时成立：

1. 板上当前 live 固件就是 `release_v1.4.0` 候选，路径为 `/lib/firmware/openamp_core0.elf`。
2. live 固件身份已确认：
   - `size=1627224`
   - `sha256=685f39b0bcdd4eee31ad81d196cf8dda4ba6e33e2285b32985727bd1465e5dc8`
3. 安装该候选后，飞腾板冷启动成功。
4. 冷启动后 `remoteproc0` 处于 `running`。
5. dmesg 已出现候选固件装载与 channel 建立关键行：
   - `Booting fw image openamp_core0.elf, size 1627224`
   - `remote processor homo_rproc is now up`
   - `creating channel rpmsg-openamp-demo-channel`
6. `/dev/rpmsg_ctrl0` 与 `/dev/rpmsg0` 都已存在。
7. `sudo rpmsg-demo` 已成功 echo，至少打到 `Hello World! No:100`。

因此，当前最精确的工程结论应更新为：

**`release_v1.4.0` 候选固件已经通过飞腾板上的关键真机门禁：安装候选后可冷启动，`remoteproc0` 可拉起，`rpmsg-openamp-demo-channel` 可建立，并且官方 userspace `rpmsg-demo` 路径可在 `/dev/rpmsg_ctrl0` / `/dev/rpmsg0` 上完成真实 echo 往返。**

## 2. 已确认的 live 固件身份

| 项目 | 值 |
| --- | --- |
| live 路径 | `/lib/firmware/openamp_core0.elf` |
| 当前身份 | `release_v1.4.0` candidate |
| 大小 | `1627224` |
| SHA-256 | `685f39b0bcdd4eee31ad81d196cf8dda4ba6e33e2285b32985727bd1465e5dc8` |

这说明本轮通过的不是“板原官方旧固件恢复态”，而是**候选已真实驻留到 live 固件位并经冷启动验证通过**。

## 3. 冷启动后的运行态证据

冷启动后已确认：

- `remoteproc0` 正在运行
- dmesg 关键行包含：

```text
Booting fw image openamp_core0.elf, size 1627224
remote processor homo_rproc is now up
creating channel rpmsg-openamp-demo-channel
```

这比首轮 live swap 试车更强，因为本轮已经跨过“同一轮 stop/start confounder”，直接证明候选在**重启后的实际板级启动链**里仍能完成 remoteproc / RPMsg bring-up。

## 4. 官方 userspace demo 路径证据

本轮还补齐了之前未闭合的用户态证据：

- `/dev/rpmsg_ctrl0` 存在
- `/dev/rpmsg0` 存在
- `sudo rpmsg-demo` 成功 echo，至少到：
  - `Hello World! No:100`

因此，当前已经不仅是“候选能 bring-up”，而是：

**候选在飞腾板上也已经跑通官方 userspace RPMsg demo 路径。**

## 5. 结论边界

这次成功验证的边界必须写清楚：

1. 已验证的是：`release_v1.4.0` 候选在真机上通过了**冷启动 + 官方 RPMsg demo 路径**。
2. 这足以说明它已经通过当前最关键的板级运行门禁。
3. 这**不**等于已证明它与板原始官方固件 byte-identical。
4. `session_bootstrap/reports/openamp_phase5_firmware_delta_classification_2026-03-14.md` 中关于“候选不是 byte-identical runtime match”的结论仍然成立。

所以，当前应采用的正式口径是：

> `release_v1.4.0` 已通过飞腾板上的冷启动与官方 userspace RPMsg demo 真机验证，但这是一条运行门禁结论，不是对板原始官方固件字节级等价性的声明。
