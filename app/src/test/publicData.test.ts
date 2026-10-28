import { describe, it, expect } from 'vitest'
import { parseEnvelope } from '../lib/contract'
import { summarizeMeta, formatMilestone, parseMetaData } from '../lib/meta'

// Contract check against the REAL files the Python exporter wrote to public/data/. If the Python
// side and contract.ts drift apart, this fails (the other tests only use hand-built fixtures).
const files = import.meta.glob('../../public/data/*.json', { eager: true, query: '?raw', import: 'default' }) as Record<string, string>

describe('public/data/*.json (written by the Python exporter)', () => {
  it('contains at least meta.json', () => {
    expect(Object.keys(files).some((f) => f.endsWith('/meta.json'))).toBe(true)
  })
  for (const [path, raw] of Object.entries(files)) {
    it(`${path.split('/').pop()} is valid JSON and satisfies the schema 0.1.0 envelope`, () => {
      const r = parseEnvelope(JSON.parse(raw))
      expect(r.ok, r.ok ? '' : r.error).toBe(true)
    })
  }
  it('meta.json carries a usable milestone number and a kind of "meta"', () => {
    const raw = Object.entries(files).find(([f]) => f.endsWith('/meta.json'))?.[1]
    const r = parseEnvelope(JSON.parse(raw ?? 'null'))
    if (!r.ok) throw new Error(r.error)
    expect(r.envelope.kind).toBe('meta')
    const m = summarizeMeta(r.envelope)
    expect(m.milestone, 'data.milestone must be a non-negative integer').not.toBeNull()
    expect(formatMilestone(m.milestone)).toMatch(/^M\d+$/)
  })
  it('meta.json data passes the data-shape validator the About page uses (sources, licence, attribution)', () => {
    const raw = Object.entries(files).find(([f]) => f.endsWith('/meta.json'))?.[1]
    const env = parseEnvelope(JSON.parse(raw ?? 'null'))
    if (!env.ok) throw new Error(env.error)
    const r = parseMetaData(env.envelope.data)
    if (!r.ok) throw new Error(r.error)
    // CBOE and Yahoo data is never committed (data/derived/README.md); the Python test pins this too,
    // and this checks the file the app really reads.
    for (const s of r.data.data_sources) {
      if (/CBOE|Yahoo/.test(s.name)) expect(s.committed, s.name).toBe(false)
    }
    // Every committed source is covered by the licence, and the attribution text names its repository.
    for (const s of r.data.data_sources.filter((x) => x.committed)) {
      expect(r.data.data_licence.applies_to, s.name).toContain(s.name)
      expect(r.data.data_licence.attribution, s.name).toContain(s.name.replace('DoltHub ', ''))
    }
  })
})
