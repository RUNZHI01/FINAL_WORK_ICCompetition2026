# 板端依赖

本目录保存飞腾派真机演示和板端 CLI 性能复现需要的运行时、模型、输入、OpenAMP 固件与源码材料。这些文件来自本项目验证过的飞腾派环境；实际连接地址由上层 Docker 脚本通过 `REMOTE_HOST` 或 `TAILSCALE_PING_TARGET` 指定。

## 内容清单

- `crypto/liboqs-dist-aarch64.tar.gz`
  - 恢复到 `/home/user/liboqs-dist`。
- `crypto/tongsuo-runtime-aarch64.tar.gz`
  - 恢复到 `/usr/local/tongsuo`。
- `crypto/libtongsuo_sig_bridge.so`
  - 恢复到 `/home/user/libtongsuo_sig_bridge.so`。
- `crypto/public_keys/board-auth-public-keys.tar.gz`
  - 只包含 SM2 / ML-DSA 公钥；私钥不进入仓库。
- `runtime/mlkem-remote-runtime-snapshot.tar.gz`
  - 板端 ML-KEM TCP server、helper 脚本和 `mlkem_link` 快照。
- `tvm/baseline/optimized_model.so`
  - TVM baseline artifact。
- `tvm/current/optimized_model.so`
  - TVM current artifact，对应 demo 当前方案。
- `tvm/current_legacy/optimized_model.so`
  - TVM legacy current artifact，用于兼容历史路径。
- `tvm/runtime/tvm310-safe-runtime-aarch64.tar.gz`
  - `tvm_inference_helper.py` 需要的板端 TVM runtime。
- `runtime/tvm_py310.tar.gz`
  - CLI smoke 使用的便携 Python 3.10 + TVM runtime，解压到隔离运行目录。
- `mnn/origin/model1.mnn`
  - MNN 重建模型。
- `runtime/mnn_py312.tar.gz.part-*`
  - CLI smoke 使用的便携 Python 3.12 runtime，包含 MNN、PyTorch、TorchVision、Pillow 和 NumPy。文件按 90 MiB 分片存放。
- `pytorch/compressed_gan.pt`
  - PyTorch JSCC sub-generator checkpoint。
- `inputs/places365-latents.tar.gz`
  - TVM 输入 latent 目录。
- `inputs/mnn-encoder-outputs.tar.gz`
  - MNN/PyTorch 输入 encoder output 目录。
- `openamp/firmware/openamp_core0.elf`
  - 当前 OpenAMP remoteproc 固件。
- `openamp/firmware/phytium-pi-board-v3-openamp.dtb`
  - 当前 OpenAMP DTB。
- `openamp/source/release_v1.4.0-jobdone-v14-openamp-source.tar.gz.part-*`
  - 与当前固件匹配的 OpenAMP 源码包，按分片存放。
- `openamp/source/release_v1.4.0-jobdone-v14-openamp-build-artifacts.tar.gz`
  - 当前 OpenAMP 构建产物、配置、ELF、map 和 app 源文件。
- `openamp/source/semantic-communication-openamp-master-07ee28f.tar.gz`
  - 从 `RUNZHI01/Semantic-Communication` 归档的 OpenAMP 相关源码、补丁、板端快照和控制面代码。
- `openamp/runtime/openamp-demo-runtime-services.tar.gz`
  - 板端 OpenAMP helper services。
- `tools/gen_identity_keys.py`
  - SM2 / ML-DSA identity key 生成工具。

## 校验与安装

校验清单：

```bash
bash board_deps/verify-board-deps.sh
```

在干净板卡上恢复依赖：

```bash
bash board_deps/install-board-deps.sh
```

`install-board-deps.sh` 会写入 runtime、模型、firmware 和 DTB，并可能覆盖板端系统路径。已经能正常运行 demo 的板卡优先使用隔离 CLI smoke，不需要重新安装。

## 三路 CLI 性能复现

推荐从仓库根目录运行 Docker 包装脚本。完整 smoke 会连接飞腾派，复制当前仓库到新的 `/home/user/iccomp_repo_selfcontained_<timestamp>`，然后在该隔离目录内运行 TVM、MNN、PyTorch 三条命令行推理路径。

Windows PowerShell:

```powershell
.\docker\run-board-cli-smoke.ps1
```

Linux / WSL:

```bash
bash docker/run-board-cli-smoke.sh
```

脚本会交互式询问板卡 SSH 密码，输入只保存在当前进程中。预期最后一行：

```text
cli-smoke-ok
```

默认每条路径处理 300 个输入；调试时可设置 `BOARD_CLI_MAX_INPUTS=3`。性能汇总写入：

```text
RUN_ROOT/logs/demo-kpi-summary.json
```

完整 smoke 是自包含复现路径，当前仓库压缩上传约 `421 MB`，一次完整隔离目录通常占用 `1.7 GB` 到 `2.0 GB`。如需反复测速，先用 `BOARD_CLI_REFRESH_CACHE=1` 跑一次完整 smoke，把板端依赖写入 `/home/user/iccomp_board_deps_cache`，之后改用快速入口：

```powershell
.\docker\run-board-cli-benchmark-fast.ps1
```

快速入口不重复上传 runtime、模型和输入大包，只同步代码层并复用板端缓存。

KPI 口径与 Electron demo 比较卡片一致：

- TVM：`inference_ms.median_ms`
- MNN：`total_ms.median_ms`
- PyTorch：`run_median_ms`

MNN 使用 `total_ms`，因为 demo 展示的是端到端 wall time，包括预处理、`runSession`、后处理和输出写入；`run_ms` 只包含 `interpreter.runSession`，不能作为交付 KPI。

## 维护脚本

- `scripts/run-isolated-cli-smoke.sh`：在板端隔离目录中执行三路 CLI smoke。
- `scripts/summarize-demo-kpis.py`：把 CLI 日志汇总成 demo 使用的 KPI JSON。
- `scripts/make-portable-runtime-dirs.sh`：从已验证板卡重建便携 runtime 目录，评委复现不需要使用。
- `reassemble-large-files.sh`：重组分片的大文件，用于安装或维护流程。
