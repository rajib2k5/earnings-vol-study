import { describe, it, expect } from 'vitest'
import { asGiven, fmt, pct, bps, sizeCheckFailedText, withheldText } from './format'

describe('formatters', () => {
  it('fmt formats with thousands separators and fixed decimals', () => {
    expect(fmt(1234.5678)).toBe('1,234.57')
    expect(fmt(1, 4)).toBe('1.0000')
  })
  it('pct converts a fraction to a percentage string', () => {
    expect(pct(0.1234)).toBe('12.34%')
    expect(pct(-0.5, 1)).toBe('-50.0%')
  })
  it('bps converts a fraction to basis points', () => {
    expect(bps(0.0012)).toBe('12.0 bps')
  })
  it('all return an em dash for non-finite input', () => {
    expect(fmt(NaN)).toBe('—')
    expect(pct(Infinity)).toBe('—')
    expect(bps(NaN)).toBe('—')
  })
})

describe('asGiven', () => {
  it('shows a number exactly as written: no rounding, no padding, exponent kept', () => {
    expect(asGiven(0.0123)).toBe('0.0123')
    expect(asGiven(-0.5)).toBe('-0.5')
    expect(asGiven(4.445e-22)).toBe('4.445e-22')
    expect(asGiven(2)).toBe('2')
  })
  it('shows a dash for null, and zero as 0 (null is not 0)', () => {
    expect(asGiven(null)).toBe('—')
    expect(asGiven(0)).toBe('0')
  })
})

describe('withheldText', () => {
  it('shows the G1 rate as a percent with two decimals and the replications with a thousands separator', () => {
    expect(withheldText(0.1845, 2000)).toBe('withheld (G1 size 18.45% over 2,000 replications)')
    expect(withheldText(0.05, 10000)).toBe('withheld (G1 size 5.00% over 10,000 replications)')
    expect(withheldText(0.0568, 500)).toBe('withheld (G1 size 5.68% over 500 replications)')
  })
})

describe('sizeCheckFailedText', () => {
  it('shows the failed G1 rate of a kept primary p-value as a percent, with the replications, and says a rejection would not be trusted', () => {
    expect(sizeCheckFailedText(0.0955, 2000)).toBe('size check failed: G1 size 9.55% over 2,000 replications, liberal; a rejection would not be trusted')
    expect(sizeCheckFailedText(0.5625, 500)).toBe('size check failed: G1 size 56.25% over 500 replications, liberal; a rejection would not be trusted')
  })
})
