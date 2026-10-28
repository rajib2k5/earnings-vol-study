/**
 * Pure grid -> 3D surface transform used by the EventTerrain3D component.
 *
 * Input is a grid `values[company][eventDay]` (one row per company/event, one column per day
 * relative to the announcement). Output is flat typed arrays that three.js can use directly:
 * one vertex per grid cell, two triangles per grid square. No WebGL, no DOM, no clock here, so
 * all of it is unit-testable.
 *
 * Axes: column j (event day) -> x, row i (company) -> z, value -> y (height, 0..`height`).
 */

/** An RGB colour with each channel in 0..1 (what three.js vertex colours expect). */
export type Rgb = readonly [number, number, number]

export interface TerrainOptions {
  /** Colour at the smallest finite value. */
  low: Rgb
  /** Colour at the largest finite value. */
  high: Rgb
  /** Colour for missing (NaN / non-finite) cells. Default: mid grey. */
  missing?: Rgb
  /** Extent along x (event days). Default 10. */
  width?: number
  /** Extent along z (companies). Default 6. */
  depth?: number
  /** Height of the tallest vertex. Default 3. */
  height?: number
}

export interface Terrain {
  rows: number
  cols: number
  /** rows * cols. */
  vertexCount: number
  /** x, y, z per vertex (length 3 * vertexCount). Always finite. */
  positions: Float32Array
  /** r, g, b per vertex (length 3 * vertexCount). */
  colors: Float32Array
  /** Triangle vertex indices. Squares touching a missing cell are left out, so gaps show as holes. */
  indices: Uint32Array
  /** Smallest / largest finite input value (NaN when the grid has none). */
  min: number
  max: number
  /** Number of non-finite input cells. */
  missingCount: number
}

const DEFAULT_MISSING: Rgb = [0.5, 0.5, 0.5]

/** Linear blend of two colours; t is clamped to 0..1. */
export function lerpRgb(a: Rgb, b: Rgb, t: number): Rgb {
  const k = Math.min(1, Math.max(0, t))
  return [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k]
}

/** Parse "#rgb" or "#rrggbb" into 0..1 channels; anything else returns null. */
export function hexToRgb(hex: string): Rgb | null {
  const m = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(hex.trim())
  if (!m) return null
  const h = m[1].length === 3 ? [...m[1]].map((c) => c + c).join('') : m[1]
  return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16) / 255) as unknown as Rgb
}

/**
 * sRGB -> linear light, per channel. three.js blends and lights vertex colours in linear space and
 * converts to sRGB only when drawing, so theme colours written as sRGB hex must be converted first.
 */
export function srgbToLinear(rgb: Rgb): Rgb {
  const f = (c: number) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4)
  return [f(rgb[0]), f(rgb[1]), f(rgb[2])]
}

/**
 * Read a CSS custom property holding a hex colour (e.g. `--accent`) as a linear colour for the
 * terrain. `read` is `(name) => string`, normally backed by getComputedStyle. If the token is
 * missing or not a hex colour, `fallbackHex` is used instead (and must itself be valid hex).
 */
export function tokenColour(read: (name: string) => string, name: string, fallbackHex: string): Rgb {
  const rgb = hexToRgb(read(name)) ?? hexToRgb(fallbackHex)
  if (!rgb) throw new Error(`tokenColour: fallback "${fallbackHex}" is not a hex colour`)
  return srgbToLinear(rgb)
}

/** Position along an axis of `n` samples, centred on 0 and `extent` wide (a single sample sits at 0). */
function axis(i: number, n: number, extent: number): number {
  return n === 1 ? 0 : (i / (n - 1) - 0.5) * extent
}

export function gridToTerrain(values: number[][], opts: TerrainOptions): Terrain {
  const { low, high, missing = DEFAULT_MISSING, width = 10, depth = 6, height = 3 } = opts
  const rows = values.length
  const cols = rows === 0 ? 0 : values[0].length
  values.forEach((row, i) => {
    if (row.length !== cols) throw new Error(`ragged grid: row ${i} has ${row.length} columns, expected ${cols}`)
  })

  let min = Infinity
  let max = -Infinity
  for (const row of values) {
    for (const v of row) {
      if (Number.isFinite(v)) {
        min = Math.min(min, v)
        max = Math.max(max, v)
      }
    }
  }
  const hasData = min <= max
  const span = hasData ? max - min : 0

  const vertexCount = rows * cols
  const positions = new Float32Array(3 * vertexCount)
  const colors = new Float32Array(3 * vertexCount)
  const isMissing = new Uint8Array(vertexCount)
  let missingCount = 0

  for (let i = 0; i < rows; i++) {
    for (let j = 0; j < cols; j++) {
      const k = i * cols + j
      const v = values[i][j]
      let y = 0
      let rgb: Rgb = missing
      if (Number.isFinite(v)) {
        // A flat grid (span 0) sits at height 0 in the low colour.
        const t = span === 0 ? 0 : (v - min) / span
        y = t * height
        rgb = lerpRgb(low, high, t)
      } else {
        isMissing[k] = 1
        missingCount++
      }
      positions.set([axis(j, cols, width), y, axis(i, rows, depth)], 3 * k)
      colors.set(rgb, 3 * k)
    }
  }

  // Two triangles per grid square, wound so the surface faces +y (up).
  const indices: number[] = []
  for (let i = 0; i < rows - 1; i++) {
    for (let j = 0; j < cols - 1; j++) {
      const a = i * cols + j
      const b = a + 1
      const c = a + cols
      const d = c + 1
      if (isMissing[a] || isMissing[b] || isMissing[c] || isMissing[d]) continue
      indices.push(a, c, b, b, c, d)
    }
  }

  return {
    rows,
    cols,
    vertexCount,
    positions,
    colors,
    indices: Uint32Array.from(indices),
    min: hasData ? min : NaN,
    max: hasData ? max : NaN,
    missingCount,
  }
}
