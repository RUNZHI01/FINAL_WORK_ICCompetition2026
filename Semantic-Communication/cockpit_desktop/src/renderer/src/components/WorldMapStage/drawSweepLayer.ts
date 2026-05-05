import type { Projection } from './projection'

export type SweepLayerParams = {
  ctx: CanvasRenderingContext2D
  cssWidth: number
  cssHeight: number
  proj: Projection
  markerX: number
  markerY: number
  sweepDeg: number
  /** Monotonic timestamp (ms) for ping ring phase animation */
  timestampMs: number
}

/** Radar sweep fan from Qt `paintSweepOverlay` + two pulsing ping rings from `paintRadarPing`. */
export function drawSweepLayer(p: SweepLayerParams): void {
  const { ctx, cssWidth: w, cssHeight: h, proj, markerX, markerY, sweepDeg, timestampMs } = p
  const { mapInset } = proj

  ctx.save()
  ctx.beginPath()
  ctx.rect(mapInset, mapInset, proj.plotWidth, proj.plotHeight)
  ctx.clip()

  // --- Radar sweep cone ---
  const sweepAngle = (sweepDeg % 360) * (Math.PI / 180)
  const sweepLength = Math.max(w, h) * 0.38
  ctx.globalCompositeOperation = 'lighter'
  ctx.beginPath()
  ctx.moveTo(markerX, markerY)
  ctx.arc(markerX, markerY, sweepLength, sweepAngle - 0.28, sweepAngle)
  ctx.closePath()
  const sweepGrad = ctx.createRadialGradient(markerX, markerY, 0, markerX, markerY, sweepLength)
  sweepGrad.addColorStop(0.0, 'rgba(120,220,255,0.10)')
  sweepGrad.addColorStop(0.4, 'rgba(120,220,255,0.04)')
  sweepGrad.addColorStop(1.0, 'rgba(120,220,255,0.0)')
  ctx.fillStyle = sweepGrad
  ctx.fill()

  // --- Two pulsing ping rings (staggered, matching Qt paintRadarPing) ---
  ctx.globalCompositeOperation = 'source-over'
  const pingCycleMs = 2200

  for (let ring = 0; ring < 2; ring++) {
    const phaseOffset = ring * (pingCycleMs / 2)
    const elapsed = ((timestampMs + phaseOffset) % pingCycleMs) / pingCycleMs
    // ease-out: fast expand, slow fade
    const t = elapsed
    const minRadius = 8
    const maxRadius = Math.max(1, Math.min(w, h) * 0.28)
    const radius = Math.max(1, minRadius + (maxRadius - minRadius) * t)
    const alpha = Math.max(0, 0.5 * (1 - t))
    if (alpha <= 0) continue

    ctx.beginPath()
    ctx.arc(markerX, markerY, radius, 0, Math.PI * 2)
    ctx.strokeStyle = `rgba(143,230,255,${alpha.toFixed(3)})`
    ctx.lineWidth = 1.4 * (1 - t * 0.5)
    ctx.stroke()
  }

  ctx.restore()
}
