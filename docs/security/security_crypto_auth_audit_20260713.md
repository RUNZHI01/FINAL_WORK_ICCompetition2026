# 加密与认证作用审计（2026-07-13）

## 结论摘要

当前系统中的 ML-KEM + SM4 与 ML-DSA + SM2 不是纯 UI 展示，TCP 安全信道路径中确实参与握手、加密传输、签名验签和失败阻断。但在当前默认 USRP IQ 直传演示路径中，它的主要作用是控制/认证面准入：先确认安全信道可用，再放行 USRP 任务；IQ 无线数据面本身没有被 ML-KEM/SM4 包裹。

因此，演示表述应区分：

- TCP/ML-KEM 路径：latent payload 与回传结果经过 AEAD 加密。
- USRP IQ 直传路径：USRP 数据面走无线/IQ 链路；ML-KEM 只作为安全控制信道和启动 gate。

## 配置入口

`cockpit_desktop/start-dev.sh` 默认设置：

- `MLKEM_TRANSPORT_MODE=usrp`
- `JSCC_LINK_MODE=iq-direct`
- `MLKEM_CIPHER_SUITE=SM4_GCM`
- `MLKEM_AUTH_ENABLED=1`
- `MLKEM_AUTH_SIG_POLICY=DUAL_REQUIRED`

`docker/run-demo-tailscale.sh` 也默认 USRP IQ 与认证开启，但仍带 `ICCOMP_COCKPIT_PROFILE=tvm250-prerecorded` 历史 profile。实际 profile 解析在 `docker/start-electron-prod-demo.sh`，当前测试期望该 profile 仍保持 `MLKEM_AUTH_ENABLED=1`。

## 加密实际作用

TCP 安全信道实现位于 `mlkem_link/secure_channel.py`：

- `handshake()` 完成 ML-KEM 公钥/密文交换并派生会话密钥。
- `send_encrypted()` 调 `MLKEMSession.encrypt()`，用 SM4-GCM 或 AES-GCM 发送帧。
- `recv_encrypted()` 解密并校验 AEAD tag。

`scripts/tcp_client.py` 与 `scripts/tcp_server.py` 的 TCP 推理路径实际调用 `send_encrypted()` / `recv_encrypted()`。服务端收到后校验 SHA256、执行 replay guard、可选 TVM 推理，并加密 ACK/结果回传。

## 认证实际作用

认证实现位于 `mlkem_link/auth.py` 与 `secure_channel.py`：

- 服务端对 transcript 做 SM2、ML-DSA 签名。
- 客户端用本地公钥验签。
- `DUAL_REQUIRED` 会拒绝策略降级。
- 客户端配置了错误 peer public key 时，SM2 与 ML-DSA 验签均失败。
- Finished 消息用派生 key 加密验证，确认双方 transcript 与共享密钥一致。
- 缺少密钥或验签失败会抛错，daemon 无法 ready，Cockpit 当前任务会被阻断。

## USRP 路径边界

`DashboardState._arm_mlkem_security_context()` 会在 `current` 且安全开关开启时启动/复用 `tcp_client.py --daemon`，并 `ping()` 确认安全信道已建立。USRP 批量随后调用 `launch_local_usrp_reconstruction_job(... control_transport="mlkem")`。

这证明控制/认证面参与了 USRP 任务准入，但不代表 IQ payload 被 ML-KEM 加密。USRP IQ 数据面仍由 `launch_local_usrp_reconstruction_job()` 走无线链路，性能统计里的 IQ 传输/解包时间不是 ML-KEM 密文传输时间。

负向阻断也已覆盖：当 `_arm_mlkem_security_context()` 返回 `crypto_unavailable` 阻断 payload 时，`run_demo_inference(... variant="current")` 不会调用 `launch_local_usrp_reconstruction_job()`，即 USRP 数据面不会绕过安全 gate 启动。

## 状态字段与 UI 展示

`/api/crypto-status` 现在显式返回安全作用范围：

- `security_scope=control_gate`：USRP IQ 直传，安全信道用于控制/认证面准入。
- `security_scope=tcp_payload`：TCP 路径，latent/ACK/结果经 ML-KEM 派生密钥与 SM4 保护。
- `data_plane_encrypted`、`tcp_payload_encrypted`、`usrp_payload_encrypted` 分别标记当前数据面是否落在 ML-KEM/SM4 保护范围内。

Cockpit 的“安全信道/配置项”会显示 `security_scope_label`。USRP IQ 默认显示“控制/认证面准入”，避免把无线 IQ payload 误描述为已加密。`server_id` 不再占用安全信道配置卡片；开启认证后，它显示在“板卡密码”辅助信息行，和主机、用户、会话密码状态放在一起。

## 已验证证据

本次本机可运行验证：

```bash
python -m pytest mlkem_link/tests/test_auth.py::TestTranscript \
  mlkem_link/tests/test_auth.py::TestWireCodec \
  mlkem_link/tests/test_auth.py::TestSignVerify \
  mlkem_link/tests/test_auth.py::TestFinished -q
# 8 passed

python -m pytest Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_crypto_runtime.py -q
# 28 passed

python -m pytest Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py::DashboardStateTest::test_run_demo_inference_with_usrp_transport_uses_local_usrp_job_with_mlkem_control \
  Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py::DashboardStateTest::test_set_board_access_applies_auth_policy_overrides \
  Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py::DashboardStateTest::test_ensure_board_tcp_server_restarts_when_auth_status_mismatches -q
# 3 passed

python -m pytest Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py::DashboardStateTest::test_get_crypto_status_marks_usrp_security_as_control_gate \
  Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py::DashboardStateTest::test_get_crypto_status_marks_tcp_security_as_payload_encryption -q
# 2 passed

python -m pytest Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py::DashboardStateTest::test_run_demo_inference_with_usrp_transport_blocks_when_mlkem_control_unavailable -q
# 1 passed

cd Semantic-Communication/cockpit_desktop
node --test src/renderer/src/pages/DashboardPageMinimal.layout.test.mjs
# 21 passed
```

本机直接跑 `mlkem_link/tests/test_session.py` 与 `scripts/test_fit.py` 失败，原因是当前 Windows 环境缺少 liboqs/Tongsuo KEM 运行库，且 `scripts/conftest.py` 调用 Unix-only `os.geteuid()`。这不是安全逻辑反证，只说明需要在容器或板端环境跑全量密码学测试。

## 风险与建议

1. UI 和汇报中应避免说“USRP IQ 数据面已被 ML-KEM/SM4 加密”。准确说法是“USRP 演示由 ML-KEM/SM4 安全控制信道准入，IQ 数据面走无线直传”。
2. `/api/crypto-status` 已增加作用范围字段，后续若新增 IQ payload 认证或加密，应同步扩展这些字段。
3. 如果比赛要求 USRP payload 也有密码学保护，需要新增 IQ payload 签名/认证标签或密文封装设计；这会改变帧大小、同步和性能，应作为独立实验。
4. 建议补一条 live 负测：替换错误 peer public key 时，USRP Current 任务必须被 `_arm_mlkem_security_context()` 阻断。
