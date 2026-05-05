import { UseQueryResult } from '@tanstack/react-query'
import type { SystemStatusResponse } from '../../../api/types'
import type { BatchStateResponse } from '../../../api/types/crypto'
import { Icons } from '../../icons'
import { CountUp } from '../../shared/CountUp'
import { useAppStore } from '../../../stores/appStore'
import { comparisonResultFromInferencePayload } from '../../../hooks/comparisonResult'
import s from './HeroMetrics.module.css'

function Sparkline({ data, color }: { data: number[], color: string }) {
  if (!data || data.length === 0) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const width = 48;
  const height = 16;

  if (data.length === 1) {
    return (
      <svg width={width} height={height} className={s.sparkline} viewBox={`0 -2 ${width} ${height + 4}`}>
        <circle cx={width / 2} cy={height / 2} r={2.5} fill={color} />
      </svg>
    );
  }
  
  const points = data.map((d, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = height - ((d - min) / range) * height;
    return `${x},${y}`;
  }).join(' L ');

  return (
    <svg width={width} height={height} className={s.sparkline} viewBox={`0 -2 ${width} ${height + 4}`}>
      <path d={`M ${points}`} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

interface HeroMetricsProps {
  system: UseQueryResult<SystemStatusResponse>
  inferenceProgress?: any
  batchState?: UseQueryResult<BatchStateResponse>
}

export function HeroMetrics({ system, inferenceProgress, batchState }: HeroMetricsProps) {
  const status = system.data
  const comparisonResults = useAppStore((s) => s.comparisonResults)
  const pendingBatchJobId = useAppStore((s) => s.pendingBatchJobId)
  const recentCurrentComparison = comparisonResultFromInferencePayload(status?.recent_results?.current)
  const recentBaselineComparison = comparisonResultFromInferencePayload(status?.recent_results?.baseline)
  const live = status?.live
  const boardOnline = live?.board_online ?? false
  const batch = batchState?.data
  const isCurrentSessionBatch = Boolean(
    batch?.batch_job_id
    && pendingBatchJobId
    && batch.batch_job_id === pendingBatchJobId,
  )
  const activeBatch = batch && (isCurrentSessionBatch || batch.status === 'running' || batch.status === 'done')
    ? batch
    : undefined

  const acceleratorResults = [comparisonResults.tvm ?? recentCurrentComparison, comparisonResults.mnn]
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

  // Mock data for sparklines to show activity
  const mockReconstructionData = [145, 142, 138, 135, 132, 130, 131, 129, 130];
  const mockSpeedupData = [85, 88, 90, 91, 92, 93, 92.5, 93, 93];

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
            <>
              <span className={`${s.metricValue} ${s.metricHighlight}`}>
                <CountUp end={baseReconstructionCurrent} decimals={1} duration={350} /> ms
              </span>
              {isActiveInference && <Sparkline data={mockReconstructionData} color="var(--color-primary)" />}
            </>
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
            {isActiveInference && <Sparkline data={mockSpeedupData} color="var(--color-primary)" />}
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
