# OpenAMP Mock

最小 OpenAMP 控制面 mock，专门服务于赛题对齐 P0/P1 首轮落地，不改现有 TVM trusted current 主流程。

## 包含内容

- `protocol.py`：协议常量、统一消息头、故障码、正式口径常量。
- `orchestrator.py`：Linux `orchestrator` 状态机。
- `guard.py`：RTOS `safety_guard` 状态机。
- `transport.py`：Linux mock transport。
- `demo.py`：最短闭环演示与证据生成入口。
- `tests/test_mock.py`：最小 unittest。

## 运行

```bash
python3 -m openamp_mock.demo --scenario all --output-dir session_bootstrap/reports/openamp_mock_examples/smoke_20260313_p0p1 --run-id openamp_mock_smoke_20260313_p0p1
python3 -m unittest discover -s openamp_mock/tests -t .
```

## 当前覆盖

- `JOB_REQ -> JOB_ACK(ALLOW)`
- `JOB_REQ -> JOB_ACK(DENY, F001/F002)`
- `JOB_REQ -> ALLOW -> HEARTBEAT timeout -> SAFE_STOP(F003)`
- `STATUS_REQ/RESP`
- `RESET_REQ/ACK`（测试覆盖，便于后续接 `TC-010`）
