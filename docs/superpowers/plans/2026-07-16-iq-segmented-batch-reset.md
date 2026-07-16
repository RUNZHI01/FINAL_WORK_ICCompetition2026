# IQ Segmented Batch Reset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make serial IQ-direct batches run as 30-image transport groups with RF boundary resets and failed-subset repair while preserving continuous and pipeline modes.

**Architecture:** `RunAnalogLatentBatch.py` remains the owner of transport ordering. Small pure helpers define segmentation, while the serial loop keeps one SSH master and decode worker alive, resets RX state between groups, and stores one final `ImageRecord` per source index. `usrp_runtime.py` maps Cockpit configuration to runner arguments; startup scripts set the quality-first defaults.

**Tech Stack:** Python 3, pytest, existing TCP control protocol (`STOP`, `STATUS`, `CAPTURE`, `WAIT`), PowerShell/Bash launch scripts, Cockpit Python backend.

## Global Constraints

- Default serial IQ-direct segment size is exactly `30`; the final group is not padded.
- `segment_size=0` preserves the previous continuous serial loop.
- Pipeline depth greater than one preserves the existing pipeline path and does not perform segmented resets.
- QPSK, security admission, remote decode worker lifetime, and final TVM invocation are unchanged.
- TVM starts only after every unique image passes the existing IQ quality gates.
- Existing working-tree changes in runner, tests, launch scripts, and docs must be preserved.

---

### Task 1: Segment Configuration And Pure Helpers

**Files:**
- Modify: `USRP292x/RunAnalogLatentBatch.py:151-410`
- Test: `USRP292x/test_analog_latent_link.py`

**Interfaces:**
- Produces: `iq_segment_size(args: argparse.Namespace, *, pipeline_enabled: bool) -> int`
- Produces: `iq_segment_repair_passes(args: argparse.Namespace) -> int`
- Produces: `partition_image_segments(images: Sequence[ImageRecord], segment_size: int) -> list[list[ImageRecord]]`

- [ ] **Step 1: Write failing parser and partition tests**

```python
def test_partition_image_segments_keeps_short_final_group():
    images = [ImageRecord(i, Path(f"{i}.bin"), Path(f"image_{i:04d}")) for i in range(35)]
    assert [len(group) for group in partition_image_segments(images, 30)] == [30, 5]

def test_iq_segment_size_zero_keeps_continuous_mode():
    assert iq_segment_size(Namespace(iq_segment_size=0), pipeline_enabled=False) == 0

def test_iq_segment_size_is_disabled_for_pipeline():
    assert iq_segment_size(Namespace(iq_segment_size=30), pipeline_enabled=True) == 0
```

- [ ] **Step 2: Run tests and confirm the helpers are missing**

Run: `python -m pytest USRP292x/test_analog_latent_link.py -k "partition_image_segments or iq_segment_size" -v`

Expected: FAIL because the new helpers do not exist.

- [ ] **Step 3: Add CLI options and pure helpers**

```python
parser.add_argument("--iq-segment-size", type=int, default=env_int("ANALOG_IQ_SEGMENT_SIZE", 30))
parser.add_argument(
    "--iq-segment-repair-passes",
    type=int,
    default=env_int("ANALOG_IQ_SEGMENT_REPAIR_PASSES", 1),
)

def iq_segment_size(args, *, pipeline_enabled):
    if pipeline_enabled:
        return 0
    return max(0, int(getattr(args, "iq_segment_size", 30) or 0))

def iq_segment_repair_passes(args):
    return max(0, int(getattr(args, "iq_segment_repair_passes", 1) or 0))

def partition_image_segments(images, segment_size):
    if segment_size <= 0:
        return [list(images)] if images else []
    return [list(images[start:start + segment_size]) for start in range(0, len(images), segment_size)]
```

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest USRP292x/test_analog_latent_link.py -k "partition_image_segments or iq_segment_size" -v`

Expected: PASS.

### Task 2: Boundary Reset And Failed-Subset Repair

**Files:**
- Modify: `USRP292x/RunAnalogLatentBatch.py:799-865,4973-5295`
- Test: `USRP292x/test_analog_latent_link.py`

**Interfaces:**
- Produces: `reset_iq_segment_boundary(args, session, log_path: Path) -> dict[str, Any]`
- Consumes: Task 1 segmentation helpers.
- Produces summary fields: `iq_segmented`, `iq_segment_size`, `iq_segment_count`, `iq_segment_repair_passes`, `iq_segment_repair_group_count`, `iq_segment_repaired_image_count`, `iq_segment_reset_count`, `iq_segment_reset_wall_sec`, and `iq_segment_resets`.

- [ ] **Step 1: Add a failing boundary-order test**

```python
def test_segment_boundary_closes_session_before_stop_and_checks_both_servers(tmp_path, monkeypatch):
    events = []
    class Session:
        def close(self):
            events.append("close")
    session = Session()
    args = Namespace(
        rx_control_host="rx",
        rx_control_port=29220,
        tx_control_host="tx",
        tx_control_port=29221,
        rx_timeout_sec=30.0,
    )
    monkeypatch.setattr(analog_batch, "stop_rx_capture", lambda *_a, **_k: events.append("stop") or "OK")
    monkeypatch.setattr(
        analog_batch,
        "run_control",
        lambda _h, port, line, *_a: events.append(f"status:{port}:{line}") or "OK busy=0",
    )
    record = analog_batch.reset_iq_segment_boundary(args, session, tmp_path / "reset.log")
    assert events == ["close", "stop", "status:29220:STATUS", "status:29221:STATUS"]
    assert record["ok"] is True
```

- [ ] **Step 2: Add failing serial-group behavior tests**

Test a five-image run with `iq_segment_size=2`, `max_arq_rounds=0`, and one repair pass. Make indexes 1 and 3 fail their normal group and pass only in repair. Assert processing order is `0,1,1,2,3,3,4`, four boundary resets occur, `completed_count == passed_count == 5`, and each index appears once in `summary["images"]`.

Add companion tests asserting:

```python
assert reset_count == 0  # iq_segment_size=0 compatibility mode
assert pipeline_function_called_once  # pipeline_depth=2
assert summary["iq_segmented"] is False
```

- [ ] **Step 3: Run the new tests and confirm failure**

Run: `python -m pytest USRP292x/test_analog_latent_link.py -k "segment_boundary or segmented_serial or continuous_mode_keeps or pipeline_keeps" -v`

Expected: FAIL because segmented orchestration is not implemented.

- [ ] **Step 4: Implement a strict boundary reset**

```python
def reset_iq_segment_boundary(args, session, log_path):
    started = time.monotonic()
    close_preconnected_control(session)
    clear_shared_rx_control_session(args, session)
    stop_rx_capture(args, log_path.with_name(f"{log_path.stem}_rx_stop.log"))
    rx_status = run_control(args.rx_control_host, args.rx_control_port, "STATUS", log_path, 5.0)
    tx_status = run_control(args.tx_control_host, args.tx_control_port, "STATUS", log_path, 5.0)
    if rx_control_response_busy(rx_status) or rx_control_response_busy(tx_status):
        raise RuntimeError("IQ segment boundary did not reach idle RF state")
    return {"ok": True, "wall_sec": time.monotonic() - started, "rx_status": rx_status, "tx_status": tx_status}
```

The real implementation must write separate RX/TX status logs so one command cannot overwrite the other. A failed idle check terminates the transport rather than publishing uncertain latent files.

- [ ] **Step 5: Refactor the serial loop into groups without duplicating final records**

Use `completed_by_index: dict[int, ImageRecord]`. Process each normal segment with the existing per-image ARQ loop, then process only failed records in each configured repair pass. Before every transition between normal and repair groups, or between adjacent normal groups, call the boundary reset. Keep `current_decode_attempt_index` local to each ARQ pass, but assign `round = len(image.records) - 1` after each attempt and annotate `segment_index`, `segment_pass`, and `segment_group_kind`.

At the end build:

```python
completed = [completed_by_index[index] for index in sorted(completed_by_index)]
```

Do not append a repaired image twice. Do not restart `RemoteAnalogDecodeWorker`, the SSH control master, or the security channel.

- [ ] **Step 6: Add summary evidence**

Store every reset record and aggregate its wall time. Record the configured size even when pipeline mode bypasses segmentation, plus an explicit `iq_segmented` boolean and `iq_segment_compatibility_mode` boolean. Keep existing `pass_count`, `fail_count`, `all_pass`, and image serialization unchanged.

- [ ] **Step 7: Run runner tests**

Run: `python -m pytest USRP292x/test_analog_latent_link.py -k "batch_runner or segment_boundary or partition_image_segments" -v`

Expected: PASS, including existing ARQ, RX health reset, shared SSH master, and pipeline tests.

### Task 3: Cockpit Runtime And Startup Defaults

**Files:**
- Modify: `Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/usrp_runtime.py:130-220,2460-2835`
- Modify: `Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/server.py`
- Modify: `Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py`
- Modify: `Semantic-Communication/cockpit_desktop/start-dev.sh`
- Verify only: `Semantic-Communication/cockpit_desktop/start-demo.ps1` delegates to `start-dev.sh`
- Modify: `docker/run-demo-tailscale.ps1`
- Modify: `docker/run-demo-tailscale.sh`
- Modify: `docker/start-electron-prod-demo.sh`
- Modify: `docker/test_demo_scripts.py`

**Interfaces:**
- Consumes environment keys `OPENAMP_IQ_SEGMENT_SIZE` and `OPENAMP_IQ_SEGMENT_REPAIR_PASSES`.
- Produces runner arguments `--iq-segment-size` and `--iq-segment-repair-passes`.

- [ ] **Step 1: Add failing runtime command tests**

Extend the IQ-direct command test to assert defaults:

```python
self.assertEqual(command[command.index("--iq-segment-size") + 1], "30")
self.assertEqual(command[command.index("--iq-segment-repair-passes") + 1], "1")
```

Add an override case with both values `0` and assert the command preserves them. Extend board-access default tests to assert both `OPENAMP_*` values.

- [ ] **Step 2: Run focused backend tests and confirm failure**

Run: `python -m pytest Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py -k "iq_direct_runner or usrp_iq_defaults" -v`

Expected: FAIL because the command does not include the new arguments.

- [ ] **Step 3: Map configuration into the runner command**

Add key tuples in `usrp_runtime.py`, read them only in the IQ-direct branch, and always append both arguments. In `server.py`, set defaults only when board access selects `transport_mode=usrp` and `jscc_link_mode=iq-direct`:

```python
if not str(env.get("OPENAMP_IQ_SEGMENT_SIZE") or "").strip():
    env["OPENAMP_IQ_SEGMENT_SIZE"] = "30"
if not str(env.get("OPENAMP_IQ_SEGMENT_REPAIR_PASSES") or "").strip():
    env["OPENAMP_IQ_SEGMENT_REPAIR_PASSES"] = "1"
```

Explicit `0` must survive because it selects compatibility mode.

- [ ] **Step 4: Set launch-script defaults and print them once**

For each Bash/PowerShell entrypoint, default the two variables to `30` and `1`, pass them into Docker, and include them in the existing IQ startup summary. Do not change QPSK defaults.

- [ ] **Step 5: Run backend and script tests**

Run: `python -m pytest Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py -k "iq_direct_runner or usrp_iq_defaults" -v`

Run: `python -m pytest docker/test_demo_scripts.py -v`

Expected: PASS.

### Task 4: Documentation And Full Software Verification

**Files:**
- Modify: `docs/README.md`
- Modify: `docs/HANDOFF.md`
- Modify: `docs/runbooks/STARTUP.md`

**Interfaces:**
- Documents normal defaults and the exact compatibility command.

- [ ] **Step 1: Document operational controls**

Add a concise table containing:

```text
OPENAMP_IQ_SEGMENT_SIZE=30             default serial IQ grouping
OPENAMP_IQ_SEGMENT_SIZE=0              previous continuous mode
OPENAMP_IQ_SEGMENT_REPAIR_PASSES=1     retry failed subset once after RF reset
ANALOG_PIPELINE_DEPTH=1                 quality-first serial mode
ANALOG_PIPELINE_DEPTH>1                 preserved experimental pipeline path
```

State that TVM and output publication still require all unique images to pass.

- [ ] **Step 2: Run formatting and targeted tests**

Run: `git diff --check`

Run: `python -m pytest USRP292x/test_analog_latent_link.py -k "batch_runner or segment or pipeline" -v`

Run: `python -m pytest Semantic-Communication/session_bootstrap/demo/openamp_control_plane_demo/tests/test_server.py -k "usrp or iq_direct" -v`

Run: `python -m pytest docker/test_demo_scripts.py -v`

Expected: all selected tests pass and `git diff --check` prints nothing.

### Task 5: Hardware Regression And Publication Audit

**Files:**
- Generated evidence only: `USRP292x/qpsk_batch_spool_arq_runs/<run-id>/batch_spool_summary.json`
- Generated evidence only: board reconstruction job directory

**Interfaces:**
- Proves the feature against the real USRP, board decoder, TVM runtime, and Cockpit output publication path.

- [ ] **Step 1: Run a 30-image Cockpit IQ-direct serial batch**

Expected: `30/30`, no TVM regression, one segment, zero boundary resets, quality metrics populated.

- [ ] **Step 2: Run a 35-image batch**

Expected: segment sizes `[30, 5]`, one normal boundary reset, `35/35`, and one reconstruction job containing 35 images.

- [ ] **Step 3: Run the required 300-image batch**

Expected: ten normal segments, recorded boundary reset timings, `passed_count=300`, `all_pass=true`, TVM processes 300 images, and the output directory contains 300 reconstruction images.

- [ ] **Step 4: Audit overhead and quality**

Compare transport wall time, reset wall time, radio attempts, PSNR, and SSIM against `cockpit_usrp_usrp-1784191178`. Boundary overhead must be reported separately; no rejected latent may reach TVM.

- [ ] **Step 5: Verify compatibility mode**

Run a short smoke batch with `OPENAMP_IQ_SEGMENT_SIZE=0`. Expected: `iq_segmented=false`, no segment reset records, and the old continuous serial path remains functional. Restore the default to `30` afterward.
