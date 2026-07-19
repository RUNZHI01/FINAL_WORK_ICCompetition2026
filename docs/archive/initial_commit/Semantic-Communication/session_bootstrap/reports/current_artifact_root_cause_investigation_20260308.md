# Current Artifact Root Cause Investigation（2026-03-08）

## Scope

Investigated why the **current** artifact appears to make the remote Phytium-Pi unstable during quick recheck, using:

- `session_bootstrap/logs/quick_rpc_tune_recheck_20260308_151301.log`
- `session_bootstrap/reports/quick_rpc_tune_recheck_20260308_151301_raw.csv`
- `session_bootstrap/logs/quick_rpc_tune_20260308_031126.log`
- `session_bootstrap/reports/quick_rpc_tune_20260308_031126.md`
- related scripts under `session_bootstrap/scripts`

## Executive Summary

The most likely root cause is **not** ordinary SSH flakiness and **not** the March 8 target refresh itself.

The strongest evidence points to this interaction:

1. `run_remote_tvm_payload.sh` quick mode is a **tight repeated `tvm.runtime.load_module()` stress loop**, not a normal inference path. See `session_bootstrap/scripts/run_remote_tvm_payload.sh:118` and `session_bootstrap/scripts/run_remote_tvm_payload.sh:182`.
2. The rebuilt/current artifact deployed into the remote JSCC archive is a **much larger Relax/VM-style `.so`** than the legacy JSCC archive copy, and it behaves pathologically under repeated `load_module()`.
3. In the failed March 8 quick run, baseline completed 3/3, but current iteration 1 already slowed from the expected ~300 s budget to **483.7 s**, and current iteration 2 hit the outer timeout (`124`) after **2620.4 s**. See `session_bootstrap/reports/quick_rpc_tune_20260308_031126.md:16` and `session_bootstrap/reports/quick_rpc_tune_20260308_031126_raw.csv:5`.
4. The current artifact’s own remote summary is extremely abnormal: only **2927** loads in 300 s, median **2.402 ms**, mean **151.732 ms**, variance **53,234,330 ms²**. Baseline in the same run completed ~**1.38 million** loads at ~**0.21 ms**. See `session_bootstrap/logs/quick_rpc_tune_20260308_031126.log:141` and `session_bootstrap/logs/quick_rpc_tune_20260308_031126.log:184`.
5. Local same-arch reproduction on this AArch64 host shows the rebuilt `optimized_model.so` leaks/retains memory under repeated `load_module()` even with `del` + `gc.collect()`: about **816 KB/load**. Extrapolated to 2927 loads, that is about **2.33 GB** of process RSS growth.
6. The rebuilt March 8 artifact is **byte-identical** to the March 6 artifact (same SHA-256), so the instability is **not newly introduced by the `generic + neon` target refresh**.

Bottom line:

- The issue is **primarily a property of the current `optimized_model.so` under repeated module-loading**.
- The board instability is triggered by the **current quick execution path**, because that path repeatedly reloads the same problematic module for hundreds/thousands of rounds.
- The artifact does **not** look universally broken for normal one-shot use: the legacy path loads once and runs a `relax.VirtualMachine`, and a local one-shot VM load+run on the rebuilt `.so` succeeds.

## Evidence Chain

### 1) Quick recheck is not testing normal execution

The quick payload runner does not do end-to-end JSCC inference. In quick mode it selects one remote archive and then, inside Python, repeatedly does:

- `mod = load_module(so_path)`
- optional DB load
- stringify the module/type key
- loop until the wall-clock budget is exhausted

See:

- archive selection for quick baseline/current: `session_bootstrap/scripts/run_remote_tvm_payload.sh:82`
- SSH/local quick probe entry: `session_bootstrap/scripts/run_remote_tvm_payload.sh:118`
- repeated load loop: `session_bootstrap/scripts/run_remote_tvm_payload.sh:182`
- the same loop in the local branch: `session_bootstrap/scripts/run_remote_tvm_payload.sh:289`

Also, the exact March 8 run env explicitly disabled DB loading:

- `REMOTE_PAYLOAD_LOAD_DB=0` at `session_bootstrap/tmp/rpc_tune_output_20260308_phytium_target/rpc_tune_run_20260308_031126.env:70`

So the quick failure is **not** coming from JSON DB parsing and **not** from real inference. It is fundamentally a `load_module()` stress test.

### 2) The current quick path is definitely loading the rebuilt artifact

`run_rpc_tune.sh` deploys the freshly built `.so` and DB into `REMOTE_TVM_JSCC_BASE_DIR` before running quick:

- `session_bootstrap/scripts/run_rpc_tune.sh:229`
- `session_bootstrap/scripts/run_rpc_tune.sh:238`

That means quick current is not using a separate scratch artifact; it is probing the deployed current archive at:

- `/home/user/Downloads/jscc-test/jscc`

The current run log confirms that the current archive being probed is exactly that path:

- `session_bootstrap/logs/quick_rpc_tune_20260308_031126.log:184`

### 3) Baseline is stable; current is the only path that degrades

The report and raw CSV for the main failure show:

- baseline completed all 3 repeats successfully
- current completed only 1 repeat successfully
- current repeat 2 timed out with exit code `124`

See:

- `session_bootstrap/reports/quick_rpc_tune_20260308_031126.md:16`
- `session_bootstrap/reports/quick_rpc_tune_20260308_031126.md:25`
- `session_bootstrap/reports/quick_rpc_tune_20260308_031126_raw.csv:2`
- `session_bootstrap/reports/quick_rpc_tune_20260308_031126_raw.csv:5`
- `session_bootstrap/reports/quick_rpc_tune_20260308_031126_raw.csv:6`

The corresponding log shows the same sequence:

- baseline summary emitted normally: `session_bootstrap/logs/quick_rpc_tune_20260308_031126.log:141`
- current iteration 1 started: `session_bootstrap/logs/quick_rpc_tune_20260308_031126.log:142`
- current iteration 1 summary emitted: `session_bootstrap/logs/quick_rpc_tune_20260308_031126.log:184`
- current iteration 2 started: `session_bootstrap/logs/quick_rpc_tune_20260308_031126.log:185`
- current iteration 2 eventually failed with timeout: `session_bootstrap/logs/quick_rpc_tune_20260308_031126.log:227`
- the trailing `Broken pipe` is consistent with the outer timeout/SSH disconnect, not a primary root cause: `session_bootstrap/logs/quick_rpc_tune_20260308_031126.log:228`

This isolates the problem to **current**, not to baseline, not to generic SSH reachability, and not to the recheck wrapper itself.

### 4) The current artifact’s load behavior is wildly abnormal even before timeout

Inside the current iteration-1 JSON summary:

- current archive: `/home/user/Downloads/jscc-test/jscc`
- rounds: `2927`
- median: `2.402 ms`
- mean: `151.732 ms`
- variance: `53234330.101994 ms²`

See `session_bootstrap/logs/quick_rpc_tune_20260308_031126.log:184`.

Compare that with baseline in the same run:

- rounds: `1384736`
- median: `0.209 ms`
- mean: `0.212 ms`

See `session_bootstrap/logs/quick_rpc_tune_20260308_031126.log:141`.

Interpretation:

- Baseline behaves like a tiny/stable module load.
- Current has a long tail so severe that its mean explodes to ~152 ms/load despite a low median.
- That pattern fits **memory growth / allocator pressure / repeated heavy initialization**, not a normal steady-state module load.

The outer elapsed time also matches this interpretation:

- `2927 * 151.732 ms ≈ 444.6 s`, close to the observed `483.7 s` for current iteration 1 (`session_bootstrap/reports/quick_rpc_tune_20260308_031126_raw.csv:5`).

So the remote JSON summary is internally consistent with the wall-clock slowdown.

### 5) The recheck artifacts are incomplete but consistent with “current phase destabilizes things”

The recheck raw CSV contains only baseline rows and no current row at all:

- `session_bootstrap/reports/quick_rpc_tune_recheck_20260308_151301_raw.csv:2`
- `session_bootstrap/reports/quick_rpc_tune_recheck_20260308_151301_raw.csv:4`

The recheck log shows:

- baseline iteration 3 completes and prints JSON at `session_bootstrap/logs/quick_rpc_tune_recheck_20260308_151301.log:141`
- current iteration 1 begins at `session_bootstrap/logs/quick_rpc_tune_recheck_20260308_151301.log:142`
- then no current JSON summary, no report file, and no raw CSV row for current

This means the recheck evidence is incomplete, but it still points in the same direction as the earlier full failure: the run gets through baseline and then stops being well-behaved when it enters **current**.

### 6) The rebuilt artifact itself shows a repeated-load memory growth problem locally

I ran a local AArch64 reproduction using the same rebuilt file:

- rebuilt artifact: `/home/tianxing/tvm_metaschedule_execution_project/session_bootstrap/tmp/rpc_tune_output_20260308_phytium_target/optimized_model.so`
- 500 repeated `tvm.runtime.load_module()` calls in one process
- no DB load
- only stringifying the module, matching the quick payload’s behavior

Observed for the rebuilt artifact:

- size: **2,054,440 bytes**
- median load: **0.74 ms**
- mean load: **0.785 ms**
- RSS samples: `152960 KB` after 1 load → `520192 KB` after 451 loads
- approximate slope: **816 KB/load**

Observed for the legacy JSCC archive copy:

- file: `/home/tianxing/TVM_LAST/finalWork/服务端/jscc-test/jscc/tvm_tune_logs/optimized_model.so`
- size: **69,320 bytes**
- median load: **0.029 ms**
- RSS stayed flat over 500 loads

I also reran the rebuilt-artifact probe with explicit `del mod` and `gc.collect()` every iteration; the RSS still climbed linearly, so this does **not** look like a simple Python-reference issue.

Projected effect using the local slope:

- `2927 loads * 816 KB/load ≈ 2.33 GB`

That is in the same order of magnitude as “board becomes unstable / slow / times out” on a small ARM device.

### 7) The rebuilt artifact is not universally broken for normal one-shot execution

The legacy JSCC runtime path loads the module once, constructs a VM once, and then runs inference many times:

- load once: `TVM_LAST/finalWork/服务端/jscc-test/jscc/tvm_001.py:33`
- `load_module`: `TVM_LAST/finalWork/服务端/jscc-test/jscc/tvm_001.py:36`
- `relax.VirtualMachine`: `TVM_LAST/finalWork/服务端/jscc-test/jscc/tvm_001.py:37`
- `main` invocation: `TVM_LAST/finalWork/服务端/jscc-test/jscc/tvm_001.py:83`

That is materially different from the current quick probe.

I also ran a local one-shot VM check on the rebuilt March 8 artifact:

- `load_module`: **1.967 ms**
- `relax.VirtualMachine(...)`: **43.119 ms**
- one `main` run on zero input `(1,32,32,32)`: **742.865 ms**
- output shape: `(1, 3, 256, 256)`

So the rebuilt `.so` can be loaded and executed normally at least once on AArch64. That argues against “the `.so` is simply corrupt” and toward “the quick repeated-load method is the trigger path.”

### 8) The March 8 target refresh is probably not the actual cause

The March 8 rebuild report says it rebuilt using:

- `target = generic + neon`: `session_bootstrap/tmp/rpc_tune_output_20260308_phytium_target/tune_report.json:3`
- existing DB from March 6: `session_bootstrap/tmp/rpc_tune_output_20260308_phytium_target/tune_report.json:13`

The March 6 run used:

- `target = generic + neon + crypto + crc`: `session_bootstrap/tmp/rpc_tune_output_20260306_195752/tune_report.json:3`

However, the produced `.so` files are byte-identical locally:

- 2026-03-08 `optimized_model.so` SHA-256: `9478c8277b013ccbcae9dabaf72dd123efc7908405a359b951d7c85f780b8df8`
- 2026-03-06 `optimized_model.so` SHA-256: `9478c8277b013ccbcae9dabaf72dd123efc7908405a359b951d7c85f780b8df8`

So the evidence says:

- removing `+crypto,+crc` on March 8 did **not** materially change the binary
- the quick/current instability is therefore **older than the target refresh**
- the March 8 rebuild mainly reproduced the same current artifact from the existing DB

## Most Likely Root Cause(s)

### Primary root cause

The **current rebuilt `optimized_model.so` has pathological repeated-load behavior** under `tvm.runtime.load_module()`.

Evidence:

- remote current quick summary is orders of magnitude worse than baseline
- local same-arch reproduction shows strong RSS growth under repeated loads
- the problem persists even with explicit Python cleanup

### Secondary trigger / amplifier

The **current quick/recheck execution path is specifically designed in a way that amplifies this artifact weakness**:

- it does repeated `load_module()` in one process for a 300-second budget
- it does not resemble the legacy JSCC real execution path, which loads once and then runs VM calls
- once the current artifact starts inflating memory / latency, the board can drift into allocator pressure, swap, or OOM-adjacent behavior, which then manifests as long hangs and eventual timeout / SSH disconnect

### Things that are unlikely to be the main cause

- **DB loading**: disabled via `REMOTE_PAYLOAD_LOAD_DB=0`
- **plain SSH flakiness**: baseline succeeds repeatedly in the same sessions; the break happens only after switching to current
- **the March 8 `generic + neon` target refresh**: rebuilt binary is identical to the March 6 binary
- **a universally broken `.so`**: one-shot local VM load+run works

## Is the problem in `optimized_model.so` itself or in the execution path?

Most accurate answer: **both, but not equally**.

- The **artifact** is the deeper problem, because current-vs-baseline divergence is already visible in raw `load_module()` cost and local memory-retention behavior.
- The **execution path** is the trigger that turns that artifact property into remote instability, because quick mode repeatedly reloads the module thousands of times instead of loading once and running normally.

So I would classify it as:

- **artifact-level pathological behavior under repeated load**: yes
- **normal one-shot inference path obviously broken**: no strong evidence
- **quick recheck implementation making a bad situation much worse**: yes

If forced to assign blame:

- **~70% artifact behavior**
- **~30% probe design / execution path**

## Smallest Safe Remote Experiments To Confirm

Do **not** rerun the current 300-second quick probe first. Use these smaller checks instead.

### Experiment 1 — 5-load RSS probe, baseline vs current

Purpose:

- confirm whether current alone shows per-load RSS growth and latency blow-up on the remote board
- keep the risk low by limiting to 5 loads

Run current:

```bash
bash ./session_bootstrap/scripts/ssh_with_password.sh \
  --host 100.121.87.73 --user user --pass user -- \
  'export SO=/home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so; \
   /home/user/anaconda3/envs/tvm310/bin/python - <<"PY"
import gc, os, time, tvm
from tvm.runtime import load_module

def rss_kb():
    with open("/proc/self/status", "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("VmRSS:"):
                return int(line.split()[1])
    return -1

path = os.environ["SO"]
print({"path": path, "rss_kb_before": rss_kb()})
for i in range(5):
    t0 = time.perf_counter()
    mod = load_module(path)
    _ = str(getattr(mod, "type_key", mod))
    dt_ms = (time.perf_counter() - t0) * 1000.0
    del mod
    gc.collect()
    print({"iter": i + 1, "elapsed_ms": round(dt_ms, 3), "rss_kb": rss_kb()})
PY'
```

Run baseline by changing only `SO`:

```bash
/home/user/Downloads/5.1TVM优化结果/tvm_tune_logs/optimized_model.so
```

Expected confirmation:

- baseline stays roughly flat
- current shows visible RSS growth and/or rapidly worsening latency even within 5 loads

### Experiment 2 — fresh-process single-load probe repeated 5 times

Purpose:

- distinguish “artifact is broken even for one load” from “same-process repeated load is the real trigger”

```bash
bash ./session_bootstrap/scripts/ssh_with_password.sh \
  --host 100.121.87.73 --user user --pass user -- \
  'for i in 1 2 3 4 5; do \
     /home/user/anaconda3/envs/tvm310/bin/python - <<"PY"
import time, tvm
path = "/home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so"
t0 = time.perf_counter()
mod = tvm.runtime.load_module(path)
_ = str(getattr(mod, "type_key", mod))
print(round((time.perf_counter() - t0) * 1000.0, 3))
PY
   done'
```

Interpretation:

- if these 5 fresh-process loads are all fine, but Experiment 1 is bad, then the main problem is **same-process repeated load behavior**
- that directly validates the current quick path as unsafe for this artifact

### Experiment 3 — one-shot VM load + one dummy run

Purpose:

- verify whether the rebuilt `.so` is usable in the intended “load once, then run” mode
- safer and much more representative than the quick load-only stress loop

```bash
bash ./session_bootstrap/scripts/ssh_with_password.sh \
  --host 100.121.87.73 --user user --pass user -- \
  '/home/user/anaconda3/envs/tvm310/bin/python - <<"PY"
import numpy as np, time, tvm
from tvm import relax

path = "/home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so"
dev = tvm.device("llvm", 0)
inp = tvm.runtime.tensor(np.zeros((1, 32, 32, 32), dtype="float32"), dev)

t0 = time.perf_counter()
lib = tvm.runtime.load_module(path)
t1 = time.perf_counter()
vm = relax.VirtualMachine(lib, dev)
t2 = time.perf_counter()
out = vm["main"](inp)
t3 = time.perf_counter()
print({
    "load_ms": round((t1 - t0) * 1000.0, 3),
    "vm_init_ms": round((t2 - t1) * 1000.0, 3),
    "run_ms": round((t3 - t2) * 1000.0, 3),
    "shape": list(out.shape),
    "dtype": str(out.dtype),
})
PY'
```

Interpretation:

- if this succeeds quickly and the board remains responsive, then the artifact is **not generally unusable**
- it confirms the instability is specific to the quick repeated-load method

## Recommended Immediate Action

Until the above experiments are done, I would treat this as an operational safety rule:

- **Do not run `run_quick.sh` current mode against this artifact with the 300 s repeated-load loop.**

If a quick validation is needed right now, prefer:

- one-shot load + one VM run
- or multiple fresh-process single-load checks

Both are far safer than the current same-process repeated `load_module()` loop.

## Final Assessment

The most likely explanation is:

- the deployed/current `optimized_model.so` is a large Relax/VM artifact that exhibits **abnormal memory-retaining repeated-load behavior**
- `run_remote_tvm_payload.sh` quick mode is **exactly the wrong stress pattern** for that artifact, because it reloads the module thousands of times in one process
- this combination is sufficient to explain the remote board becoming slow/unresponsive during quick recheck
- the March 8 target refresh itself is very unlikely to be the culprit, because it reproduced the same binary as March 6

So the issue is **not mainly “the board is unstable”** and not mainly “SSH is flaky.” It is much more likely:

> current artifact has a bad repeated-load profile, and the present quick/recheck path turns that into apparent remote instability.

## Follow-up Confirmation (2026-03-08 16:40)

### Experiment A — fresh-process single-load repeated 5 times on remote

Result:

- baseline: all 5 runs succeeded, each around `0.55-0.57 ms`
- current: all 5 runs succeeded, each around `4.12-4.17 ms`
- both variants were stable when **each load happened in a fresh Python process**

Key observation:

- current is slower per one-shot load, but it did **not** spiral or accumulate instability across fresh processes
- this strongly narrows the main trigger to **same-process repeated load behavior**, not "the artifact instantly breaks on first load"

### Experiment B — one-shot VM load + one dummy run on remote

Result:

- current: succeeded
  - `load_ms = 9.393`
  - `vm_init_ms = 4.554`
  - `run_ms = 2586.618`
  - `shape = [1, 3, 256, 256]`
  - `dtype = float32`
- baseline: not directly comparable in this probe, because it is not a Relax VM artifact (`Module has no function 'vm_load_executable'`)

Interpretation:

- the current artifact is **usable in the intended one-shot load + VM run path**
- therefore the strongest diagnosis is now:
  - **artifact has pathological same-process repeated-load behavior**
  - **quick/recheck currently stresses exactly that unsafe path**
  - **normal one-shot use is not obviously broken**

## Updated Practical Conclusion

For this artifact family, the current `run_quick.sh -> run_remote_tvm_payload.sh` quick validation method should be treated as unsafe because it reloads the module many times inside one long-lived process.

Safer validation choices are:

1. fresh-process single-load repeated a few times
2. one-shot `load_module()` + `relax.VirtualMachine(...)` + one dummy run
3. avoid same-process repeated `load_module()` loops for the current artifact unless the loader behavior is redesigned
