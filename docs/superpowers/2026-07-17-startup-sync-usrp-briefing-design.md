# Startup, Sync, and USRP Briefing Design

## Objective

Prepare the repository for the final demonstration and the 2026-07-17 team sync. The deliverable must make board recovery repeatable, keep daily startup strict, and give the PPT/document owners an accurate description of every USRP IQ-direct stage.

## Script Scope

Keep one-time initialization separate from daily startup. `docker/prepare-iq-board-sync.ps1` remains the board bundle entry point, but gains optional Docker-based deployment and verification so Windows does not depend on WSL or native `scp`. Deployment targets the parameterized board host/user/port and activates the board's `tvm310_safe` environment for tests and OTA binary builds.

`Semantic-Communication/cockpit_desktop/start-demo.ps1` remains the daily entry point. It explicitly sets the startup acceptance threshold to the requested warm-up count. The UI is shown only after all 10 default IQ-direct and TVM warm-up samples complete successfully.

## Documentation Scope

Update `docs/README.md`, `docs/runbooks/STARTUP.md`, and `docs/HANDOFF.md` to remove stale 5/10 warm-up language and the obsolete shared USRP output path. Add a focused briefing document that describes:

- image to JSCC latent conversion;
- analog latent framing and IQ waveform generation;
- persistent host TX, RF link, and persistent board RX;
- synchronization, quality gates, ARQ, segment repair, and real RX reset;
- board-local decoded latent storage;
- handwritten TVM operators and big.LITTLE reconstruction;
- Cockpit progress, metrics, and result comparison;
- control-plane security boundaries and Tailscale's role.

The briefing will separate radio airtime, transport/decode latency, TVM core latency, and end-to-end batch time. It will also list PPT claims to use and claims to avoid, especially that ML-KEM/SM4 protects the control channel rather than the analog IQ payload.

## Verification

Regenerate the bundle, deploy it, compare key file hashes, run focused Python tests, validate PowerShell syntax and documentation links, and perform a strict startup/readiness check without mixing generated runtime reports into source commits.
