# Data provenance

The app contains **no computed results of its own**. It reads JSON files from `public/data/`
written by the Python exporter (`tools/export_app_data.py`) and draws them.

## JSON contract (schema 0.1.0)

Every file in `public/data/` is one envelope with exactly these keys:

| key | type | meaning |
|---|---|---|
| `schema_version` | string, must be `"0.1.0"` | contract version the app understands |
| `kind` | string | what `data` holds, for example `"meta"` |
| `generated_at` | string | ISO-8601 UTC timestamp ending in `Z` |
| `source_commit` | string | git commit of the Python code that produced the file |
| `data` | object | the payload |

`src/lib/contract.ts` checks this and reports a descriptive error (never coerces). The app loads
`data/meta.json` at start-up (relative URL, so it works under a sub-path) and shows the schema
version, milestone and source commit in the footer; a missing or invalid file shows an error there.
In `meta.json`, `data.milestone` is a non-negative integer (0 means M0).

`meta.json` is also where the About page gets its data-sources table: the page draws the table from this file and
the app keeps no copy in code. (This file and the README describe the same sources in prose. Those copies are
written by hand, and no test compares them with `meta.json`.) The file's `data` object has exactly these keys, and
`parseMetaData` in `src/lib/meta.ts` checks them before the About page draws the table:

| key | type | meaning |
|---|---|---|
| `project`, `title` | non-empty strings | what the project is called |
| `milestone` | non-negative integer | 0 means M0 |
| `data_sources` | non-empty array | one object per source: `name`, `uses` (tables or series taken), `url` (https), `licence`, `committed` (boolean) |
| `data_licence` | object | `name`, `url` (https, the licence text), `applies_to` (source names the licence covers), `attribution` (text shown under the table) |

The Python exporter (`DATA_SOURCES` and `DATA_LICENCE` in `tools/export_app_data.py`) owns this content, and the
committed `public/data/meta.json` is its output. Two checks guard it: `tests/test_export_app_data.py` compares the
file's `data` with the exporter's `meta_data()` (it ignores `generated_at` and `source_commit`, which change on every
export), so an edit to only one of the two fails; and `parseMetaData` rejects a source named in `applies_to` whose
`licence` is not `data_licence.name`. After you change the exporter, run `uv run python tools/export_app_data.py`
and commit the new file.

## Sources and licences

| source | used for | licence | committed here? |
|---|---|---|---|
| DoltHub `post-no-preference/earnings` | `earnings_calendar`, `eps_history` | CC BY-SA 4.0 | derived rows only |
| DoltHub `post-no-preference/options` | `option_chain` | CC BY-SA 4.0 | derived rows only |
| CBOE single-stock VIX indices (`VX*`) | single-stock IV | see source | **never** |
| Yahoo Finance prices via `yfinance` | daily prices | see source | **never** |

- **CC BY-SA 4.0 (confirmed).** Both DoltHub repositories contain a `LICENSE.md` reading
  "Attribution-ShareAlike 4.0 International" (read from each repository's `dolt_docs` table through
  the DoltHub SQL API on 2026-10-28; the repository web pages do not state it). Licence text:
  <https://creativecommons.org/licenses/by-sa/4.0/>.
- **Attribution.** "Contains data from the DoltHub repositories post-no-preference/earnings and
  post-no-preference/options, licensed under Creative Commons Attribution-ShareAlike 4.0 International
  (CC BY-SA 4.0). Changes: selected and filtered by this project." The About page shows the text that Python
  wrote into `meta.json` (`data.data_licence.attribution`), which also says that CBOE and Yahoo Finance data
  is never committed.
- **ShareAlike.** Derived data that is committed here is adapted material, so treat it as CC BY-SA 4.0
  too. The owner should confirm this reading before the repository goes public.
- **CBOE and Yahoo.** Licences were not checked ("see source"). Their data is downloaded locally into
  `$VOL_DATA_DIR/earnings-vol-study/raw` by the Python side (parquet caches go in
  `$VOL_DATA_DIR/earnings-vol-study/cache`) and is never committed, exported, or put in `dist/`.

## Milestone 0

No market data is shown yet. The 3D preview draws an **illustrative synthetic surface** from a seeded
random generator (seed 2026) and says so on screen: "Illustrative synthetic shape — not data".

## Caveats for later milestones

Survivorship, point-in-time and look-ahead caveats belong with the Python code that builds the event
panel. When a chart is added here, the Python exporter must put those caveats in the file's `data`
so the page can show them next to the chart.
