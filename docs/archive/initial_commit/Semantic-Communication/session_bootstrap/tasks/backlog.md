# Backlog（待办池）

> 2026-03-05 状态快照：P0 已闭环；RPC tune 闭环已建成；下一步拿可信 baseline。

## P0（已完成）

- [x] 固定 baseline：target、shape桶、线程、测量参数。  
- [x] 建立 quick 模式最小闭环（40分钟内有报告）。  
- [x] 提取热点 task Top 3-8（作为 full 唯一输入）。  
- [x] RPC tune 闭环（笔记本 builder/tracker + 飞腾派 runner）。

## P1（当前重点）

- [x] 接入 full 夜跑（仅热点）并确保日志可追溯。  
- [ ] 从飞腾派 SCP ONNX 模型到笔记本（`manage_rpc_services.sh prepare`）。  
- [ ] 跑通第一轮 RPC tune，拿到可信 baseline（QUICK_REPEAT >= 3）。  
- [ ] 用 `extract_tasks` 识别热点 task 并记录权重排序。  
- [ ] 验证 tuning DB warm-start 可用（第 2 轮 tune 复用第 1 轮 DB）。  
- [ ] 建立失败样本最小复现记录。

## P2（阶段 B：受控空间提速）

- [ ] 搜索预算梯度实验：500 → 1000 → 2000，记录收益曲线。  
- [ ] target mattr 实验：加/去 `+crypto,+crc`，看对热点 task 的影响。  
- [ ] TUNE_MAX_TRIALS_PER_TASK 实验：64 / 128 / 256。  
- [ ] 线程数实验：4 → 2 → 1。  
- [ ] 为每个 shape 桶形成独立对比报表。  
- [ ] 统计近7天单位时间收益（性能提升/调优小时）。

## P3（阶段 C：系统设计，收益变平后再做）

- [ ] 读 best trace，总结热点 task 的有效 schedule 模式。  
- [ ] 评估自定义 ScheduleRule 的可行性（NEON tiling 约束）。  
- [ ] 评估自定义 Postproc 的可行性（内存/crash 过滤）。

## P4（止损后转向）

- [ ] 评估 INT8 量化可行性（需要校准数据集）。  
- [ ] 评估部署优化（绑核、固定频率、内存池）。

详细路线图见：`runbooks/optimization_roadmap.md`。
