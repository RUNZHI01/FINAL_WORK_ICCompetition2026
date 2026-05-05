import type { ReactNode, ComponentType } from 'react'
import { ProCard } from '@ant-design/pro-components'
import { T } from '../../theme/tokens'
import s from './PanelCard.module.css'

export type PanelCardVariant = 'default' | 'highlight' | 'glass'

type LucideIcon = ComponentType<{ size?: number | string; className?: string; style?: React.CSSProperties }>

export interface PanelCardProps {
  title?: ReactNode
  icon?: LucideIcon
  extra?: ReactNode
  children: ReactNode
  variant?: PanelCardVariant
  style?: React.CSSProperties
  bodyStyle?: React.CSSProperties
  collapsible?: boolean
  defaultCollapsed?: boolean
  'aria-label'?: string
}

const variantStyle: Record<PanelCardVariant, React.CSSProperties> = {
  default: {
    background: T.bgCard,
    borderRadius: T.radiusMd,
    border: `1px solid ${T.borderLight}`,
    boxShadow: T.elevation1,
    transition: `all ${T.durationNormal}ms ${T.easeStandard}`,
  },
  highlight: {
    background: T.bgCard,
    borderRadius: T.radiusMd,
    border: `1px solid ${T.borderBase}`,
    borderLeft: `3px solid ${T.accentBlue}`,
    boxShadow: T.elevation1,
    transition: `all ${T.durationNormal}ms ${T.easeStandard}`,
  },
  glass: {
    background: T.glassBg,
    borderRadius: T.radiusMd,
    border: `1px solid ${T.glassBorder}`,
    boxShadow: T.elevation2,
    transition: `all ${T.durationNormal}ms ${T.easeStandard}`,
  },
}

export function PanelCard({
  title,
  icon: Icon,
  extra,
  children,
  variant = 'default',
  style,
  bodyStyle,
  collapsible,
  defaultCollapsed,
  'aria-label': ariaLabel,
}: PanelCardProps) {
  const renderedTitle = Icon && typeof title === 'string'
    ? (
      <div className={s.titleGroup}>
        <Icon size={14} className={s.titleIcon} aria-hidden="true" />
        <span>{title}</span>
      </div>
    )
    : title

  return (
    <ProCard
      title={renderedTitle}
      extra={extra}
      bordered={false}
      collapsible={collapsible}
      defaultCollapsed={defaultCollapsed}
      style={{
        ...variantStyle[variant],
        ...style,
      }}
      headStyle={{
        borderBottom: `1px solid ${T.borderLight}`,
        color: T.textPrimary,
        fontSize: T.fontSizeLg,
        fontWeight: T.fontWeightMedium,
        minHeight: 40,
        paddingLeft: 16,
        paddingRight: 16,
        paddingTop: 12,
        paddingBottom: 12,
        letterSpacing: T.letterSpacingNormal,
      }}
      bodyStyle={{
        padding: 16,
        ...bodyStyle,
      }}
      aria-label={ariaLabel || (typeof title === 'string' ? title : undefined)}
      role="region"
    >
      {children}
    </ProCard>
  )
}
