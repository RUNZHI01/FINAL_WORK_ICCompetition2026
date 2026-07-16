import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const cssPath = join(dirname(fileURLToPath(import.meta.url)), 'DashboardPageMinimal.module.css')
const tsxPath = join(dirname(fileURLToPath(import.meta.url)), 'DashboardPageMinimal.tsx')
const cryptoPanelPath = join(dirname(fileURLToPath(import.meta.url)), '../components/dashboard/CryptoStatusPanel/CryptoStatusPanel.tsx')
const cryptoPanelCssPath = join(dirname(fileURLToPath(import.meta.url)), '../components/dashboard/CryptoStatusPanel/CryptoStatusPanel.module.css')
const electronMainPath = join(dirname(fileURLToPath(import.meta.url)), '../../../../electron/main.ts')
const css = readFileSync(cssPath, 'utf8')
const tsx = readFileSync(tsxPath, 'utf8')
const cryptoPanelTsx = readFileSync(cryptoPanelPath, 'utf8')
const cryptoPanelCss = readFileSync(cryptoPanelCssPath, 'utf8')
const electronMain = readFileSync(electronMainPath, 'utf8')

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

test('reconstruction comparison entry follows the board output directory', () => {
  assert.match(tsx, /板端重建输出目录[\s\S]*本次重建对比图/)
  assert.match(css, /\.pathOutputContent\s*\{[\s\S]*display:\s*grid;/)
})

test('external comparison link is restricted to loopback http', () => {
  assert.match(electronMain, /parsed\.protocol !== 'http:'/)
  assert.match(electronMain, /\['127\.0\.0\.1', 'localhost'\]\.includes\(parsed\.hostname\)/)
})

test('IQ audit panel is gated to IQ-direct USRP mode', () => {
  const panelGate = tsx.match(/const showIqAuditPanel[\s\S]*?\n  const inputModeLabel/)
  assert.ok(panelGate, 'showIqAuditPanel declaration should exist')
  assert.match(tsx, /const selectedLinkMode\s*=\s*pendingJsccLinkMode \?\? configuredLinkMode/)
  assert.match(panelGate[0], /activeTransport === 'usrp'[\s\S]*selectedLinkMode === 'iq-direct'/)
  assert.doesNotMatch(panelGate[0], /activeLinkMode === 'iq-direct'/)
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

test('active batch total overrides the live job default progress total', () => {
  assert.match(tsx, /liveExpectedCount\s*=\s*Math\.max\(1,\s*activeBatch\?\.total\s*\?\?\s*liveProgress\?\.expected_count\s*\?\?\s*1\)/)
})

test('USRP progress headline omits the redundant numeric progress control', () => {
  assert.doesNotMatch(tsx, /mainProgressStageDetail/)
  assert.doesNotMatch(tsx, /`进度 \$\{progress\}\/\$\{totalImages\}`/)
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

test('security config shows the effective protection scope from crypto status', () => {
  assert.match(cryptoPanelTsx, /label:\s*'作用范围'/)
  assert.match(cryptoPanelTsx, /data\.security_scope_label/)
  assert.doesNotMatch(cryptoPanelTsx, /security_scope_note/)
})

test('server identity is shown with board password metadata instead of security config', () => {
  assert.match(tsx, /const cryptoServerId\s*=/)
  assert.match(tsx, /className=\{s\.boardPasswordMeta\}[\s\S]*服务端标识:\s*\{cryptoServerId\}/)
  assert.doesNotMatch(cryptoPanelTsx, /label:\s*'服务端标识'/)

  const metaBlock = cssBlock('.boardPasswordMeta')
  assert.match(metaBlock, /color:\s*var\(--color-text-secondary\);/)
})
