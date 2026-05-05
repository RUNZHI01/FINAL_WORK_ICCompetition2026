import { T } from './tokens'

/**
 * Injects design tokens as CSS custom properties on :root.
 * Called once at app startup.  Bridges tokens.ts → CSS var(--xxx).
 */
export function injectCSSVariables() {
  const root = document.documentElement.style

  /* Font families */
  root.setProperty('--font-family-base',
    "'Inter Variable', 'Noto Sans SC', system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
  )
  root.setProperty('--font-family-mono',
    "'Geist Mono', 'JetBrains Mono', 'Consolas', 'Monaco', 'Courier New', monospace"
  )

  /* Backgrounds */
  root.setProperty('--color-bg-primary', T.bgPrimary)
  root.setProperty('--color-bg-card', T.bgCard)
  root.setProperty('--color-bg-card-hover', T.bgCardHover)
  root.setProperty('--color-bg-header', T.bgHeader)
  root.setProperty('--color-bg-overlay', T.bgOverlay)
  root.setProperty('--color-bg-glass', T.glassBg)
  root.setProperty('--color-bg-glass-strong', 'rgba(255,255,255,0.92)')
  root.setProperty('--color-bg-glass-intense', 'rgba(255,255,255,0.95)')

  /* Section background */
  root.setProperty('--color-bg-section', T.bgSection)

  /* Hover state backgrounds */
  root.setProperty('--color-bg-primary-hover', 'rgba(26, 86, 219, 0.06)')
  root.setProperty('--color-bg-error-hover', 'rgba(220, 38, 38, 0.06)')

  /* Hover state for primary buttons */
  root.setProperty('--color-primary-hover', '#1444B0')

  /* MD3 surface variables */
  root.setProperty('--color-surface-base', T.surface.base)
  root.setProperty('--color-surface-base-low', T.surface.baseLow)
  root.setProperty('--color-surface-container', T.surface.container)
  root.setProperty('--color-surface-container-low', T.surface.containerLow)
  root.setProperty('--color-surface-variant', T.surface.variant)

  /* Borders */
  root.setProperty('--color-border-base', T.borderBase)
  root.setProperty('--color-border-light', T.borderLight)
  root.setProperty('--color-border-accent', T.borderAccent)
  root.setProperty('--color-border-glow', T.borderGlow)

  /* Text */
  root.setProperty('--color-text-primary', T.textPrimary)
  root.setProperty('--color-text-secondary', T.textSecondary)
  root.setProperty('--color-text-tertiary', T.textLabel)
  root.setProperty('--color-text-label', T.textLabel)
  root.setProperty('--color-text-accent', T.textAccent)
  root.setProperty('--color-text-highlight', T.textHighlight)
  root.setProperty('--color-text-muted', T.textMuted)

  /* Semantic tones */
  root.setProperty('--color-tone-online', T.toneOnline)
  root.setProperty('--color-tone-warning', T.toneWarning)
  root.setProperty('--color-tone-error', T.toneError)
  root.setProperty('--color-tone-success', T.toneSuccess)
  root.setProperty('--color-tone-neutral', T.toneNeutral)

  /* MD3 primary / error containers */
  root.setProperty('--color-primary', T.primary.main)
  root.setProperty('--color-primary-on', T.primary.onMain)
  root.setProperty('--color-primary-container', T.primary.container)
  root.setProperty('--color-primary-on-container', T.primary.onContainer)

  root.setProperty('--color-secondary', T.secondary.main)
  root.setProperty('--color-secondary-container', T.secondary.container)

  root.setProperty('--color-tertiary', T.tertiary.main)

  root.setProperty('--color-error', T.error.main)
  root.setProperty('--color-error-container', T.error.container)

  root.setProperty('--color-success', T.success)
  root.setProperty('--color-success-container', T.successContainer)
  root.setProperty('--color-warning', T.warning)
  root.setProperty('--color-warning-container', T.warningContainer)
  root.setProperty('--color-info', T.info)
  root.setProperty('--color-info-container', T.infoContainer)

  /* Accent palette */
  root.setProperty('--color-accent-cyan', T.accentCyan)
  root.setProperty('--color-accent-blue', T.accentBlue)
  root.setProperty('--color-accent-indigo', T.accentIndigo)
  root.setProperty('--color-accent-teal', T.accentTeal)

  /* Glow (kept for chart shadows) */
  root.setProperty('--glow-cyan', T.glowCyan)
  root.setProperty('--glow-blue', T.glowBlue)
  root.setProperty('--glow-green', T.glowGreen)
  root.setProperty('--glow-red', T.glowRed)
  root.setProperty('--glow-orange', T.glowOrange)
  root.setProperty('--glow-purple', T.glowPurple)

  /* Spacing */
  root.setProperty('--space-xs', `${T.gapXs}px`)
  root.setProperty('--space-sm', `${T.gapSm}px`)
  root.setProperty('--space-md', `${T.gapMd}px`)
  root.setProperty('--space-lg', `${T.gapLg}px`)
  root.setProperty('--space-xl', `${T.gapXl}px`)
  root.setProperty('--space-2xl', `${T.gap2xl}px`)

  /* Radius */
  root.setProperty('--radius-xs', '4px')
  root.setProperty('--radius-sm', `${T.radiusSm}px`)
  root.setProperty('--radius-md', `${T.radiusMd}px`)
  root.setProperty('--radius-lg', `${T.radiusLg}px`)
  root.setProperty('--radius-xl', `${T.radiusXl}px`)
  root.setProperty('--radius-full', `${T.radiusFull}px`)

  /* Shadows / Elevation */
  root.setProperty('--elevation-0', T.elevation0)
  root.setProperty('--elevation-1', T.elevation1)
  root.setProperty('--elevation-2', T.elevation2)
  root.setProperty('--elevation-3', T.elevation3)
  root.setProperty('--elevation-4', T.elevation4)
  root.setProperty('--shadow-card', T.glassShadow)
  root.setProperty('--shadow-glow', `0 0 20px ${T.glowBlue}`)

  /* Transitions */
  root.setProperty('--transition-fast', `${T.durationFast}ms ${T.easeStandard}`)
  root.setProperty('--transition-normal', `${T.durationNormal}ms ${T.easeStandard}`)
  root.setProperty('--easing-standard', T.easeStandard)
  root.setProperty('--easing-emphasized', T.easeSpring)
}
