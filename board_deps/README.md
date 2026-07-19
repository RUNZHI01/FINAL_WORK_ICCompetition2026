# 板端恢复材料

`board_deps/` 保存飞腾派运行所需的离线备份，包括模型、运行时、OpenAMP 固件和 DTB、UHD images、安全信道 helper 及公钥。上位机程序和启动脚本不放在这里。

`FILES.txt` 记录文件大小，`SHA256SUMS` 用于完整性校验。私钥和板卡密码不得进入本目录；`crypto/public_keys/` 只保存公钥归档。

## 内容

| 路径 | 用途 |
|---|---|
| `crypto/` | liboqs、Tongsuo、签名桥接库和公钥备份 |
| `runtime/` | 板端 helper、便携 Python 和 TVM 运行时 |
| `tvm/` | baseline、current 和兼容版本的 TVM artifact |
| `mnn/` | MNN 重建模型 |
| `pytorch/` | PyTorch JSCC checkpoint |
| `inputs/` | TVM、MNN 和 PyTorch 的复现输入 |
| `usrp/uhd-images/` | NI USRP-2922/N210 使用的 UHD 4.6.0.0 images |
| `openamp/` | 当前固件、DTB、源码包、构建产物和 helper service |
| `tools/` | 密钥生成等维护工具 |

分片文件以 `.part-*` 结尾，用于避开单文件大小限制。需要时在仓库根目录重组：

```bash
bash board_deps/reassemble-large-files.sh
```

## 校验

```bash
bash board_deps/verify-board-deps.sh
```

校验成功时输出：

```text
board-deps-ok
```

## 恢复到新板卡

```bash
bash board_deps/install-board-deps.sh
```

安装脚本会写入运行时、模型、固件和 DTB，并可能覆盖板端系统路径。已经能正常演示的板卡不需要重复安装，优先使用隔离 CLI smoke 验证备份。

UHD images 不由安装脚本自动部署。重组后，将 `board_deps/usrp/uhd-images/uhd-images_4.6.0.0.tar.xz` 解压到控制 USRP 的主机，或让 `UHD_IMAGES_DIR` 指向解压后的 `images` 目录。

## 板端 CLI smoke

完整 smoke 会把当前仓库上传到飞腾派的新隔离目录，并分别运行 TVM、MNN 和 PyTorch：

```powershell
.\docker\run-board-cli-smoke.ps1
```

Linux 或 WSL：

```bash
bash docker/run-board-cli-smoke.sh
```

脚本交互式询问 SSH 密码。默认每条路径处理 300 个输入；调试时可设置 `BOARD_CLI_MAX_INPUTS=3`。成功时最后一行是：

```text
cli-smoke-ok
```

结果写入隔离目录的 `logs/demo-kpi-summary.json`。其中 TVM 使用 `inference_ms.median_ms`，MNN 使用端到端的 `total_ms.median_ms`，PyTorch 使用 `run_median_ms`。

需要反复测速时，先用 `BOARD_CLI_REFRESH_CACHE=1` 完成一次完整 smoke，再运行快速入口：

```powershell
.\docker\run-board-cli-benchmark-fast.ps1
```

快速入口复用 `/home/user/iccomp_board_deps_cache`，只同步代码，不重复上传模型和运行时。

## 从现有板卡刷新

确认板端文件比仓库更新后，在上位机运行：

```powershell
.\docker\pull-board-deps.ps1
```

Linux 或 WSL：

```bash
bash docker/pull-board-deps.sh
```

该操作会更新本目录的大文件。拉取后必须重新运行 `verify-board-deps.sh`，并检查 `FILES.txt`、`SHA256SUMS` 和 Git 变更范围。
