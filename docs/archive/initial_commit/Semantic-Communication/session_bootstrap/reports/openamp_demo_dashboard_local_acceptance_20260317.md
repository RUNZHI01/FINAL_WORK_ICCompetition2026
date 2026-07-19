# OpenAMP Demo Dashboard 本地启动验收（2026-03-17）

## 结论

已在本地完成一次最小启动验收，确认集成 dashboard 不只是代码已改，而是**实际运行后能够正确暴露 2026-03-17 最新 live 双路径状态**。

---

## 验收命令

```bash
bash ./session_bootstrap/scripts/run_openamp_demo.sh --port 8092
```

说明：
- 本次仅用于本地临时验收；
- 验收完成后已主动终止临时进程，避免后台残留 demo 会话。

---

## 验收结果

### 1. 健康检查

请求：

```text
GET /api/health
```

返回：

```json
{"status":"ok"}
```

结论：demo 服务可正常启动并响应本地健康检查。

### 2. Snapshot 检查

请求：

```text
GET /api/snapshot
```

本次重点核对字段：

```json
{
  "project_verdict": "P0 已板级闭环；P1 FIT-01 / FIT-02 / FIT-03 最终均为 PASS",
  "latest_live_status": {
    "report_date": "2026-03-17",
    "valid_instance": "8115",
    "current_completed": "300 / 300",
    "baseline_completed": "300 / 300",
    "report_path": "session_bootstrap/reports/openamp_demo_live_dualpath_status_20260317.md"
  },
  "docs_first": "session_bootstrap/reports/openamp_demo_live_dualpath_status_20260317.md"
}
```

结论：
- `latest_live_status` 已被 dashboard snapshot 正确暴露；
- 最新 live 状态摘要已经进入 dashboard 资料入口首位；
- 关键运行事实与 3/17 文档收口口径一致：
  - `8115` 是唯一有效实例；
  - `current` 最近 live 为 `300 / 300`；
  - `baseline` 最近 live 为 `300 / 300`。

---

## 对本轮收口的意义

这次本地验收补足了最后一层证据：

1. **文档入口已统一**；
2. **前端代码已接入**；
3. **snapshot / API 已实际返回最新状态**；
4. **本地启动路径可以工作**。

因此，2026-03-17 这轮“demo live 双路径状态”已经同时具备：
- 文档留档；
- 多入口可达；
- 答辩叙事接入；
- dashboard 用户可见；
- 本地运行验收通过。

---

## 边界说明

- 本次验收是**本地 dashboard 启动验收**，不是重新执行板端 current / baseline live run；
- `young-fjord` 会话随后收到的 `SIGTERM` 是**主动终止临时验收实例**的结果，不构成新的失败。
