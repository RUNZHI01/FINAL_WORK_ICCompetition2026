# OpenAMP Demo Baseline 语义收敛记录

Date: 2026-03-22

Scope: 收敛 `openamp_control_plane_demo` 里 baseline 路径的用户口径，不改启动器、不改前端大布局、不改现场 operator flow。

## 本轮决定

1. Demo 的 baseline live 用户口径统一写成 `PyTorch live`，不再把它写成会让答辩误解为旧 TVM baseline 的 `PyTorch legacy live`。
2. 后端技术状态继续保留真实字段：
   - `mode=legacy_sha` 表示当前 live admission 仍走 expected-SHA 准入；
   - `mode=signed_manifest_v1` 表示已配置 signed manifest live admission。
3. 第三幕默认叙事不变：
   - 默认 compare 仍是 `2026-03-12` 归档 `PyTorch reference`；
   - `2026-03-17` baseline `300/300` signed sideband live 继续保留为历史证据，不改写成默认 operator flow。

## 代码面收口

- `session_bootstrap/demo/openamp_control_plane_demo/inference_runner.py`
  - baseline + `legacy_sha` 模式下，用户标签改为 `PyTorch live 已支持/未就绪`；
  - 用户说明改成 `expected-SHA admission (legacy_sha)`，并显式说明：
    - 默认视觉对照仍是归档 `PyTorch reference`；
    - `2026-03-17` dual-path signed-sideband 结果是历史 live evidence。

## 对下一轮的含义

- 如果后续继续推进 baseline 真 live：
  - 用户可直接沿用 `PyTorch live` / `PyTorch signed live` 两套口径；
  - 不要重新引入 `baseline TVM live` 或 `PyTorch legacy live` 这种会扰乱主叙事的表述。
- 如果只做 72 秒答辩版：
  - 仍然优先停在归档 `PyTorch reference` compare；
  - 只有评委明确要求时才展开 baseline live 历史证据或现场 live 分支。
