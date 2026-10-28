import { describe, it, expect } from 'vitest'
import { gaussian, mulberry32 } from './rng'

describe('mulberry32', () => {
  it('is deterministic: the same seed yields the same sequence', () => {
    const a = mulberry32(42)
    const b = mulberry32(42)
    for (let i = 0; i < 50; i++) expect(a()).toBe(b())
  })
  it('different seeds give different sequences', () => {
    const a = Array.from({ length: 5 }, mulberry32(1))
    const b = Array.from({ length: 5 }, mulberry32(2))
    expect(a).not.toEqual(b)
  })
  it('matches an independent implementation for the first draws of seeds 0 and 42', () => {
    // Oracle: the same algorithm re-implemented with Python big-integer arithmetic
    // (a separate language, so a JS int32/uint32 slip would show up here).
    const r0 = mulberry32(0)
    expect([r0(), r0(), r0()]).toEqual([0.26642920868471265, 0.0003297457005828619, 0.2232720274478197])
    const r42 = mulberry32(42)
    expect([r42(), r42(), r42()]).toEqual([0.6011037519201636, 0.44829055899754167, 0.8524657934904099])
  })
  it('stays inside [0, 1) and looks uniform (mean near 0.5 over 20,000 draws)', () => {
    const r = mulberry32(7)
    let sum = 0
    for (let i = 0; i < 20000; i++) {
      const x = r()
      expect(x).toBeGreaterThanOrEqual(0)
      expect(x).toBeLessThan(1)
      sum += x
    }
    // sd of the mean = sqrt(1/12/20000) ~ 0.002, so 0.01 is a 5-sigma band.
    expect(Math.abs(sum / 20000 - 0.5)).toBeLessThan(0.01)
  })
  it('treats the seed as an unsigned 32-bit integer', () => {
    expect(mulberry32(-1)()).toBe(mulberry32(4294967295)())
  })
})

describe('gaussian', () => {
  it('has mean near 0 and standard deviation near 1 over 20,000 draws', () => {
    const r = mulberry32(11)
    const xs = Array.from({ length: 20000 }, () => gaussian(r))
    const mean = xs.reduce((a, b) => a + b, 0) / xs.length
    const sd = Math.sqrt(xs.reduce((a, b) => a + (b - mean) ** 2, 0) / (xs.length - 1))
    // sd of the mean ~ 0.007; sd of the sd ~ 0.005. Bands are about 5 sigma.
    expect(Math.abs(mean)).toBeLessThan(0.04)
    expect(Math.abs(sd - 1)).toBeLessThan(0.03)
  })
  it('is finite even when the uniform source returns exactly 0', () => {
    expect(Number.isFinite(gaussian(() => 0))).toBe(true)
  })
})
