import type { ReactNode } from 'react'
import s from './EmptyState.module.css'

interface EmptyStateProps {
  icon?: ReactNode
  title: string
  description?: string
  action?: ReactNode
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className={s.container}>
      <div className={s.iconWrapper}>
        {icon ?? '—'}
      </div>
      <div className={s.title}>
        {title}
      </div>
      {description && (
        <div className={s.description}>
          {description}
        </div>
      )}
      {action && <div className={s.actionWrapper}>{action}</div>}
    </div>
  )
}
