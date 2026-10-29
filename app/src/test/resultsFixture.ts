import { PROVENANCE_FIXTURE } from './metaFixture'

/** One `rows[]` entry of the fixture, with every field spelled out; the rows below override what differs. */
const ROW = {
  hypothesis: 'H1',
  role: 'primary',
  measure: 'fix_measure_a',
  statistic: 'fix_stat_one',
  estimand: 'equal_weighted',
  sample: 'daily',
  subgroup_key: 'all',
  subgroup_value: 'all',
  adjustment: 'market',
  rel_day: null,
  units: 'fixture units A',
  n: 11,
  n_clusters: 5,
  n_clusters_firm: 4,
  estimate: -0.5,
  se: 0.125,
  stat: -4,
  df: 4,
  p_value: 0.0123,
  p_holm: 0.0492,
  q_bh: null,
  ci_lo: -0.75,
  ci_hi: -0.25,
  rbar: null,
  g1_size: null,
  g1_reps: null,
  note: null,
}

/**
 * Hand-built `data/tests.json` body for tests, in the shape the Python exporter writes (schema 0.4.0).
 * Every name, unit, number and caveat is invented ("Fixture ...", "fix_...") so a page that still showed
 * the real file's text, or computed anything itself, would not match. Layout:
 *   rows[0]  primary H1, every number present
 *   rows[1]  primary H2, with se, df and the interval null (a randomisation p-value has none)
 *   rows[2]  robustness H1 (precision weighted)       rows[3]  robustness H1 (no estimand)
 *   rows[4]  robustness H2
 *   rows[5]  exploratory, no hypothesis, q_bh 0.0321  rows[6]  exploratory with p_value, stat and the interval null
 * g1: band [0.25, 0.5]; H1 passes at 0.375, H2 fails at 0.625; H1 reaches 80% power at a shift of 2, H2 never does.
 */
export const TESTS_DATA_FIXTURE = {
  rows: [
    ROW,
    { ...ROW, hypothesis: 'H2', measure: 'fix_measure_b', statistic: 'fix_stat_two', units: 'fixture units B', n: 13, estimate: 0.75, se: null, stat: 3.5, df: null, p_value: 0.25, p_holm: 1, ci_lo: null, ci_hi: null },
    { ...ROW, role: 'robustness', statistic: 'fix_stat_pw', estimand: 'precision_weighted', n: 9, estimate: -0.375, se: 0.25, stat: -1.5, df: 8, p_value: 0.17, p_holm: null, ci_lo: -0.5, ci_hi: -0.125 },
    { ...ROW, role: 'robustness', statistic: 'fix_stat_rank', estimand: null, adjustment: 'mean', n: 10, estimate: 0.0625, se: null, stat: 2.25, df: null, p_value: 0.03, p_holm: null, ci_lo: null, ci_hi: null },
    { ...ROW, hypothesis: 'H2', role: 'robustness', measure: 'fix_measure_b', statistic: 'fix_stat_three', units: 'fixture units B', n: 12, estimate: 0.5, se: 0.5, stat: 1, df: 3, p_value: 0.39, p_holm: null, ci_lo: -0.5, ci_hi: 1.5 },
    { ...ROW, hypothesis: null, role: 'exploratory', measure: 'fix_measure_c', statistic: 'fix_stat_four', sample: 'coarse', subgroup_key: 'timing', subgroup_value: 'AMC', units: 'fixture units C', n: 6, n_clusters: null, n_clusters_firm: null, estimate: 0.1875, se: 0.0625, stat: 3, df: 5, p_value: 0.0105, p_holm: null, q_bh: 0.0321, ci_lo: 0.0625, ci_hi: 0.3125 },
    { ...ROW, hypothesis: null, role: 'exploratory', measure: 'fix_measure_d', statistic: 'fix_stat_mean', estimand: null, sample: 'mixed', units: 'fixture units D', n: 4, n_clusters: 1, n_clusters_firm: null, estimate: 0.875, se: null, stat: null, df: null, p_value: null, p_holm: null, ci_lo: null, ci_hi: null },
  ],
  g1: {
    reps: 500,
    band: [0.25, 0.5],
    calibrated: [
      { hypothesis: 'H1', statistic: 'fix_stat_one', rejection_rate: 0.375, pass: true },
      { hypothesis: 'H2', statistic: 'fix_stat_two', rejection_rate: 0.625, pass: false },
    ],
    designs: [
      { design: 'FX0', hypothesis: 'H1', statistic: 'fix_stat_one', primary: true, rejection_rate: 0.375 },
      { design: 'FX1', hypothesis: 'H2', statistic: 'fix_stat_pw', primary: false, rejection_rate: 0.5 },
    ],
    power: [
      { hypothesis: 'H1', shifts: [0.5, 1, 2], power: [0.25, 0.5, 1], detectable_80: 2 },
      { hypothesis: 'H2', shifts: [0.5, 1], power: [0.125, 0.25], detectable_80: null },
    ],
    calibration: { fix_phi: 0.5, fix_noise: 2 },
  },
  holm: { family: ['H1', 'H2', 'H3'], tested: ['H1', 'H2'], untested: ['H3'], left_family: [] as string[] },
  lookups: { n_done: 7, complete: false },
  caveats: ['Fixture caveat A: the timing labels are provisional (invented).', 'Fixture caveat B: also invented.'],
  provenance: PROVENANCE_FIXTURE,
}

export const TESTS_FIXTURE = {
  schema_version: '0.4.0',
  kind: 'tests',
  generated_at: '2031-03-04T05:06:07Z',
  source_commit: 'fix1234',
  data: TESTS_DATA_FIXTURE,
}
