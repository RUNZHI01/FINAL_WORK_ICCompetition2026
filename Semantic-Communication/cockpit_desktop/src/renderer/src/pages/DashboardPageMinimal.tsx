import { memo, useMemo, useState, useEffect, useCallback, useRef } from 'react'
import { useSystemStatus } from '../hooks/useSystemStatus'
import { useAircraftPosition } from '../hooks/useAircraftPosition'
import { useInferenceProgressPoll } from '../hooks/useInferenceProgress'
import { useBatchStatePoll } from '../hooks/useBatchState'
import { useAppStore } from '../stores/appStore'
import type { ComparisonResult } from '../stores/appStore'
import { useCryptoStatus } from '../hooks/useCryptoStatus'
import {
  useProbeBoard,
  useRunInferenceBatch,
  useRunMnnBatch,
  useRunBaseline,
  useSetBoardAccess,
} from '../hooks/useActions'
import { HeroMetrics } from '../components/dashboard/HeroMetrics'
import { MinimalStatusPanel } from '../components/dashboard/MinimalStatusPanel'
import { CryptoStatusPanel } from '../components/dashboard/CryptoStatusPanel'
import { FlightPanel } from '../components/dashboard/FlightPanel'
import { PageTransition, StaggeredList, AnimatedListItem } from '../components/animations'
import { Icons } from '../components/icons'
import { CountUp } from '../components/shared/CountUp'
import type { BatchStageProgress } from '../api/types/crypto'
import { comparisonResultFromInferencePayload } from '../hooks/comparisonResult'
import s from './DashboardPageMinimal.module.css'

const LIVE_LOG_ACTIONS = ['Processing block', 'Allocating memory', 'Optimizing tensor', 'Compiling kernel', 'Syncing device']

type AuthSigPolicy = 'DUAL_REQUIRED' | 'SM2_ONLY' | 'MLDSA_ONLY'
type TransportMode = 'tcp' | 'usrp'

const AUTH_POLICY_OPTIONS: { value: AuthSigPolicy; label: string }[] = [
  { value: 'DUAL_REQUIRED', label: '双因子: SM2 + ML-DSA' },
  { value: 'SM2_ONLY', label: '仅 SM2' },
  { value: 'MLDSA_ONLY', label: '仅 ML-DSA' },
]

const AUTH_POLICY_HINTS: Record<AuthSigPolicy, string> = {
  DUAL_REQUIRED: '同时校验 SM2 与 ML-DSA 标识，最接近当前完整认证链路。',
  SM2_ONLY: '仅保留国密签名身份校验，便于单独验证 SM2 链路。',
  MLDSA_ONLY: '仅保留后量子签名身份校验，便于单独验证 ML-DSA 链路。',
}

const TRANSPORT_OPTIONS: { mode: TransportMode; label: string; caption: string }[] = [
  {
    mode: 'tcp',
    label: '预录模式',
    caption: '板端继续读取本地预录张量，保留原 demo 路径。',
  },
  {
    mode: 'usrp',
    label: 'USRP 模式',
    caption: '上位机 latent 转 bin 后走 USRP OTA，板端从 RX 目录进入重建。',
  },
]

const MAX_BATCH_COUNT = 300

function numericValue(value: unknown): number | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : undefined
  }
  return undefined
}

function normalizeStageProgress(stage: BatchStageProgress | null | undefined, fallbackTotal: number) {
  const total = Math.max(1, numericValue(stage?.total) ?? fallbackTotal)
  const completed = Math.max(0, Math.min(numericValue(stage?.completed) ?? 0, total))
  return {
    completed,
    total,
    status: stage?.status ?? 'pending',
    percent: Math.max(0, Math.min((completed / total) * 100, 100)),
  }
}

function normalizeAuthSigPolicy(rawValue: string | undefined): AuthSigPolicy {
  const normalized = String(rawValue || '').trim().toUpperCase()
  if (normalized === 'SM2_ONLY' || normalized === 'MLDSA_ONLY') {
    return normalized
  }
  return 'DUAL_REQUIRED'
}

function normalizeTransportMode(rawValue: unknown): TransportMode {
  return String(rawValue || '').trim().toLowerCase() === 'usrp' ? 'usrp' : 'tcp'
}

function normalizeBatchCountInput(rawValue: string, fallback: number): number {
  const parsed = Number(rawValue)
  if (!Number.isFinite(parsed)) {
    return fallback
  }
  return Math.max(1, Math.min(Math.trunc(parsed), MAX_BATCH_COUNT))
}

const LiveLogStream = memo(function LiveLogStream({ isRunning }: { isRunning: boolean }) {
  const [logs, setLogs] = useState<string[]>([])

  useEffect(() => {
    if (!isRunning) {
      setLogs([])
      return
    }

    const id = setInterval(() => {
      const now = new Date().toLocaleTimeString('en-US', { hour12: false })
      const action = LIVE_LOG_ACTIONS[Math.floor(Math.random() * LIVE_LOG_ACTIONS.length)]
      const blockId = Math.floor(Math.random() * 1000)
      setLogs((prev) => [...prev, `[${now}] ${action} ${blockId}... OK`].slice(-3))
    }, 800)

    return () => clearInterval(id)
  }, [isRunning])

  if (!isRunning || logs.length === 0) {
    return null
  }

  return (
    <div className={s.liveLogStream}>
      {logs.map((log, i) => (
        <div key={`${log}-${i}`} className={s.logEntry} style={{ opacity: 0.4 + (i * 0.3) }}>
          {log}
        </div>
      ))}
    </div>
  )
})

type GpsForwardStreamProps = {
  isActive: boolean
  sourceLabel?: string
  fixType?: string
  satellites?: number
  latitude?: number
  longitude?: number
  altitudeMeters?: number
}

const GpsForwardStream = memo(function GpsForwardStream({
  isActive,
  sourceLabel,
  fixType,
  satellites,
  latitude,
  longitude,
  altitudeMeters,
}: GpsForwardStreamProps) {
  const [gpsLogs, setGpsLogs] = useState<string[]>([])

  useEffect(() => {
    if (!isActive) {
      setGpsLogs([])
      return
    }

    const id = setInterval(() => {
      const now = new Date().toLocaleTimeString('en-US', { hour12: false })
      const lat = latitude ?? (30.5 + Math.random() * 0.01)
      const lon = longitude ?? (114.3 + Math.random() * 0.01)
      const alt = altitudeMeters ?? (500 + Math.random() * 10)
      const seq = Math.floor(Math.random() * 65535)
      setGpsLogs((prev) => {
        const nextLog = `[${now}] COORD_FWD seq=${seq} lat=${lat.toFixed(6)} lon=${lon.toFixed(6)} alt=${alt.toFixed(1)}m → RTOS OK`
        return [...prev, nextLog].slice(-5)
      })
    }, 600)

    return () => clearInterval(id)
  }, [isActive, latitude, longitude, altitudeMeters])

  if (!isActive) {
    return null
  }

  return (
    <div className={`${s.sectionCard} ${s.alertModeCard}`} style={{ marginTop: '12px' }}>
      <div className={s.alertModeHeader}>
        <Icons.Navigation size={20} style={{ color: 'var(--color-error)' }} />
        <div>
          <div className={s.alertModeTitle}>北斗定位持续下发中</div>
          <div className={s.alertModeSubtitle}>链路劣化，图像张量传输已挂起，仅向 RTOS 下发定位坐标</div>
        </div>
        <div className={s.progressBadge} style={{ marginLeft: 'auto' }}>
          <span className={s.pulseDot} style={{ background: 'var(--color-error)' }} />
          持续传输
        </div>
      </div>
      <div className={s.liveLogStream} style={{ marginTop: '8px' }}>
        {gpsLogs.length > 0 ? gpsLogs.map((log, i) => (
          <div key={`gps-${i}`} className={s.logEntry} style={{ opacity: 0.3 + (i * 0.15), color: 'var(--color-error)' }}>
            {log}
          </div>
        )) : (
          <div className={s.logEntry} style={{ color: 'var(--color-text-muted)' }}>等待坐标下发日志...</div>
        )}
      </div>
      <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', marginTop: '6px' }}>
        定位源: {sourceLabel ?? '—'} · 定位类型: {fixType ?? '—'} · 卫星: {satellites ?? '—'}
      </div>
    </div>
  )
})

export function DashboardPageMinimal() {
  const system = useSystemStatus()
  const aircraft = useAircraftPosition()
  const inferenceProgress = useInferenceProgressPoll()
  const batchState = useBatchStatePoll()

  const activeJobId = useAppStore((s) => s.activeJobId)
  const pendingBatchJobId = useAppStore((s) => s.pendingBatchJobId)
  const lastCompletedInference = useAppStore((s) => s.lastCompletedInference)
  const setLastCompletedInference = useAppStore((s) => s.setLastCompletedInference)
  const setLastSettledBatchToken = useAppStore((s) => s.setLastSettledBatchToken)
  const setPendingBatchJobId = useAppStore((s) => s.setPendingBatchJobId)
  const comparisonResults = useAppStore((s) => s.comparisonResults)
  const clearComparisonResults = useAppStore((s) => s.clearComparisonResults)
  const chinaTheater = useAppStore((s) => s.chinaTheater)
  const setChinaTheater = useAppStore((s) => s.setChinaTheater)
  const [boardPassword, setBoardPassword] = useState('')
  const [authEnabled, setAuthEnabled] = useState(false)
  const [authSigPolicy, setAuthSigPolicy] = useState<AuthSigPolicy>('DUAL_REQUIRED')
  const [authDirty, setAuthDirty] = useState(false)
  const [batchCount, setBatchCount] = useState<number>(300)
  const [batchCountTouched, setBatchCountTouched] = useState(false)
  const [toasts, setToasts] = useState<{ id: number; text: string; type: 'success' | 'error' }[]>([])
  const toastIdRef = useRef(0)
  const batch = batchState.isError ? undefined : batchState.data

  const { data: cryptoData } = useCryptoStatus()
  const currentMode = cryptoData?.service_mode?.current_mode

  const probeMut = useProbeBoard()
  const batchMut = useRunInferenceBatch()
  const mnnBatchMut = useRunMnnBatch()
  const baselineMut = useRunBaseline()
  const boardAccessMut = useSetBoardAccess()
  const status = system.data
  const boardAccess = status?.board_access
  const activeTransport = normalizeTransportMode(boardAccess?.transport_mode)

  const removeToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const showToast = useCallback((text: string, type: 'success' | 'error') => {
    toastIdRef.current += 1
    const id = toastIdRef.current
    setToasts((prev) => [...prev, { id, text, type }])
    setTimeout(() => removeToast(id), 3000)
  }, [removeToast])

  useEffect(() => {
    clearComparisonResults()
    setLastCompletedInference(null)
    setLastSettledBatchToken(null)
    setPendingBatchJobId(null)
  }, [clearComparisonResults, setLastCompletedInference, setLastSettledBatchToken, setPendingBatchJobId])

  useEffect(() => {
    if (authDirty) return
    setAuthEnabled(Boolean(cryptoData?.auth_enabled))
    setAuthSigPolicy(normalizeAuthSigPolicy(cryptoData?.sig_policy))
  }, [cryptoData?.auth_enabled, cryptoData?.sig_policy, authDirty])

  useEffect(() => {
    if (batchCountTouched) return
    setBatchCount(activeTransport === 'usrp' ? 20 : 300)
  }, [activeTransport, batchCountTouched])

  const handleRunInference = useCallback(
    (count: number = batchCount) => {
      batchMut.mutate({ count }, {
        onSuccess: (data) => {
          if (data.status === 'already_running') {
            showToast(`TVM ${count} 张任务已在运行中`, 'success')
          } else if (data.status === 'started') {
            showToast(`TVM ${count} 张任务已启动`, 'success')
          } else {
            showToast(data.message || `TVM ${count} 张任务启动失败`, 'error')
          }
        },
        onError: (error) => {
          showToast(`启动失败: ${error.message}`, 'error')
        },
      })
    },
    [batchCount, batchMut, showToast],
  )

  const handleRunMnnInference = useCallback(
    (count: number = batchCount) => {
      mnnBatchMut.mutate({ count }, {
        onSuccess: (data) => {
          if (data.status === 'already_running') {
            showToast(`MNN ${count} 张任务已在运行中`, 'success')
          } else if (data.status === 'started') {
            showToast(`MNN ${count} 张任务已启动`, 'success')
          } else {
            showToast(data.message || `MNN ${count} 张任务启动失败`, 'error')
          }
        },
        onError: (error) => {
          showToast(`启动失败: ${error.message}`, 'error')
        },
      })
    },
    [batchCount, mnnBatchMut, showToast],
  )

  const handleSavePassword = useMemo(
    () => () => {
      if (!boardPassword.trim()) {
        showToast('请输入板卡密码', 'error')
        return
      }
      boardAccessMut.mutate({ password: boardPassword }, {
        onSuccess: () => {
          showToast('密码已保存，现在可以启动推理了', 'success')
          setBoardPassword('')
        },
        onError: (error) => {
          showToast(`保存密码失败: ${error.message}`, 'error')
        }
      })
    },
    [boardPassword, boardAccessMut, showToast],
  )

  const handleSaveAuth = useMemo(
    () => () => {
      boardAccessMut.mutate(
        {
          auth_enabled: authEnabled,
          auth_sig_policy: authSigPolicy,
        },
        {
          onSuccess: () => {
            setAuthDirty(false)
            showToast(authEnabled ? `认证策略已保存: ${authSigPolicy}` : '认证面已关闭', 'success')
          },
          onError: (error) => {
            showToast(`保存认证设置失败: ${error.message}`, 'error')
          },
        },
      )
    },
    [authEnabled, authSigPolicy, boardAccessMut, showToast],
  )

  const handleSelectTransport = useCallback(
    (mode: TransportMode) => {
      const selected = TRANSPORT_OPTIONS.find((option) => option.mode === mode)
      boardAccessMut.mutate(
        { transport_mode: mode },
        {
          onSuccess: (data) => {
            const label = data.board_access?.transport_label ?? selected?.label ?? mode
            showToast(`数据面模式已切换: ${label}`, 'success')
          },
          onError: (error) => {
            showToast(`切换数据面模式失败: ${error.message}`, 'error')
          },
        },
      )
    },
    [boardAccessMut, showToast],
  )

  // Derived data
  const recentResults = status?.recent_results
  const currentResultFromStore = lastCompletedInference?.variant === 'current' ? lastCompletedInference : undefined
  const currentResult = currentResultFromStore ?? recentResults?.current
  const baselineResultFromStore = lastCompletedInference?.variant === 'baseline' ? lastCompletedInference : undefined
  const baselineResult = baselineResultFromStore ?? recentResults?.baseline
  const currentComparisonFromPayload = comparisonResultFromInferencePayload(currentResult)
  const baselineComparisonFromPayload = comparisonResultFromInferencePayload(baselineResult)
  const pytorchComparison =
    baselineComparisonFromPayload
    ?? comparisonResults.pytorch
  const tvmComparison =
    currentComparisonFromPayload
    ?? comparisonResults.tvm
  const mnnComparison =
    comparisonResults.mnn
  const comparisonRows = [pytorchComparison, tvmComparison, mnnComparison]
    .filter((item): item is ComparisonResult => Boolean(item))
  const maxComparisonMs = Math.max(...comparisonRows.map((item) => item.reconstructionMs), 1)
  const pytorchReferenceMs = pytorchComparison?.reconstructionMs
  const resultQuality = tvmComparison?.quality ?? mnnComparison?.quality
  const hasPositiveSpeedup = comparisonRows.some((row) => (
    row.engine !== 'pytorch'
    && pytorchReferenceMs != null
    && pytorchReferenceMs > 0
    && pytorchReferenceMs > row.reconstructionMs
  ))

  const liveJob = inferenceProgress.data
  const liveProgress = liveJob?.live_progress
  const isSingleLiveRunning = Boolean(activeJobId) && liveJob?.request_state !== 'completed'
  const liveEngineLabel = liveJob?.variant === 'baseline'
    ? 'PyTorch'
    : liveJob?.variant === 'current'
      ? 'TVM'
      : 'Live'
  const liveExpectedCount = Math.max(1, liveProgress?.expected_count ?? 1)
  const liveCompletedCount = Math.max(0, Math.min(liveProgress?.completed_count ?? 0, liveExpectedCount))
  const liveCountPercent = liveProgress?.completion_ratio != null
    ? liveProgress.completion_ratio * 100
    : (liveProgress?.percent ?? (liveCompletedCount / liveExpectedCount) * 100)
  const liveStagePercent = liveProgress?.phase_percent
  const livePercentSource = liveExpectedCount <= 1 && liveStagePercent != null
    ? Math.max(liveCountPercent, liveStagePercent)
    : liveCountPercent
  const livePercent = Math.max(
    0,
    Math.min(livePercentSource, 100),
  )
  const isCurrentSessionBatch = Boolean(batch?.batch_job_id && pendingBatchJobId && batch.batch_job_id === pendingBatchJobId)
  const activeBatch = batch && (isCurrentSessionBatch || batch.status === 'running' || batch.status === 'done')
    ? batch
    : undefined
  const batchServiceMode = activeBatch?.service_mode as string | undefined
  const batchEngine = (activeBatch?.engine === 'mnn' ? 'mnn' : 'tvm') as 'mnn' | 'tvm'
  const batchEngineLabel = batchEngine === 'mnn' ? 'MNN' : 'TVM'
  const batchTotalImages = Math.max(1, activeBatch?.total ?? 300)
  const batchProgress = Math.max(0, Math.min(activeBatch?.completed ?? 0, batchTotalImages))
  const batchSuccess = Math.max(0, activeBatch?.success ?? 0)
  const batchFallback = Math.max(0, activeBatch?.fallback ?? 0)
  const isBatchRunning = activeBatch?.status === 'running'
  const isBatchDone = activeBatch?.status === 'done'
  const hasStageProgress = !isSingleLiveRunning && Boolean(activeBatch?.host_preprocess_progress || activeBatch?.transport_progress || activeBatch?.inference_progress)
  const hostPreprocessStage = normalizeStageProgress(activeBatch?.host_preprocess_progress, batchTotalImages)
  const transportStage = normalizeStageProgress(activeBatch?.transport_progress, batchTotalImages)
  const inferenceStage = normalizeStageProgress(activeBatch?.inference_progress, batchTotalImages)
  const batchIssueMessage = isBatchDone && batchFallback > 0
    ? String(activeBatch?.message || '批量任务已回退，未产生有效 live 重建结果。')
    : ''
  const batchIssueDetail = isBatchDone && batchFallback > 0
    ? [
        activeBatch?.status_category ? `状态: ${activeBatch.status_category}` : '',
        activeBatch?.source_label ? `来源: ${activeBatch.source_label}` : '',
      ].filter(Boolean).join(' · ')
    : ''
  const isRunning = isSingleLiveRunning || isBatchRunning
  const isDone = !isSingleLiveRunning && isBatchDone
  const modeTag = batchServiceMode === 'ROI_ONLY' ? ' (降采样 3:1)' : ''
  const totalImages = isSingleLiveRunning ? liveExpectedCount : batchTotalImages
  const progress = isSingleLiveRunning ? liveCompletedCount : batchProgress
  const progressPercent = isSingleLiveRunning ? livePercent : (progress / totalImages) * 100
  const progressEngineLabel = isSingleLiveRunning ? liveEngineLabel : batchEngineLabel
  const currentStage = isSingleLiveRunning
    ? (liveProgress?.current_stage || liveProgress?.label || `${liveEngineLabel} Live 执行中`)
    : isBatchRunning
      ? batchEngine === 'mnn'
        ? (batchProgress > 0 ? `MNN 动态尺寸批量 ${batchProgress}/${batchTotalImages}` : 'MNN 动态尺寸批量执行中')
        : `TVM 在线推进 ${batchProgress}/${batchTotalImages}${modeTag}`
    : isDone
      ? batchFallback > 0
        ? `批量结束：成功 ${batchSuccess}，回退 ${batchFallback}`
        : batchEngine === 'mnn'
          ? `MNN 批量完成：${batchProgress}/${batchTotalImages}`
          : `批量完成：${batchProgress}/${batchTotalImages}${modeTag}`
      : `等待操作员启动 TVM ${batchCount} 张`
  const progressBadge = isRunning
    ? '运行中'
    : isDone
      ? batchFallback > 0
        ? (batchSuccess > 0 ? '部分回退' : '已回退')
        : '已完成'
      : '等待触发'
  const progressSubtitle = isSingleLiveRunning
    ? `${liveExpectedCount} 张 ${liveEngineLabel} Live 在线推进`
    : batchEngine === 'mnn'
      ? `${batchTotalImages} 张 MNN 动态尺寸推理`
      : batchServiceMode === 'ROI_ONLY'
        ? `${batchTotalImages} 张降采样推理 (原 300 张跳帧 3:1)`
        : `${batchTotalImages} 张 TVM 图像在线推进`
  const progressSuffix = isRunning ? '处理中' : isDone ? '已完成' : '待启动'
  const stageProgressSuffix = isRunning ? '处理中' : isDone ? '已完成' : '待启动'
  const boardOnline = status?.live?.board_online ?? false
  const hostInputDir = boardAccess?.local_usrp_image_dir
    || boardAccess?.local_usrp_input_dir
    || (activeTransport === 'usrp' ? '' : boardAccess?.remote_prerecorded_input_dir)
  const boardInputDir = activeTransport === 'usrp'
    ? boardAccess?.remote_usrp_rx_dir
    : boardAccess?.remote_prerecorded_input_dir
  const boardOutputDir = boardAccess?.remote_reconstruction_output_base
  const pendingTransportMode = boardAccessMut.variables?.transport_mode
    ? normalizeTransportMode(boardAccessMut.variables.transport_mode)
    : undefined
  const roiEffectiveCount = Math.max(1, Math.ceil(batchCount / 3))
  const batchTargetLabel = activeTransport === 'usrp' && batchCount === 20
    ? '20 张快演'
    : `${batchCount} 张`
  const batchPresetHint = activeTransport === 'usrp'
    ? 'USRP 模式推荐先跑 20 张快演，视频录制更紧凑；需要完整留证时再切回 300 张。'
    : '默认可跑 300 张全量；如需快速演示，也可以先切到 20 张。'
  const authHint = authEnabled
    ? AUTH_POLICY_HINTS[authSigPolicy]
    : '当前只保留 ML-KEM + SM4，会跳过 ML-DSA / SM2 身份认证。'
  const authStatusLabel = cryptoData?.auth_enabled
    ? `已保存: ${normalizeAuthSigPolicy(cryptoData?.sig_policy)}`
    : '已保存: 未启用'

  return (
    <PageTransition className={s.root}>
      {/* Ambient Mesh Gradient Background */}
      <div className={s.meshBackground}>
        <div className={s.meshBlob1} />
        <div className={s.meshBlob2} />
        <div className={s.meshBlob3} />
      </div>

      {/* Toast Notification Container */}
      <div className={s.toastContainer}>
        {toasts.map((toast) => (
          <div key={toast.id} className={`${s.toast} ${toast.type === 'error' ? s.toastError : s.toastSuccess}`}>
            {toast.type === 'error' ? <Icons.AlertTriangle size={16} /> : <Icons.Check size={16} />}
            <span>{toast.text}</span>
          </div>
        ))}
      </div>

      {/* Metrics Bar */}
      <div className={s.metricsBar}>
        <HeroMetrics system={system} inferenceProgress={inferenceProgress} batchState={batchState} />
        {currentMode && currentMode !== 'FULL_FRAME' && (
          <div className={s.modeBadgeTop} style={{
            background: currentMode === 'ALERT_ONLY' ? 'rgba(239, 68, 68, 0.1)' : 'rgba(245, 158, 11, 0.1)',
            color: currentMode === 'ALERT_ONLY' ? 'var(--color-error)' : '#d97706',
            border: `1px solid ${currentMode === 'ALERT_ONLY' ? 'rgba(239, 68, 68, 0.3)' : 'rgba(245, 158, 11, 0.3)'}`,
            padding: '4px 10px',
            borderRadius: '100px',
            fontSize: '12px',
            fontWeight: 700,
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            marginLeft: 'auto'
          }}>
            <span className={s.pulseDot} style={{ background: 'currentColor' }} />
            {currentMode === 'ALERT_ONLY' ? '仅定位传输 (ALERT_ONLY)' : '降采样传输 (ROI_ONLY)'}
          </div>
        )}
      </div>

      {/* Main Content Area */}
      <div className={s.mainContent}>
        {/* Left: Primary Panel (62%) */}
        <div className={s.leftPanel}>
          <StaggeredList staggerDelay={0.06}>
            <AnimatedListItem>
              {/* Progress Section */}
              {/* Unified progress card — works for all modes and engines */}
              <div className={`${s.sectionCard} ${isRunning ? `${s.cardActiveGlow} ${s.scanlineOverlay}` : ''}`}>
                <div className={s.progressHeader}>
                  <div>
                    <div className={s.progressLabel}>{progressEngineLabel} 推理进度</div>
                    <div className={s.progressSubTitle}>{progressSubtitle} {currentMode === 'ROI_ONLY' && !isSingleLiveRunning && batchEngine !== 'mnn' && '(降采样中)'}</div>
                  </div>
                  <div className={s.progressBadge}>
                    {isRunning && <span className={s.pulseDot} />}
                    {progressBadge}
                  </div>
                </div>

                {hasStageProgress ? (
                  <div className={s.stageProgressGrid}>
                    <div className={s.stageProgressRow}>
                      <div className={s.stageProgressTopline}>
                        <span className={s.stageProgressTitle}>上位机图片→latent</span>
                        <span className={s.stageProgressCount}>{hostPreprocessStage.completed} / {hostPreprocessStage.total} {stageProgressSuffix}</span>
                      </div>
                      <div className={s.progressTrack}>
                        <div
                          className={`${s.progressFill} ${s.hostPreprocessFill}`}
                          style={{ width: `${hostPreprocessStage.percent}%` }}
                        />
                      </div>
                    </div>
                    <div className={s.stageProgressRow}>
                      <div className={s.stageProgressTopline}>
                        <span className={s.stageProgressTitle}>USRP 传输/解包</span>
                        <span className={s.stageProgressCount}>{transportStage.completed} / {transportStage.total} {stageProgressSuffix}</span>
                      </div>
                      <div className={s.progressTrack}>
                        <div
                          className={`${s.progressFill} ${s.transportFill}`}
                          style={{ width: `${transportStage.percent}%` }}
                        />
                      </div>
                    </div>
                    <div className={s.stageProgressRow}>
                      <div className={s.stageProgressTopline}>
                        <span className={s.stageProgressTitle}>{batchEngineLabel} 板端推理</span>
                        <span className={s.stageProgressCount}>{inferenceStage.completed} / {inferenceStage.total} {stageProgressSuffix}</span>
                      </div>
                      <div className={s.progressTrack}>
                        <div
                          className={`${s.progressFill} ${s.inferenceFill}`}
                          style={{ width: `${inferenceStage.percent}%` }}
                        />
                      </div>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className={s.progressCount}>
                      <strong>{progress}</strong>
                      <span>/ {totalImages} {progressSuffix}</span>
                    </div>

                    <div className={s.progressTrack}>
                      <div
                        className={s.progressFill}
                        style={{ width: `${progressPercent}%` }}
                      />
                    </div>
                  </>
                )}

                <div className={s.progressMeta}>
                  当前阶段：{hasStageProgress
                    ? `USRP ${transportStage.status} · ${batchEngineLabel} ${inferenceStage.status}`
                    : currentStage}
                </div>

                {batchIssueMessage && (
                  <div className={s.progressIssue}>
                    <div className={s.progressIssueTitle}>本次批量任务未进入有效重建链路</div>
                    <div>{batchIssueMessage}</div>
                    {batchIssueDetail && <div className={s.progressIssueDetail}>{batchIssueDetail}</div>}
                  </div>
                )}

                <LiveLogStream isRunning={isRunning} />
              </div>

              <GpsForwardStream
                isActive={currentMode === 'ALERT_ONLY'}
                sourceLabel={aircraft.data?.source_label}
                fixType={aircraft.data?.fix?.type}
                satellites={aircraft.data?.fix?.satellites}
                latitude={aircraft.data?.position?.latitude}
                longitude={aircraft.data?.position?.longitude}
                altitudeMeters={aircraft.data?.kinematics?.altitude_m}
              />
            </AnimatedListItem>

            <AnimatedListItem>
              {/* Action Section */}
              <div className={s.sectionCard}>
                <div className={s.sectionTitle}>执行操作</div>

                <div className={s.batchPresetMeta}>
                  <div>
                    <div className={s.batchPresetTitle}>批量规模</div>
                    <div className={s.batchPresetHint}>{batchPresetHint}</div>
                  </div>
                  <div className={`${s.batchPresetBadge} ${activeTransport === 'usrp' ? s.batchPresetBadgeUsr : s.batchPresetBadgeTcp}`}>
                    当前: {batchTargetLabel}
                  </div>
                </div>

                <div className={s.batchInputRow}>
                  <label className={s.batchInputField}>
                    <span className={s.batchInputLabel}>图像数量</span>
                    <input
                      type="number"
                      min={1}
                      max={MAX_BATCH_COUNT}
                      step={1}
                      inputMode="numeric"
                      className={s.batchInput}
                      value={batchCount}
                      disabled={isRunning || batchMut.isPending || mnnBatchMut.isPending || baselineMut.isPending}
                      onChange={(e) => {
                        setBatchCount(normalizeBatchCountInput(e.target.value, activeTransport === 'usrp' ? 20 : 300))
                        setBatchCountTouched(true)
                      }}
                    />
                  </label>
                  <div className={s.batchInputHint}>
                    预录模式默认 300，USRP 模式默认 20，最大 300。
                  </div>
                </div>

                <button
                  className={s.btnFilled}
                  onClick={() => handleRunInference(batchCount)}
                  disabled={batchMut.isPending || mnnBatchMut.isPending || isRunning}
                >
                  {batchMut.isPending ? <span className={s.spinner} /> : <Icons.Play size={18} />}
                  <span>
                    {batchMut.isPending
                      ? '启动中...'
                      : currentMode === 'ROI_ONLY'
                        ? `启动 TVM 降采样扫描 (${batchCount} 张入口 / 约 ${roiEffectiveCount} 帧)`
                        : `启动 TVM 推理 (${batchTargetLabel})`}
                  </span>
                </button>

                <div className={s.actionRow}>
                  <button
                    className={s.btnTonal}
                    onClick={() => probeMut.mutate()}
                    disabled={probeMut.isPending}
                  >
                    <span className={`${s.actionStatusDot} ${boardOnline ? s.statusDotOnline : s.statusDotOffline}`} />
                    {probeMut.isPending ? <span className={s.spinner} /> : <Icons.Radar size={16} />}
                    <span>探测板卡</span>
                  </button>

                  <button
                    className={s.btnTonal}
                    onClick={() => handleRunMnnInference(batchCount)}
                    disabled={mnnBatchMut.isPending || batchMut.isPending || isRunning}
                  >
                    {mnnBatchMut.isPending ? <span className={s.spinner} /> : <Icons.FileText size={16} />}
                    <span>{`MNN ${batchTargetLabel}`}</span>
                  </button>

                  <button
                    className={s.btnTonal}
                    onClick={() => baselineMut.mutate({ imageIndex: 0, count: batchCount })}
                    disabled={baselineMut.isPending || isRunning}
                  >
                    {baselineMut.isPending ? <span className={s.spinner} /> : <Icons.Activity size={16} />}
                    <span>{`PyTorch ${batchTargetLabel}`}</span>
                  </button>
                </div>
              </div>
            </AnimatedListItem>

            <AnimatedListItem className={s.flex1Item}>
              {/* Result Comparison — uses flex:1 to fill remaining space */}
              <div className={`${s.resultCard} ${hasPositiveSpeedup ? s.cardSuccessGlow : ''}`} style={{ flex: 1 }}>
                <div className={s.sectionTitle}>推理结果对比</div>
                {comparisonRows.length > 0 ? (
                  <>
                    <div className={s.comparisonShowcase}>
                      {comparisonRows.map((row) => {
                        const rowSpeedup = row.engine !== 'pytorch' && pytorchReferenceMs != null && pytorchReferenceMs > 0
                          ? ((pytorchReferenceMs - row.reconstructionMs) / pytorchReferenceMs * 100)
                          : null
                        return (
                        <div key={row.engine} className={s.barRow}>
                          <div className={s.barLabel}>{row.label}</div>
                          <div className={s.barTrack}>
                            <div
                              className={row.engine === 'pytorch' ? s.barFillBaseline : s.barFillCurrent}
                              style={{ width: `${Math.min((row.reconstructionMs / maxComparisonMs) * 100, 100)}%` }}
                            />
                          </div>
                          <div className={row.engine === 'pytorch' ? s.barValue : s.barValueHighlight}>
                            <span className={s.barMetric}>
                              <CountUp end={row.reconstructionMs} decimals={1} duration={400} />
                              <span className={s.barUnit}>ms</span>
                            </span>
                            {rowSpeedup != null && (
                              <span className={`${s.trendBadge} ${rowSpeedup >= 0 ? s.trendBadgePositive : s.trendBadgeNegative}`}>
                                {rowSpeedup >= 0 ? '↓' : '↑'} <CountUp end={Math.abs(rowSpeedup)} decimals={1} duration={400} />%
                              </span>
                            )}
                          </div>
                        </div>
                        )
                      })}
                    </div>
                    {resultQuality && (
                      <div className={s.qualityMetrics}>
                        {resultQuality.psnr_db != null && (
                          <div className={s.qualityItem}>
                            <span className={s.qualityLabel}>PSNR</span>
                            <span className={s.qualityValue}>{resultQuality.psnr_db.toFixed(2)} dB</span>
                          </div>
                        )}
                        {resultQuality.ssim != null && (
                          <div className={s.qualityItem}>
                            <span className={s.qualityLabel}>SSIM</span>
                            <span className={s.qualityValue}>{resultQuality.ssim.toFixed(4)}</span>
                          </div>
                        )}
                      </div>
                    )}
                  </>
                ) : (
                  <div className={s.resultEmpty}>
                    <div className={s.emptyIconWrapper}>
                      <Icons.Activity size={24} className={s.emptyIcon} />
                    </div>
                    <div className={s.emptyTitle}>
                      暂无推理结果
                    </div>
                    <div className={s.emptySubtitle}>
                      {`点击上方「启动 TVM 推理 (${batchTargetLabel})」或「MNN ${batchTargetLabel}」开始在线推进`}
                    </div>
                    <div className={s.emptyDescription}>
                      推理完成后将展示 TVM/MNN vs PyTorch 参考重建时间对比；TVM 单图结果会附带 PSNR/SSIM 质量指标
                    </div>
                  </div>
                )}
              </div>
            </AnimatedListItem>

            <AnimatedListItem>
              {/* Board Password */}
              <div className={s.sectionCard}>
                <div className={s.sectionTitle}>板卡连接设置</div>
                <div className={s.passwordRow}>
                  <input
                    type="password"
                    placeholder="输入板卡密码"
                    aria-label="板卡密码"
                    autoComplete="current-password"
                    value={boardPassword}
                    onChange={(e) => setBoardPassword(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') handleSavePassword() }}
                    className={s.passwordInput}
                  />
                  <button
                    className={s.btnFilledSm}
                    onClick={handleSavePassword}
                    disabled={boardAccessMut.isPending}
                  >
                    {boardAccessMut.isPending ? '保存中...' : '保存'}
                  </button>
                </div>
                <div className={s.settingGroup}>
                  <div className={s.settingRow}>
                    <div className={s.settingMeta}>
                      <div className={s.settingLabel}>认证面配置</div>
                      <div className={s.settingCaption}>控制当前 ML-KEM 信道是否叠加 ML-DSA / SM2 身份认证。</div>
                    </div>
                    <label className={s.authCheck}>
                      <input
                        type="checkbox"
                        checked={authEnabled}
                        onChange={(e) => {
                          setAuthEnabled(e.target.checked)
                          setAuthDirty(true)
                        }}
                      />
                      <span>启用认证</span>
                    </label>
                  </div>
                  <div className={s.settingStack}>
                    <label className={s.formLabel} htmlFor="auth-sig-policy">认证策略</label>
                    <select
                      id="auth-sig-policy"
                      className={s.selectInput}
                      value={authSigPolicy}
                      disabled={!authEnabled || boardAccessMut.isPending}
                      onChange={(e) => {
                        setAuthSigPolicy(normalizeAuthSigPolicy(e.target.value))
                        setAuthDirty(true)
                      }}
                    >
                      {AUTH_POLICY_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className={s.settingCaption}>{authHint}</div>
                  <div className={s.settingStatus}>{authStatusLabel}</div>
                  <div className={s.settingActions}>
                    <button
                      className={s.btnFilledSm}
                      onClick={handleSaveAuth}
                      disabled={boardAccessMut.isPending}
                    >
                      {boardAccessMut.isPending ? '保存中...' : '保存认证设置'}
                    </button>
                  </div>
                </div>
                <div className={s.settingGroup}>
                  <div className={s.settingRow}>
                    <div className={s.settingMeta}>
                      <div className={s.settingLabel}>数据面输入模式</div>
                      <div className={s.settingCaption}>认证面配置下方统一切换主 demo 的重建数据来源。</div>
                    </div>
                    <div className={`${s.transportBadge} ${activeTransport === 'usrp' ? s.transportBadgeUsr : s.transportBadgeTcp}`}>
                      当前: {activeTransport === 'usrp' ? 'USRP' : '预录'}
                    </div>
                  </div>
                  <div className={s.transportSwitch}>
                    {TRANSPORT_OPTIONS.map((option) => {
                      const isActive = activeTransport === option.mode
                      const isPending = boardAccessMut.isPending && pendingTransportMode === option.mode
                      return (
                        <button
                          key={option.mode}
                          type="button"
                          className={`${s.transportOption} ${isActive ? s.transportOptionActive : ''}`}
                          aria-pressed={isActive}
                          disabled={boardAccessMut.isPending}
                          onClick={() => {
                            if (!isActive) handleSelectTransport(option.mode)
                          }}
                        >
                          <span className={s.transportOptionLabel}>
                            {isPending ? '切换中...' : option.label}
                          </span>
                          <span className={s.transportOptionCaption}>{option.caption}</span>
                        </button>
                      )
                    })}
                  </div>
                  <div className={s.pathGrid}>
                    <div className={s.pathItem}>
                      <span className={s.pathLabel}>上位机输入目录</span>
                      <span className={s.pathValue}>{hostInputDir || (activeTransport === 'usrp' ? '未配置' : '预录模式不使用上位机输入')}</span>
                    </div>
                    <div className={s.pathItem}>
                      <span className={s.pathLabel}>板端输入目录</span>
                      <span className={s.pathValue}>{boardInputDir || '未配置'}</span>
                    </div>
                    <div className={s.pathItem}>
                      <span className={s.pathLabel}>板端重建输出目录</span>
                      <span className={s.pathValue}>{boardOutputDir || '未配置'}</span>
                    </div>
                  </div>
                </div>
              </div>
            </AnimatedListItem>
          </StaggeredList>
        </div>

        {/* Right: Secondary Panel (38%) */}
        <div className={s.rightPanel}>
          <div className={s.mapSection}>
            <FlightPanel
              aircraft={aircraft}
              chinaTheater={chinaTheater}
              setChinaTheater={setChinaTheater}
            />
          </div>

          <MinimalStatusPanel
            system={system}
            inferenceProgress={inferenceProgress?.data}
            activeJobId={activeJobId}
          />

          <CryptoStatusPanel />
        </div>
      </div>
    </PageTransition>
  )
}
