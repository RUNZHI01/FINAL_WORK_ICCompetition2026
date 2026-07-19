# USRP 重建输出目录

## 对比工具数据源

| 数据源 | 板端根目录 | 选择规则 |
|---|---|---|
| `prerecorded-pytorch` | `/home/user/Downloads/jscc-test/jscc/infer_outputs` | `pytorch_reference_reconstruction_*` |
| `prerecorded-tvm` | `/home/user/Downloads/jscc-test/jscc/infer_outputs` | PyTorch 前缀以外的目录 |
| `prerecorded-mnn` | `/home/user/Downloads/jscc-test/mnn_benchmark_outputs` | 全部目录 |
| `usrp-qpsk` | `/home/user/Downloads/jscc-test-usrp/qpsk/tvm` | QPSK TVM 任务 |
| `usrp-iq-direct` | `/home/user/Downloads/jscc-test-usrp/iq-direct/tvm` | IQ 直传 TVM 任务 |

预录任务沿用原目录和名称。迁移脚本只处理旧目录 `/home/user/Downloads/jscc-test-usrp/tvm` 中符合 `openamp3_usrp_*_current` 规则的任务。新任务根据 `JSCC_LINK_MODE` 写入 QPSK 或 IQ 直传目录，MNN 使用对应的 `mnn` 子目录。

| 链路模式 | TVM 输出 | MNN 输出 |
|---|---|---|
| `qpsk` | `/home/user/Downloads/jscc-test-usrp/qpsk/tvm` | `/home/user/Downloads/jscc-test-usrp/qpsk/mnn` |
| `iq-direct` | `/home/user/Downloads/jscc-test-usrp/iq-direct/tvm` | `/home/user/Downloads/jscc-test-usrp/iq-direct/mnn` |

## 分类报告

迁移报告位于 `Semantic-Communication/session_bootstrap/reports/usrp_output_migration_20260717.json`。每条记录包含 `source`、`destination`、`mode`、`reason`、`classification` 和本地 `evidence` 路径，可用于回滚。顶层列表分别记录 `classified`、`moved`、`already_moved`、`unresolved`、`collisions` 和 `missing`。

`exact-summary` 表示任务自身的 `batch_spool_summary.json` 提供了链路证据。`inherited-base-summary` 只用于能从原任务确认链路类型的 recovery/retry 任务。证据缺失或不明确的任务保留在旧目录并标记为 `unresolved`。源目录和目标目录同时存在时记为冲突并阻止迁移；只有目标目录存在时记为 `already_moved`。

## 迁移命令

默认只做 dry-run：

```powershell
$env:BOARD_HOST = '<board-host>'
$env:BOARD_USER = '<board-user>'
$env:BOARD_PASSWORD = '<board-password>'
python scripts/migrate_usrp_output_layout.py `
  --host $env:BOARD_HOST --user $env:BOARD_USER `
  --run-root USRP292x/qpsk_batch_spool_arq_runs `
  --legacy-root /home/user/Downloads/jscc-test-usrp/tvm `
  --report Semantic-Communication/session_bootstrap/reports/usrp_output_migration_20260717.json
```

确认 dry-run 得到 239 个 IQ 直传任务、4 个 QPSK 任务、1 个继承分类的 IQ recovery、1 个 unresolved retry，并且没有冲突和缺失源目录后，才能加 `--apply`。迁移后再次执行 dry-run，244 个已分类任务应全部显示为 `already_moved`，unresolved retry 仍留在旧目录。

```powershell
# 确认报告后执行迁移
python scripts/migrate_usrp_output_layout.py --host $env:BOARD_HOST --user $env:BOARD_USER --run-root USRP292x/qpsk_batch_spool_arq_runs --legacy-root /home/user/Downloads/jscc-test-usrp/tvm --report Semantic-Communication/session_bootstrap/reports/usrp_output_migration_20260717.json --apply

# 按报告回滚
python scripts/migrate_usrp_output_layout.py --host $env:BOARD_HOST --user $env:BOARD_USER --rollback-report Semantic-Communication/session_bootstrap/reports/usrp_output_migration_20260717.json --apply
```

CLI 从环境变量读取 `BOARD_PASSWORD`；未设置时通过 `getpass` 询问，不接受明文密码参数。程序加载系统 `known_hosts`，默认拒绝未知主机密钥。若已人工核对新板卡指纹，可传入 `--host-key-fingerprint SHA256:<base64-fingerprint>`；该指纹只在本次进程中生效，不写入 `known_hosts`。

CLI 只使用 Paramiko SFTP 的 `stat`、`mkdir` 和 `rename`，不会执行远端 shell 移动命令，也不会覆盖目标目录。报告不保存连接身份和凭据。迁移与回滚会在每次 rename 前、成功后和失败时原子更新报告，重复运行会从已记录状态继续。

## 2026-07-17 验收记录

修正后的 dry-run 共分类 244 个任务：239 个 IQ 直传任务、4 个 QPSK 任务，以及 1 个继承分类的 IQ recovery 任务 `openamp3_usrp_1784197230_recovery_current`。`openamp3_usrp_1783653522_current_retry_current` 因缺少 `batch_spool_summary.json` 保持 unresolved。报告中没有冲突或缺失源目录。

`--apply` 已迁移全部 244 个已分类任务。迁移后的 dry-run 显示 244 个 `already_moved`、0 个 `moved`、同一个 unresolved retry，并返回 `safe: true`。只读 SFTP 检查确认 IQ 目录有 240 个任务，QPSK 目录有 4 个任务，旧目录只剩 unresolved retry。迁移命令没有读取或修改预录目录。
