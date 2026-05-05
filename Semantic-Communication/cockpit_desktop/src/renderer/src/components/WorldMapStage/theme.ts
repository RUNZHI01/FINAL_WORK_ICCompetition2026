import { T } from '../../theme/tokens'

/** Cool slate map colours — refined Google/Tencent aesthetic */
export const mapTheme = {
  oceanTop: '#EDF1F7',
  oceanBottom: '#E2E8F0',
  landFill: '#D1D9E6',
  landFillBright: '#C4CFDE',
  coastline: '#B0BDCF',
  gridMajorEquator: `rgba(26, 86, 219, 0.08)`,
  gridMinorLat: 'rgba(26, 86, 219, 0.04)',
  gridMinorLon: 'rgba(26, 86, 219, 0.04)',
  frameStroke: 'rgba(26, 86, 219, 0.12)',
  trackLine: T.accentBlue,
  beamHighlight: 'rgba(26, 86, 219, 0.06)',
  beamMid: 'rgba(26, 86, 219, 0.02)',
  hazeHighlight: 'rgba(217, 119, 6, 0.04)',
  hazeMid: 'rgba(217, 119, 6, 0.01)',
  trackShadow: 'rgba(26, 86, 219, 0.10)',
  trackWash: '#F0F4F9',
  trackSpotlight: 'rgba(26, 86, 219, 0.04)',
  vignette: 'rgba(240, 244, 249, 0.10)',
  statusOnline: T.toneOnline,
  statusOffline: T.toneError,
} as const
