import { Space, Typography } from 'antd'
import { PanelCard } from '../../shared/PanelCard'
import { ToneTag } from '../../shared/ToneTag'
import { InferenceTimeline } from '../../charts/InferenceTimeline'
import { CockpitProgress } from '../../ios/CockpitProgress'
import { Icons } from '../../icons'
import { UseQueryResult } from '@tanstack/react-query'
import { useAppStore } from '../../../stores/appStore'
import type { SystemStatusResponse, RunInferenceResponse } from '../../../api/types'
import s from './InferenceProgressCard.module.css'

const { Text } = Typography

interface InferenceProgressCardProps {
  activeJobId: string | null
  inferenceProgress: UseQueryResult<RunInferenceResponse | null>
  system: UseQueryResult<SystemStatusResponse>
}

export function InferenceProgressCard({ activeJobId, inferenceProgress, system }: InferenceProgressCardProps) {
  const status = system.data
  const lastCompleted = useAppStore((s) => s.lastCompletedInference)
  const setLastCompletedInference = useAppStore((s) => s.setLastCompletedInference)
  const mergedResults = {
    ...(status?.recent_results ?? {}),
    ...(lastCompleted?.variant === 'current' && lastCompleted?.execution_mode === 'live' && lastCompleted?.status === 'success'
      ? { current: lastCompleted }
      : {}),
  }

  // Active running inference
  if (activeJobId) {
    return (
      <PanelCard title="推理进度" icon={Icons.Timer} variant="highlight">
        {inferenceProgress.isPending && <Text className={s.loadingText}>查询进度...</Text>}
        {inferenceProgress.isError && <ToneTag tone="error">查询失败</ToneTag>}
        {inferenceProgress.data &&
          (() => {
            const d = inferenceProgress.data
            const lp = d.live_progress
            const isRunning = d.request_state === 'running'
            return (
              <Space direction="vertical" className={s.container} size={4}>
                <Space wrap size={4}>
                  <ToneTag tone="info" className={`${s.jobTag} text-number font-mono`}>job: {d.job_id ?? activeJobId}</ToneTag>
                  <ToneTag tone={lp?.tone} label={lp?.label ?? d.status_category ?? d.request_state} />
                </Space>
                {lp?.percent != null && (
                  <CockpitProgress
                    percent={Math.round(lp.percent)}
                    variant={isRunning ? 'primary' : 'success'}
                    size={isRunning ? 'hero' : 'default'}
                    showAnimation={isRunning}
                    formatLabel={(p) => {
                      const done = lp.completed_count ?? 0
                      const total = lp.expected_count ?? 0
                      return total > 0 ? `${done}/${total}` : `${p}%`
                    }}
                  />
                )}
                {lp?.current_stage && (
                  <div className={s.stageRow}>
                    <Icons.Clock size={12} className={s.stageIcon} />
                    <Text className={s.stageText}>{lp.current_stage}</Text>
                  </div>
                )}
                {d.message && <Text className={s.messageText}>{d.message}</Text>}
              </Space>
            )
          })()}
        {Object.keys(mergedResults).length > 0 && (
          <div className={s.timelineWrapper}>
            <InferenceTimeline results={mergedResults as Record<string, any>} />
          </div>
        )}
      </PanelCard>
    )
  }

  // Completed inference — show until user starts a new run
  if (lastCompleted) {
    const lp = lastCompleted.live_progress
    const completedCount = lp?.completed_count ?? 0
    const expectedCount = lp?.expected_count ?? 0

    return (
      <PanelCard title="推理进度" icon={Icons.Timer} variant="highlight">
        <Space direction="vertical" className={s.container} size={4}>
          <div className={s.completedHeader}>
            <div className={s.completedBadge}>
              <Icons.CheckCircle size={16} className={s.completedIcon} />
              <span className={s.completedLabel}>推理完成</span>
            </div>
            <ToneTag tone="info" className={`${s.jobTag} text-number font-mono`}>
              job: {lastCompleted.job_id}
            </ToneTag>
          </div>

          <CockpitProgress
            percent={100}
            variant="success"
            size="hero"
            showAnimation={false}
            formatLabel={() => `${completedCount}/${expectedCount}`}
          />

          <Text className={s.completedSummary}>
            共完成 {completedCount} 张推理 {expectedCount > 0 && `/ ${expectedCount} 张`}
            {lastCompleted.message && ` — ${lastCompleted.message}`}
          </Text>

          <button
            className={s.dismissBtn}
            onClick={() => setLastCompletedInference(null)}
            aria-label="关闭完成提示"
          >
            关闭
          </button>
        </Space>

        {Object.keys(mergedResults).length > 0 && (
          <div className={s.timelineWrapper}>
            <InferenceTimeline results={mergedResults as Record<string, any>} />
          </div>
        )}
      </PanelCard>
    )
  }

  // No active or completed inference
  return (
    <PanelCard title="推理进度" icon={Icons.Timer} variant="highlight">
      <Text className={s.emptyText}>无活跃推理任务</Text>
    </PanelCard>
  )
}
