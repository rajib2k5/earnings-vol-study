import { describe, it, expect } from 'vitest'
import { eventsInSubgroup, EVENT_PATHS_KIND, EVENT_PATHS_URL, findSeries, loadEventPaths, parseEventPaths, seriesOptions, type PathSeries } from './eventPaths'
import { EVENT_PATHS_DATA_FIXTURE, EVENT_PATHS_FIXTURE } from '../test/eventPathsFixture'
import { PROVENANCE_FIXTURE } from '../test/metaFixture'
import { describeLoader, edited as editedOf, errorOfParse, type Path } from '../test/editHelpers'

const edited = (path: Path, value: unknown): unknown => editedOf(EVENT_PATHS_DATA_FIXTURE, path, value)
const errorOf = (input: unknown): string => errorOfParse(parseEventPaths(input))

const KEYS = ['rel_days', 'series', 'per_event', 'lookups', 'caveats', 'provenance']
const KEY_LIST = KEYS.join(', ')
const SERIES_KEYS = ['measure', 'adjustment', 'units', 'subgroup_key', 'subgroup_value', 'n', 'mean', 'ci_lo', 'ci_hi']
const SERIES_KEY_LIST = SERIES_KEYS.join(', ')
const PER_EVENT_KEYS = ['event_id', 'ticker', 'sector', 'day0', 'timing_used', 'values']
const PER_EVENT_KEY_LIST = PER_EVENT_KEYS.join(', ')

describe('parseEventPaths: accepts the exporter shape', () => {
  it('returns the same values for a good file', () => {
    expect(parseEventPaths(EVENT_PATHS_DATA_FIXTURE)).toEqual({ ok: true, data: EVENT_PATHS_DATA_FIXTURE })
  })
  it('does not mutate its input and returns copies of the arrays', () => {
    const input = structuredClone(EVENT_PATHS_DATA_FIXTURE)
    const r = parseEventPaths(input)
    expect(input).toEqual(EVENT_PATHS_DATA_FIXTURE)
    if (!r.ok) throw new Error(r.error)
    expect(r.data.rel_days).not.toBe(input.rel_days)
    expect(r.data.series[0].mean).not.toBe(input.series[0].mean)
    expect(r.data.per_event[0].values).not.toBe(input.per_event[0].values)
    expect(r.data.caveats).not.toBe(input.caveats)
  })
  it('returns the provenance with the same values as meta.json carries', () => {
    const r = parseEventPaths(EVENT_PATHS_DATA_FIXTURE)
    if (!r.ok) throw new Error(r.error)
    expect(r.data.provenance).toEqual(PROVENANCE_FIXTURE)
  })
  it('keeps a null in the middle of a path as null (not 0), in the series and in the events', () => {
    const r = parseEventPaths(EVENT_PATHS_DATA_FIXTURE)
    if (!r.ok) throw new Error(r.error)
    expect(r.data.series[0].mean[2]).toBeNull()
    expect(r.data.series[0].ci_lo[2]).toBeNull()
    expect(r.data.series[0].n[2]).toBeNull()
    expect(r.data.per_event[1].values[2]).toBeNull()
  })
  it('accepts no events, a null timing_used, no caveats, and one single-day window', () => {
    expect(parseEventPaths(edited(['per_event'], [])).ok).toBe(true)
    expect(parseEventPaths(edited(['per_event', 0, 'timing_used'], null)).ok).toBe(true)
    expect(parseEventPaths(edited(['caveats'], [])).ok).toBe(true)
    const oneDay = {
      ...EVENT_PATHS_DATA_FIXTURE,
      rel_days: [0],
      series: [{ ...EVENT_PATHS_DATA_FIXTURE.series[0], n: [3], mean: [1], ci_lo: [0.5], ci_hi: [1.5] }],
      per_event: [{ ...EVENT_PATHS_DATA_FIXTURE.per_event[0], values: [2] }],
    }
    expect(parseEventPaths(oneDay).ok).toBe(true)
  })
  it('accepts the same subgroup under both adjustments, and a band whose two ends are equal', () => {
    expect(EVENT_PATHS_DATA_FIXTURE.series.filter((s) => s.subgroup_value === 'all').map((s) => s.adjustment)).toEqual(['market', 'mean'])
    expect(parseEventPaths(EVENT_PATHS_DATA_FIXTURE).ok).toBe(true)
    // series[0].ci_lo is [0.25, 0.75, null, 1.75, 2.25]: a ci_hi equal to it is a zero-width band.
    expect(parseEventPaths(edited(['series', 0, 'ci_hi'], [0.25, 0.75, null, 1.75, 2.25])).ok).toBe(true)
  })
})

describe('parseEventPaths: key sets must be exact', () => {
  it('rejects an input that is not a JSON object', () => {
    for (const x of [null, undefined, [], 'paths', 5]) expect(errorOf(x), String(x)).toContain('event paths data must be a JSON object')
    expect(errorOf(null)).toBe('event paths data must be a JSON object, got null')
  })
  it.each(KEYS)('requires the key %s', (key) => {
    expect(errorOf(edited([key], undefined))).toBe(`event paths data has missing key(s): ${key} (expected exactly: ${KEY_LIST})`)
  })
  it('rejects an extra key and names it', () => {
    expect(errorOf(edited(['bands'], []))).toBe(`event paths data has unexpected key(s): bands (expected exactly: ${KEY_LIST})`)
  })
  it.each(SERIES_KEYS)('requires the series key %s', (key) => {
    expect(errorOf(edited(['series', 2, key], undefined))).toBe(`series[2] has missing key(s): ${key} (expected exactly: ${SERIES_KEY_LIST})`)
  })
  it('rejects an extra series key', () => {
    expect(errorOf(edited(['series', 0, 'median'], []))).toBe(`series[0] has unexpected key(s): median (expected exactly: ${SERIES_KEY_LIST})`)
  })
  it.each(PER_EVENT_KEYS)('requires the per_event key %s', (key) => {
    expect(errorOf(edited(['per_event', 1, key], undefined))).toBe(`per_event[1] has missing key(s): ${key} (expected exactly: ${PER_EVENT_KEY_LIST})`)
  })
  it('rejects an extra per_event key', () => {
    expect(errorOf(edited(['per_event', 0, 'name'], 'x'))).toBe(`per_event[0] has unexpected key(s): name (expected exactly: ${PER_EVENT_KEY_LIST})`)
  })
  it('names the kind the Python exporter writes', () => {
    expect(EVENT_PATHS_KIND).toBe('event_paths')
    expect(EVENT_PATHS_URL).toBe('data/event_paths.json')
  })
})

describe('parseEventPaths: rel_days, series and per_event values', () => {
  it.each<[string, Path, unknown, string]>([
    ['rel_days not an array', ['rel_days'], '-2..2', 'rel_days must be an array, got "-2..2"'],
    ['rel_days empty', ['rel_days'], [], 'rel_days must not be empty'],
    ['a fractional day', ['rel_days', 1], -0.5, 'rel_days[1] must be an integer, got number -0.5'],
    ['days out of order', ['rel_days'], [-2, -1, 0, 0, 2], 'rel_days must be strictly increasing, but rel_days[3] (0) is not above rel_days[2] (0)'],
    ['series not an array', ['series'], {}, 'series must be a non-empty array, got an object'],
    ['series empty', ['series'], [], 'series must be a non-empty array, got an array'],
    ['series entry not an object', ['series', 1], 'x', 'series[1] must be an object, got "x"'],
    ['series measure empty', ['series', 0, 'measure'], '', 'series[0].measure must be a non-empty string, got ""'],
    ['series adjustment unknown', ['series', 0, 'adjustment'], 'beta', 'series[0].adjustment must be "market" or "mean", got "beta"'],
    ['series units null', ['series', 0, 'units'], null, 'series[0].units must be a non-empty string, got null'],
    ['series subgroup_key a number', ['series', 1, 'subgroup_key'], 3, 'series[1].subgroup_key must be a non-empty string, got number 3'],
    ['series subgroup_value empty', ['series', 1, 'subgroup_value'], ' ', 'series[1].subgroup_value must be a non-empty string, got " "'],
    ['n not an array', ['series', 0, 'n'], 3, 'series[0].n must be an array, got number 3'],
    ['n entry fractional', ['series', 0, 'n', 1], 2.5, 'series[0].n[1] must be a non-negative integer or null, got number 2.5'],
    ['n entry negative', ['series', 0, 'n', 0], -1, 'series[0].n[0] must be a non-negative integer or null, got number -1'],
    ['n too short (ragged)', ['series', 0, 'n'], [3, 3, 3, 3], 'series[0].n must have 5 entries (one per rel_days entry), got 4'],
    ['mean too long (ragged)', ['series', 3, 'mean'], [1, 2, 3, 2, 1, 0], 'series[3].mean must have 5 entries (one per rel_days entry), got 6'],
    ['mean entry a string', ['series', 3, 'mean', 2], '3', 'series[3].mean[2] must be a finite number or null, got "3"'],
    ['mean entry NaN', ['series', 3, 'mean', 0], NaN, 'series[3].mean[0] must be a finite number or null, got number NaN'],
    ['ci_lo too short (ragged)', ['series', 4, 'ci_lo'], [1, 2], 'series[4].ci_lo must have 5 entries (one per rel_days entry), got 2'],
    ['ci_hi entry Infinity', ['series', 4, 'ci_hi', 4], Infinity, 'series[4].ci_hi[4] must be a finite number or null, got number Infinity'],
    ['ci_hi not an array', ['series', 5, 'ci_hi'], null, 'series[5].ci_hi must be an array, got null'],
    ['band reversed on one day', ['series', 3, 'ci_hi', 1], 1, 'series[3].ci_lo[1] (1.5) must be at most ci_hi[1] (1)'],
    ['repeated series', ['series', 1], { ...EVENT_PATHS_DATA_FIXTURE.series[0] }, 'series[1] repeats series[0] (same adjustment "market" and subgroup "all" = "all")'],
    ['per_event not an array', ['per_event'], null, 'per_event must be an array, got null'],
    ['event not an object', ['per_event', 0], [], 'per_event[0] must be an object, got an array'],
    ['event_id empty', ['per_event', 0, 'event_id'], '', 'per_event[0].event_id must be a non-empty string, got ""'],
    ['ticker a number', ['per_event', 1, 'ticker'], 7, 'per_event[1].ticker must be a non-empty string, got number 7'],
    ['sector null', ['per_event', 1, 'sector'], null, 'per_event[1].sector must be a non-empty string, got null'],
    ['day0 not a real date', ['per_event', 0, 'day0'], '2031-02-30', 'per_event[0].day0 must be a date string YYYY-MM-DD, got "2031-02-30"'],
    ['day0 a timestamp', ['per_event', 0, 'day0'], '2031-01-03T00:00:00Z', 'per_event[0].day0 must be a date string YYYY-MM-DD, got "2031-01-03T00:00:00Z"'],
    ['timing_used unknown', ['per_event', 0, 'timing_used'], 'DMH', 'per_event[0].timing_used must be "BMO", "AMC" or null, got "DMH"'],
    ['timing_used lower case', ['per_event', 0, 'timing_used'], 'bmo', 'per_event[0].timing_used must be "BMO", "AMC" or null, got "bmo"'],
    ['values too short (ragged)', ['per_event', 2, 'values'], [5, 4, 3, 2], 'per_event[2].values must have 5 entries (one per rel_days entry), got 4'],
    ['values too long (ragged)', ['per_event', 0, 'values'], [1, 2, 3, 4, 5, 6], 'per_event[0].values must have 5 entries (one per rel_days entry), got 6'],
    ['values not an array', ['per_event', 0, 'values'], '12345', 'per_event[0].values must be an array, got "12345"'],
    ['a value a string', ['per_event', 1, 'values', 0], '0', 'per_event[1].values[0] must be a finite number or null, got "0"'],
    ['a value undefined-like NaN', ['per_event', 1, 'values', 4], NaN, 'per_event[1].values[4] must be a finite number or null, got number NaN'],
    ['repeated event_id', ['per_event', 2, 'event_id'], 'FXA:2031-01-02', 'per_event[2].event_id "FXA:2031-01-02" is already used by per_event[0]'],
    ['lookups.complete a string', ['lookups', 'complete'], 'false', 'lookups.complete must be true or false, got "false"'],
    ['caveat a number', ['caveats', 0], 1, 'caveats[0] must be a non-empty string, got number 1'],
    ['provenance not an object', ['provenance'], null, 'provenance must be an object, got null'],
  ])('rejects: %s', (_what, path, value, message) => {
    expect(errorOf(edited(path, value))).toContain(message)
  })
  it('measures the length of every array against rel_days, not against a fixed 21', () => {
    // 3 days: arrays of 3 are right and arrays of 5 are ragged.
    const threeDays = {
      ...EVENT_PATHS_DATA_FIXTURE,
      rel_days: [-1, 0, 1],
      series: EVENT_PATHS_DATA_FIXTURE.series.map((s) => ({ ...s, n: s.n.slice(0, 3), mean: s.mean.slice(0, 3), ci_lo: s.ci_lo.slice(0, 3), ci_hi: s.ci_hi.slice(0, 3) })),
      per_event: EVENT_PATHS_DATA_FIXTURE.per_event.map((e) => ({ ...e, values: e.values.slice(0, 3) })),
    }
    expect(parseEventPaths(threeDays).ok).toBe(true)
    expect(errorOf({ ...threeDays, rel_days: [-1, 0, 1, 2] })).toContain('must have 4 entries (one per rel_days entry), got 3')
  })
})

describe('seriesOptions, findSeries and eventsInSubgroup', () => {
  const series = EVENT_PATHS_DATA_FIXTURE.series as unknown as PathSeries[]
  const events = EVENT_PATHS_DATA_FIXTURE.per_event as unknown as Parameters<typeof eventsInSubgroup>[0]

  it('lists each adjustment and subgroup once, in order of first appearance; "all" is labelled all, a timing subgroup by its value', () => {
    expect(seriesOptions(series)).toEqual({
      adjustments: ['market', 'mean'],
      subgroups: [
        { key: 'all', value: 'all', label: 'all' },
        { key: 'timing', value: 'BMO', label: 'BMO' },
        { key: 'timing', value: 'AMC', label: 'AMC' },
      ],
    })
  })
  it('lists only what the file has: a file with one series gives one adjustment and one subgroup', () => {
    expect(seriesOptions([series[4]])).toEqual({ adjustments: ['mean'], subgroups: [{ key: 'timing', value: 'BMO', label: 'BMO' }] })
    expect(seriesOptions([])).toEqual({ adjustments: [], subgroups: [] })
  })
  it('finds the series for an adjustment and subgroup, and nothing for a pair the file lacks', () => {
    expect(findSeries(series, 'market', { key: 'timing', value: 'AMC' })).toBe(series[2])
    expect(findSeries(series, 'mean', { key: 'all', value: 'all' })).toBe(series[3])
    expect(findSeries(series, 'mean', { key: 'timing', value: 'XYZ' })).toBeUndefined()
    expect(findSeries([series[0]], 'mean', { key: 'all', value: 'all' })).toBeUndefined()
    // the key matters too: the same value under another key is another subgroup
    expect(findSeries(series, 'market', { key: 'sector', value: 'BMO' })).toBeUndefined()
  })
  it('filters the events of a timing subgroup by timing_used, keeps all of them for "all", and says null for a subgroup it cannot filter by', () => {
    expect(eventsInSubgroup(events, { key: 'all', value: 'all' })?.map((e) => e.ticker)).toEqual(['FXA', 'FXB', 'FXA'])
    expect(eventsInSubgroup(events, { key: 'timing', value: 'BMO' })?.map((e) => e.event_id)).toEqual(['FXA:2031-01-02', 'FXA:2031-04-03'])
    expect(eventsInSubgroup(events, { key: 'timing', value: 'AMC' })?.map((e) => e.event_id)).toEqual(['FXB:2031-01-09'])
    expect(eventsInSubgroup(events, { key: 'timing', value: 'XYZ' })).toEqual([])
    expect(eventsInSubgroup(events, { key: 'sector', value: 'Fixture Sector One' })).toBeNull()
  })
  it('does not hand back the input array for "all"', () => {
    expect(eventsInSubgroup(events, { key: 'all', value: 'all' })).not.toBe(events)
  })
})

describeLoader({
  name: 'loadEventPaths',
  load: loadEventPaths,
  defaultUrl: 'data/event_paths.json',
  kind: 'event_paths',
  body: EVENT_PATHS_FIXTURE,
  data: EVENT_PATHS_DATA_FIXTURE,
  brokenBody: { ...EVENT_PATHS_FIXTURE, data: edited(['per_event', 2, 'values'], [5, 4, 3, 2]) },
  brokenError: 'per_event[2].values must have 5 entries (one per rel_days entry), got 4',
})
