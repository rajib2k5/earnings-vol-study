/**
 * Pieces shared by the parsers of the milestone-3 files (`results.ts` for tests.json, `eventPaths.ts`,
 * `terrainData.ts`, `heatmap.ts`): the `lookups` and `caveats` fields every one of them carries,
 * checked arrays and grids, and the fetch + envelope + kind + shape pipeline. Like `validate.ts` it is
 * pure: nothing throws, nothing is coerced, and a failure comes back as `{ ok: false, error }` with
 * a message that names the rule.
 */
import { loadEnvelope } from './meta'
import { fail, isFiniteNumber, isNonNegInt, isObject, isText, keyProblem, show, type Parsed } from './validate'

/** Which timing look-ups are done: while `complete` is false the timing labels are provisional. */
export interface Lookups {
  n_done: number
  complete: boolean
}

const LOOKUPS_KEYS = ['n_done', 'complete'] as const

export function parseLookups(input: unknown): Parsed<Lookups> {
  if (!isObject(input)) return fail(`lookups must be an object, got ${show(input)}`)
  const problem = keyProblem('lookups', input, LOOKUPS_KEYS)
  if (problem) return fail(problem)
  const { n_done, complete } = input
  if (!isNonNegInt(n_done)) return fail(`lookups.n_done must be a non-negative integer, got ${show(n_done)}`)
  if (typeof complete !== 'boolean') return fail(`lookups.complete must be true or false, got ${show(complete)}`)
  return { ok: true, data: { n_done, complete } }
}

/** An array of non-empty strings: the caveats shown next to the numbers. */
export function parseCaveats(input: unknown): Parsed<string[]> {
  return parseArrayOf(input, 'caveats', isText, 'a non-empty string')
}

/** How the length of an array is tied to something else in the file, for the error message. */
export interface LengthRule {
  n: number
  /** What the entries are one per, e.g. "rel_days entry". */
  per: string
}

/**
 * An array whose every entry passes `test`. `expected` finishes the sentence "... must be <expected>"
 * in the message. With `length` the array must also have exactly that many entries.
 */
export function parseArrayOf<T>(input: unknown, where: string, test: (x: unknown) => x is T, expected: string, length?: LengthRule): Parsed<T[]> {
  if (!Array.isArray(input)) return fail(`${where} must be an array, got ${show(input)}`)
  for (const [i, x] of input.entries()) {
    if (!test(x)) return fail(`${where}[${i}] must be ${expected}, got ${show(x)}`)
  }
  if (length && input.length !== length.n) {
    return fail(`${where} must have ${length.n} entries (one per ${length.per}), got ${input.length}`)
  }
  return { ok: true, data: [...(input as T[])] }
}

/**
 * A rows x cols grid. The row count and the width of every row are checked first (a ragged row is
 * refused), then every cell with `test`.
 */
export function parseGrid<T>(
  input: unknown,
  where: string,
  rows: LengthRule,
  cols: LengthRule,
  test: (x: unknown) => x is T,
  expected: string,
): Parsed<T[][]> {
  if (!Array.isArray(input)) return fail(`${where} must be an array, got ${show(input)}`)
  if (input.length !== rows.n) return fail(`${where} must have ${rows.n} rows (one per ${rows.per}), got ${input.length}`)
  const out: T[][] = []
  for (const [i, row] of input.entries()) {
    const cells = parseArrayOf(row, `${where}[${i}]`, test, expected, cols)
    if (!cells.ok) return cells
    out.push(cells.data)
  }
  return { ok: true, data: out }
}

/** A finite number or null (null is how the exporter marks a missing value). */
export const isNumberOrNull = (x: unknown): x is number | null => x === null || isFiniteNumber(x)
/** A non-negative integer or null. */
export const isNonNegIntOrNull = (x: unknown): x is number | null => x === null || isNonNegInt(x)
/** A probability or share: a number from 0 to 1, both ends included. */
export const isProbability = (x: unknown): x is number => typeof x === 'number' && x >= 0 && x <= 1
/** A probability or null. */
export const isProbabilityOrNull = (x: unknown): x is number | null => x === null || isProbability(x)
export const isInteger = (x: unknown): x is number => typeof x === 'number' && Number.isInteger(x)

/** A predicate for "one of these strings". */
export const oneOf =
  <T extends string>(...values: readonly T[]) =>
  (x: unknown): x is T =>
    typeof x === 'string' && (values as readonly string[]).includes(x)

export const ADJUSTMENTS = ['market', 'mean'] as const
/** How an abnormal value was adjusted: against the market (VIX, beta per company) or against the company's own baseline mean. */
export type Adjustment = (typeof ADJUSTMENTS)[number]

/** `rel_days`: the event days of the x axis, as integers, strictly increasing, at least one. */
export function parseRelDays(input: unknown): Parsed<number[]> {
  const days = parseArrayOf(input, 'rel_days', isInteger, 'an integer')
  if (!days.ok) return days
  if (days.data.length === 0) return fail('rel_days must not be empty')
  for (const [i, d] of days.data.entries()) {
    if (i > 0 && d <= days.data[i - 1]) {
      return fail(`rel_days must be strictly increasing, but rel_days[${i}] (${d}) is not above rel_days[${i - 1}] (${days.data[i - 1]})`)
    }
  }
  return days
}

/**
 * Fetch + validate one of the data files: the envelope first (`parseEnvelope`, through `loadEnvelope`),
 * then `kind`, then the `data` shape with `parse`. Never throws: every failure comes back as
 * `{ ok: false, error }`, prefixed with the url when it is about the data.
 */
export async function loadKind<T>(url: string, kind: string, parse: (data: unknown) => Parsed<T>, fetchImpl?: typeof fetch): Promise<Parsed<T>> {
  const r = await loadEnvelope(url, fetchImpl)
  if (!r.ok) return r
  if (r.envelope.kind !== kind) return fail(`${url} has kind ${show(r.envelope.kind)}, expected "${kind}"`)
  const parsed = parse(r.envelope.data)
  return parsed.ok ? parsed : fail(`${url}: ${parsed.error}`)
}
