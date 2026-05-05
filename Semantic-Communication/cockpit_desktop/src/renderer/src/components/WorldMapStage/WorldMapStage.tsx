import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { T } from '../../theme/tokens'
import { createProjection } from './projection'
import { drawBaseLayer } from './drawBaseLayer'
import { drawTrackLayer, type TrackPoint } from './drawTrackLayer'
import { drawSweepLayer } from './drawSweepLayer'
import type { GeoRingPath } from './geoJson'
import { loadGeoJsonPaths } from './geoJson'

const MAP_INSET = 18

export type AircraftMapContract = {
  position?: { latitude?: number; longitude?: number }
  kinematics?: { heading_deg?: number }
  track?: Array<{ latitude?: number; longitude?: number; age_sec?: number }>
  mission_call_sign?: string
  source_label?: string
}

export type WorldMapStageProps = {
  aircraft?: AircraftMapContract | null
  chinaTheater?: boolean
  landingMode?: boolean
  height?: number | string
}

function setupCanvas2d(canvas: HTMLCanvasElement, cssW: number, cssH: number): CanvasRenderingContext2D | null {
  const dpr = window.devicePixelRatio || 1
  canvas.width = Math.floor(cssW * dpr)
  canvas.height = Math.floor(cssH * dpr)
  canvas.style.width = `${cssW}px`
  canvas.style.height = `${cssH}px`
  const ctx = canvas.getContext('2d')
  if (!ctx) {
    return null
  }
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  return ctx
}

function normalizeTrack(aircraft: AircraftMapContract | null | undefined): { track: TrackPoint[]; headingDeg: number } {
  const headingDeg =
    typeof aircraft?.kinematics?.heading_deg === 'number' && Number.isFinite(aircraft.kinematics.heading_deg)
      ? aircraft.kinematics.heading_deg
      : 0

  const raw = aircraft?.track
  if (Array.isArray(raw) && raw.length > 0) {
    const track = raw
      .map((t) => ({
        longitude: Number(t.longitude),
        latitude: Number(t.latitude),
        age_sec: typeof t.age_sec === 'number' ? t.age_sec : undefined,
      }))
      .filter((t) => Number.isFinite(t.longitude) && Number.isFinite(t.latitude))
    if (track.length > 0) {
      return { track, headingDeg }
    }
  }

  const lat = aircraft?.position?.latitude
  const lon = aircraft?.position?.longitude
  if (typeof lat === 'number' && typeof lon === 'number' && Number.isFinite(lat) && Number.isFinite(lon)) {
    return { track: [{ longitude: lon, latitude: lat }], headingDeg }
  }

  return { track: [], headingDeg: 0 }
}

function buildAircraftTrackKey(aircraft: AircraftMapContract | null | undefined): string {
  const heading = aircraft?.kinematics?.heading_deg ?? ''
  const position = `${aircraft?.position?.latitude ?? ''},${aircraft?.position?.longitude ?? ''}`
  const track = Array.isArray(aircraft?.track)
    ? aircraft.track
        .map((point) => `${point.latitude ?? ''},${point.longitude ?? ''},${point.age_sec ?? ''}`)
        .join('|')
    : ''
  return `${heading}::${position}::${track}`
}

export function WorldMapStage({ aircraft, chinaTheater = false, landingMode = false, height = '100%' }: WorldMapStageProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const baseRef = useRef<HTMLCanvasElement>(null)
  const trackRef = useRef<HTMLCanvasElement>(null)
  const sweepRef = useRef<HTMLCanvasElement>(null)

  const [size, setSize] = useState({ w: 640, h: typeof height === 'number' ? height : 420 })
  const [worldPaths, setWorldPaths] = useState<GeoRingPath[] | null>(null)
  const [chinaPaths, setChinaPaths] = useState<GeoRingPath[] | null>(null)

  const sweepDegRef = useRef(0)
  const rafRef = useRef<number>(0)
  const sweepCtxRef = useRef<CanvasRenderingContext2D | null>(null)

  const aircraftTrackKey = useMemo(() => buildAircraftTrackKey(aircraft), [aircraft])

  // TanStack Query returns a fresh object reference on each poll. Depend on the
  // map-relevant fields only so identical telemetry snapshots do not restart the sweep.
  const { track, headingDeg } = useMemo(
    () => normalizeTrack(aircraft),
    [aircraftTrackKey],
  )
  const hasPoint = track.length > 0

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        if (chinaTheater) {
          const paths = await loadGeoJsonPaths('/geo/china-official.geojson')
          if (!cancelled) {
            setChinaPaths(paths)
            setWorldPaths(null)
          }
        } else {
          const paths = await loadGeoJsonPaths('/geo/world-countries-ne50m.geojson')
          if (!cancelled) {
            setWorldPaths(paths)
            setChinaPaths(null)
          }
        }
      } catch (e) {
        if (!cancelled) {
          setWorldPaths(null)
          setChinaPaths(null)
        }
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [chinaTheater])

  useEffect(() => {
    const el = containerRef.current
    if (!el) {
      return
    }
    const ro = new ResizeObserver(() => {
      const w = Math.max(8, el.clientWidth)
      const h = Math.max(8, el.clientHeight)
      setSize({ w, h })
    })
    ro.observe(el)
    const initialH = el.clientHeight || (typeof height === 'number' ? height : 420)
    setSize({ w: Math.max(8, el.clientWidth), h: Math.max(8, initialH) })
    return () => ro.disconnect()
  }, [height])

  useLayoutEffect(() => {
    const canvas = baseRef.current
    if (!canvas || size.w < 8 || size.h < 8) {
      return
    }
    const ctx = setupCanvas2d(canvas, size.w, size.h)
    if (!ctx) {
      return
    }
    const proj = createProjection(size.w, size.h, MAP_INSET, chinaTheater)
    drawBaseLayer({
      ctx,
      cssWidth: size.w,
      cssHeight: size.h,
      proj,
      landingMode,
      worldPaths: chinaTheater ? null : worldPaths,
      chinaPaths: chinaTheater ? chinaPaths : null,
    })
  }, [size, worldPaths, chinaPaths, chinaTheater, landingMode])

  useLayoutEffect(() => {
    const canvas = trackRef.current
    if (!canvas || size.w < 8 || size.h < 8) {
      return
    }
    const ctx = setupCanvas2d(canvas, size.w, size.h)
    if (!ctx) {
      return
    }
    const proj = createProjection(size.w, size.h, MAP_INSET, chinaTheater)
    drawTrackLayer({
      ctx,
      cssWidth: size.w,
      cssHeight: size.h,
      proj,
      trackData: track,
      headingDeg,
      landingMode,
    })
  }, [size, track, headingDeg, chinaTheater, landingMode])

  useLayoutEffect(() => {
    const canvas = sweepRef.current
    if (!canvas || size.w < 8 || size.h < 8) {
      sweepCtxRef.current = null
      return
    }
    sweepCtxRef.current = setupCanvas2d(canvas, size.w, size.h)
    sweepCtxRef.current?.clearRect(0, 0, size.w, size.h)
  }, [size.w, size.h])

  useEffect(() => {
    if (!hasPoint) {
      sweepDegRef.current = 0
      sweepCtxRef.current?.clearRect(0, 0, size.w, size.h)
      return
    }

    // Check for reduced motion preference
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    const tick = () => {
      sweepDegRef.current = (sweepDegRef.current + 12) % 360
      const ctx = sweepCtxRef.current
      if (ctx && size.w >= 8 && size.h >= 8) {
        const proj = createProjection(size.w, size.h, MAP_INSET, chinaTheater)
        const last = track[track.length - 1]!
        const mx = proj.projectX(last.longitude)
        const my = proj.projectY(last.latitude)
        ctx.clearRect(0, 0, size.w, size.h)
        drawSweepLayer({
          ctx,
          cssWidth: size.w,
          cssHeight: size.h,
          proj,
          markerX: mx,
          markerY: my,
          sweepDeg: sweepDegRef.current,
          timestampMs: performance.now(),
        })
      }
      rafRef.current = requestAnimationFrame(tick)
    }

    // Only animate if user doesn't prefer reduced motion
    if (!prefersReducedMotion) {
      rafRef.current = requestAnimationFrame(tick)
    }

    return () => {
      cancelAnimationFrame(rafRef.current)
    }
  }, [hasPoint, size.w, size.h, chinaTheater, track])

  return (
    <div
      ref={containerRef}
      style={{ position: 'relative', width: '100%', height: height ?? '100%', borderRadius: T.radiusLg, overflow: 'hidden' }}
    >
      <canvas ref={baseRef} style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }} />
      <canvas ref={trackRef} style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }} />
      <canvas ref={sweepRef} style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }} />
    </div>
  )
}
