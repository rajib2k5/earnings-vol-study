import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import type { ReactElement } from 'react'
import EventTerrain3D from './EventTerrain3D'
import { EVENT_DAYS, illustrativeIvGrid } from '../lib/illustrative'
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

describe('EventTerrain3D', () => {
  it('labels the surface exactly as illustrative synthetic data, on screen', () => {
    setReducedMotion(false)
    render(<EventTerrain3D />)
    expect(screen.getByText('Illustrative synthetic shape — not data')).toBeInTheDocument()
    expect(screen.getByTestId('r3f-canvas')).toBeInTheDocument()
  })

  it('auto-rotates and renders continuously when motion is allowed', () => {
    setReducedMotion(false)
    render(<EventTerrain3D />)
    expect(seen.props?.frameloop).toBe('always')
    expect(scene().config).toMatchObject({ autoRotate: true, enableDamping: true })
  })

  it('respects prefers-reduced-motion: no auto-rotate, no inertia, redraw on demand', () => {
    setReducedMotion(true)
    render(<EventTerrain3D />)
    expect(seen.props?.frameloop).toBe('demand')
    expect(scene().config).toMatchObject({ autoRotate: false, enableDamping: false })
  })

  it('treats an unknown motion preference as reduced motion', () => {
    setReducedMotion(undefined)
    render(<EventTerrain3D />)
    expect(scene().config.autoRotate).toBe(false)
  })

  it('hands the scene a terrain built from the seeded grid (one vertex per company x event day)', () => {
    setReducedMotion(false)
    render(<EventTerrain3D seed={7} />)
    const terrain = scene().terrain
    expect(terrain.vertexCount).toBe(24 * EVENT_DAYS.length)
    // Same seed -> same surface: the terrain's range must equal the raw grid's range.
    const flat = illustrativeIvGrid(7).flat()
    expect(terrain.min).toBe(Math.min(...flat))
    expect(terrain.max).toBe(Math.max(...flat))
    expect(terrain.missingCount).toBe(0)
  })

  it('uses a different surface for a different seed', () => {
    setReducedMotion(false)
    const { unmount } = render(<EventTerrain3D seed={1} />)
    const a = scene().terrain.max
    unmount()
    render(<EventTerrain3D seed={2} />)
    expect(scene().terrain.max).not.toBe(a)
  })
})
