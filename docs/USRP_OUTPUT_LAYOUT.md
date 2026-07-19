# USRP 重建输出目录

## 当前目录

| 数据源 | 板端根目录 | 选择规则 |
|---|---|---|
| `prerecorded-pytorch` | `/home/user/Downloads/jscc-test/jscc/infer_outputs` | `pytorch_reference_reconstruction_*` |
| `prerecorded-tvm` | `/home/user/Downloads/jscc-test/jscc/infer_outputs` | 排除 PyTorch 前缀 |
| `prerecorded-mnn` | `/home/user/Downloads/jscc-test/mnn_benchmark_outputs` | 全部目录 |
| `usrp-qpsk` | `/home/user/Downloads/jscc-test-usrp/qpsk/tvm` | QPSK TVM 任务 |
| `usrp-iq-direct` | `/home/user/Downloads/jscc-test-usrp/iq-direct/tvm` | IQ-direct TVM 任务 |

新任务根据 `JSCC_LINK_MODE` 写入对应目录：

| 链路 | TVM | MNN |
|---|---|---|
| `qpsk` | `/home/user/Downloads/jscc-test-usrp/qpsk/tvm` | `/home/user/Downloads/jscc-test-usrp/qpsk/mnn` |
| `iq-direct` | `/home/user/Downloads/jscc-test-usrp/iq-direct/tvm` | `/home/user/Downloads/jscc-test-usrp/iq-direct/mnn` |

## 旧目录迁移

`scripts/migrate_usrp_output_layout.py` 只处理旧目录 `/home/user/Downloads/jscc-test-usrp/tvm`。默认执行 dry-run，不移动文件：

```powershell
$env:BOARD_HOST = "目标 IP"
$env:BOARD_USER = "目标用户名"
python scripts/migrate_usrp_output_layout.py `
  --host $env:BOARD_HOST `
  --user $env:BOARD_USER `
  --run-root USRP292x/qpsk_batch_spool_arq_runs `
  --legacy-root /home/user/Downloads/jscc-test-usrp/tvm `
  --report Semantic-Communication/session_bootstrap/reports/usrp_output_migration.json
```

检查报告中的 `unresolved`、`collisions` 和 `missing` 后，才能在同一命令末尾添加 `--apply`。按报告回滚：

```powershell
python scripts/migrate_usrp_output_layout.py `
  --host $env:BOARD_HOST `
  --user $env:BOARD_USER `
  --rollback-report Semantic-Communication/session_bootstrap/reports/usrp_output_migration.json `
  --apply
```

程序未从环境变量取得密码时会通过 `getpass` 询问。它使用系统 `known_hosts`，默认拒绝未知主机密钥；人工核对指纹后，可用 `--host-key-fingerprint SHA256:<fingerprint>` 只为本次进程放行。

迁移使用 Paramiko SFTP 的 `stat`、`mkdir` 和 `rename`，不执行远端 shell，不覆盖已存在的目标目录。报告不保存连接凭据，并在每次移动前后更新，重复运行会从已有状态继续。
