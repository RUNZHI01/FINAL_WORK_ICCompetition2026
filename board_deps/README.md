# Board dependencies

This directory contains the board-side runtime files that the native Electron
demo expects when it talks to the Phytium Pi through Tailscale.

The files were extracted from the live board `user@100.121.87.73`:

- `crypto/liboqs-dist-aarch64.tar.gz`
  - Restores to `/home/user/liboqs-dist`.
- `crypto/tongsuo-runtime-aarch64.tar.gz`
  - Restores to `/usr/local/tongsuo`.
- `crypto/libtongsuo_sig_bridge.so`
  - Restores to `/home/user/libtongsuo_sig_bridge.so`.
- `tvm/baseline/optimized_model.so`
  - Restores to `/home/user/Downloads/5.1TVM优化结果/tvm_tune_logs/optimized_model.so`.
- `tvm/current/optimized_model.so`
  - Restores to `/home/user/Downloads/jscc-test/jscc_opus_final_mean4_v7_20260406/tvm_tune_logs/optimized_model.so`.
- `tvm/current_legacy/optimized_model.so`
  - Restores to `/home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so`.
- `tvm/runtime/tvm310-safe-runtime-aarch64.tar.gz`
  - Board-side TVM runtime package required by `tvm_inference_helper.py`.
  - Restores the TVM Python source path, `tvm_ffi`, and runtime shared
    libraries under `/home/user`.
- `mnn/origin/model1.mnn`
  - Restores to `/home/user/Downloads/MNNversion/origin/model1.mnn`.
- `inputs/places365-latents.tar.gz`
  - Restores the TVM input directory under `/home/user/Downloads/jscc-test/简化版latent`.
- `inputs/mnn-encoder-outputs.tar.gz`
  - Restores the MNN input directory under `/home/user/Downloads/jscc-test/encoder_outputs`.
- `tools/gen_identity_keys.py`
  - Restores to `/home/user/gen_identity_keys.py` for SM2 / ML-DSA identity key generation.
- `openamp/firmware/openamp_core0.elf`
  - Current firmware loaded by `/sys/class/remoteproc/remoteproc0/firmware`.
- `openamp/firmware/phytium-pi-board-v3-openamp.dtb`
  - Current OpenAMP DTB used by the Phytium Pi demo path.
- `openamp/source/release_v1.4.0-jobdone-v14-openamp-source.tar.gz`
  - Board-side OpenAMP firmware source tree for the version that matches the
  installed `openamp_core0.elf`, excluding generated build/cache/object files.
  - Stored as `release_v1.4.0-jobdone-v14-openamp-source.tar.gz.part-*` because
    the complete archive is larger than GitHub's normal per-file limit.
  - Reassemble with `bash board_deps/reassemble-large-files.sh`.
- `openamp/source/release_v1.4.0-jobdone-v14-openamp-build-artifacts.tar.gz`
  - Current OpenAMP build metadata, ELF, map, config, and app source files.
- `openamp/source/semantic-communication-openamp-master-07ee28f.tar.gz`
  - OpenAMP-related source, patches, board snapshot, and control-plane code
    archived from `RUNZHI01/Semantic-Communication` `master@07ee28f`.
- `openamp/runtime/openamp-demo-runtime-services.tar.gz`
  - Board-side OpenAMP helper services under `/home/user/.openamp-demo`.
- `crypto/public_keys/board-auth-public-keys.tar.gz`
  - Public SM2 / ML-DSA identity keys only. Private keys are intentionally not
    committed.
- `runtime/mlkem-remote-runtime-snapshot.tar.gz`
  - Current board-side ML-KEM TCP server, helper scripts, and `mlkem_link`
    package snapshot.

Use these scripts on the board:

```bash
bash board_deps/install-board-deps.sh
bash board_deps/verify-board-deps.sh
```

Use this script from a Docker/Tailscale host to refresh the files from the live
board:

```bash
REMOTE_PASS=... bash docker/pull-board-deps.sh
```

On Windows PowerShell:

```powershell
$env:REMOTE_PASS="..."
.\docker\pull-board-deps.ps1
```

`downloads/uhd-v4.6.0.0` is intentionally not stored here because the UHD image
archive is larger than GitHub's normal file limit. Keep it as an external
download or release asset if the final submission requires it.
