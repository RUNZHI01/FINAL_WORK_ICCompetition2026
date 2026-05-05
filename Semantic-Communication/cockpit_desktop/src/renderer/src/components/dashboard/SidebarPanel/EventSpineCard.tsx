import { Space, Typography } from 'antd'
import { PanelCard } from '../../shared/PanelCard'
import { ToneTag } from '../../shared/ToneTag'
import { Icons } from '../../icons'
import { SkeletonCard } from '../../loading'
import { UseQueryResult } from '@tanstack/react-query'
import type { SystemStatusResponse } from '../../../api/types'
import s from './EventSpineCard.module.css'

const { Text } = Typography

interface EventSpineCardProps {
  system: UseQueryResult<SystemStatusResponse>
}

export function EventSpineCard({ system }: EventSpineCardProps) {
  const status = system.data
  const es = status?.event_spine

  return (
    <PanelCard title="事件脊" icon={Icons.Zap}>
      {system.isPending && <SkeletonCard lines={1} height={60} />}
      {system.isError && (
        <Text className={s.emptyText}>
          {system.error instanceof Error ? system.error.message : '加载失败'}
        </Text>
      )}
      {es && (
        <Space wrap size={6} className={s.infoGroup}>
          <ToneTag tone="neutral" className="text-number font-mono">{es.session_id ?? '—'}</ToneTag>
          <div className={s.statItem}>
            <Icons.Database size={12} className={s.statIcon} />
            <Text className="text-number font-mono statText">
              {es.event_count ?? 0} events
            </Text>
          </div>
        </Space>
      )}
    </PanelCard>
  )
}
