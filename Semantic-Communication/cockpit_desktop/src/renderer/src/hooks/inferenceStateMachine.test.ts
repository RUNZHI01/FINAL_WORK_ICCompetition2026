import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildBatchCompletionToken,
  hasCompletedBatchComparisonMetric,
  shouldHydrateRecentCurrentForBatch,
  shouldFinalizeInferenceJob,
  shouldRecordCompletedBatchComparison,
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

test('completed batch benchmark can hydrate comparison even after pending id was missed', () => {
  const batch = {
    status: 'done',
    batch_job_id: 'batch-1783519328-300',
    engine: 'tvm',
    completed: 300,
    total: 300,
    benchmark: {
      inference_ms: {
        n: 1,
        min_ms: 252.35,
        max_ms: 252.35,
        mean_ms: 252.35,
        median_ms: 252.35,
        p95_ms: null,
      },
      total_ms: {
        n: 1,
        min_ms: 1048.45,
        max_ms: 1048.45,
        mean_ms: 1048.45,
        median_ms: 1048.45,
        p95_ms: null,
      },
    },
  }

  assert.equal(hasCompletedBatchComparisonMetric(batch), true)
  assert.equal(shouldRecordCompletedBatchComparison('some-other-batch', batch), true)
})

test('completed batch without benchmark still respects current pending batch gate', () => {
  const batch = {
    status: 'done',
    batch_job_id: 'batch-without-benchmark',
    engine: 'tvm',
    completed: 300,
    total: 300,
  }

  assert.equal(hasCompletedBatchComparisonMetric(batch), false)
  assert.equal(shouldRecordCompletedBatchComparison('batch-without-benchmark', batch), true)
  assert.equal(shouldRecordCompletedBatchComparison('some-other-batch', batch), false)
})
