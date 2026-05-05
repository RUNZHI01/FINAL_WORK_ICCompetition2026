/**
 * ML-KEM crypto channel status — returned by /api/crypto-status
 */

export type CryptoChannelState = 'idle' | 'handshaking' | 'ready' | 'closed' | 'disabled'

export type BenchmarkMetric = {
  n: number
  min_ms: number
  max_ms: number
  mean_ms: number
  median_ms: number
  p95_ms: number | null
}

export type BatchBenchmark = {
  handshake_ms?: BenchmarkMetric | null
  encrypt_ms?: BenchmarkMetric | null
  decrypt_ms?: BenchmarkMetric | null
  inference_ms?: BenchmarkMetric | null
  total_ms?: BenchmarkMetric | null
  radio_airtime_ms?: BenchmarkMetric | null
  decode_ms?: BenchmarkMetric | null
  merge_ms?: BenchmarkMetric | null
  other_wall_ms?: BenchmarkMetric | null
}

export type BatchStageProgress = {
  completed?: number
  total?: number
  status?: string
}

export type ServiceModeSnapshot = {
  /** Whether the live path currently exposes service-mode state */
  available: boolean
  /** Source of the snapshot, e.g. mock/live/unavailable */
  source: string
  /** Current service mode, if available */
  current_mode: string | null
  /** Guard-advertised allowed mode, if available */
  allowed_mode: string | null
  /** Payload strategy label, if available */
  payload_strategy: string | null
  /** Total number of mode transitions since engine start */
  mode_transitions: number
  /** Last mode transition details, or null if none */
  last_transition: {
    from_mode: string
    to_mode: string
    reason: string
    timestamp_ms: number
  } | null
  /** Human-readable operator note */
  note: string
}

export type CryptoStatusResponse = {
  /** KEM backend name, e.g. "tongsuo-ML-KEM-768" or "liboqs-ML-KEM-768" */
  kem_backend: string
  /** Cipher suite, e.g. "sm4-gcm" */
  cipher_suite: string
  /** Channel state */
  channel_state: CryptoChannelState
  /** Whether ML-DSA / SM2 authentication is enabled for the channel */
  auth_enabled?: boolean
  /** Active authentication signature policy */
  sig_policy?: string
  /** Claimed remote server identity used by authenticated handshake */
  server_id?: string
  /** Last handshake duration in ms */
  handshake_ms?: number
  /** Last encrypt+send duration in ms */
  encrypt_ms?: number
  /** Last decrypt duration in ms */
  decrypt_ms?: number
  /** Last TVM inference duration in ms */
  inference_ms?: number
  /** Total bytes sent (encrypted) */
  bytes_sent?: number
  /** Total bytes received (encrypted) */
  bytes_received?: number
  /** Last SHA256 integrity check result */
  last_sha256_match?: boolean
  /** Last session timestamp */
  last_session_at?: string
  /** Number of completed sessions */
  session_count?: number
  /** Error message if any */
  error?: string
  /** Whether ML-KEM is enabled via toggle */
  enabled: boolean
  /** Whether board credentials have been entered */
  board_configured: boolean
  /** Control-plane guard state snapshot from latest OpenAMP status */
  control_guard_state?: string
  /** Control-plane last fault snapshot */
  control_last_fault_code?: string
  /** Heartbeat acknowledgement counter from control status */
  control_heartbeat_ok?: number
  /** Total fault counter from control status */
  control_total_fault_count?: number
  /** Control-plane JOB_REQ observed in demo event spine */
  control_job_req_count?: number
  /** Control-plane JOB_ACK allow observed in demo event spine */
  control_job_admit_count?: number
  /** Control-plane JOB_ACK deny observed in demo event spine */
  control_job_reject_count?: number
  /** Control-plane heartbeat-related events observed in event spine */
  control_heartbeat_event_count?: number
  /** Control-plane heartbeat lost events observed in event spine */
  control_heartbeat_lost_count?: number
  /** Control-plane SAFE_STOP triggered events observed in event spine */
  control_safe_stop_triggered_count?: number
  /** Control-plane SAFE_STOP cleared events observed in event spine */
  control_safe_stop_cleared_count?: number
  /** Whether a soft recover was attempted before blocking */
  control_recover_attempted?: boolean
  /** Soft recover note for operator context */
  control_recover_note?: string
  /** Control-plane probe source label for the current summary */
  status_source?: string
  /** Human-readable control-plane status note */
  status_note?: string
  /** ISO timestamp for the last cached control-plane snapshot */
  control_status_observed_at?: string | null
  /** Age in seconds for the last cached control-plane snapshot */
  control_status_age_sec?: number | null
  /** Whether the cached control-plane snapshot is stale */
  control_status_stale?: boolean
  /** Batch inference benchmark results (populated after batch completes) */
  batch_benchmark?: BatchBenchmark | null
  /** USRP transport/decode benchmark, separated from inference reconstruction time */
  batch_transport_benchmark?: BatchBenchmark | null
  /** Pure board-side TVM/MNN reconstruction benchmark */
  batch_inference_benchmark?: BatchBenchmark | null
  /** Batch inference run status: 'running' | 'done' | null */
  batch_status?: string | null
  /** Number of completed images in current/last batch */
  batch_completed?: number
  /** Total images in current/last batch */
  batch_total?: number
  /** Task-level service-mode status, independent from the old control summary */
  service_mode?: ServiceModeSnapshot | null
}

export type CryptoTestResult = {
  status: 'ok' | 'error'
  message?: string
  handshake_ms?: number
  sha256_match?: boolean
  wall_ms?: number
}

export type BatchInferenceResponse = {
  status: string
  batch_job_id?: string
  total?: number
  message?: string
  engine?: string
}

export type BatchStateResponse = {
  status: string
  batch_job_id?: string
  engine?: string
  total?: number
  completed?: number
  success?: number
  fallback?: number
  sha_match?: number
  started_at?: number
  finished_at?: number | null
  benchmark?: BatchBenchmark | null
  transport_benchmark?: BatchBenchmark | null
  inference_benchmark?: BatchBenchmark | null
  host_preprocess_progress?: BatchStageProgress | null
  transport_progress?: BatchStageProgress | null
  inference_progress?: BatchStageProgress | null
  message?: string
  quality?: {
    psnr_db?: number
    ssim?: number
  }
  status_category?: string
  execution_mode?: string
  source_label?: string
  diagnostics?: Record<string, unknown>
  /** Service mode active during this batch (FULL_FRAME / ROI_ONLY / ALERT_ONLY) */
  service_mode?: string
}
