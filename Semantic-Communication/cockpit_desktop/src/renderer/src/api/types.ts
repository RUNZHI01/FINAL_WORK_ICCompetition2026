/**
 * Types aligned with `server.py` JSON responses.
 */

export type JsonObject = Record<string, unknown>

// ---------------------------------------------------------------------------
// Primitive / shared
// ---------------------------------------------------------------------------

export type ExecutionMode = {
  label: string
  tone: string
  summary: string
}

// ---------------------------------------------------------------------------
// GET /api/health
// ---------------------------------------------------------------------------

export type HealthResponse = {
  status: string
}

// ---------------------------------------------------------------------------
// Live payload (inside system-status)
// ---------------------------------------------------------------------------

export type LivePayload = {
  board_online: boolean
  guard_state: string
  last_fault_code: string
  active_job_id?: number
  total_fault_count?: number
  remoteproc_state?: unknown
  rpmsg_device?: unknown
  trusted_sha?: string
  target?: string
  runtime?: string
  last_probe_at?: string
  status_source?: string
  status_note?: string
  telemetry?: BoardTelemetryPayload
  board_position_api?: JsonObject
  admission?: JsonObject
  variant_support?: { current?: JsonObject; baseline?: JsonObject }
}

export type BoardTelemetryPayload = {
  status?: string
  stale?: boolean
  source?: string
  collected_at?: string
  compute_label?: string
  compute_pct?: number | null
  memory_pct?: number | null
  memory_used_mb?: number | null
  memory_available_mb?: number | null
  memory_total_mb?: number | null
  loadavg_1m?: number | null
  cpu_cores?: number | null
  note?: string
}

// ---------------------------------------------------------------------------
// Job manifest gate
// ---------------------------------------------------------------------------

export type JobManifestGate = {
  status?: string
  label?: string
  tone?: string
  verdict?: string
  verdict_label?: string
  variant?: string
  variant_label?: string
  admission_mode?: string
  admission_label?: string
  admission_note?: string
  summary?: string
  protocol_boundary_note?: string
  demo_only_note?: string
  message?: string
  reasons?: string[]
  status_source?: string
  field_map?: Record<string, unknown>
  wire_fields?: unknown[]
  context_fields?: unknown[]
  evidence?: Record<string, unknown>
}

// ---------------------------------------------------------------------------
// Active inference
// ---------------------------------------------------------------------------

export type ActiveInference = {
  running?: boolean
  job_id?: string
  variant?: string
  source?: string
  queue_depth?: number
  request_state?: string
  status_category?: string
  message?: string
  progress?: Record<string, unknown>
}

// ---------------------------------------------------------------------------
// Link director
// ---------------------------------------------------------------------------

export type LinkDirectorProfile = {
  profile_id: string
  label: string
  tone?: string
  description?: string
  params?: JsonObject
  active?: boolean
}

export type LinkDirectorStatus = {
  status?: string
  label?: string
  tone?: string
  backend_binding?: string
  backend_status?: string
  summary?: string
  plane_split_note?: string
  mode_boundary_note?: string
  truth_note?: string
  selected_profile_id?: string
  selected_profile_label?: string
  selected_profile?: LinkDirectorProfile
  profiles?: LinkDirectorProfile[]
  last_applied_at?: string
  last_operator_action?: string
}

export type LinkDirectorSwitchResponse = LinkDirectorStatus & {
  change_applied?: boolean
  status_message?: string
  previous_profile_id?: string
  previous_profile_label?: string
}

// ---------------------------------------------------------------------------
// Safety panel
// ---------------------------------------------------------------------------

export type SafetyPanelPayload = {
  panel_label?: string
  panel_tone?: string
  safe_stop_state?: string
  safe_stop_tone?: string
  safe_stop_note?: string
  latch_state?: string
  latch_tone?: string
  latch_note?: string
  guard_state?: string
  last_fault_code?: string
  total_fault_count?: number
  board_online?: boolean
  status_source?: string
  status_note?: string
  last_fault_result?: JsonObject
  recover_action?: {
    action_id?: string
    label?: string
    api_path?: string
    method?: string
    note?: string
  }
  ownership_note?: string
}

// ---------------------------------------------------------------------------
// Operator cue
// ---------------------------------------------------------------------------

export type OperatorCueCheck = {
  label?: string
  ready?: boolean
  tone?: string
  note?: string
}

export type OperatorCueScene = {
  scene_id: string
  number?: string
  eyebrow?: string
  title: string
  status?: string
  tone?: string
  note?: string
  cue_line?: string
  jump?: JsonObject
  jump_hint?: string
  checks?: OperatorCueCheck[]
  ready_count?: number
  total_checks?: number
  meta?: string[]
  recommended?: boolean
}

export type OperatorCuePayload = {
  mode?: string
  status_label?: string
  status_tone?: string
  current_scene_id?: string
  current_scene_label?: string
  current_scene_tone?: string
  presenter_line?: string
  next_step_label?: string
  next_step_note?: string
  next_action?: JsonObject
  manual_boundary_note?: string
  boundary_note?: string
  quick_jumps?: JsonObject[]
  scenes?: OperatorCueScene[]
}

// ---------------------------------------------------------------------------
// Event spine
// ---------------------------------------------------------------------------

export type EventSpineEvent = {
  event_type?: string
  timestamp?: string
  job_id?: string
  source?: string
  plane?: string
  mode_scope?: string
  message?: string
  data?: JsonObject
}

export type EventSpineResponse = {
  session_id?: string
  aggregate?: {
    event_count?: number
    last_event_at?: string
    archive?: { enabled?: boolean }
  }
  events?: EventSpineEvent[]
  recent_events?: EventSpineEvent[]
}

// ---------------------------------------------------------------------------
// Archive
// ---------------------------------------------------------------------------

export type ArchiveSessionSummary = {
  session_id?: string
  event_count?: number
  last_event_at?: string
  is_current_session?: boolean
}

export type ArchiveSessionsResponse = {
  sessions?: ArchiveSessionSummary[]
  current_session_id?: string
}

export type ArchiveSessionDetail = {
  summary?: JsonObject
  timeline?: JsonObject[]
  paths?: JsonObject
  read_errors?: string[]
}

// ---------------------------------------------------------------------------
// Inference result (run-inference / run-baseline / inference-progress)
// ---------------------------------------------------------------------------

export type InferenceTimings = {
  payload_ms?: number | null
  prepare_ms?: number | null
  total_ms?: number | null
  stages?: Array<{ label?: string; value_ms?: number; emphasis?: string }>
}

export type InferenceQuality = {
  psnr_db?: number
  ssim?: number
  max_pixel_error?: number
  is_lossless?: boolean
}

export type InferenceSample = {
  label?: string
  index?: number
  path?: string
}

export type InferenceProgressInfo = {
  state?: string
  label?: string
  tone?: string
  percent?: number
  phase_percent?: number
  completed_count?: number
  expected_count?: number
  remaining_count?: number
  completion_ratio?: number
  count_source?: string
  count_label?: string
  current_stage?: string
  stages?: Array<{ key?: string; label?: string; status?: string; detail?: string }>
  event_log?: string[]
}

// ---------------------------------------------------------------------------
// JSCC link mode (QPSK baseline vs IQ-direct analog latent)
// ---------------------------------------------------------------------------

export type JsccLinkMode = 'qpsk' | 'iq-direct'

export type IqRadioMetricAggregate = {
  mean?: number
  max?: number
}

export type IqRadioMetrics = {
  sample_count?: number
  sync_success_count?: number
  sync_success_ratio?: number
  sync_metric?: IqRadioMetricAggregate
  evm_rms?: IqRadioMetricAggregate
  estimated_cfo_hz?: IqRadioMetricAggregate
  estimated_snr_db?: IqRadioMetricAggregate
  rx_clipping_ratio?: IqRadioMetricAggregate
  latent_mse_vs_tx?: IqRadioMetricAggregate
}

function normalizeJsccLinkMode(value: unknown): JsccLinkMode | undefined {
  if (value == null) return undefined
  const raw = String(value).trim().toLowerCase()
  if (raw === 'iq-direct' || raw === 'iq' || raw === 'analog') return 'iq-direct'
  if (raw === 'qpsk') return 'qpsk'
  return undefined
}

function asNumber(value: unknown): number | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : undefined
  }
  return undefined
}

function asMetricAggregate(value: unknown): IqRadioMetricAggregate | undefined {
  if (!value || typeof value !== 'object') return undefined
  const record = value as Record<string, unknown>
  const mean = asNumber(record.mean)
  const max = asNumber(record.max)
  if (mean == null && max == null) return undefined
  const result: IqRadioMetricAggregate = {}
  if (mean != null) result.mean = mean
  if (max != null) result.max = max
  return result
}

export function extractJsccLinkMode(summary: JsonObject | undefined): JsccLinkMode | undefined {
  if (!summary) return undefined
  return normalizeJsccLinkMode(summary.link_mode)
}

export function extractIqRadioMetrics(summary: JsonObject | undefined): IqRadioMetrics | undefined {
  if (!summary) return undefined
  const raw = summary.iq_radio_metrics
  if (!raw || typeof raw !== 'object') return undefined
  const record = raw as Record<string, unknown>
  const sampleCount = asNumber(record.sample_count)
  const syncSuccessCount = asNumber(record.sync_success_count)
  const syncSuccessRatio = asNumber(record.sync_success_ratio)
  const metrics: IqRadioMetrics = {}
  if (sampleCount != null) metrics.sample_count = sampleCount
  if (syncSuccessCount != null) metrics.sync_success_count = syncSuccessCount
  if (syncSuccessRatio != null) metrics.sync_success_ratio = syncSuccessRatio
  const syncMetric = asMetricAggregate(record.sync_metric)
  const evmRms = asMetricAggregate(record.evm_rms)
  const cfoHz = asMetricAggregate(record.estimated_cfo_hz)
  const snrDb = asMetricAggregate(record.estimated_snr_db)
  const rxClipping = asMetricAggregate(record.rx_clipping_ratio)
  const latentMse = asMetricAggregate(record.latent_mse_vs_tx)
  if (syncMetric) metrics.sync_metric = syncMetric
  if (evmRms) metrics.evm_rms = evmRms
  if (cfoHz) metrics.estimated_cfo_hz = cfoHz
  if (snrDb) metrics.estimated_snr_db = snrDb
  if (rxClipping) metrics.rx_clipping_ratio = rxClipping
  if (latentMse) metrics.latent_mse_vs_tx = latentMse
  return metrics
}

export type RunInferenceResponse = {
  status?: string
  execution_mode?: string
  request_state?: string
  status_category?: string
  variant?: string
  job_id?: string
  image_index?: number
  source_label?: string
  message?: string
  artifact_sha?: string
  timings?: InferenceTimings
  quality?: InferenceQuality
  inference_engine?: string
  control_transport?: string
  data_transport?: string
  sample?: InferenceSample
  live_progress?: InferenceProgressInfo
  live_attempt?: JsonObject
  runner_summary?: JsonObject
  wrapper_summary?: JsonObject
}

// ---------------------------------------------------------------------------
// Fault / recover
// ---------------------------------------------------------------------------

export type FaultInjectResponse = {
  status?: string
  status_category?: string
  execution_mode?: string
  fault_type?: string
  source_label?: string
  message?: string
  board_response?: JsonObject
  guard_state?: string
  last_fault_code?: string
  status_lamp?: string
  log_entries?: string[]
  details?: JsonObject
  live_attempt?: JsonObject
}

export type RecoverResponse = {
  status?: string
  status_category?: string
  execution_mode?: string
  source_label?: string
  message?: string
  board_response?: JsonObject
  guard_state?: string
  last_fault_code?: string
  status_lamp?: string
  log_entries?: string[]
  details?: JsonObject
}

// ---------------------------------------------------------------------------
// Probe
// ---------------------------------------------------------------------------

export type ProbeBoardResponse = JsonObject & {
  status?: string
  reachable?: boolean
  requested_at?: string
  details?: JsonObject
  control_status?: JsonObject
}

// ---------------------------------------------------------------------------
// Board access
// ---------------------------------------------------------------------------

export type BoardAccessPayload = {
  host?: string
  user?: string
  password?: string
  port?: number | string
  env_file?: string
  transport_mode?: string
  jscc_link_mode?: JsccLinkMode
  local_latent_dir?: string
  local_latent_pattern?: string
  auth_enabled?: boolean
  auth_sig_policy?: string
  auth_server_id?: string
}

export type BoardAccessResponse = JsonObject & {
  connection_ready?: boolean
  configured?: boolean
  probe_ready?: boolean
  missing_connection_fields?: string[]
  transport_mode?: string
  transport_label?: string
  transport_tone?: string
  transport_summary?: string
  input_source_mode?: string
  input_source_label?: string
  input_source_tone?: string
  input_source_summary?: string
  remote_usrp_rx_dir?: string
  jscc_link_mode?: JsccLinkMode | string
  local_usrp_input_dir?: string
  local_usrp_image_dir?: string
  remote_prerecorded_input_dir?: string
  remote_reconstruction_output_base?: string
}

// ---------------------------------------------------------------------------
// Gate preview
// ---------------------------------------------------------------------------

export type GatePreviewResponse = {
  status?: string
  action?: string
  preview_only?: boolean
  job_id?: string
  event_type?: string
  message?: string
  checked_at?: string
  gate?: JobManifestGate
}

// ---------------------------------------------------------------------------
// GET /api/system-status
// ---------------------------------------------------------------------------

export type SystemStatusResponse = {
  generated_at: string
  board_access: BoardAccessResponse
  execution_mode: ExecutionMode
  aircraft_position: JsonObject
  live: LivePayload
  active_inference: ActiveInference
  last_inference?: RunInferenceResponse | JsonObject
  recent_results?: Record<string, RunInferenceResponse>
  last_fault?: FaultInjectResponse | JsonObject
  safety_panel?: SafetyPanelPayload
  job_manifest_gate: JobManifestGate
  link_director: LinkDirectorStatus
  operator_cue?: OperatorCuePayload
  event_spine: EventSpineSummary
}

// ---------------------------------------------------------------------------
// GET /api/snapshot
// ---------------------------------------------------------------------------

export type DemoSnapshot = {
  generated_at: string
  project: {
    name: string
    focus?: string
    package_id?: string
    final_verdict?: string
    trusted_current_sha?: string
    final_live_firmware_sha?: string
  }
  mode: JsonObject
  board: JsonObject
  stats: {
    p0_milestones_verified?: number
    fit_final_pass_count?: number
    payload_current_ms?: number
    end_to_end_current_ms?: number
  }
  aircraft_position: JsonObject
  milestones?: unknown[]
  performance?: JsonObject
  weak_network?: JsonObject
}

// ---------------------------------------------------------------------------
// GET /api/aircraft-position
// ---------------------------------------------------------------------------

export type AircraftPositionResponse = JsonObject & {
  source_kind?: string
  source_status?: string
  source_label?: string
  mission_call_sign?: string
  position?: { latitude?: number; longitude?: number }
  kinematics?: { heading_deg?: number; altitude_m?: number; ground_speed_kph?: number; vertical_speed_mps?: number }
  fix?: { type?: string; confidence_m?: number; satellites?: number }
  track?: Array<{ latitude?: number; longitude?: number; age_sec?: number }>
  sample?: { sequence?: number; captured_at?: string; producer_id?: string; transport?: string }
}

// ---------------------------------------------------------------------------
// Shared sub-types kept for backward compat
// ---------------------------------------------------------------------------

export type EventSpineSummary = {
  api_path?: string
  session_id?: string
  event_count?: number
  last_event_at?: string
  archive_enabled?: boolean
}
