/**
 * Cockpit Design Tokens — Premium Tech Dashboard.
 *
 * Inspired by:
 *   - Google Material Design 3 Expressive (2025–2026)
 *   - Google Cloud Console 2026
 *   - Tencent TDesign 2026
 *   - Tencent Cloud Console
 *
 * Aesthetic: Cool slate surfaces, vibrant blue primary,
 * refined shadows, premium data visualization palette.
 *
 * Single source of truth.  CSS modules consume via var(--xxx);
 * TS components import { T } directly.
 */
export const T = {

  /* ── Backgrounds — cool slate, not warm beige ── */
  bgPrimary:     '#F0F4F9',   // page background — cool slate-mist (Google Cloud)
  bgCard:        '#FFFFFF',   // card surface — pure white
  bgCardHover:   '#F8FAFC',   // card hover state
  bgHeader:      '#FFFFFF',   // header bar — white, border-separated
  bgSection:     '#E8EDF3',   // section divider bg — cool stone
  bgOverlay:     'rgba(15,23,42,0.5)',

  /* ── Borders — refined cool borders ── */
  borderBase:    '#D1D9E6',   // visible separator
  borderLight:   '#E8EDF3',   // soft divider
  borderAccent:  '#1A56DB',   // blue accent border
  borderGlow:    'rgba(26,86,219,0.12)',

  /* ── Text — cool slate tones ── */
  textPrimary:   '#0F172A',   // primary text — slate-900
  textSecondary: '#475569',   // secondary — slate-600
  textLabel:     '#94A3B8',   // labels — slate-400
  textAccent:    '#1A56DB',   // links / interactive — deep blue
  textHighlight: '#1A56DB',   // highlighted interactive text
  textMuted:     '#CBD5E1',   // muted/disabled text — slate-300

  /* ── Semantic tone colours ── */
  toneOnline:    '#059669',   // emerald-600
  toneWarning:   '#D97706',   // amber-600
  toneError:     '#DC2626',   // red-600
  toneSuccess:   '#059669',
  toneNeutral:   '#475569',

  /* ── Accent palette — saturated on cool bg ── */
  accentBlue:    '#1A56DB',   // primary interactive — Google-inspired deep blue
  accentCyan:    '#0891B2',   // cyan-600 — charts
  accentIndigo:  '#6366F1',   // indigo-500 — charts
  accentTeal:    '#0D9488',   // teal-600 — charts

  /* ── Glow colours — subtle ── */
  glowCyan:      'rgba(8,145,178,0.08)',
  glowBlue:      'rgba(26,86,219,0.08)',
  glowGreen:     'rgba(5,150,105,0.08)',
  glowRed:       'rgba(220,38,38,0.08)',
  glowOrange:    'rgba(217,119,6,0.08)',
  glowPurple:    'rgba(99,102,241,0.08)',

  /* ── Glass — frosted effect ── */
  glassBg:       'rgba(255,255,255,0.82)',
  glassBorder:   'rgba(209,217,230,0.50)',
  glassShadow:   '0 2px 12px rgba(15,23,42,0.06), 0 1px 3px rgba(15,23,42,0.04)',

  /* ── Spacing (8 px base grid) ── */
  gapXs:   4,
  gapSm:   8,
  gapMd:   16,
  gapLg:   24,
  gapXl:   32,
  gap2xl:  48,

  /* ── Border Radius — MD3 Expressive graduated curvatures ── */
  radiusSm:    8,
  radiusMd:    12,
  radiusLg:    16,
  radiusXl:    24,
  radiusFull:  9999,

  /* ── Typography ── */
  fontSizeXs:      11,
  fontSizeSm:      12,
  fontSizeMd:      13,
  fontSizeBase:    14,
  fontSizeLg:      16,
  fontSizeXl:      20,
  fontSize2xl:     24,
  fontSize3xl:     32,

  fontWeightNormal:    400,
  fontWeightMedium:    500,
  fontWeightSemibold:  600,
  fontWeightBold:      700,

  letterSpacingTight:  '-0.25px',
  letterSpacingNormal: '0.01em',
  letterSpacingWide:   '0.05em',

  /* ── Elevation — cool-tinted, more refined ── */
  elevation0: 'none',
  elevation1: '0 1px 2px rgba(15,23,42,0.04), 0 1px 3px rgba(15,23,42,0.06)',
  elevation2: '0 4px 6px rgba(15,23,42,0.04), 0 2px 4px rgba(15,23,42,0.06)',
  elevation3: '0 12px 24px rgba(15,23,42,0.06), 0 4px 8px rgba(15,23,42,0.04)',
  elevation4: '0 20px 40px rgba(15,23,42,0.08), 0 8px 16px rgba(15,23,42,0.04)',

  /* ── Motion ── */
  durationFast:   150,
  durationNormal: 250,
  durationSlow:   350,

  easeStandard:  'cubic-bezier(0.2, 0.0, 0, 1.0)',
  easeSpring:    'cubic-bezier(0.175, 0.885, 0.32, 1.05)',

  /* ── MD3 colour system (cool light variants) ── */
  primary: {
    main: '#1A56DB',         // deep blue — Google-inspired
    onMain: '#FFFFFF',
    container: '#EBF0FE',    // light blue bg
    onContainer: '#1E3A8A',  // blue-900
  },
  secondary: {
    main: '#475569',         // slate-600
    onMain: '#FFFFFF',
    container: '#F1F5F9',    // slate-100
    onContainer: '#1E293B',  // slate-800
  },
  tertiary: {
    main: '#0D9488',         // teal-600
    onMain: '#FFFFFF',
    container: '#F0FDFA',    // teal-50
    onContainer: '#115E59',  // teal-800
  },
  error: {
    main: '#DC2626',         // red-600
    onMain: '#FFFFFF',
    container: '#FEF2F2',    // red-50
    onContainer: '#991B1B',  // red-800
  },
  surface: {
    base: '#F0F4F9',
    baseLow: '#F8FAFC',
    container: '#FFFFFF',
    containerLow: '#F8FAFC',
    variant: '#E2E8F0',
    onBase: '#0F172A',
    onVariant: '#475569',
    onSurface: '#94A3B8',
  },
  success: '#059669',
  successContainer: '#ECFDF5',
  warning: '#D97706',
  warningContainer: '#FFFBEB',
  info: '#1A56DB',
  infoContainer: '#EBF0FE',
} as const
