/**
 * Loads and checks `data/terrain.json` (kind "terrain", schema 0.5.0): one row per company and one
 * column per event day, each cell the company's mean abnormal log IV, for the 3D view. Written by
 * the Python exporter; the app only draws it (`terrain.ts` turns the grid into a mesh). `fetch` is
 * injected so tests never touch the network; nothing here throws or coerces.
 *
 * The `data` object has exactly these keys:
 *   measure     string, which measure the cells hold
 *   units       string, the units of the cells
 *   rel_days    array of integers, strictly increasing: the event day of each column (-10 .. 10)
 *   rows        array of { security_id, ticker, sector, n_events }, one per company, in the order of `values`
 *   values      array with one row per company, each with one number-or-null per rel_day (null = no data)
 *   row_order   string, how the rows are ordered (shown in the caption)
 *   lookups     { n_done, complete }: how many timing look-ups are done (the timing labels are provisional until complete)
 *   caveats     array of strings, shown next to the numbers
 *   provenance  same object as in meta.json (see `provenance.ts`)
 */
import { isNumberOrNull, loadKind, parseCaveats, parseGrid, parseLookups, parseRelDays, type Lookups } from './dataParts'
import { parseProvenance, type Provenance } from './provenance'
import { fail, isNonNegInt, isObject, isText, keyProblem, show, type Parsed } from './validate'

export const TERRAIN_URL = 'data/terrain.json'
export const TERRAIN_KIND = 'terrain'

export interface TerrainRow {
  security_id: string
  ticker: string
  sector: string
  n_events: number
}

export interface TerrainData {
  measure: string
  units: string
  rel_days: number[]
  rows: TerrainRow[]
  values: (number | null)[][]
  row_order: string
  lookups: Lookups
  caveats: string[]
  provenance: Provenance
}

export type TerrainResult = Parsed<TerrainData>

const TERRAIN_KEYS = ['measure', 'units', 'rel_days', 'rows', 'values', 'row_order', 'lookups', 'caveats', 'provenance'] as const
const ROW_KEYS = ['security_id', 'ticker', 'sector', 'n_events'] as const

function parseRow(input: unknown, i: number): Parsed<TerrainRow> {
  const where = `rows[${i}]`
  if (!isObject(input)) return fail(`${where} must be an object, got ${show(input)}`)
  const problem = keyProblem(where, input, ROW_KEYS)
  if (problem) return fail(problem)
  const { security_id, ticker, sector, n_events } = input
  if (!isText(security_id)) return fail(`${where}.security_id must be a non-empty string, got ${show(security_id)}`)
  if (!isText(ticker)) return fail(`${where}.ticker must be a non-empty string, got ${show(ticker)}`)
  if (!isText(sector)) return fail(`${where}.sector must be a non-empty string, got ${show(sector)}`)
  if (!isNonNegInt(n_events)) return fail(`${where}.n_events must be a non-negative integer, got ${show(n_events)}`)
  return { ok: true, data: { security_id, ticker, sector, n_events } }
}

/**
 * Check the `data` object of a `kind: "terrain"` envelope: exactly the keys above, each of the right
 * type, and `values` exactly one row per company and one column per rel_day (a ragged row is refused).
 * Nothing throws and nothing is coerced; a failure comes back as `{ ok: false, error }` naming the
 * first rule that failed.
 */
export function parseTerrainData(input: unknown): TerrainResult {
  if (!isObject(input)) return fail(`terrain data must be a JSON object, got ${show(input)}`)
  const top = keyProblem('terrain data', input, TERRAIN_KEYS)
  if (top) return fail(top)

  const { measure, units, rows, row_order } = input
  if (!isText(measure)) return fail(`measure must be a non-empty string, got ${show(measure)}`)
  if (!isText(units)) return fail(`units must be a non-empty string, got ${show(units)}`)
  if (!isText(row_order)) return fail(`row_order must be a non-empty string, got ${show(row_order)}`)
  const relDays = parseRelDays(input.rel_days)
  if (!relDays.ok) return relDays

  if (!Array.isArray(rows) || rows.length === 0) return fail(`rows must be a non-empty array, got ${show(rows)}`)
  const parsedRows: TerrainRow[] = []
  for (const [i, row] of rows.entries()) {
    const r = parseRow(row, i)
    if (!r.ok) return r
    const twin = parsedRows.findIndex((o) => o.security_id === r.data.security_id)
    if (twin >= 0) return fail(`rows[${i}].security_id ${show(r.data.security_id)} is already used by rows[${twin}]`)
    parsedRows.push(r.data)
  }

  const values = parseGrid(
    input.values,
    'values',
    { n: parsedRows.length, per: 'company in rows' },
    { n: relDays.data.length, per: 'rel_days entry' },
    isNumberOrNull,
    'a finite number or null',
  )
  if (!values.ok) return values

  const lookups = parseLookups(input.lookups)
  if (!lookups.ok) return lookups
  const caveats = parseCaveats(input.caveats)
  if (!caveats.ok) return caveats
  const provenance = parseProvenance(input.provenance)
  if (!provenance.ok) return provenance

  return {
    ok: true,
    data: {
      measure,
      units,
      rel_days: relDays.data,
      rows: parsedRows,
      values: values.data,
      row_order,
      lookups: lookups.data,
      caveats: caveats.data,
      provenance: provenance.data,
    },
  }
}

/** Fetch + validate `data/terrain.json`. Never throws: every failure comes back as `{ ok: false, error }`. */
export const loadTerrainData = (url: string = TERRAIN_URL, fetchImpl?: typeof fetch): Promise<TerrainResult> =>
  loadKind(url, TERRAIN_KIND, parseTerrainData, fetchImpl)

/** The grid `gridToTerrain` takes: the file's cells, with null (no data) as NaN so the mesh leaves a hole there. */
export const terrainGrid = (data: TerrainData): number[][] => data.values.map((row) => row.map((v) => (v === null ? NaN : v)))

/** What the axes of the 3D view mean, drawn from the file's own words (days, row order, units). */
export function terrainCaption(data: TerrainData): string {
  const first = data.rel_days[0]
  const last = data.rel_days[data.rel_days.length - 1]
  return `x: event day (${first} to ${last}) · z: company (${data.rows.length}, in the file's order: ${data.row_order}) · height and colour: ${data.units}. Gaps are cells with no data.`
}
