import { describe, it, expect } from 'vitest'
import { isFiniteNumber, isIntPair, isIsoDate, isNonNegInt, isObject, isPositiveInt, isText, isUnitInterval, keyProblem, show } from './validate'

describe('isIsoDate', () => {
  it('accepts real calendar dates, including a leap day', () => {
    for (const ok of ['2026-10-29', '2024-02-29', '2031-12-31', '2031-01-01']) expect(isIsoDate(ok), ok).toBe(true)
  })
  it('rejects dates Date.UTC would roll over, and years it would remap', () => {
    for (const bad of ['2025-02-29', '2026-02-30', '2026-04-31', '2026-13-01', '2026-00-10', '2026-10-00', '2026-10-32', '0026-10-27']) {
      expect(isIsoDate(bad), bad).toBe(false)
    }
  })
  it('rejects wrong shapes and non-strings', () => {
    for (const bad of ['2026-1-2', '26-10-29', '2026/10/29', '2026-10-29T00:00:00Z', ' 2026-10-29', '2026-10-29\n', '', 'today']) {
      expect(isIsoDate(bad), JSON.stringify(bad)).toBe(false)
    }
    for (const bad of [20261029, null, undefined, [], {}, true]) expect(isIsoDate(bad), String(bad)).toBe(false)
  })
})

describe('integer and text checks', () => {
  it('isNonNegInt: zero and up, whole numbers only', () => {
    for (const ok of [0, 1, 1000]) expect(isNonNegInt(ok), String(ok)).toBe(true)
    for (const bad of [-1, 1.5, NaN, Infinity, '1', null, undefined, [1], true]) expect(isNonNegInt(bad), String(bad)).toBe(false)
  })
  it('isPositiveInt: one and up, so zero is out', () => {
    for (const ok of [1, 21]) expect(isPositiveInt(ok), String(ok)).toBe(true)
    for (const bad of [0, -3, 2.5, NaN, '3', null]) expect(isPositiveInt(bad), String(bad)).toBe(false)
  })
  it('isFiniteNumber: any real number, negatives and fractions included', () => {
    for (const ok of [0, -0.5, 3, 1e-9, -1e9]) expect(isFiniteNumber(ok), String(ok)).toBe(true)
    for (const bad of [NaN, Infinity, -Infinity, '1', null, undefined, [1], true]) expect(isFiniteNumber(bad), String(bad)).toBe(false)
  })
  it('isUnitInterval: 0 to 1 with both ends in', () => {
    for (const ok of [0, 1, 0.5, 0.0115]) expect(isUnitInterval(ok), String(ok)).toBe(true)
    for (const bad of [-0.001, 1.001, 2, NaN, Infinity, -Infinity, '0.5', null, undefined, [0.5]]) expect(isUnitInterval(bad), String(bad)).toBe(false)
  })
  it('isIntPair: exactly two integers, negatives allowed', () => {
    expect(isIntPair([-10, 10])).toBe(true)
    expect(isIntPair([0, 0])).toBe(true)
    for (const bad of [[], [1], [1, 2, 3], [1, 2.5], ['1', 2], [null, 2], [NaN, 2], 'ab', { 0: 1, 1: 2 }]) expect(isIntPair(bad), JSON.stringify(bad)).toBe(false)
  })
  it('isText: a string with something other than whitespace in it', () => {
    expect(isText('a')).toBe(true)
    for (const bad of ['', '   ', '\t\n', 1, null, undefined, ['a']]) expect(isText(bad), JSON.stringify(bad)).toBe(false)
  })
  it('isObject: plain objects only, not null or arrays', () => {
    expect(isObject({})).toBe(true)
    for (const bad of [null, [], 'x', 1, undefined]) expect(isObject(bad), String(bad)).toBe(false)
  })
})

describe('show and keyProblem', () => {
  it('show describes a value briefly without dumping it', () => {
    expect(show('a')).toBe('"a"')
    expect(show(null)).toBe('null')
    expect(show([1, 2])).toBe('an array')
    expect(show({ a: 1 })).toBe('an object')
    expect(show(5)).toBe('number 5')
    expect(show(undefined)).toBe('undefined undefined')
  })
  it('keyProblem is null for exactly the expected keys, in any order', () => {
    expect(keyProblem('x', { b: 1, a: 2 }, ['a', 'b'])).toBeNull()
  })
  it('keyProblem names missing and extra keys, and ignores inherited ones', () => {
    expect(keyProblem('x', { a: 1, c: 3 }, ['a', 'b'])).toBe('x has missing key(s): b; unexpected key(s): c (expected exactly: a, b)')
    const inherited = Object.assign(Object.create({ b: 1 }), { a: 1 })
    expect(keyProblem('x', inherited, ['a', 'b'])).toBe('x has missing key(s): b (expected exactly: a, b)')
  })
})
