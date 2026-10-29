import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import type { ReactElement } from 'react'
import EventTerrain3D from './EventTerrain3D'
import { mulberry32 } from '../lib/rng'
import type { ControlsConfig } from '../lib/motion'
import type { Terrain } from '../lib/terrain'

// Stand-in Canvas: records the props it was given and renders nothing (no WebGL in jsdom).
type CanvasProps = { frameloop?: string; children: ReactElement<{ config: ControlsConfig; terrain: Terrain }> }
const seen = vi.hoisted(() => ({ props: null as null | CanvasProps }))
vi.mock('@react-three/fiber', () => ({
  Canvas: (props: CanvasProps) => {
    seen.props = props
    return <div data-testid="r3f-canvas" />
  },
}))
vi.mock('@react-three/drei', () => ({ OrbitControls: () => null }))

/** Props the Canvas stand-in received for the scene element; fails loudly if nothing rendered. */
function scene() {
  if (!seen.props) throw new Error('Canvas was never rendered')
  return seen.props.children.props
}

function setReducedMotion(reduce: boolean | undefined) {
  if (reduce === undefined) Reflect.deleteProperty(window, 'matchMedia')
  else Object.defineProperty(window, 'matchMedia', { configurable: true, value: () => ({ matches: reduce }) })
}

afterEach(() => {
  setReducedMotion(undefined)
  seen.props = null
})

const CAPTION = 'x: event day (-1 to 1) · z: company (3). Fixture caption.'
/** A 3 x 3 grid with one missing cell (NaN), the way terrainGrid hands a null over. */
const GRID = [
  [0.25, 0.5, 0.125],
  [0.5, NaN, 0.25],
  [1, 0.75, 0.375],
]

describe('EventTerrain3D', () => {
  it('shows the caption it is given, with how to move the view, and a canvas', () => {
    setReducedMotion(false)
    render(<EventTerrain3D grid={GRID} caption={CAPTION} />)
    expect(screen.getByText(`${CAPTION} Drag to orbit, scroll to zoom.`)).toBeInTheDocument()
    expect(screen.getByTestId('r3f-canvas')).toBeInTheDocument()
  })

  it('no longer labels the surface as illustrative synthetic data (it draws real data now)', () => {
    setReducedMotion(false)
    render(<EventTerrain3D grid={GRID} caption={CAPTION} />)
    expect(screen.queryByText(/Illustrative synthetic/)).toBeNull()
  })

  it('auto-rotates and renders continuously when motion is allowed', () => {
    setReducedMotion(false)
    render(<EventTerrain3D grid={GRID} caption={CAPTION} />)
    expect(seen.props?.frameloop).toBe('always')
    expect(scene().config).toMatchObject({ autoRotate: true, enableDamping: true })
  })

  it('respects prefers-reduced-motion: no auto-rotate, no inertia, redraw on demand', () => {
    setReducedMotion(true)
    render(<EventTerrain3D grid={GRID} caption={CAPTION} />)
    expect(seen.props?.frameloop).toBe('demand')
    expect(scene().config).toMatchObject({ autoRotate: false, enableDamping: false })
  })

  it('treats an unknown motion preference as reduced motion', () => {
    setReducedMotion(undefined)
    render(<EventTerrain3D grid={GRID} caption={CAPTION} />)
    expect(scene().config.autoRotate).toBe(false)
  })

  it('hands the scene a terrain built from the grid it was given: one vertex per company x event day, the hole kept as a hole', () => {
    setReducedMotion(false)
    render(<EventTerrain3D grid={GRID} caption={CAPTION} />)
    const terrain = scene().terrain
    expect(terrain.rows).toBe(3)
    expect(terrain.cols).toBe(3)
    expect(terrain.vertexCount).toBe(9)
    expect(terrain.missingCount).toBe(1) // the NaN cell
    // the range comes from the finite cells of the grid: smallest 0.125, largest 1
    expect(terrain.min).toBe(0.125)
    expect(terrain.max).toBe(1)
    // every square of this grid touches the missing middle vertex, so no triangle is drawn
    expect(terrain.indices.length).toBe(0)
  })

  it('draws the grid of any size it is given (seeded random 5 companies x 4 days) and uses its own range', () => {
    setReducedMotion(false)
    const rand = mulberry32(7)
    const grid = Array.from({ length: 5 }, () => Array.from({ length: 4 }, () => rand()))
    render(<EventTerrain3D grid={grid} caption={CAPTION} />)
    const terrain = scene().terrain
    const flat = grid.flat()
    expect(terrain.vertexCount).toBe(20)
    expect(terrain.missingCount).toBe(0)
    expect(terrain.min).toBe(Math.min(...flat))
    expect(terrain.max).toBe(Math.max(...flat))
    // 4 x 3 squares, two triangles each, three indices per triangle
    expect(terrain.indices.length).toBe(4 * 3 * 2 * 3)
  })

  it('draws a different surface for a different grid', () => {
    setReducedMotion(false)
    const { rerender } = render(<EventTerrain3D grid={GRID} caption={CAPTION} />)
    const first = scene().terrain
    rerender(<EventTerrain3D grid={[[0, 2], [4, 8]]} caption={CAPTION} />)
    expect(scene().terrain).not.toBe(first)
    expect(scene().terrain.max).toBe(8)
    expect(scene().terrain.vertexCount).toBe(4)
  })
})
