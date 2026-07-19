import { UseQueryResult } from '@tanstack/react-query'
import type { SystemStatusResponse } from '../../../api/types'
import type { BatchStateResponse } from '../../../api/types/crypto'
import { Icons } from '../../icons'
import { CountUp } from '../../shared/CountUp'
import { useAppStore } from '../../../stores/appStore'
import { comparisonResultFromInferencePayload } from '../../../hooks/comparisonResult'
import { shouldDisplayDashboardBatch } from '../../../hooks/dashboardBatchDisplayState'
import s from './HeroMetrics.module.css'

interface HeroMetricsProps {
  system: UseQueryResult<SystemStatusResponse>
  inferenceProgress?: any
  batchState?: UseQueryResult<BatchStateResponse>
  currentMode?: string | null
}

export function HeroMetrics({ system, inferenceProgress, batchState, currentMode }: HeroMetricsProps) {
  const status = system.data
  const comparisonResults = useAppStore((s) => s.comparisonResults)
  const pendingBatchJobId = useAppStore((s) => s.pendingBatchJobId)
  const recentTvmComparisonRaw = comparisonResultFromInferencePayload(status?.recent_results?.tvm ?? status?.recent_results?.current)
  const recentTvmComparison = recentTvmComparisonRaw?.engine === 'tvm' ? recentTvmComparisonRaw : undefined
  const recentMnnComparisonRaw = comparisonResultFromInferencePayload(status?.recent_results?.mnn ?? status?.recent_results?.current)
  const recentMnnComparison = recentMnnComparisonRaw?.engine === 'mnn' ? recentMnnComparisonRaw : undefined
  const recentBaselineComparison = comparisonResultFromInferencePayload(status?.recent_results?.pytorch ?? status?.recent_results?.baseline)
  const live = status?.live
  const boardOnline = live?.board_online ?? false
  const batch = batchState?.data
  const activeBatch = batch && shouldDisplayDashboardBatch(batch, pendingBatchJobId, currentMode)
    ? batch
    : undefined

  const acceleratorResults = [
    comparisonResults.tvm ?? recentTvmComparison,
    comparisonResults.mnn ?? recentMnnComparison,
  ]
    .filter((item): item is NonNullable<typeof item> => Boolean(item))
  const latestAccelerator = acceleratorResults.reduce<(typeof acceleratorResults)[number] | undefined>(
    (latest, item) => {
      if (!latest) return item
      return (item.updatedAt ?? 0) >= (latest.updatedAt ?? 0) ? item : latest
    },
    undefined,
  )
  const baseReconstructionCurrent = latestAccelerator?.reconstructionMs
  const reconstructionBaseline = comparisonResults.pytorch?.reconstructionMs ?? recentBaselineComparison?.reconstructionMs
  const baseImprovementPct = (baseReconstructionCurrent && reconstructionBaseline && reconstructionBaseline > 0)
    ? ((reconstructionBaseline - baseReconstructionCurrent) / reconstructionBaseline * 100)
    : null

  const lp = inferenceProgress?.data?.live_progress
  const isSingleInferenceActive = !!inferenceProgress?.data && inferenceProgress.data.request_state === 'running'
  const isBatchActive = activeBatch?.status === 'running'
  const isActiveInference = isSingleInferenceActive || isBatchActive
  const batchEngineLabel = activeBatch?.engine === 'mnn' ? 'MNN 推理' : 'TVM 推理'
  const progressLabel = isSingleInferenceActive
    ? (lp?.label ?? inferenceProgress?.data?.status_category ?? inferenceProgress?.data?.request_state)
    : isBatchActive
      ? `${batchEngineLabel} ${activeBatch?.completed ?? 0}/${activeBatch?.total ?? 300}`
      : activeBatch?.status === 'done'
        ? activeBatch.fallback && activeBatch.fallback > 0
          ? `批量结束 ${activeBatch.success ?? 0}/${activeBatch.total ?? 300} 成功`
          : '批量完成'
        : '空闲'

  return (
    <div className={s.container}>
      {/* System Status — with colored dot */}
      <div className={s.metricItem}>
        <div className={s.metricTop}>
          <span
            className={s.metricDot}
            style={{ background: boardOnline ? 'var(--color-success)' : 'var(--color-error)' }}
          />
          <span className={s.metricLabel}>状态</span>
        </div>
        <span className={s.metricValue} style={{ color: boardOnline ? 'var(--color-success)' : 'var(--color-error)' }}>
          {boardOnline ? 'Online' : 'Offline'}
        </span>
      </div>

      {/* Guard State */}
      <div className={s.metricItem}>
        <div className={s.metricTop}>
          <Icons.Shield size={11} className={s.metricIcon} aria-hidden="true" />
          <span className={s.metricLabel}>Guard</span>
        </div>
        <span className={s.metricValue}>{live?.guard_state ?? '—'}</span>
      </div>

      {/* Reconstruction latency */}
      <div className={s.metricItem}>
        <div className={s.metricTop}>
          <Icons.Zap size={11} className={s.metricIcon} aria-hidden="true" />
          <span className={s.metricLabel}>重建</span>
        </div>
        <div className={s.metricValueContainer}>
          {baseReconstructionCurrent != null ? (
            <span className={`${s.metricValue} ${s.metricHighlight}`}>
              <CountUp end={baseReconstructionCurrent} decimals={1} duration={350} /> ms
            </span>
          ) : (
            <span className={s.metricValue}>—</span>
          )}
        </div>
      </div>

      {/* Baseline */}
      <div className={s.metricItem}>
        <div className={s.metricTop}>
          <Icons.Activity size={11} className={s.metricIcon} aria-hidden="true" />
          <span className={s.metricLabel}>Baseline</span>
        </div>
        <div className={s.metricValueContainer}>
          {reconstructionBaseline != null ? (
            <span className={s.metricValue}>
              <CountUp end={reconstructionBaseline} decimals={1} duration={350} /> ms
            </span>
          ) : (
            <span className={s.metricValue}>—</span>
          )}
        </div>
      </div>

      {/* Improvement */}
      {baseImprovementPct != null && (
        <div className={s.metricItem}>
          <div className={s.metricTop}>
            <Icons.TrendingUp size={11} className={s.metricIcon} style={{ color: 'var(--color-primary)' }} aria-hidden="true" />
            <span className={s.metricLabel}>加速</span>
          </div>
          <div className={s.metricValueContainer}>
            <span className={s.metricValueGiant}>
              <CountUp end={baseImprovementPct} decimals={1} duration={350} />%
            </span>
          </div>
        </div>
      )}

      {/* Inference Status */}
      <div className={s.metricItem}>
        <div className={s.metricTop}>
          {isActiveInference ? (
            <Icons.RefreshCw size={11} className={`${s.metricIcon} icon-spin`} style={{ color: 'var(--color-primary)' }} aria-hidden="true" />
          ) : (
            <Icons.BarChart size={11} className={s.metricIcon} aria-hidden="true" />
          )}
          <span className={s.metricLabel}>推理状态</span>
        </div>
        <span
          className={s.metricValue}
          style={isActiveInference ? { color: 'var(--color-primary)' } : undefined}
        >
          {progressLabel ?? '空闲'}
        </span>
      </div>
    </div>
  )
}
