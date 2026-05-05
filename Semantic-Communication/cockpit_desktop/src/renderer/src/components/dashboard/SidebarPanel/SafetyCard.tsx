import { Descriptions, Button } from 'antd'
import { PanelCard } from '../../shared/PanelCard'
import { ToneTag } from '../../shared/ToneTag'
import { Icons } from '../../icons'
import { SkeletonCard } from '../../loading'
import { UseQueryResult } from '@tanstack/react-query'
import type { SystemStatusResponse } from '../../../api/types'

interface SafetyCardProps {
  system: UseQueryResult<SystemStatusResponse>
  onRecover: () => void
  recoverPending: boolean
}

export function SafetyCard({ system, onRecover, recoverPending }: SafetyCardProps) {
  const status = system.data
  const sp = status?.safety_panel

  return (
    <PanelCard title="安全面板" icon={Icons.Shield} variant="highlight">
      {system.isPending && <SkeletonCard lines={4} height={140} />}
      {system.isError && (
        <Descriptions column={1} size="small" styles={{ label: { color: 'var(--color-text-label)', width: 85, fontSize: 12 }, content: { fontSize: 12 } }}>
          <Descriptions.Item label="状态">
            <span style={{ color: 'var(--color-tone-error)', fontSize: 12 }}>
              {system.error instanceof Error ? system.error.message : '加载失败'}
            </span>
          </Descriptions.Item>
        </Descriptions>
      )}
      {sp && (
        <Descriptions column={1} size="small" styles={{ label: { color: 'var(--color-text-label)', width: 85, fontSize: 12 }, content: { fontSize: 12 } }}>
          <Descriptions.Item label="SAFE_STOP">
            <ToneTag tone={sp.safe_stop_tone} label={sp.safe_stop_state ?? '—'} />
          </Descriptions.Item>
          <Descriptions.Item label="Latch">
            <ToneTag tone={sp.latch_tone} label={sp.latch_state ?? '—'} />
          </Descriptions.Item>
          <Descriptions.Item label="guard_state">
            <ToneTag tone="neutral">{sp.guard_state ?? '—'}</ToneTag>
          </Descriptions.Item>
          <Descriptions.Item label="last_fault">
            <ToneTag tone={sp.last_fault_code && sp.last_fault_code !== 'NONE' ? 'warning' : 'neutral'}>
              {sp.last_fault_code ?? '—'}
            </ToneTag>
          </Descriptions.Item>
          <Descriptions.Item label="操作">
            <Button
              danger
              size="small"
              loading={recoverPending}
              onClick={onRecover}
              icon={<Icons.RefreshCw size={12} />}
            >
              收口
            </Button>
          </Descriptions.Item>
        </Descriptions>
      )}
    </PanelCard>
  )
}
