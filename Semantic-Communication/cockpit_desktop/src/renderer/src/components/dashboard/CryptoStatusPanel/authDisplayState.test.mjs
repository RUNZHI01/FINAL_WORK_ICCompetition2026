import test from 'node:test'
import assert from 'node:assert/strict'

import { resolveAuthDisplayState } from './authDisplayState.ts'

test('auth control state overrides stale crypto status for display', () => {
  assert.deepEqual(resolveAuthDisplayState(true, false), {
    known: true,
    enabled: true,
    label: 'ML-DSA + SM2',
  })
})

test('auth status still falls back to crypto status when control state is absent', () => {
  assert.deepEqual(resolveAuthDisplayState(undefined, false), {
    known: true,
    enabled: false,
    label: '未启用',
  })
})
