# Data provenance

The app contains **no computed results of its own**. It reads JSON files from `public/data/`
written by the Python exporter (`tools/export_app_data.py`) and draws them.

## JSON contract (schema 0.3.0)

Every file in `public/data/` is one envelope with exactly these keys:

| key | type | meaning |
|---|---|---|
| `schema_version` | string, must be `"0.3.0"` | contract version the app understands |
| `kind` | string | what `data` holds: `"meta"`, `"sample_funnel"` or `"iv_measures"` |
| `generated_at` | string | ISO-8601 UTC timestamp ending in `Z` |
| `source_commit` | string | git commit of the Python code that produced the file |
| `data` | object | the payload |

The version covers the **whole contract**: this envelope and the `data` shape of every kind below. A change to
either bumps it, in the exporter and in `src/lib/contract.ts` together. A file with another version (for example
the previous `"0.2.0"`) is rejected with a message that names both versions; the app does not try to read it.
0.3.0 (milestone 2) filled `sample_funnel`'s two milestone-2 fields and added `iv_measures.json`.

`src/lib/contract.ts` checks the envelope and reports a descriptive error (never coerces). The app loads
`data/meta.json` at start-up (relative URL, so it works under a sub-path) and shows the schema
version, milestone and source commit in the footer; a missing or invalid file shows an error there.
In `meta.json`, `data.milestone` is a non-negative integer (0 means M0).

### `meta.json` (kind `meta`)

`meta.json` is also where the About page gets its data-sources table: the page draws the table from this file and
the app keeps no copy in code. (This file and the README describe the same sources in prose. Those copies are
written by hand, and no test compares them with `meta.json`.) The file's `data` object has exactly these keys, and
`parseMetaData` in `src/lib/meta.ts` checks them before the About page draws the table (an extra or a missing key
is an error, and nothing is coerced):

| key | type | meaning |
|---|---|---|
| `project`, `title` | non-empty strings | what the project is called |
| `milestone` | non-negative integer | 0 means M0 |
| `data_sources` | non-empty array | one object per source: `name`, `uses` (tables or series taken), `url` (https), `licence`, `committed` (boolean) |
| `data_licence` | object | `name`, `url` (https, the licence text), `applies_to` (source names the licence covers), `attribution` (text shown under the table) |
| `sample` | object | which events the exported numbers describe: `label` (non-empty string), `day0_from` and `day0_to` (dates `YYYY-MM-DD`), `n_events` and `n_securities` (non-negative integers) |
| `params` | object | the study parameters: `event_window`, `baseline` and `baseline_exclusion` (each `[from, to]`, two integers, session offsets from day 0), `cm30_horizon_sessions` (positive integer), `clock` (non-empty string) |
| `files` | non-empty array of non-empty strings | the kinds of file available in `public/data/`, for example `["meta", "sample_funnel", "iv_measures"]`; a test checks it lists every file that is there |
| `provenance` | object | see "Provenance" below |

The Python exporter (`DATA_SOURCES` and `DATA_LICENCE` in `tools/export_app_data.py`) owns this content, and the
committed `public/data/meta.json` is its output. Two checks guard it: `tests/test_export_app_data.py` compares the
file's `data` with the exporter's `meta_data()` (it ignores `generated_at` and `source_commit`, which change on every
export), so an edit to only one of the two fails; and `parseMetaData` rejects a source named in `applies_to` whose
`licence` is not `data_licence.name`. After you change the exporter, run `uv run python tools/export_app_data.py`
and commit the new file.

### `sample_funnel.json` (kind `sample_funnel`)

How many earnings events are left after each filtering step, drawn by the **Sample** page (`src/lib/FunnelPage.tsx`).
The page shows every number exactly as given; the only thing it works out is the length of each bar (a step's
`n_events` against the first step's), which is layout, not a result. `parseSampleFunnel` in `src/lib/funnel.ts`
checks that `data` has exactly these keys:

| key | type | meaning |
|---|---|---|
| `steps` | non-empty array | one object per step, in order: `step` and `label` (non-empty strings), `n_events` and `n_removed` (non-negative integers), `reason` (string or `null`) |
| `timing_status_counts` | object | exactly the seven keys `confirmed`, `corrected`, `inferred`, `date_corrected`, `no_document`, `not_checked`, `ambiguous`, each a non-negative integer |
| `timing_status_by_sample` | array | per sample: `sample` (one of `daily`, `mixed`, `coarse`, `none`) and `timing_status_counts` (as above) |
| `by_sample` | array | per sample: `sample` (one of the same four) and `n_events` (non-negative integer) |
| `by_move_tercile` | array or `null` | ADR 0002 §3 job 3, per date sample and tercile of `abs_move_cand_max`: `sample` (`daily`, `mixed` or `coarse`), `tercile` (1, 2 or 3), `n_events`, `timing_status_counts` (as above), `share_gap_contradicts` (number in [0, 1] or `null`), `n_gap_check_changed`, `mean_abs_move` (number or `null`), `n_crush` (at most `n_events`), `mean_crush_mean_adj` (number or `null`). Filled since 0.3.0 |
| `by_move_tercile_status` | non-empty string | `computed: ...` with how it was computed, or why it is `null` ("not computed yet: ...") |
| `evar_nonpositive` | object or `null` | `n_events`, `n_identified`, `n` (non-negative integers, `n <= n_identified <= n_events`) and `share` (number in [0, 1], `null` only when `n_identified` is 0): of the events of the last step, how many have an event variance E at day −1 and how many of those have E ≤ 0. Filled since 0.3.0 |
| `evar_nonpositive_status` | non-empty string | as `by_move_tercile_status` |
| `lookups` | object | `n_done` (non-negative integer) and `complete` (boolean); the page says "provisional" until `complete` is true |
| `caveats` | array of non-empty strings | every one is listed on the page, next to the numbers |
| `provenance` | object | see "Provenance" below |

`loadSampleFunnel` (same file) fetches `data/sample_funnel.json` through an injected `fetch`, checks the envelope,
checks that `kind` is `"sample_funnel"`, then checks `data`. A missing or invalid file shows an error on the Sample
page instead of a chart.

### `iv_measures.json` (kind `iv_measures`)

How the milestone-2 measures are distributed over the primary sample, drawn by the **IV measures** page
(`src/lib/IvMeasuresPage.tsx`): counts, quantiles and histograms only. Each bar's height is its count against the
largest count of that histogram, which is layout, not a result. `parseIvMeasures` in `src/lib/ivMeasures.ts` checks
that `data` has exactly these keys:

| key | type | meaning |
|---|---|---|
| `sample` | object | `label` (non-empty string), `n_events` (non-negative integer): the events of the funnel's last step |
| `implied_move` | object | √E at day −1 of the events with E > 0: `units`, `n_identified`, `n_nonpositive`, `n` (`n_nonpositive <= n_identified`, `n <= n_identified`), `sqrt_mean_evar` (√ of the mean E over every event with an E, signed; or `null`), `quantiles` (`p10` … `p90`, non-decreasing, or `null`), `bin_edges` (strictly increasing) and `counts` (non-negative integers; `bin_edges` has one more entry, and the counts add up to `n`) |
| `crush` | object | ln IV(day 0) − ln IV(day −1) of the 30-day IV: `units`, `n`, `mean` (or `null`), `quantiles`, `bin_edges`, `counts` (same rules) |
| `caveats` | array of non-empty strings | shown under the histograms |
| `provenance` | object | see "Provenance" below |

### Provenance

Every file carries the same `provenance` object, checked by one validator (`src/lib/provenance.ts`), with exactly
these keys: `params_hash` (hash of the study parameters), `code_commit` (git commit of the Python code),
`sample_label` (which sample the numbers describe), and `dolt_commits` (an object with exactly `earnings` and
`options`, the commit of each DoltHub repository the data was read from). All four are non-empty strings. They say
which parameters, code and upstream data versions produced the file, so a number can be traced back.

## Sources and licences

This table follows the committed `public/data/meta.json`, which is the source of truth (the About page draws that
file, not this one). "derived rows only" means the repository holds values derived from the source, never the
source's own files.

| source | used for | licence | committed here? |
|---|---|---|---|
| DoltHub `post-no-preference/earnings` | `earnings_calendar`, `eps_history`, `eps_estimate` | CC BY-SA 4.0 | derived rows only |
| DoltHub `post-no-preference/options` | `option_chain`, `volatility_history` | CC BY-SA 4.0 | derived rows only |
| Wikipedia List of S&P 500 companies | company names, GICS sectors and CIKs | CC BY-SA 4.0 | derived rows only |
| FRED DTB3 | the 3-month Treasury bill rate: the discount factor and the carry inside the committed IVs and moves | public domain (FRED asks for a citation) | derived rows only (no rate value) |
| FRED VIXCLS (Cboe VIX) | the VIX close, for the market adjustment | Cboe copyright (see source) | **never** |
| Cboe single-stock volatility indices (VX\*) | validation of our 30-day IV (not run yet) | Cboe terms of use (see source) | **never** |
| Yahoo Finance | daily prices and market caps, read with `yfinance`; two labels made from them are committed | Yahoo terms of service (see source) | derived rows only: `security.in_universe`, `timing_check.gap_verdict_yf` |

- **CC BY-SA 4.0 (DoltHub, confirmed).** Both DoltHub repositories contain a `LICENSE.md` reading
  "Attribution-ShareAlike 4.0 International" (read from each repository's `dolt_docs` table through
  the DoltHub SQL API on 2026-10-28; the repository web pages do not state it). Licence text:
  <https://creativecommons.org/licenses/by-sa/4.0/>. For the Wikipedia list the licence is as `meta.json` states it;
  this file does not record a separate check of it.
- **Attribution.** The About page shows the text that Python wrote into `meta.json` (`data.data_licence.attribution`).
  It names the two DoltHub repositories and the Wikipedia list (with the revision used), says the data is licensed under
  Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0) and that this project selected, filtered and
  computed on it, gives FRED's citation for `DTB3`, and says which committed values are **not** under CC BY-SA: the two
  Yahoo-derived labels and the share of gap contradictions built from one of them, under Yahoo's terms.
- **ShareAlike.** Derived data that is committed here is adapted material, so treat it as CC BY-SA 4.0
  too, except the Yahoo-derived labels above. The owner should confirm this reading before the repository goes public.
- **Yahoo (owner decision of 2026-10-29).** `sample_funnel.json` exports `share_gap_contradicts` per move tercile,
  a share of events whose Yahoo gap verdict contradicts the label (from `timing_check.gap_verdict_yf`). It falls under
  Yahoo's terms, not CC BY-SA. The Yahoo prices and market caps themselves are downloaded locally into
  `$VOL_DATA_DIR/earnings-vol-study/raw` by the Python side (parquet caches go in
  `$VOL_DATA_DIR/earnings-vol-study/cache`) and are never committed, exported, or put in `dist/`.
- **Cboe.** No Cboe value is committed, exported, or put in `dist/` (VIX via FRED included).
- **FRED.** `DTB3` is public domain and FRED asks for a citation (given in the attribution); no rate value is exported,
  only IVs computed with it. The root `DATA.md` says what each source's terms restrict.

## What the pages show

The 3D preview draws an **illustrative synthetic surface** from a seeded random generator (seed 2026) and says so on
screen: "Illustrative synthetic shape — not data". The Sample page draws event counts from `sample_funnel.json`
(real counts, the move terciles and the E ≤ 0 line). The IV measures page draws the distributions in
`iv_measures.json` (histograms and quantiles of the implied move and the 30-day crush). No other page shows study
results.

## Caveats for later milestones

Survivorship, point-in-time and look-ahead caveats belong with the Python code that builds the event
panel. When a chart is added here, the Python exporter must put those caveats in the file's `data`
so the page can show them next to the chart. `sample_funnel.json` already does this: its `caveats` array is
listed on the Sample page.
