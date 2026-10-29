import { describe, it, expect } from 'vitest'
import { cellText, HEATMAP_KIND, HEATMAP_URL, loadHeatmap, parseHeatmap, type HeatGrid } from './heatmap'
import { HEATMAP_DATA_FIXTURE, HEATMAP_FIXTURE } from '../test/heatmapFixture'
import { PROVENANCE_FIXTURE } from '../test/metaFixture'
import { describeLoader, edited as editedOf, errorOfParse, type Path } from '../test/editHelpers'

const edited = (path: Path, value: unknown): unknown => editedOf(HEATMAP_DATA_FIXTURE, path, value)
const errorOf = (input: unknown): string => errorOfParse(parseHeatmap(input))

const KEYS = ['grids', 'lookups', 'caveats', 'provenance']
const KEY_LIST = KEYS.join(', ')
const GRID_KEYS = ['id', 'title', 'measure', 'units', 'row_labels', 'row_keys', 'col_labels', 'values', 'n', 'q']
const GRID_KEY_LIST = GRID_KEYS.join(', ')

const grids = (): HeatGrid[] => {
  const r = parseHeatmap(HEATMAP_DATA_FIXTURE)
  if (!r.ok) throw new Error(r.error)
  return r.data.grids
}

describe('parseHeatmap: accepts the exporter shape', () => {
  it('returns the same values for a good file', () => {
    expect(parseHeatmap(HEATMAP_DATA_FIXTURE)).toEqual({ ok: true, data: HEATMAP_DATA_FIXTURE })
  })
  it('does not mutate its input and returns copies', () => {
    const input = structuredClone(HEATMAP_DATA_FIXTURE)
    const r = parseHeatmap(input)
    expect(input).toEqual(HEATMAP_DATA_FIXTURE)
    if (!r.ok) throw new Error(r.error)
    expect(r.data.grids[0].values).not.toBe(input.grids[0].values)
    expect(r.data.grids[0].values[0]).not.toBe(input.grids[0].values[0])
    expect(r.data.grids[0].n[0]).not.toBe(input.grids[0].n[0])
    expect(r.data.grids[1].q).not.toBe(input.grids[1].q)
    expect(r.data.grids[0].row_labels).not.toBe(input.grids[0].row_labels)
    expect(r.data.caveats).not.toBe(input.caveats)
  })
  it('returns the provenance with the same values as meta.json carries', () => {
    const r = parseHeatmap(HEATMAP_DATA_FIXTURE)
    if (!r.ok) throw new Error(r.error)
    expect(r.data.provenance).toEqual(PROVENANCE_FIXTURE)
  })
  it('keeps null cells as null and a q of null as null', () => {
    const [byDay, bySeason] = grids()
    expect(byDay.values[1][1]).toBeNull()
    expect(byDay.q).toBeNull()
    expect(bySeason.values[0][1]).toBeNull()
    expect(bySeason.q?.[0][1]).toBeNull()
    expect(byDay.values[0][1]).toBe(0) // a real zero stays 0
  })
  it('accepts q-values at the ends 0 and 1, a 1 x 1 grid, and no caveats', () => {
    expect(parseHeatmap(edited(['grids', 1, 'q', 0, 0], 0)).ok).toBe(true)
    expect(parseHeatmap(edited(['grids', 1, 'q', 0, 0], 1)).ok).toBe(true)
    const tiny = { ...HEATMAP_DATA_FIXTURE.grids[0], row_labels: ['A'], row_keys: ['A'], col_labels: ['0'], values: [[0.5]], n: [[2]] }
    expect(parseHeatmap(edited(['grids'], [tiny])).ok).toBe(true)
    expect(parseHeatmap(edited(['caveats'], [])).ok).toBe(true)
  })
})

describe('parseHeatmap: key sets must be exact', () => {
  it('rejects an input that is not a JSON object', () => {
    for (const x of [null, undefined, [], 'heatmap', 1]) expect(errorOf(x), String(x)).toContain('heatmap data must be a JSON object')
  })
  it.each(KEYS)('requires the key %s', (key) => {
    expect(errorOf(edited([key], undefined))).toBe(`heatmap data has missing key(s): ${key} (expected exactly: ${KEY_LIST})`)
  })
  it('rejects an extra key and names it', () => {
    expect(errorOf(edited(['legend'], []))).toBe(`heatmap data has unexpected key(s): legend (expected exactly: ${KEY_LIST})`)
  })
  it.each(GRID_KEYS)('requires the grid key %s (null is not the same as missing)', (key) => {
    expect(errorOf(edited(['grids', 1, key], undefined))).toBe(`grids[1] has missing key(s): ${key} (expected exactly: ${GRID_KEY_LIST})`)
  })
  it('rejects an extra grid key', () => {
    expect(errorOf(edited(['grids', 0, 'colours'], []))).toBe(`grids[0] has unexpected key(s): colours (expected exactly: ${GRID_KEY_LIST})`)
  })
  it('names the kind the Python exporter writes', () => {
    expect(HEATMAP_KIND).toBe('heatmap')
    expect(HEATMAP_URL).toBe('data/heatmap.json')
  })
})

describe('parseHeatmap: types and shapes', () => {
  it.each<[string, Path, unknown, string]>([
    ['grids not an array', ['grids'], {}, 'grids must be a non-empty array, got an object'],
    ['grids empty', ['grids'], [], 'grids must be a non-empty array, got an array'],
    ['grid not an object', ['grids', 0], 'g', 'grids[0] must be an object, got "g"'],
    ['id empty', ['grids', 0, 'id'], '', 'grids[0].id must be a non-empty string, got ""'],
    ['title a number', ['grids', 0, 'title'], 4, 'grids[0].title must be a non-empty string, got number 4'],
    ['measure null', ['grids', 1, 'measure'], null, 'grids[1].measure must be a non-empty string, got null'],
    ['units blank', ['grids', 1, 'units'], '  ', 'grids[1].units must be a non-empty string, got "  "'],
    ['repeated id', ['grids', 1, 'id'], 'fix_by_day', 'grids[1].id "fix_by_day" is already used by grids[0]'],
    ['row_labels not an array', ['grids', 0, 'row_labels'], 'FXA', 'grids[0].row_labels must be an array, got "FXA"'],
    ['row_labels empty', ['grids', 0, 'row_labels'], [], 'grids[0].row_labels must not be empty'],
    ['a row label a number', ['grids', 0, 'row_labels', 1], 5, 'grids[0].row_labels[1] must be a string, got number 5'],
    ['row_keys shorter than row_labels', ['grids', 0, 'row_keys'], ['FXA'], 'grids[0].row_keys must have 2 entries (one per row label), got 1'],
    ['a row key null', ['grids', 0, 'row_keys', 0], null, 'grids[0].row_keys[0] must be a string, got null'],
    ['col_labels not an array', ['grids', 0, 'col_labels'], null, 'grids[0].col_labels must be an array, got null'],
    ['col_labels empty', ['grids', 0, 'col_labels'], [], 'grids[0].col_labels must not be empty'],
    ['a column label a number', ['grids', 0, 'col_labels', 0], -1, 'grids[0].col_labels[0] must be a string, got number -1'],
    ['values not an array', ['grids', 0, 'values'], null, 'grids[0].values must be an array, got null'],
    ['values with too few rows', ['grids', 0, 'values'], [[1, 2, 3]], 'grids[0].values must have 2 rows (one per row label), got 1'],
    ['values with a ragged row (short)', ['grids', 0, 'values', 1], [0.5, 0.25], 'grids[0].values[1] must have 3 entries (one per column label), got 2'],
    ['values with a ragged row (long)', ['grids', 1, 'values', 0], [1, null, 3], 'grids[1].values[0] must have 2 entries (one per column label), got 3'],
    ['a value a string', ['grids', 0, 'values', 0, 0], '-0.5', 'grids[0].values[0][0] must be a finite number or null, got "-0.5"'],
    ['a value NaN', ['grids', 0, 'values', 1, 2], NaN, 'grids[0].values[1][2] must be a finite number or null, got number NaN'],
    ['n not an array', ['grids', 0, 'n'], 4, 'grids[0].n must be an array, got number 4'],
    ['n with too many rows', ['grids', 0, 'n'], [[4, 4, 3], [5, 0, 5], [1, 1, 1]], 'grids[0].n must have 2 rows (one per row label), got 3'],
    ['n with a ragged row', ['grids', 0, 'n', 0], [4, 4], 'grids[0].n[0] must have 3 entries (one per column label), got 2'],
    ['an n null', ['grids', 0, 'n', 1, 1], null, 'grids[0].n[1][1] must be a non-negative integer, got null'],
    ['an n negative', ['grids', 0, 'n', 0, 0], -1, 'grids[0].n[0][0] must be a non-negative integer, got number -1'],
    ['an n fractional', ['grids', 0, 'n', 0, 0], 4.5, 'grids[0].n[0][0] must be a non-negative integer, got number 4.5'],
    ['q not an array or null', ['grids', 1, 'q'], 0.5, 'grids[1].q must be an array, got number 0.5'],
    ['q with a ragged row', ['grids', 1, 'q', 1], [0.1], 'grids[1].q[1] must have 2 entries (one per column label), got 1'],
    ['q with too few rows', ['grids', 1, 'q'], [[0.5, null]], 'grids[1].q must have 2 rows (one per row label), got 1'],
    ['a q above 1', ['grids', 1, 'q', 0, 0], 1.5, 'grids[1].q[0][0] must be a number from 0 to 1 or null, got number 1.5'],
    ['a q negative', ['grids', 1, 'q', 1, 1], -0.1, 'grids[1].q[1][1] must be a number from 0 to 1 or null, got number -0.1'],
    ['a q a string', ['grids', 1, 'q', 1, 0], '0.1', 'grids[1].q[1][0] must be a number from 0 to 1 or null, got "0.1"'],
    ['lookups not an object', ['lookups'], [], 'lookups must be an object, got an array'],
    ['caveats not an array', ['caveats'], null, 'caveats must be an array, got null'],
    ['provenance missing key', ['provenance', 'code_commit'], undefined, 'provenance has missing key(s): code_commit'],
  ])('rejects: %s', (_what, path, value, message) => {
    expect(errorOf(edited(path, value))).toContain(message)
  })
})

describe('cellText: row, column, value and n', () => {
  it('names the row label, the column label, the value as given and n', () => {
    const [byDay] = grids()
    expect(cellText(byDay, 0, 0)).toBe('FXA, -1: -0.5 (n = 4)')
    expect(cellText(byDay, 1, 2)).toBe('FXB, 1: -0.25 (n = 5)')
  })
  it('says "no data" for a null cell (never 0) and still gives n', () => {
    const [byDay] = grids()
    expect(cellText(byDay, 1, 1)).toBe('FXB, 0: no data (n = 0)')
  })
  it('shows a real 0 as 0', () => {
    const [byDay] = grids()
    expect(cellText(byDay, 0, 1)).toBe('FXA, 0: 0 (n = 4)')
  })
  it('uses the row label, not the row key, and adds the q-value when the cell has one', () => {
    const [, bySeason] = grids()
    expect(cellText(bySeason, 1, 0)).toBe('FX Beta, 2031Q1: -2 (n = 1), q = 0.125')
    expect(cellText(bySeason, 0, 0)).toBe('FX Alpha, 2031Q1: 1 (n = 1), q = 0.5')
  })
  it('leaves q out for a cell whose q is null', () => {
    const [, bySeason] = grids()
    expect(cellText(bySeason, 0, 1)).toBe('FX Alpha, 2031Q2: no data (n = 0)')
  })
})

describeLoader({
  name: 'loadHeatmap',
  load: loadHeatmap,
  defaultUrl: 'data/heatmap.json',
  kind: 'heatmap',
  body: HEATMAP_FIXTURE,
  data: HEATMAP_DATA_FIXTURE,
  brokenBody: { ...HEATMAP_FIXTURE, data: edited(['grids', 0, 'n', 0], [4, 4]) },
  brokenError: 'grids[0].n[0] must have 3 entries (one per column label), got 2',
})
