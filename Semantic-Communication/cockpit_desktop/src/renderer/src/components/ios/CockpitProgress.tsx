import React from 'react'
import { Progress as AntProgress } from 'antd'
import { T } from '../../theme/tokens'

export interface CockpitProgressProps {
  percent?: number
  variant?: 'primary' | 'success' | 'warning' | 'danger'
  showAnimation?: boolean
  /** 'default' = thin bar (4px). 'hero' = big, glowing bar with percentage label (14px). */
  size?: 'default' | 'hero'
  style?: React.CSSProperties
  /** Override label shown on the right of hero bar. Default: "{percent}%" */
  formatLabel?: (percent: number) => string
}

const VARIANT_COLORS: Record<string, { from: string; to: string }> = {
  primary: { from: T.accentBlue, to: T.accentCyan },
  success: { from: T.toneSuccess, to: T.accentTeal },
  warning: { from: T.toneWarning, to: T.toneError },
  danger:  { from: T.toneError, to: T.toneError },
}

export const CockpitProgress: React.FC<CockpitProgressProps> = ({
  percent,
  variant = 'primary',
  showAnimation = true,
  size = 'default',
  style,
  formatLabel,
}) => {
  const colors = VARIANT_COLORS[variant] ?? VARIANT_COLORS.primary
  const isHero = size === 'hero'

  const gradientStroke = {
    '0%': colors.from,
    '100%': colors.to,
  }

  return (
    <div
      style={{
        position: 'relative',
        ...(isHero && {
          background: `linear-gradient(135deg, ${T.bgSection}, ${T.glassBg})`,
          borderRadius: T.radiusMd,
          padding: '12px 16px',
          boxShadow: `inset 0 0 0 1px ${T.borderLight}`,
        }),
        ...style,
      }}
    >
      {isHero && percent != null && (
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'baseline',
            marginBottom: 8,
          }}
        >
          <span
            style={{
              fontSize: T.fontSizeSm,
              fontWeight: T.fontWeightMedium,
              color: T.textSecondary,
              letterSpacing: T.letterSpacingWide,
            }}
          >
            {variant === 'success' ? '推理完成' : '推理中'}
          </span>
          <span
            className="font-mono text-number"
            style={{
              fontSize: T.fontSizeXl,
              fontWeight: T.fontWeightBold,
              background: `linear-gradient(135deg, ${colors.from}, ${colors.to})`,
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              letterSpacing: T.letterSpacingTight,
            }}
          >
            {formatLabel ? formatLabel(Math.round(percent)) : `${Math.round(percent)}%`}
          </span>
        </div>
      )}

      <AntProgress
        percent={percent}
        strokeColor={gradientStroke}
        trailColor={T.bgSection}
        strokeWidth={isHero ? 14 : 4}
        showInfo={false}
        strokeLinecap="round"
        className={showAnimation ? 'progress-animated' : undefined}
        style={isHero ? { filter: `drop-shadow(0 0 6px ${colors.from}40)` } : undefined}
      />

      {isHero && (
        <div
          style={{
            height: 2,
            marginTop: 4,
            borderRadius: 1,
            background: `linear-gradient(90deg, ${colors.from}00, ${colors.from}30, ${colors.to}30, ${colors.to}00)`,
            opacity: 0.6,
          }}
        />
      )}
    </div>
  )
}
