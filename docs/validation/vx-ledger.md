# Cboe VX\* cross-check: ledger

The run log of the cross-check that ADR 0003 ("Validation plan (milestone 2)", items 1 and 3) planned. The plan it
follows is [`vx-preregistration.md`](vx-preregistration.md). Entries are written in the order they happened.

## 0. Before the first request to Cboe

- **Recorded at:** 2026-11-09T19:12:58Z (`date -u`), before any data download. (A HEAD request to the CSVs had been made
  at milestone 2; ADR 0003 records it. The first sentence of this entry said "before any request to `cdn.cboe.com`",
  which was wrong.)
- **Pre-registration:** `docs/validation/vx-preregistration.md`, SHA-256
  `94b246039e4cbd4d679e4d7e567ee7a2f35ad7ab333f182e6498096a653351d6` (`sha256sum`, measured at 19:12Z; it equals the
  hash the task brief gives). File modification time 2026-11-09T19:08:16Z. Untracked in git (`git status --short`:
  `?? docs/validation/vx-preregistration.md`).
- **No VX\* file on this machine before the download:** `$VOL_DATA_DIR/earnings-vol-study/raw/cboe/` did not exist,
  and `find / -name 'VX*_History.csv' -o -name 'VXAPL*'` found nothing.
- **Our series before the download:** `data/derived/iv_daily.parquet`, SHA-256
  `68aa42a346fe748c2fffe09c6768460ebfff09a86ad2798eca88325cbb718bf0`, byte-identical to the latest stage copy
  (`cache/stage/74bed6f4b1281810/iv_daily.parquet`, manifest `params_hash` `74bed6f4b1281810…`, equal to the current
  `params.yaml` hash). `cm30_blind_iv` non-null days: AAPL 1,219, AMZN 1,214, GOOGL 1,209, GS 1,214, IBM 1,201, each
  from 2020-01-02 to 2026-10-26 (1,713 rows per name).

## 1. The download (2026-11-09T19:14:00Z to 19:14:02Z)

- **Command:** `.venv/bin/python -m earnings_vol.ingest.cboe` (new module `src/earnings_vol/ingest/cboe.py`), started
  2026-11-09T19:14:00Z, exit 0 at 19:14:02Z. Before it ran, `fetch()` was exercised offline with a fake session (a 503,
  a connection error and a 307→200: 3 attempts and waits of 5 s and 15 s; three 503s: refused after 3 attempts; a 404:
  refused after 1 attempt, no retry).
- **Requests:** 5, one per symbol, each answered `307` then `200` (requests follows the redirect to
  `cdn-api.cboe.com`); 0 retries. User-Agent `earnings-vol-study/0.5 (research; +https://github.com/rajib2k5/earnings-vol-study)`;
  no other header was set, and no e-mail address or personal contact was sent.
- **Files** (`$VOL_DATA_DIR/earnings-vol-study/raw/cboe/<SYM>.csv`, with `fetch_log.json` beside them; local only):

| Symbol | Fetched (UTC) | SHA-256 | Bytes | Rows | First | Last |
|---|---|---|---:|---:|---|---|
| VXAPL | 2026-11-09T19:14:01Z | `9c486174445aaa611aa659bd9c5fb1f0e4030a031d77df7ae7b7679ce5c6a91d` | 202,907 | 3,978 | 2011-01-07 | 2026-11-06 |
| VXAZN | 2026-11-09T19:14:01Z | `fbbe1f3bdecb1275eb47f2533bba6d1c193240b04f18bfb6a5d02cd71e115e90` | 202,890 | 3,978 | 2011-01-07 | 2026-11-06 |
| VXGOG | 2026-11-09T19:14:01Z | `777a4d7f228a8a077e9f1a48b04c2c711a0ca5dae7cd990d5339ae5cf51881b4` | 202,898 | 3,978 | 2011-01-07 | 2026-11-06 |
| VXGS | 2026-11-09T19:14:01Z | `803fd9d59e01814b70d8bea7558961222c68f7ba854a489133c6464c3d5ee583` | 202,927 | 3,978 | 2011-01-07 | 2026-11-06 |
| VXIBM | 2026-11-09T19:14:01Z | `caa1aac4c3fccd21debfe0f2a7b2494f770e39f217b39bc56450e1a26e898ed5` | 202,905 | 3,978 | 2011-01-07 | 2026-11-06 |

- **Format:** header `DATE,OPEN,HIGH,LOW,CLOSE`, dates `MM/DD/YYYY`. ADR 0003 left the 2011 start unverified: all five
  files start on 2011-01-07.
- **Checks inside our window (2020-01-02 to 2026-10-26, 1,713 NYSE sessions), counts only:** each file has 1,712 rows
  there, every one on an NYSE session; one session is missing in all five (2020-10-16); no close ≤ 0, none missing; the
  five files carry the same dates; no two files carry the same closes; days with a close equal to the previous one:
  VXAPL 4, VXAZN 5, VXGOG 4, VXGS 5, VXIBM 10 (kept: the pre-registration names no staleness filter).

## 2. Before any statistic: inputs measured, decisions taken

Measured on 2026-11-09 after the download, before any statistic of §3 of the pre-registration was computed; this
section was written by 19:18:33Z (`date -u`).
Only counts and coverage were looked at.

- **One probe query in the mirror** (after the download; time not recorded): `dolt sql --disable-auto-gc -r csv -q "SELECT date, act_symbol,
  iv_current FROM volatility_history AS OF 'msfqpodh24viv7prdqdan8517rkjp861' WHERE date = '2025-10-30' AND act_symbol
  IN (...)"`, run from inside `cache/dolt_mirror/options` (0.22 s, 5 rows). It checked the column name and the speed;
  its values were masked in the output and are not recorded. It ran outside `dolt.guard`; the full extract (§3 below)
  runs inside it, so the guard also covers this earlier query's effect on the shared clone.
- **Per-expiry ATM IVs exist in the stage:** `cache/stage/74bed6f4b1281810/chain_expiry.parquet` (SHA-256
  `ce5a8e688a47230553dec8c088e64767b826aaa9011f8b3d071c6eb0d33af98f`, the current params hash). For the five names:
  19,191 rows (19,073 `ok`, 84 `no_atm`, 34 `no_forward`); usable expiries (`ok`, τ ≥ 5 sessions, an ATM w) on
  **6,070 of the 6,072 snapshot-`ok` sessions** (3 expiries on 5,040 days, 4 on 953, 2 on 64, 1 on 13). The longest
  usable expiry is at most **48 sessions** on every day (median 36), the shortest at least 7 (median 10).
- **Horizon coverage** with the study's blind interpolation (`termstructure.interpolate`, linear in τ, at most 10
  sessions of extrapolation, one-expiry flat-σ rule): 10 sessions 6,040 days; 15: 6,064; 21: 6,057; 30: 6,049; 42:
  5,480; **63: 0** (no expiry reaches 53 sessions). At 21 sessions it reproduces `iv_daily.cm30_blind_iv` on all 6,057
  days with a largest absolute difference of 0.
- **Bar iv's events:** the study's primary sample (`export.funnel.run_steps`, last step: 347 events; all 347 are
  `eligible_crush`) holds **34 events of the five names** (IBM 8, AMZN 7, GOOGL 7, AAPL 6, GS 6), day 0 from 2025-01-30
  to 2026-10-22, every one a one-session crush (day −1 is the session before day 0), and **all 34 `not_checked`**: their
  day 0 rests on the calendar's timing label.

**Decisions** (the pre-registration does not settle these; each takes the more conservative reading):

| # | Question | Decision |
|---|---|---|
| D1 | Interval type | Percentile interval, 2.5% and 97.5% of the 10,000 bootstrap values. A replicate where a statistic is undefined (no observation, zero variance) is dropped and counted. |
| D2 | The moving-block bootstrap | Session axis: every NYSE session from 2020-01-02 to 2026-10-26 (1,713). ⌈1,713 / L⌉ blocks of L consecutive sessions, starts uniform on [0, 1,713 − L], joined and cut to 1,713 (not circular). An observation enters as often as its session is drawn; a change is dated by its later session. One draw matrix per block length, shared by every name, the pooled statistics, the lags, the secondary changes and §5. |
| D3 | Seed | `20261109`. Block 20, block 60 and the event bootstrap each start a fresh `numpy.random.default_rng(20261109)`. |
| D4 | Primary and secondary changes | M = the sessions where both series have a value (> 0). Consecutive members of M give one change each; the gap is their distance in sessions. Gap 1: primary. Gap > 1: secondary, both series over the same two dates. |
| D5 | Lags | Lag L matches our session i with Cboe's session i + L (L = +1: Cboe one session later). Cboe values outside the window may be used for the shift. |
| D6 | Bar ii's reverse slope | OLS slope of Δln ours on Δln VX, with its reciprocal (the upper end of the errors-in-variables bracket). Both with block intervals. |
| D7 | Bar iii | Spread = VX close − 100 × ours, in vol points, on every session of M. "The name's median over all years" = the median over all of the name's days in M (not the median of the yearly medians). Years 2020–2026 (2026 to 10-26). Pass when the largest \|year median − all-days median\| ≤ 2.0. Intervals for the all-days median, that largest deviation and the share of days with VX above ours. |
| D8 | Bar iv | The 34 events above. Δln VX and Δln `cm30_blind_iv` (pre-registration §1; H1 itself uses the event-aware `cm30_iv`) from day −1 to day 0; an event without both values on both sessions is dropped and counted. **R is pooled only:** with 6–8 events per name, a per-name ratio would be an aggregate over fewer than 10 events, which data-model §2.1 treats as per-event data. |
| D9 | `volatility_history` dates | Its `date` is a snapshot date. It is mapped to sessions through the committed `session_snapshot` (`ok` rows), the map our own series uses. iv_current is compared with VX (spread VX − 100 × iv_current) and with ours (spread 100 × (iv_current − ours)): bar-i r of primary changes and the bar-iii all-days median spread, per name and pooled, block 20 and 60. |
| D10 | Maturity | Per-expiry ATM IVs exist on 6,070 of 6,072 snapshot sessions, so the identification runs. Horizons with values: 10, 15, 21, 30, 42; **63 has no value on any day** and is reported as not measurable. The medians are compared on the days where all five measurable horizons and iv_current exist. If the smallest median \|difference\| falls on 42 (the longest measurable horizon), the maturity is reported **UNRESOLVED** (at or beyond 42 sessions: 42 and 63 cannot be told apart); likewise if it falls on 10, the shortest horizon (at or below 10). Added at 19:19:17Z, still before any statistic: the edge rule at the short end. |
| D11 | Secondary changes | Reported with intervals, without a verdict. |
| D12 | ADR 0003's own slope band | ADR 0003, "How we'll know it's wrong", reads a slope outside [0.8, 1.2] as a failure; the pre-registration (which governs) makes bar ii descriptive. Whether each slope lies in [0.8, 1.2] is reported, labelled "exploratory, not pre-registered". **Superseded by the erratum of §9.1:** the pre-registration's premise ("the ADR set no tolerance") was false. |

## 3. The computation

- **First run, 2026-11-09T19:23Z** (`.venv/bin/python tools/vx_crosscheck.py`, 13 s; the extract of
  `volatility_history` ran inside `dolt.guard` in the mirror: 7 queries, one per year, each filtered on `date` first,
  6,273 rows, 6,148 with an `iv_current`, 4.0 s, shared clone unchanged). It wrote the JSON on a bootstrap axis of
  **1,712 sessions starting 2020-01-03**, the first day with a value, not D2's 1,713 sessions from 2020-01-02 (a
  session with no snapshot, so no observation). **A deviation from D2, corrected at 19:24Z**: the axis is now every
  session of our table, 2020-01-02 to 2026-10-26. The two runs were compared key by key: 348 numbers differ besides the window itself, every one an
  interval bound; the largest change is 0.039 vol points (GS's 2020 median spread, upper bound), and 10 move by more
  than 0.01, all bar-iii vol-point bounds; no point estimate, no `n`, no verdict, no lag finding
  and no maturity changed. The committed file is the corrected run's.
- **Third run, 2026-11-09T21:17:52Z** (`.venv/bin/python tools/vx_crosscheck.py`, 10 s, `iv_current` from the cached
  extract). Two changes to the runner, no change to a statistic: bar iv's caveat is now written from the events'
  timing status (`stats.vx_crosscheck.bar_iv_provisional`, D14), and `inputs.events_sha256` records the
  `events.parquet` that bar iv used (`1e5b88ee1b25f6d237ffbcf876578fc3a2f6e6d3c91d5da469bbbc946b72fbfc`, the committed
  file, unchanged against `HEAD`). Compared key by key with the second run: one key added (`inputs.events_sha256`), three
  strings changed (the two caveat texts and the per-name note of bar iv), no number changed.
- **Reproducibility:** `.venv/bin/python tools/vx_crosscheck.py --check` printed `ok: data/derived/vx_crosscheck.json
  equals a fresh computation (11 s)`.
- **Shape of the committed file:** 43,416 bytes, 1,143 numbers, longest list 6 items, largest object 17 keys;
  `aggregate_shape_problems` finds nothing.
- **Another agent worked in the same tree at the same time** (SEC EDGAR timing: `src/earnings_vol/events/{events,run,
  timing}.py`, `src/earnings_vol/ingest/edgar.py`, their tests, `docs/validation/edgar-*`). None of those files was
  edited here. Bar iv reads the committed `events.parquet` through `export.funnel`, which imports
  `events.calendar` and `events.eps` only (both unchanged); every committed `.parquet` equals `HEAD`.

**Decisions taken after the computation** (none changes a statistic or a verdict):

| # | Question | Decision |
|---|---|---|
| D13 | The app's source list (`tools/export_app_data.py`, the About page) | The VX\* row's `uses` now says the check ran on 2026-11-09, that the index values stay local and that the aggregates are in `data/derived/vx_crosscheck.json`; the attribution says the aggregates fall under Cboe's terms. **`committed` stays `False`:** `app/src/test/publicData.test.ts` and `tests/test_export_app_data.py` pin it, and the brief asked that the app's tests still pass. The About page's VX\* row therefore still reads "never" while the repository holds VX\*-derived aggregates (none in the app's data). Flipping it (and those two pins) is the owner's call. The screenshots `docs/images/app-about*.png` were not re-taken and still show the old row text. |
| D14 | Re-running bar iv after new timing labels | One command: `uv run --frozen python tools/vx_crosscheck.py` (then `tools/report_numbers.py`). Bar iv's caveat follows the timing status of its events, and `tools/report_numbers.py --check` fails when `inputs.events_sha256` differs from the committed `events.parquet`, so a new events table cannot sit next to an old bar iv. If the new labels contradict a sentence of the templates (for example "every one of these events still uses the calendar's timing label"), `report_numbers.py` names the sentence. |
| D15 | Interpretation in the report | The pre-registration gives verdicts, not readings. The report adds three readings, each labelled or checked by `vx_prose_check`: the bar-i intervals of four names and the pool hold 0.8; the forward and reverse slopes bracket 1, which is *consistent with* a slope of 1 plus daily noise, not proof of it (on the longer-gap changes the pooled pair still brackets 1, but for AAPL and AMZN the reciprocal is just under 1); ADR 0003's [0.8, 1.2] slope band is exploratory (D12). Whether the results meet ADR 0003's "How we'll know it's wrong" is put to the owner (report §9, question 9). **Corrected by §9.1:** the "bracket 1" reading is not a test (the pair always contains the ratio of the standard deviations) and was removed; the slope falsifier is met. |

## 4. Mutants

Script: [`probes/vx/mutants.py`](probes/vx/mutants.py), run on a scratch copy of the working tree with
`PYTHONPATH=<copy>/src`: each module first passes unmutated; then per mutant the module that pins it runs, must fail,
and the file is restored and its SHA-256 compared. Each module's header lists its mutants.

| Id | File | Mutant |
|---|---|---|
| V01 | `stats/vx_crosscheck.py` | `on_grid` drops a date that is not a session instead of refusing it |
| V02 | same | `shift` moves the wrong way |
| V03 | same | `matched_changes` keeps a value of 0 |
| V04 | same | `primary` takes gap ≤ 2 |
| V05 | same | `block_counts` circular (starts on [0, n), indices mod n) |
| V06 | same | `block_counts` does not cut the joined blocks to n |
| V07 | same | the slope as cov / var(y) |
| V08 | same | `weighted_median` takes the lower middle value |
| V09 | same | `spread_stats` measures each year against the weighted mean |
| V10 | same | `crush_ratio` as the mean of per-event ratios |
| V11 | same | bar i passes r = 0.8 itself |
| V12 | same | bar iv's range [0.8, 1.25] |
| V13 | same | `lag_finding` counts a tie with lag 0 as a finding |
| V14 | same | `iv_at_horizon` without the extrapolation limit |
| V15 | same | `identify_maturity` accepts a minimum on the longest horizon |
| V16 | same | `percentile_ci` keeps NaN replicates |
| V17 | same | `event_bootstrap_ratio` divides the other way round |
| V18 | same | bar iii fails a deviation of exactly 2.0 |
| V19 | same | `bar_iv_provisional` drops the caveat while some events are still `not_checked` |
| C01 | `ingest/cboe.py` | `url` accepts any symbol |
| C02 | same | a 404 is retried |
| C03 | same | one retry more than `MAX_RETRIES` |
| C04 | same | a duplicate date is dropped instead of refused |
| C05 | same | dates read day first |
| C06 | same | the User-Agent carries an address (built from `chr(64)` in the script, `example.invalid`) |
| L01 | `tools/licensing/check_data_files.py` | the aggregate JSON's shape not checked |
| L02 | same | the list-length limit removed |
| L03 | same | keys shaped like dates allowed |
| L04 | same | the number count not checked |
| R19 | `tools/report_numbers.py` | the bar-i prose claim always true |
| R20 | same | the bar-iv timing-label claim always true |
| R21 | same | the maturity claim always true |
| R22 | same | the VX primary-sample size not compared with `meta.json` |
| R23 | same | the VX `events_sha256` not compared with the committed `events.parquet` |
| R24a | same | the pooled part of the longer-gap slope claim always true |
| R24b | same | the per-name part of the longer-gap slope claim always true |

**Runs.** 2026-11-09T21:27:41Z: V01–V18, C01–C06, L01–L04, R19–R23 (before V19 and R24 existed): 34 of 34 killed, every
restore `sha256 ok=True`; each L, R and V19 mutant was then traced to the test meant to catch it. 21:31:18Z: a first
R24 (the pooled part of the claim made true) **survived**: the only test case for that claim edited a per-name value,
which the remaining conjuncts still caught. Fixed by splitting it into R24a and R24b, each with its own test case
(`VX secondary pooled`, `VX secondary name`). **Final run 21:32:02Z–21:32:29Z: 36 of 36 killed**, every restore
`sha256 ok=True`; R24a and R24b fail exactly their own case.

## 5. Results (from `data/derived/vx_crosscheck.json`)

Primary one-session changes, lag 0; 95% percentile intervals of the moving-block bootstrap (block 20, 10,000 draws,
seed 20261109; block 60 beside it).

| Name | n | Bar i: r [block 20] [block 60] | Bar i | Bar ii: slope [block 20] | 1 / reverse slope | Bar iii: median spread (vol points), largest yearly drift | Bar iii |
|---|---:|---|:-:|---|---:|---|:-:|
| AAPL (VXAPL) | 747 | 0.8578 [0.7944, 0.9065] [0.7857, 0.9101] | pass | 0.8345 [0.7764, 0.8816] | 1.134 | 3.133, 1.669 | pass |
| AMZN (VXAZN) | 745 | 0.8375 [0.7564, 0.8973] [0.7708, 0.8917] | pass | 0.8138 [0.7272, 0.8838] | 1.160 | 2.872, 0.948 | pass |
| GOOGL (VXGOG) | 735 | 0.7776 [0.6914, 0.8428] [0.6718, 0.8433] | **fail** | 0.7728 [0.6746, 0.8493] | 1.278 | 2.642, 0.523 | pass |
| GS (VXGS) | 740 | 0.8475 [0.7889, 0.8940] [0.7755, 0.8989] | pass | 0.7859 [0.7122, 0.8515] | 1.094 | 2.378, 1.727 | pass |
| IBM (VXIBM) | 730 | 0.6677 [0.5491, 0.7536] [0.5720, 0.7285] | **fail** | 0.6582 [0.5402, 0.7471] | 1.477 | 2.091, 1.141 | pass |
| Pooled | 3,697 | 0.7899 [0.7211, 0.8420] [0.7228, 0.8391] | **fail** | 0.7674 [0.6951, 0.8254] | 1.230 | (not pooled) | |

- **Bar ii:** no interval (block 20 or 60) holds 1. Exploratory ADR band [0.8, 1.2] (D12): AAPL and AMZN inside.
- **Bar iii:** VX above ours on 91.4% (IBM) to 99.1% (AAPL) of days.
- **Bar iv (provisional):** R = 0.9181, event bootstrap [0.8688, 0.9728], n = 34 (pooled), **pass**; mean Δln VX
  −0.2157, mean Δln ours −0.2349; all 34 events were `not_checked` when the check first ran; after EDGAR
  (2026-11-09) 32 are `confirmed` and 2 `not_checked` (GS next to Columbus Day), and the numbers did not change.
- **Alignment falsifier:** pooled r at lag −1 0.0354, lag 0 0.7899, lag +1 −0.0382: lag 0 is highest, no finding.
- **Secondary (gap > 1, no verdict):** pooled r 0.8791 [0.8425, 0.9089], n 2,351; slope 0.8005, 1 / reverse 1.0359
  [1.0042, 1.0749].
- **`volatility_history` (§5):** iv_current against VX, pooled r 0.8388 [0.7633, 0.8925] (per name AAPL 0.825, AMZN 0.8457, GOOGL 0.8839, GS 0.9356, IBM 0.7552); iv_current against ours 0.7862 [0.7093, 0.8435]; median
  spread VX − iv_current 2.30, iv_current − ours 0.264 vol points. **Maturity identified: 21 sessions** (an interior
  minimum; median |difference| 10: 1.900, 15: 0.974, 21: 0.624, 30: 1.330, 42: 2.001 vol points over 5,383 common
  days; 63 not measurable); change r at 21 sessions 0.7862 [0.7093, 0.8435]. Exploratory: each name alone also has
  its minimum at 21.

## 6. Files

- **New:** `src/earnings_vol/ingest/cboe.py`, `src/earnings_vol/stats/vx_crosscheck.py`, `tools/vx_crosscheck.py`,
  `tests/test_ingest_cboe.py`, `tests/test_vx_crosscheck.py`, `data/derived/vx_crosscheck.json`,
  `docs/report/templates/milestone5-vx.md`, `docs/validation/probes/vx/mutants.py`, this ledger. Local only:
  `$VOL_DATA_DIR/earnings-vol-study/raw/cboe/` (five CSVs, `fetch_log.json`) and
  `cache/vx_crosscheck/` (the `iv_current` extract and its manifest).
- **Changed (code and tests):** `tools/licensing/check_data_files.py` (rule 6 by content for the aggregate JSON),
  `tests/test_repo_data_files.py`, `tools/report_numbers.py` (VX numbers, prose claims, cross-checks),
  `tests/test_report_numbers.py`, `tools/export_app_data.py` and `tests/test_export_app_data.py` (the VX\* row's text
  and the attribution, D13).
- **Added by the review fixes (§9):** `tests/test_vx_crosscheck.py` (7 tests), `tests/test_report_numbers.py` (12
  cases and 2 tests), `tools/vx_crosscheck.py` and `src/earnings_vol/stats/vx_crosscheck.py` (the exploratory
  analyses), `docs/report/templates/*.md`, `docs/images/` (nine pictures re-taken), the PDF and DOCX.
- **Re-rendered or rebuilt by the tools:** `app/public/data/*.json` (`tools/export_app_data.py`: stamps, commit
  `6b8453f`, the two meta strings; no other value changed), `docs/report/earnings-vol-report.{md,pdf,docx,build.json}`,
  the number blocks of `README.md`, `docs/prfaq.md` and `docs/milestones/05-report-and-polish.md`.
- **Templates and docs (hand-written):** `docs/report/templates/{earnings-vol-report,readme-results,prfaq-measured}.md`;
  `docs/milestones/05-report-and-polish.md` §11; dated notes where a statement became false: `DATA.md`,
  `app/DATA.md`, `data/derived/README.md`, `data/derived/LICENSE`, `docs/prfaq.md` (How it works, item 3),
  `docs/architecture/data-model.md` (four places), `docs/adr/0003-iv-measures.md`, `docs/milestones/02-iv-measures.md`,
  `docs/milestones/03-event-study.md`.

## 7. Gates (2026-11-09, working tree)

| Gate | Printed |
|---|---|
| `uv run --frozen pytest -q -p no:cacheprovider` | `722 passed, 61 warnings in 65.43s` (650 before; 43 are this work's: 20 + 8 + 8 + 7; 29 are `tests/test_edgar_timing.py` of the other agent) |
| `cd app && npm run verify` | `Test Files  44 passed (44)`, `Tests  1894 passed (1894)`, coverage `99.78 / 99.42 / 99.39 / 99.88`, `built in 2.47s` |
| `uv run --frozen python tools/report_numbers.py --check` | `ok: 4 file(s) match 325 numbers from the committed data; the PDF and DOCX were built from this Markdown; look-ups: 453 left + 20 done = 473, as pinned (local events_report.json)` |
| `uv run --frozen python tools/licensing/check_data_files.py` (index, and a scratch copy with every file staged) | `clean: no raw vendor file and no oversized data file` (both) |
| `uv run --frozen python tools/build_notebooks.py --check` | `OK: 5 notebooks ... are in sync with src/` |
| `.venv/bin/python tools/vx_crosscheck.py --check` | `ok: data/derived/vx_crosscheck.json equals a fresh computation (11 s)` |
| Pre-registration hash | `94b246039e4cbd4d679e4d7e567ee7a2f35ad7ab333f182e6498096a653351d6`, unchanged |

## 8. Deviations and open items

- **Deviation (corrected):** the first run's bootstrap axis (§3). **Deviation (found by the adversarial review,
  2026-11-09, not corrected, recorded):** horizons were extrapolated by up to 10 sessions where the pre-registration
  said "interpolate" (§9.2). **Erratum:** the pre-registration's statement about the ADR's slope tolerance (§9.1). No bar
  moved; every analysis the plan does not name is labelled exploratory (the ADR slope band, the per-name maturity,
  the all-days maturity sensitivity, the change correlations at other horizons, and §9.3's analyses).
- **Bar iv is provisional** until the timing labels are checked; re-run with D14's command.
- **Owner decisions:** D13 (the About page's VX\* flag and the `app-about*.png` screenshots); whether bar i and bar ii
  meet ADR 0003's "How we'll know it's wrong" (report §9, question 9).
- **Not run:** an independent re-measurement (verifier) of the numbers added in §9. (An adversarial review of the
  original numbers ran on 2026-11-09; its findings are §9.)

## 9. Review fixes (2026-11-09, after the adversarial review)

An adversarial reviewer re-derived the cross-check and the EDGAR timing with its own code (an independent loader that
imports nothing from `earnings_vol`). Its findings, and what was done. Every number below that the report, the README
or the PR/FAQ prints comes from `data/derived/vx_crosscheck.json` through `tools/report_numbers.py`; the numbers
written here are copied from the same JSON and from the reviewer's scripts for the differential check (§9.5).

### 9.1 Erratum: bar ii and ADR 0003's own tolerance

**The pre-registration was wrong.** `vx-preregistration.md` §3 says for bar ii: "The ADR set no tolerance." That is
false. ADR 0003, "How we'll know it's wrong" (lines about 614-617), says the VX\* checks fail if the correlation is
below 0.8, the slope is outside [0.8, 1.2] or the day-0 crush ratio is outside [0.8, 1.2], "for most of the five
names". The pre-registration was **not edited** (the runner pins its SHA-256, `94b24603…`, unchanged); this entry is the
correction. Bar ii stays "descriptive" as a pre-registered *verdict* (no pass or fail was assigned), and D12's
"exploratory" label on the ADR band describes how the JSON recorded it at run time. Read against the ADR's own words:

| ADR 0003 falsifier | Names (or pooled) beyond it | Met? |
|---|---|---|
| correlation < 0.8 | GOOGL, IBM: 2 of 5 | **not met** (most would be 3) |
| slope outside [0.8, 1.2] | GOOGL, GS, IBM below 0.8: 3 of 5 | **met** (3 of 5 is "most") |
| day-0 crush ratio outside [0.8, 1.2] | pooled ratio 0.92, inside; per-name ratios not computed (D8) | **not met** (provisional with the timing labels) |

The report (§3.2, §7 item 8, §9 question 9), the README and the PR/FAQ now say this. The report also drops the sentence
that read the forward slope and the reciprocal of the reverse slope as "bracketing 1, consistent with daily noise":
**that is not a test.** The forward slope times the reverse slope is r², so [forward, 1 / reverse] always contains the
ratio of the two standard deviations, sd(Δln VX) / sd(Δln ours), here 0.93 to 0.99 by name (0.97 pooled). A pair that
brackets 1 is what any two series with similar spreads give, whatever the true slope. `prose_check` carries the new
sentences (R30-R33 below).

### 9.2 Deviation: horizons were extrapolated

The pre-registration §5 says the horizons are "interpolated"; the runner used `termstructure.interpolate`, which
**extrapolates** by up to `iv.cm30_max_extrap_sessions` = 10 sessions beyond the listed expiries (the same rule that
makes `cm30_blind_iv`). Counted from the JSON (days with a horizon value and an `iv_current`): **4,160 of the 5,413
values at 42 sessions lie beyond the last listed expiry** (4 more lie before the first), and **2,334 of the 5,964 at 10
sessions lie before the first** (4 beyond the last); at 21 sessions 26 of 5,981 (13 and 13), at 15 sessions 53 of 5,988,
at 30 sessions 66 of 5,973. The identified maturity (21 sessions) is the pre-registered result and is unchanged; almost all of its values
are interpolated, while the two ends of the grid (10 and 42 sessions) are largely extrapolated, so the comparison at
those two horizons is partly a comparison of extrapolations. The report says "interpolated or extrapolated by up to 10
sessions" and gives both counts.

### 9.3 The §5 check was not blind

ADR 0003:138 already held the hypothesis "about 30 days, annualised on calendar days" (its `iv_current` bullet) when
§5 was pre-registered, so the identification at 21 sessions was a test of a stated guess, not an open search. The
report says so. (The ADR's per-day `iv_current` values were removed from that bullet, §9.7.)

### 9.4 Exploratory analyses (each labelled "exploratory, not pre-registered")

New pure functions in `src/earnings_vol/stats/vx_crosscheck.py`, run by `tools/vx_crosscheck.py`, written to the
`exploratory` object of the JSON and to `volatility_history.maturity.{calendar_30,extrapolated}` (aggregates only), and
rendered in report §3.2 through the `vx.cal.*`, `vx.tf.*`, `vx.d0.*`, `vx.step*`, `vh.cal.*` and `vh.extrap.*` keys:

- **Snapshot calendar.** Share of primary changes that end on a Monday; in the Mon/Wed/Fri snapshot era (changes ending
  before the first session of September 2024, 2024-09-03) the count of those; the mean Monday Δln VX and Δln ours
  against the other days. (The reviewer called the era's Monday changes "Fri→Mon": 961 of the 1,005 start on a Friday,
  the other 44 start on a Thursday, the Friday between not being a session; the code counts changes ending on a Monday.)
- **Bar i on Tuesday-to-Friday changes**, per name and pooled, with block-20 intervals.
- **Bar i without the changes that end on a day 0**: every event of the five names in `events.parquet`, whatever its
  sample (43 such changes).
- **Non-overlapping k-session changes** (k = 1, 10, 21) from the first shared session of the daily era (2024-09-03):
  forward slope and 1 / reverse slope, pooled and per name, no intervals.
- **`iv_current` as 30 calendar days:** total variance linear in calendar days between the bracketing expiries (no
  extrapolation), IV = sqrt(365 w / 30); median |difference| and change correlation against the 21-session horizon.
  The pre-registered result stays 21 sessions on the session grid; the report reads `iv_current` as a 30-calendar-day IV
  that shows up as about 21 sessions.

The report's reading ("consistent with a clock effect that shrinks at longer horizons, except for IBM") is worded as
"consistent with", not proof; no interval is computed for the k-session slopes (n = 263 and 125 pooled, 25 to 53 per
name).

### 9.5 Differential check against the reviewer's numbers

The reviewer's scripts are `adv/{regime,horizon,ivcur,ivcur2,ivcur3,bar3,bar4,bars12,leak,timing}.py` in the session
scratchpad; they read the data with their own loader. Where my code computes the same quantity, the numbers:

| Quantity | Repo code | Reviewer | |
|---|---|---|---|
| primary changes ending on a Monday | 1,515 of 3,697 | 1,515 of 3,697 | match |
| in the Mon/Wed/Fri era, changes ending on a Monday | 1,005 of 1,111 | 1,005 of 1,111 | match |
| mean Monday Δln VX / Δln ours | +0.0173 / −0.0053 | +0.0173 / −0.0053 | match |
| bar i, Tuesday to Friday: GOOGL / pooled / IBM | 0.814 / 0.826 / 0.765 | 0.814 / 0.826 / 0.765 | match |
| changes ending on a day 0 | 43 | 43 | match |
| bar i without them: pooled / IBM | 0.747 / 0.558 | 0.747 / 0.558 | match |
| bar i without them: AMZN | 0.768 (0.76848) | 0.769 | **last digit differs**: the reviewer rounded 0.76848 to 0.7685 and again to 0.769 |
| k = 1 pooled slope / 1 / reverse | 0.742 / 1.168 | 0.742 / 1.168 | match |
| k = 10 pooled; IBM | 0.939 / 1.011; 0.854 / 0.978 | 0.939 / 1.011; 0.854 / 0.978 | match |
| k = 21 pooled; IBM | 0.954 / 0.990; 0.895 / 0.941 | 0.954 / 0.990; 0.895 / 0.941 | match |
| 42-session values beyond the last expiry | 4,160 of 5,413 | 4,160 of 5,413 | match (after splitting by side; counting both sides gives 4,164) |
| 10-session values before the first expiry | 2,334 of 5,964 | 2,334 of 5,964 | match (both sides: 2,338) |
| `iv_current` at 21 sessions, median \|diff\| (the pre-registered common days, n 5,383) | 0.624 | 0.624 | match |
| `iv_current` at 30 calendar days, median \|diff\| | 0.327 (all its 5,959 days) | 0.325 (4,679-day set) and 0.324 (5,920-day set) | **sets differ**: the reviewer's own loop on the 5,959 days gives 0.3266 |
| the same on the days with both horizons | 0.327 at 30 calendar days against 0.606 at 21 sessions | 0.325 against 0.604 (4,679 days) | same days in my run; 0.606 is the all-days sensitivity already in the JSON |
| change correlation at 30 calendar days, zero `iv_current` changes dropped | 0.8214 (n 3,544) | 0.821 (n 3,544) | match |
| change correlation at 21 sessions, zero changes dropped | 0.7884 (n 3,577) | 0.7915 (n 3,542) | **differs**: the reviewer's 21-session value is interpolation only; with the study's extrapolation (the actual `cm30_blind_iv`) the reviewer's own loop gives 0.7884, n 3,577 |
| the same without dropping zero changes (the report's pair) | 0.818 at 30 calendar days against 0.786 at 21 sessions | not computed | — |

### 9.6 Tests and mutants for the new code

`tests/test_vx_crosscheck.py` gained 7 tests with made-up values (module header: "E01-E09"). Each mutant was applied
by hand to `src/earnings_vol/stats/vx_crosscheck.py`, the module run (`pytest -q -x tests/test_vx_crosscheck.py`), seen
to fail, the file restored and its SHA-256 compared (all equal):

| Id | Mutant | Killed by |
|---|---|---|
| E01 | `weekdays_of` with `isoweekday()` | `test_weekdays_and_the_start_of_the_daily_era` |
| E02 | `era_start` counts the cut day as before the era (`<=`) | same |
| E03 | `snapshot_calendar` tests for a Friday | `test_snapshot_calendar_counts_monday_changes_and_their_means` |
| E04 | `keep_end_weekdays` keeps the complement | `test_keep_end_weekdays_and_drop_ends_at_filter_on_the_later_session` |
| E05 | `drop_ends_at` keeps the dropped ones | same |
| E06 | `stepped_changes` ignores k (overlapping steps) | `test_stepped_changes_are_non_overlapping_and_need_both_ends` |
| E07 | `ols_summary` returns the reverse slope, not its reciprocal | `test_ols_summary_against_numpy` |
| E08 | `iv_at_calendar_days` annualises with 252 | `test_iv_at_calendar_days_interpolates_total_variance_in_calendar_days` |
| E09 | `extrapolation_side` swaps the sides | `test_extrapolation_side` |

**9 of 9 killed.** In `tools/report_numbers.py`, each new `vx_prose_check` claim was made always true (the claim's
label excluded from the failure list) and the matching case of `test_disagreeing_or_contradicting_data_fail_the_check`
run, after its unmutated pass was confirmed: R30 ADR slope falsifier, R31 correlation falsifier, R32 crush-ratio
falsifier, R33 sd ratio, R34 GS's yearly step, R35 Monday calendar, R36 Tuesday-to-Friday r, R37 r without day-0
changes, R38 the stepped slopes, R39 the calendar-30 fit, R40 the extrapolation shares; R41 `events_timing` counting
open look-ups with no label outside every sample (`test_events_timing_counts_labels_and_the_open_events_without_one`);
R42 the stage comparison of the null-label count dropped
(`test_the_pinned_lookup_count_is_compared_with_a_local_stage_report`). **13 of 13 killed**, every restore `sha256 ok=True`.
Not mutated: the runner's `exploratory()` and `maturity_exploratory()` (covered by `--check` against the committed
JSON and by the reviewer's differential numbers in §9.5, not by a unit test).

### 9.7 Licensing and text fixes in the same pass

- `docs/validation/vx-egv/probes/ibm_roll_detail.out` (untracked) held per-day Cboe log changes; it was deleted.
  `probes/ibm_roll_detail.py` prints aggregates only if re-run; `channel-b.md` says why the file is gone, and its two
  sentences that quoted per-day values from it (six dates with jumps, one large day) were reduced to counts.
  ADR 0003's `iv_current` bullet no longer quotes two per-day `iv_current` values (it says `iv_current` sat about 1 vol
  point below our ATM IV for the ~29-day expiry on those dates). The two values had already been pushed with an
  earlier version of ADR 0003. By owner decision of 2026-11-09, the repository's history was rewritten (pushed
  2026-11-10) so that no commit holds them: every commit's copy of that bullet now carries the new wording, and every
  commit has a new ID ([map](history-rewrite-2026-11-09.md)). GitHub may still serve the old commits by their IDs
  until GitHub Support purges them. The deleted probe output was never committed. The
  reviewer's `leak.py` over every file git would add
  reports three files, each a coincidence of a date and an unrelated number (a coverage fraction 0.2732 next to a list
  of 1,245 missing dates in `vx-egv/probes/run_all.out`; a gap z-score 0.49 in milestone 1; a `00.000` fragment in
  `tests/test_edgar_timing.py`); none is a per-day VX\* or `iv_current` value.
- Report text: "922 events keep the calendar's label" became 922 `not_checked`, of which 892 keep the calendar's label and
  30 have none; of the 42 open look-ups, 19 keep a label and 23 have none (`lookups.left_labelled`,
  `lookups.left_unlabelled`; the 23 equals the EDGAR run's `by_reason` `null_label`, which `--check` compares when the
  local stage report exists); the limits now say the open look-ups of the daily sample (13) fall 8 / 5 / 0 across the move terciles.
- Bar iii's wording: "the spread does not drift between years" became "it passes the pre-registered rule, but the
  rule has little power: GS's yearly medians step from about 3.8-4.1 (2020-22) to about 1.7-2.1 (2023-26), a step of
  about 2.1 vol points, and GS passes only because its all-years median (2.38) sits between the two levels"
  (`vx.gs.*`, from the JSON's per-name yearly medians, which were already there).

### 9.8 Gates (2026-11-09, working tree, after these fixes)

| Gate | Printed |
|---|---|
| `uv run --frozen pytest -q` | `742 passed, 61 warnings in 152.23s (0:02:32)` (723 before this pass) |
| `cd app && npm run verify` | `Test Files  44 passed (44)`, `Tests  1894 passed (1894)`, coverage `99.78 / 99.42 / 99.39 / 99.88`, `built in 4.71s` |
| `uv run --frozen python tools/report_numbers.py --check` | `ok: 4 file(s) match 464 numbers from the committed data; the PDF and DOCX were built from this Markdown; look-ups: 42 left + 431 done = 473; …` |
| `uv run --frozen python tools/licensing/check_data_files.py` | `clean: no raw vendor file and no oversized data file` |
| `uv run --frozen python tools/vx_crosscheck.py --check` | `ok: data/derived/vx_crosscheck.json equals a fresh computation` (the JSON is 51,361 bytes, 1,351 numbers; `aggregate_shape_problems` finds nothing) |
| `uv run --frozen python tools/build_notebooks.py --check` | `OK: 5 notebooks … are in sync with src/` |
| `… tools/diagrams/build.py docs/architecture/specs --out docs/architecture/out --check` | `ok: 5 spec(s) up to date in docs/architecture/out` |
| Pre-registration hash | `94b246039e4cbd4d679e4d7e567ee7a2f35ad7ab333f182e6498096a653351d6`, unchanged (the runner checks it) |
