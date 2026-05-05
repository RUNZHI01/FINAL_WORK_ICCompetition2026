import type {
  AircraftPositionResponse,
  ArchiveSessionDetail,
  ArchiveSessionsResponse,
  BoardAccessPayload,
  BoardAccessResponse,
  DemoSnapshot,
  EventSpineResponse,
  FaultInjectResponse,
  GatePreviewResponse,
  HealthResponse,
  LinkDirectorStatus,
  LinkDirectorSwitchResponse,
  ProbeBoardResponse,
  RecoverResponse,
  RunInferenceResponse,
  SystemStatusResponse,
} from './types'
import type { BatchInferenceResponse, BatchStateResponse, CryptoStatusResponse, CryptoTestResult } from './types/crypto'

/** Vite dev server proxies /api → Python；生产直连本机（CORS 已开）。 */
const runtimeBackendUrl = window.cockpit?.backendUrl?.replace(/\/+$/, '') ?? ''
const API_PREFIX = import.meta.env.DEV ? '' : runtimeBackendUrl || 'http://127.0.0.1:8079'

function summarizeResponseText(text: string): string {
  const raw = String(text || '').trim()
  if (!raw) return ''
  const stripped = raw
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
  return (stripped || raw).slice(0, 400)
}

async function readJson<T>(response: Response): Promise<T> {
  const text = await response.text()
  if (!text.trim()) {
    return {} as T
  }
  try {
    return JSON.parse(text) as T
  } catch {
    const summary = summarizeResponseText(text)
    if (!response.ok) {
      return { message: summary || `HTTP ${response.status}` } as T
    }
    throw new Error(summary || '后端返回了非 JSON 响应')
  }
}

function throwIfNotOk(response: Response, body: unknown): void {
  if (response.ok) return
  let message = `HTTP ${response.status}`
  if (typeof body === 'object' && body !== null && 'message' in body) {
    message = String((body as { message?: unknown }).message ?? message)
  }
  throw new Error(message)
}

async function postJson<T>(url: string, body: unknown = {}): Promise<T> {
  const response = await fetch(`${API_PREFIX}${url}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const data = await readJson<T & { message?: string }>(response)
  throwIfNotOk(response, data)
  return data
}

// ---------------------------------------------------------------------------
// GET
// ---------------------------------------------------------------------------

export async function getHealth(): Promise<HealthResponse> {
  const r = await fetch(`${API_PREFIX}/api/health`)
  const d = await readJson<HealthResponse & { message?: string }>(r)
  throwIfNotOk(r, d)
  return d
}

export async function getSystemStatus(): Promise<SystemStatusResponse> {
  const r = await fetch(`${API_PREFIX}/api/system-status`)
  const d = await readJson<SystemStatusResponse & { message?: string }>(r)
  throwIfNotOk(r, d)
  return d
}

export async function getSnapshot(): Promise<DemoSnapshot> {
  const r = await fetch(`${API_PREFIX}/api/snapshot`)
  const d = await readJson<DemoSnapshot & { message?: string }>(r)
  throwIfNotOk(r, d)
  return d
}

export async function getAircraftPosition(): Promise<AircraftPositionResponse> {
  const r = await fetch(`${API_PREFIX}/api/aircraft-position`)
  const d = await readJson<AircraftPositionResponse & { message?: string }>(r)
  throwIfNotOk(r, d)
  return d
}

export async function getLinkDirector(): Promise<LinkDirectorStatus> {
  const r = await fetch(`${API_PREFIX}/api/link-director`)
  const d = await readJson<LinkDirectorStatus & { message?: string }>(r)
  throwIfNotOk(r, d)
  return d
}

export async function getEventSpine(limit = 25): Promise<EventSpineResponse> {
  const r = await fetch(`${API_PREFIX}/api/event-spine?limit=${limit}`)
  const d = await readJson<EventSpineResponse & { message?: string }>(r)
  throwIfNotOk(r, d)
  return d
}

export async function getArchiveSessions(limit = 25): Promise<ArchiveSessionsResponse> {
  const r = await fetch(`${API_PREFIX}/api/archive/sessions?limit=${limit}`)
  const d = await readJson<ArchiveSessionsResponse & { message?: string }>(r)
  throwIfNotOk(r, d)
  return d
}

export async function getArchiveSession(sessionId: string, limit = 25): Promise<ArchiveSessionDetail> {
  const r = await fetch(`${API_PREFIX}/api/archive/session?session_id=${encodeURIComponent(sessionId)}&limit=${limit}`)
  const d = await readJson<ArchiveSessionDetail & { message?: string }>(r)
  throwIfNotOk(r, d)
  return d
}

export async function getInferenceProgress(jobId: string): Promise<RunInferenceResponse> {
  const r = await fetch(`${API_PREFIX}/api/inference-progress?job_id=${encodeURIComponent(jobId)}`)
  const d = await readJson<RunInferenceResponse & { message?: string }>(r)
  throwIfNotOk(r, d)
  return d
}

// ---------------------------------------------------------------------------
// POST — actions
// ---------------------------------------------------------------------------

export async function postProbeBoard(): Promise<ProbeBoardResponse> {
  return postJson<ProbeBoardResponse>('/api/probe-board')
}

export async function postRunInference(imageIndex = 0, variant = 'current'): Promise<RunInferenceResponse> {
  return postJson<RunInferenceResponse>('/api/run-inference', { image_index: imageIndex, mode: variant })
}

export async function postRunBaseline(imageIndex = 0, count = 300): Promise<RunInferenceResponse> {
  return postJson<RunInferenceResponse>('/api/run-baseline', { image_index: imageIndex, max_inputs: count })
}

export async function postInjectFault(faultType: string): Promise<FaultInjectResponse> {
  return postJson<FaultInjectResponse>('/api/inject-fault', { fault_type: faultType })
}

export async function postRecover(): Promise<RecoverResponse> {
  return postJson<RecoverResponse>('/api/recover')
}

export async function postLinkDirectorProfile(profileId: string): Promise<LinkDirectorSwitchResponse> {
  return postJson<LinkDirectorSwitchResponse>('/api/link-director/profile', { profile_id: profileId })
}

export async function postBoardAccess(payload: BoardAccessPayload): Promise<{ status: string; board_access: BoardAccessResponse }> {
  return postJson('/api/session/board-access', payload)
}

export async function postJobManifestGatePreview(variant = 'current'): Promise<GatePreviewResponse> {
  return postJson<GatePreviewResponse>('/api/job-manifest-gate/preview', { variant })
}

// ---------------------------------------------------------------------------
// Crypto channel status (ML-KEM / AEAD)
// ---------------------------------------------------------------------------

export async function getCryptoStatus(): Promise<CryptoStatusResponse> {
  const r = await fetch(`${API_PREFIX}/api/crypto-status`)
  const d = await readJson<CryptoStatusResponse & { message?: string }>(r)
  throwIfNotOk(r, d)
  return d
}

export async function postCryptoToggle(enabled: boolean): Promise<{ status: string; enabled: boolean }> {
  return postJson<{ status: string; enabled: boolean }>('/api/crypto-toggle', { enabled })
}

export async function postCryptoTest(): Promise<CryptoTestResult> {
  return postJson<CryptoTestResult>('/api/crypto-test', {})
}

export async function postCryptoReset(restartRemoteServer = true): Promise<{
  status: string
  message?: string
  session_closed?: boolean
  remote_restart_scheduled?: boolean
}> {
  return postJson('/api/crypto-reset', { restart_remote_server: restartRemoteServer })
}

export async function postRunInferenceBatch(count = 300): Promise<BatchInferenceResponse> {
  return postJson<BatchInferenceResponse>('/api/run-inference-batch', { count, allow_preflight_degraded: true })
}

export async function postRunMnnBatch(count = 300): Promise<BatchInferenceResponse> {
  return postJson<BatchInferenceResponse>('/api/run-mnn-batch', { count })
}

export async function getBatchState(): Promise<BatchStateResponse> {
  const r = await fetch(`${API_PREFIX}/api/batch-state`)
  const d = await readJson<BatchStateResponse & { message?: string }>(r)
  throwIfNotOk(r, d)
  return d
}
