# 手写线与 ACL 复测异常说明（非 OpenAMP 板状态）

- 日期: 2026-04-04
- 范围: 记录本 session 下手写线与 ACL 集成线复测的异常背景，并给出保守结论
- 结论级别: 会话归档说明，不作为项目最终公平对比结论

## 一、问题定义

本次需要重点关注的两条线是：

- `Handwritten final`
- `ACL integration line`

当前这两条线的效果都存在可疑性，主要原因不是单纯由代码差异决定，而是被当前板端状态混淆：**OpenAMP 未启用，因此多出 1 个 CPU 核在线**。在这个前提下，当前结果只能视为“同一异常板状态下的复测记录”，不能直接提升为项目叙事中的最终公平对比结论。

## 二、本 session 已验证的板端状态

本 session 已确认的板端观测如下：

- CPU online: `0-3`
- nproc: `4`
- MemAvailable: 约 `1526 MB`

这与原本希望控制的 OpenAMP / CPU topology 边界不一致，因此该 session 的所有对比结果都带有同一板状态前提。

## 三、同板状态下的最新复测结果

以下为本次同板状态下最新复测结果，原样记录：

- Trusted Current: payload 124.808 ms, reconstruction 236.616 ms, sha 6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1
- Handwritten final: payload 152.779 ms, reconstruction 257.251 ms, sha 2aa25d2ba2ea3f76533b6c40809521e19ade5c8798160b369c3527834e0ae216
- ACL integration line: payload 161.003 ms, reconstruction 264.927 ms, sha 602371c27826d44a39bbfc2eb01c45e7d866d4f968c8cb2ddc4dd91c354fedba

在这个同板状态下，`Trusted Current` 仍然是三者中最稳妥的参考线；`Handwritten final` 与 `ACL integration line` 目前只能算候选线，且效果解释受板状态混淆。

## 四、ACL 线异常来源与修正

本 session 还确认了一个关键事实：**更早的一次 ACL rerun 失败，并不是 ACL 线本身必然失效，而是远端归档被错误产物污染了**。当时远端 archive 中混入了错误的 artifact：

- 错误 sha: `599df2068600cb945ec3b91915186dc223b4243a88bd7c757b8226b2eb2e4542`

在重新上传正确产物之后：

- 正确 sha: `602371c27826d44a39bbfc2eb01c45e7d866d4f968c8cb2ddc4dd91c354fedba`

ACL 复测才重新稳定。因此，早前 ACL rerun 的失败不能直接当作 ACL 线路真实性能结论，而应视为一次远端归档污染事件。

## 五、手写线异常慢数据的处理

`Handwritten final` 在线路稳定前曾短暂出现异常慢结果：

- payload `311.875 ms`
- reconstruction `512.298 ms`

结合当时 SSH / 板状态后续恢复稳定这一事实，这组数字应被视为**异常 session 数据**，而不是 `Handwritten final` 的规范结论值。当前更应采用同板状态稳定后的复测结果，即：

- Handwritten final: payload 152.779 ms, reconstruction 257.251 ms, sha 2aa25d2ba2ea3f76533b6c40809521e19ade5c8798160b369c3527834e0ae216

## 六、保守结论

在当前 **非 OpenAMP** 的板端状态下，由于 CPU online 为 `0-3`、`nproc=4`，手写线和 ACL 集成线的结果都受到了 CPU topology 边界变化的混淆。即使本次同板状态复测已经得到一组相对稳定的数据，也**不应将这组结果提升为项目叙事中的最终公平比较结论**。

当前更稳妥的表达应是：

- `Trusted Current` 可继续作为当前 release baseline
- `Handwritten final` 与 `ACL integration line` 只应视为 candidate lines
- 这两条线是否真正优劣，需要回到目标中的 OpenAMP / CPU topology 边界下重新复测后再定论

## 七、建议的下一步

- 在预期的 OpenAMP / CPU topology 边界下重新完整复测
- 继续将 `Trusted Current` 作为 release baseline
- 将 `Handwritten final` 和 `ACL integration line` 暂时归类为 candidate lines，而不是最终结论线

