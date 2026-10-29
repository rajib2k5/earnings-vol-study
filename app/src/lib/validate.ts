/**
 * Small checks shared by the data validators (`meta.ts`, `funnel.ts`, `provenance.ts`). All pure:
 * nothing throws and nothing is coerced. A value either is the type asked for or it is not.
 */

/** What every `parse...` function returns: the checked data, or the first rule that failed. */
export type Parsed<T> = { ok: true; data: T } | { ok: false; error: string }

export const fail = (error: string): { ok: false; error: string } => ({ ok: false, error })

export const isObject = (x: unknown): x is Record<string, unknown> => typeof x === 'object' && x !== null && !Array.isArray(x)
export const isText = (x: unknown): x is string => typeof x === 'string' && x.trim().length > 0
export const isNonNegInt = (x: unknown): x is number => typeof x === 'number' && Number.isInteger(x) && x >= 0
export const isPositiveInt = (x: unknown): x is number => typeof x === 'number' && Number.isInteger(x) && x >= 1
/** `[a, b]` with both entries integers (negative is fine: session offsets are relative to day 0). */
export const isIntPair = (x: unknown): x is [number, number] =>
  Array.isArray(x) && x.length === 2 && x.every((n) => typeof n === 'number' && Number.isInteger(n))

const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/

/**
 * True for "YYYY-MM-DD" that is also a real calendar date. `Date.UTC` rolls impossible fields over
 * (Feb 30 becomes Mar 2), so the date is formatted back and must equal the input.
 */
export function isIsoDate(x: unknown): x is string {
  if (typeof x !== 'string') return false
  const m = ISO_DATE.exec(x)
  if (!m) return false
  const [y, mo, d] = m.slice(1).map(Number)
  return new Date(Date.UTC(y, mo - 1, d)).toISOString().slice(0, 10) === x
}

/** Short description of a value for error messages (never dumps a big payload). */
export const show = (v: unknown): string =>
  typeof v === 'string' ? JSON.stringify(v) : Array.isArray(v) ? 'an array' : v === null ? 'null' : typeof v === 'object' ? 'an object' : `${typeof v} ${String(v)}`

/** A message for an object with missing or unexpected keys, or null when the keys are exactly `expected`. */
export function keyProblem(where: string, obj: Record<string, unknown>, expected: readonly string[]): string | null {
  const missing = expected.filter((k) => !Object.hasOwn(obj, k))
  const extra = Object.keys(obj).filter((k) => !expected.includes(k))
  if (missing.length === 0 && extra.length === 0) return null
  const parts = []
  if (missing.length > 0) parts.push(`missing key(s): ${missing.join(', ')}`)
  if (extra.length > 0) parts.push(`unexpected key(s): ${extra.join(', ')}`)
  return `${where} has ${parts.join('; ')} (expected exactly: ${expected.join(', ')})`
}
