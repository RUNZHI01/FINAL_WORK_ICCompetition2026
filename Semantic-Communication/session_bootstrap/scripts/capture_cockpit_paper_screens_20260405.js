#!/usr/bin/env node

const fs = require('fs')
const path = require('path')

let chromium
try {
  ;({ chromium } = require('playwright'))
} catch (error) {
  console.error('Missing dependency: playwright')
  console.error('Install it in a user-scoped environment, then rerun this script.')
  console.error(String(error))
  process.exit(1)
}

const ROOT = path.resolve(__dirname, '..', '..')
const OUT_DIR = process.env.COCKPIT_PAPER_SCREEN_DIR || path.join(ROOT, 'output', 'playwright')
const RENDER_URL = process.env.COCKPIT_RENDER_URL || 'http://127.0.0.1:5173/'

fs.mkdirSync(OUT_DIR, { recursive: true })

const NOW = '2026-04-05T17:28:00+08:00'

const systemStatus = {
  generated_at: NOW,
  board_access: { configured: true, connection_ready: true, probe_ready: true },
  execution_mode: { label: '3-core Linux + RTOS', tone: 'warn', summary: '演示模式' },
  aircraft_position: {},
  live: {
    board_online: true,
    guard_state: 'RUNNING',
    last_fault_code: 'HEARTBEAT_TIMEOUT',
    active_job_id: 'job-300-20260405',
    total_fault_count: 3,
    target: 'cortex-a72 + neon',
    last_probe_at: NOW,
  },
  active_inference: {
    running: true,
    job_id: 'job-300-20260405',
    request_state: 'running',
    status_category: 'current live',
    message: 'current live 300/300',
  },
  last_inference: {
    status: 'ok',
    request_state: 'done',
    variant: 'current',
    timings: { payload_ms: 345.3, total_ms: 353.4 },
    quality: { psnr_db: 35.66, ssim: 0.9728 },
  },
  recent_results: {
    current: {
      status: 'ok',
      request_state: 'done',
      variant: 'current',
      timings: {
        payload_ms: 345.3,
        prepare_ms: 21.6,
        total_ms: 353.4,
      },
      quality: { psnr_db: 35.66, ssim: 0.9728 },
    },
    baseline: {
      status: 'ok',
      request_state: 'done',
      variant: 'baseline',
      timings: {
        payload_ms: 811.5,
        prepare_ms: 32.1,
        total_ms: 846.7,
      },
      quality: { psnr_db: 35.44, ssim: 0.9719 },
    },
  },
  last_fault: {
    status: 'ok',
    fault_type: 'timeout',
    message: 'heartbeat timeout latched and archived',
    last_fault_code: 'HEARTBEAT_TIMEOUT',
  },
  safety_panel: {
    panel_label: 'Safety',
    safe_stop_state: 'READY',
    guard_state: 'RUNNING',
    last_fault_code: 'HEARTBEAT_TIMEOUT',
    total_fault_count: 3,
    board_online: true,
  },
  job_manifest_gate: {
    status: 'ok',
    label: 'ALLOW',
    summary: 'artifact hash + param digest admitted',
  },
  link_director: {
    status: 'ok',
    label: '10 dB bestcurrent',
    selected_profile_id: 'bestcurrent',
  },
  operator_cue: {
    status_label: 'ready',
    current_scene_label: 'Current live 300/300',
  },
  event_spine: {
    session_id: 'demo-session-001',
    event_count: 251,
    last_event_at: NOW,
    archive_enabled: true,
  },
}

const snapshot = {
  generated_at: NOW,
  project: {
    name: '飞腾弱网语义回传',
    focus: 'OpenAMP control plane + TVM/MNN',
    final_verdict: 'current live 300/300',
    trusted_current_sha: '8b115',
    final_live_firmware_sha: '2d08',
  },
  mode: { label: '3-core + RTOS demo' },
  board: { target: 'cortex-a72 + neon' },
  stats: {
    p0_milestones_verified: 9,
    fit_final_pass_count: 3,
    payload_current_ms: 345.3,
    end_to_end_current_ms: 353.4,
  },
  aircraft_position: {},
  performance: { payload_current_ms: 345.3 },
  weak_network: { snr_db: 10, profile: 'bestcurrent' },
}

const aircraft = {
  source_kind: 'backend_stub',
  source_status: 'ok',
  source_label: 'Backend stub contract',
  mission_call_sign: 'M9-DEMO',
  position: { latitude: 30.5728, longitude: 104.0668 },
  kinematics: { heading_deg: 78.0, altitude_m: 1820.0, ground_speed_kph: 248.0, vertical_speed_mps: 1.4 },
  fix: { type: '3D', confidence_m: 6.5, satellites: 11 },
  sample: { sequence: 4, captured_at: '04-05 02:38:05', producer_id: 'backend_http_post', transport: 'http' },
}

const crypto = {
  kem_backend: 'tongsuo-ML-KEM-768',
  cipher_suite: 'AES-256-GCM',
  channel_state: 'ready',
  handshake_ms: 18.7,
  inference_ms: 345.3,
  session_count: 12,
  last_sha256_match: true,
  enabled: true,
  board_configured: true,
}

const runInference = {
  status: 'ok',
  request_state: 'running',
  status_category: 'running',
  variant: 'current',
  job_id: 'job-300-20260405',
  source_label: 'paper capture mock',
  message: 'current live task started',
}

const inferenceProgress = {
  status: 'ok',
  request_state: 'running',
  status_category: 'running',
  variant: 'current',
  job_id: 'job-300-20260405',
  source_label: 'paper capture mock',
  message: 'current live task is running',
  live_progress: {
    state: 'running',
    label: 'Current live 300/300',
    tone: 'active',
    percent: 82.3,
    phase_percent: 82.3,
    completed_count: 247,
    expected_count: 300,
    remaining_count: 53,
    completion_ratio: 0.823,
    current_stage: 'current 300/300 · heartbeat healthy · awaiting final archive',
  },
}

function fulfillJson(route, payload) {
  route.fulfill({
    status: 200,
    contentType: 'application/json; charset=utf-8',
    body: JSON.stringify(payload),
  })
}

async function main() {
  const browser = await chromium.launch({ headless: process.env.COCKPIT_HEADLESS !== '0' })
  const page = await browser.newPage({
    viewport: { width: 1728, height: 1117 },
    deviceScaleFactor: 2,
  })

  await page.route('**/api/system-status', (route) => fulfillJson(route, systemStatus))
  await page.route('**/api/snapshot', (route) => fulfillJson(route, snapshot))
  await page.route('**/api/aircraft-position', (route) => fulfillJson(route, aircraft))
  await page.route('**/api/crypto-status', (route) => fulfillJson(route, crypto))
  await page.route('**/api/health', (route) => fulfillJson(route, { status: 'ok' }))
  await page.route('**/api/run-inference', (route) => fulfillJson(route, runInference))
  await page.route('**/api/inference-progress?*', (route) => fulfillJson(route, inferenceProgress))
  await page.route('**/api/probe-board', (route) => fulfillJson(route, { status: 'ok', reachable: true }))
  await page.route('**/api/run-baseline', (route) => fulfillJson(route, { status: 'ok', request_state: 'done', job_id: 'baseline-job' }))
  await page.route('**/api/inject-fault', (route) => fulfillJson(route, { status: 'ok', status_category: 'fault', fault_type: 'timeout', message: 'latched' }))
  await page.route('**/api/recover', (route) => fulfillJson(route, { status: 'ok', status_category: 'recovered', message: 'safe stop closure complete' }))

  await page.goto(RENDER_URL, { waitUntil: 'networkidle', timeout: 60000 })
  await page.waitForTimeout(1200)
  await page.getByRole('button', { name: /启动 Current 重建/ }).click()
  await page.waitForTimeout(2200)
  await page.screenshot({ path: path.join(OUT_DIR, 'cockpit_dashboard_running.png'), fullPage: true })

  await page.getByRole('button', { name: /故障注入与恢复/ }).click()
  await page.waitForTimeout(600)
  await page.screenshot({ path: path.join(OUT_DIR, 'cockpit_dashboard_faults.png'), fullPage: true })

  await browser.close()
  console.log(path.join(OUT_DIR, 'cockpit_dashboard_running.png'))
  console.log(path.join(OUT_DIR, 'cockpit_dashboard_faults.png'))
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
