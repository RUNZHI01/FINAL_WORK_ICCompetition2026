import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const cssPath = join(dirname(fileURLToPath(import.meta.url)), 'DashboardPageMinimal.module.css')
const tsxPath = join(dirname(fileURLToPath(import.meta.url)), 'DashboardPageMinimal.tsx')
const cryptoPanelPath = join(dirname(fileURLToPath(import.meta.url)), '../components/dashboard/CryptoStatusPanel/CryptoStatusPanel.tsx')
const cryptoPanelCssPath = join(dirname(fileURLToPath(import.meta.url)), '../components/dashboard/CryptoStatusPanel/CryptoStatusPanel.module.css')
const css = readFileSync(cssPath, 'utf8')
const tsx = readFileSync(tsxPath, 'utf8')
const cryptoPanelTsx = readFileSync(cryptoPanelPath, 'utf8')
const cryptoPanelCss = readFileSync(cryptoPanelCssPath, 'utf8')

function cssBlockFrom(source, selector) {
  const match = source.match(new RegExp(`${selector.replace('.', '\\.')}\\s*\\{([\\s\\S]*?)\\}`))
  assert.ok(match, `${selector} block should exist`)
  return match[1]
}

function cssBlock(selector) {
  return cssBlockFrom(css, selector)
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

test('IQ audit panel renders batch IQ tail audit metrics, not runtime profiling', () => {
  assert.match(tsx, /cryptoData\?\.batch_iq_tail_audit/)
  assert.doesNotMatch(tsx, /extractIqAuditTimeline/)
})

test('IQ direct diagnostics merges record and radio sample counts', () => {
  assert.match(tsx, /IQ直传链路诊断/)
  assert.match(tsx, /label:\s*'样本数'/)
  assert.doesNotMatch(tsx, /label:\s*'记录数'/)
  assert.doesNotMatch(tsx, /label:\s*'样本'/)
})

test('IQ direct diagnostics renders tail timing as a threshold axis', () => {
  assert.match(tsx, /尾部时间分布/)
  assert.match(tsx, /className=\{s\.iqTailAxis\}/)
  assert.match(tsx, /total_gt_250ms_count/)
  assert.match(tsx, /total_gt_275ms_count/)
  assert.match(tsx, /total_gt_500ms_count/)
  assert.match(css, /\.iqTailAxis\s*\{/)
})

test('IQ direct quality labels use the same gray tone as security metric labels', () => {
  const block = cssBlock('.iqQualityLabel')
  assert.match(block, /color:\s*var\(--color-text-tertiary\);/)
})

test('IQ direct diagnostic tail captures keep neutral containers with red values only', () => {
  const tailBlock = cssBlock('.iqTailItemFail')
  const axisBlock = cssBlock('.iqTailAxisItemFail')
  const axisMarkerBlock = cssBlock('.iqTailAxisItemFail::before')

  assert.doesNotMatch(tailBlock, /background:\s*rgba\(254,\s*242,\s*242/)
  assert.doesNotMatch(tailBlock, /border-color:\s*rgba\(220,\s*38,\s*38/)
  assert.doesNotMatch(axisBlock, /background:\s*rgba\(254,\s*242,\s*242/)
  assert.doesNotMatch(axisBlock, /border-color:\s*rgba\(220,\s*38,\s*38/)
  assert.doesNotMatch(axisMarkerBlock, /background:\s*var\(--color-error\)/)
  assert.match(css, /\.iqTailValueFail\s*\{[\s\S]*color:\s*var\(--color-error\);/)
  assert.match(css, /\.iqTailAxisValueFail\s*\{[\s\S]*color:\s*var\(--color-error\);/)
})

test('USRP progress headline avoids duplicating current-stage wording', () => {
  assert.doesNotMatch(tsx, /mainProgressStageText[\s\S]*`当前阶段：/)
  assert.doesNotMatch(tsx, /:\s*'当前阶段：等待启动'/)
})

test('USRP idle progress does not render a duplicate pending detail', () => {
  assert.doesNotMatch(tsx, /mainProgressStageDetail\s*=\s*isRunning \|\| isDone[\s\S]*:\s*progressSuffix/)
  assert.match(tsx, /\{mainProgressStageDetail && <span>\{mainProgressStageDetail\}<\/span>\}/)
})

test('USRP completed progress hides the duplicate right-side count', () => {
  assert.doesNotMatch(tsx, /mainProgressStageDetail\s*=\s*isRunning \|\| isDone/)
  assert.match(tsx, /mainProgressStageDetail\s*=\s*isRunning\s*\?[\s\S]*`进度 \$\{progress\}\/\$\{totalImages\}`[\s\S]*:\s*''/)
})

test('USRP idle progress headline says ready instead of waiting to start', () => {
  assert.match(tsx, /:\s*'就绪'/)
  assert.doesNotMatch(tsx, /:\s*'等待启动'/)
})

test('IQ audit panel appears before data plane path rows', () => {
  const auditIndex = tsx.indexOf('className={s.iqAuditPanel}')
  const pathIndex = tsx.indexOf('className={s.pathGrid}')
  assert.ok(auditIndex >= 0, 'IQ audit panel should be rendered')
  assert.ok(pathIndex >= 0, 'path grid should be rendered')
  assert.ok(auditIndex < pathIndex, 'IQ audit panel should appear before path rows')
})

test('right security panel keeps batch benchmark but no longer owns IQ tail audit', () => {
  assert.match(cryptoPanelTsx, /批量 Benchmark/)
  assert.doesNotMatch(cryptoPanelTsx, />IQ尾部审计</)
})

test('batch benchmark IQ stage labels are presentation-ready Chinese text', () => {
  assert.match(cryptoPanelTsx, /label:\s*'接收就绪'/)
  assert.match(cryptoPanelTsx, /label:\s*'接收采集'/)
  assert.match(cryptoPanelTsx, /label:\s*'接收等待'/)
  assert.match(cryptoPanelTsx, /label:\s*'解码响应'/)
  assert.doesNotMatch(cryptoPanelTsx, /label:\s*'RX arm'/)
  assert.doesNotMatch(cryptoPanelTsx, /label:\s*'RX capture'/)
  assert.doesNotMatch(cryptoPanelTsx, /label:\s*'RX wait'/)
  assert.doesNotMatch(cryptoPanelTsx, /label:\s*'CAPTURE命令'/)
  assert.doesNotMatch(cryptoPanelTsx, /label:\s*'Decode响应'/)
})

test('security runtime status handshake and traffic share one row with 1-1-2 columns', () => {
  assert.match(cryptoPanelTsx, /className=\{`\$\{s\.metricGrid\} \$\{s\.runtimeGrid\}`\}/)
  assert.match(cryptoPanelTsx, /label:\s*'加密流量'[\s\S]*half:\s*true/)

  const runtimeBlock = cssBlockFrom(cryptoPanelCss, '.runtimeGrid')
  const halfBlock = cssBlockFrom(cryptoPanelCss, '.metricHalf')
  assert.match(runtimeBlock, /grid-template-columns:\s*repeat\(4,\s*minmax\(0,\s*1fr\)\);/)
  assert.match(halfBlock, /grid-column:\s*span 2;/)
})
