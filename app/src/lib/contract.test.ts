import { describe, it, expect } from 'vitest'
import { isIsoUtc, parseEnvelope, SCHEMA_VERSION } from './contract'

// Hand-built fixture: the smallest valid envelope.
const valid = () => ({
  schema_version: '0.1.0',
  kind: 'meta',
  generated_at: '2026-10-27T12:00:00Z',
  source_commit: 'abc1234',
  data: { milestone: 'M0' },
})

/** parseEnvelope must fail, and the message must contain `needle`. */
function expectError(input: unknown, needle: string) {
  const r = parseEnvelope(input)
  expect(r.ok).toBe(false)
  if (!r.ok) expect(r.error).toContain(needle)
}

describe('parseEnvelope: accepts a valid envelope', () => {
  it('returns the typed envelope unchanged', () => {
    const r = parseEnvelope(valid())
    expect(r).toEqual({ ok: true, envelope: valid() })
  })
  it('accepts fractional seconds, an empty data object and an empty-string commit (exactly as typed)', () => {
    const r = parseEnvelope({ ...valid(), generated_at: '2026-10-27T12:00:00.123456Z', source_commit: '', data: {} })
    expect(r.ok).toBe(true)
  })
  it('exports the version the app understands', () => {
    expect(SCHEMA_VERSION).toBe('0.1.0')
  })
})

describe('parseEnvelope: schema_version', () => {
  it('rejects a different version and names both versions', () => {
    expectError({ ...valid(), schema_version: '0.2.0' }, 'unsupported schema_version "0.2.0"')
    expectError({ ...valid(), schema_version: '0.2.0' }, '"0.1.0"')
  })
  it('does not coerce: the number 0.1 or an array is not "0.1.0"', () => {
    expectError({ ...valid(), schema_version: 0.1 }, 'schema_version must be the string "0.1.0", got number 0.1')
    expectError({ ...valid(), schema_version: ['0.1.0'] }, 'schema_version must be the string "0.1.0", got an array')
    expectError({ ...valid(), schema_version: null }, 'schema_version must be the string "0.1.0", got null')
  })
  it('reports the version problem before extra keys, since a newer file may add keys', () => {
    expectError({ ...valid(), schema_version: '9.9.9', brand_new: 1 }, 'unsupported schema_version')
  })
})

describe('parseEnvelope: key set must be exactly the five keys', () => {
  it('reports every missing key', () => {
    const { kind, data, ...rest } = valid()
    void kind
    void data
    expectError(rest, 'missing key(s): kind, data')
  })
  it('reports a missing schema_version', () => {
    const { schema_version, ...rest } = valid()
    void schema_version
    expectError(rest, 'missing key(s): schema_version')
  })
  it('rejects an extra key and names it', () => {
    expectError({ ...valid(), extra: 1 }, 'unexpected key(s): extra')
  })
  it('reports missing and extra together', () => {
    const { source_commit, ...rest } = valid()
    void source_commit
    expectError({ ...rest, commit: 'x' }, 'missing key(s): source_commit; unexpected key(s): commit')
  })
  it('does not treat an inherited property as present', () => {
    // `kind` lives on the prototype only, so it is still missing from the envelope itself.
    const { kind, ...rest } = valid()
    void kind
    const input = Object.assign(Object.create({ kind: 'meta' }), rest)
    expectError(input, 'missing key(s): kind')
  })
})

describe('parseEnvelope: field types', () => {
  it('requires kind and source_commit to be strings', () => {
    expectError({ ...valid(), kind: 5 }, 'kind must be a string')
    expectError({ ...valid(), kind: null }, 'kind must be a string, got null')
    expectError({ ...valid(), source_commit: 123 }, 'source_commit must be a string')
  })
  it('requires data to be a JSON object (not null, not an array, not a string)', () => {
    expectError({ ...valid(), data: null }, 'data must be a JSON object, got null')
    expectError({ ...valid(), data: [] }, 'data must be a JSON object, got an array')
    expectError({ ...valid(), data: 'x' }, 'data must be a JSON object, got "x"')
  })
  it('rejects non-object envelopes outright', () => {
    for (const bad of [null, undefined, 3, 'text', [], true]) {
      expect(parseEnvelope(bad).ok, String(bad)).toBe(false)
    }
    expectError(null, 'envelope must be a JSON object, got null')
    expectError([], 'got an array')
  })
})

describe('parseEnvelope: generated_at', () => {
  it('rejects a timestamp that does not end in Z', () => {
    expectError({ ...valid(), generated_at: '2026-10-27T12:00:00' }, 'generated_at must be an ISO-8601 UTC timestamp')
    expectError({ ...valid(), generated_at: '2026-10-27T12:00:00+00:00' }, 'ending in "Z"')
    expectError({ ...valid(), generated_at: '2026-10-27T12:00:00-05:00' }, 'ending in "Z"')
  })
  it('rejects a non-string timestamp', () => {
    expectError({ ...valid(), generated_at: 1798372800 }, 'generated_at must be')
    expectError({ ...valid(), generated_at: null }, 'generated_at must be')
  })
  it('rejects a date-only string and a space instead of T', () => {
    expectError({ ...valid(), generated_at: '2026-10-27' }, 'generated_at must be')
    expectError({ ...valid(), generated_at: '2026-10-27 12:00:00Z' }, 'generated_at must be')
  })
})

describe('isIsoUtc', () => {
  it('accepts real moments, including leap day and the last second of a day', () => {
    for (const ok of ['2026-10-27T12:00:00Z', '2024-02-29T00:00:00Z', '2026-12-31T23:59:59Z', '2026-01-01T00:00:00.5Z']) {
      expect(isIsoUtc(ok), ok).toBe(true)
    }
  })
  it('rejects impossible dates and times that Date.UTC would silently roll over', () => {
    for (const bad of [
      '2026-02-30T00:00:00Z', // no Feb 30
      '2025-02-29T00:00:00Z', // 2025 is not a leap year
      '2026-13-01T00:00:00Z', // month 13
      '2026-00-10T00:00:00Z', // month 0
      '2026-10-27T24:00:00Z', // hour 24
      '2026-10-27T12:60:00Z', // minute 60
      '2026-10-27T12:00:60Z', // second 60
      '2026-04-31T00:00:00Z', // April has 30 days
      '0026-10-27T12:00:00Z', // Date.UTC maps years 0-99 to 1900-1999, so this would not round-trip
    ]) {
      expect(isIsoUtc(bad), bad).toBe(false)
    }
  })
  it('rejects wrong shapes: lowercase z, missing Z, stray text, empty', () => {
    for (const bad of ['2026-10-27T12:00:00z', '2026-10-27T12:00:00', ' 2026-10-27T12:00:00Z', '2026-10-27T12:00:00Z ', 'now', '']) {
      expect(isIsoUtc(bad), JSON.stringify(bad)).toBe(false)
    }
  })
})
