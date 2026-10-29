/**
 * Loads and checks `data/sample_funnel.json` (kind "sample_funnel", schema 0.3.0): how many
 * earnings events survive each filtering step, written by the Python exporter. The app only draws
 * these counts; it never recomputes them. Like `meta.ts`, `fetch` is injected so tests never touch
 * the network, and nothing here throws or coerces.
 *
 * The `data` object has exactly these keys:
 *   steps                      non-empty array of { step, label, n_events, n_removed, reason }
 *   timing_status_counts       the 7 timing statuses, each a count
 *   timing_status_by_sample    per sample: { sample, timing_status_counts }
 *   by_sample                  per sample: { sample, n_events }
 *   by_move_tercile            null (not computed) or an array of per-sample, per-tercile rows
 *   by_move_tercile_status     string saying how it was computed, or why it is null
 *   evar_nonpositive           null (not computed) or { n_events, n_identified, n, share }
 *   evar_nonpositive_status    string saying how it was computed, or why it is null
 *   lookups                    { n_done, complete }
 *   caveats                    array of strings, shown next to the numbers
 *   provenance                 same object as in meta.json (see `provenance.ts`)
 */
import { loadEnvelope } from './meta'
import { parseProvenance, type Provenance } from './provenance'
import { fail, isFiniteNumber, isNonNegInt, isObject, isText, isUnitInterval, keyProblem, show, type Parsed } from './validate'

export const SAMPLE_FUNNEL_URL = 'data/sample_funnel.json'
export const SAMPLE_FUNNEL_KIND = 'sample_funnel'

/** The four samples an event can fall in (by how precisely its day 0 is known). */
export const SAMPLE_NAMES = ['daily', 'mixed', 'coarse', 'none'] as const
export type SampleName = (typeof SAMPLE_NAMES)[number]

/** The seven timing statuses, in the order the page draws them. */
export const TIMING_STATUSES = ['confirmed', 'corrected', 'inferred', 'date_corrected', 'no_document', 'not_checked', 'ambiguous'] as const
export type TimingStatus = (typeof TIMING_STATUSES)[number]
export type TimingStatusCounts = Record<TimingStatus, number>

/** The samples that have move terciles ("none" has no day 0, so no move). */
export const TERCILE_SAMPLE_NAMES = ['daily', 'mixed', 'coarse'] as const
export type TercileSampleName = (typeof TERCILE_SAMPLE_NAMES)[number]

export interface FunnelStep {
  step: string
  label: string
  n_events: number
  n_removed: number
  /** Why events were removed at this step, or null when none were. */
  reason: string | null
}

/** One row of `by_move_tercile`: the events of one sample in one tercile of the implied move. */
export interface MoveTercileRow {
  sample: TercileSampleName
  tercile: 1 | 2 | 3
  n_events: number
  timing_status_counts: TimingStatusCounts
  /** Share of events whose Yahoo gap check contradicts the timing label, or null when not available. */
  share_gap_contradicts: number | null
  n_gap_check_changed: number
  mean_abs_move: number | null
  /** How many events of the row have a crush (at most `n_events`). */
  n_crush: number
  mean_crush_mean_adj: number | null
}

/** `evar_nonpositive`: how many events have a non-positive event variance E at day -1. */
export interface EvarNonpositive {
  n_events: number
  n_identified: number
  n: number
  /** As given by the exporter; null only when `n_identified` is 0. */
  share: number | null
}

export interface SampleFunnel {
  steps: FunnelStep[]
  timing_status_counts: TimingStatusCounts
  timing_status_by_sample: { sample: SampleName; timing_status_counts: TimingStatusCounts }[]
  by_sample: { sample: SampleName; n_events: number }[]
  /** Null while not computed (the status string says why); at 0.3.0 the exporter fills it. */
  by_move_tercile: MoveTercileRow[] | null
  by_move_tercile_status: string
  /** Null while not computed, same rule as `by_move_tercile`. */
  evar_nonpositive: EvarNonpositive | null
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
const TERCILE_ROW_KEYS = [
  'sample',
  'tercile',
  'n_events',
  'timing_status_counts',
  'share_gap_contradicts',
  'n_gap_check_changed',
  'mean_abs_move',
  'n_crush',
  'mean_crush_mean_adj',
] as const
const EVAR_KEYS = ['n_events', 'n_identified', 'n', 'share'] as const

const isSampleName = (x: unknown): x is SampleName => typeof x === 'string' && (SAMPLE_NAMES as readonly string[]).includes(x)
const isTercileSampleName = (x: unknown): x is TercileSampleName => typeof x === 'string' && (TERCILE_SAMPLE_NAMES as readonly string[]).includes(x)
const isTercile = (x: unknown): x is 1 | 2 | 3 => x === 1 || x === 2 || x === 3

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

/** `by_move_tercile`: null, or an array (possibly empty) of rows with exactly `TERCILE_ROW_KEYS`. */
function parseByMoveTercile(input: unknown): Parsed<MoveTercileRow[] | null> {
  if (input === null) return { ok: true, data: null }
  if (!Array.isArray(input)) return fail(`by_move_tercile must be null or an array, got ${show(input)}`)
  const rows: MoveTercileRow[] = []
  for (const [i, row] of input.entries()) {
    const at = `by_move_tercile[${i}]`
    if (!isObject(row)) return fail(`${at} must be an object, got ${show(row)}`)
    const problem = keyProblem(at, row, TERCILE_ROW_KEYS)
    if (problem) return fail(problem)
    const { sample, tercile, n_events, share_gap_contradicts, n_gap_check_changed, mean_abs_move, n_crush, mean_crush_mean_adj } = row
    if (!isTercileSampleName(sample)) return fail(`${at}.sample must be one of ${TERCILE_SAMPLE_NAMES.join(', ')}, got ${show(sample)}`)
    if (!isTercile(tercile)) return fail(`${at}.tercile must be 1, 2 or 3, got ${show(tercile)}`)
    if (!isNonNegInt(n_events)) return fail(`${at}.n_events must be a non-negative integer, got ${show(n_events)}`)
    const counts = parseTimingCounts(row.timing_status_counts, `${at}.timing_status_counts`)
    if (!counts.ok) return counts
    if (share_gap_contradicts !== null && !isUnitInterval(share_gap_contradicts)) {
      return fail(`${at}.share_gap_contradicts must be a number from 0 to 1, or null, got ${show(share_gap_contradicts)}`)
    }
    if (!isNonNegInt(n_gap_check_changed)) return fail(`${at}.n_gap_check_changed must be a non-negative integer, got ${show(n_gap_check_changed)}`)
    if (mean_abs_move !== null && !isFiniteNumber(mean_abs_move)) return fail(`${at}.mean_abs_move must be a finite number or null, got ${show(mean_abs_move)}`)
    if (!isNonNegInt(n_crush)) return fail(`${at}.n_crush must be a non-negative integer, got ${show(n_crush)}`)
    if (n_crush > n_events) return fail(`${at}.n_crush must be at most n_events (${n_events}), got number ${n_crush}`)
    if (mean_crush_mean_adj !== null && !isFiniteNumber(mean_crush_mean_adj)) {
      return fail(`${at}.mean_crush_mean_adj must be a finite number or null, got ${show(mean_crush_mean_adj)}`)
    }
    rows.push({ sample, tercile, n_events, timing_status_counts: counts.data, share_gap_contradicts, n_gap_check_changed, mean_abs_move, n_crush, mean_crush_mean_adj })
  }
  return { ok: true, data: rows }
}

/** `evar_nonpositive`: null, or an object with exactly `EVAR_KEYS` and n <= n_identified <= n_events. */
function parseEvarNonpositive(input: unknown): Parsed<EvarNonpositive | null> {
  if (input === null) return { ok: true, data: null }
  if (!isObject(input)) return fail(`evar_nonpositive must be null or an object, got ${show(input)}`)
  const problem = keyProblem('evar_nonpositive', input, EVAR_KEYS)
  if (problem) return fail(problem)
  const { n_events, n_identified, n, share } = input
  if (!isNonNegInt(n_events)) return fail(`evar_nonpositive.n_events must be a non-negative integer, got ${show(n_events)}`)
  if (!isNonNegInt(n_identified)) return fail(`evar_nonpositive.n_identified must be a non-negative integer, got ${show(n_identified)}`)
  if (!isNonNegInt(n)) return fail(`evar_nonpositive.n must be a non-negative integer, got ${show(n)}`)
  if (n_identified > n_events) return fail(`evar_nonpositive.n_identified must be at most n_events (${n_events}), got number ${n_identified}`)
  if (n > n_identified) return fail(`evar_nonpositive.n must be at most n_identified (${n_identified}), got number ${n}`)
  if (share === null) {
    if (n_identified !== 0) return fail(`evar_nonpositive.share may be null only when n_identified is 0, but n_identified is ${n_identified}`)
  } else if (!isUnitInterval(share)) {
    return fail(`evar_nonpositive.share must be a number from 0 to 1, or null, got ${show(share)}`)
  }
  return { ok: true, data: { n_events, n_identified, n, share } }
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

  // Each of the two milestone-2 fields is either null (not computed, and its *_status string says
  // why) or filled; both are valid, so the page can show whichever the file has.
  const { by_move_tercile_status, evar_nonpositive_status, lookups, caveats } = input
  const terciles = parseByMoveTercile(input.by_move_tercile)
  if (!terciles.ok) return terciles
  if (!isText(by_move_tercile_status)) return fail(`by_move_tercile_status must be a non-empty string, got ${show(by_move_tercile_status)}`)
  const evar = parseEvarNonpositive(input.evar_nonpositive)
  if (!evar.ok) return evar
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
      by_move_tercile: terciles.data,
      by_move_tercile_status,
      evar_nonpositive: evar.data,
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
