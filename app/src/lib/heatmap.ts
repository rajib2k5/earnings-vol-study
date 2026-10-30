/**
 * Loads and checks `data/heatmap.json` (kind "heatmap", schema 0.5.0): grids of cells (company by event
 * day, company by season) for the Heatmap page. Written by the Python exporter; the app only
 * draws it. `fetch` is injected so tests never touch the network; nothing here throws or coerces.
 *
 * The `data` object has exactly these keys:
 *   grids       non-empty array of grids, each with exactly these keys:
 *                 id, title, measure, units   non-empty strings (`id` is unique)
 *                 row_labels, row_keys        arrays of strings, one per row
 *                 col_labels                  array of strings, one per column
 *                 values                      rows x cols, each cell a number or null (null = no data)
 *                 n                           rows x cols, each cell a non-negative integer (events in the cell)
 *                 q                           null, or rows x cols of numbers from 0 to 1 or null (BH q-values)
 *   lookups     { n_done, complete }: how many timing look-ups are done (the timing labels are provisional until complete)
 *   caveats     array of strings, shown next to the numbers
 *   provenance  same object as in meta.json (see `provenance.ts`)
 */
import { isNumberOrNull, isProbabilityOrNull, loadKind, parseArrayOf, parseCaveats, parseGrid, parseLookups, type Lookups } from './dataParts'
import { parseProvenance, type Provenance } from './provenance'
import { fail, isNonNegInt, isObject, isText, keyProblem, show, type Parsed } from './validate'

export const HEATMAP_URL = 'data/heatmap.json'
export const HEATMAP_KIND = 'heatmap'

export interface HeatGrid {
  id: string
  title: string
  measure: string
  units: string
  row_labels: string[]
  row_keys: string[]
  col_labels: string[]
  values: (number | null)[][]
  n: number[][]
  q: (number | null)[][] | null
}

export interface HeatmapData {
  grids: HeatGrid[]
  lookups: Lookups
  caveats: string[]
  provenance: Provenance
}

export type HeatmapResult = Parsed<HeatmapData>

const HEATMAP_KEYS = ['grids', 'lookups', 'caveats', 'provenance'] as const
const GRID_KEYS = ['id', 'title', 'measure', 'units', 'row_labels', 'row_keys', 'col_labels', 'values', 'n', 'q'] as const

const isString = (x: unknown): x is string => typeof x === 'string'

function parseHeatGrid(input: unknown, i: number): Parsed<HeatGrid> {
  const where = `grids[${i}]`
  if (!isObject(input)) return fail(`${where} must be an object, got ${show(input)}`)
  const problem = keyProblem(where, input, GRID_KEYS)
  if (problem) return fail(problem)
  const { id, title, measure, units } = input
  if (!isText(id)) return fail(`${where}.id must be a non-empty string, got ${show(id)}`)
  if (!isText(title)) return fail(`${where}.title must be a non-empty string, got ${show(title)}`)
  if (!isText(measure)) return fail(`${where}.measure must be a non-empty string, got ${show(measure)}`)
  if (!isText(units)) return fail(`${where}.units must be a non-empty string, got ${show(units)}`)

  const rowLabels = parseArrayOf(input.row_labels, `${where}.row_labels`, isString, 'a string')
  if (!rowLabels.ok) return rowLabels
  if (rowLabels.data.length === 0) return fail(`${where}.row_labels must not be empty`)
  const rowKeys = parseArrayOf(input.row_keys, `${where}.row_keys`, isString, 'a string', { n: rowLabels.data.length, per: 'row label' })
  if (!rowKeys.ok) return rowKeys
  const colLabels = parseArrayOf(input.col_labels, `${where}.col_labels`, isString, 'a string')
  if (!colLabels.ok) return colLabels
  if (colLabels.data.length === 0) return fail(`${where}.col_labels must not be empty`)

  const rows = { n: rowLabels.data.length, per: 'row label' }
  const cols = { n: colLabels.data.length, per: 'column label' }
  const values = parseGrid(input.values, `${where}.values`, rows, cols, isNumberOrNull, 'a finite number or null')
  if (!values.ok) return values
  const n = parseGrid(input.n, `${where}.n`, rows, cols, isNonNegInt, 'a non-negative integer')
  if (!n.ok) return n
  let q: (number | null)[][] | null = null
  if (input.q !== null) {
    const parsedQ = parseGrid(input.q, `${where}.q`, rows, cols, isProbabilityOrNull, 'a number from 0 to 1 or null')
    if (!parsedQ.ok) return parsedQ
    q = parsedQ.data
  }

  return {
    ok: true,
    data: { id, title, measure, units, row_labels: rowLabels.data, row_keys: rowKeys.data, col_labels: colLabels.data, values: values.data, n: n.data, q },
  }
}

/**
 * Check the `data` object of a `kind: "heatmap"` envelope: exactly the keys above, each of the right
 * type, every grid rectangular and as large as its labels. Nothing throws and nothing is coerced; a
 * failure comes back as `{ ok: false, error }` naming the first rule that failed.
 */
export function parseHeatmap(input: unknown): HeatmapResult {
  if (!isObject(input)) return fail(`heatmap data must be a JSON object, got ${show(input)}`)
  const top = keyProblem('heatmap data', input, HEATMAP_KEYS)
  if (top) return fail(top)

  const { grids } = input
  if (!Array.isArray(grids) || grids.length === 0) return fail(`grids must be a non-empty array, got ${show(grids)}`)
  const parsedGrids: HeatGrid[] = []
  for (const [i, g] of grids.entries()) {
    const r = parseHeatGrid(g, i)
    if (!r.ok) return r
    const twin = parsedGrids.findIndex((o) => o.id === r.data.id)
    if (twin >= 0) return fail(`grids[${i}].id ${show(r.data.id)} is already used by grids[${twin}]`)
    parsedGrids.push(r.data)
  }

  const lookups = parseLookups(input.lookups)
  if (!lookups.ok) return lookups
  const caveats = parseCaveats(input.caveats)
  if (!caveats.ok) return caveats
  const provenance = parseProvenance(input.provenance)
  if (!provenance.ok) return provenance

  return { ok: true, data: { grids: parsedGrids, lookups: lookups.data, caveats: caveats.data, provenance: provenance.data } }
}

/** Fetch + validate `data/heatmap.json`. Never throws: every failure comes back as `{ ok: false, error }`. */
export const loadHeatmap = (url: string = HEATMAP_URL, fetchImpl?: typeof fetch): Promise<HeatmapResult> =>
  loadKind(url, HEATMAP_KIND, parseHeatmap, fetchImpl)

/** What a cell says about itself (title and aria-label): row, column, value and n, and its q-value when the grid has one. */
export function cellText(grid: HeatGrid, i: number, j: number): string {
  const v = grid.values[i][j]
  const q = grid.q === null ? null : grid.q[i][j]
  return `${grid.row_labels[i]}, ${grid.col_labels[j]}: ${v === null ? 'no data' : v} (n = ${grid.n[i][j]})${q === null ? '' : `, q = ${q}`}`
}
