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
import type { BatchStageProgress, IqTailAudit } from '../api/types/crypto'
import { comparisonResultFromInferencePayload } from '../hooks/comparisonResult'
import { shouldDisplayDashboardBatch } from '../hooks/dashboardBatchDisplayState'
import {
  extractIqRadioMetrics,
  extractJsccLinkMode,
  type IqRadioMetrics,
  type JsccLinkMode,
  type JsonObject,
} from '../api/types'
import s from './DashboardPageMinimal.module.css'

const LIVE_LOG_ACTIONS = ['Processing block', 'Allocating memory', 'Optimizing tensor', 'Compiling kernel', 'Syncing device']

type TransportMode = 'tcp' | 'usrp'

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

const LINK_MODE_OPTIONS: { mode: JsccLinkMode; label: string; caption: string }[] = [
  {
    mode: 'qpsk',
    label: 'QPSK',
    caption: '可靠字节链路，保留 CRC/ARQ 兜底。',
  },
  {
    mode: 'iq-direct',
    label: 'IQ 直传',
    caption: 'JSCC latent 直接映射模拟 IQ 波形。',
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

function normalizeTransportMode(rawValue: unknown): TransportMode {
  return String(rawValue || '').trim().toLowerCase() === 'usrp' ? 'usrp' : 'tcp'
}

function normalizeJsccLinkModeValue(rawValue: unknown): JsccLinkMode {
  const normalized = String(rawValue || '').trim().toLowerCase()
  return normalized === 'iq-direct' || normalized === 'iq' || normalized === 'analog' ? 'iq-direct' : 'qpsk'
}

function normalizeBatchCountInput(rawValue: string, fallback: number): number {
  const parsed = Number(rawValue)
  if (!Number.isFinite(parsed)) {
    return fallback
  }
  return Math.max(1, Math.min(Math.trunc(parsed), MAX_BATCH_COUNT))
}

function formatMetricValue(value: number | undefined, decimals = 3): string | undefined {
  return value == null ? undefined : value.toFixed(decimals)
}

function formatPercentValue(value: number | undefined): string | undefined {
  return value == null ? undefined : `${value.toFixed(1)}%`
}

type IqTailAuditItem = {
  key: string
  label: string
  value: string
  tone: 'ok' | 'fail' | 'mono'
}

type IqTailDistributionItem = {
  key: string
  label: string
  value: string
  tone: 'ok' | 'fail'
}

function iqTailCount(audit: IqTailAudit | null | undefined, key: keyof IqTailAudit): number | null {
  const value = audit?.[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function buildIqTailAuditItems(
  audit: IqTailAudit | null | undefined,
  sampleCount: number | null | undefined,
): IqTailAuditItem[] {
  const items: IqTailAuditItem[] = []

  if (sampleCount != null) {
    items.push({ key: 'sample_count', label: '样本数', value: sampleCount.toLocaleString(), tone: 'mono' })
  }
  if (!audit) return items

  const referenceMs = iqTailCount(audit, 'reference_ms')
  const overReference = iqTailCount(audit, 'over_reference_count')

  if (referenceMs != null && overReference != null) {
    items.push({
      key: 'over_reference_count',
      label: `>${referenceMs.toFixed(1)}ms`,
      value: overReference.toLocaleString(),
      tone: overReference > 0 ? 'fail' : 'ok',
    })
  }

  const tailRows: [keyof IqTailAudit, string][] = [
    ['rx_control_overhead_gt_50ms_count', 'RX控制尾部'],
    ['server_capture_gt_100ms_count', 'RX采集尾部'],
    ['decode_gt_160ms_count', '解码尾部'],
    ['worker_over_reported_gt_80ms_count', 'Worker响应'],
    ['write_gt_100ms_count', '写入尾部'],
    ['soft_completed_count', 'Soft完成'],
  ]

  for (const [key, label] of tailRows) {
    const value = iqTailCount(audit, key)
    if (value != null) {
      items.push({
        key: String(key),
        label,
        value: value.toLocaleString(),
        tone: value > 0 && key !== 'soft_completed_count' ? 'fail' : 'mono',
      })
    }
  }

  return items
}

function buildIqTailDistributionItems(audit: IqTailAudit | null | undefined): IqTailDistributionItem[] {
  if (!audit) return []

  const thresholdRows: [keyof IqTailAudit, string][] = [
    ['total_gt_250ms_count', '>250ms'],
    ['total_gt_275ms_count', '>275ms'],
    ['total_gt_500ms_count', '>500ms'],
  ]

  const items: IqTailDistributionItem[] = []
  for (const [key, label] of thresholdRows) {
    const value = iqTailCount(audit, key)
    if (value != null) {
      items.push({
        key: String(key),
        label,
        value: value.toLocaleString(),
        tone: value > 0 ? 'fail' : 'ok',
      })
    }
  }
  return items
}

type MainProgressTone = 'yellow' | 'green' | 'blue'
type MainProgressState = 'done' | 'active' | 'pending'

function mainProgressToneClass(tone: MainProgressTone): string {
  if (tone === 'yellow') return s.mainStageYellow
  if (tone === 'green') return s.mainStageGreen
  return s.mainStageBlue
}

function mainProgressStateClass(state: MainProgressState): string {
  if (state === 'done') return s.mainStageDone
  if (state === 'active') return s.mainStageActive
  return s.mainStagePending
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
      <div className={`${s.liveLogStream} ${s.alertModeLogStream}`} style={{ marginTop: '8px' }}>
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
  const [authEnabled, setAuthEnabled] = useState(true)
  const [remoteUsrPRxDir, setRemoteUsrPRxDir] = useState('')
  const [remoteUsrPRxDirDirty, setRemoteUsrPRxDirDirty] = useState(false)
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
    setAuthEnabled(Boolean(cryptoData?.auth_enabled))
  }, [cryptoData?.auth_enabled])

  useEffect(() => {
    if (batchCountTouched) return
    setBatchCount(300)
  }, [activeTransport, batchCountTouched])

  useEffect(() => {
    if (remoteUsrPRxDirDirty) return
    setRemoteUsrPRxDir(String(boardAccess?.remote_usrp_rx_dir || ''))
  }, [boardAccess?.remote_usrp_rx_dir, remoteUsrPRxDirDirty])

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

  const handleToggleAuth = useCallback(
    (enabled: boolean) => {
      setAuthEnabled(enabled)
      boardAccessMut.mutate(
        {
          auth_enabled: enabled,
          auth_sig_policy: 'DUAL_REQUIRED',
        },
        {
          onSuccess: () => {
            showToast(enabled ? '认证已启用: ML-DSA + SM2' : '认证已关闭', 'success')
          },
          onError: (error) => {
            setAuthEnabled(Boolean(cryptoData?.auth_enabled))
            showToast(`切换认证失败: ${error.message}`, 'error')
          },
        },
      )
    },
    [boardAccessMut, cryptoData?.auth_enabled, showToast],
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

  const handleSelectLinkMode = useCallback(
    (mode: JsccLinkMode) => {
      const selected = LINK_MODE_OPTIONS.find((option) => option.mode === mode)
      boardAccessMut.mutate(
        { transport_mode: 'usrp', jscc_link_mode: mode },
        {
          onSuccess: () => {
            showToast(`JSCC 链路已切换: ${selected?.label ?? mode}`, 'success')
          },
          onError: (error) => {
            showToast(`切换 JSCC 链路失败: ${error.message}`, 'error')
          },
        },
      )
    },
    [boardAccessMut, showToast],
  )

  // Derived data
  const recentResults = status?.recent_results
  const currentResultFromStore = lastCompletedInference?.variant === 'current' ? lastCompletedInference : undefined
  const currentResult = currentResultFromStore ?? recentResults?.current ?? recentResults?.tvm ?? recentResults?.mnn
  const baselineResultFromStore = lastCompletedInference?.variant === 'baseline' ? lastCompletedInference : undefined
  const baselineResult = baselineResultFromStore ?? recentResults?.pytorch ?? recentResults?.baseline
  const currentComparisonFromStore = comparisonResultFromInferencePayload(currentResultFromStore)
  const tvmComparisonFromPayloadRaw = comparisonResultFromInferencePayload(recentResults?.tvm ?? recentResults?.current)
  const tvmComparisonFromPayload = tvmComparisonFromPayloadRaw?.engine === 'tvm' ? tvmComparisonFromPayloadRaw : undefined
  const mnnComparisonFromPayloadRaw = comparisonResultFromInferencePayload(recentResults?.mnn ?? recentResults?.current)
  const mnnComparisonFromPayload = mnnComparisonFromPayloadRaw?.engine === 'mnn' ? mnnComparisonFromPayloadRaw : undefined
  const baselineComparisonFromPayload = comparisonResultFromInferencePayload(baselineResult)
  const pytorchComparison =
    baselineComparisonFromPayload
    ?? comparisonResults.pytorch
  const tvmComparison =
    comparisonResults.tvm
    ?? (currentComparisonFromStore?.engine === 'tvm' ? currentComparisonFromStore : undefined)
    ?? tvmComparisonFromPayload
  const mnnComparison =
    comparisonResults.mnn
    ?? (currentComparisonFromStore?.engine === 'mnn' ? currentComparisonFromStore : undefined)
    ?? mnnComparisonFromPayload
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
  const activeBatch = batch && shouldDisplayDashboardBatch(batch, pendingBatchJobId, currentMode)
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
  const useUsrpProgressLayout = !isSingleLiveRunning && activeTransport === 'usrp'
  const hasStageProgress = useUsrpProgressLayout && Boolean(activeBatch?.host_preprocess_progress || activeBatch?.transport_progress || activeBatch?.inference_progress)
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
  const progressPercent = totalImages > 0 ? Math.round((progress / totalImages) * 100) : 0
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
  const mainProgressRows = [
    { key: 'host', label: activeTransport === 'usrp' ? '上位机图片→latent' : '预录输入准备', tone: 'yellow' as const, stage: hostPreprocessStage },
    { key: 'transport', label: activeTransport === 'usrp' ? 'USRP 传输/解包' : '预录数据装载', tone: 'green' as const, stage: transportStage },
    { key: 'inference', label: `${batchEngineLabel} 板端推理`, tone: 'blue' as const, stage: inferenceStage },
  ]
  const stageDoneFlags = hasStageProgress
    ? mainProgressRows.map((row) => row.stage.completed >= row.stage.total || row.stage.status === 'completed' || row.stage.status === 'done')
    : [
        isRunning || isDone,
        isRunning || isDone,
        isDone,
      ]
  const firstIncompleteStageIndex = stageDoneFlags.findIndex((done) => !done)
  const activeMainStageIndex = isRunning && firstIncompleteStageIndex >= 0
    ? firstIncompleteStageIndex
    : -1
  const mainProgressStages = mainProgressRows.map((row, index) => {
    const state: MainProgressState = stageDoneFlags[index]
      ? 'done'
      : index === activeMainStageIndex
        ? 'active'
        : 'pending'
    return { ...row, state }
  })
  const activeMainStage = mainProgressStages.find((stage) => stage.state === 'active')
  const mainProgressStageText = isRunning
    ? activeMainStage?.label ?? currentStage
    : isDone
      ? currentStage
      : '就绪'
  const mainProgressStageDetail = isRunning
    ? `进度 ${progress}/${totalImages}`
    : ''
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
  const configuredLinkMode = normalizeJsccLinkModeValue(boardAccess?.jscc_link_mode)
  const pendingJsccLinkMode = boardAccessMut.variables?.jscc_link_mode
    ? normalizeJsccLinkModeValue(boardAccessMut.variables.jscc_link_mode)
    : undefined
  const currentWrapperSummary = (currentResult?.wrapper_summary ?? undefined) as JsonObject | undefined
  const activeLinkMode: JsccLinkMode = extractJsccLinkMode(currentWrapperSummary) ?? configuredLinkMode
  const iqRadioMetrics: IqRadioMetrics | undefined = extractIqRadioMetrics(currentWrapperSummary)
  const iqTailAudit = cryptoData?.batch_iq_tail_audit ?? null
  const iqTailSampleCount = iqTailCount(iqTailAudit, 'record_count') ?? iqRadioMetrics?.sample_count ?? null
  const iqTailReferenceMs = iqTailCount(iqTailAudit, 'reference_ms')
  const iqTailAuditItems = buildIqTailAuditItems(iqTailAudit, iqTailSampleCount)
  const iqTailDistributionItems = buildIqTailDistributionItems(iqTailAudit)
  const iqRadioMetricItems = [
    iqRadioMetrics?.sync_success_ratio != null
      ? { key: 'syncRatio', label: '同步率', value: formatPercentValue(iqRadioMetrics.sync_success_ratio * 100) }
      : undefined,
    iqRadioMetrics?.sync_metric?.mean != null
      ? { key: 'sync', label: 'sync', value: formatMetricValue(iqRadioMetrics.sync_metric.mean, 4) }
      : undefined,
    iqRadioMetrics?.evm_rms?.mean != null
      ? { key: 'evm', label: 'EVM', value: formatMetricValue(iqRadioMetrics.evm_rms.mean, 4) }
      : undefined,
    iqRadioMetrics?.estimated_cfo_hz?.mean != null
      ? { key: 'cfo', label: 'CFO', value: `${iqRadioMetrics.estimated_cfo_hz.mean.toFixed(1)} Hz` }
      : undefined,
    iqRadioMetrics?.estimated_snr_db?.mean != null
      ? { key: 'snr', label: 'SNR', value: `${iqRadioMetrics.estimated_snr_db.mean.toFixed(1)} dB` }
      : undefined,
    iqRadioMetrics?.rx_clipping_ratio?.mean != null
      ? { key: 'clip', label: 'Clipping', value: formatPercentValue(iqRadioMetrics.rx_clipping_ratio.mean * 100) }
      : undefined,
    iqRadioMetrics?.latent_mse_vs_tx?.mean != null
      ? { key: 'latentMse', label: 'Latent MSE', value: formatMetricValue(iqRadioMetrics.latent_mse_vs_tx.mean, 5) }
      : undefined,
  ].filter((item): item is { key: string; label: string; value: string } => Boolean(item?.value))
  const showIqAuditPanel = activeTransport === 'usrp'
    && activeLinkMode === 'iq-direct'
    && (iqTailAuditItems.length > 0 || iqTailDistributionItems.length > 0 || iqRadioMetricItems.length > 0)
  const inputModeLabel = activeTransport === 'usrp'
    ? activeLinkMode === 'iq-direct'
      ? 'USRP-IQ直传'
      : 'USRP-QPSK'
    : '预录'
  const inputModeBadgeClass = activeTransport === 'usrp'
    ? activeLinkMode === 'iq-direct'
      ? s.transportBadgeIq
      : s.transportBadgeQpsk
    : s.transportBadgeTcp
  const configuredRemoteUsrPRxDir = String(boardAccess?.remote_usrp_rx_dir ?? '').trim()
  const remoteUsrPRxDirInput = remoteUsrPRxDir.trim()
  const remoteUsrPRxDirApplied = activeTransport === 'usrp'
    && remoteUsrPRxDirInput.length > 0
    && configuredRemoteUsrPRxDir === remoteUsrPRxDirInput
  const remoteUsrPRxDirButtonLabel = boardAccessMut.isPending
    ? '保存中...'
    : remoteUsrPRxDirApplied
      ? '已生效'
      : '保存目录'
  const boardSessionReady = Boolean(boardAccess?.connection_ready)
  const handleSaveRemoteUsrPRxDir = useCallback(
    () => {
      const remoteRxDir = remoteUsrPRxDir.trim()
      if (!remoteRxDir) {
        showToast('请输入板端 USRP RX 目录', 'error')
        return
      }
      boardAccessMut.mutate(
        {
          transport_mode: 'usrp',
          jscc_link_mode: activeLinkMode,
          remote_usrp_rx_dir: remoteRxDir,
        },
        {
          onSuccess: () => {
            setRemoteUsrPRxDirDirty(false)
            showToast('USRP RX 目录已保存', 'success')
          },
          onError: (error) => {
            showToast(`保存 USRP RX 目录失败: ${error.message}`, 'error')
          },
        },
      )
    },
    [activeLinkMode, boardAccessMut, remoteUsrPRxDir, showToast],
  )
  const roiEffectiveCount = Math.max(1, Math.ceil(batchCount / 3))
  const batchTargetLabel = `${batchCount} 张`
  const boardHostLabel = typeof boardAccess?.host === 'string' && boardAccess.host.trim()
    ? boardAccess.host
    : '未配置'
  const boardUserLabel = typeof boardAccess?.user === 'string' && boardAccess.user.trim()
    ? boardAccess.user
    : '未配置'
  const boardPasswordSaved = Boolean(boardAccess?.has_password)
  const authConfig = {
    enabled: authEnabled,
    disabled: boardAccessMut.isPending,
    onToggle: handleToggleAuth,
  }

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
        <HeroMetrics system={system} inferenceProgress={inferenceProgress} batchState={batchState} currentMode={currentMode} />
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

                {useUsrpProgressLayout ? (
                  <>
                    <div className={s.progressCount}>
                      <strong className={s.progressStageText}>{mainProgressStageText}</strong>
                      {mainProgressStageDetail && <span>{mainProgressStageDetail}</span>}
                    </div>

                    <div className={s.mainStageTrack} aria-label="推理阶段进度">
                      {mainProgressStages.map((stage) => (
                        <div
                          key={stage.key}
                          className={[
                            s.mainStageSegment,
                            mainProgressToneClass(stage.tone),
                            mainProgressStateClass(stage.state),
                          ].join(' ')}
                          title={`${stage.label}: ${stage.state}`}
                          aria-label={`${stage.label}: ${stage.state}`}
                        />
                      ))}
                    </div>

                    {hasStageProgress && (
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
                    )}
                  </>
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
                        setBatchCount(normalizeBatchCountInput(e.target.value, 300))
                        setBatchCountTouched(true)
                      }}
                    />
                  </label>
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
              {/* Data Plane */}
              <div className={s.sectionCard}>
                <div className={s.sectionTitle}>数据面输入模式</div>
                <div className={s.settingGroup}>
                  <div className={s.settingRow}>
                    <div className={s.settingMeta}>
                      <div className={s.settingLabel}>输入来源</div>
                    </div>
                    <div className={`${s.transportBadge} ${inputModeBadgeClass}`}>
                      当前: {inputModeLabel}
                    </div>
                  </div>
                  <div className={s.modeSwitchStack}>
                    <div className={s.modeSwitchBlock}>
                      <div className={s.formLabel}>数据来源</div>
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
                    </div>
                    {activeTransport === 'usrp' && (
                      <div className={s.modeSwitchBlock}>
                        <div className={s.formLabel}>USRP JSCC 链路</div>
                        <div className={s.linkModeSwitch}>
                          {LINK_MODE_OPTIONS.map((option) => {
                            const isActive = configuredLinkMode === option.mode
                            const isPending = boardAccessMut.isPending && pendingJsccLinkMode === option.mode
                            return (
                              <button
                                key={option.mode}
                                type="button"
                                className={`${s.linkModeOption} ${isActive ? s.linkModeOptionActive : ''}`}
                                aria-pressed={isActive}
                                disabled={boardAccessMut.isPending}
                                onClick={() => {
                                  if (!isActive) handleSelectLinkMode(option.mode)
                                }}
                              >
                                <span className={s.linkModeOptionLabel}>
                                  {isPending ? '切换中...' : option.label}
                                </span>
                                <span className={s.linkModeOptionCaption}>{option.caption}</span>
                              </button>
                            )
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                  {showIqAuditPanel && (
                    <div className={s.iqAuditPanel}>
                      <div className={s.iqAuditHeader}>
                        <div>
                          <div className={s.iqAuditTitle}>IQ直传链路诊断</div>
                          <div className={s.iqAuditCaption}>链路质量、尾部计数与耗时阈值分布</div>
                        </div>
                        <span className={s.iqAuditBadge}>IQ 生效</span>
                      </div>

                      {iqRadioMetricItems.length > 0 && (
                        <div className={s.iqAuditSection}>
                          <div className={s.iqAuditSectionTitle}>链路质量</div>
                          <div className={s.iqQualityGrid} aria-label="IQ 射频质量指标">
                            {iqRadioMetricItems.map((item) => (
                              <div key={item.key} className={s.iqQualityItem}>
                                <span className={s.iqQualityLabel}>{item.label}</span>
                                <span className={s.iqQualityValue}>{item.value}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {iqTailDistributionItems.length > 0 && (
                        <div className={s.iqAuditSection}>
                          <div className={s.iqAuditSectionHeader}>
                            <div className={s.iqAuditSectionTitle}>尾部时间分布</div>
                            {iqTailReferenceMs != null && (
                              <div className={s.iqTailReference}>参考 {iqTailReferenceMs.toFixed(1)}ms</div>
                            )}
                          </div>
                          <div className={s.iqTailAxis} aria-label="IQ 尾部耗时阈值分布">
                            {iqTailDistributionItems.map((item) => (
                              <div
                                key={item.key}
                                className={`${s.iqTailAxisItem} ${item.tone === 'fail' ? s.iqTailAxisItemFail : s.iqTailAxisItemOk}`}
                              >
                                <span className={s.iqTailAxisTick}>{item.label}</span>
                                <span className={item.tone === 'fail' ? s.iqTailAxisValueFail : s.iqTailAxisValue}>{item.value}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {iqTailAuditItems.length > 0 && (
                        <div className={s.iqAuditSection}>
                          <div className={s.iqAuditSectionTitle}>尾部统计</div>
                          <div className={s.iqTailGrid} aria-label="IQ 尾部统计指标">
                            {iqTailAuditItems.map((item) => (
                              <div
                                key={item.key}
                                className={`${s.iqTailItem} ${item.tone === 'fail' ? s.iqTailItemFail : item.tone === 'ok' ? s.iqTailItemOk : ''}`}
                              >
                                <span className={s.iqTailLabel}>{item.label}</span>
                                <span className={item.tone === 'fail' ? s.iqTailValueFail : s.iqTailValue}>{item.value}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                  <div className={s.pathGrid}>
                    <div className={s.pathItem}>
                      <span className={s.pathLabel}>上位机输入目录</span>
                      <span className={s.pathValue}>{hostInputDir || (activeTransport === 'usrp' ? '未配置' : '预录模式不使用上位机输入')}</span>
                    </div>
                    {activeTransport === 'usrp' ? (
                      <div className={`${s.pathItem} ${s.pathItemEditable}`}>
                        <label className={s.pathLabel} htmlFor="remote-usrp-rx-dir">板端输入/RX 目录</label>
                        <input
                          id="remote-usrp-rx-dir"
                          type="text"
                          placeholder="/home/user/cockpit_usrp_rx"
                          aria-label="板端输入/RX 目录"
                          value={remoteUsrPRxDir}
                          onChange={(event) => {
                            setRemoteUsrPRxDir(event.target.value)
                            setRemoteUsrPRxDirDirty(event.target.value.trim() !== configuredRemoteUsrPRxDir)
                          }}
                          onKeyDown={(event) => {
                            if (event.key === 'Enter' && !remoteUsrPRxDirApplied) handleSaveRemoteUsrPRxDir()
                          }}
                          className={s.pathInput}
                        />
                        <button
                          type="button"
                          className={remoteUsrPRxDirApplied ? s.btnAppliedSm : s.btnFilledSm}
                          onClick={handleSaveRemoteUsrPRxDir}
                          disabled={boardAccessMut.isPending || remoteUsrPRxDirApplied || remoteUsrPRxDirInput.length === 0}
                        >
                          {remoteUsrPRxDirButtonLabel}
                        </button>
                      </div>
                    ) : (
                      <div className={s.pathItem}>
                        <span className={s.pathLabel}>板端输入目录</span>
                        <span className={s.pathValue}>{boardInputDir || '未配置'}</span>
                      </div>
                    )}
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

          <div className={s.sectionCard}>
            <div className={s.sectionTitleRow}>
              <div className={s.sectionTitle}>板卡密码</div>
              <div
                className={`${s.boardSessionBadge} ${boardSessionReady ? s.boardSessionBadgeReady : s.boardSessionBadgeBlocked}`}
                title={boardSessionReady ? 'SSH 会话字段已补齐' : '补齐板卡主机、用户和密码后才能执行 live/USRP 推理'}
              >
                {boardSessionReady ? '板卡就绪' : '板卡未就绪'}
              </div>
            </div>
            <div className={s.boardPasswordMeta}>
              <span>主机: {boardHostLabel}</span>
              <span>用户: {boardUserLabel}</span>
              <span>{boardPasswordSaved ? '当前会话已保存密码' : '当前会话缺少密码'}</span>
            </div>
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
          </div>

          <CryptoStatusPanel authConfig={authConfig} />
        </div>
      </div>
    </PageTransition>
  )
}
