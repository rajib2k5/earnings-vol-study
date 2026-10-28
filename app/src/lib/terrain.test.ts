import { describe, it, expect } from 'vitest'
import { gridToTerrain, hexToRgb, lerpRgb, srgbToLinear, tokenColour, type Rgb } from './terrain'

const LOW: Rgb = [0, 0, 1]
const HIGH: Rgb = [1, 0, 0]
const MISSING: Rgb = [0.2, 0.2, 0.2]
const OPTS = { low: LOW, high: HIGH, missing: MISSING, width: 10, depth: 6, height: 3 }

const vertex = (t: ReturnType<typeof gridToTerrain>, i: number, j: number) => {
  const k = i * t.cols + j
  return {
    pos: Array.from(t.positions.slice(3 * k, 3 * k + 3)),
    rgb: Array.from(t.colors.slice(3 * k, 3 * k + 3)),
  }
}

describe('gridToTerrain: sizes', () => {
  it('makes one vertex per cell and two triangles per grid square', () => {
    // 3 companies x 4 days -> 12 vertices; (3-1)*(4-1) = 6 squares -> 12 triangles -> 36 indices.
    const t = gridToTerrain([[1, 2, 3, 4], [2, 3, 4, 5], [3, 4, 5, 6]], OPTS)
    expect(t.rows).toBe(3)
    expect(t.cols).toBe(4)
    expect(t.vertexCount).toBe(12)
    expect(t.positions).toHaveLength(36)
    expect(t.colors).toHaveLength(36)
    expect(t.indices).toHaveLength(36)
    expect(Math.max(...t.indices)).toBeLessThan(t.vertexCount)
  })
  it('handles an empty grid and degenerate single-row / single-column grids', () => {
    const empty = gridToTerrain([], OPTS)
    expect([empty.vertexCount, empty.indices.length, empty.rows, empty.cols]).toEqual([0, 0, 0, 0])
    expect(empty.min).toBeNaN()
    const oneRow = gridToTerrain([[1, 2, 3]], OPTS)
    expect(oneRow.vertexCount).toBe(3)
    expect(oneRow.indices).toHaveLength(0) // no squares to tile
    expect(vertex(oneRow, 0, 0).pos[2]).toBe(0) // a lone row sits at z = 0
    const oneCol = gridToTerrain([[1], [2], [3]], OPTS)
    expect(oneCol.indices).toHaveLength(0)
    expect(vertex(oneCol, 0, 0).pos[0]).toBe(0) // a lone column sits at x = 0
  })
  it('throws a descriptive error on a ragged grid instead of drawing garbage', () => {
    expect(() => gridToTerrain([[1, 2, 3], [1, 2]], OPTS)).toThrow('ragged grid: row 1 has 2 columns, expected 3')
  })
})

describe('gridToTerrain: value -> height / colour mapping', () => {
  const t = gridToTerrain([[0, 10], [5, 20]], OPTS)
  it('reports the finite min and max', () => {
    expect(t.min).toBe(0)
    expect(t.max).toBe(20)
  })
  it('maps min to y = 0 and max to y = height, linearly in between', () => {
    // t = (v - min) / (max - min); y = t * 3  ->  0, 10 -> 1.5, 5 -> 0.75, 20 -> 3
    expect(vertex(t, 0, 0).pos[1]).toBe(0)
    expect(vertex(t, 0, 1).pos[1]).toBeCloseTo(1.5, 6)
    expect(vertex(t, 1, 0).pos[1]).toBeCloseTo(0.75, 6)
    expect(vertex(t, 1, 1).pos[1]).toBeCloseTo(3, 6)
  })
  it('colours min with the low colour, max with the high colour, and blends linearly', () => {
    expect(vertex(t, 0, 0).rgb).toEqual([0, 0, 1])
    expect(vertex(t, 1, 1).rgb).toEqual([1, 0, 0])
    // v = 10 -> t = 0.5 -> halfway between blue and red
    const mid = vertex(t, 0, 1).rgb
    expect(mid[0]).toBeCloseTo(0.5, 6)
    expect(mid[2]).toBeCloseTo(0.5, 6)
  })
  it('spreads x over `width` by column and z over `depth` by row, centred on 0', () => {
    expect(vertex(t, 0, 0).pos[0]).toBeCloseTo(-5, 6)
    expect(vertex(t, 0, 1).pos[0]).toBeCloseTo(5, 6)
    expect(vertex(t, 0, 0).pos[2]).toBeCloseTo(-3, 6)
    expect(vertex(t, 1, 0).pos[2]).toBeCloseTo(3, 6)
  })
  it('sits a flat grid at height 0 in the low colour (no divide-by-zero)', () => {
    const flat = gridToTerrain([[7, 7], [7, 7]], OPTS)
    for (let k = 0; k < 4; k++) {
      expect(flat.positions[3 * k + 1]).toBe(0)
      expect(Array.from(flat.colors.slice(3 * k, 3 * k + 3))).toEqual([0, 0, 1])
    }
  })
  it('uses the documented defaults when width, depth, height and missing colour are omitted', () => {
    const d = gridToTerrain([[0, 1], [NaN, 1]], { low: LOW, high: HIGH })
    expect(vertex(d, 0, 1).pos[0]).toBeCloseTo(5, 6) // width 10
    expect(vertex(d, 1, 0).pos[2]).toBeCloseTo(3, 6) // depth 6
    expect(vertex(d, 0, 1).pos[1]).toBeCloseTo(3, 6) // height 3
    expect(vertex(d, 1, 0).rgb).toEqual([0.5, 0.5, 0.5]) // mid grey
  })
})

describe('gridToTerrain: NaN handling', () => {
  it('keeps every position/colour finite, paints missing cells grey, and counts them', () => {
    const t = gridToTerrain([[1, NaN, 3], [4, 5, Infinity], [7, 8, 9]], OPTS)
    expect(t.missingCount).toBe(2)
    expect(Array.from(t.positions).every(Number.isFinite)).toBe(true)
    expect(Array.from(t.colors).every(Number.isFinite)).toBe(true)
    expect(vertex(t, 0, 1).rgb.map((c) => +c.toFixed(6))).toEqual([0.2, 0.2, 0.2])
    expect(vertex(t, 0, 1).pos[1]).toBe(0)
    // min / max ignore the missing cells
    expect(t.min).toBe(1)
    expect(t.max).toBe(9)
  })
  it('leaves a hole: squares touching a missing cell emit no triangles', () => {
    // Centre NaN in a 3x3: all four squares share the centre vertex -> nothing to draw.
    expect(gridToTerrain([[1, 2, 3], [4, NaN, 6], [7, 8, 9]], OPTS).indices).toHaveLength(0)
    // Corner NaN: only the one square containing the corner is dropped -> 3 squares * 6 indices.
    const corner = gridToTerrain([[NaN, 2, 3], [4, 5, 6], [7, 8, 9]], OPTS)
    expect(corner.indices).toHaveLength(18)
    expect(Array.from(corner.indices)).not.toContain(0) // vertex 0 is the NaN corner
  })
  it('an all-missing grid has NaN min/max, no triangles, and finite buffers', () => {
    const t = gridToTerrain([[NaN, NaN], [NaN, NaN]], OPTS)
    expect(t.min).toBeNaN()
    expect(t.max).toBeNaN()
    expect(t.missingCount).toBe(4)
    expect(t.indices).toHaveLength(0)
    expect(Array.from(t.positions).every(Number.isFinite)).toBe(true)
  })
})

describe('gridToTerrain: triangle winding', () => {
  it('winds every triangle counter-clockwise seen from +y, so the surface faces up', () => {
    // Flat grid -> every triangle's true normal must be exactly +y. Cross product computed here
    // independently of the implementation: n = (q - p) x (r - p).
    const t = gridToTerrain([[1, 1, 1], [1, 1, 1], [1, 1, 1]], OPTS)
    expect(t.indices).toHaveLength(24)
    for (let n = 0; n < t.indices.length; n += 3) {
      const [p, q, r] = [t.indices[n], t.indices[n + 1], t.indices[n + 2]].map((i) => Array.from(t.positions.slice(3 * i, 3 * i + 3)))
      const u = [q[0] - p[0], q[1] - p[1], q[2] - p[2]]
      const v = [r[0] - p[0], r[1] - p[1], r[2] - p[2]]
      const normal = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
      expect(normal[1]).toBeGreaterThan(0)
      expect(normal[0]).toBeCloseTo(0, 6)
      expect(normal[2]).toBeCloseTo(0, 6)
    }
  })
})

describe('lerpRgb', () => {
  it('blends channel-wise and clamps t to 0..1', () => {
    expect(lerpRgb([0, 0, 0], [1, 0.5, 0.2], 0.5)).toEqual([0.5, 0.25, 0.1])
    expect(lerpRgb([0, 0, 0], [1, 1, 1], -3)).toEqual([0, 0, 0])
    expect(lerpRgb([0, 0, 0], [1, 1, 1], 9)).toEqual([1, 1, 1])
  })
})

describe('hexToRgb', () => {
  it('parses #rrggbb and #rgb (any case, surrounding spaces) into 0..1 channels', () => {
    expect(hexToRgb('#ff0000')).toEqual([1, 0, 0])
    expect(hexToRgb(' #0F0 ')).toEqual([0, 1, 0])
    const c = hexToRgb('#e0a458') as Rgb // the app's --accent token
    expect(c[0]).toBeCloseTo(224 / 255, 9)
    expect(c[1]).toBeCloseTo(164 / 255, 9)
    expect(c[2]).toBeCloseTo(88 / 255, 9)
  })
  it('returns null for anything else rather than guessing', () => {
    for (const bad of ['', 'red', '#12345', '#gggggg', 'rgb(1,2,3)', '#1234567']) expect(hexToRgb(bad), bad).toBeNull()
  })
})

describe('srgbToLinear', () => {
  it('keeps black and white fixed and follows the sRGB curve in between', () => {
    expect(srgbToLinear([0, 0, 0])).toEqual([0, 0, 0])
    for (const c of srgbToLinear([1, 1, 1])) expect(c).toBeCloseTo(1, 12)
    // Hand-worked: ((0.5 + 0.055) / 1.055)^2.4 = 0.21404...; a dark value uses the linear segment: 0.04 / 12.92.
    expect(srgbToLinear([0.5, 0.04, 0.5])[0]).toBeCloseTo(0.21404114, 6)
    expect(srgbToLinear([0.5, 0.04, 0.5])[1]).toBeCloseTo(0.04 / 12.92, 12)
  })
})

describe('tokenColour', () => {
  const tokens: Record<string, string> = { '--accent': ' #ff0000', '--bad': 'not-a-colour' }
  const read = (n: string) => tokens[n] ?? ''
  it('reads a hex token (surrounding space allowed) and converts it to linear', () => {
    expect(tokenColour(read, '--accent', '#00ff00')).toEqual([1, 0, 0])
    const [r] = tokenColour((n) => (n === '--c' ? '#808080' : ''), '--c', '#00ff00')
    expect(r).toBeCloseTo(0.2158605, 6) // sRGB 128/255 -> 0.2158605 linear
  })
  it('uses the (converted) fallback when the token is missing or not hex', () => {
    expect(tokenColour(read, '--missing', '#00ff00')).toEqual([0, 1, 0])
    expect(tokenColour(read, '--bad', '#0000ff')).toEqual([0, 0, 1])
  })
  it('throws if the fallback itself is not a hex colour, rather than returning garbage', () => {
    expect(() => tokenColour(read, '--missing', 'green')).toThrow('fallback "green" is not a hex colour')
  })
})
