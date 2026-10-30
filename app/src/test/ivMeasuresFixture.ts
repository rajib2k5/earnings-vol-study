import { PROVENANCE_FIXTURE } from './metaFixture'

/**
 * Hand-built `data/iv_measures.json` body for tests, in the shape the Python exporter writes
 * (schema 0.5.0). Every label, unit, count and caveat is invented ("Fixture ...") so a page that
 * still showed the real file's text, or computed anything itself, would not match. The counts are
 * small and round so the bar heights are easy to work out by hand:
 *   implied move [1, 4, 2]  -> 25%, 100%, 50%   (largest count 4)
 *   crush        [0, 3, 6]  ->  0%,  50%, 100%  (largest count 6)
 */
export const IV_MEASURES_DATA_FIXTURE = {
  sample: { label: 'fixture-daily', n_events: 12 },
  implied_move: {
    units: 'Fixture units (0.1 = 10%)',
    n_identified: 8,
    n_nonpositive: 1,
    n: 7,
    sqrt_mean_evar: 0.0375,
    quantiles: { p10: 0.011, p25: 0.022, p50: 0.033, p75: 0.044, p90: 0.055 },
    bin_edges: [0.01, 0.02, 0.03, 0.04],
    counts: [1, 4, 2],
  },
  crush: {
    units: 'Fixture log change',
    n: 9,
    mean: -0.25,
    quantiles: { p10: -0.55, p25: -0.45, p50: -0.35, p75: -0.25, p90: -0.15 },
    bin_edges: [-0.6, -0.4, -0.2, 0],
    counts: [0, 3, 6],
  },
  caveats: ['Fixture caveat A: invented for the test.', 'Fixture caveat B: also invented.'],
  provenance: PROVENANCE_FIXTURE,
}

export const IV_MEASURES_FIXTURE = {
  schema_version: '0.5.0',
  kind: 'iv_measures',
  generated_at: '2031-03-04T05:06:07Z',
  source_commit: 'fix1234',
  data: IV_MEASURES_DATA_FIXTURE,
}
