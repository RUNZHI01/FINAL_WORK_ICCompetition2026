# 执行链路（客户端 / 服务端 / TVM优化）

## 1. 目标
把“调用从哪里发起、在哪里做优化、结果如何回传”拆成可核查步骤，今晚按此链路排障和落盘。

## 2. 总体调用链

1. 客户端准备请求：模型路径、shape、target、模式（quick/full）。  
2. 服务端接收请求并做参数校验（shape 合法性、target 一致性）。  
3. 服务端触发 TVM 优化入口（task 抽取 + MetaSchedule 调优/应用）。  
4. 若走 RPC：builder 在开发机，runner 在 ARM 真机测量。  
5. 优化完成后产出可执行模块 + tuning DB +关键指标。  
6. 服务端执行回归验证（延迟、稳定性），再返回客户端。  
7. 客户端将结果归档到报告与日志目录。

## 3. 分层细化

### 3.1 客户端层（发起与归档）

- 输入：模型版本、shape 桶、实验模式、预算。  
- 输出：任务请求、执行ID、结果摘要。  
- 失败信号：请求参数缺失、shape 未静态化、目标设备标识错误。

### 3.2 服务端层（编排与守护）

- 输入：客户端请求。  
- 行为：参数校验 -> 选择优化策略 -> 调用 TVM -> 收集指标。  
- 输出：状态码、优化产物路径、错误上下文。  
- 失败信号：RPC 未连通、编译工具链不一致、任务超时。

### 3.3 TVM 优化层（真正提速发生处）

- 输入：IRModule、target、runner配置、调优预算。  
- 行为：extract task -> search -> measure -> best schedule apply。  
- 输出：tuning DB、best trace、优化后 module。  
- 失败信号：候选质量低、测量噪声大、预算花在非热点。

## 4. 今晚可执行核查点（按顺序）

1. 核查请求参数是否固定（target/shape/线程数不能漂移）。  
2. 核查 quick 模式能在 40 分钟内完成并落盘。  
3. 核查 full 模式只包含热点 task（避免全量慢跑）。  
4. 核查 tuning DB 每轮可复用（不是每次从零开始）。  
5. 核查返回结果包含 baseline vs current 与方差信息。

## 5. 结果最小验收格式

```text
执行ID:
模式: quick/full
输入: model + shape + target
输出: baseline(ms) -> current(ms)
稳定性: P50/P90 或重复测量中位数
产物: tuning_db_path + report_path
是否可复现: 是/否（附原因）
```

## 6. 故障优先排查顺序

1. 连通性：tracker/server/runner 是否在线。  
2. 架构一致性：是否正确 AArch64 交叉编译。  
3. 数据正确性：是否调了错误 shape 或非热点 task。  
4. 噪声控制：设备负载、网络抖动、复测次数。  
5. 预算策略：是否错误使用全量长跑。
