# OpenAMP Demo Job Manifest Gate M2

## APIs added

- `GET /api/job-manifest-gate`
  - Returns the current manifest-gate status/details for `current` by default.
  - Accepts `?variant=current|baseline`.
  - Reuses the existing wrapper/live inputs only: admission mode, variant support, cached control status, current active job state, and the existing manifest contract snapshot.
- `POST /api/job-manifest-gate/preview`
  - Accepts `{ "variant": "current" | "baseline" }`.
  - Runs a demo-only admitability preview.
  - If the board session is ready, it performs a read-only `STATUS_REQ` precheck and folds that result into the gate verdict.
  - Returns a preview result plus the gate payload.
  - Does not send `JOB_REQ`, does not mutate lower-layer protocol state, and does not start board execution.
- `GET /api/system-status`
  - Now also exposes `job_manifest_gate` so the existing dashboard refresh can render the gate without adding a separate page reload flow.

## UI wiring added

- Act 1 now includes a `Job Manifest Gate` card.
- The card shows:
  - current verdict
  - current state label / summary
  - operator-visible reasons
  - current wire-side fields (`job_id`, `expected_sha256`, `expected_outputs`, `deadline_ms`, `job_flags`, manifest/key ids)
  - context-only fields and explicit protocol-boundary notes
- A `demo-only 票据预检` button triggers `POST /api/job-manifest-gate/preview` and updates the page in place after the request completes.

## Event behavior

- `GET /api/job-manifest-gate` is read-only and emits no event.
- `POST /api/job-manifest-gate/preview` publishes preview-only `JOB_*` events into the existing event spine:
  - always `JOB_SUBMITTED`
  - then `JOB_ADMITTED` when the preview verdict is allow
  - or `JOB_REJECTED` when the preview verdict is deny / hold
- Preview events are tagged with `preview_only=true` and `preview_action=job_manifest_gate_preview`.
- Preview events remain visible in `recent_events`, but they do not increment the real live-path `submitted_count` / `admitted_count` / `rejected_count`.
  - They increment the additive preview counters instead.
- Preview emits no `JOB_STARTED`, `JOB_DONE`, or fake board-execution event.
- Preview also avoids emitting heartbeat observation events, so the live inference/fault paths remain the only source of those counts.

## Still read-only / scaffold / demo-only

- M2 does **not** expand the JOB wire schema beyond the existing wrapper/live path.
- `input_shape` / `output_shape` remain operator context only; they are not claimed as new wire fields.
- M2 does **not** fake board execution, admission mutation, or protocol success.
- The preview action is operator-side only:
  - it may issue a read-only status precheck
  - it never launches the runner
  - it never claims that a real ticket was sent
- The 4-core vs 3-core boundary remains unchanged:
  - 4-core Linux performance mode still covers performance and reconstruction evidence.
  - 3-core Linux + RTOS demo mode still covers OpenAMP control-plane, admission, heartbeat, SAFE_STOP, and operator-visible gate flow.
