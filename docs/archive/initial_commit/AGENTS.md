# AGENTS.md

供 agentic coding assistants 在本仓库工作时参考。

以下内容基于当前工作区状态（2026-04-26）。如果本文与实际代码、脚本或测试入口冲突，以当前仓库实际情况为准。

## 项目上下文

**第十届全国大学生集成电路创新创业大赛（集创赛）2026 · 飞腾企业命题**。

当前仓库实际有两条主线并行：

- **加密 / 控制面主线**：`ML-KEM + HKDF-SHA256 + AEAD + SM2 / ML-DSA + OpenAMP / Cockpit`
- **USRP 主线**：`NI USRP-2922 + official examples first + ConcatCodec/BPSK 经验复用 + OTA`

当前系统收口目标已经固定为一条**混合双平面**路径：

- **控制面 / 认证面**：继续走 `Tailscale / TCP + ML-KEM + HKDF-SHA256 + AEAD + SM2 / ML-DSA`
- **数据面**：切到 `NI USRP-2922 OTA` 发送明文 `latent / quant .npz`
- **旧 TCP 密文数据面**：保留为当前更成熟的 fallback / 兼容路径，不再写成最终目标

`2026-04-26` 硬件切换：飞腾派损坏，同时怀疑 B205mini 链路余量不足。当前 USRP 数据面切到两台 NI USRP-2922。迁移策略是先跑 NI / UHD 官方例程，再从官方 examples 出发单开新的最小 TX/RX 实现；进入自有协议后第一版就按 ARQ-ready / telemetry-first 设计。尽量不要修改现有 B205 代码文件。旧 `usrp_tensor/`、`spool`、`spool_arq` 和 B205mini 指标只作为经验参考。

当前高频入口：

- `./start.sh`：本地主演示入口，后台启动 `Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/server.py`，前台启动 `cockpit_desktop`
- `./tui_start.sh`：Textual TUI 入口，支持本机回环、Tailscale 远端 helper、自检与会话导出
- `./cleanup.sh`：清理 `start.sh` 残留进程，支持 `--restart`

**语言约定**：文档写中文；代码标识符、接口名、协议字段和技术术语保持 English。

## 文档入口

开始动手前，优先看这些当前文档入口：

- `doc/README.md`
- `doc/加密套件/README.md`
- `doc/加密套件/00_总览与入口/00_总览.md`
- `doc/加密套件/00_总览与入口/03_队友快速上手.md`
- `doc/3.上位机 USRP B205 连接/README.md`
- `doc/3.上位机 USRP B205 连接/08_NI_USRP_2922迁移与官方例程.md`

如果任务与 USRP / 国赛复试 / 历史方案有关，再进入这些目录：

- `doc/3.上位机 USRP B205 连接/`
- `doc/4.国赛复试冲刺方案/`
- `doc/加密套件/Archive/`

## 构建与环境

### 推荐开发路径

优先顺序按当前仓库实际使用习惯：

1. `git submodule update --init --recursive`
2. 本地 Python / demo 联调：`source .venv/bin/activate`
3. 本地测试 / 隔离环境：`./docker/dev.sh ...`
4. 需要 Tongsuo 桥接库时：`./docker/docker-build.sh`

### 本地 Python 环境

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

注意：

- `.venv/bin/activate` 当前会自动设置 `OQS_INSTALL_PATH` 和 `LD_LIBRARY_PATH`
- 当前仓库代码也会自动探测 `./liboqs/liboqs-dist` 与 `./liboqs-dist`
- `tui_start.sh` 会检查 `textual` 是否已安装

### 本地构建 liboqs（开发后端）

```bash
cd liboqs
mkdir -p build
cd build
cmake .. -DCMAKE_INSTALL_PREFIX=../liboqs-dist \
         -DOQS_ALGS_ENABLED=ML-KEM \
         -DOQS_BUILD_TESTS=OFF \
         -DOQS_USE_OPENSSL=OFF \
         -DBUILD_SHARED_LIBS=ON
make -j"$(nproc)"
make install
cd ../..
```

### Docker 开发环境

`docker/dev.sh` 是当前推荐的“队友一键进环境”方式：

```bash
./docker/dev.sh build
./docker/dev.sh pytest mlkem_link/tests/ -v
./docker/dev.sh python scripts/demo_e2e.py
./docker/dev.sh bash
```

### 构建 Tongsuo 桥接库产物

`docker/docker-build.sh` 会输出到仓库根 `./tongsuo-dist/`：

```bash
./docker/docker-build.sh
./docker/docker-build.sh arm64
```

### cockpit_desktop（子模块前端）

```bash
cd Semantic-Communication/cockpit_desktop
npm install
npm run dev
npm run build
npm run typecheck
```

## 常用运行入口

```bash
# 主演示入口
./start.sh
./start.sh --server-only

# TUI 演示 / 截图 / 最小认证回归
./tui_start.sh

# 清理残留进程
./cleanup.sh
./cleanup.sh --restart

# Shell 语法检查
bash -n start.sh
bash -n tui_start.sh
bash -n cleanup.sh
```

当前 `start.sh` 的实际行为：

- 启动前询问飞腾派 SSH 密码，可直接回车跳过
- 自动清除 `http_proxy` / `https_proxy` 等代理变量，避免 localhost 502
- 默认导出：
  - `MLKEM_AUTH_ENABLED=1`
  - `MLKEM_AUTH_SERVER_ID=phytium-board`
  - `MLKEM_AUTH_SIG_POLICY=DUAL_REQUIRED`
- 默认关闭 Electron sandbox（当前开发环境的 `chrome-sandbox` 未按 setuid 配置）

## 测试命令

所有 Python 测试先执行：

```bash
source .venv/bin/activate
```

截至当前工作区（2026-04-21），`pytest --collect-only` 已确认以下入口：

```bash
# ── 根仓库密码线测试 ──

# mlkem_link tests（29）
python -m pytest mlkem_link/tests/ -v

# 最常用的两个最小回归
pytest -q mlkem_link/tests/test_auth.py
pytest -q mlkem_link/tests/test_tui_remote_tcp_server.py

# 单文件 / 单用例
python -m pytest mlkem_link/tests/test_session.py -v
python -m pytest mlkem_link/tests/test_session.py::TestSessionAES::test_full_handshake_and_encrypt -v

# ── FIT ──

# Unit-level FIT（17）
python -m pytest scripts/test_fit.py -v

# System-level FIT（11）
python -m pytest scripts/test_system_fit.py -v

# ── OpenAMP / 控制面子模块 ──

# OpenAMP mock（63）
python -m pytest Semantic-Communication/openamp_mock/tests/ -v

# openamp_control_plane_demo 定向回归（18）
python -m pytest \
  Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_crypto_runtime.py \
  -q

# server 相关定向子集（33 selected / 135 total）
python -m pytest \
  Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py \
  -q -k 'usrp or mlkem or crypto or batch'

# cockpit_native（33；需要把子模块根放进 PYTHONPATH）
PYTHONPATH=Semantic-Communication \
python -m pytest Semantic-Communication/cockpit_native/tests/ -q
```

其他常用脚本：

```bash
# 演示
python3 scripts/demo_e2e.py
python3 scripts/demo_handshake.py
python3 scripts/demo_tui.py

# 压力 / 可靠性
sudo python scripts/test_weak_network.py --rounds 50
python scripts/test_continuous_run.py --rounds 100
python scripts/test_resource_stress.py --rounds 30
python scripts/test_daemon_300.py
python scripts/test_jscc_ber_tolerance.py
```

说明：

- `cockpit_native` 直接从仓库根运行 `pytest Semantic-Communication/cockpit_native/tests/` 会因为模块导入路径缺失而报错；请显式设置 `PYTHONPATH=Semantic-Communication`
- `mlkem_link` 运行时只接受可信 KEM 后端（`Tongsuo > liboqs`），不会做不安全自动 fallback
- 认证单测中存在 mock 签名后端用于 isolated verification，但这不等于运行时允许透明降级

## 工具链现状

当前基础设施情况：

- 根仓库没有 Python linter / formatter 配置；未配置 `ruff`、`flake8`、`black`、`mypy`、`pre-commit`
- 根工作区当前没有仓库级 CI / GitHub Actions
- `Semantic-Communication/cockpit_desktop` 当前有 `npm run typecheck`
- `usrp_tensor/` 当前使用 CMake，本仓库没有额外 `clang-format` / `clang-tidy` 配置

## 代码风格

### 根仓库 Python（`mlkem_link/`、根 `scripts/`）

- **Indentation**：4 spaces，禁止 tab
- **Line length**：无硬限制，当前代码常见约 110-120 列
- **Quotes**：普通字符串优先 single quotes；docstring 与 JSON key 使用 double quotes
- **Blank lines**：顶层定义之间保留两空行
- **Section separators**：沿用 Unicode box-drawing
  ```python
  # ── Section Name ──
  # ══════════════════════════════════════════════
  ```
- **Imports**：stdlib → third-party → local，分组间空行
- **Deferred imports**：重依赖 / 可选依赖放到函数体内
- **Module resolution**：根 `scripts/` 继续使用 `sys.path.insert(0, ...)`
- **Type hints**：公有函数 / 方法签名保留注解；优先 PEP 604（`str | None`）
- **Structured data**：优先 `@dataclass`

### Docstring 约定

- 使用 triple-double-quote `"""`
- 描述写中文，参数名和类型保持 English
- 风格以 Google-style 为主，常见 `Args:` / `Returns:`

示例：

```python
def hkdf_sha256(ikm: bytes, salt: bytes = None, info: bytes = b"") -> bytes:
    """HKDF-SHA256 (RFC 5869)

    Args:
        ikm: 输入密钥材料（ML-KEM shared_secret，32 bytes）
        salt: 可选盐值（None 时使用全零）

    Returns:
        派生密钥（length bytes）
    """
```

### 异常与输出

- 根仓库主线代码优先使用 built-in exceptions：`RuntimeError`、`ValueError`、`ConnectionError`、`ImportError`
- 错误信息保持中文
- 包装异常时使用 `raise ... from e`
- 普通控制台输出用 `print()`；结构化留证继续用 `RunLogger`
- 不要把“全仓库禁止自定义异常”当成硬规则；子模块当前已经存在窄范围自定义异常，例如 `ArchiveSessionNotFoundError`、`CompareError`

### 子模块风格

- 修改 `Semantic-Communication/` 时，先看相邻文件再决定风格，不要把 `mlkem_link/` 的习惯硬套到所有子模块
- `cockpit_desktop/` 是 Electron + React + TypeScript 工程，按现有 `package.json` scripts 和目录组织处理
- `cockpit_native/` 是 PySide6 / Qt + QML 工程，保留现有模块划分与测试方式

### C++（`usrp_tensor/`）

- 当前使用 C++17（`CMAKE_CXX_STANDARD 17`）
- 共享定义集中在 `common.h`
- FEC 相关集中在 `fec.h`、`fec/conv.h`、`concat.h`
- 主要分隔注释和技术说明保持中文
- 帧参数、缓冲区大小、调制 / 检测常量以 `common.h` 当前定义为准，不要依赖旧文档的历史数值

## 测试风格约定

以下主要适用于 `mlkem_link/tests/` 与根 `scripts/test_*.py`：

- 按场景分测试类，例如 `TestSessionAES`、`TestCiphertextTampering`
- 测试名使用 `test_<action>_<expected_result>`
- 常见对象构造方式是 plain helper function，不强依赖复杂 fixture
- 条件 skip 当前常见做法是 `@pytest.fixture(autouse=True)`
- 新增用例时优先写清晰、显式的 case；当前根密码线里不常用 `@pytest.mark.parametrize`
- 后端测试优先真实后端，不可用时可以 skip；不要把 `MockKEM` 写成透明运行时 fallback

## 架构速览

```text
start.sh / tui_start.sh / cleanup.sh
  ├── 主演示、TUI 演示、清理入口

mlkem_link/                         # 根密码线核心库
  auth.py                           # transcript、SM2/ML-DSA、Finished
  kem.py                            # KEM backend 选择（Tongsuo > liboqs，拒绝不安全 fallback）
  session.py                        # MLKEMSession 状态机
  crypto.py                         # CipherSuite / LinkEncryptor / EncryptedPayload
  kdf.py                            # HKDF-SHA256
  secure_channel.py                 # TCP framing + authenticated_handshake()
  tests/

scripts/                            # 根联调、守护、留证、TUI、USRP 封装
  tcp_client.py                     # 上位机侧 TCP secure client（控制/认证面与 fallback 数据面）
  tcp_server.py                     # 板端 TCP secure server 入口
  tui_remote_tcp_server.py          # TUI 远端 helper（板端）
  demo_tui.py                       # Textual demo / 远端联调 / 会话导出
  demo_e2e.py                       # 内存内 E2E demo
  demo_handshake.py                 # 握手 / 故障注入 demo
  e2e_usrp.py                       # USRP OTA 编排入口；主推明文 raw-file，历史兼容保留加密 OTA
  usrp_batch_blob.py                # 明文多文件打包 / 拆包
  usrp_ota_sweep.py                 # OTA 编排与扫参
  usrp_continuous_spool_smoke.py    # continuous RX + spool 明文 latent smoke / 批量测速
  artifact_guard.py                 # TVM artifact SHA guard
  replay_guard.py                   # duplicate / replay 检测
  run_logger.py                     # JSONL audit log
  tvm_inference_helper.py           # 独立子进程 TVM 推理包装

Semantic-Communication/             # git submodule，当前工作区在 feat/crypto-control-auth
  openamp_mock/                     # OpenAMP 控制面 mock 与测试
  cockpit_desktop/                  # Electron + React dashboard
  cockpit_native/                   # PySide6 / Qt native cockpit
  session_bootstrap/                # TVM / OpenAMP / demo backend / reports
    demo/openamp_control_plane_demo/

docker/
  dev.sh                            # 开发容器入口
  dev.Dockerfile                    # 开发镜像
  Dockerfile                        # Tongsuo / 依赖构建镜像
  docker-build.sh                   # 导出 tongsuo-dist/
  tongsuo_kem_bridge.c              # Tongsuo KEM 桥接源码

usrp_tensor/                        # B205mini 历史 C++ TX / RX / ARQ / diag；USRP-2922 新线只作参考
  common.h
  concat.h
  fec.h
  fec/conv.h
  rrc.h

artifacts/                          # 运行产物、TUI 会话、扫参记录
evidence/                           # 留证索引与提交素材
Archive/                            # 历史资料
```

## 重要说明

- `Semantic-Communication/`、`Tongsuo/`、`liboqs/` 都是 git submodule；当前工作区里 `Semantic-Communication` 已检出在 `feat/crypto-control-auth`，不要想当然按 `master` 操作
- `Tongsuo/` 与 `liboqs/` 当前工作区是 commit-pinned / detached 风格的常见状态；更新前先检查分支和 commit
- 更新 submodule 前先确认目标分支，再在父仓库记录新的 submodule SHA
- **Do NOT delete or overwrite board-side files without explicit confirmation**
- 根 `scripts/` 目录仍是扁平结构，不是 Python package；很多脚本依赖 `sys.path` 注入
- `scripts/tui_remote_tcp_server.py` 当前会优先尝试导入板端已有 `mlkem_link_v2`，失败后回退到仓库内 `mlkem_link`
- `mlkem_link/auth.py` 当前包含 `MockSigBackend` 供单元测试使用；真实认证路径仍以 `SM2 + ML-DSA` 为主，默认策略是 `DUAL_REQUIRED`
- 当前最终目标已切到“密文控制/认证面 + 明文 USRP 数据面”；不要再把“整包 AEAD 密文 over OTA”写成最终主线
- `Semantic-Communication` 当前 live runtime 对 USRP 明文数据面仍未完全打通；`board_access.py` / 前端已有 `transport_mode` 预留，但 `server.py` 里的 ML-KEM session manager 仅在 `transport=tcp` 时启用
- `board_access.py` 在无显式配置时默认仍回到 `tcp/Tailscale`；文档里不要写成“当前默认已切到 USRP 数据面”
- 截至 `2026-04-23`：`33KB latent` 已通过 B205mini `single` 和 `continuous rx_spool` 明文 OTA；该结果现在是历史基线
- continuous `rx_spool` B205mini 历史冻结演示参数：`2.5 Msps + frame_order=tail-first + last_frame_extra_repeats=1`
- 板端 `rx_spool` build 必须显式使用 `Release`（`-DCMAKE_BUILD_TYPE=Release`，`-O3 -DNDEBUG`）；非 Release 会显著放大 ARM 侧 late-full 解码耗时
- B205mini 历史 continuous 指标：`2.5 Msps / count=10 / 10/10 PASS`，`remote_wall_sec=95.286`，约 `9.53 s/image`
- `rx_spool` 本地源码备份在 `usrp_tensor/usrp_tensor_rx_spool.cpp`；板端源码目录 `/home/user/usrp_tensor_codex_20260423_spool_1/usrp_tensor/`；板端二进制 `/home/user/usrp_tensor_codex_20260423_spool_1/usrp_tensor/build_spool/usrp_tensor_rx_spool`
- 当前正式 fallback：冻结 `rx_spool` 数据面继续保留为 B205mini 历史可用路径，不要在实验中直接覆盖默认入口和参数
- 当前优先级：USRP-2922 官方例程验收 + 新最小 TX/RX baseline；新自有协议从第一版就保留 ARQ 能力
- 仓库中的历史 `ARQ` 代码只可作为参考能力，不要把它误写成“当前 frozen `spool` 已经接入 ARQ”
- 当前已落地的实验入口：`scripts/usrp_latent_demo.py --ota-path spool_arq`，其语义是 `continuous RX + spool` 之上的 **control-plane chunk ARQ**（默认 `chunk_bytes=4096`、`repeat=1`），不是旧的双频 RF NACK 原型
- 初赛阶段当前只要求稳定演示闭环；`50 / 100 / 200 / 300` 批量不再作为当前硬门槛
- 冻结指标必须区分口径：Payload `1846.9 → 130.219 ms`；Real E2E `1850.0 → 230.339 ms/image`。不要混写
- USRP 二进制不可跨架构：x86_64 编译结果不能直接在板端 ARM64 运行，必须带源码到板端重新编译
- B205mini 的 TX/RX 到 RX2 没有内部耦合，loopback 需要外部 SMA 跳线；USRP-2922 loopback 先按 NI 官方例程和端口说明重新确认
- B205mini 历史 payload 调制统一走 `ConcatCodec + BPSK`，不要回退到旧的 `bytes_to_iq + FECCodec` 路径；USRP-2922 新线先跑官方 examples，承载 latent 时再评估复用该 PHY
- B205mini 历史板端 UHD 必须是 4.6.0；USRP-2922 需按 NI / UHD 官方例程重新确认驱动版本和设备 probe
- USRP-2922 是 1GbE 设备，UHD device args 优先使用 `addr=<ip>`；不要把 B205mini 的 `serial=...` 写成当前默认口径
- 不要把 B205mini 的 `tx_gain=60.0` / `rx_gain=60.0` 或旧 frozen 参数直接套到 USRP-2922；先以官方例程和 `uhd_usrp_probe` 输出重新标定
