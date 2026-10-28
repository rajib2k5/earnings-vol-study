/**
 * Loads `data/meta.json` (the Python exporter's "what produced this data" file) and turns it into
 * a short summary for the footer. The URL is RELATIVE so the built app works under any sub-path
 * (vite `base: './'`). `fetch` is injectable so tests never touch the network.
 */
import { parseEnvelope, type Envelope, type ParseResult } from './contract'

export const META_URL = 'data/meta.json'

/** Fetch + validate. Never throws: every failure comes back as `{ ok: false, error }`. */
export async function loadMeta(url: string = META_URL, fetchImpl: typeof fetch = (...a) => fetch(...a)): Promise<ParseResult> {
  let res: Response
  try {
    // 'no-cache' = always revalidate with the server: the footer must describe the data actually
    // being served, not a copy the browser kept from an earlier export.
    res = await fetchImpl(url, { cache: 'no-cache' })
  } catch (e) {
    return { ok: false, error: `could not fetch ${url}: ${e instanceof Error ? e.message : String(e)}` }
  }
  if (!res.ok) return { ok: false, error: `${url} returned HTTP ${res.status} (has the Python exporter been run?)` }
  let body: unknown
  try {
    body = await res.json()
  } catch {
    return { ok: false, error: `${url} is not valid JSON (a missing file is often served as an HTML page)` }
  }
  return parseEnvelope(body)
}

export interface MetaSummary {
  schemaVersion: string
  kind: string
  generatedAt: string
  sourceCommit: string
  /**
   * `data.milestone` as the exporter wrote it: a finite, non-negative integer (0 = M0).
   * Anything else (a string, NaN, a negative or fractional number, a missing key) is not
   * coerced: it becomes null and the footer says "unknown".
   */
  milestone: number | null
}

const isMilestone = (m: unknown): m is number => typeof m === 'number' && Number.isInteger(m) && m >= 0

export function summarizeMeta(env: Envelope): MetaSummary {
  const m = env.data.milestone
  return {
    schemaVersion: env.schema_version,
    kind: env.kind,
    generatedAt: env.generated_at,
    sourceCommit: env.source_commit,
    milestone: isMilestone(m) ? m : null,
  }
}

/** "M0", "M1", ... or "unknown" when the exporter gave no usable milestone. */
export function formatMilestone(milestone: number | null): string {
  return milestone === null ? 'unknown' : `M${milestone}`
}

/**
 * One row of the "data sources" table. Python (`tools/export_app_data.py`, `DATA_SOURCES`) is the
 * only place that lists the sources; the About page draws exactly what `meta.json` says.
 */
export interface DataSource {
  name: string
  /** Tables or series used from this source. */
  uses: string
  url: string
  /** Licence name, or "see source" when it has not been confirmed. */
  licence: string
  /** May derived rows from this source be committed to the public repo? */
  committed: boolean
}

/** The licence that covers the committed data, and the attribution text it asks us to show. */
export interface DataLicence {
  name: string
  /** Link to the licence text. */
  url: string
  /** Names of the `data_sources` that this licence covers. */
  applies_to: string[]
  attribution: string
}

/** The `data` object of `meta.json` (kind "meta", schema 0.1.0). */
export interface MetaData {
  project: string
  milestone: number
  title: string
  data_sources: DataSource[]
  data_licence: DataLicence
}

export type MetaDataResult = { ok: true; data: MetaData } | { ok: false; error: string }

const META_DATA_KEYS = ['project', 'milestone', 'title', 'data_sources', 'data_licence'] as const
const DATA_SOURCE_KEYS = ['name', 'uses', 'url', 'licence', 'committed'] as const
const DATA_LICENCE_KEYS = ['name', 'url', 'applies_to', 'attribution'] as const

const bad = (error: string): MetaDataResult => ({ ok: false, error })
const isObject = (x: unknown): x is Record<string, unknown> => typeof x === 'object' && x !== null && !Array.isArray(x)
const isText = (x: unknown): x is string => typeof x === 'string' && x.trim().length > 0
/** https only: the value goes into an `href`, so `javascript:` and `http:` links are refused. */
const isHttpsUrl = (x: unknown): x is string => typeof x === 'string' && /^https:\/\/\S+$/.test(x)

/** Short description of a value for error messages (never dumps a big payload). */
const show = (v: unknown): string => (typeof v === 'string' ? JSON.stringify(v) : Array.isArray(v) ? 'an array' : v === null ? 'null' : typeof v === 'object' ? 'an object' : `${typeof v} ${String(v)}`)

/** A message for an object with missing or unexpected keys, or null when the keys are exactly `expected`. */
function keyProblem(where: string, obj: Record<string, unknown>, expected: readonly string[]): string | null {
  const missing = expected.filter((k) => !Object.hasOwn(obj, k))
  const extra = Object.keys(obj).filter((k) => !expected.includes(k))
  if (missing.length === 0 && extra.length === 0) return null
  const parts = []
  if (missing.length > 0) parts.push(`missing key(s): ${missing.join(', ')}`)
  if (extra.length > 0) parts.push(`unexpected key(s): ${extra.join(', ')}`)
  return `${where} has ${parts.join('; ')} (expected exactly: ${expected.join(', ')})`
}

/**
 * Check the `data` object of a `kind: "meta"` envelope: exactly the keys the Python exporter
 * writes, each of the right type. Nothing throws and nothing is coerced; a failure comes back as
 * `{ ok: false, error }` naming the first rule that failed. The footer does NOT use this (it stays
 * tolerant and shows "milestone unknown"); the About page uses it before it draws the sources table.
 */
export function parseMetaData(input: unknown): MetaDataResult {
  if (!isObject(input)) return bad(`meta data must be a JSON object, got ${show(input)}`)
  const top = keyProblem('meta data', input, META_DATA_KEYS)
  if (top) return bad(top)

  const { project, milestone, title, data_sources, data_licence } = input
  if (!isText(project)) return bad(`project must be a non-empty string, got ${show(project)}`)
  if (!isMilestone(milestone)) return bad(`milestone must be a non-negative integer, got ${show(milestone)}`)
  if (!isText(title)) return bad(`title must be a non-empty string, got ${show(title)}`)

  if (!Array.isArray(data_sources) || data_sources.length === 0) {
    return bad(`data_sources must be a non-empty array, got ${show(data_sources)}`)
  }
  const sources: DataSource[] = []
  for (const [i, s] of data_sources.entries()) {
    const at = `data_sources[${i}]`
    if (!isObject(s)) return bad(`${at} must be an object, got ${show(s)}`)
    const problem = keyProblem(at, s, DATA_SOURCE_KEYS)
    if (problem) return bad(problem)
    if (!isText(s.name)) return bad(`${at}.name must be a non-empty string, got ${show(s.name)}`)
    if (sources.some((o) => o.name === s.name)) return bad(`${at}.name ${show(s.name)} is listed twice`)
    if (!isText(s.uses)) return bad(`${at}.uses must be a non-empty string, got ${show(s.uses)}`)
    if (!isHttpsUrl(s.url)) return bad(`${at}.url must be an https:// URL, got ${show(s.url)}`)
    if (!isText(s.licence)) return bad(`${at}.licence must be a non-empty string, got ${show(s.licence)}`)
    if (typeof s.committed !== 'boolean') return bad(`${at}.committed must be true or false, got ${show(s.committed)}`)
    sources.push({ name: s.name, uses: s.uses, url: s.url, licence: s.licence, committed: s.committed })
  }

  if (!isObject(data_licence)) return bad(`data_licence must be an object, got ${show(data_licence)}`)
  const licenceProblem = keyProblem('data_licence', data_licence, DATA_LICENCE_KEYS)
  if (licenceProblem) return bad(licenceProblem)
  const { applies_to } = data_licence
  if (!isText(data_licence.name)) return bad(`data_licence.name must be a non-empty string, got ${show(data_licence.name)}`)
  if (!isHttpsUrl(data_licence.url)) return bad(`data_licence.url must be an https:// URL, got ${show(data_licence.url)}`)
  if (!isText(data_licence.attribution)) return bad(`data_licence.attribution must be a non-empty string, got ${show(data_licence.attribution)}`)
  if (!Array.isArray(applies_to)) return bad(`data_licence.applies_to must be an array, got ${show(applies_to)}`)
  for (const [i, n] of applies_to.entries()) {
    const covered = sources.find((s) => s.name === n)
    if (!covered) {
      return bad(`data_licence.applies_to[${i}] must name one of the data_sources, got ${show(n)}`)
    }
    // The licence says it covers this source, so the source row must carry that licence's name:
    // a mismatch means one of the two was edited without the other.
    if (covered.licence !== data_licence.name) {
      return bad(`data_licence.applies_to[${i}] ${show(n)} is covered by ${show(data_licence.name)}, but data_sources lists its licence as ${show(covered.licence)}`)
    }
  }

  return {
    ok: true,
    data: {
      project,
      milestone,
      title,
      data_sources: sources,
      data_licence: { name: data_licence.name, url: data_licence.url, applies_to: [...applies_to], attribution: data_licence.attribution },
    },
  }
}
