# OpenAMP Demo Live 双路径状态摘要（2026-03-17）

## 结论

截至 **2026-03-17 05:45 +0800**，最近一轮 demo live 板端验证已经确认：

- **8115 是当前唯一该用的 demo 实例**。
- **current 路径已在 8115 上成功跑通**，并完成真实 reconstruction `300/300`。
- **baseline 路径也已不再 legacy 秒退**，而是通过 signed sideband（`BEGIN / CHUNK / SIGNATURE / COMMIT`）进入真机执行，随后同样完成真实 reconstruction `300/300`。
- 中途提到的 **`cool-har`** 仅是一次本地重打 signed probe 的临时会话，被外部 `SIGTERM` 结束；**没有改变任何板端结论**。

---

## 1. Current live 证据

本地证据目录：`/tmp/openamp_demo_live_5pegf64z`

### Job manifest

- `variant`: `current_reconstruction`
- `job_id`: `3544551784`
- `expected_sha256`: `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`
- `expected_outputs`: `300`
- runner:
  - `bash /home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current --max-inputs 300 --seed 0`

### Wrapper / control plane 结果

- `result = success`
- `JOB_REQ -> JOB_ACK(ALLOW)`
- `job_req fault = NONE`
- `runner_exit_code = 0`

### Runner 结果

- trusted current artifact SHA 对齐：`artifact_sha256_match = true`
- `processed_count = 300`
- `output_count = 300`
- 真实 reconstruction 已完成 `300/300`
- 运行样本中位数：`run_median_ms = 363.687`
- 均值：`run_mean_ms = 364.608`
- 输出形状：`[1, 3, 256, 256]`

---

## 2. Baseline live 证据

本地证据目录：`/tmp/openamp_demo_live_dlqi53n2`

### Job manifest

- `variant`: `baseline`
- `job_id`: `3165109497`
- `admission_mode`: `signed_manifest_v1`
- `expected_sha256`: `85d701db0021c26412c3e5e08a4ca043470aaa01fb2d6792cb3b3b29e93bf849`
- `expected_outputs`: `300`
- runner:
  - `bash ./session_bootstrap/scripts/run_remote_legacy_tvm_compat.sh --variant baseline --max-inputs 300`

### Signed sideband 结果

在 `wrapper_summary.json` 中可见已执行 signed admission 流程；本轮本地收口时确认：

- `SIGNED_ADMISSION_BEGIN` 已 ACK
- `SIGNED_ADMISSION_CHUNK` 已 ACK
- `SIGNED_ADMISSION_SIGNATURE` 已 ACK
- `SIGNED_ADMISSION_COMMIT` 已 ACK
- 随后 `JOB_REQ -> JOB_ACK(ALLOW)` 成立

也就是说，**baseline 已确实不是“秒退未上板”状态，而是通过 signed sideband 成功进入真机执行**。

### Wrapper / runner 结果

- `result = success`
- `runner_exit_code = 0`
- `legacy-compat probe_ok`
- baseline reconstruction 已完成 `300/300`
- 运行样本中位数：`run_median_ms = 1891.9`
- 均值：`run_mean_ms = 1902.622`

### 备注

- baseline 的初始 `STATUS_REQ` 里仍能看到 `last_fault = ARTIFACT_SHA_MISMATCH` 的历史残留状态；
- 但这**没有阻止**本次 signed sideband + `JOB_REQ(ALLOW)` + baseline reconstruction 成功完成；
- 因此在解释这轮结果时，应以**后续 signed sideband 全 ACK + runner 成功退出 + 300/300 完成**为最终判定。

---

## 3. 板子当前在线状态

最新探针：`session_bootstrap/reports/openamp_demo_live_probe_latest.json`

- `reachable = true`
- `remoteproc0 = running`
- `/dev/rpmsg0` 与 `/dev/rpmsg_ctrl0` 存在
- live firmware:
  - path: `/lib/firmware/openamp_core0.elf`
  - sha256: `ef14bc26c4f63ab07fc617cf9bac54abccb44a45520d8acb3af6cb74a82e6007`

这说明当前板子仍处于可继续演示 / 继续验证的在线状态。

---

## 4. 本轮收口边界

本轮新增收口只回答三件事：

1. **8115 是否仍是唯一该用 demo 实例** —— 是。
2. **current 是否真的在板上成功跑通** —— 是，且 `300/300` 完成。
3. **baseline 是否已经通过 signed sideband 进入真机执行** —— 是，且 `300/300` 完成。

本轮**没有**引入新的 benchmark 口径、没有重写旧 OpenAMP signed-admission 证据包，也没有新增板端失败结论。

---

## 5. 建议的后续引用口径

后续若需要在自动续跑、日报或答辩材料中引用 2026-03-17 这轮 demo live 状态，建议统一使用如下口径：

> **8115 当前是唯一有效 demo 实例；current 已在 8115 上成功跑通；baseline 也已通过 signed sideband 进入真机执行；两侧最近 live reconstruction 均完成 300/300；`cool-har` 只是一次本地 probe 会话被外部 SIGTERM，不构成新的板端失败。**
