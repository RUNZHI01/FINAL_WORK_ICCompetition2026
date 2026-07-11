# 2026-07-10 IQ 直传交接说明

## 交接结论

当前工作目录是 `FINAL_WORK_ICCompetition2026/FINAL_WORK_ICCompetition2026`，分支为 `feat/restore-248`。Cockpit Desktop 一键测试路径已经恢复到 IQ 直传，链路包含 handwritten TVM 和 big.LITTLE runner。QPSK 已可用并冻结，后续不要改 `USRP292x/RunQpskFileBatchSpoolArq.py`，它只作为回归基线。

当前推荐 profile 是 Docker TX、板端 `/home/user/venv/bin/python`、`REMOTE_RX_RUN_ROOT=/tmp/usrp292x_remote_runs`、bounded RX batch session `ANALOG_RX_BATCH_SESSION_CONTROL=1` + `ANALOG_RX_BATCH_SESSION_MAX_IMAGES=16`、`ANALOG_REMOTE_DECODE_RESPONSE_ONLY_SUMMARY=1`、`ANALOG_PRECREATE_REMOTE_CAPTURE_DIRS=1`。IQ 直传 median 已经低于 TVM，但 300 张 p95 和 max 还有长尾，目标还没完成。

## 2026-07-11 最新进展

09:05 最新有效 Cockpit-button-equivalent 300 张是 `batch-1783730551-300`：`300/300`、fallback `0`。TVM median/p95/max `241.69/244.45/280.68 ms`；IQ total median/p95/max `155.66/274.33/11124.64 ms`；质量 PSNR `37.0445`、SSIM `0.97494`。这轮包含两个新可靠性修复：persistent path-probe 每次请求带唯一 `probe_id`，避免同一 `request_id` 下旧 probe 的 `missing/ok` 响应污染当前判断；远端 capture 目录预创建遇到瞬时 SSH `kex_exchange_identification` 时按 chunk 重试，避免整批直接 fallback。

`batch-1783730551-300` 的结论：可靠性和画质通过，但性能还没最终达标。IQ median 已明显低于 TVM median，正常路径足够快；300 张 p95 仍比 TVM p95 高约 `29.9 ms`，max 被少数长尾拉到 `11.12 s`。主要尾巴包括真实板端 `.npy` 写入 stall（例如 `image_0172 write_npz` 约 `10.94 s`）和 soft-probe 已命中但文件可见/worker 响应仍延迟数秒的样本（例如 `image_0171`、`image_0237`、`image_0158`）。下一步应继续打板端 decoded-output publish/文件可见性和 RX capture 尾部，不要再动 QPSK。

09:12 publish-event 诊断已实现但不进默认 profile。`ANALOG_REMOTE_DECODE_PUBLISH_EVENT=1` 会让板端 decode-server 在 `atomic_savez` 后立即发 `published` 事件，runner 可把该事件当作 soft completion，并带回 partial `decode_timing_ms`。20 张 `batch-1783732029-20` 为 `20/20`、fallback `0`，IQ p95 `236.94 ms` 低于 TVM p95 `259.66 ms`；但 50 张 `batch-1783732287-50` 为 `50/50`、fallback `0`，IQ p95 `363.37 ms` 高于 TVM p95 `247.02 ms`。拆分后主要是 RX capture/wait 尾巴、一次低同步重试，以及弱同步帧真实 board decode `377.78 ms`；publish event 没有解决最终 p95，所以默认继续使用 persistent path-probe soft completion。

08:20 最新结论：decode-worker soft-probe timeout 修复有效，但 RX 侧长尾仍是主瓶颈。`batch-1783726777-300` 为 `300/300`、fallback `0`，TVM median/p95/max `241.78/244.73/277.54 ms`，IQ total median/p95/max `158.38/333.24/10395.30 ms`，PSNR `37.0445`、SSIM `0.97494`。新增 worker timing 显示 `remote_decode_worker_response_wait_ms` max 已从上一轮的 `8694 ms` 降到 `405.91 ms`，说明 soft-completion probe 不再被默认 3 秒探测拖住；剩余 p95/max 主要来自 RX arm/capture 和偶发板端 decode/write。

08:35 三个新 A/B 都不能作为默认 profile。`ANALOG_RX_WAIT_TIMEOUT_SEC=1.0` 已正确透传到每个 round，但 `batch-1783727897-300` 虽然 `300/300`，IQ p95/max 恶化到 `904.15/10540.47 ms`。再叠加短 STOP（`RX_STOP_WAIT_MS=200`、`ANALOG_RX_STOP_DRAIN_TIMEOUT_SEC=0.2`、`ANALOG_RX_STOP_ARM_FAIL_TIMEOUT_SEC=0.0`）的 `batch-1783728580-300` 失败为 `296/300`；去掉 `rx_wait_timeout` 但保留短 STOP 的 `batch-1783728902-300` 仍失败为 `299/300`。短 STOP 会降低部分等待样本，但可能留下 `capture_already_running` 状态残留，所以默认保持稳定的 `RX_STOP_WAIT_MS=8000` / `ANALOG_RX_STOP_DRAIN_TIMEOUT_SEC=8.0`。新代码只保留 `ANALOG_RX_WAIT_TIMEOUT_SEC` 和 `ANALOG_RX_STOP_ARM_FAIL_TIMEOUT_SEC` 的 opt-in 透传。

07:00 最新有效 Cockpit-button-equivalent 300 张是 `batch-1783724189-300`：`300/300`、fallback `0`，TVM `input_count=300`、`processed_count=300`，TVM median/p95/max `241.67/244.62/258.74 ms`，IQ total median/mean/p95/max `156.24/240.41/274.60/7717.03 ms`，PSNR `37.0445`、SSIM `0.97494`。这轮修复了上一轮 TVM 只看到 `299` 个输入的问题，板端实际目录为 `300` 个 `.npy`、无缺号；但 IQ p95 仍高于 TVM p95，不能算最终性能达标。

06:56 最新 20 张健康检查是 `batch-1783724140-20`：`20/20`、fallback `0`，TVM median/p95 `241.22/253.07 ms`，IQ total median/mean/p95/max `158.12/159.47/168.73/231.76 ms`，PSNR `37.0445`、SSIM `0.97494`。这说明短批次正常路径仍明显快于 TVM，且 TVM/输入目录都是完整计数。

本轮关键根因修复：`batch-1783722161-300` 传输 summary 报 `300/300`，但板端目录实际只有 `299` 个 `.npy`，缺 `00000244.npy`，TVM raw log 也从 `00000243.npy` 跳到 `00000245.npy`。原因是 persistent path probe worker 没校验 `request_id`，可能把旧 probe 的 `ok` 响应误配给新文件，导致 runner 把未落盘的远端路径记为 passed。`RemotePathProbeWorker.probe()` 现在要求响应 `request_id` 匹配；本地回归新增 `test_remote_path_probe_worker_ignores_stale_response_for_previous_request`，并通过全量 `USRP292x/test_analog_latent_link.py`。

Windows 原生 backend 的 TX 启动也已修正为默认走 Docker。之前 `OtaTxPersistentServer` 在 Windows 上是 symlink/reparse point，`Path.exists()` 为真但 Git Bash `[[ -x ]]` 会失败，导致 runtime 误走 local bash 并报 `Missing ... OtaTxPersistentServer`。`usrp_runtime._tx_server_uses_docker()` 现在在 Windows 且 Docker 可用时默认选 Docker，除非显式设置 `OPENAMP_USRP_TX_RUNNER=local/host/bash`。

`batch-1783724189-300` 的剩余尾巴：`image 146/147` 是 runner 等 decode worker 响应 `4.99/7.55 s`，但板端 reported decode 只有 `41/48 ms`；`image 171` 是 RX wait/capture `6.24/6.28 s`；`image 153` 发生一次 not-armed 后重试成功。下一步优化应集中在 decode-worker 请求排队/响应流长尾和偶发 RX wait/not-armed，而不是修改 QPSK。

05:34 当前较好的 300 张长测是 `batch-1783719194-300`：`300/300`、fallback `0`，TVM median/p95 `241.00/243.32 ms`，Cockpit API 侧 IQ median/mean/p95/max `158.27/226.27/266.12/10092.53 ms`，stage summary 侧 IQ total p95 `274.86 ms`，PSNR `37.0445`、SSIM `0.97494`。这轮已经包含 repeated soft-completion、Cockpit 默认 `ANALOG_RX_SESSION_CONTROL=1`、`RX_ARM_WAIT_MS=150` 和 not-armed 短 STOP，但 300 张 IQ p95 仍比 TVM p95 高约 `23 ms`，所以目标还没完成。

05:53 重启后默认 profile 的 20 张健康检查是 `batch-1783720370-20`：`20/20`、fallback `0`，IQ total median/mean/p95/max `163.59/178.41/249.12/268.53 ms`，PSNR `37.0445`、SSIM `0.97494`。`rx_server_arm_wait_ms` p95 低于 `1 ms`，说明 `RX_ARM_WAIT_MS=150` 已真正进入 Cockpit 默认路径；短批次能回到约 `250 ms` 显示档，但还需要新 300 张验证。

最新本地修复是 not-armed 恢复链：`RX CAPTURE did not arm before TX` 先走短 `STOP timeout=<ANALOG_RX_STOP_ARM_FAIL_TIMEOUT_SEC>`，如果最后一次 STATUS 仍是 `busy=1`，再追加完整 STOP drain，避免下一轮 ARQ 立即撞 `capture_already_running`。同时 `rx_control_response_busy()` 改为按最后一次 `busy=` 判断，避免 STOP 首行 busy 但后续 STATUS 已 idle 时误判。回归测试已覆盖 `test_process_image_escalates_arm_failure_stop_when_rx_remains_busy` 和 `test_rx_control_response_busy_uses_latest_busy_token`；这项还没跑新硬件 300 张。

06:14 的 300 张 `batch-1783721600-300` 不通过：`299/300`、fallback `1`，IQ p95 恶化，失败帧 image 288 先连续两次 not-armed，最后一次变成 `RX_metadata_error: Unknown error code 0x10`。同时 summary 显示 `rx_post_quantize=True`，与推荐 profile 不一致。已补上 Cockpit 默认 `ANALOG_RX_POST_QUANTIZE=0`，测试 `test_board_access_usrp_iq_defaults_fast_rx_arm_status_timeout` 覆盖；这轮 300 不作为有效性能结论。

两个 A/B 结论保持不变：`ANALOG_RX_BATCH_SESSION_MAX_IMAGES=64` 的 300 张虽然 all-pass，但 p95/max 更差，拒绝；`ANALOG_REMOTE_DECODE_SOFT_COMPLETE_SEC=0.02` 那轮因 SSH kex/worker 启动失败，不是有效性能结论。当前默认 soft-completion 保持 `0.05`，配合 persistent probe repeated check 使用；不要把 `0.02` 当成结论。

03:52 最新 Cockpit-button-equivalent 300 张是 `batch-1783713085-300`。配置为 Docker SSH/TX、板端 `/home/user/venv/bin/python`、`REMOTE_RX_RUN_ROOT=/tmp/usrp292x_remote_runs`、`ANALOG_RX_TAIL_SEC=0.040`、`ANALOG_REMOTE_DECODED_FORMAT=npy`、`ANALOG_RX_SC16_MMAP=1`、`ANALOG_RX_CLIPPING_DECIMATION=8`、bounded RX batch session `16`、minimal decode response、response-only summary、预创建 capture dirs。结果为 `300/300`、fallback `0`；TVM median/mean/p95/max `241.45/242.16/244.54/261.01 ms`；IQ total median/mean/p95/max `155.23/240.64/271.00/9773.22 ms`；PSNR `37.0445`、SSIM `0.97494`。这说明 visible 重建速度已经回到约 `240-250 ms` 档，IQ normal path 明显快于 TVM，但 300 张 p95 仍被少数 `.npy` 写入/board decode/RX capture 长尾拉到 TVM p95 之上，不能算最终 p95 达标。

这轮 `.npy` 数据面是有效的：`batch_spool_summary.json` 的 `remote_received_latent_npz_files` 全部是 `.npy`，`read_sc16` p95 `2.89 ms`，decoded-output write p95 `1.42 ms`。仍有极端尾巴：`image 111` 的 board-reported write 约 `4517 ms`，`image 244` runner decode wait 约 `9682 ms`，`image 226` RX capture 约 `1594 ms`。下一步优化应继续打长尾，而不是动 QPSK。

Cockpit 对比图片不更新的问题已修。根因是 running 阶段的 manifest 预填了 `.npz` 路径，terminal wrapper summary 没把最终 `iq_remote_decode_manifest` 带回 `/api/batch-state`，导致最终状态保留旧 `.npz`。现在 `usrp_runtime.py` 在 IQ-direct terminal snapshot 中携带最终 remote decode manifest，`server.py` 支持 `.npy` index 并让 summary files 覆盖 manifest defaults。重启后 5 张验证 `batch-1783713778-5` 已返回 5 个 `done`，路径全是 `/home/user/cockpit_usrp_rx/.../*.npy`，质量仍为 PSNR `37.0445`、SSIM `0.97494`。

质量验收口径确认：不是逐像素 bit-exact。当前“测试通过”的画质指标是发送/原始图与 TVM 重建图之间的 PSNR/SSIM；当前稳定值为 PSNR 约 `37.04 dB`、SSIM 约 `0.97494`。按 `0-255` 像素反推，PSNR `37.0445 dB` 约等于 MSE `12.84`、RMSE `3.58` 灰阶/通道。JSCC + TVM 重建链路是有损和数值近似的，逐像素完全相等不符合预期；若需要定位退化，应看 MSE/PSNR/SSIM 或差分图。

本轮新增的有效改动是预创建远端 capture 目录。`batch-1783704920-300` 的 not-armed 证据显示部分 RX job 有多秒 `wall_sec`，但 `drain_sec`、`stream_cmd_sec`、`receive_sec` 都接近零，瓶颈不像 UHD 收样本，而像每张图 capture 前的远端目录创建或文件打开。`RunAnalogLatentBatch.py` 现在在第一张图 `CAPTURE` 前一次性创建整批远端目录，默认由 `ANALOG_PRECREATE_REMOTE_CAPTURE_DIRS=1` 打开；server 和 Docker wrappers 已透传 `ANALOG_PRECREATE_REMOTE_CAPTURE_DIRS`、`ANALOG_PRECREATE_REMOTE_CAPTURE_DIRS_CHUNK`。

最新 50 张 Cockpit-equivalent smoke 是 `batch-1783706692-50`：`50/50`、fallback `0`、`remote_capture_dirs_precreated=true`。TVM median/p95/max 为 `240.74/243.98/256.89 ms`，IQ median/p95/max 为 `148.70/207.52/301.42 ms`，PSNR `37.0445`、SSIM `0.97494`。这是目前短批次最好的证据：IQ p95 比 TVM p95 低约 `36 ms`。

最新 300 张 gate 是 `batch-1783707048-300`：`300/300`、fallback `0`、`remote_capture_dirs_precreated=true`。TVM median/p95/max 为 `241.49/244.48/287.26 ms`，IQ median/p95/max 为 `149.14/279.76/3831.98 ms`，PSNR `37.0445`、SSIM `0.97494`，stage records `303`。这说明可靠性和一类目录/`.npz` 写入长尾已改善，但仍不是最终性能成功：300 张 IQ p95 仍高于 TVM p95。剩余主要尾巴是板端 `read_sc16` 偶发秒级卡顿、RX control/capture 响应尾巴，以及少量恢复重试。

两个最新 A/B 已拒绝：把 capture root 改成 `/dev/shm/usrp292x_remote_runs` 的 50 张 `batch-1783707439-50` 虽然 `50/50`，但 IQ p95 恶化到 `264.79 ms`；把 `ANALOG_RX_BATCH_SESSION_MAX_IMAGES` 缩到 `8` 的 50 张 `batch-1783707616-50` 也 `50/50`，但 IQ median/p95/max 恶化到 `175.06/363.43/655.65 ms`。保持 `/tmp` 和窗口 `16`。

最新同代码 no-batch 300 张 A/B 是 `batch-1783691290-300`：`300/300`、fallback `0`。TVM median/p95/max 为 `241.84/253.13/265.85 ms`；IQ median/p95/max 为 `172.71/301.74/8598.55 ms`。这说明正常路径速度够了，剩下问题集中在 RX arm/wait/control stall、runner-side decode response wait，以及少数 `/home` `.npz` 写入 stall。

最新 50 张 Cockpit-equivalent 复测是 `batch-1783694251-50`：`50/50`、fallback `0`。TVM median/p95/max 为 `241.53/247.05/257.82 ms`；IQ median/p95/max 为 `217.35/520.90/1306.86 ms`。这轮新增了更细的长尾拆分：`rx_arm_control_overhead_ms` median/p95/max `21.04/45.41/1159.40 ms`，`rx_wait_response_overhead_ms` `1.36/125.83/266.76 ms`，`remote_decode_response_overhead_ms` `16.45/128.18/395.78 ms`，而 `rx_server_receive_ms` 稳定在 `63.61/63.64/64.03 ms`。结论是服务端实际收样本很稳定，长尾主要在 runner 到 RX 控制响应、WAIT 响应和 decode worker 响应边界。

最新拆分验证是 `batch-1783695696-50`：`50/50`、fallback `0`。TVM median/p95/max 为 `242.85/259.12/370.31 ms`；IQ median/p95/max 为 `173.20/335.37/392.09 ms`。新增 `rx_session_open_ms` median/p95/max `17.52/33.38/38.52 ms`，`rx_capture_command_ms` `9.03/17.88/101.49 ms`。这说明本轮 RX WAIT 响应长尾已不明显，下一步更该看 decode worker 响应/板端 decode 尾巴，同时保留对偶发 CAPTURE command 响应尖峰的观测。

历史单因素 A/B 中，单独打开 `ANALOG_REMOTE_DECODE_RESPONSE_ONLY_SUMMARY=1` 不推荐默认打开。复测 `batch-1783696115-50` 为 `50/50`、fallback `0`，IQ median/p95/max `171.53/334.85/1166.81 ms`；`remote_decode_response_overhead_ms` 只改善到 `14.77/113.42/126.89 ms`，但 `rx_session_open_ms` max 达到 `1015.27 ms`，没有降低整体 p95/max。7/11 后它只作为当前组合 profile 的一部分使用。

历史单因素 A/B 中，bounded RX batch session 尚未单独进默认 profile。`ANALOG_RX_BATCH_SESSION_CONTROL=1` 加 `ANALOG_RX_BATCH_SESSION_MAX_IMAGES=16` 的复测 `batch-1783696822-50` 为 `50/50`、fallback `0`；TVM median/p95/max `241.94/246.45/275.62 ms`，IQ median/p95/max `154.18/326.68/333.40 ms`。这证明分窗口复用能把 median 压低，但当时 50 张 p95 仍高于 TVM，且尚未通过 300 张 gate。7/11 后窗口 `16` 只在当前组合 profile 中保留。

7/10 阶段最强组合候选是 bounded RX batch session 加 response-only-summary，但还不是最终目标。50 张 `batch-1783697847-50` 为 `50/50`、fallback `0`，TVM median/p95/max `239.25/243.52/257.93 ms`，IQ `153.55/237.32/286.80 ms`，首次让 50 张 IQ p95 低于 TVM p95。300 张 `batch-1783697942-300` 为 `300/300`、fallback `0`，TVM `239.99/243.44/296.38 ms`，IQ `153.37/269.84/8378.85 ms`，stage records `303`，wall `75.06 s`。这比 no-batch 300 张 p95 `301.74 ms` 和 batch-session-only p95 `321.68 ms` 都好，但 p95 仍高于 TVM，max 还有重试/worker 响应长尾。

`ANALOG_REMOTE_DECODE_WORKER_PREFIX=taskset -c 2` 已做成 opt-in 诊断开关，不进默认 profile。50 张 `batch-1783701414-50` 为 `50/50`、fallback `0`，IQ median/p95/max `154.96/177.68/254.72 ms`，质量 PSNR `37.0445`、SSIM `0.97494`；但 300 张 `batch-1783701712-300` 虽然 `300/300`、fallback `0`，IQ median/p95/max 是 `151.66/275.68/8884.26 ms`，TVM median/p95 `239.15/242.35 ms`。结论：taskset 对 50 张 p95 有帮助，但 300 张没有超过 prior best `269.84 ms`，也没有让 IQ p95 低于 TVM p95。

`ANALOG_REMOTE_DECODE_SOFT_COMPLETE_SEC=0.14` 不推荐。带 output-only soft completion 的 50 张 `batch-1783698593-50` 虽然 `50/50`、fallback `0`，但 IQ median/p95/max 恶化到 `169.39/365.51/2122.73 ms`，`soft_count=0`。日志显示 outlier 发生时 NPZ 在 soft timeout 时尚未可见，问题更像 worker 请求排队/调度延迟，而不是“文件已写好但 stdout 晚到”。

taskset profile 上复测 soft-completion 的 `batch-1783702255-300` 不通过：transport `298/300`，fail `2`，`soft_count=0`。失败来自 RX metadata / not-armed 链，不是 TVM 或图像质量；不要把这组 p95 当作有效性能结论。

最新补丁是 RX arm 状态恢复，不是性能 profile 切换。`wait_for_rx_capture_armed` 现在允许 shared/session `STATUS` 在“命令已发送但 session 超时”后回退到 direct `STATUS`，避免 stale socket 把已经启动的 RX 误判成 not-armed。本地回归测试为 `test_wait_for_rx_capture_armed_falls_back_after_sent_session_status_timeout`。

补丁后的 50 张 smoke `batch-1783703143-50` 为 `50/50`、fallback `0`，TVM median/p95/max `240.75/246.59/262.73 ms`，IQ median/p95/max `155.08/224.53/306.85 ms`，质量 PSNR `37.0445`、SSIM `0.97494`。300 张 `batch-1783703433-300` 为 `300/300`、fallback `0`，TVM `240.23/243.72/259.31 ms`，IQ `150.61/285.72/8847.20 ms`，stage records `302`，PSNR `37.0445`、SSIM `0.97494`。结论：可靠性通过，质量不变，但 IQ p95 没超过 prior best `269.84 ms`，也没低于 TVM p95，所以不能作为最终性能突破。

`batch-1783703433-300` 的长尾归因：image 177/285 是板端 `.npz` 写入真实卡顿，`write_npz` 最高 `5526.98 ms`；image 257/273 是 runner 等 decode worker 响应卡顿，但板端 reported decode 只有约 `39-45 ms`；image 181 是 `RX CAPTURE did not arm before TX` 后 STOP drain 再重试成功。下一步仍应优先处理 decoded-output 写入/worker 响应长尾和 RX not-armed 恢复，而不是继续动 QPSK。

tmpfs decoded-output 又复测了一轮，仍不进默认 profile。`REMOTE_USRP_RX_DIR=/dev/shm/cockpit_usrp_rx` 的 50 张 `batch-1783704246-50` 为 `50/50`、fallback `0`，`write_npz` p95/max 压到 `2.55/2.61 ms`，但 IQ median/p95/max 恶化为 `153.18/508.96/567.11 ms`，尾巴转移到 RX capture/wait。tmpfs 只保留为 I/O 诊断。

summaryless soft-completion 的逻辑缺口已修：response-only-summary 请求不再要求远端 `decode_summary.json` 存在，server 启动也会透传 `ANALOG_REMOTE_DECODE_RESPONSE_ONLY_SUMMARY` 和 `ANALOG_REMOTE_DECODE_SOFT_COMPLETE_SEC`。50 张 `batch-1783704792-50` 为 `50/50`、fallback `0`，TVM `240.29/246.72/258.10 ms`，IQ `154.63/219.79/278.24 ms`，质量不变；但没有 soft 命中。300 张 `batch-1783704920-300` 命中 `5` 次 soft completion，却因 RX WAIT/not-armed 链失败为 `299/300`、fallback `1`。通过帧 IQ p95 `247.85 ms` 不能作为有效结论；当时默认仍保持 `0`，7/11 后当前候选默认改为 `0.05` 并使用 persistent probe repeated check。

`ANALOG_RX_BATCH_SESSION_MAX_IMAGES=0` 和 `ANALOG_PRECONNECT_RX_CAPTURE_CONTROL=1` 都已拒绝。整批共用 RX session 的 50 张 `batch-1783700070-50` 虽然 `50/50`，但 IQ median/p95/max 恶化到 `185.69/571.83/1217.93 ms`，长尾来自 `rx_session_open` 和 RX control。RX CAPTURE preconnect 的 50 张 `batch-1783700726-50` 也 `50/50`，但 IQ p95 仍是 `270.40 ms`，比 no-preconnect 的 `237.32 ms` 差；它只把瓶颈从 RX control 转移到了板端 decode。

Cockpit Desktop 已跟上主链路参数和主要指标：一键路径仍是 IQ direct、Docker TX、板端 venv RX、handwritten TVM、big.LITTLE；`/api/batch-state` 已返回 `transport_benchmark`、`inference_benchmark`、`iq_stage_benchmark`。本轮补了 `/api/crypto-status` 的 `batch_iq_stage_benchmark` 透出，并在 Cockpit benchmark 表中显示 RX arm、RX 连接、CAPTURE 命令、RX capture/wait、RX arm 控制长尾、WAIT 响应长尾和 decode 响应长尾，避免这些指标只存在于 JSON 里。

## 当前代码和提交

本轮提交前最近三次关键提交：

- `f05b072 docs: record iq response-only summary ab`
- `fa323b6 diagnostics: split iq rx arm latency`
- `da8e90d diagnostics: expose iq rx tail metrics`

`ANALOG_RX_SESSION_CONTROL=1` + `ANALOG_RX_BATCH_SESSION_CONTROL=1` + `ANALOG_RX_BATCH_SESSION_MAX_IMAGES=16` + `ANALOG_REMOTE_DECODE_RESPONSE_MODE=minimal` + `ANALOG_REMOTE_DECODE_RESPONSE_ONLY_SUMMARY=1` + `ANALOG_PRECREATE_REMOTE_CAPTURE_DIRS=1` + `ANALOG_REMOTE_DECODED_FORMAT=npy` + `ANALOG_RX_SC16_MMAP=1` + `ANALOG_RX_CLIPPING_DECIMATION=8` + `ANALOG_RX_POST_QUANTIZE=0` + `ANALOG_REMOTE_DECODE_SOFT_COMPLETE_SEC=0.05` 是当前 7/11 live 候选基线。它已经通过 300 张 all-pass，并让 IQ median 到 `158 ms` 左右；但最新有效 300 张 IQ p95 仍在 `266-275 ms` 区间，高于 TVM p95 `243 ms` 左右，所以不是最终达标结论。`0.02` soft-completion A/B 因 SSH kex/worker 启动失败无效，不能推广。

`ANALOG_RX_BATCH_SESSION_MAX_IMAGES` 只在 `ANALOG_RX_BATCH_SESSION_CONTROL=1` 时生效。`0` 表示整批共用同一个 RX session，已因 `batch-1783700070-50` p95 `571.83 ms` 拒绝；`8` 也已因 `batch-1783707616-50` p95 `363.43 ms` 拒绝。当前保持窗口 `16`。

图像质量验收口径是原图/发送图和 TVM 重建图的 PSNR、SSIM，不是逐像素完全相等。历史 300 张质量报告 `quality_metrics_20260312_pytorch_vs_tvm_current` 是按 PNG 像素数组比较参考重建和 TVM current 重建，形状 `256x256x3`，无裁剪；PSNR mean/median `35.694/35.730 dB`，SSIM mean/median `0.972836/0.972942`，`perfect_match_count=0`。当前 Cockpit/IQ/TVM 通过批次反复给出 PSNR `37.0445 dB`、SSIM `0.97494`，输出形状为 `1x3x256x256`。JSCC/TVM 重建是有损链路，像素差异正常；如需定位画质退化，应补算 MSE/PSNR/SSIM 或差分图，而不是要求 bit-exact。

`PERSISTENT_RX_TX_DELAY=0.005` 已拒绝。50 张 `batch-1783691806-50` 虽然 `50/50`、fallback `0`，但 IQ median/p95 恶化到 `202.47/306.92 ms`。继续保持 `PERSISTENT_RX_TX_DELAY=0`。

WAIT timeout cleanup 的计时记录已修复。之前内层 STOP 成功后，外层异常记录可能再次解析 WAIT 错误文本里的 `stop_cmd_sec=0` / `stop_wait_sec=0`，把真实 STOP 计时覆盖掉。现在这类记录会保留 `rx_stop_after_wait_timeout.log` 里的真实 `rx_server_stop_*` 字段，便于下一轮 300 张长尾归因。

`ANALOG_REMOTE_DECODE_RESPONSE_ONLY_SUMMARY=1` 已进入当前推荐基线。单独打开它不能解决长尾，但和 bounded session、目录预创建一起使用时能减少无用响应体/文件等待；完整 evidence 以 `batch-1783706692-50` 和 `batch-1783707048-300` 为准。

## IQ 直传探索路径

已经证明有用、留在推荐 profile 的路径：

- IQ 直传替代 QPSK 数据面：QPSK 参考批次约 `2961.78 ms/image`，IQ 直传正常 median 已到 `165-175 ms` 区间。
- Docker TX + 板端 `/home/user/venv/bin/python`：解决容器迁移后环境不一致的问题，Cockpit 一键路径重新回到 handwritten TVM + big.LITTLE。
- `ANALOG_REMOTE_DECODE_RESPONSE_MODE=minimal`：减少 persistent worker stdout 响应体，保留板端完整 summary 文件。
- `ANALOG_RX_SESSION_CONTROL=1`：同一连接发送 CAPTURE/WAIT，比单独 CAPTURE preconnect 更适合作为默认控制路径。
- `ANALOG_RX_BATCH_SESSION_CONTROL=1` + `ANALOG_RX_BATCH_SESSION_MAX_IMAGES=16`：当前推荐的 bounded RX session 复用窗口，能明显降低 normal-path median；窗口 `0` 和 `8` 都已拒绝。
- `ANALOG_REMOTE_DECODE_RESPONSE_ONLY_SUMMARY=1` + `ANALOG_REMOTE_DECODE_SOFT_COMPLETE_SEC=0.05`：当前推荐组合的一部分，减少 persistent worker 响应面，并在 worker stdout 偶发滞后时用 persistent probe repeated check 提前确认远端 `.npy` 已可用。
- `ANALOG_PRECREATE_REMOTE_CAPTURE_DIRS=1`：当前最新有效改动，把远端目录创建移出 per-image RX hot path，降低目录/写入类尾巴。
- `PERSISTENT_RX_TX_DELAY=0`：RX arm barrier 已经存在，保留固定 TX 延迟会拖慢正常路径。
- `ANALOG_RX_TAIL_SEC=0.05`：当前可靠下限；短 tail 会引入 no-sync 或 p95 恶化。
- `ANALOG_RX_POST_QUANTIZE=0`、fast-first sync、`ANALOG_PRECONNECT_CONTROL=1`、`RX_ARM_WAIT_MS=150`：保留在稳定 profile 中。
- STOP/drain cleanup、session-before-STOP、not-armed 短 STOP 后条件完整 drain、decode timing 和 STOP timing 记录：主要提升可靠性和可观测性，是继续定位 p95 的基础。

已经试过但不进默认的路径：

- no-batch RX session：现在不是推荐基线；bounded session + response-only-summary + precreate 的 300 张 p95 更好。
- `ANALOG_RX_BATCH_SESSION_MAX_IMAGES=0`：50 张 `batch-1783700070-50` p95 `571.83 ms`，整批复用会放大 session open/arm 抖动。
- `ANALOG_RX_BATCH_SESSION_MAX_IMAGES=8`：50 张 `batch-1783707616-50` IQ p95 `363.43 ms`，差于窗口 `16`。
- `ANALOG_PRECONNECT_RX_CAPTURE_CONTROL=1`：50 张 `batch-1783700726-50` p95 `270.40 ms`，RX control 变稳但板端 decode 尾巴变成主因，整体不如 no-preconnect。
- `ANALOG_REMOTE_DECODE_SOFT_COMPLETE_SEC=0.14`：50 张 `batch-1783698593-50` p95 `365.51 ms`，且没有 soft completion 命中。
- `PERSISTENT_RX_TX_DELAY=0.005`：50 张 p95 恶化到 `306.92 ms`。
- 早期单独 `ANALOG_RX_TAIL_SEC=0.04/0.045` 实验：出现 no-sync retry 或 p95 大幅恶化。7/11 的 `.npy + mmap + bounded session + minimal response` 组合已用 `0.040` 重新通过 300 张，但它仍是当前候选而非最终 p95 达标 profile。
- depth-2 overlap、streaming TVM overlap：会放大 RX/worker contention，不作为默认。
- tmpfs capture root、tmpfs decoded output、早期单独 `.npy` decoded output、旧的一次性 SSH soft completion、decode-worker timeout/restart、burst-miss retry、low-sync early retry、no-poll：有诊断价值，但没有稳定改善 300 张 p95/max。当前 `.npy` 和 `0.05` soft-completion 只随 mmap/response-minimal/bounded-session/persistent-probe 组合使用。

## 推荐运行配置

保持下面这些环境变量，不要把诊断开关混进默认 profile：

```text
OPENAMP_SSH_RUNNER=docker
OPENAMP_SSH_DOCKER_IMAGE=iccomp-usrp-tx:latest
OPENAMP_USRP_TX_RUNNER=docker
OPENAMP_USRP_TX_DOCKER_IMAGE=iccomp-usrp-tx:latest
OPENAMP_USRP_TX_DOCKER_MOUNT_TARGET=/host_workspace
MLKEM_TRANSPORT_MODE=usrp
MLKEM_USRP_MODE=ota
OPENAMP_DEMO_LINK_MODE=iq-direct
JSCC_LINK_MODE=iq-direct
OPENAMP_DEMO_INPUT_SOURCE_MODE=usrp
OPENAMP_DEMO_IMAGE_TO_LATENT_ENABLED=0
REMOTE_USRP_DECODE_PYTHON=/home/user/venv/bin/python
OPENAMP_DEMO_REMOTE_DECODE_PYTHON=/home/user/venv/bin/python
ANALOG_REMOTE_DECODE_WORKER=1
ANALOG_REMOTE_DECODE_RESULT_MODE=remote-dir
ANALOG_REMOTE_DECODE_RESPONSE_MODE=minimal
ANALOG_REMOTE_DECODE_RESPONSE_ONLY_SUMMARY=1
ANALOG_REMOTE_DECODE_SOFT_COMPLETE_SEC=0.05
ANALOG_REMOTE_DECODED_FORMAT=npy
ANALOG_REMOTE_CLEANUP_MODE=skip
REMOTE_RX_RUN_ROOT=/tmp/usrp292x_remote_runs
ANALOG_RX_TAIL_SEC=0.040
ANALOG_RX_POST_QUANTIZE=0
ANALOG_RX_SC16_MMAP=1
ANALOG_RX_CLIPPING_DECIMATION=8
RX_ARM_WAIT_MS=150
RX_STOP_WAIT_MS=8000
ANALOG_RX_STOP_DRAIN_TIMEOUT_SEC=8.0
ANALOG_RX_WAIT_TIMEOUT_SEC=1.0
ANALOG_RX_WAIT_CONTROL_TIMEOUT_MARGIN_SEC=1.0
ANALOG_RX_ARM_STATUS_TIMEOUT_SEC=0.5
ANALOG_RX_ARM_STATUS_POLL_SEC=0.025
ANALOG_PIPELINE_DEPTH=1
ANALOG_PRECONNECT_CONTROL=1
ANALOG_RX_SESSION_CONTROL=1
ANALOG_PRECONNECT_RX_CAPTURE_CONTROL=0
ANALOG_RX_BATCH_SESSION_CONTROL=1
ANALOG_RX_BATCH_SESSION_MAX_IMAGES=16
ANALOG_PRECREATE_REMOTE_CAPTURE_DIRS=1
ANALOG_PRECREATE_REMOTE_CAPTURE_DIRS_CHUNK=80
PERSISTENT_RX_TX_DELAY=0
OPENAMP_TVM_BATCH_RUNNER=biglittle
OPENAMP_DEMO_TVM_BATCH_RUNNER=biglittle
OPENAMP_DEMO_USRP_SHUTDOWN_AFTER_TRANSPORT=0
```

不要默认打开 streaming TVM、depth-2 overlap、tmpfs capture root、tmpfs decoded output、旧的一次性 SSH soft completion、burst-miss retry、low-sync early retry、worker timeout/restart 或窗口 `0/8/64` 的 batch RX session。这些都有诊断价值，但目前没有通过 300 张 p95 gate。当前候选只保留 `ANALOG_REMOTE_DECODE_SOFT_COMPLETE_SEC=0.05` + persistent probe repeated check。

## 重启流程

Windows 侧 bash/SSH 辅助命令优先用 Docker，Docker 不可用时用 Windows Git Bash，不要用 WSL。板端手动执行 Python 前先激活虚拟环境：

```bash
source /home/user/venv/bin/activate
```

重启前先全停，避免继承上一轮实验状态：

```powershell
try {
  Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8079/api/usrp-control/stop `
    -ContentType 'application/json' -Body '{}' -TimeoutSec 60 | Out-Null
} catch {}

Get-CimInstance Win32_Process -Filter "name='python.exe'" |
  Where-Object { $_.CommandLine -like '*openamp_control_plane_demo/server.py*8079*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

启动 backend 后，先写入本地板端访问配置，再启动 USRP。账号、密码、host、port 只放本机运行环境或 Cockpit，不要提交进仓库。

Cockpit 测试按钮等价接口：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8079/api/usrp-control/start `
  -ContentType 'application/json' -Body '{}'

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8079/api/run-inference-batch `
  -ContentType 'application/json' -Body '{"count":50,"allow_preflight_degraded":true}'

Invoke-RestMethod -Uri http://127.0.0.1:8079/api/batch-state | ConvertTo-Json -Depth 8
```

不要把完整 `/api/system-status` 输出贴进文档或提交记录，里面可能含本机配置和敏感字段。

## 认证和 ML-KEM

当前性能基线里 runtime security channel 不在 per-image hot path。认证和 ML-KEM 不要和 IQ p95 优化混在同一轮里做。正确做法是先用 security-off profile 固定性能基线，再单独开启 security channel 跑 20 张和 300 张，对比 session-level 开销。如果 security-on 开销超过约 `5%`，性能基线继续保持 security-off，并在文档里记录差值。

## 下一步优化入口

优先级如下：

1. 处理 RX arm/wait/control stall。batch session 和 bounded batch session 都能降低 median，但没有通过 p95 gate，说明单纯复用连接不是最终解。
2. 处理 runner-side decode response wait。多次长尾里板端 reported decode 只有几十毫秒，但 runner 等响应等了几秒。
3. 复测 decoded output placement/format。tmpfs 能压低 `write_npz`，但之前没有改善 300 张 p95，只能作为诊断项。

每次改动前后都要确认 QPSK 没被动到：

```powershell
git diff -- USRP292x\RunQpskFileBatchSpoolArq.py
```

预期输出为空。

## 提交前验证

本地代码验证：

```powershell
python -m pytest USRP292x/test_analog_latent_link.py -q
python -m pytest docker/test_demo_scripts.py -q
python -m pytest Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py::ServerMainTest::test_demo_startup_env_overrides_keeps_usrp_runtime_env -q
python -m py_compile USRP292x\RunAnalogLatentBatch.py Semantic-Communication\session_bootstrap\demo\openamp_control_plane_demo\server.py
git diff --check
git diff -- USRP292x\RunQpskFileBatchSpoolArq.py
```

最近一次已完成验证：`python -m pytest USRP292x/test_analog_latent_link.py -q` 为 `109 passed`；`python -m pytest docker/test_demo_scripts.py -q` 为 `8 passed`；`python -m pytest Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py::ServerMainTest::test_demo_startup_env_overrides_keeps_usrp_runtime_env -q` 为 `1 passed`；`python -m py_compile USRP292x\RunAnalogLatentBatch.py Semantic-Communication\session_bootstrap\demo\openamp_control_plane_demo\server.py` 通过；`git diff --check` 只剩 CRLF/LF 提示；`git diff -- USRP292x\RunQpskFileBatchSpoolArq.py` 为空。

## 重要文件

- `plan_20260710.md`: 完整 IQ 优化计划和实验记录。
- `handoff_20260710_current_zh.md`: 更长的历史交接。
- `handoff_20260710_final_zh.md`: 上一版稳定交接。
- `USRP292x/RunAnalogLatentBatch.py`: IQ 直传 runner。
- `USRP292x/AnalogLatentLink.py`: IQ decode 和阶段计时。
- `USRP292x/test_analog_latent_link.py`: 当前最重要的单元测试。

生成的 report、raw log、`local_logs`、`analog_latent_runs` 不要混进 git。只把 batch id、关键指标和结论写进文档。
