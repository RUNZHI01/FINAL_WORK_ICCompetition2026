import { Typography, Steps } from 'antd'
import { PanelCard } from '../../shared/PanelCard'
import { ToneTag } from '../../shared/ToneTag'
import { Icons } from '../../icons'
import { SkeletonCard } from '../../loading'
import { UseQueryResult } from '@tanstack/react-query'
import type { SystemStatusResponse } from '../../../api/types'
import s from './OperatorCueCard.module.css'

const { Text, Paragraph } = Typography

interface OperatorCueCardProps {
  system: UseQueryResult<SystemStatusResponse>
}

export function OperatorCueCard({ system }: OperatorCueCardProps) {
  const status = system.data
  const oc = status?.operator_cue

  return (
    <PanelCard title="操作员引导" icon={Icons.User} variant="glass">
      {system.isPending && <SkeletonCard lines={3} height={140} />}
      {system.isError && (
        <Text className={s.emptyText}>
          {system.error instanceof Error ? system.error.message : '加载失败'}
        </Text>
      )}
      {oc && oc.scenes && oc.scenes.length > 0 && (
        <>
          <Steps
            direction="vertical"
            size="small"
            current={oc.scenes.findIndex((s: any) => s.recommended) ?? -1}
            items={oc.scenes.map((scene: any) => ({
              title: (
                <span className={s.cueHeader}>
                  {scene.title}
                  <ToneTag tone={scene.tone} label={scene.status} fallback="default" />
                </span>
              ),
              description: scene.cue_line ? (
                <Text className={s.cueMessage}>{scene.cue_line}</Text>
              ) : undefined,
            }))}
          />
          {oc.presenter_line && (
            <div className={s.cueItem}>
              <Icons.MessageSquare size={12} style={{ color: 'var(--color-text-accent)', marginTop: 1 }} />
              <Paragraph style={{ color: 'var(--color-text-accent)', marginTop: 0, marginBottom: 0, fontSize: 13, lineHeight: 1.5 }}>
                {oc.presenter_line}
              </Paragraph>
            </div>
          )}
        </>
      )}
    </PanelCard>
  )
}
