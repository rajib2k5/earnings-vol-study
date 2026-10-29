/**
 * Loads and checks `data/iv_measures.json` (kind "iv_measures", schema 0.4.0): the distribution of
 * the implied move at day -1 and of the 30-day IV crush, written by the Python exporter. The app
 * only draws these numbers; it never recomputes them. Like `funnel.ts`, `fetch` is injected so tests
 * never touch the network, and nothing here throws or coerces.
 *
 * The `data` object has exactly these keys:
 *   sample        { label, n_events }
 *   implied_move  { units, n_identified, n_nonpositive, n, sqrt_mean_evar, quantiles, bin_edges, counts }
 *   crush         { units, n, mean, quantiles, bin_edges, counts }
 *   caveats       array of strings, shown next to the numbers
 *   provenance    same object as in meta.json (see `provenance.ts`)
 *
 * `quantiles` is null or exactly { p10, p25, p50, p75, p90 }, finite and non-decreasing in that
 * order. A histogram is `bin_edges` (strictly increasing) and `counts`: both empty, or one more edge
 * than counts. The counts add up to `n`; that is a check of the file (a file whose counts and n
 * disagree is refused), not a result the page shows.
 */
import { loadEnvelope } from './meta'
import { parseProvenance, type Provenance } from './provenance'
import { fail, isFiniteNumber, isNonNegInt, isObject, isText, keyProblem, show, type Parsed } from './validate'

export const IV_MEASURES_URL = 'data/iv_measures.json'
export const IV_MEASURES_KIND = 'iv_measures'

/** The five quantiles, in the order the file has them and the page draws them. */
export const QUANTILE_NAMES = ['p10', 'p25', 'p50', 'p75', 'p90'] as const
export type QuantileName = (typeof QUANTILE_NAMES)[number]
export type Quantiles = Record<QuantileName, number>

export interface IvSample {
  label: string
  n_events: number
}

export interface ImpliedMove {
  units: string
  /** Events whose event variance E could be worked out at day -1. */
  n_identified: number
  /** Of those, the events with E <= 0, which have no implied move. */
  n_nonpositive: number
  /** Events in the histogram (those with E > 0). */
  n: number
  /** Square root of the mean of E over all identified events, E signed; null when not available. */
  sqrt_mean_evar: number | null
  quantiles: Quantiles | null
  bin_edges: number[]
  counts: number[]
}

export interface Crush {
  units: string
  n: number
  mean: number | null
  quantiles: Quantiles | null
  bin_edges: number[]
  counts: number[]
}

export interface IvMeasures {
  sample: IvSample
  implied_move: ImpliedMove
  crush: Crush
  caveats: string[]
  provenance: Provenance
}

export type IvMeasuresResult = Parsed<IvMeasures>

const IV_KEYS = ['sample', 'implied_move', 'crush', 'caveats', 'provenance'] as const
const SAMPLE_KEYS = ['label', 'n_events'] as const
const IMPLIED_MOVE_KEYS = ['units', 'n_identified', 'n_nonpositive', 'n', 'sqrt_mean_evar', 'quantiles', 'bin_edges', 'counts'] as const
const CRUSH_KEYS = ['units', 'n', 'mean', 'quantiles', 'bin_edges', 'counts'] as const

/** `where` is the path used in messages, e.g. "implied_move.quantiles". Null is a valid value. */
function parseQuantiles(input: unknown, where: string): Parsed<Quantiles | null> {
  if (input === null) return { ok: true, data: null }
  if (!isObject(input)) return fail(`${where} must be null or an object, got ${show(input)}`)
  const problem = keyProblem(where, input, QUANTILE_NAMES)
  if (problem) return fail(problem)
  const q = {} as Quantiles
  for (const [i, name] of QUANTILE_NAMES.entries()) {
    const v = input[name]
    if (!isFiniteNumber(v)) return fail(`${where}.${name} must be a finite number, got ${show(v)}`)
    if (i > 0 && v < q[QUANTILE_NAMES[i - 1]]) {
      const before = QUANTILE_NAMES[i - 1]
      return fail(`${where} must not decrease from ${before} to ${name}, but ${name} (${v}) is below ${before} (${q[before]})`)
    }
    q[name] = v
  }
  return { ok: true, data: q }
}

/**
 * The histogram arrays of one measure. Edges first (finite, strictly increasing), then counts
 * (non-negative integers), then the two lengths, then the sum against `n`.
 */
function parseHistogram(edges: unknown, counts: unknown, n: number, where: string): Parsed<{ bin_edges: number[]; counts: number[] }> {
  if (!Array.isArray(edges)) return fail(`${where}.bin_edges must be an array, got ${show(edges)}`)
  for (const [i, e] of edges.entries()) {
    if (!isFiniteNumber(e)) return fail(`${where}.bin_edges[${i}] must be a finite number, got ${show(e)}`)
    if (i > 0 && e <= edges[i - 1]) return fail(`${where}.bin_edges must be strictly increasing, but bin_edges[${i}] (${e}) is not above bin_edges[${i - 1}] (${edges[i - 1]})`)
  }
  if (!Array.isArray(counts)) return fail(`${where}.counts must be an array, got ${show(counts)}`)
  for (const [i, c] of counts.entries()) {
    if (!isNonNegInt(c)) return fail(`${where}.counts[${i}] must be a non-negative integer, got ${show(c)}`)
  }
  const bothEmpty = edges.length === 0 && counts.length === 0
  if (!bothEmpty && edges.length !== counts.length + 1) {
    return fail(`${where}.bin_edges must have one more entry than counts (or both be empty), got ${edges.length} edges and ${counts.length} counts`)
  }
  const total = (counts as number[]).reduce((a, b) => a + b, 0)
  if (total !== n) return fail(`${where}.counts add up to ${total}, but n is ${n}`)
  return { ok: true, data: { bin_edges: [...(edges as number[])], counts: [...(counts as number[])] } }
}

function parseSample(input: unknown): Parsed<IvSample> {
  if (!isObject(input)) return fail(`sample must be an object, got ${show(input)}`)
  const problem = keyProblem('sample', input, SAMPLE_KEYS)
  if (problem) return fail(problem)
  const { label, n_events } = input
  if (!isText(label)) return fail(`sample.label must be a non-empty string, got ${show(label)}`)
  if (!isNonNegInt(n_events)) return fail(`sample.n_events must be a non-negative integer, got ${show(n_events)}`)
  return { ok: true, data: { label, n_events } }
}

function parseImpliedMove(input: unknown): Parsed<ImpliedMove> {
  if (!isObject(input)) return fail(`implied_move must be an object, got ${show(input)}`)
  const problem = keyProblem('implied_move', input, IMPLIED_MOVE_KEYS)
  if (problem) return fail(problem)
  const { units, n_identified, n_nonpositive, n, sqrt_mean_evar } = input
  if (!isText(units)) return fail(`implied_move.units must be a non-empty string, got ${show(units)}`)
  if (!isNonNegInt(n_identified)) return fail(`implied_move.n_identified must be a non-negative integer, got ${show(n_identified)}`)
  if (!isNonNegInt(n_nonpositive)) return fail(`implied_move.n_nonpositive must be a non-negative integer, got ${show(n_nonpositive)}`)
  if (!isNonNegInt(n)) return fail(`implied_move.n must be a non-negative integer, got ${show(n)}`)
  if (n_nonpositive > n_identified) return fail(`implied_move.n_nonpositive must be at most n_identified (${n_identified}), got number ${n_nonpositive}`)
  if (n > n_identified) return fail(`implied_move.n must be at most n_identified (${n_identified}), got number ${n}`)
  if (sqrt_mean_evar !== null && !isFiniteNumber(sqrt_mean_evar)) {
    return fail(`implied_move.sqrt_mean_evar must be a finite number or null, got ${show(sqrt_mean_evar)}`)
  }
  const quantiles = parseQuantiles(input.quantiles, 'implied_move.quantiles')
  if (!quantiles.ok) return quantiles
  const histogram = parseHistogram(input.bin_edges, input.counts, n, 'implied_move')
  if (!histogram.ok) return histogram
  return { ok: true, data: { units, n_identified, n_nonpositive, n, sqrt_mean_evar, quantiles: quantiles.data, ...histogram.data } }
}

function parseCrush(input: unknown): Parsed<Crush> {
  if (!isObject(input)) return fail(`crush must be an object, got ${show(input)}`)
  const problem = keyProblem('crush', input, CRUSH_KEYS)
  if (problem) return fail(problem)
  const { units, n, mean } = input
  if (!isText(units)) return fail(`crush.units must be a non-empty string, got ${show(units)}`)
  if (!isNonNegInt(n)) return fail(`crush.n must be a non-negative integer, got ${show(n)}`)
  if (mean !== null && !isFiniteNumber(mean)) return fail(`crush.mean must be a finite number or null, got ${show(mean)}`)
  const quantiles = parseQuantiles(input.quantiles, 'crush.quantiles')
  if (!quantiles.ok) return quantiles
  const histogram = parseHistogram(input.bin_edges, input.counts, n, 'crush')
  if (!histogram.ok) return histogram
  return { ok: true, data: { units, n, mean, quantiles: quantiles.data, ...histogram.data } }
}

/**
 * Check the `data` object of a `kind: "iv_measures"` envelope: exactly the keys above, each of the
 * right type. Nothing throws and nothing is coerced; a failure comes back as
 * `{ ok: false, error }` naming the first rule that failed.
 */
export function parseIvMeasures(input: unknown): IvMeasuresResult {
  if (!isObject(input)) return fail(`iv measures data must be a JSON object, got ${show(input)}`)
  const top = keyProblem('iv measures data', input, IV_KEYS)
  if (top) return fail(top)

  const sample = parseSample(input.sample)
  if (!sample.ok) return sample
  const impliedMove = parseImpliedMove(input.implied_move)
  if (!impliedMove.ok) return impliedMove
  const crush = parseCrush(input.crush)
  if (!crush.ok) return crush

  const { caveats } = input
  if (!Array.isArray(caveats)) return fail(`caveats must be an array, got ${show(caveats)}`)
  for (const [i, c] of caveats.entries()) {
    if (!isText(c)) return fail(`caveats[${i}] must be a non-empty string, got ${show(c)}`)
  }

  const provenance = parseProvenance(input.provenance)
  if (!provenance.ok) return provenance

  return {
    ok: true,
    data: { sample: sample.data, implied_move: impliedMove.data, crush: crush.data, caveats: [...caveats], provenance: provenance.data },
  }
}

/**
 * Fetch + validate `data/iv_measures.json`: the envelope first (`parseEnvelope`, through
 * `loadEnvelope`), then `kind`, then the `data` shape. Never throws: every failure comes back as
 * `{ ok: false, error }`.
 */
export async function loadIvMeasures(url: string = IV_MEASURES_URL, fetchImpl?: typeof fetch): Promise<IvMeasuresResult> {
  const r = await loadEnvelope(url, fetchImpl)
  if (!r.ok) return r
  if (r.envelope.kind !== IV_MEASURES_KIND) {
    return fail(`${url} has kind ${show(r.envelope.kind)}, expected "${IV_MEASURES_KIND}"`)
  }
  const parsed = parseIvMeasures(r.envelope.data)
  return parsed.ok ? parsed : fail(`${url}: ${parsed.error}`)
}
