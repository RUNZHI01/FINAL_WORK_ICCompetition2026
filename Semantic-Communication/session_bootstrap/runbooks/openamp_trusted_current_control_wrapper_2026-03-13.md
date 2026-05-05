# trusted current 控制面 wrapper 接线手册

> 日期：2026-03-13  
> 目标：在不改写现有 trusted current 推理数据面的前提下，把 OpenAMP / RPMsg 控制面包裹到现有 runner 外层。  
> 约束：只包裹控制面，不重写 `current_real_reconstruction.py`、`run_remote_current_real_reconstruction.sh`、`run_inference_benchmark.sh` 的推理逻辑。

## 1. 现有可直接包裹的入口

- `session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current`
  - 当前真实端到端 trusted current 入口。
- `session_bootstrap/scripts/current_real_reconstruction.py`
  - 被远端 shell wrapper 调起的数据面 Python 执行器。
- `session_bootstrap/scripts/run_inference_benchmark.sh --env <env>`
  - baseline/current 成对 benchmark 总入口。
- `INFERENCE_CURRENT_EXPECTED_SHA256`
  - 现有 trusted artifact guard，不应被 wrapper 替换，只应被控制面透传与复用。

## 2. 本轮新增骨架

- `session_bootstrap/scripts/openamp_control_wrapper.py`
  - 作用：在 runner 执行前后发出 `STATUS_REQ`、`JOB_REQ`、`HEARTBEAT`、`JOB_DONE` 等控制事件。
  - 默认 `--transport none`，只落本地证据，不假装真实 RPMsg 已接通。
  - 未来切到真实 OpenAMP 时，改用 `--transport hook --control-hook-cmd <bridge command>`，由 bridge 负责 `/dev/rpmsg*` 或 `rpmsg_char` 收发。

## 3. 推荐接线顺序

1. 先在飞腾 Linux 侧完成平台审计，确认 `remoteproc`、`rpmsg`、`/dev/rpmsg*` 真实存在。
2. 先做 `STATUS_REQ/RESP` 最短回环，确认 Linux -> 从核 -> Linux 基本收发。
3. 再把 wrapper 放到 `run_remote_current_real_reconstruction.sh --variant current` 外层。
4. 最后才把 heartbeat、deadline、safe-stop 接到真实从核策略。

## 4. 最小使用方式

### 4.1 本地骨架 dry-run

```bash
python3 ./session_bootstrap/scripts/openamp_control_wrapper.py \
  --job-id 24001 \
  --variant current_reconstruction \
  --runner-cmd 'bash ./session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current --max-inputs 1' \
  --expected-sha256 "${INFERENCE_CURRENT_EXPECTED_SHA256}" \
  --output-dir ./session_bootstrap/reports/openamp_wrapper_dryrun_20260313 \
  --dry-run
```

### 4.2 本地控制面包裹真实 runner，但不接 RPMsg

```bash
python3 ./session_bootstrap/scripts/openamp_control_wrapper.py \
  --job-id 24002 \
  --variant current_reconstruction \
  --runner-cmd 'bash ./session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current --max-inputs 1' \
  --expected-sha256 "${INFERENCE_CURRENT_EXPECTED_SHA256}" \
  --output-dir ./session_bootstrap/reports/openamp_wrapper_local_20260313 \
  --heartbeat-interval-sec 2
```

### 4.3 未来切到真实 RPMsg bridge

```bash
python3 ./session_bootstrap/scripts/openamp_control_wrapper.py \
  --job-id 24003 \
  --variant current_reconstruction \
  --runner-cmd 'bash ./session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current --max-inputs 1' \
  --expected-sha256 "${INFERENCE_CURRENT_EXPECTED_SHA256}" \
  --output-dir ./session_bootstrap/reports/openamp_wrapper_phytium_20260313 \
  --transport hook \
  --control-hook-cmd 'python3 ./session_bootstrap/scripts/openamp_rpmsg_bridge.py --hook-stdin --rpmsg-ctrl /dev/rpmsg_ctrl0 --rpmsg-dev /dev/rpmsg0 --output-dir ./session_bootstrap/reports/openamp_wrapper_hook_bridge_20260314'
```

说明：

- `openamp_rpmsg_bridge.py` 已落库，但当前阶段只真实转发 `STATUS_REQ`。
- 若 wrapper 继续发 `JOB_REQ`，bridge 会返回本地 `DENY`，避免假装已经有从核授权路径。
- 真实 `JOB_REQ/JOB_ACK`、`HEARTBEAT`、`SAFE_STOP` 仍依赖从核 firmware 实现。
- wrapper 对 hook 的要求非常保守：
  - 事件 JSON 从 stdin 输入；
  - 当前 phase 从 `OPENAMP_PHASE` 环境变量读取；
  - hook 若返回 JSON 且包含 `decision=DENY`，wrapper 会在数据面启动前拒绝执行。

## 5. 证据落盘

每次 wrapper 运行至少应产出：

- `job_manifest.json`
- `control_trace.jsonl`
- `wrapper_summary.json`
- `runner.log`

其中：

- `job_manifest.json` 记录 runner 命令、`expected_sha256`、deadline、expected outputs。
- `control_trace.jsonl` 记录 `STATUS_REQ`、`JOB_REQ`、`JOB_ACK`、`HEARTBEAT`、`JOB_DONE` 等控制事件。
- `runner.log` 保留原始数据面输出，避免 wrapper 吞日志。

## 6. 明确边界

- 不改 `current_real_reconstruction.py` 的模型加载、latent 读取、AWGN、VM decode、PNG 输出逻辑。
- 不改 `run_remote_current_real_reconstruction.sh` 的远端 artifact 选择和 SHA guard。
- 不把大张量通过 RPMsg 传输；RPMsg 只承载控制帧。
- 不把 benchmark 结果口径从 current trusted path 挪到新的“OpenAMP 数据面实现”。

## 7. 下一步落点

- 先用已落库的 `openamp_rpmsg_bridge.py` 在真实飞腾板上回收 `STATUS_REQ` 探测证据，确认是否拿到真实 `STATUS_RESP`。
- 再让 bridge 与从核 firmware 一起支持 `JOB_REQ/JOB_ACK(ALLOW/DENY)`。
- 最后把 heartbeat timeout / safe-stop 接到从核 guard 策略，并保留现有 trusted current SHA guard 作为执行前置条件。
