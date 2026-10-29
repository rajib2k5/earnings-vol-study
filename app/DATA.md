# Data provenance

The app contains **no computed results of its own**. It reads JSON files from `public/data/`
written by the Python exporter (`tools/export_app_data.py`) and draws them.

## JSON contract (schema 0.2.0)

Every file in `public/data/` is one envelope with exactly these keys:

| key | type | meaning |
|---|---|---|
| `schema_version` | string, must be `"0.2.0"` | contract version the app understands |
| `kind` | string | what `data` holds: `"meta"` or `"sample_funnel"` |
| `generated_at` | string | ISO-8601 UTC timestamp ending in `Z` |
| `source_commit` | string | git commit of the Python code that produced the file |
| `data` | object | the payload |

The version covers the **whole contract**: this envelope and the `data` shape of every kind below. A change to
either bumps it, in the exporter and in `src/lib/contract.ts` together. A file with another version (for example
the previous `"0.1.0"`) is rejected with a message that names both versions; the app does not try to read it.

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
| `files` | non-empty array of non-empty strings | the kinds of file available in `public/data/`, for example `["meta", "sample_funnel"]`; a test checks it lists every file that is there |
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
| `by_move_tercile` | `null` | always `null` at 0.2.0: the move terciles need milestone 2. An array is reserved for milestone 2 and is rejected until the contract version that defines it |
| `by_move_tercile_status` | non-empty string | why it is `null`; the page shows it as "not computed yet: ..." |
| `evar_nonpositive` | `null` | same rule as `by_move_tercile` |
| `evar_nonpositive_status` | non-empty string | why it is `null`; shown as "not computed yet: ..." |
| `lookups` | object | `n_done` (non-negative integer) and `complete` (boolean); the page says "provisional" until `complete` is true |
| `caveats` | array of non-empty strings | every one is listed on the page, next to the numbers |
| `provenance` | object | see "Provenance" below |

`loadSampleFunnel` (same file) fetches `data/sample_funnel.json` through an injected `fetch`, checks the envelope,
checks that `kind` is `"sample_funnel"`, then checks `data`. A missing or invalid file shows an error on the Sample
page instead of a chart.

### Provenance

Both files carry the same `provenance` object, checked by one validator (`src/lib/provenance.ts`), with exactly
these keys: `params_hash` (hash of the study parameters), `code_commit` (git commit of the Python code),
`sample_label` (which sample the numbers describe), and `dolt_commits` (an object with exactly `earnings` and
`options`, the commit of each DoltHub repository the data was read from). All four are non-empty strings. They say
which parameters, code and upstream data versions produced the file, so a number can be traced back.

## Sources and licences

This table follows the committed `public/data/meta.json`, which is the source of truth (the About page draws that
file, not this one).

| source | used for | licence | committed here? |
|---|---|---|---|
| DoltHub `post-no-preference/earnings` | `earnings_calendar`, `eps_history`, `eps_estimate` | CC BY-SA 4.0 | derived rows only |
| DoltHub `post-no-preference/options` | `option_chain`, `volatility_history` | CC BY-SA 4.0 | derived rows only |
| Wikipedia List of S&P 500 companies | company names, GICS sectors and CIKs | CC BY-SA 4.0 | derived rows only |
| FRED (Federal Reserve Bank of St. Louis) | `DTB3` (3-month T-bill rate), `VIXCLS` (VIX, a CBOE index) | see source | **never** |
| CBOE single-stock VIX indices (`VX*`) | single-stock IV | see source | **never** |
| Yahoo Finance prices via `yfinance` | daily prices, market caps (one-time universe rank) | see source | **never** |

- **CC BY-SA 4.0 (DoltHub, confirmed).** Both DoltHub repositories contain a `LICENSE.md` reading
  "Attribution-ShareAlike 4.0 International" (read from each repository's `dolt_docs` table through
  the DoltHub SQL API on 2026-10-28; the repository web pages do not state it). Licence text:
  <https://creativecommons.org/licenses/by-sa/4.0/>. For the Wikipedia list the licence is as `meta.json` states it;
  this file does not record a separate check of it.
- **Attribution.** The About page shows the text that Python wrote into `meta.json` (`data.data_licence.attribution`).
  It names the two DoltHub repositories and the Wikipedia list (with the revision used), says the data is licensed under
  Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0) and that this project selected, filtered and
  computed on it, and says that CBOE and Yahoo Finance data is downloaded locally and never committed.
- **ShareAlike.** Derived data that is committed here is adapted material, so treat it as CC BY-SA 4.0
  too. The owner should confirm this reading before the repository goes public.
- **CBOE and Yahoo.** Licences were not checked ("see source"). Their data is downloaded locally into
  `$VOL_DATA_DIR/earnings-vol-study/raw` by the Python side (parquet caches go in
  `$VOL_DATA_DIR/earnings-vol-study/cache`) and is never committed, exported, or put in `dist/`.
- **FRED.** Licence not checked ("see source"); `meta.json` marks it `committed: false`, and the About page shows
  that as "never".

## What the pages show

The 3D preview draws an **illustrative synthetic surface** from a seeded random generator (seed 2026) and says so on
screen: "Illustrative synthetic shape — not data". The Sample page draws event counts from `sample_funnel.json`
(real counts, no volatility results yet). No other page shows study results.

## Caveats for later milestones

Survivorship, point-in-time and look-ahead caveats belong with the Python code that builds the event
panel. When a chart is added here, the Python exporter must put those caveats in the file's `data`
so the page can show them next to the chart. `sample_funnel.json` already does this: its `caveats` array is
listed on the Sample page.
