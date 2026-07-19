# ML-KEM 控制信道与双签认证

控制信道默认启用 ML-KEM、SM4-GCM 和双签认证。`DUAL_REQUIRED` 要求 SM2 与 ML-DSA-65 同时通过。USRP 射频数据面不在该加密范围内。

## 组成

```text
上位机容器（x86_64）                    飞腾派（aarch64）
Initiator / client                      Responder / server

ML-KEM-768 握手        <------------->  ML-KEM-768 解封装
SM2 + ML-DSA 验签      <-------------   SM2 + ML-DSA 签名
SM4-GCM 控制消息       <------------->  SM4-GCM 控制消息
```

容器保存板端公钥，只负责验签。板端保存身份私钥并生成签名。

## 握手

`mlkem_link/auth.py` 实现以下流程：

1. `ClientHello` 发送协议版本、算法套件、client nonce 和 KEM 公钥。
2. `ServerHelloAuth` 返回 server ID、server nonce、KEM ciphertext、签名策略和两个签名。
3. SM2 与 ML-DSA 签名覆盖同一份 transcript。
4. 客户端使用预置的板端公钥验签。
5. 双方用 HKDF-SHA256 派生材料完成 `Finished` 确认。

成功状态包括：

```text
last_sha256_match=true
session_count=1
auth_enabled=true
sig_policy=DUAL_REQUIRED
```

## 文件位置

### 容器

| 路径 | 内容 |
|---|---|
| `/workspace/mlkem_link/` | KEM、认证、KDF 和安全会话代码 |
| `/workspace/artifacts/crypto/libtongsuo_sig_bridge.so` | x86_64 SM2 bridge |
| `/opt/liboqs/` | x86_64 liboqs |
| `/workspace/keys/server_sm2_identity.pub` | 板端 SM2 公钥 |
| `/workspace/keys/server_mldsa_identity.pub` | 板端 ML-DSA 公钥 |
| `/workspace/scripts/start_server_auth.sh` | 认证模式入口 |

### 飞腾派

| 路径 | 内容 |
|---|---|
| `/home/user/libtongsuo_sig_bridge.so` | aarch64 SM2 bridge |
| `/home/user/liboqs-dist/` | aarch64 liboqs |
| `/usr/local/tongsuo/` | Tongsuo runtime |
| `/home/user/keys/server_sm2_identity.key` | SM2 私钥，权限 `600` |
| `/home/user/keys/server_sm2_identity.pub` | SM2 公钥 |
| `/home/user/keys/server_mldsa_identity.key` | ML-DSA-65 私钥，权限 `600` |
| `/home/user/keys/server_mldsa_identity.pub` | ML-DSA-65 公钥 |

仓库内的 `board_deps/crypto/public_keys/board-auth-public-keys.tar.gz` 只包含公钥快照。私钥不得进入仓库。

## 正常启动

现场使用 `.\demo.ps1`。Cockpit 后端会通过 SSH 拉起板端 `tcp_server.py`，不需要手动执行本节命令。

容器内单独检查认证入口：

```bash
bash /workspace/scripts/start_server_auth.sh
```

从 Windows Git Bash 调用容器时，需要关闭 MSYS 路径改写：

```bash
MSYS_NO_PATHCONV=1 docker exec iccomp-ubuntu \
  bash -lc 'cd /workspace && bash scripts/start_server_auth.sh'
```

## 板端手动启动

只在自动启动失败或调试时使用：

```bash
export MLKEM_AUTH_ENABLED=1
export MLKEM_AUTH_SIG_POLICY=DUAL_REQUIRED
export MLKEM_AUTH_SERVER_ID=phytium-board
export MLKEM_AUTH_SERVER_SM2_KEY=/home/user/keys/server_sm2_identity.key
export MLKEM_AUTH_SERVER_SM2_PUB=/home/user/keys/server_sm2_identity.pub
export MLKEM_AUTH_SERVER_MLDSA_KEY=/home/user/keys/server_mldsa_identity.key
export MLKEM_AUTH_SERVER_MLDSA_PUB=/home/user/keys/server_mldsa_identity.pub
export MLKEM_AUTH_PEER_SM2_PUB=/home/user/keys/server_sm2_identity.pub
export MLKEM_AUTH_PEER_MLDSA_PUB=/home/user/keys/server_mldsa_identity.pub
export TONGSUO_SIG_BRIDGE=/home/user/libtongsuo_sig_bridge.so
export OQS_INSTALL_PATH=/home/user/liboqs-dist

setsid python /home/user/Semantic-Communication/scripts/tcp_server.py \
  > /home/user/artifacts/evidence/logs/tcp_server.log 2>&1 < /dev/null &
```

板端没有对应的 systemd unit，重启后由一键启动脚本重新拉起。

## 密钥生成与公钥同步

新板或轮换密钥时，在飞腾派执行：

```bash
python /home/user/board_deps/tools/gen_identity_keys.py --dir /home/user/keys
chmod 600 /home/user/keys/*.key
```

随后把两个公钥复制到容器的 `/workspace/keys/`。以下命令会使用 SSH 的正常密码提示或已配置的密钥认证，不在命令行写密码：

```bash
scp <board-user>@<board-host>:/home/<board-user>/keys/server_sm2_identity.pub \
  /workspace/keys/
scp <board-user>@<board-host>:/home/<board-user>/keys/server_mldsa_identity.pub \
  /workspace/keys/
```

同步后核对公钥指纹。私钥只保留在板端。

## 关键环境变量

| 变量 | 容器 | 飞腾派 |
|---|---|---|
| `MLKEM_AUTH_ENABLED` | `1` | `1` |
| `MLKEM_AUTH_SIG_POLICY` | `DUAL_REQUIRED` | `DUAL_REQUIRED` |
| `MLKEM_AUTH_SERVER_ID` | `phytium-board` | `phytium-board` |
| `TONGSUO_SIG_BRIDGE` | `/workspace/artifacts/crypto/libtongsuo_sig_bridge.so` | `/home/user/libtongsuo_sig_bridge.so` |
| `OQS_INSTALL_PATH` | `/opt/liboqs` | `/home/user/liboqs-dist` |
| `MLKEM_AUTH_PEER_SM2_PUB` | `/workspace/keys/server_sm2_identity.pub` | 对端公钥路径 |
| `MLKEM_AUTH_PEER_MLDSA_PUB` | `/workspace/keys/server_mldsa_identity.pub` | 对端公钥路径 |

板端还需要四个 `MLKEM_AUTH_SERVER_*` 私钥、公钥路径，见手动启动命令。

## 健康检查

容器 bridge 和公钥：

```bash
python /workspace/scripts/healthcheck_sm2_bridge.py
```

板端双签 roundtrip：

```bash
python3 /home/user/scripts/healthcheck_sign_verify.py
```

端到端握手：

```bash
bash /workspace/scripts/start_server_auth.sh 2>&1 | tee /tmp/handshake.log
grep -E 'handshake_ms|last_sha256_match|session_count|auth_enabled|sig_policy' /tmp/handshake.log
```

`handshake_ms` 是包含进程启动和网络等待的墙钟时间，不是单独的 KEM 算法耗时。

## 常见错误

### bridge 路径或架构错误

容器必须加载：

```text
/workspace/artifacts/crypto/libtongsuo_sig_bridge.so
```

`board_deps/crypto/libtongsuo_sig_bridge.so` 和 `/home/user/libtongsuo_sig_bridge.so` 是 aarch64 版本，不能由 x86_64 容器加载。可用 `file` 和 `readelf -h` 检查 ELF 架构。

### Git Bash 改写容器路径

报错路径出现 Windows 盘符时，在 `docker exec` 前设置 `MSYS_NO_PATHCONV=1`。

### 容器内 SM2 keygen 失败

容器的 OpenSSL 3.0.2 bridge 用于 SM2 验签，不负责生成 SM2 密钥。密钥应在飞腾派的 Tongsuo 环境中生成。

### 板端缺少身份变量

检查 `tcp_server.py` 进程环境：

```bash
cat /proc/$(pgrep -f tcp_server.py)/environ | tr '\0' '\n' \
  | grep MLKEM_AUTH_SERVER
```

缺少变量时，按“板端手动启动”重新拉起进程。

### SSH 超时

先确认上位机和飞腾派位于同一 Tailscale 网络，再检查 `REMOTE_HOST`、ACL 和板卡在线状态。不要把密码写入重试脚本。

### `control_guard_state: PROBE_ERROR`

该状态表示 OpenAMP 控制面探测失败，不是 ML-KEM 数据面错误。重启 Cockpit 后端；若仍失败，检查板端 OpenAMP 日志和 status 接口。

## 签名策略

| 值 | 行为 |
|---|---|
| `DUAL_REQUIRED` | SM2 与 ML-DSA 都通过，默认值 |
| `SM2_ONLY` | 只校验 SM2 |
| `MLDSA_ONLY` | 只校验 ML-DSA |

容器和飞腾派必须使用相同策略。

## 代码入口

- `mlkem_link/auth.py`：握手 transcript 和签名校验
- `docker/tongsuo_sig_bridge.c`：SM2 bridge
- `docker/tongsuo_kem_bridge.c`：ML-KEM-768 bridge
- `board_deps/tools/gen_identity_keys.py`：板端身份密钥生成
- `scripts/start_server_auth.sh`：容器认证入口
- `Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/server.py`：Cockpit 后端与板端启动编排
