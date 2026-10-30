import { PROVENANCE_FIXTURE } from './metaFixture'

/**
 * Hand-built `data/sample_funnel.json` body for tests, in the shape the Python exporter writes
 * (schema 0.5.0). Every label, reason, count and caveat is invented ("Fixture ...") so a page that
 * still showed the real file's text, or computed anything itself, would not match. The counts are
 * chosen so the bar widths are easy to work out by hand: 200 -> 100%, 150 -> 75%, 50 -> 25%.
 *
 * `FUNNEL_DATA_FIXTURE` has both milestone-2 fields filled (`by_move_tercile`, `evar_nonpositive`);
 * `FUNNEL_NULL_DATA_FIXTURE` is the same file with both null, as at schema 0.2.0.
 */
export const FUNNEL_DATA_FIXTURE = {
  steps: [
    { step: 'fix_all', label: 'Fixture: every event', n_events: 200, n_removed: 0, reason: null },
    { step: 'fix_known', label: 'Fixture: timing known', n_events: 150, n_removed: 50, reason: 'fix_unknown|fix_unchecked' },
    { step: 'fix_range', label: 'Fixture: inside the range', n_events: 50, n_removed: 100, reason: 'fix_outside' },
  ],
  timing_status_counts: { confirmed: 10, corrected: 20, inferred: 30, date_corrected: 5, no_document: 15, not_checked: 100, ambiguous: 20 },
  timing_status_by_sample: [
    { sample: 'daily', timing_status_counts: { confirmed: 1, corrected: 2, inferred: 3, date_corrected: 4, no_document: 5, not_checked: 6, ambiguous: 7 } },
    { sample: 'mixed', timing_status_counts: { confirmed: 8, corrected: 9, inferred: 10, date_corrected: 11, no_document: 12, not_checked: 13, ambiguous: 14 } },
    { sample: 'coarse', timing_status_counts: { confirmed: 15, corrected: 16, inferred: 17, date_corrected: 18, no_document: 19, not_checked: 21, ambiguous: 22 } },
    { sample: 'none', timing_status_counts: { confirmed: 23, corrected: 24, inferred: 25, date_corrected: 26, no_document: 27, not_checked: 28, ambiguous: 29 } },
  ],
  by_sample: [
    { sample: 'daily', n_events: 61 },
    { sample: 'mixed', n_events: 22 },
    { sample: 'coarse', n_events: 93 },
    { sample: 'none', n_events: 24 },
  ],
  // Three rows, one per sample name that has terciles, with round numbers. Each row's timing counts
  // add up to its n_events. Row 2 has a null share and row 3 has no moves at all (null means).
  by_move_tercile: [
    {
      sample: 'daily',
      tercile: 1,
      n_events: 40,
      timing_status_counts: { confirmed: 1, corrected: 2, inferred: 3, date_corrected: 4, no_document: 5, not_checked: 24, ambiguous: 1 },
      share_gap_contradicts: 0.25,
      n_gap_check_changed: 3,
      mean_abs_move: 0.0125,
      n_crush: 38,
      mean_crush_mean_adj: -0.15,
    },
    {
      sample: 'mixed',
      tercile: 2,
      n_events: 10,
      timing_status_counts: { confirmed: 0, corrected: 0, inferred: 0, date_corrected: 0, no_document: 0, not_checked: 10, ambiguous: 0 },
      share_gap_contradicts: null,
      n_gap_check_changed: 0,
      mean_abs_move: 0.04,
      n_crush: 10,
      mean_crush_mean_adj: -0.2,
    },
    {
      sample: 'coarse',
      tercile: 3,
      n_events: 20,
      timing_status_counts: { confirmed: 6, corrected: 0, inferred: 0, date_corrected: 0, no_document: 0, not_checked: 14, ambiguous: 0 },
      share_gap_contradicts: 0,
      n_gap_check_changed: 2,
      mean_abs_move: null,
      n_crush: 0,
      mean_crush_mean_adj: null,
    },
  ],
  by_move_tercile_status: 'computed: fixture terciles from the fixture forwards',
  // `share` is deliberately NOT 5 / 190: a page that worked it out itself would not match the file.
  evar_nonpositive: { n_events: 200, n_identified: 190, n: 5, share: 0.125 },
  evar_nonpositive_status: 'computed: fixture variance at the fixture day -1',
  lookups: { n_done: 7, complete: false },
  caveats: ['Fixture caveat one: invented for the test.', 'Fixture caveat two: also invented.'],
  provenance: PROVENANCE_FIXTURE,
}

/** The same file with the two milestone-2 fields not computed (null), as the exporter wrote them at 0.2.0. */
export const FUNNEL_NULL_DATA_FIXTURE = {
  ...FUNNEL_DATA_FIXTURE,
  by_move_tercile: null,
  by_move_tercile_status: 'not_computed: fixture terciles need the fixture forwards',
  evar_nonpositive: null,
  evar_nonpositive_status: 'not_computed: fixture variance is a later measure',
}

export const FUNNEL_FIXTURE = {
  schema_version: '0.5.0',
  kind: 'sample_funnel',
  generated_at: '2031-03-04T05:06:07Z',
  source_commit: 'fix1234',
  data: FUNNEL_DATA_FIXTURE,
}

export const FUNNEL_NULL_FIXTURE = {
  ...FUNNEL_FIXTURE,
  data: FUNNEL_NULL_DATA_FIXTURE,
}
