# 设计文档：USRP B205mini Latent 数据面传输方案

> 状态：Draft / 待专家审查
> 日期：2026-04-12
> 目标版本：`usrp-latent-v1`
> 关联硬件：`USRP B205mini`
> 关联文档：
> - `session_bootstrap/reports/phytium_pi_b205mini_uhd_enablement_20260404.md`
> - `scripts/tcp_client.py`

---

## 1. 背景与结论

当前系统已经具备：

- 上位机将图像编码为 latent；
- 下位机接收 latent 后执行 TVM/MNN 解码；
- 现有 TCP / ML-KEM 控制链路可正常工作；
- 飞腾派上的 `USRP B205mini + UHD 3.15` 已安装并跑通官方例程。

当前缺口不是“模型怎么跑”，而是“如何让 USRP 数据面与现有语义通信模型的训练结构保持一致”。

本文档给出的结论是：

1. **控制面保持 TCP，不迁移到 USRP。**
2. **正式主线必须贴合论文中的 `GAN-based JSCC / LGJSCC-c3 / AWGN` 训练结构。**
3. **USRP 数据面首先要保护的是 semantic latent 的值域结构与重要性分布，而不是某个“文件字节流格式”。**
4. **`START/DATA/END + 字节流 framing + tx_samples_from_file/rx_samples_to_file` 只保留为当前 bring-up 实现映射，不再视为正式主线。**
5. **此前的 `CRC32 + TCP 缺块重传` 只适合作为 bring-up 阶段的实现手段，不应被当成“单次传输”正式方案。**
6. **若硬约束是不允许二次传输，则正式主线应切到“单次传输、低失真、训练一致性优先”模式：`semantic-latent-aware grouping + UEP + FEC + interleaving`。**
7. **若验收要求保密性，必须单独审查 `ML-KEM/AEAD` 与语义重要性保护的兼容性；二者并非天然一致。**

因此，本文档从这里开始明确区分两层：

- **正式主线：论文一致性优先的 USRP 数据面设计**
- **当前实现映射：基于现有 UHD 样例的序列化/帧化落地方式**

---

## 2. 已确认约束

### 2.1 系统边界

本方案固定采用以下边界：

- **控制面**：继续使用现有 TCP 链路，对下位机进行任务下发、模式配置、状态回报与错误处理；若处于 bring-up 落地阶段，可临时承担 ACK/NACK；
- **数据面**：USRP 负责 semantic latent 数据面传输；正式主线优先考虑值域/重要性结构一致性，当前实现层才在必要时退化成文件字节流；
- **结果回传**：暂不放到 USRP 上，仍由现有控制/结果链路承担。

### 2.2 当前 latent 输入事实

根据 `scripts/tcp_client.py`，当前上位机发送的数据模型是：

- payload：`latent_bytes`
- metadata：JSON，至少包含
  - `job_id`
  - `shape`
  - `dtype`
  - `sha256`
  - `size`
  - `run_tvm`
  - `expect_result`

当前常见 latent 形状：

- 现代格式：`1x32x32x32 float32`
- 兼容旧格式：`1x3x64x64 float32`

更关键的是：

- 结合既有 `jscc` 代码与历史工程，当前这份 latent 不是“普通中间特征”
- 它本身就是**语义通信模型 / DeepJSCC 增强路线**产出的编码结果

这会带来一个非常重要的约束：

- **USRP 数据面不能随意重写 latent 的表示方式；**
- **任何额外量化、重排、再编码，都可能破坏这份 latent 已经学到的语义几何结构。**

因此，USRP 数据面的正确职责不应简单理解成“只要把字节搬过去”，而应理解成：

- **尽量不破坏现有语义 latent 的 manifold / channel-aware structure；**
- **若要改表示，原则上应与编码器/解码器联合评估，最好联合重训。**

结合仓库内 [paper/CICC0903540初赛技术文档.md](/home/tianxing/tvm_metaschedule_execution_project/paper/CICC0903540初赛技术文档.md:143) 的说明，当前模型来源进一步明确为：

- 文献 [6]：**Lightweight Generative Joint Source-Channel Coding for Semantic Image Transmission with Compressed Conditional GANs**
- DOI：`10.1109/ICCCWORKSHOPS57813.2023.10233814`
- 论文入口：`https://ieeexplore.ieee.org/document/10233814/`

文档里给出的训练事实包括：

- 训练信道：`AWGN`
- 损失：`L_t = λ L_G + α L_MSE + β L_LPIPS`
- 训练流程：教师模型 → 通道压缩学生模型
- 当前落地模型：`LGJSCC-c3`

这意味着当前接收端 Generator 真正见过、也真正学过的扰动分布更接近：

- **latent 值域上的连续噪声扰动**

而不是：

- **序列化字节流上的离散 bit flip / burst corruption**

这对后续 USRP 方案是一个非常关键的设计约束。

### 2.3 UHD 官方例程能力边界

已验证通过的官方例程是：

- `rx_samples_to_file`
- `benchmark_rate`

但需要明确：

- `benchmark_rate` 的目标是速率/丢包压测，不带文件语义；
- `rx_samples_to_file` / `tx_samples_from_file` 的目标是收发 sample 流，不带文件分块、重组、完整性校验、重传控制。

所以官方例程只能证明：

- **B205mini 的 IQ sample 流链路已通**

不能直接证明：

- **latent 文件链路已经具备可用的数据包协议**

### 2.4 官方源码复核：它实际采用的数据结构是什么

2026-04-12 对 UHD 官方源码和官方手册做了复核。结论很明确：

- 官方例程的应用层输入输出不是“文件包”，而是**连续 IQ sample buffer**；
- 官方例程依赖的控制结构不是“自定义 payload header”，而是 **UHD streamer + metadata**；
- 官方例程没有提供适合直接传张量文件的 `job_id / chunk_idx / sha256 / size` 这类应用层字段。

本节对应的官方参考入口：

- `tx_samples_from_file.cpp`
  `https://raw.githubusercontent.com/EttusResearch/uhd/UHD-3.15.LTS/host/examples/tx_samples_from_file.cpp`
- `rx_samples_to_file.cpp`
  `https://raw.githubusercontent.com/EttusResearch/uhd/UHD-3.15.LTS/host/examples/rx_samples_to_file.cpp`
- `benchmark_rate.cpp`
  `https://raw.githubusercontent.com/EttusResearch/uhd/UHD-3.15.LTS/host/examples/benchmark_rate.cpp`
- UHD 手册 `Device streaming`
  `https://files.ettus.com/manual/page_stream.html`

#### 2.4.1 `tx_samples_from_file.cpp`

官方发射例程的核心逻辑是：

1. 按 `--type` 选择 host sample 类型：
   - `double -> std::complex<double>`
   - `float -> std::complex<float>`
   - `short -> std::complex<short>`
2. 用 `uhd::stream_args_t(cpu_format, wirefmt)` 创建 `tx_streamer`
3. 从文件中直接按 `sizeof(samp_type)` 读取原始二进制
4. 调用 `tx_stream->send(...)` 持续发送

关键点是：

- 文件内容被当作**纯样本数组**读取；
- 没有应用层帧头；
- 没有 chunk 索引；
- 没有 SHA / CRC；
- 也没有“文件开始/文件结束”以外的高级语义。

源码层面的直接证据：

- `send_from_file()` 用 `std::vector<samp_type> buff(samps_per_buff)` 建缓冲；
- `infile.read((char*)&buff.front(), buff.size() * sizeof(samp_type));`
- `tx_stream->send(&buff.front(), num_tx_samps, md);`

这说明官方 `--file` 的含义其实是：

- **“保存 IQ 样本的原始二进制文件”**

而不是：

- **“带业务帧格式的数据文件”**

#### 2.4.2 `rx_samples_to_file.cpp`

官方接收例程的核心逻辑是：

1. 用 `uhd::stream_args_t(cpu_format, wire_format)` 创建 `rx_streamer`
2. 用 `uhd::stream_cmd_t` 启动接收
3. 调用 `rx_stream->recv(...)`
4. 把收到的 sample 直接 `outfile.write(...)` 落盘

关键点是：

- 输出文件也是**纯样本数组**；
- 收到什么样本，就按当前 host 类型直接写什么二进制；
- 没有重组逻辑；
- 没有“缺块重传”；
- 没有任何针对文件语义的完整性校验。

源码层面的直接证据：

- `size_t num_rx_samps = rx_stream->recv(&buff.front(), buff.size(), md, 3.0, enable_size_map);`
- `outfile.write((const char*)&buff.front(), num_rx_samps * sizeof(samp_type));`

所以 `rx_samples_to_file` 证明的是：

- **样本流接收与落盘是通的**

而不是：

- **一个可直接承载 latent 文件的数据协议已经存在**

#### 2.4.3 `benchmark_rate.cpp`

官方压测例程的核心逻辑是：

1. 创建 `rx_streamer` / `tx_streamer`
2. 按 `get_max_num_samps()` 和 `get_bytes_per_item()` 分配原始缓冲
3. 持续 `send()` / `recv()`
4. 用 metadata 统计：
   - overrun
   - underrun
   - sequence error
   - timeout
   - dropped samples

它使用的数据结构仍然是：

- `std::vector<char>` 原始样本缓冲
- `uhd::rx_metadata_t`
- `uhd::tx_metadata_t`
- `uhd::async_metadata_t`
- `uhd::stream_cmd_t`

它没有：

- 文件分块语义；
- 文件头/帧头；
- payload CRC；
- 业务 ACK/NACK；
- 整文件重组。

因此，`benchmark_rate` 适合作为：

- **物理链路吞吐/稳定性验证工具**

不适合作为：

- **第一版 latent 文件协议的直接基座**

#### 2.4.4 官方例程真正依赖的几个结构体

从官方手册看，例程围绕下面几个结构工作：

1. `uhd::stream_args_t`
   - 定义 host 侧 `cpu_format`
   - 定义链路侧 `otw_format` / `wirefmt`
   - 可带 `channels`、`spp` 等参数
2. `uhd::tx_metadata_t`
   - 只描述 `has_time_spec / time_spec / start_of_burst / end_of_burst`
3. `uhd::rx_metadata_t`
   - 描述 `time_spec / start_of_burst / end_of_burst / fragment / error_code / out_of_sequence`
4. `uhd::stream_cmd_t`
   - 描述 `START_CONTINUOUS / STOP_CONTINUOUS / NUM_SAMPS_AND_DONE`

这些结构解决的是：

- 样本类型；
- 启停控制；
- 时间对齐；
- 突发边界；
- 传输错误报告。

这些结构**不负责**解决：

- 业务文件头；
- 张量元数据绑定；
- chunk 索引；
- 整文件校验；
- 缺块重传协商。

#### 2.4.5 对本方案的直接影响

因此，本方案的分层必须明确为：

1. **官方 UHD 层**
   - 负责收发 IQ sample buffer
2. **我们的文件协议层**
   - 负责 `START / DATA / END`
   - 负责 `stream_id / chunk_idx / file_sha256 / CRC32`
3. **现有 TCP 控制面**
   - 负责 metadata / ACK / NACK / missing_chunks

也就是说，我们不能把“张量文件打包格式”寄希望于：

- `tx_metadata_t`
- `rx_metadata_t`
- `stream_cmd_t`

因为它们的设计目标根本不是业务 payload 封装。

### 2.5 B205mini 官方硬件特性对方案的约束

结合 Ettus 官方产品页与 B200 系列手册，当前与本方案最相关的硬件事实是：

1. **B205mini 是 `1x1` 设备**
   - 对应一条 TX 链和一条 RX 链；
   - 不需要把方案设计成 MIMO 才能成立。
2. **支持 full duplex，但本方案第一版不需要吃满这个能力**
   - 因为控制面不走 USRP；
   - 第一版数据面采用单向文件突发更稳。
3. **板卡通过 USB 3.0 与主机连接**
   - 数据面稳定性不仅取决于射频，还取决于 USB 侧链路与 host 负载。
4. **模拟带宽上限为 56 MHz**
   - 这是硬件能力上限，不等于首版就应该跑到这个级别。
5. **支持 10 MHz / PPS 外部参考**
   - 如果后续要做多设备更严格的时间一致性或更长突发传输，这是重要扩展点。
6. **B200 系列手册明确提醒**
   - 多台 B2xx 同步时，推荐显式指定 `master_clock_rate`，不要完全依赖自动选择；
   - 默认 streaming 参数并不总是最优，若稳定性异常，可尝试在 device args 中设置 `recv_frame_size=1024`。

这些硬件特性带来的设计含义是：

- 第一版要优先选择**单通道、单向、短突发、保守采样率**；
- 先把“文件协议正确”与“物理层跑满性能”分离；
- 不要在没有外部参考和没有本地 TX/RX 实测闭环前，就假设可稳定跑长时间连续流。

### 2.6 你们仓库当前已经证明了什么，还没有证明什么

根据 `session_bootstrap/reports/phytium_pi_b205mini_uhd_enablement_20260404.md`，当前仓库内**已被证据证明**的是：

1. 飞腾派上的 UHD 3.15 安装完成；
2. `uhd_usrp_probe --args serial=31E74E3` 成功；
3. `B205mini` 工作在 `USB 3`；
4. `rx_samples_to_file` 在 `1 Msps` 通过；
5. `benchmark_rate --rx_rate 1000000 --duration 5` 在 `1 Msps` 下零丢样、零 overrun。

但当前**还没有在仓库证据里被证明**的是：

1. 飞腾派本机 `tx_samples_from_file` 真机发射通过；
2. 两端 B205mini 的 over-the-air 文件闭环；
3. `> 1 Msps` 的稳定空口文件传输；
4. 无外部参考条件下的长突发时钟漂移边界；
5. 数据面切到 `encrypted_bytes` 后的整体闭环。

因此，本文档后续所有“首版参数建议”都应理解为：

- **围绕当前已知硬件证据做保守扩展**

而不是：

- **默认硬件已经在你们现网环境里把所有能力都验证过**

---

## 3. 设计目标

### 3.1 必须达成

1. 能传输一个完整 latent 文件。
2. 接收端能检测丢块、错块、乱序和整文件损坏。
3. 与当前 TCP 控制面兼容。
4. 能在第一版中以最小代码改动复用官方 UHD 例程。
5. 方案能被后续专家继续审查和迭代。

### 3.2 明确不做

1. 第一版不把全部控制协议搬到无线侧。
2. 第一版不做双向 USRP 文件传输。
3. 第一版的最小 bring-up 可以暂不上复杂 FEC，但若正式目标是“单次传输、低失真”，则不能预先排除 `LDPC / Polar / Raptor / UEP / JSCC`。
4. 第一版不改 latent 内部张量格式。
5. 第一版不追求最终极限吞吐，优先保证 bring-up 成功率。

### 3.3 如果优先级从“快”切到“低失真”，且不允许二次传输，目标函数应该怎么改

如果项目当前更在意：

- **尽量不让传输过程引入重建失真**

且同时满足：

- **空口只有一次发送机会，不允许 ARQ / 二次传输**

那么本文档不再建议把目标函数写成“尽量 bit-perfect 后重传补齐”。
在这个约束下，更合理的目标是：

1. 令 `z` 为发送端 latent，`z_hat` 为接收端恢复 latent，`g(.)` 为下位机解码器；
2. 直接最小化任务侧失真：
   - `min E[ D( g(z_hat), g(z) ) ]`
3. 同时满足：
   - 单次发送功率约束
   - 单次发送带宽/时长约束
   - 允许的复杂度约束

这与此前“重传优先”的思路本质不同：

- 在单次传输约束下，**bit-perfect 不是默认可达目标，而只是一个上界愿景**；
- 真正要优化的是“误差如何最不伤 decoder”，而不是“错误后如何补发”；
- 因此，**raw `float32` 的等保护传输不是好目标**，因为它没有利用位重要性差异。

换句话说：

- **如果你现在更关心失真，而且不能重传，那么更先进的路线不是 ARQ，而是 `semantic-latent-aware` 的 UEP / FEC / JSCC。**

### 3.4 在“单次传输、低失真”约束下，真正的设计空间是什么

在这个约束下，方案大致分成三类：

1. **原始 `float32` + 等保护数字链路**
   - 优点：改动最小
   - 缺点：对指数位和符号位不敏感，失真表现通常最差
   - 结论：**不推荐作为正式方案**
2. **保持现有 semantic latent 结构的数字链路**
   - 典型做法：
     - 按 `channel / spatial tile / block` 切分 latent
     - 先评估“哪些通道、哪些空间块、哪些元素更重要”
     - 对高重要性组采用更强保护、更低码率、更低阶调制或更高功率
     - 若确有必要，再在组内细分 `sign / exponent / mantissa`
   - 优点：更尊重现有 semantic encoder 输出结构，且能保留现有 decoder
   - 结论：**这是当前工程最值得优先推进的路线**
3. **重新设计或重训的端到端 JSCC / Hybrid Digital-Analog / Semantic Transmission**
   - 典型代表：
     - DeepJSCC
     - WITT
     - GenerativeJSCC
     - SoftCast / SparseCast
   - 优点：更符合“单次传输 + 渐进退化”的先进方向
   - 缺点：通常要求重新训练或重写发端/收端表示接口
   - 结论：**这是长期最先进路线，不是当前仓库最低风险路线**

### 3.5 既然 latent 已经是 DeepJSCC 增强路线输出，这会改变什么

设：

- `z = E_theta(x)`，其中 `E_theta` 是你们现有语义通信编码器
- `x_hat = G_phi(z)`，其中 `G_phi` 是下位机解码器/生成器

那么当前真正敏感的对象不是某个独立 `float32` 数，而是：

- **整份 latent 在高维空间里的相对位置与结构**

这意味着：

1. 如果直接把 `z` 再改写成另一套数值表示，例如粗暴的 `int16 + scale`
   - 本质上是在额外施加一个 `Q(z)`
   - 实际走的是 `x_hat = G_phi(Q(z))`
2. 如果 `Q(.)` 没有经过联合训练或至少离线验证
   - 它可能把 latent 从原本学习到的 manifold 上推开
   - 导致的失真未必比信道误码更小

因此，当前项目的优先级应调整为：

1. **先保护现有 `z` 的结构**
2. **先做 tensor-domain importance protection**
3. **只有当实验明确证明 raw semantic latent 太脆弱时，才考虑改写表示并联训**

### 3.6 训练信道是 AWGN，这对 USRP 数据面意味着什么

从当前模型训练方式看，编码器/解码器学习到的基本关系更接近：

- `z_hat = z + n`
- 其中 `n ~ AWGN`

这意味着它更习惯看到的是：

- 连续值上的平滑扰动

而不习惯看到：

- 序列化字节中的离散 bit flip
- 稀疏但灾难性的 exponent/sign 翻转
- 长 burst 导致的局部字节块毁损

因此，对 USRP 数据面来说，最符合现有模型训练先验的方案排序应是：

1. **值域扰动尽量连续、近似 AWGN 的方案**
   - 更贴近现有模型训练分布
2. **若走数字链路，则必须把残余错误压到极低**
   - 避免把“连续噪声问题”变成“离散位翻转问题”
3. **不要默认接受少量 bit error 直接进 decoder**
   - 这类失真对当前模型是 distribution shift

这也是为什么：

- 如果未来可以接受更大系统改动，更应优先考虑“值域友好”的传输方式；
- 如果当前必须保留文件/分块/协议结构，那么就必须用更强的 `UEP + FEC + interleaving` 把 bit 级错误压下去。

---

## 4. 推荐总体架构（论文一致性主线）

### 4.1 主线原则

正式主线继续采用“**TCP 控制面 + USRP 数据面**”双层结构，但数据面的基本对象不再默认是“文件字节流”，而是：

- **现有 semantic encoder 输出的 latent 值域结构**
- **latent 在 `channel / tile / block` 维度上的重要性分布**

推荐主线结构如下：

```text
上位机
  ├─ TCP 控制面
  │    ├─ 下发 metadata / mode / profile / security policy
  │    ├─ 接收 ready / final_summary
  │    └─ 不参与正式模式下的无线补发
  │
  └─ USRP 数据面
       ├─ Encoder 输出 latent z
       ├─ importance profiler / grouper
       ├─ Class A/B/C protection mapper
       ├─ interleaver / FEC / modem
       └─ 发射

下位机
  ├─ TCP 控制面
  │    ├─ 进入接收态
  │    └─ 返回 final_summary / quality stats
  │
  └─ USRP 数据面
       ├─ 接收 / 同步 / soft estimate
       ├─ deinterleaver / FEC recovery
       ├─ group-wise latent reconstruction -> z_hat
       └─ Generator(z_hat) 重建图像
```

### 4.2 为什么正式主线应这样分

因为当前模型训练先验决定了：

1. Generator 更习惯接收“**连续值上的平滑扰动**”
2. 不习惯接收“**字节级离散错误**”
3. 因此正式主线更应关注：
   - `z -> z_hat` 的值域扰动形态
   - 各 latent group 的重要性保护
   - 是否仍与 `AWGN` 训练先验一致

这也意味着：

- TCP 继续负责轻量控制、模式下发与最终结果回收；
- USRP 数据面应优先承载“与模型一致的 latent 保护/映射逻辑”；
- 正式主线不应先从“文件怎么切块”出发，而应先从“`z_hat` 应该长成什么样”出发。

### 4.3 官方 UHD 代码在主线中的位置

如果考虑当前仓库里已经跑通的官方例程，那么它们在主线中的正确位置应是：

- **sample streaming 底座**

具体来说：

- `tx_samples_from_file` / `rx_samples_to_file` 解决的是“样本怎么稳定收发”
- 主线方案解决的是“semantic latent 应该如何分组、保护和映射”

因此后文涉及的任何：

- 字节流序列化
- 帧同步
- `START/DATA/END`

都只能理解成：

- **在当前官方样例约束下的一种实现映射**

而不是独立于主线之外的另一套方案。

---

## 5. 主线数据面抽象与当前序列化映射

### 5.1 主线数据面抽象

正式主线里，USRP 数据面真正要传输的对象不是“一个普通文件被切成很多 chunk”，而是：

- 语义通信编码器输出的 latent `z`
- 以及 `z` 在 `channel / tile / block` 维度上的重要性分组

因此，主线里的最小传输单元应理解为：

- **semantic group**

而不是：

- **file chunk**

每个 semantic group 至少应隐含这些属性：

| 字段 | 含义 |
|---|---|
| `group_id` | 当前 latent 分组编号 |
| `selector` | 该组对应的 `channel / tile / block` 范围 |
| `importance_class` | 重要性等级，如 `A/B/C` |
| `protection_profile` | 该组采用的 FEC / interleaving / modulation 档位 |
| `numeric_form` | 当前组是否保持 raw float、或进入组内 bit-plane 表示 |

### 5.1.1 `semantic group descriptor` 建议显式字段

为了避免后续实现时再退回“拍脑袋分组”，建议把每个 group 的描述进一步落成显式 descriptor。

推荐最小字段如下：

| 字段 | 含义 | 当前建议 |
|---|---|---|
| `group_id` | 本次发送中的组编号 | 单调递增、会话内唯一 |
| `selector_kind` | 分组选择器类型 | `channel_range / tile_range / hybrid` |
| `selector_payload` | 该组覆盖的真实 latent 区域 | 例如 `[c0, c1)`、`[h0:h1, w0:w1]` |
| `importance_score` | 离线 profiling 得到的连续重要性分数 | 用于排序和分档 |
| `importance_class` | 离散保护等级 | `A / B / C` |
| `numeric_form` | 数值表示形式 | 首版默认 `raw_float32_preserve_value_domain` |
| `protection_profile_id` | 该组绑定的保护档位 | 如 `uep_a_v1 / uep_b_v1 / uep_c_v1` |
| `symbol_budget_hint` | 该组可消耗的冗余/符号预算 | 用于 UEP 和码率分配 |
| `reconstruction_priority` | 接收端恢复优先级 | 通常与 `importance_class` 同序 |

其中最关键的是：

- `selector_kind + selector_payload` 决定“到底是哪一块 latent 被保护”；
- `importance_score + importance_class` 决定“保护强度该差多少”；
- `numeric_form` 决定“是否仍保持论文训练时更接近的值域扰动形态”。

对你们当前 `1 x 32 x 32 x 32` 的 latent，第一版推荐优先采用：

- `channel_major_g4_v1`

也就是：

- 先按 channel-major 切组；
- 每 `4` 个 channel 为一个基础组；
- 共得到 `8` 个基础 group；
- 只有在离线 profiling 证明“纯 channel 分组不够”时，再细化到 `tile_range` 或 `hybrid`。

这样做的原因是：

- 它最贴近当前 latent 的语义通道结构；
- 分组数不大，方便先做 importance profiling；
- 不会一开始就把实现复杂度推到 `tile x channel` 组合爆炸。

### 5.1.2 重要性分数与 `A/B/C` 默认分档

正式主线不应拍脑袋给 `A/B/C`，而应来自离线消融。

对一个候选 group `g`，推荐先在验证集上做：

- 屏蔽或加噪该 group；
- 观察重建图像指标下降量。

当前最贴近论文训练目标的首版分数可定义为：

```text
score(g) = 0.6 * norm(ΔLPIPS(g)) + 0.4 * norm(ΔMSE(g))
```

其中：

- `ΔLPIPS(g)` 表示扰动 group `g` 后的 LPIPS 劣化；
- `ΔMSE(g)` 表示扰动 group `g` 后的 MSE 劣化；
- `norm(.)` 表示在当前验证集上的归一化。

原因是：

- 论文训练目标里本来就显式包含 `LPIPS + MSE`；
- 先用这两个量定义重要性，比直接从裸 `IEEE754` 位级想象更贴合你们模型。

若当前还没有 profiling 数据，文档里的默认分档建议先写死为：

| 类别 | 默认占比 | 含义 |
|---|---:|---|
| `Class A` | `top 20%` | 最敏感组，优先保证失真最小 |
| `Class B` | `next 30%` | 中敏感组，兼顾失真与速率 |
| `Class C` | `remaining 50%` | 相对不敏感组，优先让渡冗余 |

这只是：

- **默认审查起点**

不是最终常数。

专家真正该审的是：

- `score(g)` 的定义是否和论文损失一致；
- `20/30/50` 是否被离线 profiling 支持；
- 是否存在某些 channel 明显应该单独升到 `Class A`。

### 5.1.3 `A/B/C` 到物理层保护的默认映射

在当前“不允许二次传输、目标是最小失真”的前提下，三档默认映射建议如下：

| 类别 | 默认保护目标 | 建议策略 |
|---|---|---|
| `Class A` | 尽量逼近 bit-perfect 或至少最小值域扰动 | 最强 FEC、最低码率、最深交织、最低阶调制、最高优先发送 |
| `Class B` | 控制失真但接受有限退化 | 中等 FEC、中等交织、保守调制 |
| `Class C` | 在吞吐约束下保留整体语义信息 | 弱保护、较高码率、但仍避免完全裸奔 |

若要把它进一步落成实现参数，可先按下面的默认口径审查：

| 类别 | `protection_profile_id` | 调制上限 | 说明 |
|---|---|---|---|
| `Class A` | `uep_a_v1` | `BPSK` | 优先稳，不先追频谱效率 |
| `Class B` | `uep_b_v1` | `QPSK` | 在保真和速率之间取中间值 |
| `Class C` | `uep_c_v1` | `QPSK` | 首版仍保持保守，不建议直接跳高阶 QAM |

这里故意没有把首版默认上限写成 `16-QAM`，原因是：

- 你们当前最重要的不是“先把空口速率冲高”；
- 而是“先让 `z_hat` 的统计扰动别偏离论文训练分布太远”。

### 5.1.4 主线抽象如何映射到当前 UHD 实现底座

把正式主线落到当前官方例程时，正确的映射顺序应是：

```text
latent z
-> semantic group descriptors
-> importance scoring / A-B-C classification
-> per-class protection mapping
-> channel encoder / interleaver / modem
-> IQ samples
-> UHD sample streaming loop
```

因此：

- `semantic group` 才是主线里的逻辑单元；
- `IQ sample stream` 才是官方例程真正接收的物理单元；
- 如果中间仍暂时退回 byte stream，那也只是这个链路里的一个序列化层，而不是主线本体。

这也是为什么当前正式主线的“打包格式”不应先定义成：

- `START/DATA/END`

而应先定义成：

- **semantic grouping + protection mapping**

只有当实现层为了复用当前 UHD 样例，仍需把它序列化成 byte stream 时，才需要下面这套“当前序列化映射”。

### 5.2 当前若采用 byte-stream over IQ，实现层如何序列化

本小节描述的不是独立方案，而是：

- **正式主线在当前官方 UHD 样例约束下的一种序列化实现方式**

也就是当底层仍采用“解调后的 byte stream + 应用层 framing”时使用。

除特别说明外，本文档中所有多字节整数统一采用**小端序**。

当前序列化映射里，USRP 数据面仍可传三类帧：

- `START`
- `DATA`
- `END`

其中：

- `START` 用于声明一次序列化传输上下文；
- `DATA` 用于承载序列化后的分组 payload；
- `END` 用于结束本次传输并触发收尾校验。

### 5.2.1 帧同步获取规则

本小节定义的是“**解调后的字节流上的序列化帧格式**”。

因此要把同步问题拆成两层：

1. **IQ -> 字节流**
   - 由下层 `modem wrapper` 负责；
   - 本文档不规定具体调制方式，但要求其最终输出连续、按字节对齐的 byte stream。
2. **字节流 -> 序列化帧**
   - 由本文档定义的 `magic + header_crc32 + payload_len + payload_crc32` 负责。

接收端推荐按如下方式做帧同步：

1. 在解调后的 byte stream 上滑窗搜索 `magic` 固定字节序列；
2. 命中后读取 32B 公共头；
3. 校验 `header_crc32`；
4. 若失败，则向后滑动 1 byte 继续搜索；
5. 若成功，则按 `payload_len` 读取 payload；
6. 校验 `payload_crc32`；
7. 若失败，则丢弃该候选并重新进入搜索态。

这意味着：

- `magic` 不是业务字段，而是**字节流同步锚点**；
- `header_crc32` 是防误同步的重要第二道门；
- 本协议默认允许在字节流中从任意位置重新获得帧边界。

### 5.3 当前序列化映射的公共帧头

所有帧采用统一小端序公共头：

| 偏移 | 大小 | 字段 | 说明 |
|---|---:|---|---|
| 0 | 4B | `magic` | 固定字节序列为 ASCII `USF1`，即 `0x55 0x53 0x46 0x31`；按小端 `uint32` 解释时数值为 `0x31465355` |
| 4 | 1B | `version` | 当前为 `1` |
| 5 | 1B | `frame_type` | `1=START, 2=DATA, 3=END` |
| 6 | 2B | `header_len` | 公共头长度，当前固定 `32` |
| 8 | 8B | `stream_id` | 本次无线数据流 ID，由控制面分配 |
| 16 | 4B | `seq_no` | 帧序号，从 `0` 单调递增 |
| 20 | 4B | `payload_len` | 后续 payload 长度 |
| 24 | 4B | `header_crc32` | 对偏移 `0..23` 的 CRC32 |
| 28 | 4B | `payload_crc32` | 对 payload 的 CRC32 |

说明：

- `stream_id` 用于把一次 USRP 传输和一次 TCP 任务绑定；
- `seq_no` 用于表示**无线发送顺序**，发现乱序与丢帧；
- `header_crc32` 让解析器先过滤坏头，再决定是否进入 payload 处理；
- `payload_crc32` 用于 chunk 级错误检测。

补充约定：

- 初次发送与重传发送都共享同一个 `stream_id`；
- 若某个 `DATA` chunk 被重传，则：
  - `chunk_idx` 保持不变；
  - `seq_no` 必须递增，反映这是后来再次发出的物理帧；
- 因此：
  - `chunk_idx` 表示**逻辑文件位置**
  - `seq_no` 表示**空口发送顺序**

### 5.4 `START` 帧 payload

`START` payload 固定 64B：

| 偏移 | 大小 | 字段 | 说明 |
|---|---:|---|---|
| 0 | 8B | `file_size` | 整文件字节数 |
| 8 | 4B | `chunk_size` | chunk 字节数，第一版固定建议 `1024` |
| 12 | 4B | `chunk_count` | 总 chunk 数 |
| 16 | 32B | `file_sha256` | 整文件 SHA-256 原始 32B 摘要 |
| 48 | 4B | `metadata_crc32` | 控制面 metadata JSON 的 CRC32 |
| 52 | 1B | `payload_kind` | `0=raw_latent_bytes`, `1=encrypted_bytes` |
| 53 | 1B | `fec_kind` | `0=none` |
| 54 | 2B | `reserved0` | 预留 |
| 56 | 8B | `job_tag` | `job_id` 的低 64 位哈希，便于日志核对 |

说明：

- `file_sha256` 让接收端最终按整文件做强校验；
- `metadata_crc32` 用于确认无线 payload 和 TCP metadata 未错配；
- `payload_kind` 为后续“直接发送 ML-KEM 密文”预留兼容位。

补充约定：

- `metadata_crc32` 的计算对象必须是：
  - 上位机在 TCP 控制面发出的**原始 metadata UTF-8 字节串**
  - 且计算发生在任何加密封装之前
- 下位机必须对：
  - 从 TCP 控制面解出的**原始 metadata UTF-8 字节串**
  - 在 JSON parse 之前直接计算 CRC32
- 不允许对 parse 后 JSON 重新序列化再计算 CRC32，否则会引入键顺序/空白差异。

另外：

- `job_tag` 固定定义为：
  - `SHA256(job_id UTF-8 bytes)` 的低 64 位
  - 仅用于日志核对和抓包定位，不参与安全决策。

### 5.5 `DATA` 帧 payload

`DATA` payload 由“固定子头 + chunk 数据”组成。

固定子头为 8B：

| 偏移 | 大小 | 字段 | 说明 |
|---|---:|---|---|
| 0 | 4B | `chunk_idx` | 从 `0` 开始的 chunk 索引 |
| 4 | 2B | `chunk_len` | 当前块有效数据长度 |
| 6 | 2B | `flags` | 预留，第一版固定 `0` |

紧随其后是：

- `chunk_data[chunk_len]`

说明：

- 最后一个 chunk 可小于 `chunk_size`；
- 接收端按 `chunk_idx` 直接写入重组缓冲区；
- `chunk_len + payload_crc32` 足以发现截断、篡改和局部误码。

补充约定：

- 同一个 `chunk_idx` 若在同一 `stream_id` 中收到多份 `DATA`：
  - 若前一份已通过 CRC，则保留第一份并忽略重复份；
  - 若前一份未通过 CRC，则接受后续通过 CRC 的份替换它；
- 第一版中 `flags` 仍固定为 `0`，不把重传轮次塞进无线头部；
- 重传轮次由 TCP 控制面日志记录。

### 5.6 `END` 帧 payload

`END` payload 固定 40B：

| 偏移 | 大小 | 字段 | 说明 |
|---|---:|---|---|
| 0 | 4B | `last_chunk_idx` | 最后一块索引 |
| 4 | 4B | `chunks_sent` | 本轮实际发出的 DATA 帧数量 |
| 8 | 32B | `file_sha256` | 与 `START` 中一致，用于收尾再确认 |

说明：

- `END` 到达后，接收端即可判断：
  - 是否块数齐全；
  - 是否整文件 SHA256 匹配；
  - 是否需要通过 TCP 请求重传。

### 5.7 当前序列化映射的数据结构不变量

从数据结构角度，这个协议必须始终满足以下不变量：

1. `chunk_count = ceil(file_size / chunk_size)`
2. 对任意 `DATA` 帧：
   - `payload_len = 8 + chunk_len`
   - `0 < chunk_len <= chunk_size`
3. 对最后一个 chunk：
   - `chunk_len = file_size - chunk_size * (chunk_count - 1)`
4. 对非最后一个 chunk：
   - `chunk_len = chunk_size`
5. 对同一 `stream_id`：
   - 逻辑文件位置由 `chunk_idx` 唯一确定
   - 空口发送顺序由 `seq_no` 唯一确定
6. `START.file_sha256 == END.file_sha256`
7. `START.file_size / START.chunk_size / START.chunk_count` 必须与控制面 metadata 一致

对当前主流 latent：

- `file_size = 1 x 32 x 32 x 32 x 4B = 131072 B`
- 若 `chunk_size = 1024 B`
- 则 `chunk_count = 131072 / 1024 = 128`

因此首版实现时，接收端内部最简单的数据结构可以直接定为：

- `bitset[chunk_count]` 或 `bool received[chunk_count]`
- `bytearray[file_size]`
- `crc_ok_count`
- `expected_sha256`
- `stream_id`

这也是为什么当前方案优先选 `1024 B`：

- 数学上是整除；
- 数据结构上是定长块；
- 调试时 `0..127` 的 chunk 索引也最直观。

### 5.8 数据结构角度：为什么 raw `float32` 对残余误码并不友好

如果目标是“允许少量残余 bit error，但希望图像失真尽量小”，那么原始 `float32` latent 并不是最稳的传输表示。

原因在于 IEEE754 `float32` 的结构是：

- `1 bit sign`
- `8 bit exponent`
- `23 bit mantissa`

这带来两个问题：

1. **指数位翻转非常危险**
   - 可能把数值放大/缩小很多个数量级；
   - 甚至可能直接变成 `Inf / NaN`
2. **误差不是有界的**
   - 同样是 1 bit 错误，落在不同位上的失真差异极大

所以从“失真最小化”角度看：

- 如果链路能靠 `CRC + 重传 + SHA256` 做到 bit-perfect，那么直接传 `float32` 没问题；
- 但如果你预期链路上会残留少量误码，那么 `float32` 不是一个好的“容错数据结构”。

这也意味着方案上应分成两条路：

1. **零失真路线**
   - 继续传原始 `float32` 字节
   - 但必须追求 bit-perfect 恢复
2. **有界失真路线**
   - 把 latent 改写成更稳的表示，例如：
     - `int16 + scale`
     - block floating point
     - 分块量化 + 每块独立 scale
   - 这样单 bit 错误的影响更容易被限制在局部块内

从数学上看，`float32` 的值可写成：

- `x = (-1)^s * 2^(e-127) * (1 + m / 2^23)`

这里：

- `s` 是 sign bit
- `e` 是 8-bit exponent
- `m` 是 23-bit mantissa

因此：

1. mantissa 第 `k` 位翻转，通常只会引入大约 `2^-(k+1)` 量级的相对误差；
2. exponent 某一位翻转，会把量级按 `2^delta` 成倍推走；
3. sign bit 翻转会直接把值映射到相反半轴。

所以如果仍坚持发送“数值表示”，那就不能再把所有 bit 看成等价。
但对你们当前项目来说，更高一层的事实是：

- **bit 重要性只是第二层；**
- **第一层其实是 latent 张量内部的语义重要性。**

### 5.9 如果仍保留数字链路，`float32` 更先进的打包方式是什么

如果你不打算直接跳到新的端到端 JSCC，而是希望尽量复用现有 semantic latent / decoder，那么比“裸传 IEEE754 字节流”更先进的做法应分两层：

第一层：**tensor-domain importance**

1. **先做 latent 分组**
   - 例如按 `channel`
   - 或按 `channel tile`
   - 或按固定大小 block
2. **先评估每组对重建质量的影响**
   - 可用离线消融
   - 可用梯度/敏感度
   - 可用 encoder 输出能量或方差做近似
3. **按语义重要性分级**
   - `Class A`：最重要
   - `Class B`：中等重要
   - `Class C`：次重要
4. **先对分组做 UEP / 功率分配 / 调制分配**
   - 这是当前项目最应该优先做的“先进保护”

第二层：**bit-domain importance**

在每个组内部，如果仍然保留 `float32`，再继续做下面这些：

1. **把重要字段拆开**
   - 方案 A：显式拆成 `sign / exponent / mantissa`
   - 方案 B：改成 `block floating`
   - 方案 C：改成 `int16 + shared scale`
2. **按重要性重新排序 bitstream**
   - 第一层：`shared scale / shared exponent / sign`
   - 第二层：mantissa 高位平面
   - 第三层：mantissa 低位平面
3. **对不同层做 UEP**
   - 第一层：最强保护
   - 第二层：中等保护
   - 第三层：最弱保护，必要时可裁剪
4. **对发送符号做交织**
   - 把 burst error 打散，避免集中打坏同一个 block 的关键信息

这类打包方式的关键点不在“字段更多”，而在于：

- **先把“哪些 latent 组更重要”暴露给物理层；**
- **再把“哪些 bit 更重要”暴露给信道编码和调制层。**

如果要给一个当前项目可落地的推荐顺序，我建议：

1. `channel / tile` 级 importance profile
2. 分组 UEP / 功率分配 / 调制分配
3. 组内 `float32` bit-plane UEP
4. 只有在离线验证通过后，才考虑 `block floating / int16 + scale`

---

## 6. 控制面协同方式

### 6.1 不改变“控制面保留 TCP”这个大原则

这里的“保持控制面不动”，不是字面上的“一行不改”。

更准确的定义应是：

- **会话建立、任务调度、模式下发、状态确认仍由 TCP 完成；**
- **不重新发明一套无线控制协议。**

对正式主线，metadata JSON 更应描述：

- 当前采用的 `transport_mode`
- 当前采用的 `importance_profile`
- 当前采用的 `fec / security policy`

正式主线建议最小扩展为：

```json
{
  "job_id": "demo_0001",
  "shape": [1, 32, 32, 32],
  "dtype": "float32",
  "sha256": "....",
  "size": 131072,
  "run_tvm": true,
  "expect_result": true,
  "transport": "usrp-semantic-v1",
  "usrp": {
    "mode": "paper_aligned_one_shot",
    "grouping_policy": "channel_major_g4_v1",
    "importance_profile": "channel_group_v1",
    "importance_metric": "delta_lpips_mse_v1",
    "class_thresholds": "A:top20%,B:next30%,C:rest",
    "numeric_mapping": "raw_float32_preserve_value_domain",
    "fec_profile": "uep_ldpc_v1",
    "security_policy": "control_plane_only"
  }
}
```

如果当前只是为了最小 bring-up 落地，才退回到：

- `transport = usrp-latent-v1`
- `stream_id / chunk_size / chunk_count / max_retx_rounds`

补充约定：

- 若当前实现仍采用序列化帧映射，则 `stream_id` 由上位机控制面生成；
- 推荐生成方式：
  - `uint64`
  - 每个 job 唯一
  - 可由 `time_ns ^ random64 ^ job_hash64` 组合而成；
- 只要求在一次演示/实验会话内不碰撞，不要求全局永久单调。

### 6.2 推荐控制时序

```text
1. 上位机 TCP 发送 metadata（含 transport_mode / importance_profile / sha256）
2. 下位机 TCP 回复 ready
3. 上位机启动 USRP 发送“经过 semantic grouping + protection mapping 后”的数据流
4. 下位机完成解调、去交织、纠错、重组，并恢复 `z_hat`
5. 下位机 TCP 回复
   - 正式主线：`final_summary`
   - 当前序列化映射：`ACK/NACK`
6. 若当前实现仍采用 `START/DATA/END + ARQ`，才进入缺块补发逻辑
7. 主线约束通过后，下位机进入现有 TVM/MNN 解码流程
```

上面这套时序描述的是统一抽象：

- 第 3 步发送的是“主线数据面映射结果”；
- 若当前实现仍是 `START/DATA/END + ARQ`，则第 5-6 步展开为 `ACK/NACK + 定向补发`；
- 若正式切到“单次传输、低失真”主线，则可以进一步收缩为下面这套严格 one-shot 时序：

```text
1. 上位机 TCP 发送 metadata（含 mode / representation / fec_profile）
2. 下位机 TCP 回复 ready
3. 上位机启动 USRP 发一次性编码后的数据流
4. 下位机完成解调、去交织、纠错、重组
5. 下位机返回 final_summary
   - 是否解码成功
   - 估计误块率 / 误码率
   - latent 侧校验结果
   - 图像重建质量指标（若可得）
6. 校验/重建通过后，下位机进入现有 TVM/MNN 解码流程
```

### 6.3 推荐控制面反馈格式

为避免后续实现时各写一套口径：

- 下述三类反馈主要对应当前 `START/DATA/END + ARQ` 序列化实现；
- 若正式切到“单次传输、低失真”主线，则应把 `ack/nack` 收缩成单个 `final_summary`，不再默认带 `missing_chunks`。

当前 `START/DATA/END + ARQ` 序列化实现建议最小固定三类反馈：

1. `ready`

```json
{
  "status": "ready",
  "job_id": "demo_0001",
  "stream_id": 12345678,
  "ready_timeout_ms": 5000
}
```

2. `ack`

```json
{
  "status": "ack",
  "job_id": "demo_0001",
  "stream_id": 12345678,
  "sha256_match": true,
  "bytes_received": 131072,
  "chunk_count": 128
}
```

3. `nack`

```json
{
  "status": "nack",
  "job_id": "demo_0001",
  "stream_id": 12345678,
  "sha256_match": false,
  "missing_chunks": [7, 18, 19],
  "detail": "3 missing chunks after pass 1"
}
```

### 6.4 发送端/接收端状态机

下述状态机对应当前 `START/DATA/END + ARQ` 序列化实现。
若正式采用“单次传输、低失真”模式，则发送端应删除 `TX_RETRY_PASS`，接收端应删除 `WAIT_RETRY_OR_ABORT`。

建议发送端状态机：

```text
IDLE
  -> SEND_METADATA
  -> WAIT_READY
  -> TX_INITIAL_PASS
  -> WAIT_FEEDBACK
     -> ACK => COMPLETE
     -> NACK => TX_RETRY_PASS
  -> WAIT_FEEDBACK
     -> ACK => COMPLETE
     -> NACK and retry_count < max_retx_rounds => TX_RETRY_PASS
     -> NACK and retry_count >= max_retx_rounds => ABORT
```

建议接收端状态机：

```text
IDLE
  -> RX_METADATA
  -> READY
  -> RX_STREAM_SEARCH_SYNC
  -> RX_START
  -> RX_DATA
  -> RX_END
  -> REASSEMBLE_AND_VERIFY
     -> PASS => ACK
     -> FAIL => NACK(missing_chunks / sha256_mismatch)
  -> WAIT_RETRY_OR_ABORT
```

### 6.5 当前序列化实现映射建议超时

| 参数 | 建议值 | 说明 |
|---|---:|---|
| `ready_timeout_ms` | `5000` | metadata 发出后等待下位机进入接收态 |
| `feedback_timeout_ms` | `10000` | 一轮空口发送后等待 ACK/NACK |
| `max_retx_rounds` | `3` | 控制面最多允许三轮补发 |

### 6.6 为什么当前序列化实现映射采用 TCP 缺块重传

这只对当前的 bring-up 实现映射成立，因为这样能把复杂度压到最低：

- 无线侧只做单向大流量发送；
- 可靠性由接收端统计后经 TCP 回传；
- 重传粒度直接按 `chunk_idx`；
- 不需要在第一版就引入双向无线交互。

---

## 7. 参数建议

### 7.1 正式主线默认参数优先级

正式主线真正应该先锁定的，不是 `chunk_size`，而是下面这些会直接决定 `z_hat` 长什么样的参数：

| 参数 | 当前默认值 | 说明 |
|---|---|---|
| `transport_mode` | `paper_aligned_one_shot` | 一次发送优先，不把 ARQ 当主线 |
| `grouping_policy` | `channel_major_g4_v1` | 首版以 `4-channel` 为基础组 |
| `importance_metric` | `delta_lpips_mse_v1` | 先与论文损失项保持一致 |
| `class_thresholds` | `A:20% / B:30% / C:50%` | 默认审查起点，后续由 profiling 校准 |
| `numeric_mapping` | `raw_float32_preserve_value_domain` | 首版不随意改写 semantic latent 表示 |
| `protection_mode` | `one_shot_uep` | 不默认依赖重传 |
| `interleave_policy` | `enabled` | 首版就启用，优先打散 burst error |
| `modulation_ceiling` | `QPSK` | 先保守，不让高阶调制先主导失真 |

这些参数的优先级高于：

- `chunk_size`
- `max_retx_rounds`
- `stream_id`

因为后者即便调得再漂亮，也只是当前某种序列化实现映射的细节，不能替代主线设计本身。

### 7.2 当前序列化实现映射参数

下面这组参数只服务于：

- `START/DATA/END` 字节流实现映射

它们不是当前正式主线的首要参数。

| 参数 | 建议值 | 原因 |
|---|---:|---|
| `chunk_size` | `1024 B` | 丢一个 chunk 的代价可控，重传粒度细，头部开销仍可接受 |
| `max_retx_rounds` | `3` | 足够覆盖 bring-up 阶段的偶发缺块 |
| `fec_kind` | `none` | 先保证链路打通，再决定是否加 FEC |
| `payload_kind` | `bring-up: raw_latent_bytes` / `secure demo: encrypted_bytes` | 仅适用于当前序列化映射，不代表正式主线最终安全口径 |

### 7.3 为什么当前实现映射先用 `1024 B`

它在第一版里是一个平衡点：

- 比 `256 B` / `512 B` 头部开销更低；
- 比 `4 KB` / `8 KB` 重传代价更低；
- 接收缓冲区管理简单；
- 后续如要改成 `2048 B` 或接入 FEC，协议不需要重写。

对于当前主流 latent 大小：

- `1 x 32 x 32 x 32 x 4B = 131072 B = 128 KiB`

采用 `chunk_size = 1024B` 时有一个额外好处：

- 恰好是 `128` 个 chunk，便于首版 bring-up 时观察、统计和人工核对。

### 7.4 首版硬件工作点建议

结合 B205mini 特性和你们仓库里当前已验证证据，首版建议工作点如下：

| 项 | 建议 | 原因 |
|---|---|---|
| 设备选择 | 固定 `serial=...` | 仓库已有记录表明比 `type=b200` 更稳 |
| 通道数 | 单通道 | B205mini 是 `1x1`，首版不引入多通道复杂度 |
| 方向 | 单向突发 | 控制面保留 TCP，不需要满双工 |
| host sample 类型 | `short` | 对应 `std::complex<short>`，最接近官方样例默认路径 |
| wire format | `sc16` | 首版优先稳定与兼容，不先压到 `sc8` |
| 初始采样率 | 从 `1 Msps` 起步 | 这是当前仓库里唯一已实证的板端稳定点 |
| device args | 如遇稳定性问题尝试 `recv_frame_size=1024` | 这是 B200 手册明确给出的优化建议 |
| 参考时钟 | 无明确外部参考时，按“每次文件传输重新捕获同步”设计 | 降低长突发漂移风险 |
| 模拟带宽 | 设为接近目标占用带宽，不要默认放到很宽 | 减少无谓噪声与干扰引入 |

额外建议：

- 第一阶段先验证 `RX-only`、再验证 `TX-only`、最后验证 `over-the-air TX->RX`；
- 不要直接把“协议打包”“调制细节”“高采样率冲性能”三件事绑在同一轮 bring-up 里。

### 7.5 当前序列化实现映射下的协议开销与速率预算

设：

- `S = file_size`
- `C = chunk_size`
- `N = ceil(S / C)`

则在 `usrp-latent-v1` 当前实现映射下，**一轮初始发送**的总字节数为：

```text
wire_bytes = S + N * 40 + 168
```

其中：

- 每个 `DATA` 帧固定额外开销 `32 + 8 = 40 B`
- `START` 总开销 `32 + 64 = 96 B`
- `END` 总开销 `32 + 40 = 72 B`
- `96 + 72 = 168 B`

对当前主流 latent：

- `S = 131072 B`
- `C = 1024 B`
- `N = 128`

则：

```text
wire_bytes = 131072 + 128 * 40 + 168 = 136360 B
overhead_bytes = 136360 - 131072 = 5288 B
overhead_ratio = 5288 / 131072 ≈ 4.03%
```

这个结果意味着：

- 纯协议头开销本身不大，约 `4.03%`
- 影响链路是否够用的真正大头，不是帧头，而是：
  - 采样率 / 调制方式
  - 是否重传
  - 是否加 FEC

### 7.6 传输速率要求

本节速率预算同样优先描述：

- `START/DATA/END` 字节流实现映射

如果后续正式主线改成值域友好的 symbol/value-domain 传输，本节数字只能作为“与文件字节流实现映射的对照参考”，不能直接等价套用。

要让无线链路不成为系统瓶颈，至少要覆盖你们当前已公开的两个性能口径：

1. `230.339 ms/image`
   - 对应 `4.3414 fps`
   - 仅裸 latent payload 速率约 `4.5523 Mbps`
   - 加上本文协议头后，首轮空口速率约 `4.7360 Mbps`
2. `134.617 ms/image`
   - 对应 `7.4285 fps`
   - 仅裸 latent payload 速率约 `7.7893 Mbps`
   - 加上本文协议头后，首轮空口速率约 `8.1036 Mbps`

如果再给重传预留 `10%` 空口预算，则：

- 对 `230.339 ms/image` 口径，需要约 `5.2622 Mbps`
- 对 `134.617 ms/image` 口径，需要约 `9.0040 Mbps`

这直接带来一个关键结论：

- **当前仓库里唯一被实证的 `1 Msps` 工作点，只够做 bring-up，不足以无压力承载当前系统吞吐目标。**

粗略按调制阶数估算，在不加 FEC、1 symbol ≈ 1 sample 的理想化近似下：

- `BPSK @ 1 Msym/s` 约 `1 Mbps`
- `QPSK @ 1 Msym/s` 约 `2 Mbps`
- `16-QAM @ 1 Msym/s` 约 `4 Mbps`

因此：

- `1 Msps + QPSK` 明显不够
- `1 Msps + 16-QAM` 也只勉强接近最低口径，且没有抗干扰余量
- 若要真正覆盖你们当前系统吞吐，最终要么：
  - 提高样本/符号率
  - 提高频谱效率
  - 减小 latent 大小
  - 或接受较低图像吞吐

### 7.7 如果目标是“最小失真”，且不允许二次传输，推荐路线会怎么变

若当前优先级是：

- **失真最小化**

而不是：

- **吞吐最优**

则推荐路线不再是“小 chunk + 多重传”，而应改为下面三档：

| 路线 | 核心思想 | 对现有系统改动 | 失真表现 | 当前建议 |
|---|---|---|---|---|
| A. raw `float32` + 等保护 | 裸传 IEEE754 字节，统一保护 | 最小 | 最差，容易被 exponent/sign bit 拖垮 | 不推荐 |
| B. semantic-latent-aware 数字链路 | `tensor-group importance + UEP + interleaving + FEC`，必要时组内再做 `float32` bit-plane 保护 | 中等 | 好，且更尊重现有 semantic latent | **推荐主线** |
| C. JSCC / Hybrid / Analog | 直接优化“信源到信道”的表示与映射 | 最大 | 最好，具备渐进退化 | 长期路线 |

如果当前只能在现有工程上继续推进，我建议的默认工作点是：

1. 不再把 `chunk` 理解为“重传单位”，而把它理解为“编码块 / 交织块”
2. 编码块长度控制在 `256~512 B` 级别，便于局部重要性保护
3. 调制优先 `BPSK / QPSK`
4. 引入强交织
5. 采用 `LDPC / Polar / Raptor` 这类单次传输友好的保护手段
6. 先建立 `channel / tile / block` 级 importance profile
7. 对 `Class A / B / C` 采用不同保护强度
8. 仅在离线验证明确受益时，才把 raw `float32` 改成：
   - `block floating`
   - 或 `int16 + shared scale`
9. 若愿意接受更大系统改动，再评估 DeepJSCC / WITT / SparseCast

因此，在“不允许二次传输”的前提下：

- **默认审查口径不应再是 `512 B chunk + 更多重传`，而应是 `semantic-latent-aware grouping + UEP + interleaving + one-shot FEC`。**

---

## 8. 如何把主线方案落到官方 UHD 代码上

### 8.1 官方例程在主线中的真正角色

基于当前对官方源码的复核，UHD 官方例程真正能稳定提供的是：

- **IQ sample streaming substrate**

它们不能直接提供的是：

- semantic latent 的重要性保护
- 论文一致的数据面语义
- 你们模型所需的 `z -> z_hat` 扰动控制

因此，官方例程在主线里的正确角色应是：

- **实现底座**

而不是：

- **独立方案分支**

同样地，不建议基于 `benchmark_rate` 开始，原因是：

1. 它的主目标是压测吞吐和 overrun/underrun；
2. 它不提供适合承载主线语义的稳定应用层边界；
3. 改完也不会比 `tx_samples_from_file` / `rx_samples_to_file` 更适合作为主线底座。

### 8.2 结合官方源码后，应如何理解“最小改动”

从官方源码可以看出，最稳定的复用边界其实是：

- **保留官方例程的 sample streaming 主循环**

而不是：

- **把主线语义硬塞进 UHD metadata**

更具体地说：

1. 官方例程对外真正稳定的输入是“原始样本数组文件”；
2. 官方例程对外真正稳定的输出也是“原始样本数组文件”；
3. 因此最小改动的关键，不是重写 `send()/recv()` 循环，而是：
   - 在它前面放主线的数据面映射逻辑
   - 在它后面放主线的数据面恢复逻辑

### 8.3 当前推荐的实现底座

当前第一版仍优先基于：

- `tx_samples_from_file`
- `rx_samples_to_file`

但这里的含义已经改成：

1. 它们负责“样本发出去/收回来”；
2. semantic latent 的分组、保护、映射在它们之外完成；
3. UHD 官方代码本体尽量不承载业务语义。

### 8.4 建议的主线最小落地方式

如果按照当前论文一致性主线落地，我建议最小拆成五个薄层：

1. `semantic grouper`
   - 输入：Encoder 输出 latent `z`
   - 输出：按 `channel / tile / block` 分组后的 semantic groups
   - 每组带上第 5.1.1 节定义的 descriptor
2. `protection mapper`
   - 输入：semantic groups
   - 输出：带 `importance_class / protection_profile_id` 的发送序列
3. `channel encoder / interleaver / modem`
   - 输入：发送序列
   - 输出：可交给 UHD 发射的 IQ 样本
4. `uhd example shell`
   - 直接调用官方样例进行发射/接收
5. `receiver reconstructor`
   - 输入：接收到的 IQ 样本
   - 输出：`z_hat`，再交给 Generator 重建

这样做的好处是：

- 官方例程继续只承担它最稳定的职责；
- 主线方案与论文训练结构的对应关系更清晰；
- 问题定位也更清楚，能分开看：
  - `semantic grouping/protection` 是否合理
  - `modem/FEC` 是否稳定
  - `RF/UHD` 是否稳定

---

## 9. 若当前实现采用序列化帧映射，接收端判定规则

本节只适用于：

- 当前实现仍采用 `START/DATA/END` 序列化帧映射

接收端在 `END` 后按以下顺序判定：

1. 公共头 CRC 是否全部通过；
2. 每个 `DATA` payload CRC 是否通过；
3. `chunk_idx` 是否覆盖 `0..chunk_count-1`；
4. 重组后总字节数是否等于 `file_size`；
5. 重组后 `SHA256` 是否匹配 `START.file_sha256`；
6. 若任一失败，则通过 TCP 返回 `missing_chunks` 或 `sha256_mismatch`。

推荐回报格式：

```json
{
  "status": "nack",
  "job_id": "demo_0001",
  "stream_id": 12345678,
  "missing_chunks": [7, 18, 19],
  "sha256_match": false,
  "detail": "3 missing chunks after first pass"
}
```

---

## 10. 与现有系统的兼容关系

### 10.1 与 `scripts/tcp_client.py` 的关系

当前 `tcp_client.py` 是：

- 先经 `send_encrypted(metadata, aad=b"metadata")`
- 再经 `send_encrypted(latent_bytes, aad=metadata)`

若迁到本方案，推荐演进为：

- **metadata 仍走现有 TCP/ML-KEM 控制面**
- **latent 的无线发送由 USRP 数据面承担，但发送对象应先经过主线的 `grouping / protection / modulation` 映射**

这样：

- 现有 JSON metadata 结构可复用；
- 现有 `job_id / shape / dtype / sha256` 语义不丢；
- 下位机只需多一个“从 USRP 接收并恢复 `z_hat`”的阶段。

### 10.2 与保密性目标的关系

这里存在一个必须明确的审查点：

- 如果项目当前只要求“先把无线链路打通”，那么 `payload_kind = raw_latent_bytes` 是最简单的 bring-up 模式；
- 如果项目要求“无线数据面也必须保持现有安全口径”，那么最终默认模式不应停留在 `raw_latent_bytes`，而应切换到 `payload_kind = encrypted_bytes`。

因此建议把安全口径理解成两种实现姿态：

1. `bring-up / lab mode`
   - `payload_kind = raw_latent_bytes`
   - 目标是尽快打通 USRP 物理链路、验证主线映射与接收恢复逻辑
2. `secure demo mode`
   - `payload_kind = encrypted_bytes`
   - 目标是保持“控制面不动”的同时，不让 latent 明文暴露在无线侧

这不是文档细节，而是实现前必须锁定的验收边界。

### 10.3 是否必须保持 `.bin/.npy/.npz` 文件格式不变

这里要区分两个层次：

1. **系统边界格式**
   - 推荐保持不变
   - 也就是 `tcp_client.py`、板端执行器、TVM/MNN 消费接口仍可继续接受当前 `.bin/.npy/.npz`
2. **无线数据面内部表示**
   - 不必等同于“原文件字节逐字发送”
   - 正式主线允许把 latent 先变成 `semantic groups -> protection mapping -> IQ`

因此当前更准确的建议是：

- **外部接口尽量保持不变**
- **无线内部表示不必被文件字节流束缚**

### 10.4 如何把现有 ML-KEM 安全链路叠到 USRP 数据面上

你在消息里写的是 `MLO`，但按仓库现状和代码实际，这里统一按 **ML-KEM** 处理：

- 当前真实存在的是 `ML-KEM-768 + AES/SM4-GCM`
- 对应实现位于：
  - `../ICCompetition2026/mlkem_link/`
  - `../ICCompetition2026/scripts/tcp_client.py`
  - `scripts/tcp_client.py`

#### 10.4.1 现有 ML-KEM 结构的关键点

当前 `SecureChannel` 的分层其实已经很适合迁到无线数据面：

1. **握手层**
   - `pk = 1184 B`
   - `ct = 1088 B`
   - 外层目前是 TCP `4B length + payload`
2. **数据层**
   - `send_encrypted(plaintext, aad)`
   - 输出 `EncryptedPayload.to_bytes()`
3. **AEAD 载荷结构**
   - `1B nonce_len + 12B nonce + ciphertext_and_tag`
   - 对 AES/SM4-GCM 来说，相对明文固定增加约 `29 B`

这意味着：

- **真正与传输介质耦合的是 `SecureChannel` 最外层的“怎么把字节发出去”**
- **而不是 ML-KEM/AEAD 本身**

#### 10.4.2 推荐叠加方式

推荐的安全叠加顺序是：

```text
metadata_bytes
  -> 仍走现有 TCP / ML-KEM 控制面

latent_bytes
  -> 用现有 ML-KEM 会话派生出的 AEAD key 加密
  -> 得到 EncryptedPayload.to_bytes()
  -> 再作为 USRP 数据面的输入，经过实际采用的数据面映射后上空口
```

也就是说，正确顺序应是：

```text
先加密，再分块，再上空口
```

而不是：

```text
先分块，再对每个 chunk 单独做一次新的 AEAD 加密
```

#### 10.4.3 为什么必须“先加密再分块”

因为这样有四个直接好处：

1. **最小改动**
   - 现有 `MLKEMSession / LinkEncryptor / EncryptedPayload` 基本不动
2. **AAD 绑定关系不变**
   - 继续使用 `metadata_bytes` 作为 AAD
3. **若当前实现仍保留分段发送，工程上更容易复用**
   - 不需要因为重复发送某段内容而重新加密、重新生成 nonce
4. **安全语义清晰**
   - 无线侧看到的永远是密文切片，而不是 latent 明文

#### 10.4.4 secure mode 下的尺寸影响

若对 `131072 B` 的 latent 做一次 AEAD 封装：

- `EncryptedPayload.to_bytes()` 额外固定增加约 `29 B`
- 得到总密文载荷约 `131101 B`

此时若仍采用 `chunk_size = 1024 B`：

- `chunk_count = ceil(131101 / 1024) = 129`

这比明文模式只多：

- `1` 个 chunk
- 以及极少量的帧头开销

结论是：

- **ML-KEM/AEAD 本身对当前 128 KiB 级 latent 的尺寸膨胀非常小**
- 真正决定链路是否够用的仍然是空口速率和重传率，而不是 AEAD 头部

#### 10.4.5 首版工程建议

建议分两步走：

1. `bring-up / lab mode`
   - 先用 `raw_latent_bytes`
   - 目标是验证 USRP 物理链路、主线映射与接收恢复逻辑
2. `secure demo mode`
   - 切到 `encrypted_bytes`
   - 沿用现有 ML-KEM 会话和 AAD 绑定逻辑
   - 空口只传经主线映射后的安全载荷

如果后续要进一步统一到“控制面 + 数据面共用一套 ML-KEM 会话”，建议的最小改动点是：

- 不重写 `kem/crypto/kdf/session`
- 只把 `secure_channel.py` 最外层的 transport 从 `socket recv/send` 抽象成可替换 transport
- 让 TCP 与 USRP 共享相同的加解密核心，但使用不同的底层 transport

### 10.5 从“单次传输 + 低失真”角度，ML-KEM 应该怎么用

如果当前硬约束是：

- **不允许二次传输**
- **仍希望尽量降低 latent 失真**

那么这里有一个必须明说的 tradeoff：

- **标准 `ML-KEM + AEAD` 的“先整体加密，再过信道”做法，与 `semantic-latent-aware UEP / JSCC` 并不天然兼容。**

原因很直接：

1. AEAD 后的 payload 在统计上接近均匀随机比特；
2. 一旦先整体加密，信道侧就看不见：
   - 哪些 bit 是 exponent
   - 哪些 bit 是 sign
   - 哪些 bit 更重要
3. 这样就无法再做真正有意义的：
   - 位重要性感知 UEP
   - 语义重要性功率分配
   - 渐进退化式 JSCC

因此，在“单次传输、低失真”目标下，必须把安全方案分成两条：

1. **安全优先路线**
   - 继续沿用 `ML-KEM + AEAD` 整体加密 payload
   - 但无线侧只能做传统数字纠错
   - 这条路保密性强，但会牺牲语义感知保护能力
2. **低失真优先路线**
   - `ML-KEM` 继续用于握手、身份认证、控制面安全
   - 数据面尽量保留“可见的重要性结构”
   - 让 UEP / JSCC / power allocation 能感知 block / scale / bit-plane 重要性
   - 这条路更利于单次传输低失真，但不能简单套“整份 latent 先 AEAD 再发”的旧思路

因此，当前项目必须尽早拍板：

- **到底是“payload 全密文优先”，还是“单次传输低失真优先”。**

如果让我从当前用户目标出发给推荐：

- **既然你现在明确说“不允许二次传输，而且更关心失真”，那么数据面不应再默认采用“整体 AEAD 后再一视同仁发送”的方案。**

---

## 11. 风险与后续扩展

### 11.1 第一版主要风险

1. 物理层调制/解调误码率高于预期，导致重传频繁；
2. 若 modem 层无法稳定输出字节对齐 byte stream，则上层 `magic + CRC` 帧同步无法工作；
3. 若一次传输窗口太长，TCP 控制面超时参数可能需要同步放宽；
4. 若下位机边收边写策略不当，可能引入额外缓存压力。
5. 若项目对保密性有硬要求，而实现仍停留在 `raw_latent_bytes`，则会与现有安全口径冲突。

### 11.2 当前未覆盖的边界条件

第一版实现前，至少要把下面这些边界条件在代码设计里定清楚：

| 场景 | 推荐处置 |
|---|---|
| `file_size == 0` | 控制面直接拒绝，不启动 USRP |
| `chunk_size == 0` 或 `chunk_count == 0` | 视为控制面参数错误，直接 reject |
| `DATA` 在 `START` 前到达 | 丢弃并保持搜索态 |
| `END` 在 `START` 前到达 | 丢弃并记一次协议异常 |
| `START.stream_id` 与控制面不一致 | 直接 abort 当前 job，回 `stream_mismatch` |
| `START.file_size/chunk_count` 与控制面不一致 | 直接 abort，避免错把别的文件拼进来 |
| `chunk_idx >= chunk_count` | 丢弃该帧并记协议异常 |
| `chunk_len > chunk_size` | 丢弃该帧并记协议异常 |
| 同一 `chunk_idx` 重复到达 | 保留第一份 CRC 正确的数据，后续只作重复统计 |
| `END` 已收到但缺块仍存在 | 进入 `NACK`，等待重传轮 |
| `feedback_timeout_ms` 到时仍无反馈 | 发送端按超时失败处理，不无限等待 |
| 接收端 `READY` 后长时间收不到 `START` | 回到 `IDLE` 并清空当前重组缓冲 |
| 上一轮残留字节进入下一轮 | 依靠 `magic + header_crc32 + stream_id` 过滤，并在 job 结束后清空上下文 |
| 连续两个 job 背靠背发送 | 必须以新的 `stream_id` 开新上下文，不复用旧缓冲 |
| 接收端正忙时收到另一个 job 的 metadata | 控制面直接回 `busy`，避免两个空口文件流互相污染 |

### 11.3 抗干扰要求

若当前主流 latent 采用：

- `file_size = 131072 B`
- `chunk_size = 1024 B`
- `chunk_count = 128`

则“整文件一次首传成功概率”和“单 chunk 错误率”之间的关系近似为：

```text
P_file ≈ (1 - p_chunk)^128
```

反推可得：

- 若希望首传整文件成功率 `>= 50%`
  - 则 `p_chunk <= 0.5401%`
- 若希望首传整文件成功率 `>= 90%`
  - 则 `p_chunk <= 0.0823%`
- 若希望首传整文件成功率 `>= 95%`
  - 则 `p_chunk <= 0.0401%`

对当前 `DATA` 帧，单帧总字节数约为：

- `32 + 8 + 1024 = 1064 B`
- 即约 `8512 bit`

若粗略按独立误码近似：

```text
BER ≈ p_chunk / 8512
```

则上面三个目标大致对应：

- `50%` 首传成功率：`BER` 量级约 `9.18e-7`
- `90%` 首传成功率：`BER` 量级约 `9.67e-8`
- `95%` 首传成功率：`BER` 量级约 `4.71e-8`

这给出一个很重要的工程结论：

- **只靠 CRC32 + 重传，可以支撑实验室 bring-up；**
- **但若要在更强干扰或更差 SNR 条件下追求高首传成功率，后续很可能需要再上交织/FEC/自适应调制。**

因此抗干扰策略建议分层为：

1. 若当前实现仍采用序列化映射
   - `magic + CRC32 + TCP NACK`
2. 正式主线优先层
   - `semantic-latent-aware grouping`
   - `UEP + interleaving + one-shot FEC`
   - 低阶调制优先
3. 后续增强层
   - 更强外层 FEC
   - 自适应调制与速率切换
   - 更贴近训练分布的 value-domain 映射

### 11.4 从“减小失真”出发的最终建议

如果你明确表示：

- “我不在意传多久，我更在意重建别失真”
- “而且不允许二次传输”

那么本方案的推荐主线应改成：

1. **放弃“ARQ 补救”作为默认前提**
   - 单次传输时，错误必须在第一次发送里被尽量吸收
2. **优先保护现有 semantic latent 结构**
   - 不要默认重写表示
3. **优先做 tensor-domain importance protection**
   - 先决定哪些 `channel / tile / block` 更重要
4. **再做 bit-domain UEP**
   - `scale / exponent / sign` 最强保护
   - mantissa 高位中等保护
   - mantissa 低位弱保护或可裁剪
5. **优先采用交织与强 FEC**
   - 把 burst error 打散
   - 让一次传输尽量具备“局部失真、逐级退化”特性
6. **调制优先保守**
   - 先 `BPSK / QPSK`
   - 再评估是否有足够链路预算去冲更高阶
7. **若离线验证证明现有 latent 本身数值脆弱，再考虑改写表示并联训**
8. **若愿意接受系统级改造，再考虑 DeepJSCC / WITT / SparseCast**
   - 这才是更接近“业内先进”的长期方向

因此，如果现在让我只给一个方向性结论：

- **你们这条链路要想在“单次传输”前提下最小化失真，首选不是“重传补齐”，也不是“先把 latent 改成另一套格式”，而是“围绕现有 semantic latent 的 group importance 做 UEP + FEC + 交织”，必要时再做组内 `float32` 保护或联合重训。**

### 11.5 预留扩展点

当前协议已预留：

- `version`
- `fec_kind`
- `flags`
- `payload_kind`

因此后续可以平滑扩展到：

- `encrypted_bytes` 直接过 USRP；
- 每 N 个 chunk 一组的轻量 FEC；
- 更大的 `chunk_size`；
- 更强的链路统计与自适应参数。

---

## 12. 专家审查时建议重点看什么

建议专家优先审以下问题：

1. 若保留当前序列化实现映射，`chunk_size=1024B` 是否适合当前板卡和预期调制方式；
2. `CRC32 + TCP 重传` 是否只应保留在 bring-up 阶段，而不应作为正式单次传输方案；
3. `START/DATA/END` 三帧模型是否只应保留为当前实现映射，而不是正式主线；
4. `stream_id + file_sha256 + metadata_crc32` 的绑定是否足够防错配；
5. 若保留当前序列化实现映射，当前采用“magic 扫描 + header_crc32”作为字节流同步锚点是否足够稳；
6. modem 层是否能稳定输出 byte-aligned stream，还是需要额外外层 framing；
7. `payload_kind=encrypted_bytes` 是否会破坏数据面 UEP / JSCC 能力，从而与“单次传输低失真”目标冲突；
8. 若正式模式不允许二次传输，控制面是否应移除 `missing_chunks / max_retx_rounds` 相关假设。
9. 若走当前实现映射，飞腾派本机 `tx_samples_from_file` 与真正 over-the-air TX/RX 是否需要先单独设一个硬件 gate；
10. 首版是否要强制采用 `serial=...`、`sc16`、`1 Msps` 这一保守工作点。
11. 当前 `1 Msps` 证据点与所需 `4.7~8.1 Mbps` 空口速率之间的差距，最终通过哪条路径填平；
12. 当前更适合的正式主线是：
   - `semantic-latent-aware digital UEP`
   - 还是直接进入 `DeepJSCC / WITT / SparseCast` 路线。
13. 如果当前最高优先级确实是“减少失真”，是否应把默认基线从“重传优先”切到“单次传输 UEP/FEC 优先”。
14. `ML-KEM` 在本项目中是否应只保留为控制面安全与握手，而不再对数据面做整体 AEAD。
15. 后续任何数据面设计是否都必须以论文中的 `GAN-based JSCC / LGJSCC-c3 / AWGN` 训练结构为上位约束，而不是凭空重造一套与训练分布不匹配的传输假设。

---

## 13. 当前决策

截至 `2026-04-12`，本文档锁定如下决策：

1. 控制面不迁到 USRP。
2. 第一版只传 latent 数据面，不传结果回传。
3. 正式主线不再默认以 `START/DATA/END` 三类帧为核心。
4. `START/DATA/END + chunk_size=1024B` 仅保留给当前最小 bring-up 实现映射。
5. 第一版不基于 `benchmark_rate` 魔改。
6. 若走当前实现映射，优先围绕 `tx_samples_from_file` / `rx_samples_to_file` 建立薄封装。
7. 当前实现映射明确区分：
   - `bring-up / lab mode`：`raw_latent_bytes`
   - `secure demo mode`：`encrypted_bytes`
8. 若当前阶段明确以“单次传输 + 失真最小化”为第一目标，则默认审查口径改为：
   - 不再以重传为主线
   - 优先 `semantic-latent-aware grouping`
   - 优先 `UEP + interleaving + one-shot FEC`
   - 优先 `BPSK / QPSK`
9. 当前工程的近期推荐主线是：
   - 先做 `channel / tile / block` 级 importance profile
   - 再做分组 `UEP + interleaving + one-shot FEC`
   - 仅在必要时再做组内 `float32` bit-plane 保护
10. 后续所有正式方案，必须优先贴合论文中的 `GAN-based JSCC / LGJSCC-c3 / AWGN` 训练结构；任何改变 latent 表示或扰动统计的方案，都必须先给出论文一致性论证，必要时联合重训。

---

## 14. 文档维护约定

后续如方案调整，建议只按以下方式维护：

1. 若只是参数变化，直接更新第 7 节与第 13 节。
2. 若当前实现映射的帧头字段变化，必须同步更新第 5 节的偏移表。
3. 若控制面交互变化，必须同步更新第 6 节时序图。
4. 若当前实现映射的基座从 `tx/rx_samples_from_file` 变更到其他官方例程，必须同步更新第 8 节。
5. 每次专家审查后的结论，追加到本文档末尾的“审查记录”。
6. 若硬件验证边界发生变化，例如“本机 TX 已通过”或“>1 Msps 已实证”，必须同步更新第 2.6 节与第 7.3 节。
7. 若 ML-KEM 接入方式变化，例如从“整体加密后发送”改成“仅控制面保留 ML-KEM、数据面暴露重要性结构”，必须同步更新第 10.4 节与第 12 节。

---

## 15. 审查记录

### 2026-04-12

- 初版成文。
- 已明确：控制面保留 TCP，USRP 仅负责 latent 数据面。
- 已明确：`benchmark_rate` 不作为第一版魔改基座。
- 待专家确认：`chunk_size`、是否第一版上 FEC、以及最终 framing / modem 细节。
- 已补充：对 `tx_samples_from_file.cpp`、`rx_samples_to_file.cpp`、`benchmark_rate.cpp` 的官方源码复核结论。
- 已修正：`magic` 的 ASCII/小端数值对应关系，固定为字节序列 `USF1`。
- 已补充：`metadata_crc32` 的精确定义，避免 JSON 重序列化导致错配。
- 已补充：发送端/接收端状态机、推荐超时和最小控制面反馈格式。
- 已补充：`bring-up / lab mode` 与 `secure demo mode` 的保密性边界。
- 已补充：B205mini 相关硬件约束、当前本地证据边界、首版硬件工作点建议。
- 已补充：第一版尚未覆盖的边界条件清单与推荐处置。
- 已补充：从数学角度推导协议开销、所需空口速率，以及 `1 Msps` 当前证据点与目标吞吐之间的差距。
- 已补充：从抗干扰角度量化 `chunk error rate / BER` 目标，并明确 CRC+重传仅适合作为首版 bring-up 基线。
- 已补充：ML-KEM 叠加方案，明确 secure mode 应采用“先加密、后分块、重传同一密文字节”的路径。
- 已补充：若项目当前更关心“减少失真”而非“更快传完”，则默认推荐切向更保守的低阶调制与单次传输保护口径。
- 已修正：此前“通过重传把误码挡在 decoder 外”的主线，只适用于 bring-up，不适用于“不允许二次传输”的正式目标。
- 已修正：既有 latent 本身就是语义通信模型输出，因此近期主线不应默认重写表示，而应先保护现有 semantic latent 的结构与重要性分布。
- 已补充：`ML-KEM/AEAD` 与数据面 UEP / JSCC 之间的结构性冲突，要求在“保密性优先”和“低失真优先”之间明确拍板。
- 已锁定：后续方案必须以论文中的 `GAN-based JSCC / LGJSCC-c3 / AWGN` 训练结构为上位约束，不再接受脱离模型训练先验的“想当然”传输方案。
- 已修正：文档结构已改成“正式主线（论文一致性优先）在前、当前实现映射（字节流 framing）在后”，避免把 bring-up 落地方式误写成正式方案。

---

## 16. 相关研究与业内路线参考

下面这些资料不是为了“照搬论文”，而是为了明确当前业界更先进的方向，避免把方案长期停留在“裸传 `float32` + 统一保护”的老思路里。

### 16.1 JSCC / Hybrid / Graceful Degradation 路线

1. DeepJSCC
   https://arxiv.org/abs/1809.01733
   代表性意义：把图像传输从“源编码 + 信道编码分离”改为端到端联合优化，是现代无线图像语义传输的起点之一。
2. DeepJSCC-Q
   https://arxiv.org/abs/2206.08100
   代表性意义：把 JSCC 拉回可用离散星座的实际系统，更接近 USRP 这类硬件约束。
3. WITT: A Wireless Image Transmission Transformer
   https://resourcecenter.ieee.org/conferences/icassp-2023/spsicassp23vid2465
   代表性意义：把 transformer 结构用于无线图像传输，强调语义提取与信道适配。
4. SparseCast
   https://arxiv.org/abs/1811.10079
   代表性意义：Hybrid Digital-Analog 路线，突出 graceful degradation，适合“不允许二次传输”的思路。
5. SoftCast
   https://people.csail.mit.edu/szym/softcast/tr2.pdf
   代表性意义：经典“随信道质量渐进退化”路线，适合理解为什么一次传输场景下不能只靠传统数字分离架构。

### 16.2 Importance-Aware / UEP / Interface 路线

1. Learning-Based Interface for Semantic Communication with Bit Importance Awareness
   https://arxiv.org/abs/2507.12850
   代表性意义：强调 bit-level importance interface，使网络层/信道层能感知 bit 重要性。
2. Channel Coding for Unequal Error Protection in Digital Semantic Communication
   https://arxiv.org/abs/2508.03381
   代表性意义：直接讨论数字语义通信里的 UEP channel coding，和本文档的 `float-aware digital UEP` 高度相关。
3. Toward Robust Semantic Communications: Proactive Importance-Ordered Restructuring for Enhanced Unequal Error Protection
   https://arxiv.org/abs/2604.00595
   代表性意义：不仅被动评估重要性，还主动重塑重要性分布，再联合优化特征选择、调制与功率分配。
4. Vision Transformer-based Semantic Communications With Importance-Aware Quantization
   https://arxiv.org/abs/2412.06038
   代表性意义：说明“重要性感知量化”已经成为现实可行路线，不一定必须全量端到端重训。
5. Importance-Aware Semantic Communication in MIMO-OFDM Systems Using Vision Transformer
   https://arxiv.org/abs/2508.07696
   代表性意义：把重要性感知进一步落到子载波映射和功率分配，说明先进方案的关键不是“多发几遍”，而是“资源按重要性分配”。

### 16.3 本文档对上述资料的工程化提炼

结合这些研究，本文档当前的工程结论是：

1. 如果 **允许大改系统并重训端到端模型**，长期最先进路线是 `DeepJSCC / WITT / Hybrid Analog`。
2. 如果 **希望尽量保留现有 semantic latent / decoder / TVM 执行链**，近期最合理路线是：
   - 先建立 `channel / tile / block` 级 importance profile
   - 做分组 `UEP + interleaving + one-shot FEC`
   - 仅在必要时再做组内 `float32` bit-plane 保护
3. 如果 **仍坚持 raw `float32` 裸字节整体加密后统一保护**，那基本就放弃了当前最有价值的“语义重要性感知”收益。
