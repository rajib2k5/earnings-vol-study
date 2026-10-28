import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ThreeDPreview } from './ThreeDPreview'

const mode = vi.hoisted(() => ({ canvasThrows: false }))
vi.mock('@react-three/fiber', () => ({
  Canvas: () => {
    if (mode.canvasThrows) throw new Error('WebGL context lost')
    return <div data-testid="r3f-canvas" />
  },
}))
vi.mock('@react-three/drei', () => ({ OrbitControls: () => null }))

afterEach(() => {
  mode.canvasThrows = false
  vi.restoreAllMocks()
})

describe('ThreeDPreview', () => {
  it('shows a loading line while the 3D chunk loads, then the surface', async () => {
    render(<ThreeDPreview />)
    expect(screen.getByText('Loading 3D view…')).toBeInTheDocument()
    expect(await screen.findByTestId('r3f-canvas')).toBeInTheDocument()
    expect(screen.queryByText('Loading 3D view…')).toBeNull()
  })

  it('explains itself as a placeholder', () => {
    render(<ThreeDPreview />)
    expect(screen.getByRole('heading', { name: '3D preview' })).toBeInTheDocument()
    expect(screen.getByText(/Placeholder for the event-time IV surface/)).toBeInTheDocument()
  })

  it('shows an error message instead of a blank page when the 3D view cannot start', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {}) // React logs caught render errors
    mode.canvasThrows = true
    render(<ThreeDPreview />)
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('The 3D view could not start (it needs WebGL): WebGL context lost')
    expect(screen.getByRole('heading', { name: '3D preview' })).toBeInTheDocument() // page survives
  })
})
