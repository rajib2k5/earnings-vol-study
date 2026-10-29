import { describe, it, expect } from 'vitest'
import { parseProvenance } from './provenance'
import { PROVENANCE_FIXTURE } from '../test/metaFixture'

type Path = (string | number)[]
/** A deep copy of the hand-built good provenance with the value at `path` replaced (`undefined` deletes the key). */
const edited = (path: Path, value: unknown): unknown => {
  const root = structuredClone(PROVENANCE_FIXTURE) as Record<string, unknown>
  let node: Record<string | number, unknown> = root
  for (const key of path.slice(0, -1)) node = node[key] as Record<string | number, unknown>
  const last = path[path.length - 1]
  if (value === undefined) delete node[last]
  else node[last] = value
  return root
}

describe('parseProvenance', () => {
  it('accepts the exporter shape and returns the same values', () => {
    expect(parseProvenance(PROVENANCE_FIXTURE)).toEqual({ ok: true, data: PROVENANCE_FIXTURE })
  })
  it('returns a new object, not the input', () => {
    const input = structuredClone(PROVENANCE_FIXTURE)
    const r = parseProvenance(input)
    if (!r.ok) throw new Error(r.error)
    expect(r.data).not.toBe(input)
    expect(r.data.dolt_commits).not.toBe(input.dolt_commits)
  })
  it.each<[string, unknown, string]>([
    ['null', null, 'null'],
    ['an array', [], 'an array'],
    ['a string', 'p', '"p"'],
    ['a number', 5, 'number 5'],
    ['a boolean', true, 'boolean true'],
  ])('rejects %s instead of an object', (_what, input, shown) => {
    expect(parseProvenance(input)).toEqual({ ok: false, error: `provenance must be an object, got ${shown}` })
  })
  it('names the path it was given when the input is not an object', () => {
    expect(parseProvenance(null, 'data.provenance')).toEqual({ ok: false, error: 'data.provenance must be an object, got null' })
  })
  it.each<[string, unknown, string]>([
    ['the object itself', 'not an object', 'x.prov must be an object, got "not an object"'],
    ['an extra key', edited(['branch'], 'x'), 'x.prov has unexpected key(s): branch (expected exactly: params_hash, code_commit, sample_label, dolt_commits)'],
    ['params_hash', edited(['params_hash'], ''), 'x.prov.params_hash must be a non-empty string, got ""'],
    ['code_commit', edited(['code_commit'], ''), 'x.prov.code_commit must be a non-empty string, got ""'],
    ['sample_label', edited(['sample_label'], ''), 'x.prov.sample_label must be a non-empty string, got ""'],
    ['dolt_commits', edited(['dolt_commits'], ''), 'x.prov.dolt_commits must be an object, got ""'],
    ['an extra dolt key', edited(['dolt_commits', 'wiki'], 'x'), 'x.prov.dolt_commits has unexpected key(s): wiki (expected exactly: earnings, options)'],
    ['dolt earnings', edited(['dolt_commits', 'earnings'], ''), 'x.prov.dolt_commits.earnings must be a non-empty string, got ""'],
    ['dolt options', edited(['dolt_commits', 'options'], ''), 'x.prov.dolt_commits.options must be a non-empty string, got ""'],
  ])('uses the given path "x.prov" in the message about %s', (_what, input, message) => {
    expect(parseProvenance(input, 'x.prov')).toEqual({ ok: false, error: message })
  })

  it.each<[string, Path, unknown, string]>([
    ['a key is missing', ['sample_label'], undefined, 'provenance has missing key(s): sample_label (expected exactly: params_hash, code_commit, sample_label, dolt_commits)'],
    ['an extra key', ['branch'], 'main', 'provenance has unexpected key(s): branch (expected exactly: params_hash, code_commit, sample_label, dolt_commits)'],
    ['params_hash is empty', ['params_hash'], '', 'provenance.params_hash must be a non-empty string, got ""'],
    ['params_hash is a number', ['params_hash'], 12, 'provenance.params_hash must be a non-empty string, got number 12'],
    ['code_commit is blank', ['code_commit'], '   ', 'provenance.code_commit must be a non-empty string, got "   "'],
    ['code_commit is null', ['code_commit'], null, 'provenance.code_commit must be a non-empty string, got null'],
    ['sample_label is an array', ['sample_label'], ['daily'], 'provenance.sample_label must be a non-empty string, got an array'],
    ['dolt_commits is null', ['dolt_commits'], null, 'provenance.dolt_commits must be an object, got null'],
    ['dolt_commits is an array', ['dolt_commits'], [], 'provenance.dolt_commits must be an object, got an array'],
    ['dolt_commits lacks earnings', ['dolt_commits', 'earnings'], undefined, 'provenance.dolt_commits has missing key(s): earnings (expected exactly: earnings, options)'],
    ['dolt_commits has an extra key', ['dolt_commits', 'wiki'], 'x', 'provenance.dolt_commits has unexpected key(s): wiki (expected exactly: earnings, options)'],
    ['earnings commit is empty', ['dolt_commits', 'earnings'], '', 'provenance.dolt_commits.earnings must be a non-empty string, got ""'],
    ['options commit is a number', ['dolt_commits', 'options'], 5, 'provenance.dolt_commits.options must be a non-empty string, got number 5'],
  ])('rejects: %s', (_what, path, value, message) => {
    expect(parseProvenance(edited(path, value))).toEqual({ ok: false, error: message })
  })
})
