import { Table, Typography } from 'antd'
import { PanelCard } from '../../shared/PanelCard'
import { Icons } from '../../icons'
import { SkeletonCard } from '../../loading'
import { UseQueryResult } from '@tanstack/react-query'
import type { SystemStatusResponse } from '../../../api/types'
import { useAppStore } from '../../../stores/appStore'
import s from './ComparisonCard.module.css'

const { Text } = Typography

interface ComparisonCardProps {
  system: UseQueryResult<SystemStatusResponse>
}

export function ComparisonCard({ system }: ComparisonCardProps) {
  const status = system.data
  const results = status?.recent_results
  const lastCompletedInference = useAppStore((s) => s.lastCompletedInference)
  const currentFromStatus = results?.['current']
  const current = (
    lastCompletedInference?.variant === 'current'
    && lastCompletedInference?.execution_mode === 'live'
    && lastCompletedInference?.status === 'success'
  ) ? lastCompletedInference : currentFromStatus
  const baseline = results?.['baseline']

  if (system.isPending) {
    return (
      <PanelCard title="Current vs Baseline" icon={Icons.TrendingUp}>
        <SkeletonCard lines={4} height={160} />
      </PanelCard>
    )
  }

  if (system.isError) {
    return (
      <PanelCard title="Current vs Baseline" icon={Icons.TrendingUp}>
        <Text className={s.emptyText}>
          {system.error instanceof Error ? system.error.message : '加载失败'}
        </Text>
      </PanelCard>
    )
  }

  if (!current || !baseline) {
    return (
      <PanelCard title="Current vs Baseline" icon={Icons.TrendingUp}>
        <Text className={s.emptyText}>需要同时存在 current 和 baseline 结果</Text>
      </PanelCard>
    )
  }

  const dataSource = [
    { key: 'payload_ms', metric: 'Payload (ms)', current: current.timings?.payload_ms, baseline: baseline.timings?.payload_ms },
    { key: 'total_ms', metric: 'Total (ms)', current: current.timings?.total_ms, baseline: baseline.timings?.total_ms },
    { key: 'psnr', metric: 'PSNR (dB)', current: current.quality?.psnr_db, baseline: baseline.quality?.psnr_db },
    { key: 'ssim', metric: 'SSIM', current: current.quality?.ssim, baseline: baseline.quality?.ssim },
  ]

  return (
    <PanelCard title="性能对比" icon={Icons.TrendingUp}>
      <Table
        dataSource={dataSource}
        pagination={false}
        size="small"
        rowKey="key"
        columns={[
          {
            title: '指标',
            dataIndex: 'metric',
            key: 'metric',
            width: 110,
            render: (v: string) => <span style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>{v}</span>,
          },
          {
            title: 'Current',
            dataIndex: 'current',
            key: 'current',
            width: 90,
            align: 'right',
            render: (v: number | null | undefined) => (
              <span className="text-number font-mono" style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-text-primary)' }}>
                {v != null ? v.toFixed(2) : '—'}
              </span>
            ),
          },
          {
            title: 'Baseline',
            dataIndex: 'baseline',
            key: 'baseline',
            width: 90,
            align: 'right',
            render: (v: number | null | undefined) => (
              <span className="text-number font-mono" style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>
                {v != null ? v.toFixed(2) : '—'}
              </span>
            ),
          },
        ]}
      />
    </PanelCard>
  )
}
