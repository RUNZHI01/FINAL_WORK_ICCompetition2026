# cockpit_native demo packet index（2026-03-24）

## Live entry

- native cockpit launcher: `bash ./session_bootstrap/scripts/run_cockpit_native.sh`
- one-shot rehearsal: `bash ./session_bootstrap/scripts/run_cockpit_native_demo_rehearsal.sh`
- GO / NO-GO summary: `bash ./session_bootstrap/scripts/print_cockpit_native_go_no_go.sh`
- build deliverable archive: `bash ./session_bootstrap/scripts/build_cockpit_native_demo_packet.sh`
- verify latest packet: `bash ./session_bootstrap/scripts/verify_cockpit_native_demo_packet.sh`

## Talk track

- main talk track: `session_bootstrap/runbooks/cockpit_native_demo_talk_track_2026-03-24.md`
- presenter card: `cockpit_native/runtime/deliverables/cockpit_native_demo_packet_latest/PRESENTER_CARD.txt`

## Static pack

- embedded html overview: `cockpit_native/runtime/deliverables/cockpit_native_demo_packet_latest/index_embedded.html`
- html overview: `cockpit_native/runtime/deliverables/cockpit_native_demo_packet_latest/index.html`
- landing: `cockpit_native/runtime/captures/demo_pack/landing.png`
- flight: `cockpit_native/runtime/captures/demo_pack/flight.png`
- actiondock: `cockpit_native/runtime/captures/demo_pack/actiondock.png`
- manifest: `cockpit_native/runtime/captures/demo_pack/manifest.md`
- deliverable archive: `cockpit_native/runtime/deliverables/cockpit_native_demo_packet_<timestamp>.tar.gz`
- deliverable zip: `cockpit_native/runtime/deliverables/cockpit_native_demo_packet_<timestamp>.zip`
- latest deliverable dir: `cockpit_native/runtime/deliverables/cockpit_native_demo_packet_latest`
- latest deliverable tar: `cockpit_native/runtime/deliverables/cockpit_native_demo_packet_latest.tar.gz`
- latest deliverable zip: `cockpit_native/runtime/deliverables/cockpit_native_demo_packet_latest.zip`

## Headline

- `1844.1 ms -> 153.778 ms`
- `Current 相比 baseline 提升 91.66%`

## Demo flow

1. `current_online_rebuild`
2. `reload_contracts`
3. `probe_live_board`

## Position source rule

- true live GPS: `/api/aircraft-position`
- if live feed absent: explicit `backend_stub / stub`
- never present default sample coordinates as real GPS
