# Cockpit Batch Launch Feedback

## Problem

The batch API creates a `launching` state before ML-KEM admission and USRP job initialization, but the POST request does not return the batch job ID until those synchronous steps finish. During that interval the renderer has no pending job ID, hides the polled `launching` state, and leaves the operator with an apparently idle screen.

## Design

Keep the existing three-stage progress bar for real work only: host image to latent, USRP transport/decode, and board inference. Do not advance any stage before its reported progress changes.

Add launch feedback at both boundaries:

- The backend batch state includes a concise `current_stage` and `message` as soon as it enters `launching`: the task was accepted and security admission, resident USRP service checks, and job initialization are in progress.
- The renderer accepts the visible non-hidden `launching` batch even before `pendingBatchJobId` is available. If backend text is absent, it uses the same conservative fallback copy.
- The status badge reads `启动中`. The three progress segments remain pending until the backend changes to `running` and reports stage progress.
- Once host preprocessing begins, normal stage labels and counts replace the launch message. Failed launch responses continue to use the existing error path.

## Testing

Add regression coverage for a visible `launching` batch without a pending job ID, backend launch-state copy, and the transition from launch feedback to real stage progress. Run the focused Node and Python tests plus Cockpit type checking. Do not restart Cockpit while the current 300-image run is active.

## Scope

This change only fixes operator feedback. It does not alter ML-KEM, USRP startup order, batch timing, or inference behavior. UI performance work is tracked separately because it involves hardware acceleration and polling payloads.
