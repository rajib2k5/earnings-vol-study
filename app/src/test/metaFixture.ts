/** Hand-built `provenance` object (shared by the meta and sample_funnel fixtures), invented values. */
export const PROVENANCE_FIXTURE = {
  params_hash: 'fixture-params-hash-0123',
  code_commit: 'fix1234',
  sample_label: 'fixture-sample',
  dolt_commits: { earnings: 'fixture-earnings-commit', options: 'fixture-options-commit' },
}

/**
 * Hand-built `data/meta.json` body for tests, in the shape the Python exporter writes (schema 0.5.0).
 * The names, URLs, licences and numbers are invented on purpose ("Fixture ..."): a page that still
 * showed a hard-coded copy of the real values would not match them.
 */
export const META_DATA_FIXTURE = {
  project: 'fixture-project',
  milestone: 4,
  title: 'Fixture title',
  data_sources: [
    { name: 'Fixture open source', uses: 'table_a, table_b', url: 'https://example.com/open', licence: 'FIX-OPEN 1.0', committed: true },
    { name: 'Fixture vendor', uses: 'series_x', url: 'https://example.com/vendor', licence: 'see source', committed: false },
  ],
  data_licence: {
    name: 'FIX-OPEN 1.0',
    url: 'https://example.com/licence',
    applies_to: ['Fixture open source'],
    attribution: 'Fixture attribution: contains data from the fixture open source.',
  },
  sample: { label: 'fixture-sample', day0_from: '2031-01-02', day0_to: '2031-06-30', n_events: 123, n_securities: 7 },
  params: {
    event_window: [-3, 4] as [number, number],
    baseline: [-40, -15] as [number, number],
    baseline_exclusion: [-14, 6] as [number, number],
    cm30_horizon_sessions: 17,
    clock: 'Fixture clock (fixture calendar)',
  },
  files: ['meta', 'fixture_kind', 'drivers', 'implied_vs_realised'],
  provenance: PROVENANCE_FIXTURE,
}

export const META_FIXTURE = {
  schema_version: '0.5.0',
  kind: 'meta',
  generated_at: '2026-10-27T12:00:00Z',
  source_commit: 'abc1234',
  data: META_DATA_FIXTURE,
}

/** A fetch stand-in that answers every request with the given JSON body (200 OK). */
export function jsonFetch(body: unknown): typeof fetch {
  return (async () => ({ ok: true, status: 200, json: async () => body }) as Response) as typeof fetch
}
