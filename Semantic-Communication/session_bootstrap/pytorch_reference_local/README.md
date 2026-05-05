# PyTorch Reference Local Workspace

This directory is an isolated local work area for iterating on the current
PyTorch reference reconstruction flow without editing the mainline copies under
`session_bootstrap/scripts/`.

Copied on 2026-03-18 from:

- `session_bootstrap/scripts/pytorch_reference_reconstruction.py`
- `session_bootstrap/scripts/run_remote_pytorch_reference_reconstruction.sh`

Files in this folder:

- `pytorch_reference_reconstruction.py`: Python helper that generates
  reproducible PyTorch JSCC reference reconstructions from latent inputs.
  It also contains the local-only experimental scheduler path
  `--local-experimental-subprocess-per-image`, which runs each image in its
  own Python subprocess and stores child records under
  `<output-dir>/local_experimental_subprocess_worker_records/`.
  The isolated helper also exposes `--local-disable-mkldnn` to disable
  oneDNN/MKLDNN for this copied workflow only.
- `run_remote_pytorch_reference_reconstruction.sh`: Bash wrapper that resolves
  env/config inputs and invokes the Python helper for remote or local runs.
  For SSH runs it now stages the helper as a temporary real file on the remote
  host so the local-only experimental subprocess mode can re-exec the helper.

Intended use:

- Make local experimental edits here first.
- Keep the originals in `session_bootstrap/scripts/` unchanged until any
  follow-up work is ready to be promoted deliberately.
- Use `--local-experimental-subprocess-per-image` only for isolated
  local-wrapper experiments; it is intentionally named as local-only and
  should not be treated as a mainline behavior change.
