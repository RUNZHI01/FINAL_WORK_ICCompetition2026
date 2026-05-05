import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildBatchCompletionToken,
  shouldHydrateRecentCurrentForBatch,
  shouldFinalizeInferenceJob,
  shouldRefreshCompletedBatch,
  shouldTrackInferenceJob,
} from './inferenceStateMachine.js'

test('completed inference should not keep active polling job', () => {
  const payload = {
    job_id: 'job-42',
    request_state: 'completed',
    status: 'success',
  }

  assert.equal(shouldTrackInferenceJob(payload), false)
  assert.equal(shouldFinalizeInferenceJob(payload, 'job-42'), true)
})

test('non-running intermediate states should not finalize polling job', () => {
  const payload = {
    job_id: 'job-43',
    request_state: 'accepted',
    status: 'running',
  }

  assert.equal(shouldTrackInferenceJob(payload), true)
  assert.equal(shouldFinalizeInferenceJob(payload, 'job-43'), false)
})

test('batch completion token is stable for the same settled batch', () => {
  const batch = {
    status: 'done',
    batch_job_id: 'batch-1',
    finished_at: 123456,
    total: 300,
    completed: 300,
    engine: 'tvm',
  }

  const token = buildBatchCompletionToken(batch)
  assert.equal(shouldRefreshCompletedBatch(null, batch), true)
  assert.equal(shouldRefreshCompletedBatch(token, batch), false)
})

test('tvm and mnn batch completion should hydrate recent current result', () => {
  assert.equal(shouldHydrateRecentCurrentForBatch({ status: 'done', engine: 'mnn' }), true)
  assert.equal(shouldHydrateRecentCurrentForBatch({ status: 'done', engine: 'tvm' }), true)
  assert.equal(shouldHydrateRecentCurrentForBatch({ status: 'done' }), false)
})
