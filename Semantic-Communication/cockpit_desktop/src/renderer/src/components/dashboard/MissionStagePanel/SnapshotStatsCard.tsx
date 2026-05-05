import { Statistic, Tag, Space } from 'antd'
import { PanelCard } from '../../shared/PanelCard'
import { PerformanceGauge } from '../../charts/PerformanceGauge'
import { Icons } from '../../icons'
import { SkeletonCard } from '../../loading'
import { CountUp } from '../../shared/CountUp'

function formatMs(value: number | undefined | null): string {
  if (value === undefined || value === null || Number.isNaN(value)) return '—'
  return `${Number(value).toFixed(2)} ms`
}

interface SnapshotStatsCardProps {
  snapshot: any
}

export function SnapshotStatsCard({ snapshot }: SnapshotStatsCardProps) {
  const snap = snapshot.data

  return (
    <PanelCard title="证据包快照" icon={Icons.BarChart} variant="glass">
      {snapshot.isPending && <SkeletonCard lines={2} height={140} />}
      {snapshot.isError && (
        <Tag color="error" className="text-caption">{snapshot.error instanceof Error ? snapshot.error.message : '加载失败'}</Tag>
      )}
      {snap && (
        <>
          <Space style={{ display: 'flex', gap: 'var(--space-lg, 24px)', flexWrap: 'wrap', marginBottom: 6 }}>
            <Statistic
              title={<span className="text-caption">Payload current</span>}
              valueStyle={{ color: 'var(--color-text-accent)', fontSize: 16 }}
              value={snap.stats.payload_current_ms ?? 0}
              formatter={((value: number) => (
                <CountUp
                  end={Number(value) ?? 0}
                  decimals={2}
                  formatValue={(v) => formatMs(v)}
                />
              )) as any}
            />
            <Statistic
              title={<span className="text-caption">E2E current</span>}
              valueStyle={{ color: 'var(--color-text-accent)', fontSize: 16 }}
              value={snap.stats.end_to_end_current_ms ?? 0}
              formatter={((value: number) => (
                <CountUp
                  end={Number(value) ?? 0}
                  decimals={2}
                  formatValue={(v) => formatMs(v)}
                />
              )) as any}
            />
            <Statistic
              title={<span className="text-caption">P0 / FIT</span>}
              valueStyle={{ color: 'var(--color-text-highlight)', fontSize: 16 }}
              value={0}
              formatter={() => (
                <span className="text-number font-mono">
                  {snap.stats.p0_milestones_verified ?? '—'} / {snap.stats.fit_final_pass_count ?? '—'}
                </span>
              )}
            />
          </Space>
          <PerformanceGauge
            payloadMs={snap.stats.payload_current_ms ?? undefined}
            e2eMs={snap.stats.end_to_end_current_ms ?? undefined}
          />
        </>
      )}
    </PanelCard>
  )
}
