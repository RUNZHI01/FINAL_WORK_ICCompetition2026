import test from 'node:test'
import assert from 'node:assert/strict'

import {
  batchMatchesCurrentServiceMode,
  isDashboardBatchRunning,
  isDashboardWorkRunning,
  shouldDisplayDashboardBatch,
} from './dashboardBatchDisplayState.ts'

test('does not display stale ROI batch after switching back to full frame mode', () => {
  assert.equal(
    shouldDisplayDashboardBatch(
      { status: 'done', batch_job_id: 'roi-1', service_mode: 'ROI_ONLY' },
      'roi-1',
      'FULL_FRAME',
    ),
    false,
  )
})

test('does not display stale alert batch after switching back to full frame mode', () => {
  assert.equal(
    shouldDisplayDashboardBatch(
      { status: 'running', batch_job_id: 'alert-1', service_mode: 'ALERT_ONLY' },
      'alert-1',
      'FULL_FRAME',
    ),
    false,
  )
})

test('keeps legacy batches without service_mode compatible with full frame mode', () => {
  assert.equal(batchMatchesCurrentServiceMode(undefined, 'FULL_FRAME'), true)
  assert.equal(
    shouldDisplayDashboardBatch(
      { status: 'done', batch_job_id: 'full-1' },
      null,
      'FULL_FRAME',
    ),
    true,
  )
})

test('keeps matching ROI batch visible while ROI mode is active', () => {
  assert.equal(
    shouldDisplayDashboardBatch(
      { status: 'done', batch_job_id: 'roi-1', service_mode: 'ROI_ONLY' },
      null,
      'ROI_ONLY',
    ),
    true,
  )
})

test('treats launching batches as active dashboard work', () => {
  assert.equal(isDashboardBatchRunning({ status: 'launching' }), true)
})

test('keeps dashboard work running when system active inference has already refreshed', () => {
  assert.equal(
    isDashboardWorkRunning(undefined, {
      running: true,
      request_state: 'running',
      progress: { current_stage: 'USRP 数据面 0/300' },
    }),
    true,
  )
})
