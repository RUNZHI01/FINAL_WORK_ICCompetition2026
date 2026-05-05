import { Descriptions, Tag } from 'antd'
import { PanelCard } from '../../shared/PanelCard'
import { Icons } from '../../icons'
import { SkeletonCard } from '../../loading'

interface TelemetryCardProps {
  aircraft: any
}

export function TelemetryCard({ aircraft }: TelemetryCardProps) {
  const ap = aircraft.data

  const descStyle = { label: { color: 'var(--color-text-tertiary)', width: 60 }, content: {} }

  return (
    <PanelCard
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Icons.Activity size={14} style={{ color: 'var(--color-primary)' }} />
          <span>飞机遥测</span>
        </div>
      }
    >
      {aircraft.isPending && <SkeletonCard lines={6} height={120} />}
      {aircraft.isError && (
        <Tag color="error">{aircraft.error instanceof Error ? aircraft.error.message : '加载失败'}</Tag>
      )}
      {ap && (
        <Descriptions column={1} size="small" styles={descStyle}>
          <Descriptions.Item label="源">
            <Tag>{String(ap.source_kind ?? '—')}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="状态">
            <Tag>{String(ap.source_status ?? '—')}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="经纬">
            <span className="text-number font-mono text-caption" style={{ color: 'var(--color-text-secondary)' }}>
              {ap.position?.latitude != null && ap.position?.longitude != null
                ? `${ap.position.latitude.toFixed(4)}, ${ap.position.longitude.toFixed(4)}`
                : '—'}
            </span>
          </Descriptions.Item>
          <Descriptions.Item label="航向">
            <span className="text-number font-mono text-caption" style={{ color: 'var(--color-text-secondary)' }}>
              {ap.kinematics?.heading_deg != null
                ? `${Number(ap.kinematics.heading_deg).toFixed(1)}°`
                : '—'}
            </span>
          </Descriptions.Item>
          <Descriptions.Item label="高度">
            <span className="text-number font-mono text-caption" style={{ color: 'var(--color-text-secondary)' }}>
              {ap.kinematics?.altitude_m != null
                ? `${Number(ap.kinematics.altitude_m).toFixed(1)} m`
                : '—'}
            </span>
          </Descriptions.Item>
          <Descriptions.Item label="速度">
            <span className="text-number font-mono text-caption" style={{ color: 'var(--color-text-secondary)' }}>
              {ap.kinematics?.ground_speed_kph != null
                ? `${Number(ap.kinematics.ground_speed_kph).toFixed(1)} kph`
                : '—'}
            </span>
          </Descriptions.Item>
        </Descriptions>
      )}
    </PanelCard>
  )
}
