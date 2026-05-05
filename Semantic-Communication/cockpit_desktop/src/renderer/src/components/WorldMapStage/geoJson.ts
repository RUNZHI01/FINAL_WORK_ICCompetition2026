export type GeoJsonGeometry = {
  type?: string
  coordinates?: unknown
}

export type GeoJsonFeature = {
  geometry?: GeoJsonGeometry
  properties?: Record<string, unknown>
}

export type GeoJsonFeatureCollection = {
  type?: string
  features?: GeoJsonFeature[]
}

export type GeoRingPath = {
  ring: [number, number][]
  name: string
  index: number
}

export function flattenGeometryRings(geometry: GeoJsonGeometry | undefined): [number, number][][] {
  if (!geometry?.coordinates) {
    return []
  }
  const type = geometry.type
  const coords = geometry.coordinates
  const rings: [number, number][][] = []
  if (type === 'Polygon' && Array.isArray(coords)) {
    for (const ring of coords as [number, number][][]) {
      rings.push(ring)
    }
  } else if (type === 'MultiPolygon' && Array.isArray(coords)) {
    for (const poly of coords as [number, number][][][]) {
      for (const ring of poly) {
        rings.push(ring)
      }
    }
  }
  return rings
}

export function featureCollectionToPaths(payload: GeoJsonFeatureCollection): GeoRingPath[] {
  const features = Array.isArray(payload.features) ? payload.features : []
  const paths: GeoRingPath[] = []
  let index = 0
  for (const feature of features) {
    const rings = flattenGeometryRings(feature.geometry)
    const props = feature.properties ?? {}
    const name = String(props.NAME ?? props.name ?? '')
    for (const ring of rings) {
      paths.push({ ring, name, index: index++ })
    }
  }
  return paths
}

function resolveAssetUrl(url: string): string {
  if (window.location.protocol === 'file:' && url.startsWith('/')) {
    return new URL(url.slice(1), window.location.href).toString()
  }
  return url
}

export async function loadGeoJsonPaths(url: string): Promise<GeoRingPath[]> {
  const resolvedUrl = resolveAssetUrl(url)
  const response = await fetch(resolvedUrl)
  if (!response.ok) {
    throw new Error(`GeoJSON ${url}: HTTP ${response.status}`)
  }
  const payload = (await response.json()) as GeoJsonFeatureCollection
  return featureCollectionToPaths(payload)
}
