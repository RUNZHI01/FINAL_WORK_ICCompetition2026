const CHINA_MIN_LON = 72
const CHINA_MAX_LON = 136
const CHINA_MIN_LAT = 16
const CHINA_MAX_LAT = 56

export type Projection = {
  mapInset: number
  plotWidth: number
  plotHeight: number
  chinaTheater: boolean
  projectX: (longitude: number) => number
  projectY: (latitude: number) => number
}

export function createProjection(
  cssWidth: number,
  cssHeight: number,
  mapInset: number,
  chinaTheater: boolean,
): Projection {
  const canvasW = Math.max(1, cssWidth - mapInset * 2)
  const canvasH = Math.max(1, cssHeight - mapInset * 2)

  const minLon = chinaTheater ? CHINA_MIN_LON : -180
  const maxLon = chinaTheater ? CHINA_MAX_LON : 180
  const minLat = chinaTheater ? CHINA_MIN_LAT : -90
  const maxLat = chinaTheater ? CHINA_MAX_LAT : 90

  const lonSpan = Math.max(1, maxLon - minLon)
  const latSpan = Math.max(1, maxLat - minLat)

  // Preserve geographic aspect ratio
  const geoAspect = lonSpan / latSpan
  const canvasAspect = canvasW / canvasH

  let plotW: number
  let plotH: number
  let padX: number
  let padY: number

  if (canvasAspect > geoAspect) {
    // Canvas wider → fit by height, center horizontally
    plotH = canvasH
    plotW = canvasH * geoAspect
    padX = (canvasW - plotW) / 2
    padY = 0
  } else {
    // Canvas taller → fit by width, center vertically
    plotW = canvasW
    plotH = canvasW / geoAspect
    padX = 0
    padY = (canvasH - plotH) / 2
  }

  function projectX(longitude: number): number {
    return mapInset + padX + ((Number(longitude) - minLon) / lonSpan) * plotW
  }

  function projectY(latitude: number): number {
    return mapInset + padY + ((maxLat - Number(latitude)) / latSpan) * plotH
  }

  return {
    mapInset,
    plotWidth: canvasW,
    plotHeight: canvasH,
    chinaTheater,
    projectX,
    projectY,
  }
}

export const worldLatitudeTicks = [-60, -30, 0, 30, 60] as const
export const worldLongitudeTicks = [-120, -60, 0, 60, 120] as const
export const chinaLatitudeTicks = [20, 30, 40, 50] as const
export const chinaLongitudeTicks = [80, 100, 120, 130] as const
