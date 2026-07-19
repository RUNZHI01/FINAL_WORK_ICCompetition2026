# OpenAMP Demo 最终彩排结果回填 / GO-NO-GO 模板（2026-04-03）

> 用途：在 presentation-day 或最终彩排后，把真实 UI / 板侧 / operator flow 结果按同一格式回填，避免任务板继续凭感觉勾完成。

---

## 1. 基本信息

- rehearsal_date:
- operator:
- machine / host:
- demo_build / commit:
- launch_command:
- probe_env_used:
- board_instance_expected: `8115`
- chosen_mode:
  - `L0 docs-first`
  - `L1 board-visible`
  - `L2 low-touch live`

---

## 2. 启动与健康检查

- page_load:
  - [ ] PASS
  - [ ] FAIL
- `/api/health`:
  - [ ] PASS
  - [ ] FAIL
- `/api/system-status` returns `operator_cue`:
  - [ ] PASS
  - [ ] FAIL
- notes:

---

## 3. 首屏 / Top-line Status 实测

### 3.1 实际看到的字段

- valid instance visible: `8115`
  - [ ] PASS
  - [ ] FAIL
- `Current 300 / 300` visible
  - [ ] PASS
  - [ ] FAIL
- `PyTorch reference 300 / 300 (archive)` visible
  - [ ] PASS
  - [ ] FAIL
- mode boundary visible (`4-core Linux performance mode` vs `3-core Linux + RTOS demo mode`)
  - [ ] PASS
  - [ ] FAIL
- trusted current SHA entry reachable
  - [ ] PASS
  - [ ] FAIL

### 3.2 口径风险检查

- did not mislabel baseline historical `300 / 300` as default live branch
  - [ ] PASS
  - [ ] FAIL
- did not turn `300 / 300` into `TC-010 / RESET_REQ/ACK` closure
  - [ ] PASS
  - [ ] FAIL
- did not mix headline performance with demo-mode live wording
  - [ ] PASS
  - [ ] FAIL
- notes:

---

## 4. 四幕执行结果

### Act 1
- session / password reuse path usable
  - [ ] PASS
  - [ ] FAIL
- read-only probe usable or honest evidence fallback applied
  - [ ] PASS
  - [ ] FAIL
- notes:

### Act 2
- preview-only gate wording stayed truthful
  - [ ] PASS
  - [ ] FAIL
- Current live branch usable, or honest degraded fallback used
  - [ ] PASS
  - [ ] FAIL
- notes:

### Act 3
- default compare stayed on archived `PyTorch reference`
  - [ ] PASS
  - [ ] FAIL
- only quoted `1846.9 -> 130.219 ms`
  - [ ] PASS
  - [ ] FAIL
- only quoted `1850.0 -> 230.339 ms/image`
  - [ ] PASS
  - [ ] FAIL
- did not use drift / degraded-board figures as headline
  - [ ] PASS
  - [ ] FAIL
- notes:

### Act 4
- replay vs live boundary stayed truthful
  - [ ] PASS
  - [ ] FAIL
- SAFE_STOP ownership wording stayed correct
  - [ ] PASS
  - [ ] FAIL
- notes:

---

## 5. 追问口径核对

- `TC-002` answered as live reconstruction closure only
  - [ ] PASS
  - [ ] FAIL
- `TC-010` kept as out-of-scope / not-claimed boundary
  - [ ] PASS
  - [ ] FAIL
- `FIT-01/02/03` safe to claim
  - [ ] PASS
  - [ ] FAIL
- `FIT-04/05` / `RESET_REQ/ACK` / sticky reset not overclaimed
  - [ ] PASS
  - [ ] FAIL
- notes:

---

## 6. 降级与切换结果

- fallback path needed:
  - [ ] NO
  - [ ] YES
- if YES, chosen fallback:
  - [ ] `L0 docs-first`
  - [ ] `L1 board-visible`
- fallback remained truthful and sufficient for defense:
  - [ ] PASS
  - [ ] FAIL
- notes:

---

## 7. 最终 GO / NO-GO 判定

### 建议判定

- [ ] GO：允许按当前版本上台
- [ ] GO_WITH_DOCS_FIRST_ONLY：允许上台，但默认不用低扰动 live cue
- [ ] NO_GO：仍需修正后再上台

### 判定理由

-
-
-

---

## 8. 对任务板的回填建议

### 可考虑勾完成的项

- [ ] 四幕 Demo 重构项可勾完成
- [ ] Demo 首屏显示项可勾完成
- [ ] Demo 对比页两条正式口径项可勾完成
- [ ] Demo 三个故障按钮项可勾完成

### 仍应保持未完成的项

- [ ] 四幕 Demo 重构项继续保留未完成
- [ ] Demo 首屏显示项继续保留未完成
- [ ] Demo 对比页两条正式口径项继续保留未完成
- [ ] Demo 三个故障按钮项继续保留未完成

### 回填说明（建议直接粘到任务板）

> 2026-__-__：基于最终彩排 / presentation-day 实测，已按 `openamp_demo_presentation_day_checklist_2026-04-03.md` 完成逐项核对。结论：________。因此将 ________ 标记为完成 / 保留未完成，理由：________。

---

## 9. 关联文档

- `session_bootstrap/reports/openamp_demo_presentation_day_checklist_2026-04-03.md`
- `session_bootstrap/reports/openamp_demo_open_items_split_2026-04-03.md`
- `session_bootstrap/reports/openamp_demo_topline_acceptance_note_2026-04-03.md`
- `session_bootstrap/reports/openamp_demo_video_script_alignment_2026-04-03.md`
- `session_bootstrap/reports/openamp_tc002_tc010_defense_scope_note_2026-04-03.md`
