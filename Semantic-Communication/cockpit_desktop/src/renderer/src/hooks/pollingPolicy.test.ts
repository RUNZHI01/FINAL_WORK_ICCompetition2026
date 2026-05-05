import test from 'node:test'
import assert from 'node:assert/strict'

import { getBatchStateRefetchInterval } from './pollingPolicy.js'

test('batch polling stays hot only while a batch is active', () => {
  assert.equal(getBatchStateRefetchInterval({ status: 'running' }), 2000)
  assert.equal(getBatchStateRefetchInterval({ status: 'launching' }), 2000)
  assert.equal(getBatchStateRefetchInterval({ status: 'done' }), false)
  assert.equal(getBatchStateRefetchInterval({ status: 'idle' }), false)
  assert.equal(getBatchStateRefetchInterval(null), false)
})
