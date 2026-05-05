import type { Projection } from './projection'
import { mapTheme } from './theme'

export type TrackPoint = {
  longitude: number
  latitude: number
  age_sec?: number
}

export type TrackLayerParams = {
  ctx: CanvasRenderingContext2D
  cssWidth: number
  cssHeight: number
  proj: Projection
  trackData: TrackPoint[]
  headingDeg: number
  landingMode: boolean
}

export function drawTrackLayer(p: TrackLayerParams): void {
  const { ctx, cssWidth: w, cssHeight: h, proj, trackData, headingDeg, landingMode } = p
  const { mapInset } = proj

  const hasCurrentPoint =
    trackData.length > 0 &&
    Number.isFinite(trackData[trackData.length - 1]!.longitude) &&
    Number.isFinite(trackData[trackData.length - 1]!.latitude)

  if (hasCurrentPoint) {
    const last = trackData[trackData.length - 1]!
    const mx = proj.projectX(last.longitude)
    const my = proj.projectY(last.latitude)
    const spotlightRadius = Math.max(1, Math.min(w, h) * 0.38)
    const spotlight = ctx.createRadialGradient(mx, my, 0, mx, my, spotlightRadius)
    spotlight.addColorStop(0.0, mapTheme.trackSpotlight)
    spotlight.addColorStop(0.3, 'rgba(26,86,219,0.04)')
    spotlight.addColorStop(1.0, 'rgba(26,86,219,0.0)')
    ctx.fillStyle = spotlight
    ctx.fillRect(0, 0, w, h)
  }

  ctx.save()
  ctx.beginPath()
  ctx.rect(mapInset, mapInset, proj.plotWidth, proj.plotHeight)
  ctx.clip()

  drawTrack(ctx, proj, trackData, headingDeg, landingMode)
  ctx.restore()
}

function drawTrack(
  ctx: CanvasRenderingContext2D,
  proj: Projection,
  trackData: TrackPoint[],
  headingDeg: number,
  landingMode: boolean,
): void {
  if (!trackData.length) {
    return
  }

  ctx.save()
  ctx.lineJoin = 'round'
  ctx.lineCap = 'round'

  if (trackData.length > 1) {
    const shadowWidth = landingMode ? 8.4 : 7.2
    const washWidth = landingMode ? 4.8 : 4.2
    const trackWidth = landingMode ? 3.1 : 2.6
    const segCount = trackData.length - 1

    for (let seg = 0; seg < segCount; seg++) {
      const segAlpha = 0.15 + 0.85 * (seg / segCount)
      const p0 = trackData[seg]!
      const p1 = trackData[seg + 1]!
      const sx0 = proj.projectX(p0.longitude)
      const sy0 = proj.projectY(p0.latitude)
      const sx1 = proj.projectX(p1.longitude)
      const sy1 = proj.projectY(p1.latitude)

      ctx.globalAlpha = segAlpha * 0.5
      ctx.beginPath()
      ctx.moveTo(sx0, sy0)
      ctx.lineTo(sx1, sy1)
      ctx.strokeStyle = mapTheme.trackShadow
      ctx.lineWidth = shadowWidth
      ctx.stroke()

      ctx.globalAlpha = segAlpha * 0.3
      ctx.beginPath()
      ctx.moveTo(sx0, sy0)
      ctx.lineTo(sx1, sy1)
      ctx.strokeStyle = mapTheme.trackWash
      ctx.lineWidth = washWidth
      ctx.stroke()

      ctx.globalAlpha = segAlpha * 0.94
      ctx.beginPath()
      ctx.moveTo(sx0, sy0)
      ctx.lineTo(sx1, sy1)
      ctx.strokeStyle = mapTheme.trackLine
      ctx.lineWidth = trackWidth
      ctx.stroke()
    }
    ctx.globalAlpha = 1.0

    for (let midIndex = 0; midIndex < trackData.length; midIndex++) {
      const midPoint = trackData[midIndex]!
      const dotX = proj.projectX(midPoint.longitude)
      const dotY = proj.projectY(midPoint.latitude)
      const dotAlpha = 0.15 + 0.85 * (midIndex / Math.max(1, trackData.length - 1))
      ctx.globalAlpha = dotAlpha * 0.88
      ctx.beginPath()
      ctx.arc(
        dotX,
        dotY,
        midIndex === trackData.length - 1 ? (landingMode ? 5.2 : 4.6) : landingMode ? 3.2 : 2.8,
        0,
        Math.PI * 2,
      )
      ctx.fillStyle = mapTheme.trackLine
      ctx.fill()
    }
    ctx.globalAlpha = 1.0
  }

  const last = trackData[trackData.length - 1]!
  if (Number.isFinite(last.longitude) && Number.isFinite(last.latitude)) {
    const cx = proj.projectX(last.longitude)
    const cy = proj.projectY(last.latitude)
    const headingRadians = ((headingDeg - 90) * Math.PI) / 180

    ctx.beginPath()
    ctx.arc(cx, cy, 22, 0, Math.PI * 2)
    ctx.strokeStyle = 'rgba(26,86,219,0.3)'
    ctx.lineWidth = 1.4
    ctx.stroke()

    ctx.beginPath()
    ctx.arc(cx, cy, 56, 0, Math.PI * 2)
    ctx.strokeStyle = 'rgba(26,86,219,0.15)'
    ctx.lineWidth = 1.2
    ctx.stroke()

    ctx.beginPath()
    ctx.arc(cx, cy, 38, (-140 * Math.PI) / 180, (40 * Math.PI) / 180)
    ctx.strokeStyle = 'rgba(251,191,36,0.4)'
    ctx.lineWidth = 1.2
    ctx.stroke()

    ctx.beginPath()
    ctx.moveTo(cx, cy)
    ctx.lineTo(cx + Math.cos(headingRadians) * 74, cy + Math.sin(headingRadians) * 74)
    ctx.strokeStyle = 'rgba(71,85,105,0.7)'
    ctx.lineWidth = 1.4
    ctx.stroke()

    ctx.beginPath()
    ctx.arc(cx, cy, 6.5, 0, Math.PI * 2)
    ctx.fillStyle = 'rgba(255,255,255,0.95)'
    ctx.fill()
  }

  ctx.restore()
}
