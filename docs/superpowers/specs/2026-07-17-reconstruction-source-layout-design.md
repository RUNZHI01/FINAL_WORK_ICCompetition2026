# Reconstruction Source Layout Design

## Scope

The reconstruction comparison page will expose five sources: prerecorded TVM, prerecorded MNN, prerecorded PyTorch reference, USRP-QPSK, and USRP-IQ direct. Prerecorded inference output paths and inference behavior remain unchanged. USRP output storage will be split by radio link mode.

## Output Layout

Existing prerecorded roots remain authoritative:

- TVM and PyTorch reference: `/home/user/Downloads/jscc-test/jscc/infer_outputs`
- MNN: `/home/user/Downloads/jscc-test/mnn_benchmark_outputs`

The browser distinguishes TVM and PyTorch jobs by their established directory prefixes. It does not move or rename prerecorded results.

New USRP TVM jobs use these roots:

- QPSK: `/home/user/Downloads/jscc-test-usrp/qpsk/tvm`
- IQ direct: `/home/user/Downloads/jscc-test-usrp/iq-direct/tvm`

Cockpit Demo must select the USRP root inside `_usrp_stage_access()` from the effective `JSCC_LINK_MODE`. This changes the actual `REMOTE_OUTPUT_BASE`; it is not only a browser-side filter. The same layout leaves room for engine-specific subdirectories such as `qpsk/mnn` without changing this feature's UI.

## Historical Migration

Board job names do not encode the link mode. Migration therefore joins the timestamp in `openamp3_usrp_<token>_current` to the corresponding host run directory `USRP292x/qpsk_batch_spool_arq_runs/cockpit_usrp_usrp-<token>`.

An IQ classification requires `phy=analog-latent-iq`, `remote_received_latent_npz`, or equivalent analog-run metadata. A QPSK classification requires QPSK schema fields such as `max_arq_rounds`, `chunk_bytes`, or `cpp_sync_mode`. Recovery jobs may inherit a classification from their base token. Jobs without evidence stay in the legacy `/home/user/Downloads/jscc-test-usrp/tvm` root and are recorded as unresolved; the migration must not guess or overwrite an existing destination.

The migration writes an auditable JSON report and is idempotent. `docs/USRP_OUTPUT_LAYOUT.md` will document the final counts, unresolved jobs, new layout, and rollback procedure.

## Comparison Page

A `reconstruction-source` select is placed in the upper-right job controls. Changing it clears the selected job, preview, quality marker, and cached UI state, then requests jobs for that source. Jobs remain ordered newest first and reconstruction images are still downloaded only after the user clicks **拉取**.

The service owns a source registry containing each source's remote root and optional name filter. Missing roots and empty sources return an empty job list with a source-specific status message; they never fall back to another source. Existing original/PyTorch reference selection, per-image metrics, lazy loading, and board resource limits remain unchanged.

## Verification

Tests cover all five source mappings, prerecorded prefix filtering, USRP mode-to-output-path selection, historical classification, unresolved-job handling, idempotent migration, API source validation, and browser state reset. A board dry run verifies migration decisions before any move. Final acceptance lists all five sources in the page and confirms one new QPSK and one new IQ job are written to their respective roots.
