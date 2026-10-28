import { describe, it, expect, vi } from 'vitest'
import { formatMilestone, loadMeta, META_URL, parseMetaData, summarizeMeta } from './meta'
import type { Envelope } from './contract'
import { META_DATA_FIXTURE } from '../test/metaFixture'

const body = {
  schema_version: '0.1.0',
  kind: 'meta',
  generated_at: '2026-10-27T12:00:00Z',
  source_commit: 'abc1234',
  data: { milestone: 0 },
}

/** A fake fetch that answers with the given Response-like object. */
const fakeFetch = (res: Partial<Response>) => vi.fn(async () => res as Response) as unknown as typeof fetch

describe('META_URL', () => {
  it('is relative (no leading slash, no scheme) so the app works under a sub-path', () => {
    expect(META_URL).toBe('data/meta.json')
    expect(META_URL.startsWith('/')).toBe(false)
    expect(META_URL).not.toMatch(/^[a-z]+:/i)
  })
})

describe('loadMeta', () => {
  it('returns the validated envelope for a good response, requesting the given URL', async () => {
    const f = fakeFetch({ ok: true, status: 200, json: async () => body })
    const r = await loadMeta('x/meta.json', f)
    expect(r).toEqual({ ok: true, envelope: body })
    expect(f).toHaveBeenCalledWith('x/meta.json', { cache: 'no-cache' })
  })
  it('reports a network failure without throwing', async () => {
    const f = vi.fn(async () => {
      throw new TypeError('Failed to fetch')
    }) as unknown as typeof fetch
    const r = await loadMeta('data/meta.json', f)
    expect(r).toEqual({ ok: false, error: 'could not fetch data/meta.json: Failed to fetch' })
  })
  it('reports a non-Error rejection too', async () => {
    const f = vi.fn(async () => {
      throw 'boom'
    }) as unknown as typeof fetch
    const r = await loadMeta('data/meta.json', f)
    expect(r).toEqual({ ok: false, error: 'could not fetch data/meta.json: boom' })
  })
  it('reports an HTTP error status', async () => {
    const r = await loadMeta('data/meta.json', fakeFetch({ ok: false, status: 404 }))
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.error).toContain('HTTP 404')
  })
  it('reports a body that is not JSON (e.g. an HTML fallback page for a missing file)', async () => {
    const f = fakeFetch({
      ok: true,
      status: 200,
      json: async () => {
        throw new SyntaxError('Unexpected token <')
      },
    })
    const r = await loadMeta('data/meta.json', f)
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.error).toContain('is not valid JSON')
  })
  it('passes contract violations through (here: a wrong schema version)', async () => {
    const r = await loadMeta('data/meta.json', fakeFetch({ ok: true, status: 200, json: async () => ({ ...body, schema_version: '0.0.1' }) }))
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.error).toContain('unsupported schema_version')
  })
  it('defaults to the global fetch and the relative META_URL', async () => {
    const spy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({ ok: true, status: 200, json: async () => body } as Response)
    const r = await loadMeta()
    expect(r.ok).toBe(true)
    expect(spy).toHaveBeenCalledWith('data/meta.json', { cache: 'no-cache' })
    spy.mockRestore()
  })
})

describe('summarizeMeta', () => {
  const env = body as Envelope
  it('copies the envelope fields and reads data.milestone when it is an integer (the exporter writes 0 for M0)', () => {
    expect(summarizeMeta(env)).toEqual({
      schemaVersion: '0.1.0',
      kind: 'meta',
      generatedAt: '2026-10-27T12:00:00Z',
      sourceCommit: 'abc1234',
      milestone: 0,
    })
  })
  it('accepts any finite non-negative integer', () => {
    for (const m of [0, 1, 7, 1000]) expect(summarizeMeta({ ...env, data: { milestone: m } }).milestone, String(m)).toBe(m)
  })
  it('gives milestone null (unknown) for anything else, with no coercion', () => {
    const bad: unknown[] = [
      'M0', // a string, even a sensible one
      '0', // a numeric string
      NaN,
      Infinity,
      -Infinity,
      -1, // negative
      1.5, // fractional
      null,
      true,
      [0],
      { n: 0 },
    ]
    for (const m of bad) expect(summarizeMeta({ ...env, data: { milestone: m } }).milestone, String(m)).toBeNull()
    expect(summarizeMeta({ ...env, data: {} }).milestone).toBeNull() // key absent
  })
})

describe('formatMilestone', () => {
  it('prefixes an integer with M, and says "unknown" for null', () => {
    expect(formatMilestone(0)).toBe('M0')
    expect(formatMilestone(12)).toBe('M12')
    expect(formatMilestone(null)).toBe('unknown')
  })
})

describe('parseMetaData', () => {
  type Path = (string | number)[]
  /** A deep copy of the hand-built good `data` with the value at `path` replaced (`undefined` deletes the key). */
  const edited = (path: Path, value: unknown): unknown => {
    const root = structuredClone(META_DATA_FIXTURE) as Record<string, unknown>
    let node: Record<string | number, unknown> = root
    for (const key of path.slice(0, -1)) node = node[key] as Record<string | number, unknown>
    const last = path[path.length - 1]
    if (value === undefined) delete node[last]
    else node[last] = value
    return root
  }
  const errorOf = (input: unknown): string => {
    const r = parseMetaData(input)
    if (r.ok) throw new Error('expected a failure, but the input was accepted')
    return r.error
  }

  it('accepts the exporter shape and returns the same values', () => {
    const r = parseMetaData(META_DATA_FIXTURE)
    expect(r).toEqual({ ok: true, data: META_DATA_FIXTURE })
  })
  it('keeps the order of the sources', () => {
    const r = parseMetaData(edited(['data_sources'], [...META_DATA_FIXTURE.data_sources].reverse()))
    if (!r.ok) throw new Error(r.error)
    expect(r.data.data_sources.map((s) => s.name)).toEqual(['Fixture vendor', 'Fixture open source'])
  })
  it('accepts a licence whose applies_to list is empty', () => {
    expect(parseMetaData(edited(['data_licence', 'applies_to'], [])).ok).toBe(true)
  })

  it('rejects an input that is not a JSON object', () => {
    for (const x of [null, undefined, [], 'meta', 5, true]) expect(errorOf(x), String(x)).toContain('meta data must be a JSON object')
  })
  it('names missing and unexpected keys', () => {
    expect(errorOf(edited(['data_licence'], undefined))).toBe(
      'meta data has missing key(s): data_licence (expected exactly: project, milestone, title, data_sources, data_licence)',
    )
    expect(errorOf(edited(['sample'], {}))).toBe(
      'meta data has unexpected key(s): sample (expected exactly: project, milestone, title, data_sources, data_licence)',
    )
    expect(errorOf({ milestone: 0 })).toContain('missing key(s): project, title, data_sources, data_licence')
  })

  // [what is wrong, where, the bad value, a piece of the message]
  it.each<[string, Path, unknown, string]>([
    ['project is empty', ['project'], '', 'project must be a non-empty string, got ""'],
    ['project is blank', ['project'], '   ', 'project must be a non-empty string'],
    ['project is a number', ['project'], 5, 'project must be a non-empty string, got number 5'],
    ['title is null', ['title'], null, 'title must be a non-empty string, got null'],
    ['milestone is a string', ['milestone'], '0', 'milestone must be a non-negative integer, got "0"'],
    ['milestone is negative', ['milestone'], -1, 'milestone must be a non-negative integer, got number -1'],
    ['milestone is fractional', ['milestone'], 1.5, 'milestone must be a non-negative integer, got number 1.5'],
    ['milestone is an array', ['milestone'], [0], 'milestone must be a non-negative integer, got an array'],
    ['milestone is an object', ['milestone'], {}, 'milestone must be a non-negative integer, got an object'],
  ])('rejects: %s', (_what, path, value, message) => {
    expect(errorOf(edited(path, value))).toContain(message)
  })

  it.each<[string, Path, unknown, string]>([
    ['data_sources is not an array', ['data_sources'], {}, 'data_sources must be a non-empty array, got an object'],
    ['data_sources is empty', ['data_sources'], [], 'data_sources must be a non-empty array, got an array'],
    ['a source is not an object', ['data_sources', 1], 'x', 'data_sources[1] must be an object, got "x"'],
    ['a source is null', ['data_sources', 0], null, 'data_sources[0] must be an object, got null'],
    ['a source lacks a key', ['data_sources', 1, 'uses'], undefined, 'data_sources[1] has missing key(s): uses'],
    ['a source has an extra key', ['data_sources', 0, 'note'], 'x', 'data_sources[0] has unexpected key(s): note'],
    ['a name is empty', ['data_sources', 0, 'name'], '', 'data_sources[0].name must be a non-empty string'],
    ['a name is listed twice', ['data_sources', 1, 'name'], 'Fixture open source', 'data_sources[1].name "Fixture open source" is listed twice'],
    ['uses is blank', ['data_sources', 0, 'uses'], ' ', 'data_sources[0].uses must be a non-empty string'],
    ['url is http', ['data_sources', 0, 'url'], 'http://example.com/', 'data_sources[0].url must be an https:// URL, got "http://example.com/"'],
    ['url is a javascript: link', ['data_sources', 1, 'url'], 'javascript:alert(1)', 'data_sources[1].url must be an https:// URL'],
    ['url is empty', ['data_sources', 0, 'url'], '', 'data_sources[0].url must be an https:// URL'],
    ['url has a space', ['data_sources', 0, 'url'], 'https://example.com/a b', 'data_sources[0].url must be an https:// URL'],
    ['url is not a string', ['data_sources', 0, 'url'], 5, 'data_sources[0].url must be an https:// URL, got number 5'],
    ['licence is empty', ['data_sources', 1, 'licence'], '', 'data_sources[1].licence must be a non-empty string'],
    ['committed is the string "true"', ['data_sources', 0, 'committed'], 'true', 'data_sources[0].committed must be true or false, got "true"'],
    ['committed is 1', ['data_sources', 1, 'committed'], 1, 'data_sources[1].committed must be true or false, got number 1'],
  ])('rejects data_sources: %s', (_what, path, value, message) => {
    expect(errorOf(edited(path, value))).toContain(message)
  })

  it.each<[string, Path, unknown, string]>([
    ['data_licence is an array', ['data_licence'], [], 'data_licence must be an object, got an array'],
    ['data_licence is null', ['data_licence'], null, 'data_licence must be an object, got null'],
    ['data_licence lacks a key', ['data_licence', 'attribution'], undefined, 'data_licence has missing key(s): attribution'],
    ['data_licence has an extra key', ['data_licence', 'year'], 2026, 'data_licence has unexpected key(s): year'],
    ['licence name is empty', ['data_licence', 'name'], '', 'data_licence.name must be a non-empty string'],
    ['licence url is http', ['data_licence', 'url'], 'http://example.com/l', 'data_licence.url must be an https:// URL'],
    ['attribution is blank', ['data_licence', 'attribution'], '  ', 'data_licence.attribution must be a non-empty string'],
    ['attribution is a number', ['data_licence', 'attribution'], 1, 'data_licence.attribution must be a non-empty string, got number 1'],
    ['applies_to is a string', ['data_licence', 'applies_to'], 'Fixture open source', 'data_licence.applies_to must be an array, got "Fixture open source"'],
    ['applies_to names an unknown source', ['data_licence', 'applies_to'], ['Nobody'], 'data_licence.applies_to[0] must name one of the data_sources, got "Nobody"'],
    ['applies_to holds a number', ['data_licence', 'applies_to'], ['Fixture open source', 7], 'data_licence.applies_to[1] must name one of the data_sources, got number 7'],
    [
      'a covered source row carries another licence',
      ['data_sources', 0, 'licence'],
      'FIX-OTHER 2.0',
      'data_licence.applies_to[0] "Fixture open source" is covered by "FIX-OPEN 1.0", but data_sources lists its licence as "FIX-OTHER 2.0"',
    ],
    [
      'the licence is renamed but the covered source row is not',
      ['data_licence', 'name'],
      'FIX-OTHER 2.0',
      'data_licence.applies_to[0] "Fixture open source" is covered by "FIX-OTHER 2.0", but data_sources lists its licence as "FIX-OPEN 1.0"',
    ],
    [
      'the second covered source carries another licence (every entry is checked)',
      ['data_licence', 'applies_to'],
      ['Fixture open source', 'Fixture vendor'],
      'data_licence.applies_to[1] "Fixture vendor" is covered by "FIX-OPEN 1.0", but data_sources lists its licence as "see source"',
    ],
  ])('rejects data_licence: %s', (_what, path, value, message) => {
    expect(errorOf(edited(path, value))).toContain(message)
  })
  it('lets a source that the licence does not cover carry any licence text', () => {
    // The fixture's second source says "see source" and is not in applies_to.
    expect(parseMetaData(edited(['data_sources', 1, 'licence'], 'FIX-OTHER 2.0')).ok).toBe(true)
  })

  it('does not coerce or mutate its input, and returns a copy of applies_to', () => {
    const input = structuredClone(META_DATA_FIXTURE)
    const r = parseMetaData(input)
    expect(input).toEqual(META_DATA_FIXTURE)
    if (!r.ok) throw new Error(r.error)
    expect(r.data.data_licence.applies_to).not.toBe(input.data_licence.applies_to)
  })
})
