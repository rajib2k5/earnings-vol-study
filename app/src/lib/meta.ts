/**
 * Loads `data/meta.json` (the Python exporter's "what produced this data" file) and turns it into
 * a short summary for the footer. The URL is RELATIVE so the built app works under any sub-path
 * (vite `base: './'`). `fetch` is injectable so tests never touch the network.
 */
import { parseEnvelope, type Envelope, type ParseResult } from './contract'
import { parseProvenance, type Provenance } from './provenance'
import { fail, isIntPair, isIsoDate, isNonNegInt, isObject, isPositiveInt, isText, keyProblem, show, type Parsed } from './validate'

export const META_URL = 'data/meta.json'

/**
 * Fetch + validate the envelope of any file in `public/data/`. Never throws: every failure comes
 * back as `{ ok: false, error }`.
 */
export async function loadEnvelope(url: string, fetchImpl: typeof fetch = (...a) => fetch(...a)): Promise<ParseResult> {
  let res: Response
  try {
    // 'no-cache' = always revalidate with the server: the page must describe the data actually
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

/** Fetch + validate `data/meta.json`'s envelope. Never throws. */
export const loadMeta = (url: string = META_URL, fetchImpl?: typeof fetch): Promise<ParseResult> => loadEnvelope(url, fetchImpl)

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

/** Which events the exported numbers describe (the "daily" sample is the one with a day-0 date range). */
export interface MetaSample {
  label: string
  /** First and last day 0, "YYYY-MM-DD". */
  day0_from: string
  day0_to: string
  n_events: number
  n_securities: number
}

/** The study parameters the Python side ran with. Windows are `[from, to]` session offsets from day 0. */
export interface MetaParams {
  event_window: [number, number]
  baseline: [number, number]
  baseline_exclusion: [number, number]
  cm30_horizon_sessions: number
  clock: string
}

/** The `data` object of `meta.json` (kind "meta", schema 0.5.0). */
export interface MetaData {
  project: string
  milestone: number
  title: string
  data_sources: DataSource[]
  data_licence: DataLicence
  sample: MetaSample
  params: MetaParams
  /** The kinds of file available in `public/data/` (e.g. "meta", "sample_funnel", "iv_measures"). */
  files: string[]
  provenance: Provenance
}

export type MetaDataResult = Parsed<MetaData>

const META_DATA_KEYS = ['project', 'milestone', 'title', 'data_sources', 'data_licence', 'sample', 'params', 'files', 'provenance'] as const
const DATA_SOURCE_KEYS = ['name', 'uses', 'url', 'licence', 'committed'] as const
const DATA_LICENCE_KEYS = ['name', 'url', 'applies_to', 'attribution'] as const
const SAMPLE_KEYS = ['label', 'day0_from', 'day0_to', 'n_events', 'n_securities'] as const
const PARAMS_KEYS = ['event_window', 'baseline', 'baseline_exclusion', 'cm30_horizon_sessions', 'clock'] as const

const bad = fail
/** https only: the value goes into an `href`, so `javascript:` and `http:` links are refused. */
const isHttpsUrl = (x: unknown): x is string => typeof x === 'string' && /^https:\/\/\S+$/.test(x)

function parseSample(input: unknown): Parsed<MetaSample> {
  if (!isObject(input)) return bad(`sample must be an object, got ${show(input)}`)
  const problem = keyProblem('sample', input, SAMPLE_KEYS)
  if (problem) return bad(problem)
  const { label, day0_from, day0_to, n_events, n_securities } = input
  if (!isText(label)) return bad(`sample.label must be a non-empty string, got ${show(label)}`)
  if (!isIsoDate(day0_from)) return bad(`sample.day0_from must be a date string YYYY-MM-DD, got ${show(day0_from)}`)
  if (!isIsoDate(day0_to)) return bad(`sample.day0_to must be a date string YYYY-MM-DD, got ${show(day0_to)}`)
  if (!isNonNegInt(n_events)) return bad(`sample.n_events must be a non-negative integer, got ${show(n_events)}`)
  if (!isNonNegInt(n_securities)) return bad(`sample.n_securities must be a non-negative integer, got ${show(n_securities)}`)
  return { ok: true, data: { label, day0_from, day0_to, n_events, n_securities } }
}

function parseParams(input: unknown): Parsed<MetaParams> {
  if (!isObject(input)) return bad(`params must be an object, got ${show(input)}`)
  const problem = keyProblem('params', input, PARAMS_KEYS)
  if (problem) return bad(problem)
  const { event_window, baseline, baseline_exclusion, cm30_horizon_sessions, clock } = input
  if (!isIntPair(event_window)) return bad(`params.event_window must be an array of two integers, got ${show(event_window)}`)
  if (!isIntPair(baseline)) return bad(`params.baseline must be an array of two integers, got ${show(baseline)}`)
  if (!isIntPair(baseline_exclusion)) return bad(`params.baseline_exclusion must be an array of two integers, got ${show(baseline_exclusion)}`)
  if (!isPositiveInt(cm30_horizon_sessions)) return bad(`params.cm30_horizon_sessions must be a positive integer, got ${show(cm30_horizon_sessions)}`)
  if (!isText(clock)) return bad(`params.clock must be a non-empty string, got ${show(clock)}`)
  return {
    ok: true,
    data: {
      event_window: [...event_window],
      baseline: [...baseline],
      baseline_exclusion: [...baseline_exclusion],
      cm30_horizon_sessions,
      clock,
    },
  }
}

function parseFiles(input: unknown): Parsed<string[]> {
  if (!Array.isArray(input) || input.length === 0) return bad(`files must be a non-empty array, got ${show(input)}`)
  for (const [i, f] of input.entries()) {
    if (!isText(f)) return bad(`files[${i}] must be a non-empty string, got ${show(f)}`)
  }
  return { ok: true, data: [...input] }
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

  const sample = parseSample(input.sample)
  if (!sample.ok) return sample
  const params = parseParams(input.params)
  if (!params.ok) return params
  const files = parseFiles(input.files)
  if (!files.ok) return files
  const provenance = parseProvenance(input.provenance)
  if (!provenance.ok) return provenance

  return {
    ok: true,
    data: {
      project,
      milestone,
      title,
      data_sources: sources,
      data_licence: { name: data_licence.name, url: data_licence.url, applies_to: [...applies_to], attribution: data_licence.attribution },
      sample: sample.data,
      params: params.data,
      files: files.data,
      provenance: provenance.data,
    },
  }
}
