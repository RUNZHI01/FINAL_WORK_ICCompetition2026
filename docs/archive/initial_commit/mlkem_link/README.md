# mlkem_link — 后量子安全链路模块

上位机 ↔ 飞腾派板之间的后量子安全通信模块。基于 ML-KEM-768 密钥协商 + AES-256-GCM / SM4-128-GCM 双套件对称加密。

## 架构

```
上位机 (Initiator)                         飞腾派 (Responder)
     │                                           │
     │──── ML-KEM public_key ──────────────────>│  start_handshake()
     │                                           │
     │<──── ML-KEM ciphertext ──────────────────│  respond_handshake()
     │                                           │
   complete_handshake()                          │
     │                                           │
     │<===== AEAD 加密通信 (AES/SM4-GCM) ======>│
```

## 认证层（可选）

在基础 `ML-KEM + AEAD` 之上，当前模块已经补入可选的服务端身份认证层：

- 握手主流程仍由 `MLKEMSession` 提供共享密钥
- 认证扩展由 [`auth.py`](./auth.py) 提供
- `SecureChannel.handshake()` 保持兼容；新增 `SecureChannel.authenticated_handshake()`
- 服务端可按策略启用 `SM2`、`ML-DSA` 或双签名 `DUAL_REQUIRED`
- 握手末尾新增 `Finished` 密钥确认，避免只验签不验会话绑定

当前整合约定：

- 板端 `~/mlkem_link_v2` 视为带认证能力的参考实现
- 本地 `mlkem_link/` 已回移认证核心，便于后续直接合入主线
- 认证层只覆盖控制面/认证面；不再把“零误码要求”的数据面演示继续绑死在这一层

### 关键对象

| 文件 | 作用 |
|---|---|
| `auth.py` | `IdentityConfig`、签名后端、transcript 编解码、Finished 确认 |
| `secure_channel.py` | `authenticated_handshake()`，对原无认证握手保持兼容 |
| `session.py` | 暴露 `shared_secret`，供认证层派生 Finished key |
| `tests/test_auth.py` | 认证编解码、签名校验、mock 握手测试 |

## 依赖

### 方案 A：Tongsuo 全栈（首选）

| 组件 | 版本 | 用途 |
|---|---|---|
| **Tongsuo 8.5.0+** | pre1（基于 OpenSSL 3.5.4） | ML-KEM + SM4-GCM + AES-GCM，单库包揽 |
| **libtongsuo_kem_bridge.so** | C bridge | ctypes 桥接，简化 Python 调用 |
| Python 3.8+ | | |

### 方案 B：liboqs + cryptography（兜底）

| 组件 | 版本 | 用途 |
|---|---|---|
| **liboqs-python** | ≥ 0.12 | ML-KEM-768（经多年审计的 PQClean 实现） |
| **cryptography** | == 45.0.7 | AES-256-GCM + SM4-GCM（wheel 内置 OpenSSL 3.5.0+） |
| Python 3.8+ | | |

### 编译 Tongsuo

```bash
# Docker 编译（推荐）
./docker/docker-build.sh

# 产物在 tongsuo-dist/ 目录下
ls tongsuo-dist/lib64/libtongsuo_kem_bridge.so
```

## 快速开始

```python
from mlkem_link import (
    TongsuoBackend, MLKEMSession, SessionRole,
    CipherSuite, derive_session_keys,
)

# 1. 创建后端
kem = TongsuoBackend("768")

# 2. 建立会话
init = MLKEMSession(SessionRole.INITIATOR, kem, CipherSuite.AES_256_GCM)
resp = MLKEMSession(SessionRole.RESPONDER, kem, CipherSuite.AES_256_GCM)

pk = init.start_handshake()
ct = resp.respond_handshake(pk)
init.complete_handshake(ct)

# 3. 加密通信
payload = init.encrypt(b"latent tensor data")
plaintext = resp.decrypt(payload)
assert plaintext == b"latent tensor data"
```

## 模块结构

| 文件 | 职责 |
|---|---|
| `kem.py` | KEM 后端抽象（Tongsuo / LibOQS，自动选择） |
| `crypto.py` | AEAD 加密层（AES-256-GCM + SM4-128-GCM，可插拔） |
| `session.py` | 会话握手状态机（INITIATOR / RESPONDER 双角色） |
| `kdf.py` | HKDF-SHA256 密钥派生（双套件密钥批量派生） |
| `auth.py` | 服务端身份认证扩展（SM2 / ML-DSA / Finished） |

## 认证运行时开关

`scripts/tcp_client.py` / `scripts/tcp_server.py` 通过环境变量启用认证，默认关闭，不影响现有无认证链路。

客户端：

```bash
export MLKEM_AUTH_ENABLED=1
export MLKEM_AUTH_SERVER_ID=phytium-board
export MLKEM_AUTH_SIG_POLICY=DUAL_REQUIRED
export MLKEM_AUTH_PEER_SM2_PUB=/path/to/server_sm2_identity.pub
export MLKEM_AUTH_PEER_MLDSA_PUB=/path/to/server_mldsa_identity.pub
```

服务端：

```bash
export MLKEM_AUTH_ENABLED=1
export MLKEM_AUTH_SERVER_ID=phytium-board
export MLKEM_AUTH_SIG_POLICY=DUAL_REQUIRED
export MLKEM_AUTH_SERVER_SM2_KEY=/path/to/server_sm2_identity.key
export MLKEM_AUTH_SERVER_SM2_PUB=/path/to/server_sm2_identity.pub
export MLKEM_AUTH_SERVER_MLDSA_KEY=/path/to/server_mldsa_identity.key
export MLKEM_AUTH_SERVER_MLDSA_PUB=/path/to/server_mldsa_identity.pub
```

可选策略：

- `DUAL_REQUIRED`：SM2 + ML-DSA 都必须通过
- `SM2_ONLY`
- `MLDSA_ONLY`

## 后端选择优先级

| 优先级 | 后端 | KEM 来源 | AEAD 来源 | SM4 | 定位 |
|---|---|---|---|---|---|
| 1 | **TongsuoBackend** | 铜锁 EVP API | 铜锁（AES + SM4） | 有 | 首选：国密 + 后量子双叙事 |
| 2 | **LibOQSBackend** | liboqs-python | cryptography/OpenSSL | 取决于 OpenSSL | 兜底：成熟稳定 |

自动选择：`from mlkem_link import get_backend; kem = get_backend("768")`

若 `Tongsuo` 和 `liboqs` 均不可用，`get_backend()` 会直接拒绝建立会话，不做不安全降级。

**为什么双方案**：Tongsuo 8.5.0-pre1 是唯一含 ML-KEM 的版本（2026-03-21 更新，仅 9 天）。双方案互为兜底，功能正确优先，国密叙事是加分项。

## 密码套件

| 套件 | 算法 | 密钥长度 | 硬件加速 | 用途 |
|---|---|---|---|---|
| `AES_256_GCM` | AES-256-GCM | 32 bytes | ARMv8 AES+PMULL | 数据面（latent 传输） |
| `SM4_GCM` | SM4-128-GCM | 16 bytes | Tongsuo ARM 汇编 | 控制面 + 国密叙事 |

密钥派生：

```
ML-KEM-768 shared_secret (32B)
    ├─ HKDF(info="aes-256-gcm key") → 32B → AES key
    └─ HKDF(info="sm4-128-gcm key") → 16B → SM4 key
```

## 已知限制

**Tongsuo 的 libcrypto.so 与系统 Python cryptography 库绑定的 libcrypto 存在符号冲突，不能共存于同一进程。**

解决方案：
- **生产环境**：在 Docker 容器中运行（容器内只有 Tongsuo 的 OpenSSL）
- **飞腾派**：板侧无系统 cryptography 依赖，直接安装 Tongsuo 即可
- **开发测试**：使用 Docker 容器运行完整测试

## Docker 测试

```bash
# 构建镜像（内含 Python 3.12 + cryptography 45.0.7 + Tongsuo）
docker build -t tongsuo-build:amd64 -f docker/Dockerfile .

# 运行测试（AES-256-GCM + SM4-GCM + ML-KEM-768 全覆盖）
docker run --rm \
  -v $(pwd)/mlkem_link:/workspace/mlkem_link \
  tongsuo-build:amd64 \
  python3 -m pytest mlkem_link/tests/ -v
```

本机最小认证回归：

```bash
pytest -q mlkem_link/tests/test_auth.py
```

说明：

- 当前 Ubuntu 系统自带 `cryptography/OpenSSL` 组合未必支持 `SM4-GCM`
- 因此 `test_auth.py` 的本机回归已改为使用 `AES_256_GCM` 覆盖认证握手逻辑
- 需要验证 `SM4-GCM` 时，仍以 Docker/Tongsuo 环境为准

## 飞腾派编译与部署指南

### 板侧环境信息

| 项目 | 值 |
|---|---|
| CPU 架构 | aarch64 (ARMv8.2, Phytium) |
| CPU 特性 | `aes pmull sha1 sha2 sha3 sha512 crc32` |
| 操作系统 | Ubuntu 20.04 (aarch64) |
| Python | 3.10 |
| 系统 OpenSSL | 1.1.1f（**不会被替换**） |
| 磁盘空间需求 | ~500MB（源码 + 编译） |
| 内存需求 | >= 512MB（编译时峰值） |

### 步骤 1：SSH 连接板子

```bash
# 替换为实际 IP/用户名/密码
export BOARD=user@192.168.x.x
ssh $BOARD
```

### 步骤 2：安装编译依赖

```bash
# 板子上执行
sudo apt-get update && sudo apt-get install -y build-essential git perl
```

如果无 sudo 权限，检查 `gcc` 和 `make` 是否已安装：

```bash
gcc --version && make --version && perl --version
```

### 步骤 3：下载 Tongsuo 源码

```bash
# 板子上执行
cd ~
git clone https://github.com/Tongsuo-Project/Tongsuo.git
cd Tongsuo
# 确认版本
cat VERSION.dat
# 应显示 TONGSUO_MAJOR=8, TONGSUO_MINOR=5
```

如果板子无法访问 GitHub，在上位机打包后 SCP 传过去：

```bash
# 上位机执行
tar czf tongsuo-src.tar.gz Tongsuo/
scp tongsuo-src.tar.gz $BOARD:~/
# 板子上执行
ssh $BOARD "cd ~ && tar xzf tongsuo-src.tar.gz"
```

### 步骤 4：编译 Tongsuo

```bash
# 板子上执行，预计 15-30 分钟
cd ~/Tongsuo

./config \
    --prefix=/usr/local/tongsuo \
    --openssldir=/usr/local/tongsuo/ssl \
    enable-ntls \
&& make -j$(nproc) \
&& make install_sw
```

**关键说明**：
- 安装到 `/usr/local/tongsuo`（独立前缀），**绝不替换系统 OpenSSL 1.1.1f**
- `install_sw` 只安装库文件，不装文档，节省空间
- 系统服务（apt/ssh 等）完全不受影响

验证编译：

```bash
/usr/local/tongsuo/bin/openssl version
# 输出: Tongsuo: Tongsuo 8.5.0-pre1

/usr/local/tongsuo/bin/openssl list -kem-algorithms | grep -i ml-kem
# 应显示 ML-KEM-512, ML-KEM-768, ML-KEM-1024
```

### 步骤 5：编译 C 桥接库

```bash
# 板子上执行
# 先把 tongsuo_kem_bridge.c 传到板上
# 上位机: scp docker/tongsuo_kem_bridge.c $BOARD:~/

gcc -shared -fPIC -O2 \
    -o /usr/local/tongsuo/lib64/libtongsuo_kem_bridge.so \
    ~/tongsuo_kem_bridge.c \
    -I/usr/local/tongsuo/include \
    -L/usr/local/tongsuo/lib64 \
    -lcrypto \
    -Wl,-rpath,/usr/local/tongsuo/lib64

# 验证
ls -la /usr/local/tongsuo/lib64/libtongsuo_kem_bridge.so
```

### 步骤 6：部署 mlkem_link 模块

```bash
# 上位机执行
scp -r mlkem_link/ $BOARD:~/mlkem_link/
scp scripts/demo_e2e.py $BOARD:~/
```

### 步骤 7：验证

```bash
# 板子上执行
export LD_LIBRARY_PATH=/usr/local/tongsuo/lib64
export TONGSUO_KEM_BRIDGE=/usr/local/tongsuo/lib64/libtongsuo_kem_bridge.so

# 安装 cryptography（如果板子没有）
pip3 install cryptography

# 跑端到端测试
python3 ~/demo_e2e.py

# 跑单元测试
python3 -m pytest ~/mlkem_link/tests/ -v
```

### 步骤 8：性能基准

```bash
# 板子上执行
# Tongsuo 内置 openssl speed
LD_LIBRARY_PATH=/usr/local/tongsuo/lib64 \
/usr/local/tongsuo/bin/openssl speed -seconds 3 aes-256-gcm

LD_LIBRARY_PATH=/usr/local/tongsuo/lib64 \
/usr/local/tongsuo/bin/openssl speed -seconds 3 sm4-gcm

# ML-KEM-768 延迟
python3 -c "
import time, os
os.environ['LD_LIBRARY_PATH'] = '/usr/local/tongsuo/lib64'
os.environ['TONGSUO_KEM_BRIDGE'] = '/usr/local/tongsuo/lib64/libtongsuo_kem_bridge.so'
from mlkem_link.kem import TongsuoBackend
kem = TongsuoBackend('768')

t0 = time.perf_counter()
for _ in range(100):
    kp = kem.keygen()
    enc = kem.encaps(kp.public_key)
    kem.decaps(kp.secret_key, enc.ciphertext, public_key=kp.public_key)
t1 = time.perf_counter()
print(f'ML-KEM-768 roundtrip: {(t1-t0)/100*1000:.2f} ms/次')
"
```

### 环境变量持久化

```bash
# 板子上执行，写入 .bashrc
cat >> ~/.bashrc << 'EOF'
# Tongsuo ML-KEM 环境
export LD_LIBRARY_PATH=/usr/local/tongsuo/lib64:$LD_LIBRARY_PATH
export TONGSUO_KEM_BRIDGE=/usr/local/tongsuo/lib64/libtongsuo_kem_bridge.so
EOF
source ~/.bashrc
```

### 回滚/卸载

```bash
# 完全清除 Tongsuo（对系统零影响）
sudo rm -rf /usr/local/tongsuo
# 从 ~/.bashrc 删除 Tongsuo 相关行
```

### 已知问题与对策

| 问题 | 说明 | 对策 |
|---|---|---|
| libcrypto 符号冲突 | Tongsuo libcrypto.so.3 与系统 Python cryptography 绑定的 libcrypto 冲突 | 板侧若装了 cryptography，设置 `LD_LIBRARY_PATH` 时注意加载顺序；或用 Docker 隔离 |
| 编译内存不足 | Tongsuo 编译峰值约 512MB | 减少 `-j` 并行度：`make -j2` |
| 板子无外网 | 无法 git clone / pip install | 上位机打包 → SCP 传输 |
| Tongsuo pre-release | 8.5.0-pre1 是唯一含 ML-KEM 的版本 | ML-KEM 来自 OpenSSL 3.5.4 上游（NIST FIPS 203），算法本身是生产级 |
