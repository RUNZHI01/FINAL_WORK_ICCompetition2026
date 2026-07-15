import test from 'node:test'
import assert from 'node:assert/strict'

import { comparisonResultFromInferencePayload } from './comparisonResult.js'

test('baseline reference result can hydrate comparison from runner summary fallback', () => {
  const result = comparisonResultFromInferencePayload({
    status: 'success',
    execution_mode: 'reference',
    variant: 'baseline',
    runner_summary: {
      processed_count: 300,
      total_wall_ms: 105000,
    },
  })

  assert.deepEqual(result, {
    engine: 'pytorch',
    label: 'PyTorch参考',
    reconstructionMs: 350,
    runMs: 350,
    sampleCount: 300,
    quality: undefined,
  })
})

test('current live result falls back to nested pipeline summary when timings are absent', () => {
  const result = comparisonResultFromInferencePayload({
    status: 'success',
    execution_mode: 'live',
    variant: 'current',
    runner_summary: {
      pipeline: {
        processed_count: 300,
        ms_per_image: 251.4,
        run_median_ms: 239.8,
      },
    },
  })

  assert.deepEqual(result, {
    engine: 'tvm',
    label: 'TVM重建',
    reconstructionMs: 251.4,
    runMs: 239.8,
    sampleCount: 300,
    quality: undefined,
  })
})

test('current live result preserves quality metrics for display', () => {
  const result = comparisonResultFromInferencePayload({
    status: 'success',
    execution_mode: 'live',
    variant: 'current',
    timings: {
      total_ms: 251.4,
      payload_ms: 239.8,
    },
    quality: {
      psnr_db: 37.0445,
      ssim: 0.9749,
    },
  })

  assert.deepEqual(result, {
    engine: 'tvm',
    label: 'TVM重建',
    reconstructionMs: 251.4,
    runMs: 239.8,
    sampleCount: undefined,
    quality: {
      psnr_db: 37.0445,
      ssim: 0.9749,
    },
  })
})

test('current live ML-KEM TVM result uses board inference time for reconstruction KPI', () => {
  const result = comparisonResultFromInferencePayload({
    status: 'success',
    execution_mode: 'live',
    variant: 'current',
    control_transport: 'mlkem',
    timings: {
      total_ms: 3300,
      payload_ms: 259,
    },
  })

  assert.equal(result?.reconstructionMs, 259)
  assert.equal(result?.runMs, 259)
})

test('current live mnn result is recorded as mnn comparison', () => {
  const result = comparisonResultFromInferencePayload({
    status: 'success',
    execution_mode: 'live',
    variant: 'current',
    inference_engine: 'mnn',
    runner_summary: {
      sample_stats: {
        total_ms: {
          count: 5,
          median_ms: 329.6,
          mean_ms: 331.0,
        },
        run_ms: {
          count: 5,
          median_ms: 161.9,
          mean_ms: 163.2,
        },
      },
    },
    quality: {
      psnr_db: 37.0445,
      ssim: 0.9749,
    },
  })

  assert.deepEqual(result, {
    engine: 'mnn',
    label: 'MNN重建',
    reconstructionMs: 329.6,
    runMs: 161.9,
    sampleCount: 5,
    quality: {
      psnr_db: 37.0445,
      ssim: 0.9749,
    },
  })
})

test('current prerecorded TVM result can hydrate comparison', () => {
  const result = comparisonResultFromInferencePayload({
    status: 'success',
    execution_mode: 'prerecorded',
    variant: 'current',
    timings: {
      total_ms: 123.4,
      payload_ms: 118.2,
    },
    quality: {
      psnr_db: 37.0445,
      ssim: 0.9749,
    },
  })

  assert.deepEqual(result, {
    engine: 'tvm',
    label: 'TVM重建',
    reconstructionMs: 123.4,
    runMs: 118.2,
    sampleCount: undefined,
    quality: {
      psnr_db: 37.0445,
      ssim: 0.9749,
    },
  })
})

test('baseline fallback reference result still hydrates comparison from timings', () => {
  const result = comparisonResultFromInferencePayload({
    status: 'fallback',
    execution_mode: 'reference',
    variant: 'baseline',
    timings: {
      total_ms: 412.8,
      payload_ms: 412.8,
    },
  })

  assert.deepEqual(result, {
    engine: 'pytorch',
    label: 'PyTorch参考',
    reconstructionMs: 412.8,
    runMs: 412.8,
    sampleCount: undefined,
    quality: undefined,
  })
})

test('baseline reference result with zero timing is not shown as a comparison result', () => {
  const result = comparisonResultFromInferencePayload({
    status: 'success',
    execution_mode: 'prerecorded',
    variant: 'baseline',
    timings: {
      total_ms: 0,
      payload_ms: 0,
    },
  })

  assert.equal(result, undefined)
})
