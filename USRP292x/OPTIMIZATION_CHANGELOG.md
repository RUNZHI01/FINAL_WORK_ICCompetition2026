# USRP 单图传输性能优化 — 交付说明

> 日期：2026-05-01
> 问题：`tui_start.sh --usrp` 按 `s` 单图传输耗时约 7 秒，远超理论空口时间（~50ms）
> 目标：定位瓶颈并修复，降低单图端到端延迟

---

## 一、问题定位

### 测试场景

- 入口：`tui_start.sh --usrp` → TUI 界面按 `s` 发送单图
- 模式：Local TX（上位机发射）+ remote-decode（飞腾派接收并解码）
- 链路：上位机 → USRP 2920 → 空口 → USRP 2920 → 飞腾派（ARM64，Tailscale 连接）
- 载荷：WebP ~24KB

### 瓶颈分析

TUI 默认已使用 C++ 解码器 + header sync mode，解码器本身不是瓶颈。
实际耗时集中在 **SSH 连接开销** 和 **射频参数冗余** 上：

| 瓶颈 | 原因 | 估算耗时 |
|---|---|---|
| 6 次独立 SSH 连接 | `decode_batch_remote()` 中每步操作（stat/mkdir/push/decode/pull/cleanup）各建一次 SSH | 2-3s |
| RX Server 每次重建 stream | `OtaRxPersistentServer.cpp` 每次 CAPTURE 都调 `get_rx_stream()` | 0.1-0.3s |
| warmup/tail 采样过大 | 250k samples = 50ms/项，round0 三项合计 150ms 空口浪费 | ~0.15s |

> 飞腾派 ARM64 做 SSH 密钥协商比 x86 慢，加上 Tailscale VPN 延迟，
> 每次 SSH 握手约 300-500ms，6 次合计 1.8-3s。

---

## 二、修改内容

### 修改 1：SSH ControlMaster 持久连接复用

**文件**：`USRP292x/RunQpskFileBatchSpoolArq.py`

**原理**：第一次 SSH 建立后保持 master socket（`/tmp/usrp_ssh_ctrl_<pid>`），
后续所有 SSH/SCP 通过 Unix socket 多路复用，跳过完整握手。

**改动**：
- 新增三个函数：`_ssh_control_socket_path()`、`_ssh_start_control_master()`、`_ssh_stop_control_master()`
- `_ssh_base_args()`、`_scp_base_args()`、`_ssh_shell_prefix()` 增加可选参数 `control_socket`
- `main()` 在 remote 模式下自动启动 ControlMaster，程序退出时自动清理
- 所有 SSH 调用点（共 8 处）均传递 control_socket

**预计收益**：省 1.5-2.5s（5 次后续 SSH 免去握手）

### 修改 2：合并 SSH 命令

**文件**：`USRP292x/RunQpskFileBatchSpoolArq.py`

**改动**：原来的 stat（获取远端文件大小）和 mkdir（创建远端目录）是两次独立 SSH，
现在合并为一条命令，减少 1 次 subprocess 调用。

**预计收益**：省 0.2-0.3s

### 修改 3：RX Server 持久化 rx_stream

**文件**：`USRP292x/OtaRxPersistentServer.cpp`

**改动**：
- `rx_stream_` 从局部变量提升为类成员，构造时创建一次，后续复用
- 每次新 CAPTURE 前自动 drain 清空残留数据
- STOP 路径直接用缓存的 stream，不再重建
- 对比：TX Server 本来就是这么做的，RX 之前漏了

**预计收益**：省 0.1-0.3s

### 修改 4：减少 warmup/tail/gap 采样数

**文件**：`USRP292x/RunQpskFileBatchSpoolArq.py`

| 参数 | 改动前 | 改动后 | 说明 |
|---|---|---|---|
| round0 warmup | 250,000 (50ms) | 100,000 (20ms) | AGC 稳定 <10ms |
| round0 tail | 250,000 (50ms) | 100,000 (20ms) | EOB 余量 20ms 够用 |
| round0 batch_gap | 250,000 (50ms) | 100,000 (20ms) | 帧间隔 |
| fast-ARQ warmup | 100,000 (20ms) | 50,000 (10ms) | round1+ 射频已锁 |
| fast-ARQ tail | 100,000 (20ms) | 50,000 (10ms) | |
| fast-ARQ batch_gap | 100,000 (20ms) | 50,000 (10ms) | |

**预计收益**：省 60-80ms 空口时间，连带减少 RX 录制时长和磁盘 I/O

### 修改 5：BuildOtaTools.sh 自动架构检测

**文件**：`USRP292x/BuildOtaTools.sh`

**改动**：
- 自动检测 `uname -m`（x86_64 或 aarch64）
- 编译产物带架构后缀，如 `OtaRxPersistentServer.x86_64`
- 创建无后缀的 symlink 供现有脚本引用
- 全部使用 `-O3 -march=native` 优化
- 两套架构的二进制可以共存，不会互相覆盖

---

## 三、部署步骤

### 上位机（x86_64，TX 端）

代码已改好，直接编译即可：

```bash
cd ICCompetition2026
bash USRP292x/BuildOtaTools.sh
```

### 飞腾派（aarch64，RX 端）

需要把修改后的源码同步到飞腾派，然后在飞腾派上编译：

```bash
# 方法 1：git pull（如果飞腾派有仓库）
cd /home/user
git pull

# 方法 2：scp 关键文件
scp USRP292x/OtaRxPersistentServer.cpp user@100.121.87.73:/home/user/USRP292x/
scp USRP292x/BuildOtaTools.sh user@100.121.87.73:/home/user/USRP292x/

# 在飞腾派上编译
ssh user@100.121.87.73
cd /home/user
bash USRP292x/BuildOtaTools.sh
```

### 重启服务并测试

```
# 在 TUI 中操作：
1. 按 c 关闭现有常驻服务
2. 按 u 重新启动常驻服务（会使用新编译的二进制）
3. 按 s 测试单图传输
4. 观察耗时变化
```

---

### 修改 6：消灭 Python 子进程启动开销

**文件**：`USRP292x/RunQpskFileBatchSpoolArq.py`

原来每次单图传输会 spawn 4 个 Python 子进程，每个需要 ~100-300ms 启动 Python 解释器：

| 子进程 | 改动前 | 改动后 |
|---|---|---|
| `python3 QpskFileLink.py make` | subprocess (~350ms) | 直接 import 调用 (~5ms) |
| `python3 OtaRxControl.py capture` | subprocess (~150ms) | 内联 TCP socket (~2ms) |
| `python3 OtaTxControl.py send` | subprocess (~150ms) | 内联 TCP socket (~2ms) |
| `python3 OtaRxControl.py wait` | subprocess (~150ms) | 内联 TCP socket (~2ms) |

**改动**：
- 新增 `_send_tcp_command()` 和 `run_control_inline()`，直接用 `socket.create_connection` 发送 TCP 命令，不再启动 Python 子进程
- 新增 `_get_qpsk_link()` 懒加载 import QpskFileLink 模块，`make_waveform()` 直接调用模块函数
- 原有的 `run_control()` 保留作为 fallback

**预计收益**：省 ~700-800ms（4 个子进程的 Python 解释器启动开销）

---

## 四、预期效果

| 优化项 | 最小收益 | 最大收益 |
|---|---|---|
| SSH ControlMaster | 1.5s | 2.5s |
| 合并 SSH 命令 | 0.2s | 0.3s |
| RX stream 持久化 | 0.1s | 0.3s |
| warmup/tail 减小 | 0.06s | 0.08s |
| 消灭 Python 子进程 | 0.7s | 0.8s |
| **合计** | **~2.6s** | **~4s** |

单图传输预计从 **~7s 降到 ~3-4.5s**，接近全 C++ 重写的效果（~1.2s 不可压缩时间来自空口+远端解码+SSH）。

---

## 五、注意事项

1. **warmup/tail 减小后的风险**：如果发现 round0 丢包率明显上升，
   可以通过环境变量恢复旧值：`WARMUP_SAMPLES=250000 TAIL_SAMPLES=250000`
2. **SSH ControlMaster 依赖**：需要 OpenSSH 客户端支持 ControlMaster（Linux 默认支持）。
   如果 Tailscale 连接断开后重连，ControlMaster socket 可能失效，重新运行 batch 即可自动重建。
3. **架构检测编译**：`BuildOtaTools.sh` 现在会输出 `architecture=x86_64` 或 `architecture=aarch64`，
   确认编译目标是否正确。不同架构的二进制带后缀共存，不会互相覆盖。
4. **Python 侧无需重新安装**：`RunQpskFileBatchSpoolArq.py` 的改动是纯 Python，无需 pip install。

---

## 六、后续可选优化方向

如果 3-4.5s 仍不满足需求，下一步可以考虑：

- **在飞腾派上运行持久化解码 daemon**（类似 RX/TX persistent server），
  通过 TCP 而非 SSH 控制解码，彻底消除 SSH 开销（预计再省 0.5-1s）
- **流水线化**：TX 发送第 N+1 张图的同时解码第 N 张图（批量模式下有效）
