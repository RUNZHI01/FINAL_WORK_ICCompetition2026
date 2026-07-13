import test from 'node:test'
import assert from 'node:assert/strict'

import { getBatchStateRefetchInterval, getSystemStatusRefetchInterval } from './pollingPolicy.js'

test('batch polling stays hot only while a batch is active', () => {
  assert.equal(getBatchStateRefetchInterval({ status: 'running' }), 2000)
  assert.equal(getBatchStateRefetchInterval({ status: 'launching' }), 2000)
  assert.equal(getBatchStateRefetchInterval({ status: 'done' }), false)
  assert.equal(getBatchStateRefetchInterval({ status: 'idle' }), false)
  assert.equal(getBatchStateRefetchInterval(null), false)
})

test('system status polling keeps hardware telemetry visibly fresh', () => {
  assert.equal(getSystemStatusRefetchInterval({ active_inference: { running: true } }), 3000)
  assert.equal(getSystemStatusRefetchInterval({ active_inference: { request_state: 'running' } }), 3000)
  assert.equal(getSystemStatusRefetchInterval({ active_inference: { running: false } }), 3000)
  assert.equal(getSystemStatusRefetchInterval(null), 3000)
})
