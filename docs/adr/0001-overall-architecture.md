# ADR 0001: Overall architecture

- **Status:** Accepted (milestone 0), revised 2026-10-28 after the milestone-0 methodology and delta reviews, and
  2026-10-29 after the milestone-1 review (notes below)
- **Date:** 2026-10-28
- **Deciders:** project owner. Drafted by the architect agent; to be attacked by the adversarial reviewer.
- **Related:** [0002 day 0](0002-day-zero-convention.md), [0003 IV measures](0003-iv-measures.md),
  [0004 windows](0004-baseline-and-event-windows.md), [0005 tests](0005-statistical-test-suite.md),
  [data model](../architecture/data-model.md)

> **Revised after milestone-0 review** ([ledger](../validation/m0-methodology-ledger.md)). The architecture is
> unchanged. Two things it quotes from other ADRs changed:
>
> - **The oracle value.** The test-strategy table quoted the hand-worked oracle as E = 0.000693. That number came from
>   a prototype that did not follow ADR 0003's forward rule (ledger N1). It is now 0.00088284.
> - **A new input (proposed, pending the owner's decision; see ADR 0002 Status).** ADR 0002 proposes taking the timing label from SEC EDGAR 8-K filings, because the price-gap rule
>   selected on move size (ledger claim 2). EDGAR is US-government public data (class U). It is a new `ingest` input
>   of the `events` layer.

> **Revised after the milestone-0 delta review** ([delta ledger](../validation/m0-delta-ledger.md)).
>
> - **Unmarked (claim 4a): the `events` row of the layer table listed "SEC EDGAR 8-K filing index" as an input** with
>   no qualifier, as if EDGAR were approved. It now says "only if the owner approves EDGAR", like the `ingest` row.
> - **A new input under ADR 0002's default rule.** The press release of every `daily` and `mixed` event is looked up
>   by hand (ADR 0002 §3, route (a)). The look-ups are recorded in a committed file,
>   `data/manual/press_release_checks.csv`, which the `events` layer reads. The class-F text in §7 now names
>   ADR 0002's *default* rule (it said "fallback") and marks the EDGAR alternative "proposed".

> **Milestone 1, 2026-10-29: measured, and one planned fallback taken.**
>
> - **The fingerprint guard tripped on a pure SELECT, so the pipeline reads a private copy** ("How we'll know it's
>   wrong", first bullet). Tested on a copy of the `earnings` clone before anything ran in the shared one: with dolt
>   2.6.1, `dolt sql -q "SELECT HASHOF('HEAD')"` rewrites `noms/manifest`, `noms/journal.idx`, the chunk journal and
>   the `stats/` store. The bytes stay the same; the modification times change. A test reproduces it on a throw-away
>   `dolt init` repository (`tests/test_dolt.py`). As this ADR decided for that case, each clone is now copied to
>   `cache/dolt_mirror/<repo>/` (`ingest/dolt.py`, `refresh_mirror`), every query runs there with `--disable-auto-gc`,
>   and each batch checks that the shared clone's (path, size, mtime) fingerprint did not change at all and that the
>   mirror's data files kept their bytes. Dolt was never run inside a shared clone by this project. The copy took
>   0.30 s (`earnings`, 1.8 GB) and 5.23 s (`options`, 8.3 GB) on this machine. **The hub session has not been told**:
>   this project cannot write to the hub's `STATUS.md`, so the owner should pass it on. The hub's own clones show the
>   same touches (the `options` clone's manifest was rewritten at 2026-10-28 14:11 CDT, before this milestone ran).
> - **`dolt sql -r parquet` works and replaces CSV** (§3): typed dates, decimals and real nulls, at the same speed (one
>   month of `option_chain` for 50 names: 40.75 s Parquet, 40.25 s CSV). The `'<NULL>'` sentinel is therefore not used.
> - **Pinning** reads the commits named in `params.yaml` (earnings `fjrb6h5le9h1qiif2j4pl6cpaas7pnee`, options
>   `msfqpodh24viv7prdqdan8517rkjp861`, both HEAD on 2026-10-29) and checks that they exist, instead of reading HEAD on
>   every run, so a re-run reads the same data after the hub pulls. They go into `params_hash` and every manifest.
> - **Extraction wall time** ("Consequences", "How we'll know it's wrong"): 82 monthly `option_chain` queries for the 52
>   source tickers of the 50 companies, 2020-01 to 2026-10, took 1,294 s of query time in total (21.6 minutes;
>   8,174,225 rows). A daily-era month took 41 s at the median and 51 s at most, a Mon/Wed/Fri month 6.4 s. That is
>   under the 2-minute-per-month line, so the batching stays.

> **Milestone 2, 2026-10-29.** The measures layer is built (`chain_expiry`, `iv_daily` and the new `event_iv`; the
> layer table below names the modules). `chain_expiry` stays local (17.0 MB, and its `df` is a FRED value); `iv_daily`
> (4.7 MB) and `event_iv` are committed. Under the owner's data decision of 2026-10-29 (§7) the registry can name the
> class-R columns a committed table keeps; milestone 2 keeps one, `timing_check.gap_verdict_yf`. The JSON contract is
> at 0.3.0. Walkthrough: `docs/milestones/02-iv-measures.md`.

> **Revised after the milestone-1 review** ([ledger](../validation/m1-ledger.md), 2026-10-29).
>
> - **The layer table lacked `session_snapshot`**, which `measures` writes at milestone 1. It is now listed.
> - **"`test_layering` enforces purity" was refuted (claim 15).** It checked only the direction of imports. It now
>   also fails when a module of `events`, `measures`, `panel`, `stats` or `export` other than its `run.py` imports
>   a file, network or process module or calls `open()` or a read/write method.
> - **The shared-clone fingerprint now covers the whole clone folder**, not only `.dolt/` (claim 1b), so a file
>   created beside `.dolt/` is caught. The mirror's content fingerprint still sizes, but does not hash, the large
>   content-addressed table files; a same-size change to one of them would go unseen. Hashing them would read
>   about 10 GB around every batch.
> - **§7's class-F example** no longer names a committed market-cap rank: `security.universe_rank` was a per-row
>   Yahoo-derived number for 497 firms (claim 10) and was removed from the committed table.

## In one paragraph

The study is a one-way Python pipeline in `src/earnings_vol/`. It runs in six stages: **ingest → events →
measures → panel → stats → export**. Each stage reads typed Parquet tables and writes typed Parquet tables. The
computation inside a stage is a pure function, so a hand-worked example can test it. Raw data stays outside the
repository under `VOL_DATA_DIR`. The shared Dolt clones are read with the `dolt sql` command line only. Every
query is a `SELECT` pinned to a commit with `AS OF '<hash>'`. A fingerprint check before and after each batch
proves that nothing in `.dolt/` changed. The React app receives one versioned JSON file per view and never
computes a statistic. Only small tables derived from DoltHub are committed, under CC BY-SA 4.0. No committed column
holds a Yahoo or CBOE value for a date or event, and no committed column lets a reader compute one directly (§7).
Two kinds of value derived from that data may still be committed. One is a statistic over many values, and only if
an export-time disclosure test shows that nothing exported can be solved for any single event's value or any VIX
change. The other
is a categorical label, such as an announcement's timing or a VIX tercile. Where the line sits is the owner's
decision.

## Context

What has to be true:

1. **The data is large, shared and live.** The two DoltHub clones in `~/data/vol-projects/dolthub/` (1.8 GB
   `earnings`, 8.3 GB `options`) are read by four projects. Two rules come from the hub file
   `~/data/vol-projects/STATUS.md`: "Never write into the dolt clones" and "Always filter on `date` first: it is
   the leading key". The upstream publisher commits new data every day at about 06:35 UTC. The DoltHub
   `dolt_log`, checked on 2026-10-28, shows commits such as `option_chain 2026-10-26 update` at
   `2026-10-27 06:34:46`. A result is therefore only reproducible if it names the commit it read.
2. **Licences differ by source.** Both DoltHub repositories carry a `LICENSE.md` titled *Attribution-ShareAlike
   4.0 International* (read from their `dolt_docs` table on 2026-10-28). CBOE index history and Yahoo prices are
   not ours to redistribute. The repository is public (see `app/CLAUDE.md`).
3. **The app never computes.** Python writes JSON, and the app validates the envelope and draws. The envelope is
   already fixed (`src/earnings_vol/contract.py`, `app/src/lib/contract.ts`, schema `0.1.0`).
4. **The owner is learning and must defend every line in an interview.** We want few moving parts, plain
   pandas/NumPy/SciPy/statsmodels, one direction of data flow, and every formula in a docstring next to its code.
5. **Being wrong is cheap to detect but expensive to notice late.** A bad day-0 label or a wrong time clock
   produces plausible-looking numbers. So the tests must be able to fail. See *Testing* below.

## Decision

### 1. A layered pipeline with one direction of data flow

```
 ingest ──► events ──────► measures ──► panel ───────► stats ──► export
 (I/O)      (pure)         (pure)       (pure)         (pure)    (I/O)
   │          │               │           │              │         │
   ▼          ▼               ▼           ▼              ▼         ▼
 raw/*    session,         session_      event_window_  results  app/public/data/*.json
 cache/*  market_daily,    snapshot,     obs,                    data/derived/*.parquet
          security,        chain_expiry, event_measures,
          ticker_alias,    iv_daily      event_measures_vx
          events, eps,
          timing_check
```

| Layer | Modules (planned) | Reads | Writes (tables in data-model.md) |
|---|---|---|---|
| `ingest` | `dolt.py`, `prices.py`, `fred.py`, `cboe.py`, `edgar.py` (accepted 2026-10-28; runs only once the owner sets the `SEC_EDGAR_USER_AGENT` contact string), `universe.py` | Dolt clones, yfinance, FRED, CBOE, SEC EDGAR submissions JSON (one per security; only if approved), S&P 500 list | `raw/…` downloads, `cache/…` extracts |
| `events` | `calendar.py` (NYSE sessions), `market.py`, `events.py`, `timing.py`, `eps.py` | raw and cache extracts (calendar, EPS, Yahoo prices, FRED, S&P list, and the SEC EDGAR 8-K filing index only if the owner approves EDGAR); the committed press-release look-up record `data/manual/press_release_checks.csv` (ADR 0002 §3, data model §1.3) | `session`, `market_daily`, `security`, `ticker_alias`, `events`, `eps`, `timing_check` |
| `measures` | `black.py`, `chain.py`, `termstructure.py`, `realised.py`; at milestone 1 `snapshots.py`, `forward.py`, `snapshot_close.py`; at milestone 2 `black.py`, `chain.py`, `termstructure.py`, `tables.py`, `event_iv.py` (the planned `realised.py` became part of `event_iv.py`) and `report.py` | option extracts, `session_snapshot`, `session`, `market_daily` (`r_cont`), `security`, `ticker_alias`, `events` (day 0, to classify spanning expiries) | `session_snapshot` (milestone 1: which sessions have a usable snapshot), `chain_expiry`, `iv_daily`, `event_iv` (milestone 2: the IV columns of `event_measures`, data model §3.11a) |
| `panel` | `panel.py`, `abnormal.py`, `eligibility.py` | `iv_daily`, `chain_expiry`, `events`, `eps`, `security` (`cboe_vx_index`), `session`, `market_daily`, Yahoo and VX\* extracts (local `_yf`/`_cboe` columns) | `event_window_obs`, `event_measures`, `event_measures_vx` |
| `stats` | `eventtests.py`, `regress.py`, `multiple.py`, `validate.py` | `event_measures`, `event_measures_vx`, `event_window_obs`, `events`, `eps`, `security`, and for validation `iv_daily`, `chain_expiry` and the VX\* extract | `results` |
| `export` | `contract.py` (exists), `export.py`; runner `tools/export_app_data.py` (exists) | everything above | JSON views, `data/derived/` |

**Where each cross-table column lives, so that data flows one way.** A column is written by the first layer that has
all its inputs:

- `market_daily` is written by `events`. It is a session-keyed reference table like `session`, and `measures`
  (`r_cont` for discounting) and `panel` (VIX) both sit to its right.
- `events.sample` and `events.orphan_nearby` stay in `events`. `sample` is a function of day-0 dates alone (ADR 0004
  §5), and `orphan_nearby` needs only `eps.match_status` and `session`. Neither needs IV data. Inside the layer the
  order is fixed: `session`, `market_daily`, `security` → `ticker_alias` → base `events` → `timing` → day 0 and
  prev/next links → `eps` matching → `orphan_nearby`, `sample` → `exclusion_reason`. The other layers have fixed
  orders too. In `measures`: `chain_expiry` → `iv_daily`. In `panel`: window rows and baseline flags → β per
  security → market-adjusted window columns → the rest of `event_measures` → the same steps on VX\* →
  `event_measures_vx` (data-model §3.11). Each table is written once, at the end.
- Per-measure eligibility (`eligible_*`, `ineligible_reason`) moves to `event_measures` in `panel`. It needs observed
  snapshots and clean baseline counts. `events.exclusion_reason` keeps only event-level rules.
- The price-scaled surprises (`price_ref`, `surprise_scaled`, `abs_surprise_scaled_w`, `sue_hist`) move from `eps` to
  `event_measures`. They need the day −1 option forward from `measures`. `eps` keeps the raw EPS, consensus and match.
- `realised.py` stays in `measures` as a function library. `panel` calls it to fill `event_measures.realized_ret_0`,
  which is a leftward import. *Milestone 2:* by the rule above, the per-event IV columns (E at day −1, the crushes,
  `realized_ret_0`, `abs_move_cand_max`) are written by `measures` itself, which has all their inputs (`iv_daily`,
  `chain_expiry`, `events`), into `event_iv` (`measures/event_iv.py`). The order in `measures` is `chain_expiry` →
  `iv_daily` → `event_iv`. `panel` takes the columns over into `event_measures` at milestone 3.

Rules:

- **A layer imports only from layers to its left.** A test parses the imports with `ast` and fails on a
  backward import. This checks real structure, not a substring. **Reading a table follows the same rule:** a stage's
  `run_<stage>()` may read only tables written by earlier layers or earlier in its own fixed order. A second test
  compares each stage's declared reads with the writer layer of every table.
- **Computation is pure; I/O is at the edges.** Functions in `events`, `measures`, `panel` and `stats` take
  DataFrames or arrays and return them. They read no clock, touch no network and do no file I/O. A thin
  `run_<stage>()` reads the input Parquet, calls the pure functions and writes the output with its manifest.
- **One parameter file.** `params.yaml` at the repository root holds every tunable choice from ADRs 0002 to 0005:
  windows, filters, clocks, thresholds. It is loaded into a frozen dataclass. The SHA-256 of its canonical
  form, `params_hash`, goes into every output. Changing a parameter changes the hash, so stale caches are
  detected rather than reused.

### 2. Where the data lives

```
$VOL_DATA_DIR/                         (default ~/data/vol-projects; see src/earnings_vol/config.py)
  dolthub/earnings/  dolthub/options/  shared, READ-ONLY, never written by this project
  earnings-vol-study/                  this project's own folder: config.project_dir()
    raw/                               small sources that this project downloads: config.raw_dir()
      yfinance/<ticker>.parquet        OHLCV + Dividends + Stock Splits (not committed)
      fred/<series>.parquet            DTB3, VIXCLS
      cboe/<index>.csv                 VXAPL, VXAZN, VXGOG, VXGS, VXIBM as downloaded (not committed)
    cache/                             files that can be rebuilt: config.cache_dir()
      dolt/<repo>@<commit>/<table>/<yyyy-mm>.parquet  query extracts, keyed by Dolt commit
      stage/<params_hash>/<table>.parquet  derived tables
      stage/<params_hash>/<table>.manifest.json
```

This follows the hub's `STATUS.md`: each project downloads its own small sources into
`$VOL_DATA_DIR/<repo>/raw/`. The Dolt extracts and the derived tables can be rebuilt, so they sit next to `raw/`,
in `cache/`. `config.py` has one function for each folder.

**Cache format: Parquet** (pyarrow, zstd). It keeps types: dates stay dates, decimals become float64 with an
explicit null, enums become dictionary strings. It is columnar, so reading 3 of 13 chain columns is cheap. pandas
reads it natively. Every write checks the Arrow schema against the one in `data-model.md`. A mismatch is an
error, not a silent cast. Every table has a sibling **manifest**: input file SHA-256s, the Dolt commit hashes,
`params_hash`, the git commit of the code, the row count and the UTC write time. A stage is rebuilt when any
input hash differs. Nothing is rebuilt because of a file's modification time.

### 3. How we read Dolt: the `dolt sql` CLI, read-only, pinned with `AS OF`

```
dolt sql -r csv -q "SELECT … FROM option_chain AS OF '<commit>' WHERE date BETWEEN … AND act_symbol IN (…)"
```

This runs as a subprocess with `cwd` set to the clone and the result parsed into a typed DataFrame. CSV prints SQL
NULL as an empty field. That is unambiguous for the numeric columns. For the one text column where it matters,
`earnings_calendar.when`, we select ``COALESCE(`when`, '<NULL>')``. **The sentinel is a transport detail only.** The
parser turns `'<NULL>'` back into a real null before it writes the cache extract, so no Parquet file or table ever
holds it, and `events.timing_raw` is a nullable enum {`BMO`, `AMC`} (data-model §2). A unit test feeds the parser the
three source values plus an unknown string. It checks that the unknown string is an error and that the output holds a
null, not the text. If `-r json` or `-r parquet` proves faster on dolt v2.6.1, it may replace CSV. That is an
implementation detail, measured at milestone 1.

- **Batching.** `option_chain`'s primary key starts with `date`. One query per calendar month, filtered by
  `date BETWEEN` and `act_symbol IN (<≈50 tickers>)`, is about 80 queries for 2020–2026. Each result is cached as
  one Parquet file under `cache/dolt/options@<commit>/option_chain/<yyyy-mm>.parquet`. A month that is already
  cached is never queried again for the same commit.
- **Pinning.** The pipeline reads `SELECT HASHOF('HEAD')` once per run and writes it to the manifest. That
  query and `AS OF '<hash>'` were both run on the DoltHub API on 2026-10-28. Every query then
  uses `AS OF '<that hash>'`. A `dolt pull` by the hub session in the middle of a run cannot mix two data
  vintages.
- **How we guarantee read-only.** There are three independent guards:
  1. *Statement allowlist.* The query function rejects anything that is not a single statement starting with
     `SELECT`, `WITH`, `SHOW` or `DESCRIBE`. Semicolons, `CALL`, `dolt_*` procedures and all DML/DDL keywords
     are refused. Unit-tested with hostile strings.
  2. *Commit pinning.* Every query reads a historical commit through `AS OF`. Only SELECTs run, so no write path
     exists.
  3. *Fingerprint check.* Before and after each extraction batch we record `(path, size, mtime_ns)` for every
     file under `<clone>/.dolt/` and the HEAD hash. If anything differed, the batch aborts with an error naming
     the changed files. Two causes are possible: our process wrote something, or the hub pulled new data in the
     middle of the batch. The batch must stop in both cases. An integration test, marked `dolt` and skipped
     when the clone is absent, runs one real query and asserts that the fingerprint did not change.
- **Never `dolt sql-server`.** A server writes `sql-server.info` and a lock file into the repository directory.
  Recent versions may also write statistics under `.dolt/stats`. Any other session's `dolt sql` would then
  silently route through our server. All of those are writes to a shared resource.

### 4. The JSON contract to the app

- **One file per view** in `app/public/data/<kind>.json`, where `kind` equals the file stem. The planned files
  are `meta`, `sample_funnel`, `event_paths`, `heatmap`, `terrain`, `implied_vs_realised`, `tests`,
  `drivers` and `validation`. [data-model.md §4](../architecture/data-model.md#4-python--app-json-contract)
  lists every field.
- **The envelope is fixed:** `schema_version`, `kind`, `generated_at`, `source_commit`, `data`, and `data` is
  always an object. **`schema_version` versions the whole contract**, envelope and all payload shapes. Any field
  change bumps it, and `contract.ts` and the exporter change in the same commit. The app already refuses
  versions it does not know. The per-view files arrive as `0.2.0`.
- **The app never computes a statistic.** Every number it displays is in the file: means, CI bounds, n,
  p-values, Holm-adjusted p-values. UI-only transforms are allowed: grid to mesh, formatting, axis layout.
- **Missing is `null` plus a reason.** NaN and Infinity are refused at export (`allow_nan=False` already). Every
  nullable number has a sibling `*_status` string when the reason matters, for example
  `implied_move_status = "nonpositive_event_variance"`.
- **Stable bytes.** Floats are rounded at export to a fixed number of decimals per field family: IV 4,
  moves 5, p-values 4 significant figures. Keys are sorted (already). Rerunning on the same inputs gives a
  byte-identical file, so a git diff shows only real changes.
- **Provenance in every file.** `data.provenance = {params_hash, dolt_commits: {earnings, options},
  sample_label, code_commit}`.

### 5. Notebooks are generated from `src/`

This already exists (`tools/build_notebooks.py`, `tests/test_notebooks_sync.py`). One notebook per milestone
(`01_events`, `02_iv_measures`, …). Each one imports `earnings_vol` and calls the stage functions. No logic is
defined in a notebook. The sync test fails if a committed notebook differs from a fresh build.

### 6. Testing: tests that can fail

| Kind | What it pins | Example |
|---|---|---|
| Hand-worked oracle | a formula on numbers computed by hand in the test's comment | event variance on the AAPL 2025-10-30 quotes in ADR 0003 (E = 0.00088284 on the session clock, with the 4-strike forward; the milestone-0 value 0.000693 came from a prototype that used all strikes and was corrected after the review); the day-0 table in ADR 0002; BMP on a 4-event toy example |
| Synthetic truth | a whole stage recovers known parameters | build Black-76 prices on the real sparse strike grid from a two-component model with known E and σ_d. The ATM, cm30 and E code must recover them within 1e-6. |
| Monte Carlo calibration | a test statistic has the right size | under H0 with partial date clustering (ADR 0005 §5), the 5% rejection rate must fall inside the binomial 99% band. Seeded RNG. The primary statistics also pass gate G1 at the real event design (ADR 0005 §5). |
| Mutation check | the tests above notice breakage | each test module's docstring lists the mutations it must catch (swap T1/T2, calendar clock instead of sessions, all-strike forward instead of the 4-strike rule, flip BMO/AMC, drop √(2/π), day-0 clusters for a ramp measure). At each milestone review, apply them by hand and confirm that the module's tests go red. |
| Contract | exporter ↔ app agreement | existing `test_contract.py` and `contract.test.ts`, plus one key-set test per view |
| Structure / guards | layering, read-only Dolt, licence classes | import graph and declared-reads tests, fingerprint integration test, "no `_yf`/`_cboe` column in `data/derived` or JSON except one a committed table names in `keep_restricted`" test (since the owner's decision of 2026-10-29, §7), "class R ⇔ suffix" test over the schema registry's value columns, "no exported cell under 10 events or 10 dates" test, and the export disclosure (row-space) test (§7) |

Rules (from the owner's global standards): no test greps source text. No test helper re-implements the thing
under test. A new assertion is seen to fail before it passes. Coverage is not evidence.

### 7. Licensing

> **Owner decision, 2026-10-29 (real data; replaces the two notes below and every "default taken: strict"
> note).** The repository is a public portfolio. It commits the real data that the app and the docs need: the
> exported app JSON; small derived per-event, per-company and per-session tables in `data/derived/`, including
> class-R columns built from Yahoo, Cboe, FRED, Kaggle or OptionsDX data; and real values quoted in the docs. It
> never commits bulk raw files: vendor downloads, the yfinance Parquet, the Dolt clones and mirrors, the cache, or raw
> `option_chain` rows. Each committed data file stays under about 10 MB and never reaches 50 MB.
> `tests/test_repo_data_files.py` checks both rules on every run, and `DATA.md` gives each source's terms.
> *After the milestone-2 review (claim 15b)* the check also refuses compressed archives anywhere, and any file in
> `data/derived/` or `app/public/data/` that is not on the allow-lists below (by name, and by its columns or its
> `kind`), so a re-serialised raw month or a local-only table is refused without the local vendor folder too.
> Tests keep their hand-worked made-up values. Public history stays as it is. `tools/licensing/scan_real_rows.py`
> is kept as a tool, but is no longer a push gate.

> **Owner decision, 2026-10-29 (data policy), replaced the same day by the note above.** Keep the strict rule. No new commit may hold a real vendor
> value or a vendor data file: no Yahoo, Cboe (including VIX via FRED), Kaggle or OptionsDX values. Tests use
> made-up values, and DoltHub rows are preferred made up there too. Public history stays as it is: commit `3636e98`
> holds two quoted Yahoo values (ADR 0002 and `research/prototypes/worked.py`, both AAPL around 2025-10-30). They are
> left in place, with no rewrite and no force-push. Before every push, `tools/licensing/scan_real_rows.py` must report
> 0 lines flagged.
>
> **Owner decision, 2026-10-29 (DoltHub tables), replaced the same day by the first note.** Small derived DoltHub tables may be committed, as the original
> plan said. They are per-event and per-company tables in `data/derived/`, under CC BY-SA 4.0 with the attribution
> and licence notice (`data/derived/LICENSE`, `README.md`). Raw `option_chain` rows are never committed. Every
> Yahoo, Cboe or FRED column (class R) is dropped before a table is written. The strict rule still covers Yahoo,
> Cboe, FRED and OptionsDX/Kaggle values.

- **Code:** MIT (root `LICENSE`).
- **`data/derived/`:** CC BY-SA 4.0 with attribution (`data/derived/README.md`, `LICENSE`), except the two
  Yahoo-derived columns named there (`timing_check.gap_verdict_yf`, `security.in_universe`), which fall under Yahoo's
  terms. *Allow-list (revised after the milestone-2 review):* a table goes there only if the schema registry marks it
  committed, and only with its committed columns: at milestone 2 `security`, `ticker_alias`, `session`, `events`, `eps`,
  `timing_check` (the verdict only), `session_snapshot`, `iv_daily` and `event_iv`; later `event_window_obs`,
  `event_measures` and `results`. Besides the tables: `README.md`, `LICENSE` and the milestone-0
  `earnings_calendar_30_large_caps.json`. `tools/licensing/check_data_files.py` (rule 6) enforces the list. The S&P 500
  sector list in `security` is taken from Wikipedia, which is CC BY-SA and so compatible. `session` is the public NYSE
  calendar. Size budget: under 20 MB in total.
- **The rule, column by column.** Each column has a licensing class (data-model §2.1):
  - **U**: DoltHub, FRED `DTB3`, Wikipedia or calendar lineage only. Keys and counts of available observations are
    U. Committed.
  - **R**: a numeric value of a Yahoo or CBOE series for one date or one event, or any transform that keeps its
    magnitude (log, change, gap, z-score, residual). It also covers **any column that can be combined with committed
    columns to compute such values**. Not committed, except a column a committed table names in `keep_restricted`
    (owner decision of 2026-10-29; at milestone 2 only `timing_check.gap_verdict_yf`). *Example:* `e_abn_cboe` = Δln cm30 − β·Δln VIX. If it were
    committed next to `d_ln_cm30` and `beta_vix`, it would give back Δln VIX exactly. So it is class R, and so is
    every market-adjusted per-event measure. *Second example, found by the adversarial review:* the per-event baseline
    sd `s_abn` gives one quadratic equation per event in the unknown VIX changes. With ≈ 880 events against ≈ 660
    dates, a simulation solved that system for every date (data-model §2.1). So it is `s_abn_cboe`.
  - **S**: a statistic over many restricted observations, such as `beta_vix` (50 slopes) or a correlation with
    VXAPL. It is committed only under the export rules in data-model §2.1:
    1. market-adjusted aggregates for the `all` and `timing` subgroups only, and finer subgroups mean-adjusted;
    2. no fixed-effect coefficients;
    3. cells of ≥ 10 events on ≥ 10 dates, with secondary suppression and no `n` printed for a suppressed cell;
    4. a **disclosure test** at every export. With the VIX *levels* as unknowns and each row built from its exact
       event set, it asserts by SVD that no single event's market-adjusted value, and no VIX difference between
       any two dates, lies in the row space of the exported linear statistics.

    *Third example from the review:* the minimum cell size alone was not enough. Market-adjusted path cells by
    timing, sector and season, each with ≥ 10 events on ≥ 10 dates, recovered Δln VIX exactly on every day-0 date in
    a simulation, by ordinary least squares. With `all` and `timing` only, no VIX change was identified. One event's
    value still was, through the difference between path and scalar event sets, and that is why the test checks
    per-event values too (data-model §2.1).
  - **F**: a categorical label derived with restricted data, from which no numeric value can be computed. It is
    either a fact that Yahoo prices only helped check (`timing_used`, `timing_status`, and through them day 0, under
    ADR 0002's default rule; under its proposed EDGAR rule, only if the owner approves it, they would have no Yahoo
    lineage and be class U, with the caveat in ADR 0002's delta revision note, item 9), or a
    coarse label with at most 5 levels (`vix_regime`), or a one-time selection of firms (`security.in_universe`;
    the market-cap rank behind it is not committed, milestone-1 review). A finer label on a per-date series is R.
    Committed by default.
- **Column-provenance suffixes make the rule mechanical.** Every class-R column ends in `_yf` (Yahoo) or `_cboe`
  (CBOE). **That includes VIX**: FRED's `VIXCLS` is a CBOE index republished by FRED, so it is CBOE data. A
  market-adjusted measure is therefore `crush_cboe`, and its mean-adjusted twin `crush_mean_adj` is committed. The
  writer for `data/derived/` and the JSON exporter drop suffixed columns, except one a committed table names in
  `keep_restricted` (owner decision of 2026-10-29; at milestone 2 only `timing_check.gap_verdict_yf`). Two tests
  guard this. One asserts that no other suffixed column survives in the output. The other asserts, over the schema registry's value columns, that a column
  is class R exactly when it has a suffix, so a forgotten suffix fails as loudly as a stray one. Examples:
  `gap_z_d_yf`, `ln_mcap_yf`, `aliv_cboe`, `s_abn_cboe`.
- **Owner decision (a licence-interpretation call; not legal advice).** The default is strict for numbers and
  permissive for labels. It keeps the primary, market-adjusted per-event values local: they are published only as
  aggregates, and anyone with FRED `VIXCLS` can recompute them with the pipeline. Two other readings are possible:
  1. **Looser:** a sparse sample of Δln VIX on announcement dates is not "CBOE data" in the licence's sense. Then the
     market-adjusted columns lose their suffix and are committed. That is a rename, cheap before milestone 3 builds
     these tables.
  2. **Stricter:** labels count as Yahoo/CBOE data too. Withholding `vix_regime` is workable. Withholding the timing
     label is not, because day 0 depends on it and nothing per event could then be committed.

  The owner chooses the reading.
- **Per-event realised moves come from DoltHub, not Yahoo.** The realised day-0 move is measured from the
  put-call-parity forward of the same option snapshots ([ADR 0003 §e](0003-iv-measures.md#e-realised-move)). It is
  therefore CC BY-SA data and may appear per event in `implied_vs_realised.json`. Yahoo closes are used locally
  only, to cross-check it.
- **Aggregates are statistics, not data** (class S). A correlation with VXAPL, or a regression coefficient on log
  market cap, may be exported. A per-day VXAPL series may not. An aggregate over very few events or dates counts as
  per-event data. Many overlapping large cells can be solved jointly, as the review showed. Hence the export rules
  above, and a disclosure test rather than a rule of thumb. Per-security and other fine-grained views use
  mean-adjusted values. *This line is a
  judgement call, not legal advice. The owner decides whether it is acceptable for a public repository.*
- **App JSON inherits CC BY-SA**, except `sample_funnel.json`'s `share_gap_contradicts`, which is built from the
  Yahoo-derived `gap_verdict_yf` and falls under Yahoo's terms (the attribution in `meta.json` says so). The per-view
  files are otherwise derived from DoltHub. `meta.json` gets a
  `data_licence` field saying so (needs a contract bump).

## Consequences

- Good: each stage can be rerun alone and tested alone. A reviewer can trace any number in the app back to a
  manifest, a Dolt commit and a params hash.
- Good: the shared clones are protected by three independent mechanisms. A violation is detected, not just
  forbidden.
- Cost: the first extraction is roughly 80 monthly queries over an 8.3 GB store. Wall time is **unmeasured**, and we
  measure it at milestone 1. If it takes more than an hour, see "How we'll know it's wrong".
- Cost: the contract is versioned as a whole, so any payload change touches Python, TypeScript and a version
  bump in one commit. That is deliberate.
- Cost: `_yf`/`_cboe` suffixes are a naming discipline that must be followed. The class-R-iff-suffix test makes
  forgetting it loud.
- Cost: under the strict licensing default, `data/derived/` alone cannot reproduce the market-adjusted primary
  statistics. A reader needs the pipeline and their own FRED `VIXCLS` download.

## Alternatives rejected

| Alternative | Why rejected | What would have to be true for it to win |
|---|---|---|
| `dolt sql-server` + PyMySQL | It writes server-info, lock and possibly stats files into the shared repository. Other sessions' CLI calls would route through our server. It is a long-lived process with a port to manage. Typed results and lower per-query cost are real advantages. | The CLI's per-query start-up cost dominates (e.g. > 10 s per query × thousands of queries), *and* a private copy of the clone exists so the server touches only our copy. |
| `dolt dump` / `dolt table export` | It exports whole tables. `option_chain` covers ≈1,500 symbols, and we need about 50. No filter, so disk and time are wasted. | The study widens to the whole optionable universe. |
| DoltHub SQL API | Not reproducible offline, rate-limited, and slow: two of our tiny exploratory queries hit `context deadline exceeded` on 2026-10-28. Fine for schema discovery, which is how this ADR used it. | Never, for the pipeline. |
| A private full copy of the clones (`cp -r`) | 10 GB of duplicate disk, and it drifts from the hub's updates. It is the fallback if the fingerprint check ever shows that the CLI writes. | The fingerprint guard trips on a pure SELECT. |
| DuckDB / SQLite as the cache | Another engine to learn and explain, for no gain at this size. Estimated sizes: **≈ 85.7k `iv_daily` rows** (50 securities × 1,713 sessions, 2020-01-02 → 2026-10-26, including sessions without a snapshot), of which ≈ 61.4k are observed (50 × (695 Mon/Wed/Fri sessions + 533 daily)); ≈ 200k `chain_expiry` rows (3.3 per observed pair); and ≈ 9 million `option_chain` quote rows in the extract (≈ 3.3 expiries × ≈ 23 strikes × 2 sides per observed pair). Arithmetic in data-model §3.6. An earlier "about 27k" counted the daily era only (50 × 533). | Interactive cross-table SQL over the cache becomes the main way of working. |
| Notebooks as the source of truth | They are untestable, diff badly and hide state. | Never. Notebooks are generated views. |
| The app recomputing aggregates from per-event JSON | It would duplicate statistics in TypeScript and could disagree with Python. | Never. Recorded as an invariant in `app/CLAUDE.md`. |

## How we'll know it's wrong

- The **fingerprint guard trips on a pure SELECT run**. Then the CLI writes to the clone: switch to a private copy at
  once and tell the hub session.
- **Extraction wall time** is measured at milestone 1. If one month of `option_chain` for 50 symbols takes more than
  2 minutes, reconsider the per-symbol-month batching or `sql-server` against a private copy.
- **A rerun with the same params and commits produces different bytes** in any Parquet or JSON file. Then something
  non-deterministic (clock, dictionary order, unseeded RNG) leaked into a pure function.
- **The app needs a number that is not in a file.** Then the contract is missing a field; add it in Python and do
  not compute it in TypeScript.
