/**
 * Loads and checks `data/event_paths.json` (kind "event_paths", schema 0.4.0): the path of abnormal log
 * IV around the announcement, as a mean with a pointwise 95% band per series and as one path per
 * event. Written by the Python exporter; the app only draws it. `fetch` is injected so tests never
 * touch the network; nothing here throws or coerces.
 *
 * The `data` object has exactly these keys:
 *   rel_days    array of integers, strictly increasing: the event days of every array below (-10 .. 10)
 *   series      array of { measure, adjustment, units, subgroup_key, subgroup_value, n, mean, ci_lo, ci_hi }.
 *               `adjustment` is "market" or "mean"; the four arrays have one entry per rel_day, each a
 *               number or null (n: a non-negative integer or null). One series per (adjustment, subgroup)
 *   per_event   array of { event_id, ticker, sector, day0, timing_used, values }: `day0` is "YYYY-MM-DD",
 *               `timing_used` is "BMO", "AMC" or null, `values` has one number-or-null per rel_day
 *   lookups     { n_done, complete }: how many timing look-ups are done (the timing labels are provisional until complete)
 *   caveats     array of strings, shown next to the numbers
 *   provenance  same object as in meta.json (see `provenance.ts`)
 */
import {
  ADJUSTMENTS,
  isNonNegIntOrNull,
  isNumberOrNull,
  loadKind,
  oneOf,
  parseArrayOf,
  parseCaveats,
  parseLookups,
  parseRelDays,
  type Adjustment,
  type Lookups,
} from './dataParts'
import { parseProvenance, type Provenance } from './provenance'
import { fail, isIsoDate, isObject, isText, keyProblem, show, type Parsed } from './validate'

export const EVENT_PATHS_URL = 'data/event_paths.json'
export const EVENT_PATHS_KIND = 'event_paths'

export type TimingUsed = 'BMO' | 'AMC'

export interface PathSeries {
  measure: string
  adjustment: Adjustment
  units: string
  subgroup_key: string
  subgroup_value: string
  n: (number | null)[]
  mean: (number | null)[]
  ci_lo: (number | null)[]
  ci_hi: (number | null)[]
}

export interface PerEventPath {
  event_id: string
  ticker: string
  sector: string
  day0: string
  timing_used: TimingUsed | null
  values: (number | null)[]
}

export interface EventPaths {
  rel_days: number[]
  series: PathSeries[]
  per_event: PerEventPath[]
  lookups: Lookups
  caveats: string[]
  provenance: Provenance
}

export type EventPathsResult = Parsed<EventPaths>

const EVENT_PATHS_KEYS = ['rel_days', 'series', 'per_event', 'lookups', 'caveats', 'provenance'] as const
const SERIES_KEYS = ['measure', 'adjustment', 'units', 'subgroup_key', 'subgroup_value', 'n', 'mean', 'ci_lo', 'ci_hi'] as const
const PER_EVENT_KEYS = ['event_id', 'ticker', 'sector', 'day0', 'timing_used', 'values'] as const

const isTiming = oneOf<TimingUsed>('BMO', 'AMC')
const isAdjustment = oneOf(...ADJUSTMENTS)

function parseSeries(input: unknown, i: number, days: number): Parsed<PathSeries> {
  const where = `series[${i}]`
  if (!isObject(input)) return fail(`${where} must be an object, got ${show(input)}`)
  const problem = keyProblem(where, input, SERIES_KEYS)
  if (problem) return fail(problem)
  const { measure, adjustment, units, subgroup_key, subgroup_value } = input
  if (!isText(measure)) return fail(`${where}.measure must be a non-empty string, got ${show(measure)}`)
  if (!isAdjustment(adjustment)) return fail(`${where}.adjustment must be "market" or "mean", got ${show(adjustment)}`)
  if (!isText(units)) return fail(`${where}.units must be a non-empty string, got ${show(units)}`)
  if (!isText(subgroup_key)) return fail(`${where}.subgroup_key must be a non-empty string, got ${show(subgroup_key)}`)
  if (!isText(subgroup_value)) return fail(`${where}.subgroup_value must be a non-empty string, got ${show(subgroup_value)}`)

  const length = { n: days, per: 'rel_days entry' }
  const n = parseArrayOf(input.n, `${where}.n`, isNonNegIntOrNull, 'a non-negative integer or null', length)
  if (!n.ok) return n
  const mean = parseArrayOf(input.mean, `${where}.mean`, isNumberOrNull, 'a finite number or null', length)
  if (!mean.ok) return mean
  const lo = parseArrayOf(input.ci_lo, `${where}.ci_lo`, isNumberOrNull, 'a finite number or null', length)
  if (!lo.ok) return lo
  const hi = parseArrayOf(input.ci_hi, `${where}.ci_hi`, isNumberOrNull, 'a finite number or null', length)
  if (!hi.ok) return hi
  for (const [d, l] of lo.data.entries()) {
    const h = hi.data[d]
    if (l !== null && h !== null && l > h) return fail(`${where}.ci_lo[${d}] (${l}) must be at most ci_hi[${d}] (${h})`)
  }

  return {
    ok: true,
    data: { measure, adjustment, units, subgroup_key, subgroup_value, n: n.data, mean: mean.data, ci_lo: lo.data, ci_hi: hi.data },
  }
}

function parsePerEvent(input: unknown, i: number, days: number): Parsed<PerEventPath> {
  const where = `per_event[${i}]`
  if (!isObject(input)) return fail(`${where} must be an object, got ${show(input)}`)
  const problem = keyProblem(where, input, PER_EVENT_KEYS)
  if (problem) return fail(problem)
  const { event_id, ticker, sector, day0, timing_used } = input
  if (!isText(event_id)) return fail(`${where}.event_id must be a non-empty string, got ${show(event_id)}`)
  if (!isText(ticker)) return fail(`${where}.ticker must be a non-empty string, got ${show(ticker)}`)
  if (!isText(sector)) return fail(`${where}.sector must be a non-empty string, got ${show(sector)}`)
  if (!isIsoDate(day0)) return fail(`${where}.day0 must be a date string YYYY-MM-DD, got ${show(day0)}`)
  if (timing_used !== null && !isTiming(timing_used)) return fail(`${where}.timing_used must be "BMO", "AMC" or null, got ${show(timing_used)}`)
  const values = parseArrayOf(input.values, `${where}.values`, isNumberOrNull, 'a finite number or null', { n: days, per: 'rel_days entry' })
  if (!values.ok) return values
  return { ok: true, data: { event_id, ticker, sector, day0, timing_used, values: values.data } }
}

/**
 * Check the `data` object of a `kind: "event_paths"` envelope: exactly the keys above, each of the
 * right type, every array as long as `rel_days`. Nothing throws and nothing is coerced; a failure
 * comes back as `{ ok: false, error }` naming the first rule that failed.
 */
export function parseEventPaths(input: unknown): EventPathsResult {
  if (!isObject(input)) return fail(`event paths data must be a JSON object, got ${show(input)}`)
  const top = keyProblem('event paths data', input, EVENT_PATHS_KEYS)
  if (top) return fail(top)

  const relDays = parseRelDays(input.rel_days)
  if (!relDays.ok) return relDays
  const days = relDays.data.length

  const { series, per_event } = input
  if (!Array.isArray(series) || series.length === 0) return fail(`series must be a non-empty array, got ${show(series)}`)
  const parsedSeries: PathSeries[] = []
  for (const [i, s] of series.entries()) {
    const r = parseSeries(s, i, days)
    if (!r.ok) return r
    const twin = parsedSeries.findIndex((o) => o.adjustment === r.data.adjustment && o.subgroup_key === r.data.subgroup_key && o.subgroup_value === r.data.subgroup_value)
    if (twin >= 0) {
      return fail(`series[${i}] repeats series[${twin}] (same adjustment ${show(r.data.adjustment)} and subgroup ${show(r.data.subgroup_key)} = ${show(r.data.subgroup_value)})`)
    }
    parsedSeries.push(r.data)
  }

  if (!Array.isArray(per_event)) return fail(`per_event must be an array, got ${show(per_event)}`)
  const parsedEvents: PerEventPath[] = []
  for (const [i, e] of per_event.entries()) {
    const r = parsePerEvent(e, i, days)
    if (!r.ok) return r
    const twin = parsedEvents.findIndex((o) => o.event_id === r.data.event_id)
    if (twin >= 0) return fail(`per_event[${i}].event_id ${show(r.data.event_id)} is already used by per_event[${twin}]`)
    parsedEvents.push(r.data)
  }

  const lookups = parseLookups(input.lookups)
  if (!lookups.ok) return lookups
  const caveats = parseCaveats(input.caveats)
  if (!caveats.ok) return caveats
  const provenance = parseProvenance(input.provenance)
  if (!provenance.ok) return provenance

  return {
    ok: true,
    data: {
      rel_days: relDays.data,
      series: parsedSeries,
      per_event: parsedEvents,
      lookups: lookups.data,
      caveats: caveats.data,
      provenance: provenance.data,
    },
  }
}

/** Fetch + validate `data/event_paths.json`. Never throws: every failure comes back as `{ ok: false, error }`. */
export const loadEventPaths = (url: string = EVENT_PATHS_URL, fetchImpl?: typeof fetch): Promise<EventPathsResult> =>
  loadKind(url, EVENT_PATHS_KIND, parseEventPaths, fetchImpl)

/** A subgroup as the selector offers it. `label` is "all" for the whole sample, else the subgroup value (e.g. "BMO"). */
export interface SubgroupOption {
  key: string
  value: string
  label: string
}

export interface SeriesOptions {
  adjustments: Adjustment[]
  subgroups: SubgroupOption[]
}

/** The adjustments and subgroups the file has series for, each once, in order of first appearance. */
export function seriesOptions(series: readonly PathSeries[]): SeriesOptions {
  const adjustments: Adjustment[] = []
  const subgroups: SubgroupOption[] = []
  for (const s of series) {
    if (!adjustments.includes(s.adjustment)) adjustments.push(s.adjustment)
    if (!subgroups.some((g) => g.key === s.subgroup_key && g.value === s.subgroup_value)) {
      subgroups.push({ key: s.subgroup_key, value: s.subgroup_value, label: s.subgroup_key === 'all' ? 'all' : s.subgroup_value })
    }
  }
  return { adjustments, subgroups }
}

/** The series for an adjustment and subgroup, or undefined when the file has none (the page then says so). */
export const findSeries = (series: readonly PathSeries[], adjustment: Adjustment, group: { key: string; value: string }): PathSeries | undefined =>
  series.find((s) => s.adjustment === adjustment && s.subgroup_key === group.key && s.subgroup_value === group.value)

/**
 * The per-event paths that belong to a subgroup: all of them for "all", those with the same
 * `timing_used` for the "timing" subgroups, and null for a subgroup the events cannot be filtered by.
 */
export function eventsInSubgroup(events: readonly PerEventPath[], group: { key: string; value: string }): PerEventPath[] | null {
  if (group.key === 'all') return [...events]
  if (group.key === 'timing') return events.filter((e) => e.timing_used === group.value)
  return null
}
