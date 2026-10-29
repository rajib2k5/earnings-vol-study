import { PROVENANCE_FIXTURE } from './metaFixture'

/**
 * Hand-built `data/terrain.json` body for tests (schema 0.4.0), invented values. Three companies and
 * three event days; the middle company has no data on day 0 (null), which must become a hole in the mesh.
 */
export const TERRAIN_DATA_FIXTURE = {
  measure: 'fix_aliv_mean_adj',
  units: 'fixture abnormal log IV',
  rel_days: [-1, 0, 1],
  rows: [
    { security_id: 'FXA', ticker: 'FXA', sector: 'Fixture Sector One', n_events: 4 },
    { security_id: 'FXB', ticker: 'FXB', sector: 'Fixture Sector One', n_events: 5 },
    { security_id: 'FXC', ticker: 'FXC', sector: 'Fixture Sector Two', n_events: 6 },
  ],
  values: [
    [0.25, 0.5, 0.125],
    [0.5, null, 0.25],
    [1, 0.75, 0.375],
  ],
  row_order: 'fixture sector, then id',
  lookups: { n_done: 3, complete: false },
  caveats: ['Fixture terrain caveat A: the timing labels are provisional (invented).', 'Fixture terrain caveat B: a description, not a test (invented).'],
  provenance: PROVENANCE_FIXTURE,
}

export const TERRAIN_FIXTURE = {
  schema_version: '0.4.0',
  kind: 'terrain',
  generated_at: '2031-03-04T05:06:07Z',
  source_commit: 'fix1234',
  data: TERRAIN_DATA_FIXTURE,
}
