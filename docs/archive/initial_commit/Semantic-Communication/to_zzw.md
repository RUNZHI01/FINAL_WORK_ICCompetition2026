# 给 zzw：current 重建环境说明

这份文档整理的是**当前 demo 实际复用的 current 重建环境链路**，方便直接对照配置，不用再从网页 demo 里反推。

## 1. 当前 demo 实际使用的 env 基准

demo 当前预载的推理 env 文件是：

```bash
session_bootstrap/tmp/inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.env
```

current 重建实际入口命令是：

```bash
bash ./session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current
```

如果想走和 demo 更接近的统一包装器，也可以：

```bash
bash ./session_bootstrap/scripts/run_inference_benchmark.sh \
  --env session_bootstrap/tmp/inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.env
```

---

## 2. 最小必需配置

如果只是想把 **current 重建** 跑起来，最少要有这些变量：

### 2.1 SSH / 板卡连接

```bash
REMOTE_MODE=ssh
REMOTE_HOST=<板子IP>
REMOTE_USER=<用户名>
REMOTE_PASS=<密码>
REMOTE_SSH_PORT=22
```

> 注意：
> - demo 网页里输入的密码只保存在当前 demo 进程里，**不会写回仓库**。
> - 如果你直接跑脚本，而不是走 demo，`REMOTE_PASS` 必须自己补。

### 2.2 远端 Python / TVM 环境

```bash
REMOTE_TVM_PYTHON='<远端 TVM Python 启动串>'
REMOTE_TORCH_PYTHONPATH=<torch site-packages 路径>
```

其中 `REMOTE_TVM_PYTHON` 在当前 demo env 里不是简单的 python 路径，而是一整段启动命令，核心目的是：

- 指向 `tvm310_safe` 这套 Python
- 补齐 `LD_LIBRARY_PATH`
- 补齐 `TVM_LIBRARY_PATH`
- 补齐 `PYTHONPATH`
- 允许同时借用 torch 侧依赖

### 2.3 输入 / 输出路径

```bash
REMOTE_INPUT_DIR=<latent 输入目录>
REMOTE_OUTPUT_BASE=<输出根目录>
```

### 2.4 current 工件

```bash
REMOTE_CURRENT_ARTIFACT=<current optimized_model.so 路径>
```

或者提供：

```bash
REMOTE_TVM_JSCC_BASE_DIR=<JSCC 根目录>
```

脚本会按默认规则去找：

```bash
$REMOTE_TVM_JSCC_BASE_DIR/tvm_tune_logs/optimized_model.so
```

### 2.5 current 运行参数

```bash
REMOTE_SNR_CURRENT=10
REMOTE_BATCH_CURRENT=1
```

### 2.6 当前工件强校验

```bash
INFERENCE_CURRENT_EXPECTED_SHA256=<64位 sha256>
```

当前 demo 里对应的是：

```bash
INFERENCE_CURRENT_EXPECTED_SHA256=6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1
```

---

## 3. 当前 demo env 中和 current 重建直接相关的关键项

下面这些是当前 demo env 里最关键的 current 配置项：

```bash
MODEL_NAME=jscc
TARGET='{"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon"],"num-cores":4}'
THREADS=4

REMOTE_MODE=ssh
REMOTE_SSH_PORT=22

REMOTE_TVM_PYTHON='env TVM_FFI_DISABLE_TORCH_C_DLPACK=1 LD_LIBRARY_PATH=/home/user/anaconda3/envs/tvm310_safe/lib/python3.10/site-packages/tvm_ffi/lib:/home/user/tvm_samegen_safe_20260309/build TVM_LIBRARY_PATH=/home/user/tvm_samegen_safe_20260309/build PYTHONPATH=/home/user/tvm_samegen_20260307/python:/home/user/anaconda3/envs/tvm310_safe/lib/python3.10/site-packages:/home/user/anaconda3/envs/myenv/lib/python3.10/site-packages /home/user/anaconda3/envs/tvm310_safe/bin/python'
REMOTE_TVM310_PYTHON=/home/user/venv/bin/tvm_compat_python.sh

REMOTE_JSCC_DIR=/home/user/Downloads/jscc-test/jscc
REMOTE_INPUT_DIR=/home/user/Downloads/jscc-test/简化版latent
REMOTE_OUTPUT_BASE=/home/user/Downloads/jscc-test/jscc/infer_outputs
REMOTE_CURRENT_ARTIFACT=/home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so
REMOTE_TVM_JSCC_BASE_DIR=/home/user/Downloads/jscc-test/jscc

REMOTE_SNR_CURRENT=10
REMOTE_BATCH_CURRENT=1

INFERENCE_CURRENT_CMD='bash ./session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current'
INFERENCE_CURRENT_EXPECTED_SHA256=6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1
REMOTE_TORCH_PYTHONPATH=/home/user/anaconda3/envs/myenv/lib/python3.10/site-packages
```

> 出于安全考虑，这里**不写仓库中的密码/板卡登录口令**。
> 如果要在自己环境里直接执行，请本地补：
>
> ```bash
> REMOTE_HOST=<板子IP>
> REMOTE_USER=<用户名>
> REMOTE_PASS=<密码>
> ```

---

## 4. 推荐给 zzw 的最小模板

可以新建一个本地 env 文件，比如：

```bash
# current_rebuild.env
REMOTE_MODE=ssh
REMOTE_HOST=<板子IP>
REMOTE_USER=<用户名>
REMOTE_PASS=<密码>
REMOTE_SSH_PORT=22

REMOTE_TVM_PYTHON='<远端 TVM Python 启动串>'
REMOTE_TORCH_PYTHONPATH=<torch site-packages 路径>

REMOTE_INPUT_DIR=<latent 输入目录>
REMOTE_OUTPUT_BASE=<输出根目录>
REMOTE_CURRENT_ARTIFACT=<current optimized_model.so 路径>

REMOTE_SNR_CURRENT=10
REMOTE_BATCH_CURRENT=1

INFERENCE_CURRENT_EXPECTED_SHA256=<64位 sha256>
INFERENCE_CURRENT_CMD='bash ./session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current'
```

---

## 5. 直接运行方法

### 5.1 只跑 current 重建

```bash
set -a
source ./current_rebuild.env
set +a
bash ./session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current
```

### 5.2 走 benchmark/demo 同款包装器

```bash
bash ./session_bootstrap/scripts/run_inference_benchmark.sh --env ./current_rebuild.env
```

---

## 6. 这个 current 重建脚本实际做了什么

它不是假的 demo 占位脚本，实际跑的是：

1. 读取 latent 输入
2. 加信道噪声
3. 用 TVM / VM decode
4. 写出重建结果
5. 打印逐样本 latency
6. 输出最终 summary

对应文件：

```bash
session_bootstrap/scripts/run_remote_current_real_reconstruction.sh
session_bootstrap/scripts/current_real_reconstruction.py
```

---

## 7. 常见坑

### 7.1 只从 demo 抄 env，但没补密码

demo 里网页输入的密码不会写回 env；
直接跑脚本时必须自己补：

```bash
REMOTE_PASS=<密码>
```

### 7.2 只有 artifact，没有 `REMOTE_TVM_PYTHON`

脚本会硬检查：

- `REMOTE_TVM_PYTHON`
- `REMOTE_INPUT_DIR`
- `REMOTE_OUTPUT_BASE`
- ssh 模式下还会检查 `REMOTE_HOST / REMOTE_USER / REMOTE_PASS`

### 7.3 torch 相关导入失败

补上：

```bash
REMOTE_TORCH_PYTHONPATH=<torch site-packages>
```

`current_real_reconstruction.py` 会优先尝试正常导入 torch，失败后再从：

- `REMOTE_TORCH_PYTHONPATH`
- `REMOTE_REAL_EXTRA_PYTHONPATH`
- `DEMO_EXTRA_PYTHONPATH`

这些路径里兜底补。

### 7.4 current 工件 sha 不匹配

如果设置了：

```bash
INFERENCE_CURRENT_EXPECTED_SHA256
```

那脚本会严格校验 64 位 sha256，不匹配会直接报错。

---

## 8. 一句话总结

如果 zzw 只是想复现 demo 里的 **current 重建环境**，最直接的做法就是：

1. 参考 `session_bootstrap/tmp/inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.env`
2. 本地补上 `REMOTE_HOST / REMOTE_USER / REMOTE_PASS`
3. 确认 `REMOTE_TVM_PYTHON / REMOTE_INPUT_DIR / REMOTE_OUTPUT_BASE / REMOTE_CURRENT_ARTIFACT / INFERENCE_CURRENT_EXPECTED_SHA256`
4. 运行：

```bash
bash ./session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current
```

如果想看和 demo 更接近的总包装行为，再用：

```bash
bash ./session_bootstrap/scripts/run_inference_benchmark.sh --env ./current_rebuild.env
```
