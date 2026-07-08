import test from 'node:test'
import assert from 'node:assert/strict'

import { buildComparisonRows } from './comparisonRows.ts'

test('current-only inference result still produces comparison rows', () => {
  const rows = buildComparisonRows(
    {
      timings: {
        payload_ms: 281.077,
        total_ms: 281.077,
      },
      quality: {
        psnr_db: 37.0445,
        ssim: 0.97494,
      },
    },
    undefined,
  )

  assert.deepEqual(rows, [
    { key: 'payload_ms', metric: 'Payload (ms)', current: 281.077, baseline: undefined },
    { key: 'total_ms', metric: 'Total (ms)', current: 281.077, baseline: undefined },
    { key: 'psnr', metric: 'PSNR (dB)', current: 37.0445, baseline: undefined },
    { key: 'ssim', metric: 'SSIM', current: 0.97494, baseline: undefined },
  ])
})
