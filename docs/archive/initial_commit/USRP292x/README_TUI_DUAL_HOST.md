# USRP-2922 双端 TUI 收发测试全流程

> 适用版本：2026-05-01 起，`UsrpTui.py` 已支持 `local-tx` 双机模式。默认 RX 端为飞腾派（`user@100.121.87.73`）。

## 0. 前置条件

### 硬件

| 角色 | 主机 | USRP | 设备 IP | 连接方式 |
|---|---|---|---|---|
| TX | 本机（Fedora 43） | serial `30D1554` | `192.168.10.2` | 1GbE |
| RX | 飞腾派 / imini（备选） | serial `30D1555` | `192.168.10.22` | 1GbE |

两台 USRP 型号一致（N210r4 + SBXv3），天线已连接。

### 网络

TX 主机和 RX 主机各通过 1GbE 连接各自的 USRP，网段 `192.168.10.0/24`。

TX 主机网络配置：
```bash
sudo ./USRP292x/FedoraUsrpNetwork.sh host-init
```

RX 主机网络配置（imini / 飞腾派）：
```bash
sudo ./USRP292x/FedoraUsrpNetwork.sh board-init
```

验证连通性：
```bash
ping -c 2 192.168.10.2    # TX 侧
ping -c 2 192.168.10.22   # RX 侧
```

### 免密 SSH

TX 主机 → RX 主机需免密 SSH（TUI 的 `u` 键会通过 SSH 远程拉起 RX server）。

**方式一：SSH key（推荐，imini 等已配免密的主机）**

```bash
# TX 侧执行（一次性配置）
ssh-copy-id user@<RX-IP>
# 验证
ssh user@<RX-IP> echo ok
```

推荐在 `~/.ssh/config` 中配置别名（本机已配 `Host imini`）。

**方式二：SSHPASS 环境变量（飞腾派等未配 key 的主机）**

TUI 和 batch 脚本检测到 `SSHPASS` 环境变量时自动使用 `sshpass -e`，无需免密 key。

```bash
# 启动 TUI 时设置密码环境变量（不写入 .bashrc）
SSHPASS=user python3 USRP292x/UsrpTui.py

# 或 export 后再启动（当前 shell 有效）
export SSHPASS=user
python3 USRP292x/UsrpTui.py
```

### Tailscale（控制面）

TX/RX persistent server 绑定 `0.0.0.0`，控制命令通过 Tailscale 隧道传输。确保两台主机 Tailscale 已连通。

### 编译 C++ 工具（每台主机各自编译）

> **重要**：C++ 二进制与 UHD 版本绑定，不可跨主机拷贝。rsync 代码后必须在目标主机上重新编译。

| 主机 | OS / Arch | UHD 版本 | 安装依赖 |
|---|---|---|---|
| TX 上位机（本机） | Fedora 43 / x86_64 | 4.8.0.0 | `sudo dnf install uhd-devel boost-devel` |
| RX imini | Ubuntu 24.04 / x86_64 | 4.6.0.0 | `sudo apt install libuhd-dev libboost-all-dev` |
| RX 飞腾派 | Ubuntu 20.04 / aarch64 | 4.6.0.0 | `sudo apt install libuhd-dev libboost-all-dev` |

```bash
# 在每台主机上各自执行（不是 rsync 过来的）
bash USRP292x/BuildOtaTools.sh
```

编译产物（4 个二进制）已在 `.gitignore` 中，rsync 时会被排除。编译清单：

| 二进制 | 依赖 UHD | 依赖 | 用途 |
|---|---|---|---|
| `OtaRxPersistentServer` | 是 | uhd, boost | RX 常驻捕获服务 |
| `OtaTxPersistentServer` | 是 | uhd, boost | TX 常驻发送服务 |
| `OtaRxCaptureGain` | 是 | uhd, boost | RX 增益标定工具 |
| `QpskFileDecode` | **否** | 无 | C++ 解码器（纯标准库，任何主机可直接编译） |

**rsync 代码到远端后的一键初始化**：

```bash
# 从 TX 侧同步代码到 RX 主机（排除编译产物和临时文件）
rsync -avz --delete \
  --exclude='OtaRx*' --exclude='OtaTx*' --exclude='QpskFileDecode' \
  --exclude='*.sc16' --exclude='*.dat' --exclude='*.log' \
  --exclude='qpsk_*_runs/' --exclude='payloads/' --exclude='run_logs/' \
  USRP292x/ imini:/path/to/ICCompetition2026/USRP292x/

# 在 RX 主机上编译（需要先装好 uhd-devel + boost-devel）
ssh imini 'cd /path/to/ICCompetition2026 && bash USRP292x/BuildOtaTools.sh'
```

## 1. 启动 TUI

```bash
source .venv/bin/activate

# 双机 TX 模式（推荐）
REMOTE_RX_SSH_TARGET=user@100.121.87.73 \
USRP_LOCAL_ROLE_MODE=local-tx \
python3 USRP292x/UsrpTui.py
```

也可以不设环境变量，直接在 TUI 里修改字段。

## 2. 配置 TUI 参数

### 必改字段

| 字段 | 说明 | 双机值 |
|---|---|---|
| Local role mode | 下拉框 | `Local TX` |
| RX CTRL host:port | RX server 控制地址 | `100.121.87.73:29220`（飞腾派 Tailscale IP） |
| Remote RX SSH target | 远端 RX 主机 SSH 目标 | `user@100.121.87.73`（飞腾派） |

### 默认冻结基线（一般不用改）

| 字段 | 默认值 |
|---|---|
| FREQ | `500M` |
| RATE | `5M` |
| TX_GAIN | `25` |
| RX_GAIN | `15` |
| TX_ARGS (addr=IP) | `addr=192.168.10.2` |
| RX_ARGS (addr=IP) | `addr=192.168.10.22` |
| Chunk bytes | `2048` |
| Batch size | `20` |
| Decode workers | `2` |
| Artifact mode | `minimal` |
| Backend | `cpp` |
| C++ mode | `header` |

### Payload preset

- `WebP (~24KB)` — 当前冻结业务基线（默认），~0.502 s/image
- `Stress (131KB)` — 压力包口径，~0.9-1.0 s/image

切换 role mode 时，`Local RX` 模式会自动隐藏 TX 参数和远端 RX 参数。

## 3. 操作流程

```
┌─────────────────────────────────────────────────────────┐
│  1. 选 Local TX                                          │
│  2. 填 RX CTRL host:port + Remote RX SSH target          │
│  3. 按 u — 启动常驻服务器                                 │
│     ├─ TX server: 本机启动 (pid 记录到 server_logs/)       │
│     └─ RX server: SSH 远程启动到 imini                     │
│  4. 按 r — 确认 "Persistent RX: alive / TX: alive"        │
│  5. 按 b — 批量 / 按 s — 单图 / 按 d — dry-run           │
│     ├─ TX: 通过 TCP 发送波形到 USRP                      │
│     ├─ RX: USRP 捕获 IQ 数据（远端）                       │
│     ├─ remote-decode: 远端解码 + 回传小结果               │
│     └─ 本机 merge + SHA256 比对                          │
│  6. 按 q — 退出（自动关闭本机 TX server + 远端 RX server） │
└─────────────────────────────────────────────────────────┘
```

### 各按键说明

| 键 | 功能 | 说明 |
|---|---|---|
| `u` | 启动常驻 | 本地启动 TX server，SSH 远程启动 RX server，等待就绪（最长 15s） |
| `r` | 查询状态 | ping 两台 server，显示 busy/idle、job_id、sample count |
| `d` | Dry Run | 只检查参数和命令编排，不实际发射 |
| `s` | 单图 | count=1，跑一次完整 ARQ 流程 |
| `b` | 批量 | 按 Count 字段跑批量，进度实时显示 |
| `x` | 停止 | 终止正在运行的 batch |
| `c` | 关闭常驻 | 向两台 server 发 quit 命令 |
| `q` | 退出 | 停止 batch + 关闭 owned 的常驻 server 后退出 |
| `h` / `F1` | 帮助 | 打开帮助弹窗 |

## 4. 三种收发解码模式

`--rx-capture-mode` 控制收发和解码的分工方式。`local-tx` 角色默认使用 `remote-decode`。

### 4.1 local（单机模式）

TX 和 RX 在同一台主机上，.sc16 文件直接写本地磁盘，本机 C++ 解码。

```
TX server → USRP → 空中 → USRP → RX server → 本地 .sc16 → 本机 QpskFileDecode
```

- 适用：单台 USRP SMA 回环测试、开发调试
- 无需 SSH，延迟最低
- 解码：本机多线程（`--decode-workers`）

### 4.2 remote-pull（远端捕获 + 本地解码）

RX 在远端主机捕获 .sc16，TX 主机 SCP 拉回后本地解码。

```
TX server → USRP → 空中 → USRP → RX server (imini) → 远端 .sc16
  → SCP 拉回 (~1.4s/batch, 几百 MB) → 本机 QpskFileDecode → merge
```

- 适用：远端 RX 主机性能不足时
- 每个 batch 一次 SCP 拉回 .sc16（大文件，主要瓶颈）
- 解码：本机多线程，速度最快（~345ms/image）
- 性能（2026-05-01 实测）：**~0.82s/image**（300/300 PASS）

### 4.3 remote-decode（远端捕获 + 远端解码，默认）

RX 在远端捕获 .sc16，远端直接解码，只回传小文件结果。

```
TX server → USRP → 空中 → USRP → RX server (imini) → 远端 .sc16
  → SSH stat 获取文件大小 → tar-pipe 推送 manifest+reference (~0.03s)
  → SSH 远端 QpskFileDecode (2 workers, ~585ms/image)
  → tar-pipe 拉回 summary+decoded (~0.02s) → 本机 merge
```

- 适用：最终部署架构（上位机发送 → 板端接收 + 本地解码）
- 无大文件回传，只回传 ~25KB/图（summary ~1KB + decoded ~24KB）
- 解码：远端执行，受 `--decode-workers` 限制并发数（默认 2，保护板端 CPU）
- 性能（2026-05-01 实测）：**~0.95s/image**（去异常 batch，300/300 PASS）
- 注意：远端需编译 QpskFileDecode（纯标准库，`g++ -std=c++17 -O3` 即可）

### 模式对比

| 指标 | local | remote-pull | remote-decode |
|---|---|---|---|
| .sc16 回传 | 无 | ~1.4s/batch | 无 |
| 小文件回传 | 无 | 无 | ~0.05s/batch |
| 解码位置 | 本机 | 本机 | 远端 |
| 解码速度 | 最快 (~345ms/img) | 最快 (~345ms/img) | ~585ms/img (2 workers) |
| SSH 连接/batch | 0 | 1 (SCP) | 5 (mkdir+tar+decode+tar+cleanup) |
| 部署匹配 | 否 | 否 | **是**（板端本地解码） |
| 实测 300 图 | — | 0.82s/img | 0.95s/img* |

\* 去除偶发 SSH 超时 batch 后的均值

### 切换方式

```bash
# 环境变量
RX_CAPTURE_MODE=remote-pull python3 USRP292x/RunQpskFileBatchSpoolArq.py ...
RX_CAPTURE_MODE=remote-decode python3 USRP292x/RunQpskFileBatchSpoolArq.py ...

# CLI 参数
python3 USRP292x/RunQpskFileBatchSpoolArq.py --rx-capture-mode remote-decode ...

# TUI 中：local-tx 角色自动使用 remote-decode
```

### remote-decode 注意事项

1. **远端编译**：`QpskFileDecode.cpp` 纯标准库，无 UHD 依赖，任何有 g++ 17+ 的主机可直接编译：
   ```bash
   scp USRP292x/QpskFileDecode.cpp imini:/tmp/
   ssh imini 'g++ -std=c++17 -O3 -Wall -Wextra /tmp/QpskFileDecode.cpp -o /tmp/QpskFileDecode'
   ```

2. **远端二进制路径**：默认 `/tmp/QpskFileDecode`，可通过 `--remote-decode-bin` 或环境变量 `REMOTE_DECODE_BIN` 覆盖。

3. **CPU 并发保护**：远端解码并发数由 `--decode-workers`（默认 2）控制。板端 CPU 资源有限时不要调大。

4. **文件大小校准**：remote-decode 通过 SSH `stat` 获取远端 .sc16 的实际大小（而非 TX 发送大小），确保最后一个 burst 的信号不被截断（RX 因 `rx_tail_sec` 会多录一段）。

## 5. 数据流（remote-decode 模式）

```
TUI (TX 主机)
  │
  ├─ _collect_params() 读取所有字段
  ├─ build_batch_env() 设置环境变量
  │     └─ RX_CAPTURE_MODE=remote-decode  (local-tx 模式自动设置)
  │     └─ REMOTE_RX_SSH_TARGET=user@100.121.87.73
  │
  ├─ RunQpskFileBatchSpoolArq.py
  │     ├─ OtaTxControl.py → TX server (TCP :29221)
  │     │     └─ TX server → USRP → 空中发射
  │     ├─ OtaRxControl.py → RX server (TCP :29221)
  │     │     └─ RX server ← USRP ← 空中接收 → 写 .sc16 到 imini
  │     ├─ SSH stat → 获取远端 .sc16 实际大小
  │     ├─ tar-pipe → 推送 manifest + reference 到 imini
  │     ├─ SSH → 远端 QpskFileDecode 并行解码 (decode_workers=2)
  │     ├─ tar-pipe → 拉回 decode_summary.json + decoded_wire_blob.bin
  │     └─ 本机 merge → SHA256 比对 → pass/fail
  │
  └─ 结果写入 qpsk_batch_spool_arq_runs/<run_id>/
        └─ batch_spool_summary.json (完整 JSON)
```

运行完成后，TUI 右侧状态栏显示：

```
状态：结束
result: PASS 1 / 1 | FAIL 0 | all_pass=True
timing: total 2.478s | wall mean 2.478s/image | airtime 38.048 ms/image
decode: 345.857 ms/image | merge: 0.413 ms/image
```

详细 JSON 在 `USRP292x/qpsk_batch_spool_arq_runs/<run_id>/batch_spool_summary.json`。

## 6. 常见问题

### "常驻链路尚未就绪"

按 `u` 后再按 `r`，确认两台 server 都是 `alive`。如果 RX 不通：
1. 检查 RX CTRL host:port 是否正确（Tailscale IP，非 192.168.10.x）
2. 检查 imini 上 RX server 是否在运行：`ssh imini 'ss -tlnp | grep 29220'`
3. 检查防火墙是否放行 29220/29221 端口

### "参数错误: ... host:port 格式不对"

host:port 字段格式为 `IP:PORT`，例如 `100.121.87.73:29220`，不要漏掉冒号或端口号。

### batch 全部 CRC 失败

1. 确认 RATE/FREQ 默认值未被覆盖（应为 `500M` / `5M`，不是纯数字）
2. 确认 TX/RX 天线已连接并对准
3. 用 `d` dry-run 检查命令编排是否正确

### SSH 连接失败

TUI 使用 `BatchMode=yes`（免密），不支持密码。确保已配置 SSH key：
```bash
ssh -o BatchMode=yes imini echo ok
```

### 退出后 RX server 残留

如果 TUI 非正常退出（kill -9 等），远端 RX server 不会自动清理。手动清理：
```bash
ssh imini 'ss -tlnp | grep 29220'   # 找 PID
ssh imini 'kill <PID>'
```

## 7. 纯 CLI 回退

如果 TUI 不可用，可以用纯 CLI 复现同等流程：

```bash
# 1. RX 侧手动启动
ssh imini 'nohup bash /home/zhangzw0170/Lab/ICCompetition2026/USRP292x/OtaRxPersistentServer.sh > /tmp/rx.log 2>&1 &'

# 2. TX 侧手动启动
nohup bash USRP292x/OtaTxPersistentServer.sh > /tmp/tx.log 2>&1 &

# 3. 等待就绪
sleep 3

# 4. 运行 batch（remote-decode 模式，默认）
RX_CONTROL_HOST=100.121.87.73 \
RX_CAPTURE_MODE=remote-decode \
REMOTE_RX_SSH_TARGET=user@100.121.87.73 \
python3 USRP292x/RunQpskFileBatchSpoolArq.py \
  --input USRP292x/test_smoke_4k.bin \
  --count 1 --decode-backend cpp

# 4b. 或使用 remote-pull 模式
RX_CONTROL_HOST=100.121.87.73 \
RX_CAPTURE_MODE=remote-pull \
REMOTE_RX_SSH_TARGET=user@100.121.87.73 \
python3 USRP292x/RunQpskFileBatchSpoolArq.py \
  --input USRP292x/test_smoke_4k.bin \
  --count 1 --decode-backend cpp

# 5. 清理
python3 USRP292x/OtaTxControl.py --host 127.0.0.1 --port 29221 quit
python3 USRP292x/OtaRxControl.py --host 100.121.87.73 --port 29220 quit
```
