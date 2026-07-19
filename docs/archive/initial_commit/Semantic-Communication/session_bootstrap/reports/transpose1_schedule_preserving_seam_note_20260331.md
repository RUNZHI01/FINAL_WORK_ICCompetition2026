# Transpose1 Schedule-Preserving Evaluation Seam Note

- operator: `fused_conv2d_transpose1_add9`
- status: `design_only`
- scope: `contract-side next step after 758e4bf`
- recommended next implementation target: `post_db_scheduled_primfunc_swap`

## Why this note exists

The current handwritten evaluation seam for `fused_conv2d_transpose1_add9` is now
explicitly labeled `diagnostic_raw_pre_compile_replacement`. That path proved the
checked-in candidate can be consumed by `rpc_tune.py`, but it also changed the
workload structure enough to miss the existing best-staging MetaSchedule records.

The next step should therefore preserve as much schedule context as possible
before any new operator-side candidate work (`v1`) is attempted.

## Local evidence collected

Using the existing best-staging artifact directory
`session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315`:

1. `relax_integration.extract_tasks()` still exposes an extracted task named
   `fused_conv2d_transpose1_add9` from the tuned-stage Relax module.
2. For that exact extracted task, the staged JSON DB can answer all three of:
   - `query_tuning_record(...)`
   - `query_ir_module(...)`
   - `query_schedule(...)`
3. `query_schedule(...).mod` is structurally equal to `query_ir_module(...)` for
   this task, and the recovered schedule trace is non-trivial (`trace len = 68`).
4. `MetaScheduleApplyDatabase` applied to the full tuned-stage Relax module still
   leaves a named global `fused_conv2d_transpose1_add9` in the resulting module,
   and that function is already marked `tir.is_scheduled = True`.

These points matter because they show the schedule-aware boundary already exists
in the current toolchain. We do **not** need to invent a new abstract hook from
scratch.

## Option A — keep using raw pre-compile replacement

### Shape
Replace the target PrimFunc before `compile_relax()` using handwritten source TIR,
which is what the current handwritten path does.

### Pros
- already implemented
- easy to reason about mechanically
- useful for integration and structural validation

### Cons
- loses workload identity relative to the staged DB
- does not preserve best-staging MetaSchedule schedule context
- payload/runtime numbers become `non_comparable_diagnostic_only`

### Verdict
Keep only as a diagnostic path. Do not use for future candidate-performance
judgment.

## Option B — query the DB at extracted-task granularity

### Shape
Use the extracted task for `fused_conv2d_transpose1_add9` as the lookup key and
recover the best staged result with `query_ir_module(...)` or `query_schedule(...)`.
Then perform a handwritten comparison or replacement against that recovered,
**already scheduled** task module.

### Pros
- uses the same workload boundary MetaSchedule tuned
- preserves the best staged schedule context as the reference object
- gives a narrow seam at operator granularity instead of whole-module surgery
- can be validated locally before any remote run

### Cons
- not yet wired into the repo’s handwritten path
- needs a careful contract for what “replacement” means when the baseline module
  is already scheduled
- may require a temporary operator-only evaluation helper before integration into
  `rpc_tune.py`

### Verdict
This is the narrowest honest seam currently visible in the repo.

## Option C — apply DB to the full module, then swap the scheduled global

### Shape
Run `MetaScheduleApplyDatabase` on the full tuned-stage Relax module first. Then
find `fused_conv2d_transpose1_add9` in the resulting module and swap only that
already-scheduled global for handwritten evaluation.

### Pros
- stays close to the final full-module compilation path
- preserves schedule context for the untouched operators
- local evidence shows the named global still exists post-DB and remains
  individually addressable

### Cons
- semantics are trickier than Option B because the handwritten candidate must be
  compared against an already scheduled PrimFunc, not the raw extracted task
- a naive swap may still invalidate assumptions baked into the scheduled form
- more integrated, therefore harder to debug than Option B

### Verdict
This is a strong second step, but it is slightly less minimal than Option B for
first implementation.

## Recommended next implementation target

Implement a **local-only operator probe/helper** for
`fused_conv2d_transpose1_add9` that:

1. reconstructs the tuned-stage Relax module from the known ONNX + target inputs
2. extracts the task named `fused_conv2d_transpose1_add9`
3. queries the staged DB for `query_ir_module(...)` and `query_schedule(...)`
4. confirms the recovered scheduled task module can be located and inspected
5. defines the future contract boundary as:
   `schedule_context_preserving_evaluation = compare/replace against DB-recovered scheduled task module`

After that helper exists and is stable, the next code step should be one of:

- **B1:** operator-level scheduled-task comparison helper (no full `rpc_tune.py`
  integration yet)
- **B2:** wire `rpc_tune.py` to route a handwritten candidate through the
  DB-recovered scheduled task seam instead of the current raw pre-compile seam

Update: `104fe46` already proved the DB-recovered scheduled seam is mechanically
reachable. `18cb4ae` then proved the helper can compare that scheduled
reference against the checked-in handwritten candidate module and report that a
future post-DB scheduled swap is structurally plausible.

The next concrete milestone is to perform that swap on the post-database full
module in-memory and verify the swapped module still remains locally buildable.

## Recommendation in one sentence

Do **not** resume operator-side `v1` work yet; first build a local
`post_db_scheduled_primfunc_swap` / `db_recovered_scheduled_task_probe` seam so
handwritten candidates can be judged without throwing away the best-staging
MetaSchedule context.
