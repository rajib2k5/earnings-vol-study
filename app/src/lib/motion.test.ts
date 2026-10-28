import { describe, it, expect, vi } from 'vitest'
import { controlsConfig, prefersReducedMotion } from './motion'

describe('prefersReducedMotion', () => {
  it('asks the reduced-motion media query and returns its answer', () => {
    const matchMedia = vi.fn((q: string) => ({ matches: q === '(prefers-reduced-motion: reduce)' }))
    expect(prefersReducedMotion({ matchMedia })).toBe(true)
    expect(matchMedia).toHaveBeenCalledWith('(prefers-reduced-motion: reduce)')
    expect(prefersReducedMotion({ matchMedia: () => ({ matches: false }) })).toBe(false)
  })
  it('chooses "no motion" when matchMedia is unavailable (we cannot tell)', () => {
    expect(prefersReducedMotion({})).toBe(true)
  })
})

describe('controlsConfig', () => {
  it('reduced motion: no auto-rotate, no inertia, and redraw only on demand', () => {
    expect(controlsConfig(true)).toEqual({ autoRotate: false, autoRotateSpeed: 0, enableDamping: false, frameloop: 'demand' })
  })
  it('normal motion: slow auto-rotate with smoothing and a continuous render loop', () => {
    expect(controlsConfig(false)).toEqual({ autoRotate: true, autoRotateSpeed: 0.6, enableDamping: true, frameloop: 'always' })
  })
})
