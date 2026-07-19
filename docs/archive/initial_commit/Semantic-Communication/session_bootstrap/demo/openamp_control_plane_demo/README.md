# 飞腾多核弱网安全语义视觉回传系统 Demo

This package ships the operator-facing local dashboard for the current repo state. It is not a disconnected mock: the backend reads the existing OpenAMP evidence package, raw probe JSON, FIT summaries, wrapper evidence, the latest live dual-path status snapshot (`session_bootstrap/reports/openamp_demo_live_dualpath_status_20260317.md`), and the trusted-current performance reports that already live under `session_bootstrap/reports/`.

The UI keeps the system story explicit:

- Current / PyTorch reconstruction remains the existing semantic-visual-return data plane
- OpenAMP is the control plane for admission, heartbeat, SAFE_STOP, and fault evidence
- headline performance quotes `4-core Linux performance mode`
- OpenAMP live cues are presented as `3-core Linux + RTOS demo mode`, not as a speedup path

## What it shows

- four-act Chinese-first operator flow: trusted state -> Current semantic visual return live -> formal comparison / performance positioning -> fault injection / recovery
- web-side board credential entry for `host / user / password / port / env_file`, stored only in the current demo-server process and reused for later actions
- board/control-plane status with explicit evidence-backed vs live-probe mode
- key OpenAMP milestones across cold boot, `STATUS_REQ/RESP`, `JOB_REQ/JOB_ACK`, heartbeat, wrapper-backed board smoke, `SAFE_STOP`, and `JOB_DONE`
- final `FIT-01`, `FIT-02`, `FIT-03` state, including `FIT-03` pre-fix FAIL -> post-fix PASS history
- trusted-current performance positioning with the data-plane/control-plane boundary called out explicitly
- default third-act baseline = `2026-03-12` archived PyTorch reference; the `2026-03-17` dual-path live status remains linked as historical evidence
- when baseline live is available, the user-facing cockpit now keeps the label on `PyTorch live` / `PyTorch signed live`; the backend JSON still preserves the technical admission mode as `legacy_sha` or `signed_manifest_v1`
- explicit mode split for the operator: `4-core Linux performance mode` vs `3-core Linux + RTOS demo mode`
- operator launch commands and source-of-truth document links

## Launch

Default local dashboard:

```bash
bash ./session_bootstrap/scripts/run_openamp_demo.sh
```

Open it at `http://127.0.0.1:8079`.
If that port is still held by an older instance of this same OpenAMP demo server, the launcher will stop it and restart cleanly. If some other service owns the port, the launcher exits with a targeted error instead of killing it.

This launches the app-layer dashboard for the Feiteng semantic visual return system. The launcher does not change the runtime split: performance headline numbers still come from `4-core Linux performance mode` reports, while OpenAMP live actions remain `3-core Linux + RTOS demo mode`.

Optional live board probe wiring:

```bash
bash ./session_bootstrap/scripts/run_openamp_demo.sh \
  --port 8090 \
  --probe-env ./session_bootstrap/config/phytium_pi_login.env
```

Optional local external positioning feed wiring:

```bash
bash ./session_bootstrap/scripts/run_openamp_demo.sh \
  --aircraft-position-env ./session_bootstrap/config/aircraft_position_baidu_ip.example.env
```

## Session Readiness Check

Before trying to continue the live operator flow, run the launcher-level readiness preflight first:

```bash
bash ./session_bootstrap/scripts/run_openamp_demo.sh --check-readiness
```

If you need the raw checker directly, you can still run:

```bash
python3 ./session_bootstrap/scripts/check_openamp_demo_session_readiness.py --format text
```

Default JSON output is also available for machine-readable checks:

```bash
python3 ./session_bootstrap/scripts/check_openamp_demo_session_readiness.py
```

The readiness checker reuses the same demo defaults and field contracts as the dashboard server:

- checks whether `host / user / port / password` are complete for the current session
- reports whether the probe env defaults are present and whether the effective inference env is complete
- distinguishes `docs-first only` from `can continue live probe` and `can continue live inference`
- exits with `0` when the full live operator flow is ready, `2` when readiness blockers remain

In the normal repo state, the check should explicitly report `missing password` while showing that the probe/inference defaults are already preloaded.

Optional signed-manifest demo admission for the current artifact, baseline artifact, or both:

```bash
bash ./session_bootstrap/scripts/run_openamp_demo.sh \
  --signed-manifest-file /tmp/openamp_demo_signed_admission/current.bundle.json \
  --signed-manifest-public-key /tmp/openamp_demo_signed_admission/current.public.pem \
  --baseline-signed-manifest-file /tmp/openamp_demo_signed_admission/baseline.bundle.json \
  --baseline-signed-manifest-public-key /tmp/openamp_demo_signed_admission/baseline.public.pem
```

The demo keeps the legacy path intact by default. Current and Baseline are configured independently:

- if a variant-specific signed bundle and public key are supplied, that live path switches to `signed_manifest_v1` preflight
- the signed bundle is verified locally with the supplied public key before the wrapper launches
- wrapper traces and manifests carry the signed-manifest metadata for the user-facing demo
- the live control hook now emits `SIGNED_ADMISSION_BEGIN/CHUNK/SIGNATURE/COMMIT` before the unchanged 44-byte `JOB_REQ`
- if Baseline signed admission is not configured or fails local verification, the demo stays explicit: Baseline live falls back to expected-SHA admission when available, the UI still labels that path as `PyTorch live`, and the backend state keeps `mode=legacy_sha`; otherwise the UI keeps the formal archived baseline comparison only

The same override can also be carried in the active inference env file with:

```bash
OPENAMP_DEMO_ADMISSION_MODE=signed_manifest_v1
OPENAMP_DEMO_SIGNED_MANIFEST_FILE=/tmp/openamp_demo_signed_admission/current.bundle.json
OPENAMP_DEMO_SIGNED_MANIFEST_PUBLIC_KEY=/tmp/openamp_demo_signed_admission/current.public.pem

OPENAMP_DEMO_BASELINE_ADMISSION_MODE=signed_manifest_v1
OPENAMP_DEMO_BASELINE_SIGNED_MANIFEST_FILE=/tmp/openamp_demo_signed_admission/baseline.bundle.json
OPENAMP_DEMO_BASELINE_SIGNED_MANIFEST_PUBLIC_KEY=/tmp/openamp_demo_signed_admission/baseline.public.pem
```

The dashboard stays evidence-led either way. The "探测板卡 / OpenAMP" action only runs a read-only SSH probe plus an optional cached RPMsg status query.
If `session_bootstrap/reports/openamp_demo_live_probe_latest.json` already exists, the dashboard loads that saved successful probe on startup and keeps showing it if a later in-dashboard refresh fails.

On startup, the demo now also preloads practical repo-backed defaults when they exist:

- SSH defaults: `session_bootstrap/config/phytium_pi_login.env`, else `session_bootstrap/config/phytium_pi_login.example.env`
- inference defaults for the demo line: prefer the env snapshot referenced by `session_bootstrap/reports/inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md`, else fall back to `session_bootstrap/config/inference_real_reconstruction_compare.2026-03-11.phytium_pi.env`
- live inference now reuses that validated env contract directly instead of rewriting `INFERENCE_CURRENT_EXPECTED_SHA256` inside the demo server

Repo-side password fields are ignored intentionally. The operator still enters the password once in the web UI, and the current demo-server process reuses it for later probe / inference / fault actions.

If you want to re-check readiness with a runtime password without starting the dashboard first, prefer the same launcher entrypoint:

```bash
bash ./session_bootstrap/scripts/run_openamp_demo.sh --check-readiness-prompt-password
```

The launcher reads the password once from stdin without echoing it, forwards it only to the readiness checker process, and does not write it back into repo files.
If you prefer the split form, this is equivalent:

```bash
bash ./session_bootstrap/scripts/run_openamp_demo.sh --check-readiness --prompt-password
```

The older explicit override still works when you intentionally want a non-interactive call:

```bash
bash ./session_bootstrap/scripts/run_openamp_demo.sh \
  --check-readiness \
  --password '<runtime-password>'
```

If the readiness retry passes and you want to launch the dashboard with one temporary runtime password, the launcher now also supports:

```bash
bash ./session_bootstrap/scripts/run_openamp_demo.sh --prompt-password
```

If you want the same launch to immediately attempt one read-only startup probe, use:

```bash
bash ./session_bootstrap/scripts/run_openamp_demo.sh --prompt-password --probe-startup
```

There is also a shorthand alias for the same flow:

```bash
bash ./session_bootstrap/scripts/run_openamp_demo.sh --prompt-password-probe-startup
```

If you want a one-shot startup-probe capture instead of keeping the dashboard running, use:

```bash
bash ./session_bootstrap/scripts/run_openamp_demo_probe_once.sh --prompt-password
```

Default behavior:

- binds the temporary demo server on `127.0.0.1:18079` so it does not reclaim your usual manual `8079` dashboard by accident
- launches the existing demo launcher with startup probe enabled
- waits for `/api/health`, captures `/api/health`, `/api/system-status`, and `/api/snapshot`
- writes the raw JSON plus launcher logs under `session_bootstrap/tmp/openamp_demo_probe_once_<timestamp>/`
- prints a concise summary for `execution_mode`, `connection_ready`, `missing_connection_fields`, `mode.effective_label`, `board.current_status.label / summary`, and `valid_instance`
- stops the temporary demo process automatically after capture

If you already have a runtime password and accept the usual shell-history/process-list tradeoff, the helper also supports:

```bash
bash ./session_bootstrap/scripts/run_openamp_demo_probe_once.sh \
  --password '<runtime-password>' \
  --probe-timeout-sec 5
```

If you also want the same one-shot helper to trigger a fresh `/api/probe-board` attempt and capture the returned auth/probe result, use:

```bash
bash ./session_bootstrap/scripts/run_openamp_demo_probe_once.sh \
  --prompt-password \
  --post-probe-board
```

If you want the helper to fail fast for automation whenever fresh `/api/probe-board` is not actually successful, use:

```bash
bash ./session_bootstrap/scripts/run_openamp_demo_probe_once.sh \
  --prompt-password \
  --strict-probe-board
```

The helper stays honest about snapshot freshness. If the capture still says `保存的只读 SSH 探板` and the summary says the result comes from a saved record, treat that as saved-probe replay rather than claiming a fresh startup probe succeeded.

## External Position API

The current demo already supports a purchased external positioning feed as long as the upstream can be pulled as an HTTP `GET` that returns a JSON object with at least latitude and longitude.

The normalization bridge entrypoint is:

```bash
python3 ./session_bootstrap/demo/openamp_control_plane_demo/aircraft_position_bridge.py --once
```

Recommended config template:

```bash
./session_bootstrap/config/aircraft_position_external_api.example.env
```

For the current Baidu service-side IP location route, use:

```bash
./session_bootstrap/config/aircraft_position_baidu_ip.example.env
```

Typical runtime keys:

```bash
AIRCRAFT_POSITION_UPSTREAM_URL=https://provider.example/api/v1/position?token=<key>
AIRCRAFT_POSITION_BACKEND_BASE_URL=http://127.0.0.1:8079
AIRCRAFT_POSITION_UPSTREAM_HEADERS_JSON='{"Authorization":"Bearer <token>"}'
AIRCRAFT_POSITION_LATITUDE_PATH=
AIRCRAFT_POSITION_LONGITUDE_PATH=
```

If the upstream is called by the local demo machine rather than the board, set:

```bash
AIRCRAFT_POSITION_EXECUTION_MODE=local
```

What the bridge already handles without code changes:

- custom upstream headers via `AIRCRAFT_POSITION_UPSTREAM_HEADERS_JSON`
- query-string auth embedded directly in `AIRCRAFT_POSITION_UPSTREAM_URL`
- non-default field names through `AIRCRAFT_POSITION_*_PATH`
- unit scaling through `AIRCRAFT_POSITION_GROUND_SPEED_SCALE`, `AIRCRAFT_POSITION_ALTITUDE_SCALE`, and `AIRCRAFT_POSITION_VERTICAL_SPEED_SCALE`

Important boundary:

- if the vendor gives you a plain HTTP JSON API, the existing bridge can usually connect directly
- if the vendor only gives you an SDK or device-side binary interface, you still need a thin wrapper service that exposes an HTTP JSON endpoint for this demo

For the `北斗`-aligned route we checked so far:

- 百度地图 `智能硬件定位` is listed as an advanced paid service and follows `申请试用 -> 开通试用 -> 正式付费` rather than a simple self-serve public JSON API
- 百度地图 `北斗高精度定位服务` is presented as商务咨询/合作咨询导向

Official pages:

- `地图高级服务 / 智能硬件定位`: https://lbs.baidu.com/cashier/service
- `百度智能定位`: https://lbs.baidu.com/products/location
- `北斗高精度定位服务`: https://lbs.baidu.com/products/highaccbdloc

If you want a non-interactive, one-shot ML-KEM live closure (startup -> board session -> crypto ON -> current inference -> summary capture), use:

```bash
bash ./session_bootstrap/scripts/run_openamp_demo_mlkem_once.sh --prompt-password
```

Default behavior:

- binds a temporary demo backend on `127.0.0.1:18089`
- injects board session (`host/user/password/port`) via `/api/session/board-access`
- enables ML-KEM toggle via `/api/crypto-toggle`
- triggers one `current` launch via `/api/run-inference`
- if backend returns `running`, polls `/api/inference-progress` until completion
- captures `/api/crypto-status`, `/api/system-status`, `/api/event-spine`
- writes artifacts under `session_bootstrap/tmp/openamp_demo_mlkem_once_<timestamp>/`

By default, the helper exits non-zero if the final inference is not `status=success`, `status_category=success`, and `execution_mode=live`. For rehearsal mode where fallback is acceptable, add `--allow-fallback`.

For full-batch verification (e.g. all 300 images through ML-KEM live path), use:

```bash
bash ./session_bootstrap/scripts/run_openamp_demo_mlkem_batch.sh --prompt-password --count 300
```

Batch helper behavior:

- launches the demo backend once, reuses the same board session and crypto toggle
- iterates `image_index` in `[start_index, start_index + count)`
- records per-item results to `batch_results.jsonl`
- writes aggregate `batch_summary.json` and top-level `summary.json`
- exits non-zero by default if not all items are `status=success`, `status_category=success`, `execution_mode=live`

If OpenAMP control STATUS preflight becomes unstable during long runs but you still need to finish data-plane encryption evidence collection on the same day, you can enable:

```bash
--allow-control-preflight-degraded
```

This keeps ML-KEM data-plane execution running when control preflight times out. Keep this mode explicitly marked as an operator override in evidence notes.

Example with explicit output dir:

```bash
bash ./session_bootstrap/scripts/run_openamp_demo_mlkem_batch.sh \
  --prompt-password \
  --count 300 \
  --output-dir ./session_bootstrap/tmp/openamp_demo_mlkem_batch_full300
```

Direct checker usage still works when needed:

```bash
python3 ./session_bootstrap/scripts/check_openamp_demo_session_readiness.py \
  --password '<runtime-password>' \
  --format text
```

The readiness outputs only report `has_password=true/false`; they do not print the raw password back out.

## Board GPS bridge

The cockpit and static demo page already read the unified backend contract at `/api/aircraft-position`.
What was missing is a real producer that can run on the board and forward live GPS/INS data into that contract.

The repo now also includes a board-local positioning API service at
`session_bootstrap/demo/openamp_control_plane_demo/board_position_api_service.py`.
It exposes `http://127.0.0.1:9000/api/v1/position` on the board and tries common native
GNSS sources in order:

- `gpsd` on `127.0.0.1:2947`
- local NMEA devices such as `/dev/ttyUSB0`, `/dev/ttyACM0`, `/dev/ttyAMA0`, `/dev/ttyS0`

That service is auto-deployed before the bridge probe runs, so if the board has a real GNSS source but
did not already expose an HTTP positioning API, the demo can still discover `9000/api/v1/position` and
wire it into `/api/aircraft-position`.

You can now run a portable bridge on the board:

```bash
bash ./session_bootstrap/scripts/run_aircraft_position_bridge.sh \
  --upstream-url http://127.0.0.1:9000/gps \
  --backend-base-url http://<demo-host>:8079 \
  --ground-speed-scale 3.6
```

Behavior:

- polls the real board-side positioning API at `--upstream-url`
- normalizes the payload into the existing `/api/aircraft-position` schema
- POSTs live samples into the current demo backend without changing the Electron/frontend contract
- keeps working even if the upstream JSON shape differs, via `--latitude-path`, `--longitude-path`, and the other `--*-path` overrides

The demo backend can now auto-deploy and auto-start this bridge on the board after you save board access in the UI.
To enable that path, put these env vars into the same board/inference env that the demo already loads:

```bash
AIRCRAFT_POSITION_UPSTREAM_URL=http://127.0.0.1:9000/gps
AIRCRAFT_POSITION_BACKEND_BASE_URL=http://<demo-host>:8079
AIRCRAFT_POSITION_GROUND_SPEED_SCALE=3.6
```

If the demo backend is started on a non-loopback bind address such as `0.0.0.0`, the backend can auto-derive
`AIRCRAFT_POSITION_BACKEND_BASE_URL` from the current host network address and only `AIRCRAFT_POSITION_UPSTREAM_URL`
remains mandatory.

If you do not want to hardcode a single upstream URL, the board bridge and demo backend now also support
candidate auto-discovery:

```bash
AIRCRAFT_POSITION_UPSTREAM_CANDIDATES_JSON='[
  "http://127.0.0.1:9000/gps",
  "http://127.0.0.1:9000/api/v1/position",
  "http://127.0.0.1:9527/api/v1/position"
]'
```

With that in place:

- the backend probes common board-local endpoints after `board-access` is saved
- the built-in defaults already cover common `/gps`, `/position`, `/location`, `/api/*`, and `/api/v1/*` paths on `9000`, `9527`, and `8080`
- `/api/system-status` exposes whether the bridge is `autodiscovered`, `upstream_not_found`, or `upstream_probe_error`
- if one candidate responds with usable latitude/longitude, the backend injects the discovered URL and starts the bridge automatically

Optional envs supported by the bridge and safe for remote auto-deploy:

- `AIRCRAFT_POSITION_UPSTREAM_HEADERS_JSON`
- `AIRCRAFT_POSITION_UPSTREAM_CANDIDATES_JSON`
- `AIRCRAFT_POSITION_BACKEND_HEADERS_JSON`
- `AIRCRAFT_POSITION_SOURCE_LABEL`
- `AIRCRAFT_POSITION_SOURCE_NOTE`
- `AIRCRAFT_POSITION_AIRCRAFT_ID`
- `AIRCRAFT_POSITION_MISSION_CALL_SIGN`
- `AIRCRAFT_POSITION_INTERVAL_SEC`
- `AIRCRAFT_POSITION_TIMEOUT_SEC`
- `AIRCRAFT_POSITION_*_PATH`

When those vars are present and the session has `host/user/password`, the demo backend uploads:

- `aircraft_position_bridge.py`
- `run_aircraft_position_bridge.sh`
- `aircraft_position_bridge.env`
- a user-level `systemd` unit

to `~/.openamp-demo/aircraft_position_bridge` on the board, then tries `systemctl --user enable --now`.
If the board does not expose a working user `systemd` bus, the demo falls back to a background `nohup` process instead.

Typical path overrides for a non-demo-native upstream:

```bash
bash ./session_bootstrap/scripts/run_aircraft_position_bridge.sh \
  --upstream-url http://127.0.0.1:9000/api/v1/position \
  --backend-base-url http://<demo-host>:8079 \
  --latitude-path gps.latitude_deg \
  --longitude-path gps.longitude_deg \
  --ground-speed-kph-path gps.speed_mps \
  --ground-speed-scale 3.6 \
  --captured-at-path meta.timestamp \
  --sequence-path meta.seq
```

Use `--once` for one-shot validation during bring-up. In steady state, leave it in loop mode and supervise it with your usual board-side process manager.
The repo also includes a matching user-service template at `session_bootstrap/scripts/aircraft_position_bridge.service.example`.

## Web-side credential flow

Open the dashboard and fill the "会话接入" card:

- `主机 / IP`
- `用户名`
- `密码`
- `SSH 端口`
- optional `env 文件`

The password is kept only in memory inside the current demo server process. It is not written back to the repo.
If the startup defaults above were found, the UI prelabels which fields were preloaded and which one is still missing. In the normal repo state, `host / user / port / env_file` are already filled, so only the password must be entered before Current / Baseline attempt live execution.
Later board-facing actions reuse the same in-process session automatically:

- Act 1 trusted-state probe
- Act 2 Current semantic visual return live attempt
- Act 3 formal comparison / optional PyTorch live cue
- Act 4 RPMsg fault injection / SAFE_STOP recovery

If the board is unreachable or the env file is incomplete for inference, the UI falls back to prerecorded evidence and labels that downgrade explicitly.

## Read-only board probe

Standalone CLI:

```bash
python3 ./session_bootstrap/scripts/probe_openamp_board_status.py \
  --env ./session_bootstrap/config/phytium_pi_login.env
```

Default output:

- `session_bootstrap/reports/openamp_demo_live_probe_latest.json`

The probe only reads:

- hostname / user
- `/sys/class/remoteproc/remoteproc*/state`
- `/dev/rpmsg*`
- RPMsg channel names under `/sys/bus/rpmsg/devices/*/name`
- `/lib/firmware/openamp_core0.elf` size and SHA256

It does not reboot the board, does not send `JOB_REQ`, and does not modify firmware/runtime state.

## Host and slave side scope

Host side inputs:

- `session_bootstrap/reports/openamp_control_plane_evidence_package_20260315/`
- `session_bootstrap/reports/openamp_demo_live_dualpath_status_20260317.md`
- raw board probes such as `openamp_job_done_real_probe_20260315_001.json`
- FIT bundles under `openamp_*_fit_*`
- `session_bootstrap/scripts/openamp_control_wrapper.py`
- `session_bootstrap/scripts/openamp_rpmsg_bridge.py`
- trusted-current performance reports for SHA `6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1`

App-layer interpretation boundary:

- Current / PyTorch reconstruction is the data plane shown to the evaluator
- OpenAMP evidence is the control/safety plane shown alongside it
- `remoteproc0=running` live cues must be explained as `3-core Linux + RTOS demo mode`
- performance headline numbers stay attached to the separate `4-core Linux performance mode` reports

Slave/OpenAMP side assumptions:

- the board remains on the already prepared OpenAMP path
- RPMsg transport and remoteproc state are the ones validated in the existing evidence package
- the final post-fix firmware SHA in the dashboard comes from the board-backed `FIT-03` PASS bundle
- live control actions first try the SSH user's direct `/dev/rpmsg*` access, then `sudo -n` if the board already grants passwordless sudo; otherwise the demo reports an explicit board-side permission gate instead of pretending the control path ran
- if `remoteproc` has claimed one Linux CPU, the operator explains the board as `3-core Linux + RTOS demo mode`, not as a 4-core performance run

## Local verification

Recommended checks:

```bash
python3 -m unittest discover -s ./session_bootstrap/demo/openamp_control_plane_demo/tests -p 'test_*.py'
bash ./session_bootstrap/scripts/run_openamp_demo.sh --port 8079
```

## Regression coverage snapshot

The current demo regression suite covers these public/operator-facing surfaces:

- snapshot construction in `demo_data.build_snapshot()`, including final FIT verdicts, trusted-current performance alignment, live-probe mode switching, and saved-probe labeling
- HTTP smoke coverage for `GET /api/snapshot`, `GET /api/system-status`, `POST /api/session/board-access`, `POST /api/probe-board`, `POST /api/run-inference`, `POST /api/inject-fault`, `GET /docs?path=...`, `GET /api/health`, `GET /`, `GET /app.js`, and `GET /app.css`
- localhost socket smoke coverage for `GET /api/health` that boots `DemoHTTPServer` on an ephemeral port, hits the real bound endpoint once, and shuts down cleanly when the runtime permits local socket creation
- live-probe cache behavior: startup reuse of the last successful probe artifact and preservation of that saved probe when a later refresh fails
- session credential behavior: redacted public payloads, probe reuse of saved credentials, and fallback/live inference API payload shaping
- docs endpoint guardrails for missing path, invalid repo-external path, missing file, and JSON pretty-print rendering
- direct `board_probe` unit coverage for command construction, cache helpers, and execution outcomes: password-auth SSH selection, `REMOTE_SSH_PORT` override handling, `connect_phytium_pi.sh --env ...` fallback, dedicated `load_probe_output()` checks for missing, malformed, and valid-non-dict JSON, `write_probe_output()` success-and-write-failure paths, and `run_live_probe()` success, timeout, launch/configuration failure, non-zero exit, and JSON parse-error payload shaping
- `server.main()` bootstrap coverage for both normal startup and `--probe-startup`, including `DashboardState` construction, startup probe ordering, `DemoHTTPServer` wiring, and the printed launch banner without binding a real socket

Intentional gaps and next-optional coverage:

- optional extra `board_probe` unit coverage would now be limited to rarer platform-specific shell/permission anomalies beyond the current command-construction, cache-helper, launch-failure, and result-shaping paths
- the frontend is covered as served assets only; there is no browser-level regression for DOM rendering or the in-page refresh flow
- the localhost socket smoke skips explicitly when the runtime forbids socket creation, so heavily sandboxed environments still will not exercise bind/listen despite the test existing
