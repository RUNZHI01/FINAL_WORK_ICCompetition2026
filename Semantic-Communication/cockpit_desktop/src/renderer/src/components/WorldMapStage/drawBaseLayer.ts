import type { GeoRingPath } from './geoJson'
import { mapTheme } from './theme'
import type { Projection } from './projection'
import {
  chinaLatitudeTicks,
  chinaLongitudeTicks,
  worldLatitudeTicks,
  worldLongitudeTicks,
} from './projection'

const FEATURE_TONES = ['#C4CFDE', '#B8C4D4', '#ACBACA', '#D1D9E6', '#DDE4ED'] as const

const LABEL_COLOR = 'rgba(71, 85, 105, 0.6)'
const LABEL_FONT = '10px "JetBrains Mono", "Consolas", monospace'

function formatLat(deg: number): string {
  if (deg === 0) return '0°'
  return deg > 0 ? `${deg}°N` : `${-deg}°S`
}

function formatLon(deg: number): string {
  if (deg === 0) return '0°'
  return deg > 0 ? `${deg}°E` : `${-deg}°W`
}

function featureTone(index: number): string {
  return FEATURE_TONES[index % FEATURE_TONES.length]!
}

function drawPolygon(
  ctx: CanvasRenderingContext2D,
  proj: Projection,
  polygon: [number, number][],
  fillStyle: string,
  strokeStyle: string,
  lineWidth = 1.25,
): void {
  if (!polygon || polygon.length < 2) {
    return
  }
  ctx.beginPath()
  for (let i = 0; i < polygon.length; i++) {
    const [lon, lat] = polygon[i]!
    const px = proj.projectX(lon)
    const py = proj.projectY(lat)
    if (i === 0) {
      ctx.moveTo(px, py)
    } else {
      ctx.lineTo(px, py)
    }
  }
  ctx.closePath()
  ctx.fillStyle = fillStyle
  ctx.strokeStyle = strokeStyle
  ctx.lineWidth = lineWidth
  ctx.fill()
  ctx.stroke()
}

function drawPolygonStrokeOnly(
  ctx: CanvasRenderingContext2D,
  proj: Projection,
  polygon: [number, number][],
  strokeStyle: string,
  lineWidth: number,
): void {
  if (!polygon || polygon.length < 2) {
    return
  }
  ctx.beginPath()
  for (let i = 0; i < polygon.length; i++) {
    const [lon, lat] = polygon[i]!
    const px = proj.projectX(lon)
    const py = proj.projectY(lat)
    if (i === 0) {
      ctx.moveTo(px, py)
    } else {
      ctx.lineTo(px, py)
    }
  }
  ctx.closePath()
  ctx.strokeStyle = strokeStyle
  ctx.lineWidth = lineWidth
  ctx.stroke()
}

export type BaseLayerParams = {
  ctx: CanvasRenderingContext2D
  cssWidth: number
  cssHeight: number
  proj: Projection
  landingMode: boolean
  worldPaths: GeoRingPath[] | null
  chinaPaths: GeoRingPath[] | null
}

export function drawBaseLayer(p: BaseLayerParams): void {
  const { ctx, cssWidth: w, cssHeight: h, proj, landingMode, worldPaths, chinaPaths } = p
  const { mapInset } = proj

  const ocean = ctx.createLinearGradient(0, 0, 0, h)
  ocean.addColorStop(0.0, landingMode ? '#e0f2fe' : mapTheme.oceanTop)
  ocean.addColorStop(0.34, landingMode ? '#bae6fd' : '#E5EAF2')
  ocean.addColorStop(0.62, landingMode ? '#e0f2fe' : '#E5EAF2')
  ocean.addColorStop(1.0, landingMode ? '#f0f9ff' : mapTheme.oceanBottom)
  ctx.fillStyle = ocean
  ctx.fillRect(0, 0, w, h)

  const beamCenterX = w * 0.72
  const beamCenterY = h * 0.32
  const beamRadius = Math.max(1, w * 0.55)
  const beam = ctx.createRadialGradient(beamCenterX, beamCenterY, 0, beamCenterX, beamCenterY, beamRadius)
  beam.addColorStop(0.0, landingMode ? mapTheme.beamMid : mapTheme.beamHighlight)
  beam.addColorStop(0.52, landingMode ? 'rgba(26,86,219,0.02)' : mapTheme.beamMid)
  beam.addColorStop(1.0, 'rgba(26,86,219,0.0)')
  ctx.fillStyle = beam
  ctx.fillRect(0, 0, w, h)

  const hazeCenterX = w * 0.22
  const hazeCenterY = h * 0.78
  const hazeRadius = Math.max(1, w * 0.42)
  const haze = ctx.createRadialGradient(hazeCenterX, hazeCenterY, 0, hazeCenterX, hazeCenterY, hazeRadius)
  haze.addColorStop(0.0, landingMode ? 'rgba(251,191,36,0.05)' : mapTheme.hazeHighlight)
  haze.addColorStop(0.5, landingMode ? 'rgba(251,191,36,0.015)' : mapTheme.hazeMid)
  haze.addColorStop(1.0, 'rgba(251,191,36,0.0)')
  ctx.fillStyle = haze
  ctx.fillRect(0, 0, w, h)

  ctx.save()
  ctx.beginPath()
  ctx.rect(mapInset, mapInset, proj.plotWidth, proj.plotHeight)
  ctx.clip()

  const landFill = landingMode ? '#4a7090' : mapTheme.landFill

  const latTicks = proj.chinaTheater ? chinaLatitudeTicks : worldLatitudeTicks
  for (const lat of latTicks) {
    const y = proj.projectY(lat)
    ctx.beginPath()
    ctx.moveTo(mapInset, y)
    ctx.lineTo(w - mapInset, y)
    const isEq = !proj.chinaTheater && lat === 0
    ctx.strokeStyle = isEq
      ? landingMode
        ? 'rgba(26,86,219,0.35)'
        : mapTheme.gridMajorEquator
      : landingMode
        ? 'rgba(148,163,184,0.25)'
        : mapTheme.gridMinorLat
    ctx.lineWidth = isEq ? 1.4 : 1.0
    ctx.stroke()
  }

  const lonTicks = proj.chinaTheater ? chinaLongitudeTicks : worldLongitudeTicks
  for (const lon of lonTicks) {
    const x = proj.projectX(lon)
    ctx.beginPath()
    ctx.moveTo(x, mapInset)
    ctx.lineTo(x, h - mapInset)
    const isPrime = !proj.chinaTheater && lon === 0
    ctx.strokeStyle = isPrime
      ? landingMode
        ? 'rgba(26,86,219,0.35)'
        : mapTheme.gridMajorEquator
      : landingMode
        ? 'rgba(148,163,184,0.25)'
        : mapTheme.gridMinorLon
    ctx.lineWidth = isPrime ? 1.4 : 1.0
    ctx.stroke()
  }

  // --- Lat / lon tick labels (aligned with Qt WorldMapStageCanvas) ---
  ctx.font = LABEL_FONT
  ctx.fillStyle = LABEL_COLOR
  ctx.textBaseline = 'top'
  ctx.textAlign = 'left'
  for (const lat of latTicks) {
    const y = proj.projectY(lat)
    ctx.fillText(formatLat(lat), mapInset + 4, y + 3)
  }
  ctx.textAlign = 'right'
  ctx.textBaseline = 'bottom'
  for (const lon of lonTicks) {
    const x = proj.projectX(lon)
    ctx.fillText(formatLon(lon), x - 4, h - mapInset - 3)
  }

  if (proj.chinaTheater && chinaPaths?.length) {
    for (const cp of chinaPaths) {
      drawPolygon(ctx, proj, cp.ring, landFill, 'rgba(148, 163, 184, 0.35)')
    }
  } else if (worldPaths?.length) {
    for (const wp of worldPaths) {
      const ring = wp.ring
      ctx.save()
      ctx.translate(0, 2)
      drawPolygon(ctx, proj, ring, 'rgba(148, 163, 184, 0.08)', 'rgba(148,163,184,0)')
      ctx.restore()
      ctx.save()
      ctx.globalAlpha = 0.2
      drawPolygonStrokeOnly(ctx, proj, ring, 'rgba(37, 99, 235, 0.4)', 4)
      ctx.globalAlpha = 1.0
      ctx.restore()
      drawPolygon(ctx, proj, ring, featureTone(wp.index), 'rgba(148, 163, 184, 0.35)')
    }
  } else {
    // GeoJSON not yet loaded — show clean ocean + grid only (no crude fallback).
  }

  ctx.beginPath()
  ctx.rect(mapInset, mapInset, proj.plotWidth, proj.plotHeight)
  ctx.strokeStyle = mapTheme.frameStroke
  ctx.lineWidth = 1
  ctx.stroke()
  ctx.restore()

  const vigGrad = ctx.createRadialGradient(
    w * 0.5,
    h * 0.5,
    Math.min(w, h) * 0.32,
    w * 0.5,
    h * 0.5,
    Math.max(w, h) * 0.58,
  )
  vigGrad.addColorStop(0.0, 'rgba(0,0,0,0)')
  vigGrad.addColorStop(1.0, mapTheme.vignette)
  ctx.fillStyle = vigGrad
  ctx.fillRect(0, 0, w, h)
}
