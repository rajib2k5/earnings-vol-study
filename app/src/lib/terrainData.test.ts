import { describe, it, expect } from 'vitest'
import { loadTerrainData, parseTerrainData, TERRAIN_KIND, TERRAIN_URL, terrainCaption, terrainGrid, type TerrainData } from './terrainData'
import { gridToTerrain } from './terrain'
import { TERRAIN_DATA_FIXTURE, TERRAIN_FIXTURE } from '../test/terrainFixture'
import { PROVENANCE_FIXTURE } from '../test/metaFixture'
import { describeLoader, edited as editedOf, errorOfParse, type Path } from '../test/editHelpers'

const edited = (path: Path, value: unknown): unknown => editedOf(TERRAIN_DATA_FIXTURE, path, value)
const errorOf = (input: unknown): string => errorOfParse(parseTerrainData(input))

const KEYS = ['measure', 'units', 'rel_days', 'rows', 'values', 'row_order', 'lookups', 'caveats', 'provenance']
const KEY_LIST = KEYS.join(', ')
const ROW_KEY_LIST = 'security_id, ticker, sector, n_events'

const good = (): TerrainData => {
  const r = parseTerrainData(TERRAIN_DATA_FIXTURE)
  if (!r.ok) throw new Error(r.error)
  return r.data
}

describe('parseTerrainData: accepts the exporter shape', () => {
  it('returns the same values for a good file', () => {
    expect(parseTerrainData(TERRAIN_DATA_FIXTURE)).toEqual({ ok: true, data: TERRAIN_DATA_FIXTURE })
  })
  it('does not mutate its input and returns copies', () => {
    const input = structuredClone(TERRAIN_DATA_FIXTURE)
    const r = parseTerrainData(input)
    expect(input).toEqual(TERRAIN_DATA_FIXTURE)
    if (!r.ok) throw new Error(r.error)
    expect(r.data.values).not.toBe(input.values)
    expect(r.data.values[0]).not.toBe(input.values[0])
    expect(r.data.rel_days).not.toBe(input.rel_days)
    expect(r.data.rows).not.toBe(input.rows)
    expect(r.data.caveats).not.toBe(input.caveats)
  })
  it('returns the provenance with the same values as meta.json carries', () => {
    expect(good().provenance).toEqual(PROVENANCE_FIXTURE)
  })
  it('keeps a null cell as null (not 0), and accepts a row whose cells are all null', () => {
    expect(good().values[1][1]).toBeNull()
    expect(parseTerrainData(edited(['values', 0], [null, null, null])).ok).toBe(true)
  })
  it('accepts zero events for a company and a single company with a single day', () => {
    expect(parseTerrainData(edited(['rows', 0, 'n_events'], 0)).ok).toBe(true)
    const small = { ...TERRAIN_DATA_FIXTURE, rel_days: [0], rows: [TERRAIN_DATA_FIXTURE.rows[0]], values: [[0.5]] }
    expect(parseTerrainData(small).ok).toBe(true)
  })
})

describe('parseTerrainData: key sets must be exact', () => {
  it('rejects an input that is not a JSON object', () => {
    for (const x of [null, undefined, [], 'terrain', 3]) expect(errorOf(x), String(x)).toContain('terrain data must be a JSON object')
  })
  it.each(KEYS)('requires the key %s', (key) => {
    expect(errorOf(edited([key], undefined))).toBe(`terrain data has missing key(s): ${key} (expected exactly: ${KEY_LIST})`)
  })
  it('rejects an extra key and names it', () => {
    expect(errorOf(edited(['colour'], 'red'))).toBe(`terrain data has unexpected key(s): colour (expected exactly: ${KEY_LIST})`)
  })
  it.each(['security_id', 'ticker', 'sector', 'n_events'])('requires the row key %s', (key) => {
    expect(errorOf(edited(['rows', 1, key], undefined))).toBe(`rows[1] has missing key(s): ${key} (expected exactly: ${ROW_KEY_LIST})`)
  })
  it('rejects an extra row key', () => {
    expect(errorOf(edited(['rows', 0, 'name'], 'x'))).toBe(`rows[0] has unexpected key(s): name (expected exactly: ${ROW_KEY_LIST})`)
  })
  it('names the kind the Python exporter writes', () => {
    expect(TERRAIN_KIND).toBe('terrain')
    expect(TERRAIN_URL).toBe('data/terrain.json')
  })
})

describe('parseTerrainData: types and shapes', () => {
  it.each<[string, Path, unknown, string]>([
    ['measure empty', ['measure'], '', 'measure must be a non-empty string, got ""'],
    ['units a number', ['units'], 3, 'units must be a non-empty string, got number 3'],
    ['row_order null', ['row_order'], null, 'row_order must be a non-empty string, got null'],
    ['rel_days not an array', ['rel_days'], 'days', 'rel_days must be an array, got "days"'],
    ['rel_days empty', ['rel_days'], [], 'rel_days must not be empty'],
    ['rel_days unordered', ['rel_days'], [0, -1, 1], 'rel_days must be strictly increasing, but rel_days[1] (-1) is not above rel_days[0] (0)'],
    ['rows not an array', ['rows'], {}, 'rows must be a non-empty array, got an object'],
    ['rows empty', ['rows'], [], 'rows must be a non-empty array, got an array'],
    ['row not an object', ['rows', 2], 'FXC', 'rows[2] must be an object, got "FXC"'],
    ['security_id empty', ['rows', 0, 'security_id'], '', 'rows[0].security_id must be a non-empty string, got ""'],
    ['ticker null', ['rows', 0, 'ticker'], null, 'rows[0].ticker must be a non-empty string, got null'],
    ['sector a number', ['rows', 1, 'sector'], 1, 'rows[1].sector must be a non-empty string, got number 1'],
    ['n_events negative', ['rows', 1, 'n_events'], -1, 'rows[1].n_events must be a non-negative integer, got number -1'],
    ['n_events fractional', ['rows', 1, 'n_events'], 2.5, 'rows[1].n_events must be a non-negative integer, got number 2.5'],
    ['n_events null', ['rows', 1, 'n_events'], null, 'rows[1].n_events must be a non-negative integer, got null'],
    ['repeated security_id', ['rows', 2, 'security_id'], 'FXA', 'rows[2].security_id "FXA" is already used by rows[0]'],
    ['values not an array', ['values'], null, 'values must be an array, got null'],
    ['too few value rows', ['values'], [[1, 2, 3]], 'values must have 3 rows (one per company in rows), got 1'],
    ['too many value rows', ['values'], [[1, 2, 3], [1, 2, 3], [1, 2, 3], [1, 2, 3]], 'values must have 3 rows (one per company in rows), got 4'],
    ['a ragged row (short)', ['values', 1], [0.5, 0.25], 'values[1] must have 3 entries (one per rel_days entry), got 2'],
    ['a ragged row (long)', ['values', 2], [1, 2, 3, 4], 'values[2] must have 3 entries (one per rel_days entry), got 4'],
    ['a row that is not an array', ['values', 0], 0.25, 'values[0] must be an array, got number 0.25'],
    ['a cell a string', ['values', 0, 1], '0.5', 'values[0][1] must be a finite number or null, got "0.5"'],
    ['a cell NaN', ['values', 2, 2], NaN, 'values[2][2] must be a finite number or null, got number NaN'],
    ['a cell Infinity', ['values', 1, 0], Infinity, 'values[1][0] must be a finite number or null, got number Infinity'],
    ['lookups missing n_done', ['lookups', 'n_done'], undefined, 'lookups has missing key(s): n_done'],
    ['caveats a string', ['caveats'], 'x', 'caveats must be an array, got "x"'],
    ['provenance extra key', ['provenance', 'x'], 1, 'provenance has unexpected key(s): x'],
  ])('rejects: %s', (_what, path, value, message) => {
    expect(errorOf(edited(path, value))).toContain(message)
  })
  it('checks the grid against the number of rows and of rel_days: changing either makes the grid ragged', () => {
    expect(errorOf(edited(['rel_days'], [-1, 0, 1, 2]))).toBe('values[0] must have 4 entries (one per rel_days entry), got 3')
    const fourthCompany = { security_id: 'FXD', ticker: 'FXD', sector: 'Fixture Sector Two', n_events: 1 }
    expect(errorOf({ ...TERRAIN_DATA_FIXTURE, rows: [...TERRAIN_DATA_FIXTURE.rows, fourthCompany] })).toBe('values must have 4 rows (one per company in rows), got 3')
  })
})

describe('terrainGrid: null becomes NaN so the mesh leaves a hole', () => {
  it('keeps every number and turns every null into NaN, row by row', () => {
    const grid = terrainGrid(good())
    expect(grid).toHaveLength(3)
    expect(grid[0]).toEqual([0.25, 0.5, 0.125])
    expect(grid[2]).toEqual([1, 0.75, 0.375])
    expect(Number.isNaN(grid[1][1])).toBe(true)
    expect(grid[1][0]).toBe(0.5)
    expect(grid[1][2]).toBe(0.25)
  })
  it('does not turn a real 0 into NaN', () => {
    const data = good()
    data.values[0][0] = 0
    expect(terrainGrid(data)[0][0]).toBe(0)
  })
  it('does not change the data it was given', () => {
    const data = good()
    terrainGrid(data)
    expect(data.values[1][1]).toBeNull()
  })
  it('builds a mesh with exactly one hole: 9 vertices, 1 missing, and the 4 squares around the middle vertex dropped', () => {
    // 3 x 3 grid, middle vertex missing: all 4 grid squares touch it, so no triangle is left.
    const t = gridToTerrain(terrainGrid(good()), { low: [0, 0, 0], high: [1, 1, 1] })
    expect(t.vertexCount).toBe(9)
    expect(t.missingCount).toBe(1)
    expect(t.indices.length).toBe(0)
    // range of the finite cells, taken from the file: smallest 0.125, largest 1
    expect(t.min).toBe(0.125)
    expect(t.max).toBe(1)
  })
})

describe('terrainCaption', () => {
  it('says what x, z and height mean, in the words of the file', () => {
    expect(terrainCaption(good())).toBe(
      "x: event day (-1 to 1) · z: company (3, in the file's order: fixture sector, then id) · height and colour: fixture abnormal log IV. Gaps are cells with no data.",
    )
  })
  it('uses the first and last rel_day and the number of companies', () => {
    const data = good()
    data.rel_days = [-10, 0, 10]
    data.rows = data.rows.slice(0, 2)
    expect(terrainCaption(data)).toContain('event day (-10 to 10)')
    expect(terrainCaption(data)).toContain('company (2,')
  })
})

describeLoader({
  name: 'loadTerrainData',
  load: loadTerrainData,
  defaultUrl: 'data/terrain.json',
  kind: 'terrain',
  body: TERRAIN_FIXTURE,
  data: TERRAIN_DATA_FIXTURE,
  brokenBody: { ...TERRAIN_FIXTURE, data: edited(['values', 1], [0.5, 0.25]) },
  brokenError: 'values[1] must have 3 entries (one per rel_days entry), got 2',
})
