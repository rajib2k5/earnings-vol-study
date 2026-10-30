import { describe, it, expect, vi } from 'vitest'
import type { Parsed } from '../lib/validate'

export type Path = (string | number)[]

/** A deep copy of `source` with the value at `path` replaced (`undefined` deletes the key). */
export function edited(source: unknown, path: Path, value: unknown): unknown {
  const root = structuredClone(source) as Record<string, unknown>
  let node: Record<string | number, unknown> = root
  for (const key of path.slice(0, -1)) node = node[key] as Record<string | number, unknown>
  const last = path[path.length - 1]
  if (value === undefined) delete node[last]
  else node[last] = value
  return root
}

/** The message of a failed parse; throws if the input was accepted. */
export function errorOfParse(r: Parsed<unknown>): string {
  if (r.ok) throw new Error('expected a failure, but the input was accepted')
  return r.error
}

/** A fake fetch that answers with the given Response-like object. */
export const fakeFetch = (res: Partial<Response>) => vi.fn(async () => res as Response) as unknown as typeof fetch
export const serving = (body: unknown) => fakeFetch({ ok: true, status: 200, json: async () => body })

/**
 * The tests every `load...` function must pass (the same fetch + envelope + kind + shape pipeline):
 * what it requests, how it reports network, HTTP, JSON, version, kind and shape failures.
 * `brokenBody` is a whole file body whose `data` breaks the rule behind `brokenError`.
 */
export function describeLoader<T>(spec: {
  name: string
  load: (url?: string, fetchImpl?: typeof fetch) => Promise<Parsed<T>>
  defaultUrl: string
  kind: string
  body: { kind: string }
  data: unknown
  brokenBody: unknown
  brokenError: string
}) {
  const { name, load, defaultUrl, kind, body, data, brokenBody, brokenError } = spec
  describe(`${name}: the loader`, () => {
    it('returns the validated data for a good response, requesting the given URL without cache', async () => {
      const f = serving(body)
      expect(await load('x/file.json', f)).toEqual({ ok: true, data })
      expect(f).toHaveBeenCalledWith('x/file.json', { cache: 'no-cache' })
    })
    it(`defaults to the global fetch and the relative ${defaultUrl}`, async () => {
      const spy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({ ok: true, status: 200, json: async () => body } as Response)
      const r = await load()
      expect(r.ok).toBe(true)
      expect(spy).toHaveBeenCalledWith(defaultUrl, { cache: 'no-cache' })
      spy.mockRestore()
    })
    it('reports a network failure without throwing', async () => {
      const f = vi.fn(async () => {
        throw new TypeError('Failed to fetch')
      }) as unknown as typeof fetch
      expect(await load(defaultUrl, f)).toEqual({ ok: false, error: `could not fetch ${defaultUrl}: Failed to fetch` })
    })
    it('reports an HTTP error status', async () => {
      const r = await load(defaultUrl, fakeFetch({ ok: false, status: 404 }))
      expect(r).toEqual({ ok: false, error: `${defaultUrl} returned HTTP 404 (has the Python exporter been run?)` })
    })
    it('reports a body that is not JSON', async () => {
      const f = fakeFetch({
        ok: true,
        status: 200,
        json: async () => {
          throw new SyntaxError('Unexpected token <')
        },
      })
      const r = await load(defaultUrl, f)
      expect(r.ok).toBe(false)
      if (!r.ok) expect(r.error).toContain('is not valid JSON')
    })
    it('passes envelope violations through (here: the previous schema version 0.4.0)', async () => {
      const r = await load(defaultUrl, serving({ ...body, schema_version: '0.4.0' }))
      expect(r).toEqual({ ok: false, error: 'unsupported schema_version "0.4.0": this app only understands "0.5.0"' })
    })
    it('refuses a valid envelope of another kind, naming both kinds, before it looks at the data', async () => {
      const r = await load(defaultUrl, serving({ ...body, kind: 'meta' }))
      expect(r).toEqual({ ok: false, error: `${defaultUrl} has kind "meta", expected "${kind}"` })
    })
    it('names the file and the rule when the data has the wrong shape', async () => {
      const r = await load(defaultUrl, serving(brokenBody))
      expect(r).toEqual({ ok: false, error: `${defaultUrl}: ${brokenError}` })
    })
    it(`has the kind "${kind}" in the fixture it is tested with`, () => {
      expect(body.kind).toBe(kind)
    })
  })
}
