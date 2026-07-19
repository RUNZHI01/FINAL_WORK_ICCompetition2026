# ML-KEM 安全信道部署指南

本文档描述 `ML-KEM + SM2 + ML-DSA` 安全信道的部署、密钥管理、容器/板端环境要求，以及常见故障排查。该信道是控制面的默认安全层，认证策略 `DUAL_REQUIRED`（SM2 + ML-DSA 双签同时校验），默认启用。

## 1. 架构总览

```text
┌──────────────────────┐                      ┌──────────────────────┐
│  容器（x86_64）       │   ML-KEM 握手 +      │  飞腾派（aarch64）   │
│  Initiator / client  │  ← DUAL_REQUIRED →   │  Responder / server  │
│                      │   SM2 + ML-DSA 签名  │                      │
│  - 验签（不签发）     │                      │  - Tongsuo 签 SM2    │
│  - liboqs 验 ML-DSA  │                      │  - liboqs 签 ML-DSA  │
└──────────────────────┘                      └──────────────────────┘
        │                                              │
        │ TONGSUO_SIG_BRIDGE                           │ TONGSUO_SIG_BRIDGE
        │ = /workspace/artifacts/crypto/              │ = /home/user/libtongsuo_sig_bridge.so
        │   libtongsuo_sig_bridge.so (x86_64)         │   (aarch64, board_deps/crypto/)
        │                                              │
        │ OQS_INSTALL_PATH                             │ OQS_INSTALL_PATH
        │ = /opt/liboqs                                │ = /home/user/liboqs-dist
        └──────────────────────────────────────────────┘
```

握手流程（`mlkem_link/auth.py`）：

1. `ClientHello`：客户端送 `proto_version + suite + client_nonce + kem_pk`。
2. `ServerHelloAuth`：服务端送 `server_id + server_nonce + kem_ct + sig_policy + sm2_signature + mldsa_signature`。两个签名覆盖同一份 transcript。
3. 客户端用预置的 peer 公钥（`server_sm2_identity.pub`、`server_mldsa_identity.pub`）验双签。
4. `Finished` 双向密钥确认（HKDF-SHA256 派生的 transcript digest 比对）。

成功标志：`last_sha256_match=true`、`session_count=1`、`auth_enabled=true`、`sig_policy=DUAL_REQUIRED`。

## 2. 文件清单

### 2.1 容器侧（x86_64）

| 路径 | 说明 |
|---|---|
| `/workspace/mlkem_link/` | Python 包：kem / auth / kdf / secure_channel / session |
| `/workspace/docker/tongsuo_kem_bridge.c` | ML-KEM-768 KEM 桥接源码 |
| `/workspace/docker/tongsuo_sig_bridge.c` | SM2 签名桥接源码 |
| `/workspace/artifacts/crypto/libtongsuo_sig_bridge.so` | x86_64 SM2 桥接库（Dockerfile 编译） |
| `/opt/liboqs/` | liboqs 安装目录（Dockerfile 编译） |
| `/workspace/keys/server_sm2_identity.pub` | 板端 SM2 公钥（用于验签） |
| `/workspace/keys/server_mldsa_identity.pub` | 板端 ML-DSA 公钥（用于验签） |
| `/workspace/scripts/start_server_auth.sh` | 带认证模式的 server.py 启动入口 |

容器端 **不需要** 板端的私钥。容器只验签，从不签发。

### 2.2 板端侧（aarch64）

| 路径 | 说明 |
|---|---|
| `/home/user/libtongsuo_sig_bridge.so` | aarch64 SM2 桥接库（来自 `board_deps/crypto/`） |
| `/home/user/liboqs-dist/` | aarch64 liboqs 安装目录 |
| `/usr/local/tongsuo/` | Tongsuo 主安装目录（提供 SM2 实现） |
| `/home/user/keys/server_sm2_identity.key` | SM2 私钥（600） |
| `/home/user/keys/server_sm2_identity.pub` | SM2 公钥 |
| `/home/user/keys/server_mldsa_identity.key` | ML-DSA-65 私钥（600） |
| `/home/user/keys/server_mldsa_identity.pub` | ML-DSA-65 公钥 |

### 2.3 仓库内的密钥材料

`board_deps/crypto/public_keys/board-auth-public-keys.tar.gz` 包含演示用公钥快照。私钥 **不在仓库**（`*.key` 在 `.gitignore` 内），需要时在板端用 `board_deps/tools/gen_identity_keys.py` 现场生成。

## 3. 容器内启动

### 3.1 标准入口

```bash
# 容器内
bash /workspace/scripts/start_server_auth.sh
```

`start_server_auth.sh` 已经配齐 15 个 `MLKEM_AUTH_*` 环境变量。关键映射：

| 变量 | 容器（x86_64） | 板端（aarch64） |
|---|---|---|
| `MLKEM_AUTH_ENABLED` | `1` | `1` |
| `MLKEM_AUTH_SIG_POLICY` | `DUAL_REQUIRED` | `DUAL_REQUIRED` |
| `MLKEM_AUTH_SERVER_ID` | `phytium-board` | `phytium-board` |
| `TONGSUO_SIG_BRIDGE` | `/workspace/artifacts/crypto/libtongsuo_sig_bridge.so` | `/home/user/libtongsuo_sig_bridge.so` |
| `MLKEM_REMOTE_TONGSUO_SIG_BRIDGE` | `/home/user/libtongsuo_sig_bridge.so` | — |
| `OQS_INSTALL_PATH` | `/opt/liboqs` | `/home/user/liboqs-dist` |
| `MLKEM_REMOTE_OQS_INSTALL` | `/home/user/liboqs-dist` | — |
| `MLKEM_AUTH_SERVER_SM2_KEY` | （容器不需要） | `/home/user/keys/server_sm2_identity.key` |
| `MLKEM_AUTH_SERVER_SM2_PUB` | （容器不需要） | `/home/user/keys/server_sm2_identity.pub` |
| `MLKEM_AUTH_SERVER_MLDSA_KEY` | （容器不需要） | `/home/user/keys/server_mldsa_identity.key` |
| `MLKEM_AUTH_SERVER_MLDSA_PUB` | （容器不需要） | `/home/user/keys/server_mldsa_identity.pub` |
| `MLKEM_AUTH_PEER_SM2_PUB` | `/workspace/keys/server_sm2_identity.pub` | （对端公钥） |
| `MLKEM_AUTH_PEER_MLDSA_PUB` | `/workspace/keys/server_mldsa_identity.pub` | （对端公钥） |

### 3.2 在 Windows 主机调用容器

Windows 主机通过 docker exec 调用时，**必须** 加 `MSYS_NO_PATHCONV=1`，否则 git-bash 会把 `/workspace/...` 路径改写成 `E:/Software/Scoop/.../workspace/...`：

```bash
MSYS_NO_PATHCONV=1 docker exec iccomp-ubuntu bash -lc 'cd /workspace && bash scripts/start_server_auth.sh'
```

## 4. 板端启动

板端 `tcp_server` 由容器内的 `server.py` 通过 SSH 在启动阶段自动拉起，使用 `setsid` 脱离 SSH 会话。如果需要手动重启：

```bash
# 板端（默认地址 100.121.87.73，默认用户 user；密码由当前会话提供）
export MLKEM_AUTH_ENABLED=1
export MLKEM_AUTH_SIG_POLICY=DUAL_REQUIRED
export MLKEM_AUTH_SERVER_ID=phytium-board
export MLKEM_AUTH_SERVER_SM2_KEY=/home/user/keys/server_sm2_identity.key
export MLKEM_AUTH_SERVER_SM2_PUB=/home/user/keys/server_sm2_identity.pub
export MLKEM_AUTH_SERVER_MLDSA_KEY=/home/user/keys/server_mldsa_identity.key
export MLKEM_AUTH_SERVER_MLDSA_PUB=/home/user/keys/server_mldsa_identity.pub
export MLKEM_AUTH_PEER_SM2_PUB=/home/user/keys/server_sm2_identity.pub   # 演示：自签自验
export MLKEM_AUTH_PEER_MLDSA_PUB=/home/user/keys/server_mldsa_identity.pub
export TONGSUO_SIG_BRIDGE=/home/user/libtongsuo_sig_bridge.so
export OQS_INSTALL_PATH=/home/user/liboqs-dist
setsid python /home/user/Semantic-Communication/scripts/tcp_server.py \
  > /home/user/artifacts/evidence/logs/tcp_server.log 2>&1 < /dev/null &
```

板端没有 systemd 单元；重启板卡后必须重新拉起 `tcp_server`。

## 5. 密钥生成

新板或轮换密钥时，在板端执行：

```bash
# 板端（必须，因为容器不能 keygen SM2）
python /home/user/board_deps/tools/gen_identity_keys.py --dir /home/user/keys
chmod 600 /home/user/keys/*.key
```

这会生成：

- `server_sm2_identity.key` / `.pub`（SM2: sk 32B, pk 65B）
- `server_mldsa_identity.key` / `.pub`（ML-DSA-65: sk 4032B, pk 1952B）

公钥必须同步到容器侧 `/workspace/keys/`，否则容器无法验签：

```bash
# 控制机（通过 Tailscale SSH 拉公钥到容器）
sshpass -p user scp user@100.121.87.73:/home/user/keys/server_sm2_identity.pub /workspace/keys/
sshpass -p user scp user@100.121.87.73:/home/user/keys/server_mldsa_identity.pub /workspace/keys/
```

## 6. 容器 x86_64 SM2 桥接编译

Dockerfile 在镜像构建阶段已经编译并放到 `/workspace/artifacts/crypto/libtongsuo_sig_bridge.so`。但如果需要重新编译（例如改了 `tongsuo_sig_bridge.c`）：

```bash
# 容器内
apt-get install -y libssl-dev
gcc -O2 -fPIC -shared /workspace/docker/tongsuo_sig_bridge.c \
  -o /workspace/artifacts/crypto/libtongsuo_sig_bridge.so -lcrypto
```

**注意**：编译输出会有 `EC_KEY_*` deprecation 警告，无害。

**vanilla OpenSSL 3.0.2 限制**：

- ✅ 支持 SM2 **sign / verify**（走 deprecated `EC_KEY` 路径）
- ❌ **不支持** SM2 **keygen** via `EVP_PKEY_Q_keygen("SM2")`，调用返回 `rc=-1`

容器只需要 verify，所以这个限制无害。keygen 在板端 Tongsuo 里完成。

## 7. 健康检查

仓库自带两个标准化健康检查脚本：

- `scripts/healthcheck_sm2_bridge.py` — 容器端，验 `libtongsuo_sig_bridge.so` 加载 + 板端公钥读取
- `scripts/healthcheck_sign_verify.py` — 板端，跑 SM2 + ML-DSA 双签 + 验签 roundtrip

### 7.1 容器桥接加载检查

```bash
# 容器内
python /workspace/scripts/healthcheck_sm2_bridge.py
```

预期输出：

```text
[1/3] bridge: /workspace/artifacts/crypto/libtongsuo_sig_bridge.so (17704 bytes)
[2/3] backend loaded: tongsuo-sm2 (pk=65B sk=32B sig=72B)
[3/3] board pub: /workspace/keys/server_sm2_identity.pub (65B)
OK: bridge load + board pub read
```

### 7.2 板端 sign/verify 全链路检查

```bash
# 板端（需要先把脚本 scp 到 /home/user/scripts/）
python3 /home/user/scripts/healthcheck_sign_verify.py
```

预期输出：

```text
sm2:   sk=32B  pk=65B
mldsa: sk=4032B  pk=1952B
loading sm2 backend...
  -> tongsuo-sm2
loading mldsa backend...
  -> oqs-mldsa-65
signing with DUAL_REQUIRED...
  sign: ~77ms (sm2=71B, mldsa=3309B)
verifying...
  verify: ~3ms (ok=True sm2=True mldsa=True err=None)
OK: DUAL_REQUIRED sign+verify roundtrip passed
```

### 7.3 端到端握手检查

```bash
# 容器内
bash /workspace/scripts/start_server_auth.sh 2>&1 | tee /tmp/handshake.log
grep -E 'handshake_ms|last_sha256_match|session_count|auth_enabled|sig_policy' /tmp/handshake.log
```

成功标志：

```text
handshake_ms: <本次实测值>
last_sha256_match=true
session_count=1
auth_enabled=true
sig_policy=DUAL_REQUIRED
server_id=phytium-board
```

`handshake_ms` 是会话建立的墙钟时间，受进程冷启动和持久会话复用影响。历史独立冷启动曾记录约 `1400 ms`，不要把它写成固定算法耗时。

## 8. 典型故障排查

### 8.1 `ImportError: 找不到 libtongsuo_sig_bridge.so`

容器 `TONGSUO_SIG_BRIDGE` 指向了不存在的路径。

- **不要** 用板端路径 `/home/user/libtongsuo_sig_bridge.so`，容器内没有这个文件。
- **不要** 用 `board_deps/crypto/libtongsuo_sig_bridge.so`，那是 aarch64 二进制，x86_64 容器加载会报 `cannot open shared object file`。
- 正确值：`/workspace/artifacts/crypto/libtongsuo_sig_bridge.so`（Dockerfile 编译）。

### 8.2 `cannot open shared object file: No such file or directory`（架构不匹配）

加载 aarch64 `.so` 到 x86_64 进程时报错。检查 ELF 头：

```bash
file /workspace/artifacts/crypto/libtongsuo_sig_bridge.so
# 应该是: ELF 64-bit LSB shared object, x86-64
readelf -h /workspace/artifacts/crypto/libtongsuo_sig_bridge.so | grep Machine
# 应该是: Machine: Advanced Micro Devices X86-64 (0x3e)
```

板端 `.so` 应该是 `Machine: AArch64 (0xb7)`。

### 8.3 `bash: line 1: E:/Software/Scoop/apps/git/...: No such file or directory`

git-bash 路径改写问题。`docker exec bash -c "..."` 内的 `/workspace/...` 被 git-bash 改写成 Windows 路径。

修复：在控制机命令前加 `MSYS_NO_PATHCONV=1`：

```bash
MSYS_NO_PATHCONV=1 docker exec iccomp-ubuntu bash -lc 'cd /workspace && ...'
```

### 8.4 `Tongsuo SM2 keygen 失败: rc=-1`

vanilla OpenSSL 3.0.2 不支持 SM2 keygen。**容器内是预期行为**，不影响验签。如果需要 keygen，去板端运行 `gen_identity_keys.py`。

### 8.5 `已启用身份认证，但缺少 MLKEM_AUTH_SERVER_SM2_KEY`

板端 `tcp_server` 启动时缺少私钥环境变量。检查：

```bash
# 板端
cat /proc/$(pgrep -f tcp_server.py)/environ | tr '\0' '\n' | grep MLKEM_AUTH_SERVER
```

应能看到 `MLKEM_AUTH_SERVER_SM2_KEY=/home/user/keys/server_sm2_identity.key` 等四个变量。如果没有，重启 `tcp_server` 并 export 全部 env。

### 8.6 SSH 到 100.121.87.73 超时

Tailscale 偶发抖动。用 retry loop：

```bash
for i in 1 2 3 4 5; do
  ssh -o ConnectTimeout=5 user@100.121.87.73 true && break
  echo "retry $i..."
  sleep 2
done
```

或启用 SSH ControlMaster 复用连接（见 `RunAnalogLatentBatch.py` 的 `_open_ssh_master` 实现）。

### 8.7 `control_guard_state: PROBE_ERROR`

OpenAMP 控制面心跳问题，**与 ML-KEM 数据面无关**。重启 `server.py` 通常能清掉。如果重启后仍持续，看 `/home/user/artifacts/evidence/logs/openamp.log` 是否有 board status 接口超时，单独追踪。

## 9. 策略选项

`MLKEM_AUTH_SIG_POLICY` 支持三档：

| 值 | 含义 | 适用场景 |
|---|---|---|
| `DUAL_REQUIRED`（默认） | SM2 + ML-DSA 同时校验通过才算握手成功 | 默认部署、抗量子 + 国密合规 |
| `SM2_ONLY` | 只校验 SM2 | 国密合规演示，不要求抗量子 |
| `MLDSA_ONLY` | 只校验 ML-DSA | 抗量子演示，不要求国密 |

切换策略时，**容器和板端必须设同一档**，否则握手会因 policy 不一致而失败。

## 10. 参考

- `mlkem_link/auth.py` — 协议定义、SigBackend、SM2SigBackend、MLDSA backend、`sign_transcript` / `verify_transcript` / `authenticated_handshake`
- `docker/tongsuo_sig_bridge.c` — SM2 桥接源码
- `docker/tongsuo_kem_bridge.c` — ML-KEM-768 KEM 桥接源码
- `board_deps/tools/gen_identity_keys.py` — 密钥生成工具
- `scripts/start_server_auth.sh` — 容器带认证启动入口
- `Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/server.py` — 主 server，自动 SSH 拉起板端 `tcp_server`
