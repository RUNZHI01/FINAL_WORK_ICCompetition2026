# Scheme A Baseline Payload Compat Progress (2026-03-11)

## Change

- `session_bootstrap/scripts/run_remote_tvm_inference_payload.sh` now falls back to `tvm.runtime.ndarray.array(...)` only when `tvm.runtime.tensor` is missing.
- The current safe-runtime path is unchanged because the native `tvm.runtime.tensor` path is still used whenever it exists.

## Host validation attempt

Command run from this host:

```bash
set -a; source session_bootstrap/config/inference_compare_scheme_a_fair.2026-03-11.phytium_pi.env; set +a;
REMOTE_TVM_PYTHON=/home/user/venv/bin/tvm_compat_python.sh INFERENCE_REPEAT=1 INFERENCE_WARMUP_RUNS=0 \
bash ./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh --variant baseline
```

Observed result:

```text
socket: Operation not permitted
ssh: connect to host 100.121.87.73 port 22: failure
```

## Status

- The previous baseline payload blocker (`AttributeError: module tvm.runtime has no attribute tensor`) is addressed in the payload runner code.
- This session could not verify remote baseline execution because SSH is blocked before the remote Python process starts.
- No additional Scheme A env changes were made in this session because the requested remote validation did not complete.

## Next step

- Re-run the exact command above on a host with SSH access to the Phytium Pi to confirm whether baseline payload now reaches `load_module -> relax.VirtualMachine -> main()`.
