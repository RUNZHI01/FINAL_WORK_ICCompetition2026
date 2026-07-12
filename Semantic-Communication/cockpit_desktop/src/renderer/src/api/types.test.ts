import test from 'node:test'
import assert from 'node:assert/strict'

import { extractIqAuditTimeline } from './types.js'

test('IQ audit timeline hydrates aggregated runtime profiling rows', () => {
  const rows = extractIqAuditTimeline({
    runtime_profiling: {
      top_ops: [
        {
          name: 'decode_tail',
          mean_duration_us: 12500,
          mean_percent: 62.5,
          mean_count: 3,
          devices: ['cpu'],
          samples: 8,
        },
        {
          name: 'copy_payload',
          mean_duration_us: 7500,
          mean_percent: 37.5,
        },
      ],
    },
  })

  assert.deepEqual(rows, [
    {
      name: 'decode_tail',
      duration_ms: 12.5,
      percent: 62.5,
      count: 3,
      device: 'cpu',
      samples: 8,
    },
    {
      name: 'copy_payload',
      duration_ms: 7.5,
      percent: 37.5,
    },
  ])
})

test('IQ audit timeline falls back to sample profile rows', () => {
  const rows = extractIqAuditTimeline({
    runtime_profiling: {
      sample_results: [
        {
          rows: [
            {
              name: 'tail_sync',
              duration_us: 4200,
              percent: 70,
              count: 1,
              device: 'cpu',
            },
          ],
        },
      ],
    },
  })

  assert.deepEqual(rows, [
    {
      name: 'tail_sync',
      duration_ms: 4.2,
      percent: 70,
      count: 1,
      device: 'cpu',
    },
  ])
})
