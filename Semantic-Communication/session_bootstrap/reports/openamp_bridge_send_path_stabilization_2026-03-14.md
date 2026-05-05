# OpenAMP bridge send-path stabilization

> Date: 2026-03-14  
> Scope: local bridge send-path fix only, no board deployment in this step.

## Observation

- The known-good board probe in `session_bootstrap/reports/openamp_joback_v14_trial_20260314/joback_probe.py` opens `/dev/rpmsg0` with `O_NONBLOCK` and calls `os.write()` immediately.
- `session_bootstrap/scripts/openamp_rpmsg_bridge.py` opened the same device with `O_NONBLOCK` but waited for `select(..., writable)` before the first write attempt.
- Under the board-backed wrapper path, that bridge write path timed out on `JOB_REQ` even though the direct board probe already proved real `JOB_REQ -> JOB_ACK(ALLOW)` works on the patched firmware.

## Most likely root cause

The bridge was treating `POLLOUT` readiness as a prerequisite for sending on `/dev/rpmsg0`. For this rpmsg char device, writable readiness is stricter or less reliable than a direct nonblocking `write()`. That creates the exact failure split we observed:

- direct probe: immediate `write()` succeeds
- wrapper bridge: pre-write readiness wait times out before the bridge even attempts the send

## Local fix

- `write_all()` now attempts `os.write()` first on the nonblocking fd.
- Only retryable nonblocking errors (`EAGAIN` / `EWOULDBLOCK` / `EINTR`) fall back to `select(..., writable)` and retry.
- No protocol format or wrapper contract changed.

## Intended effect

`JOB_REQ` in hook mode now uses the same practical send behavior as the probe that already worked on the board: optimistic nonblocking write first, readiness wait only when the kernel actually reports backpressure.
