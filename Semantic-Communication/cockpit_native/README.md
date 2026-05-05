# cockpit_native

PySide6-first native cockpit prototype for the existing TVM/OpenAMP demo contracts.

Smoke/import check without PySide6:

```bash
python3 -m cockpit_native --smoke-import-check
```

Dump the normalized UI state:

```bash
python3 -m cockpit_native --dump-ui-state
```

Launch the adaptive QML shell when `PySide6` is installed:

```bash
python3 -m cockpit_native
```

Project-local operator launcher:

```bash
bash ./session_bootstrap/scripts/run_cockpit_native.sh
```

The launcher now supervises the Qt process, retries once with software rendering if the first GPU-backed launch exits early, and auto-starts the repo-local operator server when `127.0.0.1:8079` is not healthy.

Force software rendering from the start:

```bash
python3 -m cockpit_native --software-render
```

Capture an offscreen screenshot through the repo-local venv launcher:

```bash
bash ./session_bootstrap/scripts/run_cockpit_native_capture.sh
```

Default output:

```text
./cockpit_native/runtime/captures/cockpit_native_latest.png
```

Override the output path if needed:

```bash
bash ./session_bootstrap/scripts/run_cockpit_native_capture.sh --output /tmp/cockpit_native.png
```

Presentation talk track:

```text
./session_bootstrap/runbooks/cockpit_native_demo_talk_track_2026-03-24.md
```

One-shot demo rehearsal:

```bash
bash ./session_bootstrap/scripts/run_cockpit_native_demo_rehearsal.sh
```

Fast GO / NO-GO summary:

```bash
bash ./session_bootstrap/scripts/print_cockpit_native_go_no_go.sh
```

Verify the latest packet before sharing it:

```bash
bash ./session_bootstrap/scripts/verify_cockpit_native_demo_packet.sh
```

Build a deliverable archive:

```bash
bash ./session_bootstrap/scripts/build_cockpit_native_demo_packet.sh
```

The builder now emits both `.tar.gz` and `.zip`, plus `SHA256SUMS.txt` inside the packet.
It also refreshes stable `cockpit_native_demo_packet_latest/`, `cockpit_native_demo_packet_latest.tar.gz`, and `cockpit_native_demo_packet_latest.zip` outputs.
