import type { ReactNode, CSSProperties } from 'react'
import { Tag } from 'antd'
import { T } from '../../theme/tokens'

function withAlpha(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r},${g},${b},${alpha})`
}

const TONE_MAP: Record<string, { color: string; bg: string; border: string }> = {
  online:   { color: T.toneOnline,  bg: withAlpha(T.toneOnline, 0.08),  border: withAlpha(T.toneOnline, 0.24) },
  success:  { color: T.toneSuccess,  bg: withAlpha(T.toneSuccess, 0.08), border: withAlpha(T.toneSuccess, 0.24) },
  degraded: { color: T.toneWarning,  bg: withAlpha(T.toneWarning, 0.08), border: withAlpha(T.toneWarning, 0.24) },
  warning:  { color: T.toneWarning,  bg: withAlpha(T.toneWarning, 0.08), border: withAlpha(T.toneWarning, 0.24) },
  offline:  { color: T.toneError,    bg: withAlpha(T.toneError, 0.08),   border: withAlpha(T.toneError, 0.24) },
  error:    { color: T.toneError,    bg: withAlpha(T.toneError, 0.08),   border: withAlpha(T.toneError, 0.24) },
  danger:   { color: T.toneError,    bg: withAlpha(T.toneError, 0.08),   border: withAlpha(T.toneError, 0.24) },
  neutral:  { color: T.toneNeutral,  bg: withAlpha(T.toneNeutral, 0.06), border: withAlpha(T.toneNeutral, 0.15) },
  idle:     { color: T.textLabel,    bg: withAlpha(T.textLabel, 0.06),   border: withAlpha(T.textLabel, 0.15) },
  info:     { color: T.accentBlue,   bg: withAlpha(T.accentBlue, 0.08),  border: withAlpha(T.accentBlue, 0.24) },
}

export interface ToneTagProps {
  tone?: string
  label?: string
  fallback?: string
  children?: ReactNode
  size?: 'sm' | 'md'
  dot?: boolean
  pulse?: boolean
  className?: string
}

export function ToneTag({
  tone,
  label,
  fallback,
  children,
  size = 'sm',
  dot = false,
  pulse = false,
  className,
}: ToneTagProps) {
  const key = (tone ?? '').toLowerCase()
  const mapped = TONE_MAP[key]
  const fs = size === 'sm' ? 11 : 12
  const padding = size === 'sm' ? '2px 10px' : '4px 12px'

  const baseStyle: CSSProperties = mapped
    ? { background: mapped.bg, color: mapped.color, border: `1px solid ${mapped.border}` }
    : { background: withAlpha(T.textLabel, 0.06), color: T.textLabel, border: `1px solid ${withAlpha(T.textLabel, 0.15)}` }

  const tagProps: Record<string, unknown> = {
    style: {
      ...baseStyle,
      borderRadius: T.radiusFull,
      padding,
      fontSize: fs,
      fontWeight: 500,
      margin: 0,
      lineHeight: '18px',
    },
    role: 'status',
    'aria-label': String(children ?? label ?? tone ?? fallback ?? '—'),
  }

  if (className) {
    tagProps.className = className
  }

  return (
    <Tag {...tagProps as any}>
      {dot && (
        <span
          className={['status-dot', pulse && 'status-pulse'].filter(Boolean).join(' ') || undefined}
          style={{
            display: 'inline-block',
            width: 6,
            height: 6,
            borderRadius: '50%',
            marginRight: 5,
            background: mapped?.color ?? T.textLabel,
          }}
          aria-hidden="true"
        />
      )}
      {children ?? label ?? tone ?? fallback ?? '—'}
    </Tag>
  )
}
