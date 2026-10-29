import { describe, it, expect } from 'vitest'
import {
  ADJUSTMENTS,
  isInteger,
  isNonNegIntOrNull,
  isNumberOrNull,
  isProbability,
  isProbabilityOrNull,
  loadKind,
  oneOf,
  parseArrayOf,
  parseCaveats,
  parseGrid,
  parseLookups,
  parseRelDays,
} from './dataParts'
import { fail, isFiniteNumber, type Parsed } from './validate'
import { fakeFetch, serving } from '../test/editHelpers'

const errorOf = (r: Parsed<unknown>): string => {
  if (r.ok) throw new Error('expected a failure, but the input was accepted')
  return r.error
}

describe('parseLookups', () => {
  it('accepts { n_done, complete } and returns a copy', () => {
    const input = { n_done: 20, complete: false }
    const r = parseLookups(input)
    expect(r).toEqual({ ok: true, data: { n_done: 20, complete: false } })
    if (r.ok) expect(r.data).not.toBe(input)
    expect(parseLookups({ n_done: 0, complete: true }).ok).toBe(true)
  })
  it.each<[string, unknown, string]>([
    ['not an object', null, 'lookups must be an object, got null'],
    ['an array', [], 'lookups must be an object, got an array'],
    ['missing complete', { n_done: 1 }, 'lookups has missing key(s): complete (expected exactly: n_done, complete)'],
    ['an extra key', { n_done: 1, complete: true, total: 5 }, 'lookups has unexpected key(s): total (expected exactly: n_done, complete)'],
    ['negative n_done', { n_done: -1, complete: true }, 'lookups.n_done must be a non-negative integer, got number -1'],
    ['fractional n_done', { n_done: 1.5, complete: true }, 'lookups.n_done must be a non-negative integer, got number 1.5'],
    ['string n_done', { n_done: '20', complete: true }, 'lookups.n_done must be a non-negative integer, got "20"'],
    ['string complete (not coerced)', { n_done: 1, complete: 'false' }, 'lookups.complete must be true or false, got "false"'],
    ['numeric complete', { n_done: 1, complete: 0 }, 'lookups.complete must be true or false, got number 0'],
  ])('rejects %s', (_what, input, message) => {
    expect(errorOf(parseLookups(input))).toBe(message)
  })
})

describe('parseCaveats', () => {
  it('accepts strings, an empty list, and returns a copy', () => {
    const input = ['a', 'b']
    const r = parseCaveats(input)
    expect(r).toEqual({ ok: true, data: ['a', 'b'] })
    if (r.ok) expect(r.data).not.toBe(input)
    expect(parseCaveats([]).ok).toBe(true)
  })
  it.each<[string, unknown, string]>([
    ['not an array', 'caveat', 'caveats must be an array, got "caveat"'],
    ['null', null, 'caveats must be an array, got null'],
    ['a number entry', ['a', 3], 'caveats[1] must be a non-empty string, got number 3'],
    ['an empty entry', ['a', ' '], 'caveats[1] must be a non-empty string, got " "'],
  ])('rejects %s', (_what, input, message) => {
    expect(errorOf(parseCaveats(input))).toBe(message)
  })
})

describe('parseArrayOf', () => {
  it('checks every entry with the test and reports the first bad index', () => {
    expect(parseArrayOf([1, 2, 3], 'xs', isFiniteNumber, 'a number')).toEqual({ ok: true, data: [1, 2, 3] })
    expect(errorOf(parseArrayOf([1, NaN, 'x'], 'xs', isFiniteNumber, 'a number'))).toBe('xs[1] must be a number, got number NaN')
    expect(errorOf(parseArrayOf([1, 'x'], 'xs', isFiniteNumber, 'a number'))).toBe('xs[1] must be a number, got "x"')
  })
  it('rejects a non-array', () => {
    expect(errorOf(parseArrayOf({ 0: 1 }, 'xs', isFiniteNumber, 'a number'))).toBe('xs must be an array, got an object')
  })
  it('enforces the length only when one is given, naming what the entries are one per', () => {
    expect(parseArrayOf([1, 2], 'xs', isFiniteNumber, 'a number', { n: 3, per: 'day' }).ok).toBe(false)
    expect(errorOf(parseArrayOf([1, 2], 'xs', isFiniteNumber, 'a number', { n: 3, per: 'day' }))).toBe('xs must have 3 entries (one per day), got 2')
    expect(errorOf(parseArrayOf([1, 2, 3, 4], 'xs', isFiniteNumber, 'a number', { n: 3, per: 'day' }))).toBe('xs must have 3 entries (one per day), got 4')
    expect(parseArrayOf([1, 2, 3], 'xs', isFiniteNumber, 'a number', { n: 3, per: 'day' }).ok).toBe(true)
    expect(parseArrayOf([], 'xs', isFiniteNumber, 'a number').ok).toBe(true)
  })
  it('checks the entries before the length', () => {
    expect(errorOf(parseArrayOf([1, 'x'], 'xs', isFiniteNumber, 'a number', { n: 3, per: 'day' }))).toContain('xs[1] must be a number')
  })
  it('returns a copy', () => {
    const input = [1]
    const r = parseArrayOf(input, 'xs', isFiniteNumber, 'a number')
    if (r.ok) expect(r.data).not.toBe(input)
  })
})

describe('parseGrid', () => {
  const rows = { n: 2, per: 'company' }
  const cols = { n: 3, per: 'day' }
  const good = [
    [1, null, 3],
    [4, 5, 6],
  ]
  it('accepts a rectangle of the right size, with null cells', () => {
    expect(parseGrid(good, 'g', rows, cols, isNumberOrNull, 'a number or null')).toEqual({ ok: true, data: good })
  })
  it('refuses a ragged row (too short and too long) and names the row', () => {
    expect(errorOf(parseGrid([[1, 2, 3], [4, 5]], 'g', rows, cols, isNumberOrNull, 'a number or null'))).toBe('g[1] must have 3 entries (one per day), got 2')
    expect(errorOf(parseGrid([[1, 2, 3, 4], [4, 5, 6]], 'g', rows, cols, isNumberOrNull, 'a number or null'))).toBe('g[0] must have 3 entries (one per day), got 4')
  })
  it('refuses the wrong number of rows', () => {
    expect(errorOf(parseGrid([[1, 2, 3]], 'g', rows, cols, isNumberOrNull, 'a number or null'))).toBe('g must have 2 rows (one per company), got 1')
  })
  it('refuses a row that is not an array and a grid that is not an array', () => {
    expect(errorOf(parseGrid([[1, 2, 3], 'abc'], 'g', rows, cols, isNumberOrNull, 'a number or null'))).toBe('g[1] must be an array, got "abc"')
    expect(errorOf(parseGrid(null, 'g', rows, cols, isNumberOrNull, 'a number or null'))).toBe('g must be an array, got null')
  })
  it('refuses a cell of the wrong type and names its position (a string, NaN and undefined are not numbers or null)', () => {
    expect(errorOf(parseGrid([[1, 2, 3], [4, '5', 6]], 'g', rows, cols, isNumberOrNull, 'a number or null'))).toBe('g[1][1] must be a number or null, got "5"')
    expect(errorOf(parseGrid([[1, NaN, 3], [4, 5, 6]], 'g', rows, cols, isNumberOrNull, 'a number or null'))).toBe('g[0][1] must be a number or null, got number NaN')
  })
  it('returns copies of the rows', () => {
    const r = parseGrid(good, 'g', rows, cols, isNumberOrNull, 'a number or null')
    if (!r.ok) throw new Error(r.error)
    expect(r.data).not.toBe(good)
    expect(r.data[0]).not.toBe(good[0])
  })
})

describe('cell predicates', () => {
  it('isNumberOrNull: finite numbers and null only', () => {
    for (const x of [0, -1.5, 1e-22, null]) expect(isNumberOrNull(x), String(x)).toBe(true)
    for (const x of [NaN, Infinity, '1', undefined, true, [], {}]) expect(isNumberOrNull(x), String(x)).toBe(false)
  })
  it('isNonNegIntOrNull: non-negative integers and null only', () => {
    for (const x of [0, 7, null]) expect(isNonNegIntOrNull(x), String(x)).toBe(true)
    for (const x of [-1, 1.5, '1', NaN, undefined]) expect(isNonNegIntOrNull(x), String(x)).toBe(false)
  })
  it('isProbability and isProbabilityOrNull: 0 to 1 inclusive', () => {
    for (const x of [0, 0.5, 1, 4.445e-22]) expect(isProbability(x), String(x)).toBe(true)
    for (const x of [-0.001, 1.000001, NaN, Infinity, '0.5', null]) expect(isProbability(x), String(x)).toBe(false)
    expect(isProbabilityOrNull(null)).toBe(true)
    expect(isProbabilityOrNull(0.3)).toBe(true)
    expect(isProbabilityOrNull(1.5)).toBe(false)
  })
  it('isInteger: any integer, including negative', () => {
    expect(isInteger(-10)).toBe(true)
    expect(isInteger(0)).toBe(true)
    expect(isInteger(1.5)).toBe(false)
    expect(isInteger('1')).toBe(false)
    expect(isInteger(NaN)).toBe(false)
  })
  it('oneOf: exactly the listed strings, nothing coerced', () => {
    const isAB = oneOf('a', 'b')
    expect(isAB('a')).toBe(true)
    expect(isAB('c')).toBe(false)
    expect(isAB('A')).toBe(false)
    expect(isAB(['a'])).toBe(false)
    expect(isAB(null)).toBe(false)
  })
  it('lists the two adjustments', () => {
    expect([...ADJUSTMENTS]).toEqual(['market', 'mean'])
  })
})

describe('parseRelDays', () => {
  it('accepts increasing integers, negative ones included', () => {
    expect(parseRelDays([-10, -9, 0, 10])).toEqual({ ok: true, data: [-10, -9, 0, 10] })
    expect(parseRelDays([3]).ok).toBe(true)
  })
  it.each<[string, unknown, string]>([
    ['not an array', 5, 'rel_days must be an array, got number 5'],
    ['empty', [], 'rel_days must not be empty'],
    ['a fractional day', [0, 0.5], 'rel_days[1] must be an integer, got number 0.5'],
    ['a string day', [0, '1'], 'rel_days[1] must be an integer, got "1"'],
    ['a repeated day', [0, 1, 1], 'rel_days must be strictly increasing, but rel_days[2] (1) is not above rel_days[1] (1)'],
    ['a decreasing day', [2, 1], 'rel_days must be strictly increasing, but rel_days[1] (1) is not above rel_days[0] (2)'],
  ])('rejects %s', (_what, input, message) => {
    expect(errorOf(parseRelDays(input))).toBe(message)
  })
})

describe('loadKind', () => {
  const parse = (data: unknown): Parsed<number> => (typeof data === 'object' && data !== null && 'x' in data ? { ok: true, data: 1 } : fail('x is missing'))
  const body = (patch: Record<string, unknown> = {}) => ({ schema_version: '0.4.0', kind: 'thing', generated_at: '2031-03-04T05:06:07Z', source_commit: 'c', data: { x: 1 }, ...patch })

  it('returns what parse returns for the data of a good envelope of the right kind', async () => {
    expect(await loadKind('u.json', 'thing', parse, serving(body()))).toEqual({ ok: true, data: 1 })
  })
  it('refuses another kind without calling parse', async () => {
    expect(await loadKind('u.json', 'thing', parse, serving(body({ kind: 'other' })))).toEqual({ ok: false, error: 'u.json has kind "other", expected "thing"' })
  })
  it('prefixes the url to a data error and passes an envelope error through unchanged', async () => {
    expect(await loadKind('u.json', 'thing', parse, serving(body({ data: {} })))).toEqual({ ok: false, error: 'u.json: x is missing' })
    expect(await loadKind('u.json', 'thing', parse, fakeFetch({ ok: false, status: 500 }))).toEqual({ ok: false, error: 'u.json returned HTTP 500 (has the Python exporter been run?)' })
  })
})
