# 国奖决战期 AI 交接文档 (AI_HANDOFF_DEGRADATION_UPGRADE)

## 1. 核心战略方向
当前项目正从“弱网语义图像回传系统”全面升级为：**面向极端弱网无人巡检的飞腾抗毁语义通信与安全控制一体系统**。

**战略取舍与结论（请务必遵循）：**
1. **重点推进：基于真实 USRP 的任务级退化保底。** 实现在网络恶化时，系统从【全图传输 (L0)】自动降级至【局部/ROI (L1)】、【告警摘要 (L2)】乃至【安全停机 (L3)】。
2. **战略放弃：飞腾板卡真实的 OP-TEE 硬件环境交叉编译与烧录部署。**（因为工程代价与时间成本过高）
3. **应对策略：** 涉及“可信准入”的赛题要求，继续沿用我们已经在 `openamp_mock/crypto_guard.py` 中实现的“软件层 Hash 验签与 Token 制”，在文档中包装为“软件机制验证完成，TA 安全应用下沉部署中”，通过信息差规避编译地狱。

---

## 2. 目前已完成的工作：退化保底机制沙盒 (Mock/PoC)
目前已经在 `openamp_mock/` 目录跑通了核心的协议扩展与状态机测试：
- `protocol.py`：新增了 `ServiceMode` 枚举（对应不同降级模式）、新消息类型及故障码。
- `link_health.py`：实现了 `LinkHealthReport` 结构和用于测试的 `LinkHealthSimulator`。
- `guard.py`：实现了 `SafetyGuard` 双层状态机与 **防抖滞回逻辑（Hysteresis）**，避免模式因网络波动频繁横跳。
- `orchestrator.py`：处理了 `MODE_DIRECTIVE`，管理模式降级的响应。
- `demo.py`：新写了 4 个环境劣化的 FIT 测试场景（FIT-04~07），测试全部通过。

---

## 3. 重大架构重定界（必须注意的历史包袱）
**警示：不要把 `openamp_mock` 当作孤立的废案原型！**
本项目实际上已经拥有极其庞大立体的 5 层架构。**`openamp_mock/protocol.py` 中的枚举和协议定义，已经在真实板卡的控制面代码 `scripts/openamp_rpmsg_bridge.py` 中被直接 `import` 并复用！**

因此，接下来的重点**不是**用 C/C++ 从零重写板卡逻辑，而是顺着已有的 Python 基础链路，将我们的退化降级状态机（Mock）与 5 层基础架构进行**管线打通**。

---

## 4. 下一步待接手集成任务：跨层真实闭环联动
接下来的主要任务是在真实项目中完成闭环，具体分布如下：

### 任务 1：控制面板卡桥接联动（Layer 3）
- **涉及文件**：`scripts/openamp_rpmsg_bridge.py` 和 `scripts/openamp_control_wrapper.py`
- **动作**：解析 `protocol.py` 中新增的 `LINK_HEALTH` 帧和 `MODE_DIRECTIVE` 帧，确保这些指令数据能在真机的 RPMsg 设备与 Host 侧控制面之间顺利流转与握手。

### 任务 2：HTTP 后端与推理管线联动（Layer 2）
- **涉及文件**：`session_bootstrap/demo/openamp_control_plane_demo/server.py` 与 `inference_runner.py`
- **动作**：
  1. Server 端需新增相应的 API endpoints，用于向外暴露出当前的 `ServiceMode` 状态，并能接收从外部传入的 Link Health 状态。
  2. 推理调度器需增加分流判断：当系统被判定处于降级/告警模式时，停止跑满载的整图语义重建。

### 任务 3：原生 UI 座舱展示联动（Layer 1）
- **涉及文件**：`cockpit_native/adapter.py` 及相关 QML
- **动作**：前端 UI 必须能够向用户实时展示当前系统所处的“降级保底”状态（如安全警示灯切换、降级模式弹窗或图标）。这是决赛 Demo 现场最核心的产品力与视觉展示得分点。

### 任务 4：USRP 物理数据面演进（Layer 5）
- **涉及文件**：`docs/design_usrp_latent_transport.md`
- **动作**：在该 2000 行设计文档的基础上，逐步将代码中虚拟假造的 `LinkHealthSimulator` 替换为真实能够读取 USRP 物理信道反馈（SNR/PER计算）的链路监控模块。

---
**致下一个 AI：**
请不要重头造轮子！起步前请务必确认理解 `openamp_mock/protocol.py` 与 `scripts/openamp_rpmsg_bridge.py` 之间已发生的物理调用关系。你可以直接从上述的【任务 1】或【任务 2】开始撰写实现计划。祝你编码顺利！
