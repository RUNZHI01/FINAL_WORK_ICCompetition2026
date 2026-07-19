# Board Offline Resume Plan (2026-03-09)

当前状态：
- 飞腾派 `100.121.87.73` 整机失联
- `22 / 9190 / 9092` 都超时
- `tailscale ping` 无响应
- safe-runtime 重建在失联前至少推进到 `19/568`

已准备的恢复后动作：

## 1. 自动等待恢复并续跑
脚本：
- `session_bootstrap/scripts/auto_resume_safe_runtime_after_recovery.sh`

默认行为：
1. 等待 SSH 恢复
2. 检查 `/home/user/tvm_samegen_safe_20260309/build/libtvm.so` 和 `libtvm_runtime.so`
3. 若库已存在：直接 probe current artifact
4. 若库不存在：重新执行 safe-runtime build
5. 完成后自动 probe current round1 artifact

默认 probe 目标：
- `/home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so`

## 2. 手动运行方式
```bash
bash ./session_bootstrap/scripts/auto_resume_safe_runtime_after_recovery.sh \
  100.121.87.73 user user 22
```

可选环境变量：
- `WAIT_SEC` 默认 `1800`
- `INTERVAL_SEC` 默认 `20`
- `JOBS` 默认 `2`
- `REMOTE_BUILD_ROOT` 默认 `/home/user/tvm_samegen_safe_20260309`

## 3. 当前已知 ground truth
- round1 tuning 已成功
- quick 已成功
- baseline realcmd 可在 `venv + tvm_compat_20260306` 下运行
- round1 current artifact 在该 runtime 下失败：`Module has no function 'vm_load_executable'`
- 因此 blocker 是 **runtime compatibility / remote runtime availability**，不是 tuning 本身
