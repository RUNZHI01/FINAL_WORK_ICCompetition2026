# Legacy launchers

This directory keeps the old host-side launch scripts for team reference only.
Judges should use the Docker entrypoints documented in the repository root
`README.md`:

- `docker/repro.*`
- `docker/run-demo.*`
- `docker/run-demo-wslg-tailscale.ps1`
- `docker/run-board-cli-smoke.*`

These legacy scripts may assume a local `.venv`, direct board credentials, and
the historical repository layout. They are not part of the judged
reproducibility path.
