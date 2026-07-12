import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const cssPath = join(dirname(fileURLToPath(import.meta.url)), 'DashboardPageMinimal.module.css')
const tsxPath = join(dirname(fileURLToPath(import.meta.url)), 'DashboardPageMinimal.tsx')
const css = readFileSync(cssPath, 'utf8')
const tsx = readFileSync(tsxPath, 'utf8')

function cssBlock(selector) {
  const match = css.match(new RegExp(`${selector.replace('.', '\\.')}\\s*\\{([\\s\\S]*?)\\}`))
  assert.ok(match, `${selector} block should exist`)
  return match[1]
}

test('alert mode log stream can display five coordinate lines without crowding', () => {
  const block = cssBlock('.alertModeLogStream')
  assert.match(block, /height:\s*108px;/)
})

test('live log entries use an explicit readable line height', () => {
  const block = cssBlock('.logEntry')
  assert.match(block, /line-height:\s*14px;/)
})

test('data plane card does not render the bulky readiness grid', () => {
  assert.doesNotMatch(tsx, /className=\{s\.readinessGrid\}/)
  assert.doesNotMatch(tsx, /className=\{s\.usrpRxConfig\}/)
})

test('board password card owns the board session readiness badge', () => {
  assert.match(tsx, /className=\{`\$\{s\.boardSessionBadge\}/)
  assert.match(css, /\.boardSessionBadge\s*\{/)
})

test('remote USRP RX directory save action is colocated with the board input path row', () => {
  assert.match(tsx, /板端输入\/RX 目录[\s\S]*handleSaveRemoteUsrPRxDir/)
})

test('IQ audit panel is gated to IQ-direct USRP mode', () => {
  assert.match(tsx, /showIqAuditPanel\s*=\s*activeTransport === 'usrp'[\s\S]*activeLinkMode === 'iq-direct'/)
})

test('IQ audit panel appears before data plane path rows', () => {
  const auditIndex = tsx.indexOf('className={s.iqAuditPanel}')
  const pathIndex = tsx.indexOf('className={s.pathGrid}')
  assert.ok(auditIndex >= 0, 'IQ audit panel should be rendered')
  assert.ok(pathIndex >= 0, 'path grid should be rendered')
  assert.ok(auditIndex < pathIndex, 'IQ audit panel should appear before path rows')
})
