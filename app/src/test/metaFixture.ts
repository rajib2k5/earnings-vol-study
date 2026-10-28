/**
 * Hand-built `data/meta.json` body for tests, in the shape the Python exporter writes (schema 0.1.0).
 * The names, URLs and licences are invented on purpose ("Fixture ..."): a page that still showed a
 * hard-coded copy of the real sources would not match them.
 */
export const META_DATA_FIXTURE = {
  project: 'fixture-project',
  milestone: 0,
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
}

export const META_FIXTURE = {
  schema_version: '0.1.0',
  kind: 'meta',
  generated_at: '2026-10-27T12:00:00Z',
  source_commit: 'abc1234',
  data: META_DATA_FIXTURE,
}

/** A fetch stand-in that answers every request with the given JSON body (200 OK). */
export function jsonFetch(body: unknown): typeof fetch {
  return (async () => ({ ok: true, status: 200, json: async () => body }) as Response) as typeof fetch
}
