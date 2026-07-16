# IQ Segmented Batch Reset

## Problem

The 300-image IQ-direct run `cockpit_usrp_usrp-1784191178` completed only 260 images after 1,684 receive attempts. All captures contained the requested 317,890 samples and reported no RX timeout or overflow. The failures came from synchronization and pilot-quality gates, and became more frequent late in the run. Existing `ANALOG_RX_BATCH_SESSION_MAX_IMAGES=16` only recycles the RX control TCP connection; it does not explicitly stop and drain the RF receive state.

The quality gates must stay in place. Relaxing them would allow the corrupted latent candidates that previously produced color-noise reconstructions to reach TVM.

## Selected Design

Keep one Cockpit batch job, security channel, remote decode worker, and final TVM job. Split only the IQ transport loop into ordered segments of 30 images. The final segment uses its actual size and is never padded.

At each segment boundary, except after the final segment:

1. Finish all in-flight work for the current segment.
2. Send `STOP` to the persistent RX server and wait until it reports idle.
3. Close the shared RX control connection and open a new one.
4. Check that the TX server is idle; do not restart it because each `SEND` is already finite.
5. Continue with the next segment without restarting SSH control masters, the remote decode worker, ML-KEM/authentication, or Cockpit.

The default applies only to serial IQ-direct transport. QPSK behavior is unchanged. Pipeline mode remains available and keeps its existing execution path because a chunk boundary cannot safely reset RF state while captures are in flight.

## Failure Handling

Per-image ARQ and the current IQ quality gates remain authoritative. After the first pass through a segment, collect only its failed images. Perform the same boundary reset, then retry that failed subset once as a segment repair pass. Successful images are not transmitted again, and accepted remote latent files remain in place.

Treat the repair subset as its own transport group. If another normal segment follows, run another boundary reset after the repair group. No two groups share RF state across their boundary.

If images still fail after the repair pass, finish the transport summary with their original indexes and do not start TVM. This preserves the all-pass publication rule and prevents a partial reconstruction directory from appearing as a valid result. Progress counts unique accepted images, not radio attempts.

## Configuration And Compatibility

Add `ANALOG_IQ_SEGMENT_SIZE`, exposed by the Cockpit runtime as `OPENAMP_IQ_SEGMENT_SIZE`. Its default is `30` for IQ-direct serial runs. A value of `0` disables segmentation and restores the current continuous long-batch behavior.

Add `ANALOG_IQ_SEGMENT_REPAIR_PASSES`, exposed as `OPENAMP_IQ_SEGMENT_REPAIR_PASSES`, with a default of `1`. A value of `0` keeps segmentation and boundary resets but disables failed-subset repair.

Existing controls retain their meaning:

- `ANALOG_PIPELINE_DEPTH=1` selects the quality-first serial path.
- Pipeline depth greater than one uses the existing pipeline path without segmented RF resets.
- `ANALOG_RX_BATCH_SESSION_MAX_IMAGES` remains a lower-level control-connection recycling limit.
- `OPENAMP_IQ_STREAMING_TVM=0` keeps TVM after the complete transport gate.

The summary records segment size, segment count, reset timings and failures, repair-pass counts, unique accepted images, total attempts, and whether compatibility mode was selected. Existing top-level pass/fail fields and output paths remain compatible with Cockpit.

## Expected Cost

Successful 30-image runs spent about 31-32 seconds after one-time worker startup. Ten in-process segments should therefore spend roughly 318 seconds on normal transport, plus about 5-20 seconds for nine boundary resets. This is an estimated 2-6% cost relative to an ideal non-degrading continuous run, but substantially less than the failed 645-second run. Starting ten independent jobs is not part of this design because repeated worker startup would add roughly 45-340 seconds.

## Verification

Unit tests cover segment slicing, a short final segment, boundary-reset ordering, failed-subset repair, unique progress counting, compatibility mode, and the unchanged pipeline path. Runtime summaries must expose reset and repair evidence.

Hardware validation runs in this order:

1. A 30-image IQ-direct serial run to confirm no regression.
2. A non-multiple batch, such as 35 images, to verify the final 5-image segment.
3. A 300-image run requiring 300 accepted latents before TVM starts.
4. Output verification that one reconstruction job contains 300 images and quality metrics are populated.
5. A continuous-mode smoke run with segment size `0` to prove the previous mode remains usable.

Record transport time, reset overhead, attempt count, failed indexes, TVM image count, reconstruction count, PSNR, and SSIM for each hardware run.
