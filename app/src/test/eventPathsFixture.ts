import { PROVENANCE_FIXTURE } from './metaFixture'

/**
 * Hand-built `data/event_paths.json` body for tests, in the shape the Python exporter writes (schema
 * 0.5.0). Names, units, numbers and caveats are invented ("Fixture ...") so a page that still showed
 * the real file's text, or computed anything itself, would not match. Five event days, six series
 * (market and mean x all, BMO, AMC) and three events:
 *   E1 BMO  [1, 2, 3, 4, 5]        E2 AMC  [0, 1, null, 3, 4]        E3 BMO  [5, 4, 3, 2, 1]
 * The mean path of (market, all) is [0.5, 1, null, 2, 2.5] with a band of 0.25 each side (a null day has no band).
 */
const REL_DAYS = [-2, -1, 0, 1, 2]

const series = (adjustment: string, subgroup_key: string, subgroup_value: string, mean: (number | null)[], half: number) => ({
  measure: 'fix_aliv',
  adjustment,
  units: 'fixture abnormal log IV',
  subgroup_key,
  subgroup_value,
  n: mean.map((m) => (m === null ? null : 3)),
  mean,
  ci_lo: mean.map((m) => (m === null ? null : m - half)),
  ci_hi: mean.map((m) => (m === null ? null : m + half)),
})

export const EVENT_PATHS_DATA_FIXTURE = {
  rel_days: REL_DAYS,
  series: [
    series('market', 'all', 'all', [0.5, 1, null, 2, 2.5], 0.25),
    series('market', 'timing', 'BMO', [1, 1.5, 2, 2.5, 3], 0.5),
    series('market', 'timing', 'AMC', [0, 0.5, 1, 1.5, 2], 0.5),
    series('mean', 'all', 'all', [1, 2, 3, 2, 1], 0.5),
    series('mean', 'timing', 'BMO', [3, 3, 3, 3, 3], 0.25),
    series('mean', 'timing', 'AMC', [-1, -1, -1, -1, -1], 0.25),
  ],
  per_event: [
    { event_id: 'FXA:2031-01-02', ticker: 'FXA', sector: 'Fixture Sector One', day0: '2031-01-03', timing_used: 'BMO', values: [1, 2, 3, 4, 5] },
    { event_id: 'FXB:2031-01-09', ticker: 'FXB', sector: 'Fixture Sector Two', day0: '2031-01-10', timing_used: 'AMC', values: [0, 1, null, 3, 4] },
    { event_id: 'FXA:2031-04-03', ticker: 'FXA', sector: 'Fixture Sector One', day0: '2031-04-04', timing_used: 'BMO', values: [5, 4, 3, 2, 1] },
  ],
  lookups: { n_done: 3, complete: false },
  caveats: ['Fixture paths caveat A: the timing labels are provisional (invented).', 'Fixture paths caveat B: bands are pointwise (invented).'],
  provenance: PROVENANCE_FIXTURE,
}

export const EVENT_PATHS_FIXTURE = {
  schema_version: '0.5.0',
  kind: 'event_paths',
  generated_at: '2031-03-04T05:06:07Z',
  source_commit: 'fix1234',
  data: EVENT_PATHS_DATA_FIXTURE,
}
