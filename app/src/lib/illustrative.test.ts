import { describe, it, expect } from 'vitest'
import { EVENT_DAYS, ILLUSTRATIVE_LABEL, illustrativeIvGrid, ivBump } from './illustrative'

describe('EVENT_DAYS', () => {
  it('runs -10 ... +10 inclusive with day 0 in the middle', () => {
    expect(EVENT_DAYS).toHaveLength(21)
    expect(EVENT_DAYS[0]).toBe(-10)
    expect(EVENT_DAYS[20]).toBe(10)
    expect(EVENT_DAYS[10]).toBe(0)
  })
})

describe('ivBump', () => {
  it('matches hand-worked values on the run-up, the peak and the crush', () => {
    expect(ivBump(-10)).toBe(0) // ((-10 + 10) / 10)^2
    expect(ivBump(-5)).toBeCloseTo(0.25, 12) // (5 / 10)^2
    expect(ivBump(-1)).toBeCloseTo(0.81, 12) // (9 / 10)^2
    expect(ivBump(0)).toBe(1)
    expect(ivBump(1)).toBeCloseTo(0.15, 12) // 0.15 * exp(0)
    expect(ivBump(4)).toBeCloseTo(0.15 * Math.exp(-1), 12) // 0.15 * exp(-(4 - 1) / 3)
  })
  it('rises into day 0, peaks there, and the crush sits below the pre-event level', () => {
    for (let d = -10; d < 0; d++) expect(ivBump(d + 1)).toBeGreaterThan(ivBump(d))
    for (let d = 1; d <= 10; d++) expect(ivBump(d)).toBeLessThan(ivBump(-1))
  })
})

describe('illustrativeIvGrid', () => {
  it('is deterministic per seed and differs between seeds', () => {
    expect(illustrativeIvGrid(5)).toEqual(illustrativeIvGrid(5))
    expect(illustrativeIvGrid(5)).not.toEqual(illustrativeIvGrid(6))
  })
  it('has one row per company and one column per event day, all finite and positive', () => {
    const g = illustrativeIvGrid(1, 7)
    expect(g).toHaveLength(7)
    for (const row of g) {
      expect(row).toHaveLength(EVENT_DAYS.length)
      for (const v of row) {
        expect(Number.isFinite(v)).toBe(true)
        expect(v).toBeGreaterThan(0)
      }
    }
  })
  it('shows run-up then crush in the cross-company average, for several seeds', () => {
    const at = (g: number[][], day: number) => g.reduce((s, row) => s + row[EVENT_DAYS.indexOf(day)], 0) / g.length
    for (const seed of [1, 2, 3, 42, 2026]) {
      const g = illustrativeIvGrid(seed)
      expect(at(g, -1), `seed ${seed}: run-up`).toBeGreaterThan(at(g, -10))
      expect(at(g, 0), `seed ${seed}: peak`).toBeGreaterThan(at(g, -1))
      expect(at(g, 1), `seed ${seed}: crush`).toBeLessThan(at(g, -1))
    }
  })
})

describe('ILLUSTRATIVE_LABEL', () => {
  it('is exactly the wording the brief requires (em dash included)', () => {
    expect(ILLUSTRATIVE_LABEL).toBe('Illustrative synthetic shape — not data')
  })
})
