import { Space, Typography } from 'antd'
import { PanelCard } from '../../shared/PanelCard'
import { ToneTag } from '../../shared/ToneTag'
import { Icons } from '../../icons'
import { SkeletonCard } from '../../loading'
import { UseQueryResult } from '@tanstack/react-query'
import type { SystemStatusResponse } from '../../../api/types'
import s from './JobManifestCard.module.css'

const { Text, Paragraph } = Typography

interface JobManifestCardProps {
  system: UseQueryResult<SystemStatusResponse>
}

export function JobManifestCard({ system }: JobManifestCardProps) {
  const status = system.data
  const gate = status?.job_manifest_gate

  return (
    <PanelCard title="任务票闸机" icon={Icons.CheckCircle}>
      {system.isPending && <SkeletonCard lines={3} height={120} />}
      {system.isError && (
        <Text className={s.emptyText}>
          {system.error instanceof Error ? system.error.message : '加载失败'}
        </Text>
      )}
      {gate && (
        <>
          <Space wrap size={4} className={s.verdictGroup}>
            {gate.verdict != null ? (
              <div className={s.verdictItem}>
                <span className={`status-dot ${gate.verdict === 'allow' ? 'status-online' : 'status-warning'}`} />
                <ToneTag tone={gate.verdict === 'allow' ? 'success' : 'warning'}>
                  {gate.verdict_label ? `${gate.verdict_label} (${gate.verdict})` : String(gate.verdict)}
                </ToneTag>
              </div>
            ) : (
              <ToneTag tone="neutral">—</ToneTag>
            )}
            {gate.tone && <ToneTag tone={gate.tone} label={gate.status} />}
          </Space>
          {gate.message && (
            <Paragraph className={s.messageText}>
              {gate.message}
            </Paragraph>
          )}
          {gate.reasons && gate.reasons.length > 0 && (
            <ul className={s.reasonsList}>
              {gate.reasons.map((r: string, i: number) => (
                <li key={i}>
                  <Text className={s.reasonItem}>{r}</Text>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </PanelCard>
  )
}
