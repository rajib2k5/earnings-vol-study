import { PROVENANCE_FIXTURE } from './metaFixture'

/** One term of the fixture with every field spelled out; the terms below override what differs. */
const TERM = {
  term: 'fix_term_a',
  label: 'Fixture term A',
  hypothesis: 'H5',
  role: 'exploratory',
  statistic: 'twoway_date_t',
  cov_type: 'fixture two-way, t',
  n: 40,
  n_clusters_date: 20,
  n_clusters_firm: 8,
  coef: 0.25,
  se: 0.0625,
  t: 4,
  df: 7,
  df_num: null,
  p_value: 0.0125,
  ci_lo: 0.125,
  ci_hi: 0.375,
  p_holm: null,
  q_bh: 0.0375,
  g1_size: null,
  g1_reps: null,
  note: null,
}

/**
 * Hand-built `data/drivers.json` body for tests, in the shape the Python exporter writes (schema 0.5.0, after fix R1:
 * the declared family binds). Every name, number and caveat is invented ("Fixture ...", "fix_...") so a page that still
 * showed the real file's text, or computed anything itself, would not match. It satisfies the cross-field rules D1 to D8
 * of `drivers.ts`. Layout:
 *   models[0]  "Fixture model A", market, daily, two fixed effects:
 *     terms[0]  two-way H5 PRIMARY, every number present, Holm p 0.0625, and its FAILED size check (G1 size 62.5% over
 *               500 replications, the H5 primary entry of g1) with a note: the p-value is kept
 *     terms[1]  two-way H6 primary, negative, interval spans 0, Holm p 1, no g1_size (H6 passed gate G1)
 *     terms[2]  one-way H5 robustness, p-value withheld (G1 size 75% over 500 replications, the H5 cluster_date_t entry), no interval
 *     terms[3]  two-way H6 robustness, p-value withheld (G1 size 9.375% over 10,000 replications), no interval, coefficient kept
 *     terms[4]  two-way Wald H7 PRIMARY: no coef, se or interval; F 1.5 on 2 and 7 df; Holm p 0.5; failed size check 56.25%
 *   models[1]  "Fixture model B (twin)": the id of model A again, mean-adjusted, coarse sample, no fixed effects, r2 and firm clusters null:
 *     terms[0]  exploratory, no hypothesis        terms[1]  two-way H5 robustness, withheld with the "twoway_date_t:mean_adj" rate 68.75%
 *   models[2]  "Fixture model C (Wald only)": an exploratory Wald row only, so there is nothing to plot
 * g1: band [0.25, 0.5] on 500 replications; H5 fails at 0.625 (its one-way statistic at 0.75, its twin at 0.6875), H6 passes at 0.375,
 * H7 fails at 0.5625; H5 never reaches 80% power on its grid, H6 does at 0.04, H7 (a slope b) at 0.5.
 * holm: the declared family H1, H2, H5, H6, H7 binds, none left it; the post-gate sensitivity drops the failed H5 and H7
 * (family H1, H2, H6) and holds H2's season cut.
 */
export const DRIVERS_DATA_FIXTURE = {
  models: [
    {
      model_id: 'fix_model_a',
      adjustment: 'market',
      sample: 'daily',
      label: 'Fixture model A',
      dep_var: 'FIX_DEP (log)',
      fixed_effects: ['fix_fe1', 'fix_fe2'],
      n: 40,
      n_clusters_date: 20,
      n_clusters_firm: null,
      r2: 0.5,
      terms: [
        { ...TERM, role: 'primary', p_holm: 0.0625, q_bh: null, g1_size: 0.625, g1_reps: 500, note: 'Fixture note: size check failed; the p-value is kept.' },
        { ...TERM, term: 'fix_term_b', label: 'Fixture term B', hypothesis: 'H6', role: 'primary', coef: -0.125, se: 0.125, t: -1, p_value: 0.5, ci_lo: -0.375, ci_hi: 0.125, p_holm: 1, q_bh: null },
        {
          ...TERM,
          role: 'robustness',
          statistic: 'cluster_date_t',
          cov_type: 'fixture one-way, t',
          n_clusters_firm: null,
          se: 0.03125,
          t: 8,
          df: 19,
          p_value: null,
          ci_lo: null,
          ci_hi: null,
          q_bh: null,
          g1_size: 0.75,
          g1_reps: 500,
          note: 'Fixture note: p-value and interval withheld.',
        },
        {
          ...TERM,
          term: 'fix_term_b',
          label: 'Fixture term B',
          hypothesis: 'H6',
          role: 'robustness',
          coef: 0.1875,
          se: 0.0625,
          t: 3,
          p_value: null,
          ci_lo: null,
          ci_hi: null,
          q_bh: null,
          g1_size: 0.09375,
          g1_reps: 10000,
          note: 'Fixture note: withheld, coefficient kept.',
        },
        {
          ...TERM,
          term: 'fix_wald',
          label: 'Fixture joint test',
          hypothesis: 'H7',
          role: 'primary',
          statistic: 'twoway_date_wald',
          cov_type: 'fixture two-way, Wald F',
          coef: null,
          se: null,
          t: 1.5,
          df: 7,
          df_num: 2,
          p_value: 0.28125,
          ci_lo: null,
          ci_hi: null,
          p_holm: 0.5,
          q_bh: null,
          g1_size: 0.5625,
          g1_reps: 500,
          note: 'Fixture note: the joint test failed its size check.',
        },
      ],
    },
    {
      model_id: 'fix_model_a',
      adjustment: 'mean',
      sample: 'coarse',
      label: 'Fixture model B (twin)',
      dep_var: 'FIX_DEP (log)',
      fixed_effects: [] as string[],
      n: 12,
      n_clusters_date: null,
      n_clusters_firm: 6,
      r2: null,
      terms: [
        { ...TERM, term: 'fix_term_c', label: 'Fixture term C', hypothesis: null, n: 12, n_clusters_date: null, n_clusters_firm: 6, coef: 0.5, se: 0.25, t: 2, df: 5, p_value: 0.125, ci_lo: -0.125, ci_hi: 1.125, q_bh: 0.25 },
        {
          ...TERM,
          label: 'Fixture term A (twin)',
          role: 'robustness',
          n: 12,
          n_clusters_date: null,
          n_clusters_firm: 6,
          coef: 0.375,
          se: 0.125,
          t: 3,
          df: 5,
          p_value: null,
          ci_lo: null,
          ci_hi: null,
          q_bh: null,
          g1_size: 0.6875,
          g1_reps: 500,
          note: 'Fixture note: the twin is withheld too.',
        },
      ],
    },
    {
      model_id: 'fix_model_c',
      adjustment: 'none',
      sample: 'mixed',
      label: 'Fixture model C (Wald only)',
      dep_var: 'FIX_R2',
      fixed_effects: ['fix_fe1'],
      n: 9,
      n_clusters_date: 5,
      n_clusters_firm: 3,
      r2: 0.125,
      terms: [
        {
          ...TERM,
          term: 'fix_wald_c',
          label: 'Fixture joint test C',
          hypothesis: null,
          statistic: 'cluster_date_wald',
          cov_type: 'fixture one-way, Wald F',
          coef: null,
          se: null,
          t: 0.5,
          df: 4,
          df_num: 2,
          p_value: 0.625,
          ci_lo: null,
          ci_hi: null,
          q_bh: 0.75,
        },
      ],
    },
  ],
  g1: {
    reps: 500,
    band: [0.25, 0.5],
    calibrated: [
      { hypothesis: 'H5', statistic: 'twoway_date_t', primary: true, rejection_rate: 0.625, reps: 500, pass: false },
      { hypothesis: 'H5', statistic: 'cluster_date_t', primary: false, rejection_rate: 0.75, reps: 500, pass: false },
      { hypothesis: 'H5', statistic: 'twoway_date_t:mean_adj', primary: false, rejection_rate: 0.6875, reps: 500, pass: false },
      { hypothesis: 'H6', statistic: 'twoway_date_t', primary: true, rejection_rate: 0.375, reps: 500, pass: true },
      { hypothesis: 'H7', statistic: 'twoway_date_wald', primary: true, rejection_rate: 0.5625, reps: 500, pass: false },
    ],
    designs: [
      { design: 'FXD0', hypothesis: 'H5', statistic: 'twoway_date_t', primary: true, rejection_rate: 0.125 },
      { design: 'FXD1', hypothesis: 'H6', statistic: 'cluster_date_t', primary: false, rejection_rate: 0.5 },
    ],
    power: [
      { hypothesis: 'H5', kind: 'beta', shifts: [0.01, 0.02], power: [0.25, 0.75], detectable_80: null },
      { hypothesis: 'H6', kind: 'beta', shifts: [0.01, 0.02, 0.04], power: [0.25, 0.5, 1], detectable_80: 0.04 },
      { hypothesis: 'H7', kind: 'b', shifts: [0.5, 1], power: [0.875, 0.125], detectable_80: 0.5 },
    ],
    calibration_h7: { fix_nu: 6.5, fix_rho: 0.25, fix_missing: null } as Record<string, number | null>,
  },
  holm: {
    family: ['H1', 'H2', 'H5', 'H6', 'H7'],
    left_family: [] as string[],
    post_gate: { family: ['H1', 'H2', 'H6'], p_holm: { H1: 0.03125, H2: 0.09375, H6: 0.875 }, season_cut: { H2: 0.15625 } },
  },
  lookups: { n_done: 7, complete: false },
  caveats: [
    'Fixture caveat D: the timing labels are provisional (invented).',
    'Fixture caveat E: also invented.',
    'Fixture caveat X: every exploratory p and q here comes from an invented statistic.',
  ],
  provenance: PROVENANCE_FIXTURE,
}

export const DRIVERS_FIXTURE = {
  schema_version: '0.5.0',
  kind: 'drivers',
  generated_at: '2031-03-04T05:06:07Z',
  source_commit: 'fix1234',
  data: DRIVERS_DATA_FIXTURE,
}
