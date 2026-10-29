import { describe, it, expect, vi } from 'vitest'
import { loadSampleFunnel, parseSampleFunnel, SAMPLE_FUNNEL_URL } from './funnel'
import { FUNNEL_DATA_FIXTURE, FUNNEL_FIXTURE } from '../test/funnelFixture'
import { PROVENANCE_FIXTURE } from '../test/metaFixture'

type Path = (string | number)[]
/** A deep copy of the hand-built good `data` with the value at `path` replaced (`undefined` deletes the key). */
const edited = (path: Path, value: unknown): unknown => {
  const root = structuredClone(FUNNEL_DATA_FIXTURE) as Record<string, unknown>
  let node: Record<string | number, unknown> = root
  for (const key of path.slice(0, -1)) node = node[key] as Record<string | number, unknown>
  const last = path[path.length - 1]
  if (value === undefined) delete node[last]
  else node[last] = value
  return root
}
const errorOf = (input: unknown): string => {
  const r = parseSampleFunnel(input)
  if (r.ok) throw new Error('expected a failure, but the input was accepted')
  return r.error
}

const KEYS = [
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
]
const KEY_LIST = KEYS.join(', ')

describe('parseSampleFunnel: accepts the exporter shape', () => {
  it('returns the same values for a good file', () => {
    expect(parseSampleFunnel(FUNNEL_DATA_FIXTURE)).toEqual({ ok: true, data: FUNNEL_DATA_FIXTURE })
  })
  it('keeps the order of steps and samples exactly as written', () => {
    const r = parseSampleFunnel(
      edited(['by_sample'], [
        { sample: 'none', n_events: 1 },
        { sample: 'daily', n_events: 2 },
      ]),
    )
    if (!r.ok) throw new Error(r.error)
    expect(r.data.by_sample.map((s) => s.sample)).toEqual(['none', 'daily'])
    const s = parseSampleFunnel(edited(['steps'], [...FUNNEL_DATA_FIXTURE.steps].reverse()))
    if (!s.ok) throw new Error(s.error)
    expect(s.data.steps.map((x) => x.step)).toEqual(['fix_range', 'fix_known', 'fix_all'])
  })
  it('accepts zeros, empty sample lists, no caveats and a one-step funnel', () => {
    const zero = { step: 'z', label: 'Zero', n_events: 0, n_removed: 0, reason: null }
    expect(parseSampleFunnel(edited(['steps'], [zero])).ok).toBe(true)
    expect(parseSampleFunnel(edited(['by_sample'], [])).ok).toBe(true)
    expect(parseSampleFunnel(edited(['timing_status_by_sample'], [])).ok).toBe(true)
    expect(parseSampleFunnel(edited(['caveats'], [])).ok).toBe(true)
    expect(parseSampleFunnel(edited(['lookups'], { n_done: 0, complete: true })).ok).toBe(true)
  })
  it('accepts all four sample names', () => {
    for (const sample of ['daily', 'mixed', 'coarse', 'none']) {
      expect(parseSampleFunnel(edited(['by_sample'], [{ sample, n_events: 1 }])).ok, sample).toBe(true)
    }
  })
  it('does not mutate its input and returns copies of the arrays', () => {
    const input = structuredClone(FUNNEL_DATA_FIXTURE)
    const r = parseSampleFunnel(input)
    expect(input).toEqual(FUNNEL_DATA_FIXTURE)
    if (!r.ok) throw new Error(r.error)
    expect(r.data.caveats).not.toBe(input.caveats)
    expect(r.data.steps).not.toBe(input.steps)
    expect(r.data.by_sample).not.toBe(input.by_sample)
    expect(r.data.timing_status_counts).not.toBe(input.timing_status_counts)
  })
})

describe('parseSampleFunnel: key set must be exactly the eleven keys', () => {
  it('rejects an input that is not a JSON object', () => {
    for (const x of [null, undefined, [], 'funnel', 5, true]) expect(errorOf(x), String(x)).toContain('sample funnel data must be a JSON object')
    expect(errorOf(null)).toBe('sample funnel data must be a JSON object, got null')
  })
  it.each(KEYS)('requires the key %s', (key) => {
    expect(errorOf(edited([key], undefined))).toBe(`sample funnel data has missing key(s): ${key} (expected exactly: ${KEY_LIST})`)
  })
  it('rejects an extra key and names it', () => {
    expect(errorOf(edited(['n_total'], 5))).toBe(`sample funnel data has unexpected key(s): n_total (expected exactly: ${KEY_LIST})`)
  })
  it('reports missing and extra keys together', () => {
    const input = edited(['caveats'], undefined) as Record<string, unknown>
    input.note = 'x'
    expect(errorOf(input)).toContain('missing key(s): caveats; unexpected key(s): note')
  })
})

describe('parseSampleFunnel: steps', () => {
  it.each<[string, Path, unknown, string]>([
    ['steps is not an array', ['steps'], {}, 'steps must be a non-empty array, got an object'],
    ['steps is empty', ['steps'], [], 'steps must be a non-empty array, got an array'],
    ['a step is a string', ['steps', 1], 'x', 'steps[1] must be an object, got "x"'],
    ['a step is null', ['steps', 0], null, 'steps[0] must be an object, got null'],
    ['a step lacks a key', ['steps', 2, 'reason'], undefined, 'steps[2] has missing key(s): reason'],
    ['a step has an extra key', ['steps', 0, 'note'], 'x', 'steps[0] has unexpected key(s): note'],
    ['step id is empty', ['steps', 0, 'step'], '', 'steps[0].step must be a non-empty string, got ""'],
    ['step id is a number', ['steps', 1, 'step'], 3, 'steps[1].step must be a non-empty string, got number 3'],
    ['label is blank', ['steps', 2, 'label'], '  ', 'steps[2].label must be a non-empty string'],
    ['n_events is a string', ['steps', 0, 'n_events'], '200', 'steps[0].n_events must be a non-negative integer, got "200"'],
    ['n_events is negative', ['steps', 1, 'n_events'], -1, 'steps[1].n_events must be a non-negative integer, got number -1'],
    ['n_events is fractional', ['steps', 1, 'n_events'], 150.5, 'steps[1].n_events must be a non-negative integer, got number 150.5'],
    ['n_events is NaN', ['steps', 2, 'n_events'], NaN, 'steps[2].n_events must be a non-negative integer, got number NaN'],
    ['n_events is Infinity', ['steps', 2, 'n_events'], Infinity, 'steps[2].n_events must be a non-negative integer, got number Infinity'],
    ['n_removed is null', ['steps', 1, 'n_removed'], null, 'steps[1].n_removed must be a non-negative integer, got null'],
    ['n_removed is negative', ['steps', 2, 'n_removed'], -50, 'steps[2].n_removed must be a non-negative integer, got number -50'],
    ['reason is a number', ['steps', 1, 'reason'], 5, 'steps[1].reason must be a string or null, got number 5'],
    ['reason is an array', ['steps', 1, 'reason'], ['a'], 'steps[1].reason must be a string or null, got an array'],
  ])('rejects: %s', (_what, path, value, message) => {
    expect(errorOf(edited(path, value))).toContain(message)
  })
  it('allows a string reason (even an empty one) and null', () => {
    expect(parseSampleFunnel(edited(['steps', 1, 'reason'], '')).ok).toBe(true)
    expect(parseSampleFunnel(edited(['steps', 1, 'reason'], null)).ok).toBe(true)
  })
})

describe('parseSampleFunnel: timing status counts', () => {
  const STATUSES = ['confirmed', 'corrected', 'inferred', 'date_corrected', 'no_document', 'not_checked', 'ambiguous']
  it('rejects a non-object', () => {
    expect(errorOf(edited(['timing_status_counts'], [1, 2]))).toContain('timing_status_counts must be an object, got an array')
    expect(errorOf(edited(['timing_status_counts'], null))).toContain('timing_status_counts must be an object, got null')
  })
  it.each(STATUSES)('requires the status %s', (status) => {
    const msg = errorOf(edited(['timing_status_counts', status], undefined))
    expect(msg).toBe(
      `timing_status_counts has missing key(s): ${status} (expected exactly: ${STATUSES.join(', ')})`,
    )
  })
  it('rejects an eighth status', () => {
    expect(errorOf(edited(['timing_status_counts', 'pending'], 3))).toContain('timing_status_counts has unexpected key(s): pending')
  })
  it.each(STATUSES)('rejects a count that is not a non-negative integer (%s)', (status) => {
    expect(errorOf(edited(['timing_status_counts', status], -1))).toContain(`timing_status_counts.${status} must be a non-negative integer, got number -1`)
    expect(errorOf(edited(['timing_status_counts', status], '4'))).toContain(`timing_status_counts.${status} must be a non-negative integer, got "4"`)
    expect(errorOf(edited(['timing_status_counts', status], 2.5))).toContain(`timing_status_counts.${status} must be a non-negative integer, got number 2.5`)
  })
})

describe('parseSampleFunnel: timing_status_by_sample and by_sample', () => {
  it.each<[string, Path, unknown, string]>([
    ['timing_status_by_sample is an object', ['timing_status_by_sample'], {}, 'timing_status_by_sample must be an array, got an object'],
    ['a row is null', ['timing_status_by_sample', 0], null, 'timing_status_by_sample[0] must be an object, got null'],
    ['a row lacks timing_status_counts', ['timing_status_by_sample', 1, 'timing_status_counts'], undefined, 'timing_status_by_sample[1] has missing key(s): timing_status_counts'],
    ['a row has an extra key', ['timing_status_by_sample', 2, 'n_events'], 1, 'timing_status_by_sample[2] has unexpected key(s): n_events'],
    ['sample is not one of the four', ['timing_status_by_sample', 0, 'sample'], 'weekly', 'timing_status_by_sample[0].sample must be one of daily, mixed, coarse, none, got "weekly"'],
    ['sample is upper case', ['timing_status_by_sample', 0, 'sample'], 'Daily', 'timing_status_by_sample[0].sample must be one of'],
    ['sample is a number', ['timing_status_by_sample', 3, 'sample'], 1, 'timing_status_by_sample[3].sample must be one of daily, mixed, coarse, none, got number 1'],
    ['a status count is missing', ['timing_status_by_sample', 1, 'timing_status_counts', 'inferred'], undefined, 'timing_status_by_sample[1].timing_status_counts has missing key(s): inferred'],
    ['a status count is negative', ['timing_status_by_sample', 2, 'timing_status_counts', 'ambiguous'], -3, 'timing_status_by_sample[2].timing_status_counts.ambiguous must be a non-negative integer, got number -3'],
    ['by_sample is null', ['by_sample'], null, 'by_sample must be an array, got null'],
    ['by_sample row is a string', ['by_sample', 2], 'x', 'by_sample[2] must be an object, got "x"'],
    ['by_sample row lacks n_events', ['by_sample', 0, 'n_events'], undefined, 'by_sample[0] has missing key(s): n_events'],
    ['by_sample row has an extra key', ['by_sample', 0, 'share'], 0.3, 'by_sample[0] has unexpected key(s): share'],
    ['by_sample sample is unknown', ['by_sample', 1, 'sample'], 'other', 'by_sample[1].sample must be one of daily, mixed, coarse, none, got "other"'],
    ['by_sample n_events is a string', ['by_sample', 3, 'n_events'], '24', 'by_sample[3].n_events must be a non-negative integer, got "24"'],
    ['by_sample n_events is fractional', ['by_sample', 3, 'n_events'], 0.5, 'by_sample[3].n_events must be a non-negative integer, got number 0.5'],
  ])('rejects: %s', (_what, path, value, message) => {
    expect(errorOf(edited(path, value))).toContain(message)
  })
})

describe('parseSampleFunnel: the milestone-2 fields are null for now', () => {
  it('accepts null for by_move_tercile and evar_nonpositive', () => {
    const r = parseSampleFunnel(FUNNEL_DATA_FIXTURE)
    if (!r.ok) throw new Error(r.error)
    expect(r.data.by_move_tercile).toBeNull()
    expect(r.data.evar_nonpositive).toBeNull()
  })
  it.each<[string, unknown, string]>([
    ['an empty array', [], 'an array'],
    ['an array of tercile rows', [{ tercile: 1, n_events: 3 }], 'an array'],
    ['an object', {}, 'an object'],
    ['a number', 0, 'number 0'],
    ['a string', 'none', '"none"'],
  ])('rejects %s for by_move_tercile and evar_nonpositive, saying it is reserved for milestone 2', (_what, value, shown) => {
    expect(errorOf(edited(['by_move_tercile'], value))).toBe(`by_move_tercile must be null at schema 0.2.0 (an array is reserved for milestone 2), got ${shown}`)
    expect(errorOf(edited(['evar_nonpositive'], value))).toBe(`evar_nonpositive must be null at schema 0.2.0 (an array is reserved for milestone 2), got ${shown}`)
  })
  it('does not treat a missing key as null', () => {
    expect(errorOf(edited(['by_move_tercile'], undefined))).toContain('missing key(s): by_move_tercile')
  })
  it.each(['by_move_tercile_status', 'evar_nonpositive_status'])('requires %s to be a non-empty string', (key) => {
    expect(errorOf(edited([key], ''))).toBe(`${key} must be a non-empty string, got ""`)
    expect(errorOf(edited([key], '   '))).toContain(`${key} must be a non-empty string`)
    expect(errorOf(edited([key], null))).toBe(`${key} must be a non-empty string, got null`)
    expect(errorOf(edited([key], 7))).toBe(`${key} must be a non-empty string, got number 7`)
  })
})

describe('parseSampleFunnel: lookups, caveats, provenance', () => {
  it.each<[string, Path, unknown, string]>([
    ['lookups is null', ['lookups'], null, 'lookups must be an object, got null'],
    ['lookups is an array', ['lookups'], [7, false], 'lookups must be an object, got an array'],
    ['lookups lacks complete', ['lookups', 'complete'], undefined, 'lookups has missing key(s): complete (expected exactly: n_done, complete)'],
    ['lookups has an extra key', ['lookups', 'n_total'], 9, 'lookups has unexpected key(s): n_total'],
    ['n_done is negative', ['lookups', 'n_done'], -1, 'lookups.n_done must be a non-negative integer, got number -1'],
    ['n_done is a string', ['lookups', 'n_done'], '7', 'lookups.n_done must be a non-negative integer, got "7"'],
    ['n_done is fractional', ['lookups', 'n_done'], 7.5, 'lookups.n_done must be a non-negative integer, got number 7.5'],
    ['complete is the string "false"', ['lookups', 'complete'], 'false', 'lookups.complete must be true or false, got "false"'],
    ['complete is 0', ['lookups', 'complete'], 0, 'lookups.complete must be true or false, got number 0'],
    ['caveats is a string', ['caveats'], 'one caveat', 'caveats must be an array, got "one caveat"'],
    ['caveats is null', ['caveats'], null, 'caveats must be an array, got null'],
    ['a caveat is empty', ['caveats', 1], '', 'caveats[1] must be a non-empty string, got ""'],
    ['a caveat is blank', ['caveats', 0], '   ', 'caveats[0] must be a non-empty string'],
    ['a caveat is a number', ['caveats', 0], 4, 'caveats[0] must be a non-empty string, got number 4'],
    ['provenance is null', ['provenance'], null, 'provenance must be an object, got null'],
    ['provenance lacks a key', ['provenance', 'params_hash'], undefined, 'provenance has missing key(s): params_hash'],
    ['provenance has an extra key', ['provenance', 'branch'], 'main', 'provenance has unexpected key(s): branch'],
    ['provenance dolt commit is empty', ['provenance', 'dolt_commits', 'earnings'], '', 'provenance.dolt_commits.earnings must be a non-empty string'],
    ['provenance sample_label is a number', ['provenance', 'sample_label'], 1, 'provenance.sample_label must be a non-empty string, got number 1'],
  ])('rejects: %s', (_what, path, value, message) => {
    expect(errorOf(edited(path, value))).toContain(message)
  })
  it('returns the provenance with the same values as meta.json carries', () => {
    const r = parseSampleFunnel(FUNNEL_DATA_FIXTURE)
    if (!r.ok) throw new Error(r.error)
    expect(r.data.provenance).toEqual(PROVENANCE_FIXTURE)
  })
})

describe('SAMPLE_FUNNEL_URL', () => {
  it('is relative (no leading slash, no scheme) so the app works under a sub-path', () => {
    expect(SAMPLE_FUNNEL_URL).toBe('data/sample_funnel.json')
  })
})

describe('loadSampleFunnel', () => {
  /** A fake fetch that answers with the given Response-like object. */
  const fakeFetch = (res: Partial<Response>) => vi.fn(async () => res as Response) as unknown as typeof fetch
  const serving = (body: unknown) => fakeFetch({ ok: true, status: 200, json: async () => body })

  it('returns the validated data for a good response, requesting the given URL without cache', async () => {
    const f = serving(FUNNEL_FIXTURE)
    const r = await loadSampleFunnel('x/sample_funnel.json', f)
    expect(r).toEqual({ ok: true, data: FUNNEL_DATA_FIXTURE })
    expect(f).toHaveBeenCalledWith('x/sample_funnel.json', { cache: 'no-cache' })
  })
  it('defaults to the global fetch and the relative SAMPLE_FUNNEL_URL', async () => {
    const spy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({ ok: true, status: 200, json: async () => FUNNEL_FIXTURE } as Response)
    const r = await loadSampleFunnel()
    expect(r.ok).toBe(true)
    expect(spy).toHaveBeenCalledWith('data/sample_funnel.json', { cache: 'no-cache' })
    spy.mockRestore()
  })
  it('reports a network failure without throwing', async () => {
    const f = vi.fn(async () => {
      throw new TypeError('Failed to fetch')
    }) as unknown as typeof fetch
    expect(await loadSampleFunnel('data/sample_funnel.json', f)).toEqual({ ok: false, error: 'could not fetch data/sample_funnel.json: Failed to fetch' })
  })
  it('reports an HTTP error status', async () => {
    const r = await loadSampleFunnel('data/sample_funnel.json', fakeFetch({ ok: false, status: 404 }))
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.error).toContain('data/sample_funnel.json returned HTTP 404')
  })
  it('reports a body that is not JSON', async () => {
    const f = fakeFetch({
      ok: true,
      status: 200,
      json: async () => {
        throw new SyntaxError('Unexpected token <')
      },
    })
    const r = await loadSampleFunnel('data/sample_funnel.json', f)
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.error).toContain('is not valid JSON')
  })
  it('passes envelope violations through (here: the previous schema version)', async () => {
    const r = await loadSampleFunnel('data/sample_funnel.json', serving({ ...FUNNEL_FIXTURE, schema_version: '0.1.0' }))
    expect(r).toEqual({ ok: false, error: 'unsupported schema_version "0.1.0": this app only understands "0.2.0"' })
  })
  it('refuses a valid envelope of another kind, naming both kinds', async () => {
    const r = await loadSampleFunnel('data/sample_funnel.json', serving({ ...FUNNEL_FIXTURE, kind: 'meta' }))
    expect(r).toEqual({ ok: false, error: 'data/sample_funnel.json has kind "meta", expected "sample_funnel"' })
  })
  it('names the file and the rule when the data has the wrong shape', async () => {
    const broken = { ...FUNNEL_FIXTURE, data: edited(['steps'], []) }
    const r = await loadSampleFunnel('data/sample_funnel.json', serving(broken))
    expect(r).toEqual({ ok: false, error: 'data/sample_funnel.json: steps must be a non-empty array, got an array' })
  })
  it('checks the kind before looking at the data (a meta file is not reported as a bad funnel)', async () => {
    const r = await loadSampleFunnel('data/sample_funnel.json', serving({ ...FUNNEL_FIXTURE, kind: 'meta', data: { milestone: 1 } }))
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.error).toContain('expected "sample_funnel"')
  })
})
