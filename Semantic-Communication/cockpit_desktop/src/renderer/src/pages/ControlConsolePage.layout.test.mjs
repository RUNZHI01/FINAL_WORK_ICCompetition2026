import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const pageDir = dirname(fileURLToPath(import.meta.url))
const tsx = readFileSync(join(pageDir, 'ControlConsolePage.tsx'), 'utf8')
const css = readFileSync(join(pageDir, 'ControlConsolePage.module.css'), 'utf8')

test('event timeline keeps the newest event first and highlighted', () => {
  assert.match(tsx, /rightTime[^\n]+- \(Number\.isNaN\(leftTime\)/)
  assert.match(tsx, /const isLatest = i === 0/)
  assert.match(tsx, /timelineRef\.current\.scrollTop = 0/)
})

test('SAFE_STOP uses a green label and light green surface', () => {
  const base = css.match(/\.btnRecover\s*\{([\s\S]*?)\}/)?.[1] ?? ''
  const hover = css.match(/\.btnRecover:hover:not\(:disabled\)\s*\{([\s\S]*?)\}/)?.[1] ?? ''
  assert.match(base, /background:\s*rgba\(5, 150, 105, 0\.06\)/)
  assert.match(base, /color:\s*var\(--color-success\)/)
  assert.match(hover, /background:\s*rgba\(5, 150, 105, 0\.12\)/)
  assert.match(hover, /border-color:\s*var\(--color-success\)/)
})

test('security FIT group uses a natural Chinese label', () => {
  assert.match(tsx, /label: '安全防护验证'/)
  assert.doesNotMatch(tsx, /负向自检/)
})
