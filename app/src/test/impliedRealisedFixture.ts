import { PROVENANCE_FIXTURE } from './metaFixture'

/** One event of the fixture with every field spelled out; the points below override what differs. */
const POINT = {
  event_id: 'FIXA:2031-01-01',
  ticker: 'FIXA',
  sector: 'Fixture Sector One',
  day0: '2031-01-02',
  timing_used: 'BMO',
  event_var: 0.004,
  implied_var_total: 0.0045,
  implied_move: 0.0625,
  implied_abs_move_total: 0.05,
  realized_ret_0: -0.025,
  abs_realized: 0.025,
  implied_move_status: 'ok',
  surprise_scaled: 0.125,
}

/**
 * Hand-built `data/implied_vs_realised.json` body for tests, in the shape the Python exporter writes (schema 0.5.0).
 * Every name, number and caveat is invented ("Fixture ...", "FIX...") so a page that still showed the real file's
 * text, or computed anything itself, would not match. Layout (expected |move| x, realised |move| y):
 *   points[0]  FIXA BMO   x 0.05    y 0.025   below the line      points[1]  FIXB AMC   x 0.0625  y 0.1     above the line (the largest value)
 *   points[2]  FIXC AMC   x 0.03125 y 0.0375 above the line      points[3]  FIXD timing unknown, status null, x 0.0375 y 0.0125 below the line
 *   points[4]  FIXE BMO   no expected move (non-positive event variance), y 0.05: counted, not drawn
 * summary: 5 events, 4 with an expected move; share 0.5 against 0.425; b 0.75 with interval [0.25, 1.25]; Wald F 2.5 on 2 and 9 df,
 * p 0.125, PRIMARY with Holm p 0.5 (fix R1: it stays in the declared family), and it FAILED gate G1's size check (rate 0.5625 against
 * the bar 0.5); the one-way test failed too (rate 0.625), so its p-value is withheld (null). It satisfies the rules I1 to I5 of
 * `impliedRealised.ts`.
 */
export const IMPLIED_REALISED_DATA_FIXTURE = {
  points: [
    POINT,
    { ...POINT, event_id: 'FIXB:2031-02-01', ticker: 'FIXB', sector: 'Fixture Sector Two', day0: '2031-02-02', timing_used: 'AMC', implied_abs_move_total: 0.0625, realized_ret_0: 0.1, abs_realized: 0.1 },
    { ...POINT, event_id: 'FIXC:2031-03-01', ticker: 'FIXC', day0: '2031-03-03', timing_used: 'AMC', implied_abs_move_total: 0.03125, realized_ret_0: -0.0375, abs_realized: 0.0375 },
    { ...POINT, event_id: 'FIXD:2031-04-01', ticker: 'FIXD', day0: '2031-04-02', timing_used: null, implied_abs_move_total: 0.0375, realized_ret_0: 0.0125, abs_realized: 0.0125, implied_move_status: null, surprise_scaled: null },
    {
      ...POINT,
      event_id: 'FIXE:2031-05-01',
      ticker: 'FIXE',
      day0: '2031-05-02',
      event_var: -0.001,
      implied_var_total: 0.0008,
      implied_move: null,
      implied_abs_move_total: null,
      realized_ret_0: 0.05,
      abs_realized: 0.05,
      implied_move_status: 'nonpositive_event_variance',
    },
  ],
  summary: {
    n: 5,
    n_evar_nonpositive: 1,
    n_with_implied_abs_move: 4,
    share_exceed: 0.5,
    share_exceed_se: 0.125,
    share_exceed_p: 0.75,
    share_exceed_benchmark: 0.425,
    mean_log_ratio: -0.25,
    median_ratio: 0.75,
    regression: {
      n: 5,
      a: 0.001,
      a_se: 0.0005,
      b: 0.75,
      b_se: 0.25,
      b_ci: [0.25, 1.25],
      wald_f: 2.5,
      wald_df_num: 2,
      wald_df: 9,
      wald_p: 0.125,
      role: 'primary',
      p_holm: 0.5,
      n_clusters_date: 4,
      n_clusters_firm: 3,
      wald_p_one_way: null,
      g1_rate: 0.5625,
      g1_pass: false,
      g1_bar: 0.5,
      g1_rate_one_way: 0.625 as number | null,
      g1_pass_one_way: false as boolean | null,
    },
  },
  lookups: { n_done: 7, complete: false },
  caveats: ['Fixture caveat F: the timing labels are provisional (invented).', 'Fixture caveat G: also invented.'],
  provenance: PROVENANCE_FIXTURE,
}

export const IMPLIED_REALISED_FIXTURE = {
  schema_version: '0.5.0',
  kind: 'implied_vs_realised',
  generated_at: '2031-03-04T05:06:07Z',
  source_commit: 'fix1234',
  data: IMPLIED_REALISED_DATA_FIXTURE,
}
