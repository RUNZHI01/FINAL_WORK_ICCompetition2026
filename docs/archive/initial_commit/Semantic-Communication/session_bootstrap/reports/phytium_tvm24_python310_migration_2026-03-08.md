# 飞腾派 TVM 0.24 / Python 3.10 迁移记录（2026-03-08）

## 结论摘要

本次兼容性排障已得到明确结论：

1. 飞腾派上的 `tvm_samegen_20260307` 已成功编译出：
   - `/home/user/tvm_samegen_20260307/build/libtvm.so`
   - `/home/user/tvm_samegen_20260307/build/libtvm_runtime.so`
2. `apache-tvm-ffi 0.24.dev0` 已可安装。
3. 旧远端环境 `/home/user/venv/bin/python` 实际为 **Python 3.9.5**，无法兼容 TVM 0.24 Python 侧代码。
4. 新环境 `/home/user/anaconda3/envs/tvm310/bin/python`（**Python 3.10.20**）已经成功导入 TVM 0.24。

因此，后续飞腾派执行入口必须切到：

```bash
REMOTE_TVM_PYTHON=/home/user/anaconda3/envs/tvm310/bin/python
```

旧 `venv` 仍可保留作回退参考，但**不能再作为 TVM 0.24 的运行入口**。

## 关键证据

### A. 旧环境失败（Python 3.9.5）

在 `/home/user/venv/bin/python` 下，导入新树 TVM 0.24 时失败，典型报错：

```text
TypeError: unsupported operand type(s) for |: 'types.GenericAlias' and 'NoneType'
```

对应位置：

- `tvm/runtime/script_printer.py`

这说明 TVM 0.24 的 Python 代码使用了 Python 3.10+ 的类型注解语法，
飞腾派旧 `venv` 不满足运行要求。

### B. 新环境成功（Python 3.10.20）

在 `/home/user/anaconda3/envs/tvm310/bin/python` 下，以下导入验收通过：

```python
import tvm
print(tvm.__version__)
print(tvm.__file__)
```

结果指向：

- `TVM_VERSION=0.24.dev0`
- `TVM_FILE=/home/user/tvm_samegen_20260307/python/tvm/__init__.py`

### C. `tvm-ffi` 已安装

新环境中 `apache-tvm-ffi 0.24.dev0` 已完成安装。
旧链路里“仅 `libtvm.so` 编好但 Python 包层未接通”的问题已解除。

## 本次迁移中踩到的坑

### 1. `libtvm.so` 编译耗时极长

飞腾派上单线程补编主库耗时很久，期间本地会话句柄多次丢失。
最终改为“远端后台 + 日志文件”才把构建稳定接完。

### 2. `ssh_with_password.sh` 的临时 askpass 脚本在长命令里不稳

部分长命令出现过：

```text
ssh_askpass: exec(/tmp/ssh_askpass_xxx.sh): No such file or directory
```

后续若继续远程大任务，建议优先考虑：

- 更稳定的 SSH 认证方式；或
- 远端 `nohup` / 日志落盘；或
- 直接切到已有交互 shell / tmux。

### 3. 旧路径残留会造成“旧 Python + 新 C++”混搭

排障过程中曾出现：

- `tvm.egg-link` 指向新树；
- 但 `easy-install.pth` 或当前工作目录仍让旧树 Python 代码优先导入；
- 结果变成旧 Python 包加载新 `libtvm.so`，报 `undefined symbol: TVMGetLastError`。

这说明后续验收应始终在 **明确的 Python 环境 + 明确的工作目录** 下执行。

## 当前推荐运行入口

### 推荐（后续所有飞腾派 TVM 0.24 执行）

```bash
REMOTE_TVM_PYTHON=/home/user/anaconda3/envs/tvm310/bin/python
```

### 不再推荐（仅保留回退/对照）

```bash
REMOTE_TVM_PYTHON=/home/user/venv/bin/python
```

## 下一步建议

1. 将所有飞腾派相关 env/config 中的 `REMOTE_TVM_PYTHON` 切到 `tvm310`。
2. 后续 quick/full/realcmd/rpc runner 一律使用 `tvm310`。
3. 在新环境下补做一轮 readiness / quick 验证，确认脚本侧无遗漏。
4. 在确认运行链路已稳定后，再决定是否删除旧树：
   - `/home/user/tvm`
   - `/home/user/tvm_compat_20260306`
   - 旧 `/home/user/venv` 中与 TVM 绑定的残留入口

## 一句话状态

**飞腾派上的 TVM 0.24 已经在 Python 3.10 conda 环境里跑通；当前不是“编不过”，而是“必须弃用旧 3.9 venv 入口”。**
