import { Space, Typography } from 'antd'
import { PanelCard } from '../../shared/PanelCard'
import { ToneTag } from '../../shared/ToneTag'
import { Icons } from '../../icons'
import { SkeletonCard } from '../../loading'
import { UseQueryResult } from '@tanstack/react-query'
import type { SystemStatusResponse } from '../../../api/types'

const { Paragraph } = Typography

interface ExecutionModeCardProps {
  system: UseQueryResult<SystemStatusResponse>
}

export function ExecutionModeCard({ system }: ExecutionModeCardProps) {
  const status = system.data

  return (
    <PanelCard title="执行模式" icon={Icons.Settings} variant="highlight">
      {system.isPending && <SkeletonCard lines={2} height={60} />}
      {system.isError && (
        <ToneTag tone="error">{system.error instanceof Error ? system.error.message : '加载失败'}</ToneTag>
      )}
      {status && (
        <>
          <Space wrap size={4} style={{ marginBottom: 6 }}>
            <ToneTag tone={status.execution_mode.tone} label={status.execution_mode.label} />
            <span className="text-number font-mono text-label">
              {status.generated_at}
            </span>
          </Space>
          <Paragraph className="text-secondary" style={{ marginBottom: 0, lineHeight: 1.5 }}>
            {status.execution_mode.summary}
          </Paragraph>
        </>
      )}
    </PanelCard>
  )
}
