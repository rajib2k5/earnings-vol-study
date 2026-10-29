/**
 * Validator for the JSON envelope the Python exporter (`tools/export_app_data.py`) writes around
 * every file in `public/data/`. The app never computes results; it only reads these files, so the
 * first thing it does with any of them is check the envelope.
 *
 * Contract (schema 0.2.0) - exactly these five keys, no more, no fewer:
 *   schema_version  the string "0.2.0"
 *   kind            string, says what `data` holds ("meta" or "sample_funnel")
 *   generated_at    ISO-8601 UTC timestamp ending in "Z", e.g. "2026-10-27T12:00:00Z"
 *   source_commit   string, the git commit of the Python code that produced the file
 *   data            JSON object with the payload
 *
 * The version covers the whole contract: this envelope AND the `data` shape of every kind
 * (`meta.ts` checks "meta", `funnel.ts` checks "sample_funnel"). A change to either bumps it, in
 * the Python exporter and here together.
 *
 * Nothing here throws and nothing is coerced: bad input comes back as `{ ok: false, error }`
 * with a message that says which rule failed.
 */

export const SCHEMA_VERSION = '0.2.0'

const ENVELOPE_KEYS = ['schema_version', 'kind', 'generated_at', 'source_commit', 'data'] as const

export interface Envelope {
  schema_version: typeof SCHEMA_VERSION
  kind: string
  generated_at: string
  source_commit: string
  data: Record<string, unknown>
}

export type ParseResult = { ok: true; envelope: Envelope } | { ok: false; error: string }

const fail = (error: string): ParseResult => ({ ok: false, error })

const isPlainObject = (x: unknown): x is Record<string, unknown> => typeof x === 'object' && x !== null && !Array.isArray(x)

/** Short description of a value for error messages (never dumps a big payload). */
function show(v: unknown): string {
  if (typeof v === 'string') return JSON.stringify(v)
  if (v === null) return 'null'
  if (Array.isArray(v)) return 'an array'
  return typeof v === 'object' ? 'an object' : `${typeof v} ${String(v)}`
}

const ISO_UTC = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?Z$/

/**
 * True for "YYYY-MM-DDTHH:MM:SS[.fraction]Z" that is also a real moment (no Feb 30, no hour 24).
 * `Date.UTC` silently rolls impossible fields over (Feb 30 becomes Mar 2), so we format the result
 * back to ISO and require the same date and time as the input.
 */
export function isIsoUtc(s: string): boolean {
  const m = ISO_UTC.exec(s)
  if (!m) return false
  const [y, mo, d, h, mi, se] = m.slice(1, 7).map(Number)
  const roundTrip = new Date(Date.UTC(y, mo - 1, d, h, mi, se)).toISOString()
  return roundTrip.slice(0, 19) === s.slice(0, 19)
}

export function parseEnvelope(input: unknown): ParseResult {
  if (!isPlainObject(input)) return fail(`envelope must be a JSON object, got ${show(input)}`)

  // Version first: a newer file may legitimately have different keys, and "unsupported version"
  // is a more useful message than "unexpected key".
  if (Object.hasOwn(input, 'schema_version') && input.schema_version !== SCHEMA_VERSION) {
    const v = input.schema_version
    return fail(
      typeof v === 'string'
        ? `unsupported schema_version ${show(v)}: this app only understands "${SCHEMA_VERSION}"`
        : `schema_version must be the string "${SCHEMA_VERSION}", got ${show(v)}`,
    )
  }

  const keys = Object.keys(input)
  const missing = ENVELOPE_KEYS.filter((k) => !Object.hasOwn(input, k))
  const extra = keys.filter((k) => !(ENVELOPE_KEYS as readonly string[]).includes(k))
  if (missing.length > 0 || extra.length > 0) {
    const parts = []
    if (missing.length > 0) parts.push(`missing key(s): ${missing.join(', ')}`)
    if (extra.length > 0) parts.push(`unexpected key(s): ${extra.join(', ')}`)
    return fail(`envelope has ${parts.join('; ')} (expected exactly: ${ENVELOPE_KEYS.join(', ')})`)
  }

  const { kind, generated_at, source_commit, data } = input
  if (typeof kind !== 'string') return fail(`kind must be a string, got ${show(kind)}`)
  if (typeof generated_at !== 'string' || !isIsoUtc(generated_at)) {
    return fail(`generated_at must be an ISO-8601 UTC timestamp ending in "Z" (e.g. 2026-10-27T12:00:00Z), got ${show(generated_at)}`)
  }
  if (typeof source_commit !== 'string') return fail(`source_commit must be a string, got ${show(source_commit)}`)
  if (!isPlainObject(data)) return fail(`data must be a JSON object, got ${show(data)}`)

  return { ok: true, envelope: { schema_version: SCHEMA_VERSION, kind, generated_at, source_commit, data } }
}
