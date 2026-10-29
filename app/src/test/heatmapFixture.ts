import { PROVENANCE_FIXTURE } from './metaFixture'

/**
 * Hand-built `data/heatmap.json` body for tests (schema 0.4.0), invented values. Two grids:
 *   fix_by_day     2 companies x 3 days, values [[-0.5, 0, 0.25], [0.5, null, -0.25]]  -> largest |value| 0.5
 *   fix_by_season  2 companies x 2 seasons, values [[1, null], [-2, 0.5]] with q-values -> largest |value| 2
 * n is the number of events behind each cell (0 where the value is null).
 */
export const HEATMAP_DATA_FIXTURE = {
  grids: [
    {
      id: 'fix_by_day',
      title: 'Fixture grid by day',
      measure: 'fix_measure_a',
      units: 'fixture units A',
      row_labels: ['FXA', 'FXB'],
      row_keys: ['FXA', 'FXB'],
      col_labels: ['-1', '0', '1'],
      values: [
        [-0.5, 0, 0.25],
        [0.5, null, -0.25],
      ],
      n: [
        [4, 4, 3],
        [5, 0, 5],
      ],
      q: null,
    },
    {
      id: 'fix_by_season',
      title: 'Fixture grid by season',
      measure: 'fix_measure_b',
      units: 'fixture units B',
      row_labels: ['FX Alpha', 'FX Beta'],
      row_keys: ['FXA', 'FXB'],
      col_labels: ['2031Q1', '2031Q2'],
      values: [
        [1, null],
        [-2, 0.5],
      ],
      n: [
        [1, 0],
        [1, 1],
      ],
      q: [
        [0.5, null],
        [0.125, 0.25],
      ],
    },
  ],
  lookups: { n_done: 3, complete: false },
  caveats: ['Fixture heatmap caveat A: the timing labels are provisional (invented).', 'Fixture heatmap caveat B: no cell is tested (invented).'],
  provenance: PROVENANCE_FIXTURE,
}

export const HEATMAP_FIXTURE = {
  schema_version: '0.4.0',
  kind: 'heatmap',
  generated_at: '2031-03-04T05:06:07Z',
  source_commit: 'fix1234',
  data: HEATMAP_DATA_FIXTURE,
}
