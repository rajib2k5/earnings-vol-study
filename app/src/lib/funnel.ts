/**
 * Loads and checks `data/sample_funnel.json` (kind "sample_funnel", schema 0.2.0): how many
 * earnings events survive each filtering step, written by the Python exporter. The app only draws
 * these counts; it never recomputes them. Like `meta.ts`, `fetch` is injected so tests never touch
 * the network, and nothing here throws or coerces.
 *
 * The `data` object has exactly these keys:
 *   steps                      non-empty array of { step, label, n_events, n_removed, reason }
 *   timing_status_counts       the 7 timing statuses, each a count
 *   timing_status_by_sample    per sample: { sample, timing_status_counts }
 *   by_sample                  per sample: { sample, n_events }
 *   by_move_tercile            null at 0.2.0 (see below)
 *   by_move_tercile_status     string saying why it is null
 *   evar_nonpositive           null at 0.2.0 (see below)
 *   evar_nonpositive_status    string saying why it is null
 *   lookups                    { n_done, complete }
 *   caveats                    array of strings, shown next to the numbers
 *   provenance                 same object as in meta.json (see `provenance.ts`)
 */
import { SCHEMA_VERSION } from './contract'
import { loadEnvelope } from './meta'
import { parseProvenance, type Provenance } from './provenance'
import { fail, isNonNegInt, isObject, isText, keyProblem, show, type Parsed } from './validate'

export const SAMPLE_FUNNEL_URL = 'data/sample_funnel.json'
export const SAMPLE_FUNNEL_KIND = 'sample_funnel'

/** The four samples an event can fall in (by how precisely its day 0 is known). */
export const SAMPLE_NAMES = ['daily', 'mixed', 'coarse', 'none'] as const
export type SampleName = (typeof SAMPLE_NAMES)[number]

/** The seven timing statuses, in the order the page draws them. */
export const TIMING_STATUSES = ['confirmed', 'corrected', 'inferred', 'date_corrected', 'no_document', 'not_checked', 'ambiguous'] as const
export type TimingStatus = (typeof TIMING_STATUSES)[number]
export type TimingStatusCounts = Record<TimingStatus, number>

export interface FunnelStep {
  step: string
  label: string
  n_events: number
  n_removed: number
  /** Why events were removed at this step, or null when none were. */
  reason: string | null
}

export interface SampleFunnel {
  steps: FunnelStep[]
  timing_status_counts: TimingStatusCounts
  timing_status_by_sample: { sample: SampleName; timing_status_counts: TimingStatusCounts }[]
  by_sample: { sample: SampleName; n_events: number }[]
  /**
   * Always null at schema 0.2.0: the move terciles need milestone 2. An array is reserved for
   * milestone 2 and is rejected until the contract version that defines it.
   */
  by_move_tercile: null
  by_move_tercile_status: string
  /** Always null at schema 0.2.0, same rule as `by_move_tercile`. */
  evar_nonpositive: null
  evar_nonpositive_status: string
  lookups: { n_done: number; complete: boolean }
  caveats: string[]
  provenance: Provenance
}

export type SampleFunnelResult = Parsed<SampleFunnel>

const FUNNEL_KEYS = [
  'steps',
  'timing_status_counts',
  'timing_status_by_sample',
  'by_sample',
  'by_move_tercile',
  'by_move_tercile_status',
  'evar_nonpositive',
  'evar_nonpositive_status',
  'lookups',
  'caveats',
  'provenance',
] as const
const STEP_KEYS = ['step', 'label', 'n_events', 'n_removed', 'reason'] as const
const TIMING_BY_SAMPLE_KEYS = ['sample', 'timing_status_counts'] as const
const BY_SAMPLE_KEYS = ['sample', 'n_events'] as const
const LOOKUPS_KEYS = ['n_done', 'complete'] as const

const isSampleName = (x: unknown): x is SampleName => typeof x === 'string' && (SAMPLE_NAMES as readonly string[]).includes(x)

function parseSteps(input: unknown): Parsed<FunnelStep[]> {
  if (!Array.isArray(input) || input.length === 0) return fail(`steps must be a non-empty array, got ${show(input)}`)
  const steps: FunnelStep[] = []
  for (const [i, s] of input.entries()) {
    const at = `steps[${i}]`
    if (!isObject(s)) return fail(`${at} must be an object, got ${show(s)}`)
    const problem = keyProblem(at, s, STEP_KEYS)
    if (problem) return fail(problem)
    const { step, label, n_events, n_removed, reason } = s
    if (!isText(step)) return fail(`${at}.step must be a non-empty string, got ${show(step)}`)
    if (!isText(label)) return fail(`${at}.label must be a non-empty string, got ${show(label)}`)
    if (!isNonNegInt(n_events)) return fail(`${at}.n_events must be a non-negative integer, got ${show(n_events)}`)
    if (!isNonNegInt(n_removed)) return fail(`${at}.n_removed must be a non-negative integer, got ${show(n_removed)}`)
    if (reason !== null && typeof reason !== 'string') return fail(`${at}.reason must be a string or null, got ${show(reason)}`)
    steps.push({ step, label, n_events, n_removed, reason })
  }
  return { ok: true, data: steps }
}

/** `where` is the path used in messages, e.g. "timing_status_counts". */
function parseTimingCounts(input: unknown, where: string): Parsed<TimingStatusCounts> {
  if (!isObject(input)) return fail(`${where} must be an object, got ${show(input)}`)
  const problem = keyProblem(where, input, TIMING_STATUSES)
  if (problem) return fail(problem)
  const counts = {} as TimingStatusCounts
  for (const status of TIMING_STATUSES) {
    const n = input[status]
    if (!isNonNegInt(n)) return fail(`${where}.${status} must be a non-negative integer, got ${show(n)}`)
    counts[status] = n
  }
  return { ok: true, data: counts }
}

function parseTimingBySample(input: unknown): Parsed<SampleFunnel['timing_status_by_sample']> {
  if (!Array.isArray(input)) return fail(`timing_status_by_sample must be an array, got ${show(input)}`)
  const rows: SampleFunnel['timing_status_by_sample'] = []
  for (const [i, row] of input.entries()) {
    const at = `timing_status_by_sample[${i}]`
    if (!isObject(row)) return fail(`${at} must be an object, got ${show(row)}`)
    const problem = keyProblem(at, row, TIMING_BY_SAMPLE_KEYS)
    if (problem) return fail(problem)
    if (!isSampleName(row.sample)) return fail(`${at}.sample must be one of ${SAMPLE_NAMES.join(', ')}, got ${show(row.sample)}`)
    const counts = parseTimingCounts(row.timing_status_counts, `${at}.timing_status_counts`)
    if (!counts.ok) return counts
    rows.push({ sample: row.sample, timing_status_counts: counts.data })
  }
  return { ok: true, data: rows }
}

function parseBySample(input: unknown): Parsed<SampleFunnel['by_sample']> {
  if (!Array.isArray(input)) return fail(`by_sample must be an array, got ${show(input)}`)
  const rows: SampleFunnel['by_sample'] = []
  for (const [i, row] of input.entries()) {
    const at = `by_sample[${i}]`
    if (!isObject(row)) return fail(`${at} must be an object, got ${show(row)}`)
    const problem = keyProblem(at, row, BY_SAMPLE_KEYS)
    if (problem) return fail(problem)
    if (!isSampleName(row.sample)) return fail(`${at}.sample must be one of ${SAMPLE_NAMES.join(', ')}, got ${show(row.sample)}`)
    if (!isNonNegInt(row.n_events)) return fail(`${at}.n_events must be a non-negative integer, got ${show(row.n_events)}`)
    rows.push({ sample: row.sample, n_events: row.n_events })
  }
  return { ok: true, data: rows }
}

/**
 * Check the `data` object of a `kind: "sample_funnel"` envelope: exactly the keys above, each of
 * the right type. Nothing throws and nothing is coerced; a failure comes back as
 * `{ ok: false, error }` naming the first rule that failed.
 */
export function parseSampleFunnel(input: unknown): SampleFunnelResult {
  if (!isObject(input)) return fail(`sample funnel data must be a JSON object, got ${show(input)}`)
  const top = keyProblem('sample funnel data', input, FUNNEL_KEYS)
  if (top) return fail(top)

  const steps = parseSteps(input.steps)
  if (!steps.ok) return steps
  const timing = parseTimingCounts(input.timing_status_counts, 'timing_status_counts')
  if (!timing.ok) return timing
  const timingBySample = parseTimingBySample(input.timing_status_by_sample)
  if (!timingBySample.ok) return timingBySample
  const bySample = parseBySample(input.by_sample)
  if (!bySample.ok) return bySample

  // Milestone 2 will define what an array looks like here; until the contract version that does
  // (a bump from 0.2.0), the only valid value is null and the *_status string says why.
  const { by_move_tercile, by_move_tercile_status, evar_nonpositive, evar_nonpositive_status, lookups, caveats } = input
  if (by_move_tercile !== null) return fail(`by_move_tercile must be null at schema ${SCHEMA_VERSION} (an array is reserved for milestone 2), got ${show(by_move_tercile)}`)
  if (!isText(by_move_tercile_status)) return fail(`by_move_tercile_status must be a non-empty string, got ${show(by_move_tercile_status)}`)
  if (evar_nonpositive !== null) return fail(`evar_nonpositive must be null at schema ${SCHEMA_VERSION} (an array is reserved for milestone 2), got ${show(evar_nonpositive)}`)
  if (!isText(evar_nonpositive_status)) return fail(`evar_nonpositive_status must be a non-empty string, got ${show(evar_nonpositive_status)}`)

  if (!isObject(lookups)) return fail(`lookups must be an object, got ${show(lookups)}`)
  const lookupsProblem = keyProblem('lookups', lookups, LOOKUPS_KEYS)
  if (lookupsProblem) return fail(lookupsProblem)
  if (!isNonNegInt(lookups.n_done)) return fail(`lookups.n_done must be a non-negative integer, got ${show(lookups.n_done)}`)
  if (typeof lookups.complete !== 'boolean') return fail(`lookups.complete must be true or false, got ${show(lookups.complete)}`)

  if (!Array.isArray(caveats)) return fail(`caveats must be an array, got ${show(caveats)}`)
  for (const [i, c] of caveats.entries()) {
    if (!isText(c)) return fail(`caveats[${i}] must be a non-empty string, got ${show(c)}`)
  }

  const provenance = parseProvenance(input.provenance)
  if (!provenance.ok) return provenance

  return {
    ok: true,
    data: {
      steps: steps.data,
      timing_status_counts: timing.data,
      timing_status_by_sample: timingBySample.data,
      by_sample: bySample.data,
      by_move_tercile: null,
      by_move_tercile_status,
      evar_nonpositive: null,
      evar_nonpositive_status,
      lookups: { n_done: lookups.n_done, complete: lookups.complete },
      caveats: [...caveats],
      provenance: provenance.data,
    },
  }
}

/**
 * Fetch + validate `data/sample_funnel.json`: the envelope first (`parseEnvelope`, through
 * `loadEnvelope`), then `kind`, then the `data` shape. Never throws: every failure comes back as
 * `{ ok: false, error }`.
 */
export async function loadSampleFunnel(url: string = SAMPLE_FUNNEL_URL, fetchImpl?: typeof fetch): Promise<SampleFunnelResult> {
  const r = await loadEnvelope(url, fetchImpl)
  if (!r.ok) return r
  if (r.envelope.kind !== SAMPLE_FUNNEL_KIND) {
    return fail(`${url} has kind ${show(r.envelope.kind)}, expected "${SAMPLE_FUNNEL_KIND}"`)
  }
  const parsed = parseSampleFunnel(r.envelope.data)
  return parsed.ok ? parsed : fail(`${url}: ${parsed.error}`)
}
