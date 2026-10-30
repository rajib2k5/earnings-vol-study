# Data model

- **Status:** milestone 4. `security`, `ticker_alias`, `session`, `market_daily`, `events`, `eps`, `timing_check`,
  `session_snapshot`, since milestone 2 `chain_expiry`, `iv_daily` and `event_iv`, and since milestone 3
  `event_window_obs`, `event_measures` and `results` are built (schema registry: `src/earnings_vol/schema.py`); since
  milestone 4 `event_measures`' regressor columns are filled and `results` holds the regressions;
  `event_measures_vx` is designed, not yet built. Revised 2026-10-28 after the milestone-0 reviews, and on 2026-10-29
  at milestones 1, 2, 3 and 4 (notes below).
- **Date:** 2026-10-28
- **Decisions behind it:** [ADR 0001](../adr/0001-overall-architecture.md) (layers, cache, licensing),
  [0002](../adr/0002-day-zero-convention.md) (day 0, timing), [0003](../adr/0003-iv-measures.md) (IV measures),
  [0004](../adr/0004-baseline-and-event-windows.md) (windows, abnormal IV), [0005](../adr/0005-statistical-test-suite.md) (tests)

This file is the **single source** for:

- the stored tables (§3);
- their keys and cardinalities (§5), from which the Mermaid ERD and the YAML ERD spec are drawn;
- the Python → app JSON contract (§4).

If code and this file disagree, one of them is a bug.

> **Revised after milestone-0 review** ([ledger](../validation/m0-methodology-ledger.md)). Changes follow the ADR
> revisions:
>
> - **Timing (ADR 0002 §3, ledger claim 2 and N10).**
>   - `events.timing_status` has new values, and `timing_source`, `edgar_accession` and `edgar_accepted_utc` are new
>     columns. The two `edgar_*` columns and the `edgar` value of `timing_source` exist **only if the owner approves
>     EDGAR**: ADR 0002's EDGAR rule is *Proposed: pending owner decision*.
>   - `date_suspect` no longer excludes an event.
>   - No label is set by prices alone. Under the default (no EDGAR: the press release, then the calendar label)
>     `timing_used` and `timing_status` stay class F; they would be class U under the proposed EDGAR rule.
> - **Statistics (ADR 0005, ledger 7b, 7d and claim 9).**
>   - `results.statistic` drops `kp_t` and `cluster_t`. It adds `twoway_date_t`, `twoway_season_t` (the primaries),
>     `cluster_date_t`, `cluster_season_t`, `rad_season_p`, `sa_twoway_season_t` and `kpp_t`.
>   - `results.n_clusters_firm` is new, for the two-way rows.
>   - The new `results.estimand` column labels each row as equal- or precision-weighted.
>   - `kp_ow_t` is no longer described as "not a published procedure"; it is a refinement of Kolari, Pape & Pynnönen
>     (2018).
> - **Units (ADR 0003 §c, ledger claim 13).** Every stored σ_d column is now stated as an annualised volatility, and
>   per-session variance is `sigma_d²/252`.
> - **Leftovers from earlier passes.** `iv_tercile` was used but never defined, and is removed. `beta_vix` is added to
>   the disclosure test's non-linear list (ledger N11). `stale_copy` already matched ADR 0002 §1, which now matches
>   it.

> **Revised after the milestone-0 delta review** ([delta ledger](../validation/m0-delta-ledger.md)). Changes follow
> ADR 0002's and ADR 0005's delta notes:
>
> - **`events.timing_status` (4b-ii).** `unverified` meant "no document found" here but "never looked up" in ADR 0002.
>   It is split into `no_document` and `not_checked` (§3.7). New members:
>   {`confirmed`,`corrected`,`inferred`,`date_corrected`,`no_document`,`not_checked`,`ambiguous`}.
> - **The default timing rule (4b-i, 4c).** Every event with D on or after 2024-09-11, and every NULL-label event, is
>   looked up by hand. The record is a new committed source file, `data/manual/press_release_checks.csv` (§1.3).
> - **The move terciles (N7).** `sample_funnel.by_move_tercile` used |`realized_ret_0`|, which is measured on the day
>   0 used and so puts mislabelled events in the low tercile by construction. It now uses the new label-free column
>   `event_measures.abs_move_cand_max` (§3.11). The new `events.gap_check_changed` (§3.7) feeds the funnel's new
>   `n_gap_check_changed` and the sensitivity analysis without gap-triggered changes (§4).
> - **`results` (N2).** A new invariant pins each row's reference distribution: `df` from the cluster counts, and
>   `p_value` from `stat` and `df` (§3.13, ADR 0005 §5 G1).

> **Milestone 1, 2026-10-29: what building the tables changed.**
>
> - **New columns.** `security.cik` (the SEC CIK from the same Wikipedia table, needed by the EDGAR client) and
>   `events.announce_date_used` (the documents' date for a `date_corrected` event; the event keeps its calendar
>   `event_id`). The press-release record gains `label` and `lookup_minutes` (§1.3).
> - **New table** `session_snapshot` (§3.6a): the first four columns of `iv_daily`, built early because the baseline
>   counts of the sample funnel need to know which sessions are observed.
> - **`timing_check` value columns are nullable** (§3.9): a non-session D has no BMO candidate, and a day missing
>   from Yahoo has no gap.
> - **A provisional exclusion reason**, `timing_not_checked` (§3.7): a NULL-label event on a session day that nobody
>   looked up. It exists only while the look-ups are incomplete (owner default of 2026-10-29, §6 item 7).
> - **Owner decisions recorded** in §6 (items 2, 3, 6, 7) with their dates.
> - **Contract 0.2.0** (§4): `meta` gains `sample`, `params`, `files`, `provenance`; `sample_funnel` is built, with
>   `by_move_tercile` and `evar_nonpositive` null until milestone 2 and a status string saying why.

> **Milestone 2, 2026-10-29: what building the IV tables changed.**
>
> - **Built:** `chain_expiry` (§3.5, local), `iv_daily` (§3.6, committed, 4.7 MB) and a new table `event_iv`
>   (§3.11a, committed): the IV columns of `event_measures`, built early by the measures layer, as `session_snapshot`
>   was at milestone 1. Milestone 3 folds them into `event_measures`. New relationship R24 (§5).
> - **`chain_expiry` nullability.** `forward` is null for `no_forward` and `stale` rows, and the ATM columns
>   (`strike_lo` … `w_atm`, `iv_atm`, `forward_dispersion`) are null unless an ATM was found; the table said
>   `float64` without null. `next_event_id` and `spans_next_event` are class F (they depend on day 0).
> - **Owner decision, 2026-10-29 (data).** Real Yahoo, Cboe and FRED values that the app or the docs need may be
>   committed. The registry names them per table (`Table.keep_restricted`); `store.write_derived` keeps exactly those
>   and drops every other class-R column. Milestone 2 keeps one: `timing_check.gap_verdict_yf`, for the funnel's
>   `share_gap_contradicts` (§2.1, §3.9). Every other class-R column stays local.
> - **Contract 0.3.0** (§4): `sample_funnel.by_move_tercile` and `evar_nonpositive` are filled, the funnel has a new
>   `iv_usable` step, and `iv_measures.json` is new.
> - **Not built:** `iv_daily.vendor_iv_current` is null everywhere: `volatility_history` was not extracted (it is
>   ADR 0003's third validation check only).

> **Revised after the milestone-2 review** ([ledger](../validation/m2-ledger.md)).
>
> - **Licence notices (claim 15a).** §1.3, §2 and §2.1 now say that two Yahoo-derived columns are committed under
>   Yahoo's terms, not CC BY-SA: `timing_check.gap_verdict_yf` and `security.in_universe`. `data/derived/LICENSE` and
>   `README.md` name every column derived from Yahoo, Cboe or FRED data. §6 item 8 is a new owner question: Cboe's
>   terms may restrict using Cboe data to verify other data, which bears on the VX\* validation.
> - **Method (ADR 0003's review note).** `spans_next_event` classes an expiry on an AMC announcement day as spanning
>   (§3.5); `ev_exp1` and `ev_exp2` are the two shortest *usable* spanning expiries (§3.6); `w_atm` is never extrapolated
>   from one side of the money (§3.5).
> - **Corrections.** `n_strikes_valid` counts strikes with a root, not strikes passing the quote filter (§3.5);
>   `chain_expiry` stays local because of its size, not because of FRED's rate (§3.5).

> **Milestone 3, 2026-10-29: what building the event study changed.**
>
> - **Built:** `event_window_obs` (§3.10, committed, 89,389 rows, 2.8 MB), `event_measures` (§3.11, committed, 1,353
>   rows) and `results` (§3.13, committed). `event_iv` and `session_snapshot` are kept: `event_measures` copies
>   `event_iv`'s IV columns, and nothing was dropped.
> - **Renamed:** `event_measures.beta_vix` is `beta_vix_cboe`, class R, local. The owner's data decision of 2026-10-29
>   allows VIX-derived values in the repository, and the brief for this milestone preferred keeping VIX-derived
>   *per-row* values local unless the app needs them. No view needs β per company, so it stays local with the other
>   market-adjusted per-row values (`e_abn_cboe`, `aliv_cboe`, the `*_cboe` measures, `s_abn_cboe`, `sa_*_cboe`).
>   Only aggregates of them are committed: the market-adjusted rows of `results` (class S) and the JSON built from
>   them. Every notice names them (`data/derived/LICENSE` and `README.md`, `DATA.md`, `app/DATA.md`, `meta.json`).
> - **The disclosure test of §2.1 is not built.** It belonged to the strict reading of the licence rule, which the
>   owner's decision of 2026-10-29 replaced (ADR 0001 §7). With the per-row values and β local, a reader cannot solve
>   the committed aggregates for Δ ln VIX without FRED's own `VIXCLS` series, which is the reason the test existed.
> - **Nullability:** `event_measures.implied_move_status` is nullable, as in `event_iv` (null without a pre session).
> - **New column:** `results.df_num`, the numerator degrees of freedom of a Wald row (ADR 0005 §5, G1's
>   reference-distribution check). The invariant of §3.13 runs on every write and read (`src/earnings_vol/invariants.py`).
> - **Left null at milestone 3:** the milestone-4 regressors of `event_measures` (`price_ref`, `surprise_scaled`,
>   `abs_surprise_scaled_w`, `sue_hist`, `sue_hist_n`, `realized_ret_0_yf`, `ln_mcap_yf`) and `vix_regime`;
>   `crush_two_session_*` (no event is `timing_ambiguous`); the VX\* columns of `event_window_obs` (`cboe5` is not
>   built: no VX\* file has been downloaded).
> - **Defaults taken (the owner can override):** in `mixed` and `coarse` a baseline change may span two sessions
>   across unobserved ones (ADR 0004 §4; `params.yaml` `windows.baseline_max_change_span`); the scale $s_i$ and the
>   standardised values are built for `daily` only (the Mon/Wed/Fri correction of ADR 0005 §1 is not built); in
>   `coarse` RUNUP is read at the pre session and PERSIST_h at the first usable of +h, +h−1, +h+1; β pools the clean
>   one-session baseline changes of all of a company's non-excluded events, in every sample, as ADR 0004 §2 says.
> - **Contract 0.4.0** (§4): `tests.json`, `event_paths.json`, `terrain.json` and `heatmap.json` are new; each carries
>   `lookups` and `caveats` (the timing labels are provisional).

> **Milestone 4, 2026-10-29: the drivers and implied against realised moves.**
>
> - **Filled:** the regressor columns of `event_measures` (§3.11): `price_ref`, `surprise_scaled`,
>   `abs_surprise_scaled_w`, `sue_hist`, `sue_hist_n`, `vix_regime` (committed) and `realized_ret_0_yf`, `ln_mcap_yf`
>   (class R, local). The rules the table left open are in §3.11 and the milestone-4 page's decisions table. Every
>   other committed table is byte-identical to milestone 3's.
> - **`results` (§3.13):** `family = regression` rows (62), with the statistics `twoway_date_t` / `cluster_date_t`
>   for a coefficient and `twoway_date_wald` / `cluster_date_wald` for H7's joint test; a new `adjustment` value
>   `none` (H7's moves are not market-adjusted); `family = descriptive` rows `holm_post_gate` (the Holm p over the
>   family without the hypotheses whose G1 primary failed, H1–H4, and H2's season cut over it: a sensitivity);
>   `validation` rows `g1_calibration_h7:*` and gate G1's H5–H7 rates. The invariant checks a Wald row's df from its
>   cluster counts too.
> - **Gate G1 failed H5–H7** (milestone-4 page §6.1): their statistics are liberal. *Fixed after the milestone-4
>   review (R1):* they stay in Holm's declared family H1–H7 as role `primary` with their real p-values and `p_holm`;
>   the first build made them exploratory and ran Holm over H1–H4 (ADR 0005 §5, dated note).
> - **Contract 0.5.0** (§4): `drivers.json` and `implied_vs_realised.json` are built, with the shapes below (they
>   differ from the milestone-0 sketch: `n_clusters_season` is dropped, each term carries its role, test and G1
>   note).

---

## 1. Source tables as found

Verified on **2026-10-28** through DoltHub's read-only SQL API (`/api/v1alpha1/post-no-preference/<repo>/master`) with
`SHOW CREATE TABLE`, `GROUP BY` counts and `LIMIT`-ed samples. The local clones were **not** touched. The DDL below is
exactly what the API returned. Collation clauses are omitted, and all tables are `utf8mb4_0900_bin`.

### 1.1 `post-no-preference/earnings` (CC BY-SA 4.0)

Tables: `balance_sheet_assets`, `balance_sheet_equity`, `balance_sheet_liabilities`, `cash_flow_statement`,
`earnings_calendar`, `eps_estimate`, `eps_history`, `income_statement`, `rank_score`, `sales_estimate`. The study uses
the first three below.

```sql
CREATE TABLE `earnings_calendar` (
  `act_symbol` varchar(64) NOT NULL,
  `date` date NOT NULL,
  `when` text,
  PRIMARY KEY (`act_symbol`,`date`)
);
CREATE TABLE `eps_history` (
  `act_symbol` varchar(64) NOT NULL,
  `period_end_date` date NOT NULL,
  `reported` decimal(16,2),
  `estimate` decimal(16,2),
  PRIMARY KEY (`act_symbol`,`period_end_date`)
);
CREATE TABLE `eps_estimate` (
  `date` date NOT NULL,
  `act_symbol` varchar(64) NOT NULL,
  `period` varchar(64) NOT NULL,
  `period_end_date` date,
  `consensus` decimal(7,2),
  `recent` decimal(7,2),
  `count` smallint,
  `high` decimal(7,2),
  `low` decimal(7,2),
  `year_ago` decimal(7,2),
  PRIMARY KEY (`date`,`act_symbol`,`period`)
);
```

| Fact | Value / evidence |
|---|---|
| `earnings_calendar` rows, range | 122,113 rows; `date` 2020-01-22 → **2026-12-04** (future rows are scheduled or projected dates) |
| `when` values | `'After market close'` 50,915; `'Before market open'` 39,487; NULL 31,711 (26.0%). No other value. |
| NULL `when`, 30 large caps | 9 of 784 rows (1.1%) |
| Wrong `when` (price-verified) | GOOGL 2024-10-29 and NFLX 2024-10-17 are labelled BMO but were AMC (ADR 0002) |
| Missing events | GS: no rows for Jul 2024 or Jan 2025, although `eps_history` has those periods. COST: 20 rows where 27 are expected. |
| Ticker changes | FB → META: calendar `FB` up to 2022-04-27, `META` from 2022-07-27 |
| `eps_history` range | 169,386 rows; `period_end_date` 2016-07-31 → 2026-09-30. **Normalised to month-ends**: day 31 for 87,028 rows, 30 for 81,486, 28 for 700, 29 for 172. AAPL's fiscal quarter ending 2025-12-27 is stored as 2025-12-31. |
| `eps_history` split basis | **Not split-adjusted.** NVDA: 6.12 for 2024-04-30, then 0.68 for 2024-07-31, after the 10:1 split. |
| `eps_history` duplicates | `FB` *and* `META` rows for 2021-12-31 and 2022-03-31 |
| `eps_estimate` | Weekly (Sunday) snapshots. `period` ∈ {`Current Quarter`, `Next Quarter`, `Current Year`, `Next Year`}. AAPL's last snapshot before the event, 2025-10-26 for period 2025-09-30, shows consensus 1.73 = `eps_history.estimate` 1.73. |

### 1.2 `post-no-preference/options` (CC BY-SA 4.0)

```sql
CREATE TABLE `option_chain` (
  `date` date NOT NULL,
  `act_symbol` varchar(64) NOT NULL,
  `expiration` date NOT NULL,
  `strike` decimal(7,2) NOT NULL,
  `call_put` varchar(64) NOT NULL,      -- 'Call' | 'Put'
  `bid` decimal(7,2),
  `ask` decimal(7,2),
  `vol` decimal(5,4),                   -- vendor IV, method undocumented
  `delta` decimal(5,4),
  `gamma` decimal(5,4),
  `theta` decimal(5,4),                 -- per calendar day
  `vega` decimal(5,4),                  -- per vol point
  `rho` decimal(5,4),                   -- per 1% rate
  PRIMARY KEY (`date`,`act_symbol`,`expiration`,`strike`,`call_put`)
);
CREATE TABLE `volatility_history` (
  `date` date NOT NULL,
  `act_symbol` varchar(64) NOT NULL,
  `hv_current` decimal(5,4), `hv_week_ago` decimal(5,4), `hv_month_ago` decimal(5,4),
  `hv_year_high` decimal(5,4), `hv_year_high_date` date,
  `hv_year_low` decimal(5,4),  `hv_year_low_date` date,
  `iv_current` decimal(5,4), `iv_week_ago` decimal(5,4), `iv_month_ago` decimal(5,4),
  `iv_year_high` decimal(5,4), `iv_year_high_date` date,
  `iv_year_low` decimal(5,4),  `iv_year_low_date` date,
  PRIMARY KEY (`date`,`act_symbol`)
);
```

| Fact | Value / evidence |
|---|---|
| Columns that do **not** exist | underlying price, open interest, volume, timestamp |
| Vendor greeks and IV | Vendor-computed with undocumented inputs. Call/put IV at the same strike differ by 0.1–0.3 vol points on normal days and up to 3.1 on an announcement day. Deep-ITM IVs are meaningless. |
| Expirations per snapshot | **3–4**, chosen by the vendor per date and identical across symbols. Front ≈ 10–16 calendar days, second ≈ front + 14, third ≈ monthly 39–60 days. The set can change entirely between consecutive sessions. |
| Strikes per expiry | ≈ 19–27, irregular. AAPL 2025-11-14 on 2025-10-30 had no 270 strike (listed on 10-29 and 10-31). |
| Snapshot frequency | Weekly on **Saturdays** 2019-02-09 → 2020-01-04; Mon/Wed/Fri 2020-01-06 → 2024-09-09; **daily from 2024-09-11**. Single sessions are sometimes missing (2024-11-12). |
| Non-session snapshots | Exist on holidays (2024-09-02 Labor Day) as **stale copies** of the previous session. 2025 has 259 snapshot dates against 250 NYSE sessions. |
| Snapshot time | Closing quotes of `date` (parity forward ≈ official close; no after-hours contamination on AAPL's AMC day). Commits at ≈ 06:35 UTC on D+1. ADR 0002 has the evidence. |
| Breadth | `volatility_history` ≈ 1,538 symbols per day (531 in 2019) |
| `volatility_history.iv_current` | Maturity undocumented; AAPL values are consistent with ≈ 30-day ATM, about 1 vol point lower. Unconfirmed. `iv_month_ago` is NULL in every row sampled. |
| Query hint | `date` leads both primary keys, so always filter on `date` first. A `COUNT(DISTINCT act_symbol)` over one full `option_chain` date timed out on the API. |

### 1.3 Other sources (never committed row by row)

| Source | Fields used | Licence posture |
|---|---|---|
| Yahoo Finance via `yfinance` | daily `Open, High, Low, Close, Volume, Dividends, Stock Splits`; shares outstanding | local only; columns suffixed `_yf`. *Since the owner's decision of 2026-10-29* two labels made from them are committed, under Yahoo's terms and not CC BY-SA: `timing_check.gap_verdict_yf` and `security.in_universe` (`data/derived/LICENSE`) |
| FRED `DTB3` | 3-month T-bill rate | US government data; may be committed |
| FRED `VIXCLS` | VIX close | **CBOE index**, so treated as CBOE data: suffix `_cboe`, never committed |
| CBOE VX\* CSVs | `VXAPL, VXAZN, VXGOG, VXGS, VXIBM` daily closes | never committed; suffix `_cboe` |
| Wikipedia "List of S&P 500 companies" (snapshot) | ticker, name, GICS sector and sub-industry | CC BY-SA 4.0, compatible; may be committed |
| SEC EDGAR submissions JSON (`data.sec.gov/submissions/CIK##########.json`, one per security) | `form`, `items`, `acceptanceDateTime` (UTC), `accessionNumber` of 8-K filings with Item 2.02 | **Accepted 2026-10-28; runs once the owner's contact string is set** (ADR 0002, milestone-1 note). The client (`src/earnings_vol/ingest/edgar.py`) refuses to run while the environment variable `SEC_EDGAR_USER_AGENT` is unset; it has no default or placeholder. No request was made at milestone 1. US-government public data; class U, may be committed. SEC's fair-access policy allows ≤ 10 requests/s and requires a real contact email in the User-Agent. Added after the review (ADR 0002 §3). |
| Company press releases (investor-relations pages, or the newswire copy they link to) | the release's date and time: its time stamp, else its own words, else the earnings-call time it announces | Read by hand, one event at a time (ADR 0002 §3, "The default rule"). Under the default (no EDGAR) they are the first timing source, looked up for every event with D on or after 2024-09-11 and every NULL-label event. *Revised after the delta review:* each look-up is recorded in a committed, hand-maintained file, `data/manual/press_release_checks.csv`, one row per look-up: `security_id`, `announce_date` (the calendar's D; with `security_id` it gives `event_id`), `found` (bool), `release_date`, `release_time_et` (`HH:MM` New York time, null if the release gives none), `basis` (what the stored time is: `time_stamp` the release's own time stamp, `announced_time` the release time the company announced beforehand; or, with no time, `release_text` or `call_time`; *`announced_time` added after the milestone-1 review*, and the parser refuses a time with any other basis), `label` (`BMO` or `AMC` as read; required, because a `release_text` or `call_time` reading has no time; when a time is given, the label must agree with it), `url`, `source_kind` (`company`, `newswire` or `aggregator`: what the URL is; an aggregator, a third-party re-host, is kept only where no company or newswire page was found; *added after the milestone-1 review*), `time_source` (the `https://` page on which the stored `release_time_et` was read: the `url` itself when it shows the time, else the page named; required with a time and only with one; *added after the milestone-1 delta review*), `checked_on`, `reread` (bool: a second, blind reading triggered by the gap), `lookup_minutes` (the measured time of the look-up, added at milestone 1), `note`. A re-read adds a row for the same event; the label changes only when a second and a third blind reading agree against the first (ADR 0002 §3). An event with no row is `not_checked`. The file holds dates, times, URLs and short notes in our own words, facts about the company, and no quoted text: class U, committed. Milestone 1 holds 20 rows (ADR 0002, milestone-1 note). |

---

## 2. Conventions

- **Types** are Arrow/Parquet: `string`, `date32`, `int16`, `int32`, `float64`, `bool`, `enum` (a dictionary-encoded
  string with the listed values only). Source `decimal` columns become `float64`, and NULL stays null.
- **Keys:** PK = primary key (unique, not null), FK = foreign key. Composite keys are listed in order.
- **Units:** IV is a decimal fraction, session-annualised (`0.2826` = 28.26%) unless the name says otherwise. Log
  quantities are natural-log points (`-0.123` ≈ −12.3%). Moves are decimal fractions of price. `tau_*` counts sessions
  unless the column ends in `_cal_days`.
  - **Every `sigma_d*` column is an annualised volatility**, $\sigma_{d,\text{ann}} = \sqrt{252\,\sigma_d^2}$, not a
    variance and not per session (ADR 0003 §c, "Units"). Wherever it is added to E or to a squared return it must be
    converted first: $\sigma_d^2 = \texttt{sigma\_d}^2/252$ per session.
  - `E` (`event_var`, `evar_*`) and `w_atm` are total variances in squared-log-return units.
  - `dsigma_d_*` is a log change and has no units.
- **Nulls:** a null number means "not computed". When the reason matters there is a sibling `*_status` enum.
  A column typed `…, null` may hold a real null; every other column is NOT NULL and the writer rejects a null in it.
  **An enum never has a `NULL` member.** "No value" is a real null. The `'<NULL>'` sentinel that carries SQL NULL
  through Dolt's CSV output (ADR 0001 §3) is turned into a real null by the extract parser and never reaches a table.
- **Flags:** `flags` is a `string` of `|`-separated codes, sorted, `''` if none (e.g. `fwd_dispersion|interpolated`).
- **Source suffixes:** `_yf` = from Yahoo, `_cboe` = from CBOE (including VIX). Any column with these suffixes is
  **dropped** before writing `data/derived/` or app JSON (ADR 0001 §7), except one a committed table names in
  `keep_restricted` (owner decision of 2026-10-29; at milestone 2 only `timing_check.gap_verdict_yf`). §2.1 says which
  columns need a suffix.
- **Committed?** marks whether the table goes to `data/derived/` (CC BY-SA 4.0, except the two Yahoo-derived columns
  `timing_check.gap_verdict_yf` and `security.in_universe`, which fall under Yahoo's terms; `data/derived/LICENSE`).
  Only a table marked committed may be there, with its committed columns (`tools/licensing/check_data_files.py`, rule
  6). Every table also exists in `$VOL_DATA_DIR/earnings-vol-study/cache/stage/<params_hash>/`.
- **FKs are checked in the stage cache.** Where the parent table is not committed (`chain_expiry`, the parent of
  `iv_daily`'s R12 FKs), the committed copy of the child keeps the column as plain information.

### 2.1 Licensing class of every column computed from Yahoo or CBOE data

ADR 0001 §7 states the rule. In short, each column has one of four classes:

| Class | Meaning | Committed? | Suffix |
|---|---|---|---|
| **U** | Lineage is DoltHub, FRED `DTB3`, Wikipedia, `exchange_calendars` or our own parameters only. Keys and counts of available observations are U even in a local-only table. | yes | none |
| **R** | A **numeric value** of a Yahoo or CBOE series for one date or one event, or any transform that keeps its magnitude (log, change, gap, z-score, residual). Also **any column that can be combined with committed columns to compute such values**, including a per-event statistic, if there are enough of them to solve for the dates involved (see `s_abn` below). | **never**, except a column a committed table names in `keep_restricted` (owner decision of 2026-10-29; at milestone 2 only `timing_check.gap_verdict_yf`, under Yahoo's terms) | `_yf` / `_cboe`, required |
| **S** | A statistic estimated from many restricted observations. It is committed only if the **export disclosure test** below shows that no single-date VIX change can be solved for from everything exported. Counting equations against unknowns is not enough. | yes, if the test passes | none; listed below |
| **F** | A **categorical label** derived with restricted data, from which no numeric value can be computed. It is either a fact that Yahoo prices only helped check (the announcement timing), or a coarse label with at most 5 levels (VIX tercile, threshold flag), or a one-time cross-sectional rank of firms. A finer label on a per-date series, such as a daily VIX rank, is R. | yes, by default (**owner decision**) | none; listed below |

The schema registry that mirrors §3 in code records each column's class. The writer refuses class R. A test asserts,
over **value columns** (keys excluded), that a column is class R exactly when it has a suffix. So a missing suffix and a
stray suffix both fail.

Columns with Yahoo or CBOE lineage are listed below. Every column not listed here is class U.

- A column that depends on Yahoo data only through day 0 is committable exactly when the timing label is. That covers
  almost every per-event column (`season`, `sample`, `event_var` at day −1, every window row, …).
- Under the default (ADR 0002 without EDGAR: the press release, then the calendar label) the label is class F. Every
  `daily` and `mixed` event is looked up, but a gap contradiction triggers a second reading, and in `coarse` it
  decides which events are looked up at all. The "stricter" reading below would then withhold all of those columns.
- The label would be class U under ADR 0002's EDGAR rule, which would leave those columns with no Yahoo lineage at
  all. That rule was accepted 2026-10-28 and is gated on the owner's contact string; until the string is set the
  default applies. *Caveat found in the delta review:* the EDGAR rule's own
  gap-triggered press-release check (ADR 0002 §3, job 1) would also put a Yahoo-derived bit into the status, so it
  is class U only if that check is dropped (ADR 0002, delta note item 9).

| Column(s) | Class | Committed | Why |
|---|---|---|---|
| `market_daily.vix_close_cboe`, `ln_vix_cboe` | R | no | the index itself |
| `timing_check` value columns, all `*_yf`, including `rel_day_max_outside_yf` | R | no | Yahoo gaps and their z-scores. The location of the largest outside gap is a detail of the evidence, not a fact about the company. |
| `events.timing_used`, and what follows from it: `day0_session`, `day_m1_session`, every `rel_day` | **F** under the default (no EDGAR); U only under ADR 0002's EDGAR rule once it runs | yes | When a company announced is a fact, taken from documents: the press release and the calendar label, plus the SEC 8-K acceptance time once EDGAR runs (accepted 2026-10-28, gated on the owner's contact string) (ADR 0002 §3). **Settled after the review (ledger N10):** no label is ever set by Yahoo gaps alone. A NULL label is filled only from a document, and without one the event is `ambiguous`. So the class-F "fact that Yahoo prices only helped check" rationale holds for every committed label. Under the EDGAR rule Yahoo would play no part at all. |
| `timing_check.gap_verdict_yf` | R | **yes, since 2026-10-29** (owner decision: real values the app needs may be committed) | The verdict of the Yahoo gap on the label in use. The sample funnel's `share_gap_contradicts` per move tercile is built from it. It is the only class-R column committed at milestone 2 (`schema.TIMING_CHECK.keep_restricted`). |
| `events.timing_status`, `timing_source`, `gap_check_changed`, `edgar_accession`, `edgar_accepted_utc` | `timing_status`, `timing_source` and `gap_check_changed` (added after the delta review) are **F** under the default (no EDGAR), because a Yahoo gap can trigger the second reading or the `coarse` look-up that sets them; all four are U under the EDGAR rule (with the caveat above) | yes | Under the default, which labels got a second reading, and which `coarse` events got a look-up, depends on a Yahoo gap trigger, so `timing_status` carries one Yahoo-derived bit per event (F, as before). Under the EDGAR rule they would record calendar-vs-document agreement only. The two `edgar_*` columns exist only once EDGAR runs (accepted 2026-10-28, gated on the owner's contact string). |
| `event_measures.vix_regime` | F | yes (owner decision) | It is a three-level bin of VIX on day −1, with the cut points taken over the sample. It reveals order, not values. |
| `security.in_universe` | F if the milestone-1 rule ranks by Yahoo market cap; U otherwise | yes; *since 2026-10-29* stated to fall under Yahoo's terms, not CC BY-SA (`data/derived/LICENSE`) | an in/out label of 499 firms on one date. *Revised after the milestone-1 review:* the rank behind it (`universe_rank`, 497 firms) is a per-row Yahoo-derived number, so it is not committed; it stays in the local `cache/universe.parquet` (§3.1). |
| `event_window_obs.e_abn_cboe`, `aliv_cboe` | R | no | Were they committed, $\Delta\ln\text{VIX}_t = (\texttt{d\_ln\_cm30} - \texttt{e\_abn\_cboe})/\beta_s$ would follow. Without $\beta_s$, cross-firm ratios still give the series up to a single scale factor. |
| `event_window_obs.ln_vx_cboe`, `e_abn_vx_cboe`; the `_cboe` columns of `event_measures_vx` | R | no | VX\* values and their transforms |
| `event_measures.runup_cboe`, `crush_cboe`, `persist_1_cboe`, `persist_5_cboe`, `persist_10_cboe`, `dsigma_d_cboe`, `crush_two_session_cboe`, `sa_*_cboe` | R | no | For example, `crush_cboe` $= \Delta x_0 - \beta_s\Delta m_0$, and $\Delta x_0$ follows from the committed `iv_daily.cm30_iv`, so $\Delta\ln\text{VIX}$ on every day-0 date could be recovered. |
| `event_measures.s_abn_cboe` | R | no | **Measured, 2026-10-28.** Each $s_i$ gives one quadratic equation in the unknown $\Delta m_t$ on that event's baseline dates. $\Delta x_t$, the baseline dates and $\beta_s$ are all committed. The adversarial reviewer simulated the coarse era (884 events, 657 unknown dates, simplified: fixed 23-change baselines, no exclusion holes, full precision), starting from committed data only. In 2 of 5 seeds it recovered every date to RMSE ≤ 1.7e-13; in the other 3 it reached correlation 0.984–0.994 with the true series. We re-ran seed 2 and got RMSE 1.69e-13. An earlier draft wrongly classed `s_abn` as S. |
| `event_measures.realized_ret_0_yf`, `ln_mcap_yf` | R | no | Yahoo close and market cap |
| `event_measures.beta_vix_cboe` (was `beta_vix`), `beta_n` | `beta_vix_cboe` R, `beta_n` F | `beta_n` only | *Milestone 3:* the 50 slopes are VIX-derived per-row values that no view needs, so they stay local (renamed with the suffix, class R). They are the known coefficients that would make every exported market-adjusted aggregate a *linear* equation in the VIX series. `beta_n` is a count. |
| `results` rows computed from R columns, including every `cboe5` row | S | yes, since milestone 3 (owner decision of 2026-10-29) | The numbers of a market-adjusted row (`estimate`, `se`, `stat`, `p_value`, `ci_lo`, `ci_hi`, `p_holm`, `q_bh`, `rbar`) are class S in the registry. The export rules below belonged to the strict reading and are not built (milestone-3 note). |

**Export rules for aggregates of class-R inputs.** These cover every `results` row, JSON series or cell and
regression coefficient computed from market-adjusted values, `_yf` values or VX\* values. Mean-adjusted aggregates
have no class-R input and are not restricted.

1. **Default export set.** Market-adjusted values are exported only for the subgroups `all` and `timing`, per measure,
   sample and rel_day, plus the named regressor coefficients of the ADR 0005 §3 models. Finer subgroups (`sector`,
   `season`, `vix_regime`, `security`) and the heatmaps are exported **mean-adjusted**. **Fixed-effect
   coefficients are never exported**: a firm fixed effect is a per-firm mean, and so is a sector effect for a
   one-firm sector. `cboe5` rows are exported only for `all`.
2. **Minimum cell:** ≥ 10 events on ≥ 10 distinct day-0 dates. **Secondary suppression:** no partition may have
   exactly one suppressed cell, because `all` minus the other cells would give it back. A suppressed cell is exported
   as `null` **without its `n`**.
3. **Disclosure test, run at every export.** It is a mechanical gate, not a judgement.
   - **Unknowns:** the ln VIX **levels** $m_t$ on every session any exported row touches. Changes are not the right
     unknowns: ALIV is a level minus a baseline mean.
   - **Rows:** one coefficient row for every exported number that is linear in $m$ given the committed columns: cell
     means, path means, scalar test estimates and regression coefficients. Each row is built from **that row's exact
     event set**. Path cells (events observed at $t$) and scalar rows (events with `eligible_*`) differ, and their
     differences can isolate single events.
   - **Assertions,** on the full-precision Parquet, with tolerance $10^{-8}$ on the projection onto the null space:
     - no single event's market-adjusted value (each event's ALIV at every exported rel_day, its crush, run-up,
       persistence and two-session crush) lies in the row space;
     - no difference $m_t - m_s$ lies in it, for **any** pair of dates. That is equivalent to "no two dates have equal
       null-space rows". It covers the 2-session Mon→Wed and Wed→Fri changes of the coarse era, which a
       single-session check cannot see.
   - **On failure** the export is refused. The remedy is either a common event set per subgroup, sample and measure
     family, or dropping rows until the test passes.
   - **Not covered:** standard errors, p-values, CIs, `rbar` and regression $R^2$ add *non-linear* equations.
     - So does the committed **`beta_vix`** itself. It is an OLS slope, $\sum\Delta x\,\Delta m/\sum(\Delta m)^2$
       over each security's clean baseline dates, so each of the 50 values is one non-linear equation in the
       unknown $\Delta m$. *Added after the review (ledger N11):* this list used to omit it, although the linear
       part of the test already uses `beta_vix` as a known coefficient.
     - At milestone 3 a non-linear solve (as in the `s_abn` simulation) is run once on the real export, with the 50
       `beta_vix` equations included.
     - If it recovers anything above, the fields concerned are dropped for market-adjusted rows. If `beta_vix` is
       what makes the difference, it moves to class R.
4. **Scope notes.** Every dummy-variable coefficient counts as a fixed effect and is never exported. That includes the
   VIX-tercile dummies of ADR 0005 §3's market-conditions variant, since each would be a regime mean of a
   market-adjusted outcome. The per-security VX\* statistics in `validation.vx[]` are validation, not `cboe5` event
   results. They are allowed per security, and they enter the disclosure test with the VX\* levels as extra unknowns.

**The default set is not yet proven (measured, 2026-10-28).** In the reviewer's simulation of exactly this default
set (`all`/BMO/AMC paths at −10…+10, plus crush, run-up and persist rows over their own eligibility sets; 78 rows,
rank 44; market-wide and per-security missing days), no VIX change was identified. But in 1 of 4 seeds **one event's
ALIV₀ was identified exactly**, because the path and scalar event sets differed. Our re-run of seed 3 reproduced it:
1 of 1,970 per-event values. That is why the test checks per-event values and arbitrary pairs.

**Why the minimum cell alone failed (measured, 2026-10-28).** The adversarial reviewer simulated the daily era (≈ 390
events, 50 securities, sectors of 10 down to 1 firm). Market-adjusted path cells by `all`/`timing`/`sector`/`season`
(plus `vix_regime` and an `iv_tercile` subgroup that has since been removed) × rel_day −10…+10, every one with ≥ 10 events on ≥ 10 dates, were combined by ordinary
least squares. This used committed `aliv_mean_adj`, `beta_vix`, `in_baseline` and the subgroup labels. It recovered
Δln VIX **exactly** on every day-0 date in seeds 1–3, and on 355–372 of 357–372 window dates. Our re-run of seed 1 gave
180 of 180 day-0 dates to 1.3e-14. Working from the 4-decimal JSON alone, the day-0 error was ≤ 2.8e-3, against a daily
sd of 0.07. The leak needs `season` *together with* `timing` and `sector`. Without `season` the series was not
identified (correlation 0.25–0.41). We ran the default set alone, `all` + `timing`, in the same simulation (63
equations, seeds 1–3). It identified **0** of 357–372 window dates and 0 of 180–189 day-0 dates, and the
least-squares estimate's correlation with the true series was 0.05–0.25. That simulation covers path means only, not
the regression coefficients or scalar test rows, so the disclosure test still has to pass on the real export.

**Owner decision (a licence-interpretation call, not settled here, and not legal advice).** The default above is
the strict reading for numeric values and the permissive reading for labels. It makes the primary, market-adjusted
per-event values local-only. A reader of `data/derived/` can still recompute them with the pipeline and their own
copy of FRED `VIXCLS`. The owner can read the rule differently in either direction:

1. **Looser:** a sparse sample of Δln VIX on announcement dates is not CBOE data. Then drop the `_cboe` suffix from
   the market-adjusted columns and commit them. This is a rename, cheap before milestone 3 builds these tables and
   expensive after.
2. **Stricter:** labels count as Yahoo/CBOE data too. Then `vix_regime` (and `security.in_universe`; the Yahoo-based
   rank itself is already local, §3.1) become R, and the timing label could not be committed either. That would leave nothing per event, since day 0 depends on
   the label. We see no workable version of the study under that reading for timing, so F is the default. Withholding
   `vix_regime` alone would be workable. The adversarial reviewer recommends doing so, since no view needs it per
   event.

The cost of the default is real. Subgroup results for run-up and persistence, where market adjustment matters most
(ADR 0004 §2), are published mean-adjusted only. Under the "looser" reading this cost disappears.

---

## 3. Derived tables

### 3.1 `security`: one row per company considered

| Column | Type | Key | Lineage / meaning |
|---|---|---|---|
| `security_id` | string | **PK** | stable id = ticker at study build (e.g. `META`); never reassigned |
| `name` | string | | Wikipedia S&P 500 list |
| `gics_sector` | enum (11 GICS sectors) | | Wikipedia S&P 500 list |
| `gics_sub_industry` | string | | Wikipedia S&P 500 list |
| `cik` | string, null | | *Added at milestone 1.* SEC Central Index Key, 10 digits, from the same Wikipedia table; the EDGAR client needs it. Class U. |
| `in_universe` | bool | | milestone-1 selection rule. Class F (§2.1). |
| `cboe_vx_index` | enum {`VXAPL`,`VXAZN`,`VXGOG`,`VXGS`,`VXIBM`}, null | | GOOGL is mapped to `VXGOG` (an index on GOOG) |

Rows: every S&P 500 constituent of the pinned Wikipedia revision, one share class per company (499 at milestone 1,
497 of them ranked); `in_universe` marks the 50 of the study (rule and survivorship bias:
`src/earnings_vol/ingest/universe.py`). The columns are listed in the code's order. Committed: yes.

*Revised after the milestone-1 review (claim 10).* The table used to hold `universe_rank`, the Yahoo market-cap rank
of 497 firms. A rank of ~500 firms on one date is a per-row Yahoo-derived number, which the strict reading of §2.1
makes class R, and nothing downstream reads it. It is no longer a column of `security`; the selection keeps it in the
local `cache/universe.parquet` only.

### 3.2 `ticker_alias`: ticker → security over time

| Column | Type | Key | Lineage |
|---|---|---|---|
| `ticker` | string | **PK** (1/2) | `act_symbol` as it appears in any source |
| `valid_from` | date32 | **PK** (2/2) | |
| `valid_to` | date32, null | | null = still valid |
| `security_id` | string | FK → `security` | |

Example rows: (`FB`, 2012-05-18, 2022-06-08, `META`), (`META`, 2022-06-09, null, `META`), (`UTX`, 2016-01-01,
2020-04-02, `RTX`), (`RTX`, 2020-04-03, null, `RTX`). A ticker with no known change is asserted valid from
2016-01-01, the start of the session table; history before that is not checked. Calendar rows resolve by ticker *and*
date; `eps_history` rows resolve by ticker alone, because DoltHub copied FB's quarters under META with dates before
META existed. Committed: yes.

### 3.3 `session`: NYSE trading calendar

| Column | Type | Key | Lineage |
|---|---|---|---|
| `session_date` | date32 | **PK** | `exchange_calendars` XNYS |
| `session_index` | int32 | unique | 0, 1, 2, … (rel_day arithmetic) |
| `is_half_day` | bool | | early close |
| `close_time_et` | string | | `16:00` or `13:00` |
| `era` | enum {`none`,`weekly`,`mwf`,`daily`} | | which snapshot regime covers this session (§1.2); `none` before 2019-02-09 and after the pinned data end |

Range: 2016-01-01 → 2027-12-31. That covers every EPS-period zone (`eps_history` starts 2016-07-31) and every
calendar row's window (rows run to 2026-12-04), so every session FK resolves. Committed: yes.

### 3.4 `market_daily`: market-wide inputs per session

| Column | Type | Key | Lineage |
|---|---|---|---|
| `session_date` | date32 | **PK**, FK → `session` | |
| `r_dtb3` | float64 | | FRED DTB3 (percent, discount basis): the last value on or before the session, since rates move slowly |
| `r_cont` | float64 | | DTB3 converted to continuous compounding |
| `vix_close_cboe` | float64, null | | FRED VIXCLS for that session only. It is null when FRED has no value and is never carried forward, so a missing VIX never becomes a fake zero change. |
| `ln_vix_cboe` | float64, null | | ln of the above |

Written by the `events` layer (module `market.py`, ADR 0001 §1), because `measures` needs `r_cont` and `panel` needs
VIX. Committed: no (it has `_cboe` columns). `r_*` may be split out and committed if useful.

### 3.5 `chain_expiry`: the atom, one row per (security, session, expiry) (ADR 0003 §0)

| Column | Type | Key | Lineage / meaning |
|---|---|---|---|
| `security_id` | string | **PK** (1/3); FK (1/2) → `iv_daily` (R11) | via `ticker_alias` from `option_chain.act_symbol` |
| `session_date` | date32 | **PK** (2/3); FK (2/2) → `iv_daily` (R11) | `as_of_session(option_chain.date)` |
| `expiration` | date32 | **PK** (3/3) | `option_chain.expiration` |
| `snapshot_date` | date32 | | `option_chain.date` |
| `tau_sessions` | int16 | | sessions in (session_date, expiration] |
| `tau_cal_days` | int16 | | calendar days |
| `df` | float64 | | $e^{-r\,\tau_{cal}/365}$, r = `market_daily.r_cont` |
| `forward` | float64, null | | median parity forward $K + (C_{mid}-P_{mid})/DF$ from `bid`, `ask`; null for `no_forward` and `stale` |
| `forward_n_strikes` | int16 | | strikes used for the forward (≤ 4) |
| `forward_dispersion` | float64, null | | (max − min) $F_K$ / F |
| `n_strikes_valid` | int16 | | strikes valid for the ATM step: the out-of-the-money quote passes the quote filter, \|ln(K/F)\| ≤ 0.5, the no-arbitrage bounds, and Black-76 has a root in [1e-8, 4] (`chain.py`; *corrected after the milestone-2 review*: this said "passing the quote filter") |
| `strike_lo`, `strike_hi` | float64, null | | ATM bracket strikes (also kept when the bracket was too wide and the quadratic was used) |
| `k_lo`, `k_hi` | float64, null | | ln(K/F) of the bracket strikes |
| `rel_spread_lo`, `rel_spread_hi` | float64, null | | (ask−bid)/mid of the OTM quotes at the bracket strikes |
| `w_atm` | float64, null | | ATM total implied variance (Black-76, OTM side, linear in k; or, for a bracket wider than 1.5 sd, the weighted quadratic, which needs a valid strike on each side of k = 0); null unless `status = ok` |
| `iv_atm` | float64, null | | $\sqrt{252\,w/\tau}$ |
| `atm_method` | enum {`bracket_linear`,`quadratic`,`none`} | | |
| `vendor_iv_atm` | float64, null | | `option_chain.vol` of the OTM quotes at the bracket strikes, interpolated linearly in k the same way (validation only; `bracket_linear` rows only) |
| `straddle_atm` | float64, null | | C+P mid at the bracket strikes interpolated linearly in k to 0 (both legs must pass the quote filter at both strikes). C+P has a kink at K = F, so this overstates the ATM straddle a little and `iv_straddle` sits above `iv_atm` (measured at milestone 2: 36,104 `straddle_gap` flags among 177,582 `ok` rows) |
| `iv_straddle` | float64, null | | IV inverted from `straddle_atm` |
| `next_event_id` | string, null | FK → `events` | the security's next event with day0 > session_date. For a `timing_ambiguous` event (null day 0), its **effective day 0** is next(D), the later candidate. Ambiguous events therefore still split expiries into clean and spanning. |
| `spans_next_event` | bool, null | | `as_of(expiration)` ≥ the first session on or after that event's announcement date D. That is day 0 for a BMO event or a release on a non-session day, and D itself, one session before day 0, for an AMC event or an event without a label: an expiry on D is exercised after the release (decision until 5:30 p.m. ET), so it is classed spanning, conservatively (ADR 0003 §b, *revised after the milestone-2 review*) |
| `status` | enum {`ok`,`no_atm`,`no_forward`,`stale`} | | `stale` = the session's snapshot is a `stale_repeat` (ADR 0002 §1). Its rows are kept so the decision can be audited, and no measure uses them. |
| `flags` | string | | `fwd_dispersion`, `few_strikes` (forward from fewer than 4 strikes), `iv_no_root`, `wide_bracket`, `no_bracket`, `straddle_gap` |

Keys: `(security_id, session_date)` is a composite FK to `iv_daily`'s primary key. Every `chain_expiry` row therefore
belongs to exactly one `iv_daily` row, and the security and session follow from it (R11). Cardinality: about 3.3 rows
per (security, session) that has a snapshot, and **none** when `iv_daily.snapshot_status = missing`. That gives
3.3 × ≈ 61,400 observed (security, session) pairs ≈ **200k rows** (arithmetic in §3.6). Committed: **no**. It can be
rebuilt from Dolt. *Measured at milestone 2:* 181,597 rows (3.14 per observed pair) in a 17.0 MB Parquet file. It
stays local (`cache/stage/<hash>/chain_expiry.parquet`) because of its size, above the 10 MB line. *Corrected after the
milestone-2 review:* this said "`df` is a FRED value, so it stays local"; FRED's `DTB3` may be committed (§1.3), and the
committed `iv_daily` is computed with the same discount factor.

### 3.6 `iv_daily`: one row per (security, session)

| Column | Type | Key | Lineage / meaning |
|---|---|---|---|
| `security_id` | string | **PK** (1/2), FK → `security` | |
| `session_date` | date32 | **PK** (2/2), FK → `session` | |
| `snapshot_date` | date32, null | | null if no snapshot |
| `snapshot_status` | enum {`ok`,`stale_repeat`,`missing`} | | ADR 0002 §1. `stale_copy` is not a session status. It is the reason a *duplicate* snapshot is dropped when another snapshot maps to the same session, and the session's status then comes from the snapshot that was kept. The stage manifest counts these drops. |
| `next_event_id` | string, null | FK → `events` | |
| `sessions_to_next_event` | int16, null | | day0 − session, in sessions |
| `prev_event_id` | string, null | FK → `events` | |
| `sessions_since_prev_event` | int16, null | | |
| `front_expiry` | date32, null | FK (3/3) → `chain_expiry`, R12a | shortest expiry with τ ≥ 5 among the `ok` rows |
| `front_tau` | int16, null | | |
| `front_atm_iv` | float64, null | | `chain_expiry.iv_atm` of `front_expiry` (rolls; display only) |
| `cm30_iv` | float64, null | | **event-aware** 21-session IV (ADR 0003 §b) |
| `cm30_method` | enum {`interp_clean`,`interp_spanning`,`extrap_clean`,`extrap_spanning`,`two_component`,`flat_sigma`,`none`} | | |
| `cm30_exp_lo`, `cm30_exp_hi` | date32, null | each FK (3/3) → `chain_expiry`, R12b / R12c | expiries used |
| `cm30_blind_iv` | float64, null | | event-blind interpolation (validation and leak measure) |
| `sigma_d_iv` | float64, null | | ex-event ("diffusive") IV: $\sigma_{d,\text{ann}} = \sqrt{252\,(w_2-w_1)/(\tau_2-\tau_1)}$, the forward variance between two same-class expiries expressed as an **annualised volatility**. Per-session variance = `sigma_d_iv²/252`. |
| `event_var` | float64, null | | **E, signed** (needs at least 2 usable spanning expiries) |
| `ev_exp1`, `ev_exp2` | date32, null | each FK (3/3) → `chain_expiry`, R12d / R12e | the two shortest **usable** (`ok`, τ ≥ 5) spanning expiries. A shorter spanning expiry without an ATM w (`no_atm`, `no_forward`) is skipped, and the next usable one is T2 (*documented after the milestone-2 review*; ADR 0003 §c, "Which expiries") |
| `ev_tau1`, `ev_tau2` | int16, null | | |
| `ev_w1`, `ev_w2` | float64, null | | their `w_atm` |
| `implied_move` | float64, null | | √E if E > 0 |
| `implied_abs_move` | float64, null | | $\sqrt{2/\pi}\sqrt E$ |
| `implied_abs_move_total` | float64, null | | $\sqrt{2/\pi}\sqrt{E+\texttt{sigma\_d\_iv}^2/252}$, i.e. with σ_d² per session (ADR 0003 §c) |
| `implied_move_status` | enum {`ok`,`nonpositive_event_variance`,`not_identified`} | | |
| `ts_slope` | float64, null | | ln(σ_T1/σ_T2) of the two shortest valid expiries |
| `forward_front` | float64, null | | `chain_expiry.forward` of the front expiry. For display only: the realised move and `price_ref` read `chain_expiry` directly, because they need the same expiry on two days and its `df`. |
| `vendor_iv_current` | float64, null | | `volatility_history.iv_current` (validation). *Milestone 2:* null everywhere; `volatility_history` is not extracted yet. |
| `flags` | string | | |

**The five "expiry used" FKs (R12a–e).** Each one is the triple (`security_id`, `session_date`, *role column*) →
`chain_expiry` (`security_id`, `session_date`, `expiration`). The first two columns are this row's own primary key, so
the referenced expiry is always one of this row's own `chain_expiry` children (R11). A null role column means no
reference (the FK is not checked). Invariants, tested at milestone 2:

- every non-null role column matches a `chain_expiry` row with `status = ok`;
- `front_expiry` is the shortest expiry with τ ≥ 5 among the `ok` rows;
- `ev_exp1` < `ev_exp2`, and both have `spans_next_event = true`;
- `cm30_exp_lo` and `cm30_exp_hi` depend on `cm30_method` (ADR 0003 §b):
  - `interp_*` / `extrap_*`: lo < hi, both in the named class;
  - `two_component`: lo = the longest clean expiry, hi = the spanning one;
  - `flat_sigma`: lo = hi = the single clean expiry;
  - `none`: both null.

Cardinality: 1 row per security per NYSE session in the coverage, **including sessions without a snapshot**
(`snapshot_status = missing`, measure columns null). The coverage is 2020-01-02 → 2026-10-26, which is **1,713
sessions** (counted with the NYSE holiday list; the daily-era part, 533 sessions, matches ADR 0004).

| | sessions per security | × 50 securities |
|---|---:|---:|
| all sessions in coverage (= rows) | 1,713 | **85,650** |
| Mon/Wed/Fri sessions in the coarse era, 2020-01-06 → 2024-09-09 | 695 | 34,750 |
| daily era, 2024-09-11 → 2026-10-26 | 533 | 26,650 |
| observed (= Mon/Wed/Fri + daily) | 1,228 | **61,400** |

The row count is an upper bound, because a security with shorter option coverage has fewer rows. The observed count
is approximate in both directions and is not counted here; milestone 1 counts it. Missing single days (such as
2024-11-12) lower it. Extra weekday snapshots (such as Tue 2020-06-09) raise it, as do non-session snapshots that map
to an otherwise unobserved session and pass the `stale_repeat` test.
Committed: yes. *Measured at milestone 2 (re-measured after the review's fixes):* 85,650 rows, 57,749 with an `ok`
snapshot; 57,087 of those have a `cm30_iv` and 19,601 an `event_var`. The Parquet file is 4.7 MB
(`data/derived/iv_daily.parquet`), under the 10 MB per-file limit of the owner's data decision.

How the columns are computed is ADR 0003 and `docs/milestones/02-iv-measures.md`. Choices the ADR left open and the
code fixes: the next event of a session is the first event (duplicate rows aside) whose effective day 0 is after it, and
the previous one the last on or before it; an expiry spans that event when the session it settles on,
`as_of(expiration)`, is on or after the first session on or after the announcement date (day 0, or the AMC
announcement day itself: §3.5, `spans_next_event`); only `ok` expiries with τ ≥ 5 enter the measures; `sigma_d_iv` is
taken from E's two spanning expiries, else from the two shortest clean ones; `implied_abs_move_total` needs E > 0 and a non-negative
forward variance (else null, with `negative_forward_variance` in `flags`).

### 3.6a `session_snapshot`: is a usable snapshot there? (milestone 1)

| Column | Type | Key | Lineage / meaning |
|---|---|---|---|
| `security_id` | string | **PK** (1/2), FK → `security` | via `ticker_alias` from `option_chain.act_symbol`, by date |
| `session_date` | date32 | **PK** (2/2), FK → `session` | |
| `snapshot_date` | date32, null | | the snapshot kept for the session; null if `missing` |
| `snapshot_status` | enum {`ok`,`stale_repeat`,`missing`} | | as `iv_daily.snapshot_status` (ADR 0002 §1). `stale_copy` drops are counted in the manifest. |

The first four columns of `iv_daily`, built at milestone 1 from the option-chain extract because the funnel's baseline
step needs the observed sessions. Same coverage as `iv_daily` (2020-01-02 → the data end, every session, observed or
not). At milestone 2 `iv_daily` takes these columns over (the funnel reads them there) and this table feeds
`iv_daily` (which snapshot belongs to which session); it can be dropped at milestone 3. Class U. Committed: yes.

### 3.7 `events`: one row per announcement

| Column | Type | Key | Lineage / meaning |
|---|---|---|---|
| `event_id` | string | **PK** | `"{security_id}:{announce_date}"`, e.g. `AAPL:2025-10-30` |
| `security_id` | string | FK → `security` | via `ticker_alias` |
| `ticker_at_event` | string | | `earnings_calendar.act_symbol` |
| `announce_date` | date32 | | `earnings_calendar.date` |
| `announce_date_used` | date32 | | *Added at milestone 1.* The announcement date day 0 is computed from: the documents' date for a `date_corrected` event (ADR 0002 §3), otherwise `announce_date`. `event_id` keeps the calendar date. Class F, like `timing_used`. |
| `timing_raw` | enum {`BMO`,`AMC`}, null | | `earnings_calendar.when`: `'Before market open'` → `BMO`, `'After market close'` → `AMC`, SQL NULL → null. Any other value is an error, since §1.1 found exactly these three. |
| `timing_used` | enum {`BMO`,`AMC`}, null | | After the ADR 0002 §3 check, from documents. Null for `ambiguous`, and for a NULL-label `not_checked` event outside every sample. For a non-session D the label does not affect day 0. A release timed inside the session (09:30–16:00) is stored as `BMO`, which gives the same day 0 (ADR 0002 §3, added after the delta review). Class F under the default (no EDGAR), U under the proposed EDGAR rule (§2.1). |
| `timing_status` | enum {`confirmed`,`corrected`,`inferred`,`date_corrected`,`no_document`,`not_checked`,`ambiguous`} | | ADR 0002 §3, revised after the review and again after the delta review. `confirmed`: a document agrees with the label. `corrected`: a document contradicts it, and its timing is used. `inferred`: no label, a document gives the timing. `date_corrected`: the documents put the announcement on another date, which is used (replaces `date_suspect`, which used to exclude the event). `no_document`: **looked up**, nothing found (no press release, and no 8-K if EDGAR is approved); the calendar label is kept. `not_checked`: **never looked up**; the calendar label is kept. `ambiguous`: looked up, nothing found, and the label is NULL. *Delta review (4b-ii):* `no_document` and `not_checked` replace `unverified`, which this table defined as "no document found" while ADR 0002 also gave it to every event nobody looked up. **Invariant** (tested at milestone 1; the `events` layer stops otherwise; the same statement as ADR 0002 §3): `not_checked` is allowed only for an event with `announce_date` before 2024-09-11, a non-NULL label and no gap trigger; any other `not_checked` event is a build error. Labelled events with `announce_date` in the 10 sessions before 2024-09-11 are looked up too, because a wrong label or date can move their day 0 into `mixed`. Same class as `timing_used`. |
| `timing_source` | enum {`edgar`,`press_release`,`calendar`}, null | | What decided `timing_used`: a hand-checked press release, the calendar label alone (`no_document`, `not_checked`), or the 8-K acceptance time. **`edgar` only once EDGAR runs** (accepted 2026-10-28, gated on the owner's contact string; ADR 0002, status note); under the default the values are `press_release` and `calendar`. Null for `ambiguous`. |
| `gap_check_changed` | bool | | *Added after the delta review.* True when a gap-triggered check changed the label: a second reading of the press release under the default, or a press-release check of the 8-K under the EDGAR rule (ADR 0002 §3, job 1). The sensitivity analysis of job 1 re-runs the pipeline with these changes undone (`params.timing_undo_gap_checks`). Class F, like `timing_status`. |
| `edgar_accession` | string, null | | **Only once EDGAR runs** (accepted 2026-10-28, gated on the owner's contact string; null for every event under the default). Accession number of the matched Item 2.02 8-K; null if none. Class U. |
| `edgar_accepted_utc` | string, null | | **Only once EDGAR runs** (null for every event under the default). Its `acceptanceDateTime` as EDGAR gives it (ISO 8601, UTC). The BMO/AMC reading converts it to New York time (ADR 0002 §3). Class U. |
| `day0_session` | date32, null | FK → `session` (R9a) | ADR 0002 §2 |
| `day_m1_session` | date32, null | FK → `session` (R9b) | |
| `fiscal_period_end` | date32, null | **not a key** | A denormalised copy of the matched `eps` row's `fiscal_period_end`. The link of record is `eps.event_id` (R13), and this copy must agree with it (invariant in §3.8). |
| `prev_event_id` | string, null | FK → `events.event_id` (**self-reference**, R18a) | The same security's previous event, ordered by `announce_date`. Null for the security's first event. |
| `next_event_id` | string, null | FK → `events.event_id` (**self-reference**, R18b) | The same security's next event. Null for its last event. |
| `gap_sessions_prev` | int16, null | | day0 − previous day0 in sessions; null if either day 0 is null |
| `orphan_nearby` | bool | | An `orphan` or `pre_calendar` EPS-period zone overlaps [−60, +10] (around next(D) when day 0 is null). Needs `eps.match_status` and `session` only, both from this same layer. |
| `season` | string | | calendar quarter of day 0 (of next(D) when day 0 is null), e.g. `2025Q1` |
| `sample` | enum {`daily`,`mixed`,`coarse`,`none`} | | A partition of events by day-0 date, from the ranges in ADR 0004 §5. It uses `day0_session`, or `announce_date` when day 0 is null, and never IV data. `none` = outside every range. |
| `exclusion_reason` | string, null | | The first failed **event-level** rule, in this order: `duplicate_row` (*added after the milestone-1 delta review:* a second calendar row of another event's release, i.e. a row of the same security within 14 days of a row with stronger timing evidence, ADR 0002 §3; it is set before the EPS match, which skips it, and it has no zone of its own in other events' baselines; milestone 1 has one, BRK.B 2024-11-01), `timing_ambiguous`, `timing_not_checked` (*milestone 1, provisional:* a NULL-label event on a session day that nobody looked up; the build invariant forbids it, once the look-ups are complete, for every event that can enter a sample; a NULL-label date scheduled after the data end keeps it), `outside_samples`. (`date_suspect` was removed after the review. A doubtful date is checked against documents and then kept, either confirmed or corrected; ADR 0002 §3.) It is computed last in the layer, because it needs `sample`. Every event still gets an `event_measures` row, and a non-null reason makes every `eligible_*` false. Only events with a null reason get `event_window_obs` rows. A `timing_ambiguous` event has null `day0_session` and `day_m1_session`. It still gets the two-session robustness crush (ADR 0002 §2), computed from `iv_daily` at prev(D) and next(D), and for other events' baselines its zone is [−21, +10] around **both** candidate days (ADR 0004 §1). Wherever another table needs its day 0 (`season`, `orphan_nearby`, `iv_daily`/`chain_expiry.next_event_id`), it uses the effective day 0, next(D). Data-availability rules live in `event_measures.ineligible_reason`. |
| `calendar_commit` | string | | Dolt commit hash read |

The prev/next chain covers **every** event of the security, excluded ones included, because baseline exclusion needs
every other event's zone (ADR 0004 §1). Orphan EPS periods are not events and are not in the chain. Invariants, tested
at milestone 1:

- `next.prev_event_id = event_id` whenever `next_event_id` is set, and the reverse;
- both ends of each link have the same `security_id`;
- `prev.announce_date < announce_date` for every link (this also rules out cycles);
- each security **with at least one event** has exactly one event with a null `prev_event_id` and one with a null
  `next_event_id`;
- following `next_event_id` from that first event visits every event of the security, in `announce_date` order.

Without the ordering check, a correct chain A→B plus a detached loop C⇄D would pass the other checks. The traversal
check tests the whole chain directly.

Committed: yes. Per-measure eligibility moved to `event_measures` (§3.11), because it needs observed snapshots and
clean baseline counts, which `events` cannot know (ADR 0001 §1).

### 3.8 `eps`: one row per (security, fiscal period)

| Column | Type | Key | Lineage / meaning |
|---|---|---|---|
| `security_id` | string | **PK** (1/2), FK → `security` | |
| `fiscal_period_end` | date32 | **PK** (2/2) | `eps_history.period_end_date` (month-end normalised) |
| `event_id` | string, null | FK → `events`, **unique**; **the link of record** (R13) | *Revised after the milestone-1 review and again after its delta review.* The announcement of this period, among the security's events (not `duplicate_row`, §3.7) from **14 days after the first day of the period end's month** to **100 days after the period end** (the stored end is month-end normalised, so the true end is no earlier than the first of the month; `params.yaml` `eps_match.window_start: month_start+14`). Periods and events are paired one-to-one and in order, with the smallest total distance (|lag| days per link, 101 per period left without an event), so a period whose own report is missing becomes `orphan`, and it cannot take the next quarter's report unless that report comes at least 74 days after its own period end (no link in the data is longer than 59 days; ADR 0002 §3, "When a link can still move"; `events/eps.py`). An orphan is a genuine missing event, and its zone rightly contaminates nearby baselines. Null iff `match_status` ∈ {`orphan`, `pre_calendar`}. |
| `match_status` | enum {`matched`,`orphan`,`pre_calendar`,`ticker_conflict`} | | `pre_calendar` = unmatched, its window starts before the calendar does (2020-01-22), and the window holds no event of the security. This can only happen to periods ending on or before 2020-01-31. `orphan` = unmatched and not `pre_calendar`; a period whose window holds an event that went to another period is always an orphan. Both kinds of zone are removed from baselines (ADR 0004 §1), but only `orphan` counts towards ADR 0002's orphan-rate check. `ticker_conflict` = two tickers report the period with different values (ADR 0002 §4). It keeps its `event_id`. |
| `lag_days` | int16, null | | announce_date − fiscal_period_end; null iff `event_id` is null. Negative when a report comes before the stored month-end (Costco's May quarters, −1 to −6 days at milestone 1). |
| `reported` | float64, null | | `eps_history.reported` (as reported, **not split-adjusted**). Null when the source is null, and for `ticker_conflict`, where neither value is chosen. |
| `estimate` | float64, null | | `eps_history.estimate`, with the same null rule |
| `surprise` | float64, null | | reported − estimate; null if either is null |
| `consensus`, `consensus_high`, `consensus_low` | float64, null | | `eps_estimate` row with period = `Current Quarter`, same period_end, last `date` ≤ day −1 |
| `consensus_count` | int16, null | | `eps_estimate.count` |
| `consensus_date` | date32, null | | `eps_estimate.date` used |
| `surprise_disp` | float64, null | | (reported − consensus)/(high − low) if count ≥ 3 and high > low |

Price-scaled surprises (`price_ref`, `surprise_scaled`, `abs_surprise_scaled_w`, `sue_hist`, `sue_hist_n`) moved to
`event_measures` (§3.11). They need the day −1 option forward, which the `measures` layer produces after `eps` is
written (ADR 0001 §1). How many source EPS values are null is not measured yet; milestone 1 counts them.

**One link, one direction.** `eps.event_id → events.event_id` is the only FK between the two tables (R13).
`events.fiscal_period_end` is a convenience copy. Invariants, tested at milestone 1 (`tests/test_events_eps_link.py`
on the committed tables, `tests/test_eps.py` on fixtures):

1. every non-null `eps.event_id` exists in `events` and appears at most once;
2. `eps.security_id = events.security_id` for every linked pair;
3. `events.fiscal_period_end` equals the linked row's `eps.fiscal_period_end`, and it is null iff no `eps` row links
   to the event;
4. `eps.event_id` is null iff `match_status` ∈ {`orphan`, `pre_calendar`}, and `lag_days` is null iff `eps.event_id`
   is null;
5. every linked event lies in its period's window (from 14 days after the first day of the period end's month to
   the period end + 100 days), and the links of a security keep their order: a later period never has an earlier
   event; no `duplicate_row` event is linked, and each group of calendar rows within 14 days keeps one row;
6. `ticker_conflict` rows have null `reported` and `estimate`;
7. on fixtures shaped like the milestone-1 review's cases, each period links to its own quarter: Costco (a report
   2 days before the stored month-end; the February report missing, so February is the orphan and May keeps its
   event), Oracle (reports 9 days after a month-end), Berkshire (a February Q4 release stays with December, also on
   1 March); a missing report gives an orphan, never the next quarter's event, even where shifting a chain would
   gain a link; slow reporters (lags 65–66, the delta review's S1 and S2) keep their own quarters; and a link moves
   to the next period only from 74 days late.

The tests must be seen to fail when one event's `fiscal_period_end` is corrupted, when the window's lower bound
moves off 14 days after the first of the month, when the upper bound becomes exclusive, when the assignment takes the
first event in the window, when it maximises the number of links before the distance, when the cost of an unlinked
period changes from 101, and when a duplicate row is matched (*revised after the milestone-1 review*, which found the
first window, 10 to 100 days after the period end, wrong for month-end normalised periods, and after its delta
review, which found a duplicate row linked and long lags shifted).

Cardinality: `events` 0..1 — 0..1 `eps`. An orphan or pre-calendar period has no event, and an event can lack an EPS
row. Committed: yes.

### 3.9 `timing_check`: the price-gap diagnostic (local only)

Since the review, this table is a **diagnostic**. It never sets `timing_used` and never excludes an event (ADR 0002
§3). It feeds two things. The first is the hand-check list of ADR 0002 §3's default rule: in `daily` and `mixed`,
events whose gap contradicts the press-release label or whose nearby flag fires get a second reading; in `coarse`, a
labelled event is looked up only on such a trigger. The second is the sample funnel's `share_gap_contradicts` by
tercile of `event_measures.abs_move_cand_max` (revised after the delta review; the terciles used to be of |r₀|).

| Column | Type | Key | Lineage |
|---|---|---|---|
| `event_id` | string | **PK**, FK → `events` | |
| `gap_bmo_yf`, `gap_amc_yf` | float64, null | | market-adjusted overnight log gap at each candidate day, with the dividend added back on its ex-date; null without a candidate (a non-session D has no BMO candidate) or without Yahoo data. *Milestone 1:* every value column of this table is nullable for the same reasons, and the scale needs at least 10 gaps in [−60, −22] around as_of(D). |
| `gap_scale_yf` | float64, null | | median \|gap\| over [−60, −22] |
| `z_bmo_yf`, `z_amc_yf` | float64, null | | |
| `z_max_outside_yf` | float64, null | | largest z in [D−3, D+4] excluding the candidates |
| `rel_day_max_outside_yf` | int16, null | | where that largest z is. Yahoo-derived evidence detail, class R (§2.1). |
| `gap_verdict_yf` | enum {`supports`,`contradicts`,`quiet`}, null | | the gap's verdict on `timing_used`, with ADR 0002 §3's thresholds (4, 3×). Class R. |
| `outside_flag_yf` | bool, null | | a session in [D−3, D+4], other than the candidates, with z ≥ 6 and ≥ 3× the candidates' maximum. Class R. |

Committed: **only `event_id` and `gap_verdict_yf`** since milestone 2 (owner decision of 2026-10-29; the registry's
`keep_restricted`). All its value columns are class R; the key `event_id` is U. Before milestone 2 only the resulting
`events.timing_used` / `timing_status` (class F under the default, U only under ADR 0002's EDGAR rule once it runs;
§2.1) were committed.

### 3.10 `event_window_obs`: one row per (event, rel_day), from rel_day −60 to +10

| Column | Type | Key | Lineage / meaning |
|---|---|---|---|
| `event_id` | string | **PK** (1/2), FK → `events` | |
| `rel_day` | int16 | **PK** (2/2) | −60 … +10 sessions from day 0 |
| `session_date` | date32 | FK → `session` | |
| `observed` | bool | | `iv_daily.snapshot_status = ok` |
| `in_window` | bool | | rel_day ∈ [−10, +10] |
| `in_baseline` | bool | | ADR 0004 §1 |
| `baseline_excluded_reason` | enum {`other_event_zone`,`orphan_zone`,`not_observed`,`null_iv`,`outside`}, null | | `orphan_zone` covers both `orphan` and `pre_calendar` periods. `not_observed` covers `missing` and `stale_repeat` sessions. |
| `cm30_iv` | float64, null | | `iv_daily.cm30_iv` |
| `ln_cm30` | float64, null | | |
| `d_ln_cm30` | float64, null | | one-session change; null if the previous session is unobserved |
| `e_abn_cboe` | float64, null | | $\Delta x - \beta_s \Delta m$ (ADR 0004 §2). Class R: local only. |
| `aliv_cboe` | float64, null | | Market-adjusted abnormal log IV (the primary definition). Class R: local only. |
| `aliv_mean_adj` | float64, null | | mean-adjusted abnormal log IV (committed) |
| `aiv_level` | float64, null | | abnormal IV in vol points, mean-adjusted (display) |
| `front_fixed_iv` | float64, null | | IV of the event's T1\* expiry (from `chain_expiry`) |
| `front_fixed_interpolated` | bool | | T1\* not listed that day |
| `sigma_d_iv` | float64, null | | `iv_daily.sigma_d_iv` |
| `event_var` | float64, null | | `iv_daily.event_var` when `next_event_id` = this event |
| `ln_vx_cboe` | float64, null | | ln of the VX\* index of the event's security, for the `cboe5` sample only; null for other securities. Class R. |
| `e_abn_vx_cboe` | float64, null | | the same abnormal change computed on `ln_vx_cboe`. Class R. |

*Milestone 3 (built).* One row per (event, rel_day) for every event with a null `exclusion_reason` (1,259 events, 89,389
rows). `usable` in the code means an ok snapshot **and** a `cm30_iv` (ADR 0004 §1 rules 3 and 4). `d_ln_cm30` and
`e_abn_cboe` are null at rel_day −60 (the previous session is outside the window) and wherever either end is not
usable. `aliv_cboe`, `aliv_mean_adj` and `aiv_level` are null for an event whose baseline fails the minimum.
`front_fixed_iv` is filled inside the event window [−10, +10] only, while T1\* has at least 5 sessions to go; it is
interpolated (never extrapolated) when T1\* is not listed that day (`front_fixed_interpolated`). `ln_vx_cboe` and
`e_abn_vx_cboe` are null (`cboe5` is not built).

Cardinality: `events` 1 — 0..71 `event_window_obs`. Committed: yes, without the `_cboe` columns. **Licensing:** the
committed per-row values are mean-adjusted. The market-adjusted `e_abn_cboe` and `aliv_cboe` would let a reader recover
Δln VIX on every window date from `d_ln_cm30` and `beta_vix` (§2.1). Relaxing this is an owner decision (§2.1).
Mean-adjusted run-up and persistence per event are `aliv_mean_adj` at rel_day −1 and +h.

### 3.11 `event_measures`: one row per event, the tested quantities (ADR 0004 §3, ADR 0005)

| Column | Type | Key | Meaning |
|---|---|---|---|
| `event_id` | string | **PK**, FK → `events` (1:1) | |
| `eligible_crush`, `eligible_runup`, `eligible_persist_10` | bool | | Per-measure eligibility. It needs `events.exclusion_reason` null, the observed sessions the measure uses (ADR 0002 §5, ADR 0004 §4) and a baseline of at least 20 sessions and 15 changes (ADR 0004 §1). `persist_10` also needs day +10 ≤ the data end. |
| `ineligible_reason` | string | | `\|`-separated `measure:reason` codes (flags convention), e.g. `crush:missing_0\|persist_10:beyond_data_end`; `''` if all are eligible. Reasons: `event_excluded`, `missing_m1`, `missing_0`, `missing_target`, `short_baseline`, `beyond_data_end`. |
| `baseline_n`, `baseline_n_changes` | int16 | | clean sessions and clean one-session changes |
| `baseline_mean_ln_iv`, `baseline_mean_iv` | float64, null | | μ_i and the level mean |
| `beta_vix_cboe` | float64, null | | β_s (pooled per security). *Milestone 3:* class R, local (was `beta_vix`, class S; see the milestone-3 note). |
| `beta_n` | int32 | | changes used for β_s (0 for an excluded event). Class F. |
| `s_abn_cboe` | float64, null | | s_i, the sd of the market-adjusted baseline changes. **Class R**: enough of them can be solved for Δln VIX (§2.1). |
| `runup_cboe`, `crush_cboe`, `persist_1_cboe`, `persist_5_cboe`, `persist_10_cboe`, `dsigma_d_cboe` | float64, null | | **The primary tested quantities**: market-adjusted, log (ADR 0004 §3). Class R: local only. `stats` reads them from the stage cache. |
| `crush_mean_adj`, `dsigma_d_mean_adj` | float64, null | | Mean-adjusted (committed). Run-up and persistence have no column here: they are `event_window_obs.aliv_mean_adj` at −1 and +h. |
| `crush_two_session_cboe`, `crush_two_session_mean_adj` | float64, null | | $x(\text{next}(D)) - x(\text{prev}(D))$, market- and mean-adjusted, for `timing_ambiguous` events only (the ADR 0002 §2 robustness crush); null otherwise, or when either end is unobserved. `results.measure = crush_two_session`. At about 1% of events its market-adjusted cell never reaches 10 events, so only the mean-adjusted version is exported. |
| `crush_front_fixed` | float64, null | | ln σ_T1\*(0) − ln σ_T1\*(−1), from `chain_expiry` |
| `crush_span_sessions` | int16, null | | 1 daily; 1–3 coarse |
| `sa_crush_cboe`, `sa_runup_cboe`, `sa_persist_1_cboe`, `sa_persist_5_cboe`, `sa_persist_10_cboe`, `sa_dsigma_d_cboe` | float64, null | | Standardised $A_i/(s_i\sqrt{a^\top\hat R a})$. Class R. |
| `evar_m1` | float64, null | | E at day −1 (signed) |
| `evar_m2` | float64, null | | E at day −2 (robustness for wide announcement-day quotes, ADR 0003 §c) |
| `implied_move_m1`, `implied_abs_move_total_m1` | float64, null | | |
| `implied_move_status` | enum (as `iv_daily`), null | | null without a pre session (as `event_iv`) |
| `sigma_d_m1`, `cm30_m1`, `ts_slope_m1` | float64, null | | regressors. `sigma_d_m1` and `cm30_m1` are annualised volatilities. H7's regressor is `evar_m1 + sigma_d_m1²/252` (ADR 0005 §3). |
| `price_ref` | float64, null | | As-of, unadjusted parity spot on day −1: `chain_expiry.forward × chain_expiry.df` of `iv_daily.front_expiry` on day −1. Dividends inside about 2 weeks are ignored. (Moved from `eps`.) |
| `surprise_scaled` | float64, null | | `eps.surprise / price_ref`; null without a linked `eps` row |
| `abs_surprise_scaled_w` | float64, null | | \|surprise_scaled\| winsorised at 1%/99% over the events with the same `events.sample` |
| `sue_hist` | float64, null | | (surprise_scaled − mean of the security's previous 8) / sd of the previous 8, ordered by day 0 |
| `sue_hist_n` | int16, null | | number of prior quarters used (≥ 4 required) |
| `realized_ret_0` | float64, null | | ln(F_0/F_−1) + carry, same expiry on both days, from `chain_expiry` (ADR 0003 §e) |
| `abs_move_cand_max` | float64, null | | *Added after the delta review (ledger N7).* The larger absolute parity-forward move over the two candidate day-0 sessions: max(\|r(prev(D) → D)\|, \|r(D → next(D))\|), each computed like `realized_ret_0` (same expiry on both days, plus carry). For a non-session D, the one move \|r(prev(D) → next(D))\|. Each end is the nearest observed snapshot, so in `coarse` a move can span more than one session. It does not depend on the timing label, and it exists for `ambiguous` events too. The sample funnel's move terciles use it (ADR 0002 §3, job 3); \|`realized_ret_0`\| is measured on the day 0 used and would put mislabelled events in the low tercile. Null when an end is unobserved. Class U. |
| `realized_ret_0_yf` | float64, null | | Yahoo close-to-close (cross-check). Class R. |
| `abs_ret_over_implied` | float64, null | | \|realized_ret_0\| / implied_abs_move_total_m1, E > 0 only |
| `vix_regime` | enum {`low`,`mid`,`high`}, null | | VIX tercile at day −1 over the sample. Class F, a coarse label (§2.1); committing it is part of the owner decision. |
| `ln_mcap_yf` | float64, null | | Class R |

Committed: yes, without the `_yf` and `_cboe` columns (§2.1). Every event has a row (1:1), and an excluded event has
all `eligible_*` false.

*Milestone 4 (built): the regressor columns* (`src/earnings_vol/panel/regressors.py`, run by `panel/run.py`):

- `price_ref` is read at **`event_iv.pre_session`** (day −1 in `daily`, the session of E, σ_d and SLOPE): forward × df
  of that session's `iv_daily.front_expiry` (an `ok` `chain_expiry` row with a forward). 1,200 events.
- `surprise_scaled` = `eps.surprise` / `price_ref` over the linked `eps` row (R13); 1,198 events.
- `abs_surprise_scaled_w`: winsorised at numpy's linear 1% / 99% quantiles over **every event of the same
  `events.sample` with a `surprise_scaled`** (excluded events included); params `drivers.surprise_winsor`.
- `sue_hist`: the previous quarters are the security's earlier events **with a `surprise_scaled`**, ordered by the
  effective day 0; the last `drivers.sue_prev` (8) of them, at least `sue_min_prev` (4); sd with ddof 1; an sd of 0
  gives null. `sue_hist_n` is the count used, null exactly when `sue_hist` is. 998 events.
- `vix_regime`: terciles (numpy's 1/3 and 2/3 quantiles) of `market_daily.vix_close_cboe` at `day_m1_session` within
  each `events.sample`, over its events with a VIX there; a value on a cut point goes to the lower bin; `none`: null.
  1,259 events (daily: 127 low, 118 mid, 121 high).
- `realized_ret_0_yf` = ln((close_post + dividend_post) / close_pre) from the local Yahoo file, pre and post as
  `event_iv`'s. A cross-check: on the 336 primary events with `realized_ret_0` the median absolute difference is 16.9 bp.
- `ln_mcap_yf` = ln(market cap on `universe.rank_date`) + ln(close(day −1) / last close in the file), split-adjusted
  closes: the share count of the rank date is assumed (no share-count history is held).

*Milestone 3 (built).* The rules of `src/earnings_vol/panel/window.py`:

- **pre / post** are `event_iv`'s. In `daily` and `mixed` the crush needs exactly day −1 and day 0 (each usable); in
  `coarse` the nearest observed within one session (ADR 0004 §4), and RUNUP is read at pre, PERSIST_h at the first usable
  of +h, +h−1, +h+1 inside the window.
- **Eligibility**, the first failing rule per measure: `event_excluded`, `beyond_data_end` (persist_10 only),
  `missing_m1` / `missing_0` / `missing_target`, `short_baseline`. `baseline_n_changes` counts one-session changes in
  `daily` and changes of up to 2 sessions across unobserved sessions only in `mixed` and `coarse`.
- **Measured:** eligible CRUSH 347 daily (exactly the funnel's last step), 33 mixed, 110 coarse; RUNUP 356 / 34 / 117;
  PERSIST_10 329 / 35 / 127. Daily ineligibility: CRUSH missing_0 9, missing_m1 4, short_baseline 6; PERSIST_10
  beyond_data_end 18, missing_target 12, short_baseline 7. Only 127 of 845 coarse events keep a baseline: Mon/Wed/Fri
  data gives at most about 23 sessions in [−60, −22], so the 20-session minimum removes most of them.
- `s_abn_cboe` and every `sa_*_cboe` are filled for `daily` events only; R-hat is pooled over each measure's own
  eligible daily events (ADR 0005 §1). For ΔSIGMA_D the scale is the sd of the abnormal baseline changes of
  ln `sigma_d_iv` (the code's `sigma_d_baseline`).
- `persist_1_cboe` and `persist_5_cboe` (exploratory) need a passing baseline and their target, like PERSIST_10. The `panel` layer reads `iv_daily`, `chain_expiry`, `events`, `eps`, `security`, `session`,
`market_daily` and the local Yahoo and VX\* extracts. Its order has no cycle:

1. window rows with their class-U columns (`observed`, `in_baseline`, `ln_cm30`, `d_ln_cm30`, …);
2. β per security from the pooled clean baseline changes (stored in `event_measures.beta_vix`);
3. the market-adjusted window columns (`e_abn_cboe`, `aliv_cboe`);
4. the rest of `event_measures`;
5. the same steps on ln VX\*, giving `beta_vix_vx_cboe`, `e_abn_vx_cboe` and `event_measures_vx`.

Each table is written once, at the end.

### 3.11a `event_iv`: the IV columns of `event_measures`, built early (milestone 2)

One row per event (1:1 with `events`, R24), written by the measures layer after `iv_daily`
(`src/earnings_vol/measures/event_iv.py`). The names are those of §3.11, so milestone 3 can take the columns over.

| Column | Type | Key | Meaning |
|---|---|---|---|
| `event_id` | string | **PK**, FK → `events` (R24) | |
| `pre_session`, `post_session` | date32, null | | the two ends of the crush: the last observed session at day −1 or day −2, the first at day 0 or +1 (ADR 0004 §4); null without a day 0 or an end |
| `crush_span_sessions` | int16, null | | sessions from `pre_session` to `post_session` (§3.11) |
| `evar_m1` | float64, null | | E at `pre_session` (signed), only when that session's next event is this event |
| `evar_m2` | float64, null | | E at day −2 itself |
| `implied_move_m1`, `implied_abs_move_total_m1`, `implied_move_status`, `sigma_d_m1`, `cm30_m1`, `ts_slope_m1` | | | `iv_daily` at `pre_session` (§3.11); `implied_move_status` is null without a pre session |
| `cm30_0` | float64, null | | `iv_daily.cm30_iv` at `post_session` |
| `crush_mean_adj` | float64, null | | ln `cm30_0` − ln `cm30_m1`: the mean adjustment of a one-step change is nothing (ADR 0004 §2) |
| `dsigma_d_mean_adj` | float64, null | | ½ ln(σ_d²(post)/σ_d²(pre)), the forward variance between E's two expiries on both days |
| `front_fixed_expiry` | date32, null | | T1\*: the shortest `ok` expiry at pre with τ ≥ 5 at day 0 (ADR 0003 §a) |
| `front_fixed_iv_m1`, `front_fixed_iv_0` | float64, null | | its IV at pre and post; at post interpolated in τ (never extrapolated) among that day's usable expiries of T1\*'s class when T1\* is not listed |
| `front_fixed_interpolated` | bool | | T1\* was not listed at post |
| `crush_front_fixed` | float64, null | | ln `front_fixed_iv_0` − ln `front_fixed_iv_m1` |
| `realized_ret_0` | float64, null | | ADR 0003 §e: ln(F_post/F_pre) + r Δcal/365 on the shortest expiry with a forward on both days and τ ≥ 5 at post; r of the pre session |
| `abs_ret_over_implied` | float64, null | | \|`realized_ret_0`\| / `implied_abs_move_total_m1` (E > 0 only) |
| `abs_move_cand_max` | float64, null | | §3.11: the larger parity-forward move over the two candidate day-0 sessions of `announce_date_used`; each start the last observed session at its target or one before, each end the first observed at its target or one after; null if a leg cannot be measured. Class U |
| `flags` | string | | `pre_is_m2`, `post_is_p1`, `next_event_differs` |

Class F apart from `abs_move_cand_max` (U): every other column depends on day 0. Committed: yes (174 KB at
milestone 2). Not built here, because they need the baseline or the market adjustment: everything else of §3.11.

### 3.12 `event_measures_vx`: the `cboe5` sample on the CBOE VX\* series (local only)

| Column | Type | Key | Meaning |
|---|---|---|---|
| `event_id` | string | **PK**, FK → `events` (R21) | An event is a member when its security has `security.cboe_vx_index` set, `events.exclusion_reason` is null, VX\* is observed on day −1 and day 0, and at least 20 clean VX\* baseline sessions and 15 changes remain after the same exclusions as ADR 0004 §1 (other events' zones, orphan and pre-calendar zones). |
| `vx_index` | enum {`VXAPL`,`VXAZN`,`VXGOG`,`VXGS`,`VXIBM`} | | class U (an identifier) |
| `baseline_n_changes` | int16 | | class U (a count of available observations) |
| `beta_vix_vx_cboe`, `s_abn_vx_cboe` | float64, null | | as in §3.11, on ln VX\* |
| `runup_vx_cboe`, `crush_vx_cboe`, `persist_10_vx_cboe` | float64, null | | as in §3.11, on ln VX\* |
| `sa_runup_vx_cboe`, `sa_crush_vx_cboe`, `sa_persist_10_vx_cboe` | float64, null | | standardised |

Cardinality: `events` 1 — 0..1 `event_measures_vx`; having a row means the event is in `cboe5`. Committed: **no**
(every `_cboe` column is class R). Because membership needs a null `exclusion_reason`, `cboe5` inherits the day-0
ranges of `daily`, `mixed` and `coarse`, so it starts around 2020-04-01 (ADR 0004 §5). It also needs at least 15 clean
VX\* baseline changes, like ADR 0004 §1. It is written by `panel` with the same pure functions as `event_measures`,
applied to `event_window_obs.ln_vx_cboe`. Only `results` rows with `sample = cboe5` and `subgroup_key = all` leave the
machine (§2.1 export rules).

### 3.13 `results`: every aggregate the report or app shows

| Column | Type | Key | Meaning |
|---|---|---|---|
| `result_id` | string | **PK** | SHA-1 of the key columns below |
| `family` | enum {`event_test`,`regression`,`validation`,`descriptive`} | | |
| `hypothesis` | enum {`H1`…`H7`}, null | | primary family (ADR 0005 §4) |
| `role` | enum {`primary`,`robustness`,`exploratory`} | | |
| `measure` | string | | e.g. `crush_cm30`, `runup`, `persist_10`, `dsigma_d`, `evar`, `aliv_path`, `crush_two_session` |
| `statistic` | string | | *Milestone 4:* a regression coefficient row has `twoway_date_t` (two-way day-0 date × firm) or `cluster_date_t` (one-way date), with `model_id` and `term`; H7's joint test has `twoway_date_wald` or `cluster_date_wald`; a model's R² is a row with `r2`; the Holm sensitivity rows have `holm`. Before milestone 4: `twoway_date_t`, `twoway_season_t`, `cluster_date_t`, `cluster_season_t`, `rad_season_p`, `sa_twoway_season_t`, `bmp_t`, `kp_ow_t`, `kpp_t`, `patell_z`, `gen_sign_z`, `rank_t`, `ols_coef`, `wald`, `corr`, `mean` (ADR 0005 §2, §4). **Primary:** `twoway_date_t` (two-way day-0 date × firm, CR1 components, $t_{\min(G)-1}$) for H1 and H4; `twoway_season_t` (two-way merged season × firm) for H2 and H3. If seasons are unbalanced (more than 1.5×), the H2/H3 p-value comes from `rad_season_p` (ADR 0005 §2b). `cluster_date_t` and `cluster_season_t` are the one-way forms, kept as robustness. `rad_season_p` is a full-enumeration Rademacher randomisation p by season; it cannot be below $2/2^G$. **`kpp_t`** = Kolari, Pape & Pynnönen (2018)'s average-overlap adjustment of BMP. It replaces `kp_t` (KP 2010, r̄ over all pairs), which was deleted after the review. **`kp_ow_t`** = the per-pair form of the same adjustment (Pynnönen 2022, eq. 25), a refinement, not a new procedure. Both are reported for one-session measures only. `cs_t` is no longer reported as a test. The Webb bootstrap (`wcr_season_p` in a first draft) was deleted after the second review, because it was more liberal than CR1. |
| `estimand` | enum {`equal_weighted`,`precision_weighted`}, null | | What the row's estimate and test are about. `precision_weighted` for `bmp_t`, `kp_ow_t`, `kpp_t`, `sa_twoway_season_t` and `patell_z` (the mean of standardised values, ADR 0005 §2d). `equal_weighted` for the primary rows, `cluster_*_t` and `rad_season_p`. Null for `gen_sign_z` and `rank_t`, which test a sign share and a mean rank rather than a mean, and for regressions and validation. Added after the review (ledger 7b). |
| `rel_day` | int16, null | | for path or point results |
| `sample` | enum {`daily`,`mixed`,`coarse`,`cboe5`} | | The analysis sample. `daily`, `mixed` and `coarse` are the values of `events.sample` other than `none`; `none` never appears here, because those events are not tested. `cboe5` is **not** a value of `events.sample`, because it is not a partition by date. It is an overlay: the events with an `event_measures_vx` row, drawn from all three date samples, measured on VX\* instead of `cm30_iv`. An event can count in both `daily` and `cboe5`. |
| `subgroup_key` | string | | `all`, `timing`, `sector`, `vix_regime`, `season`, `security`. (`iv_tercile` was listed here and in §2.1 but never defined by any table; it was removed after the review.) Rows with class-R inputs (`adjustment = market`, and every `cboe5` row) are exported only under the §2.1 export rules: market-adjusted for `all` and `timing` only, `cboe5` for `all` only, with minimum cells, secondary suppression and the disclosure test. Every other subgroup is exported mean-adjusted. |
| `subgroup_value` | string | | e.g. `AMC`, `Information Technology` |
| `adjustment` | enum {`market`,`mean`,`none`} | | `none` (milestone 4): H7's rows, whose realised and implied moves are not adjusted for the market |
| `model_id`, `term` | string, null | | regressions only |
| `n` | int32 | | events (or observations) |
| `n_clusters` | int32, null | | G of the row's time clustering: distinct day-0 dates, or season clusters after merging seasons with fewer than 10 events (ADR 0005 §2b) |
| `n_clusters_firm` | int32, null | | G of the firm dimension, for two-way rows (`twoway_*`, `sa_twoway_season_t`, two-way regressions); null otherwise. The critical value uses $\min$(`n_clusters`, `n_clusters_firm`) − 1 degrees of freedom. |
| `df` | float64, null | | |
| `df_num` | float64, null | | *Added at milestone 3.* The numerator degrees of freedom of a `wald` row; null otherwise (ADR 0005 §5). |
| `estimate`, `se`, `stat`, `p_value`, `ci_lo`, `ci_hi` | float64, null | | |
| `p_holm` | float64, null | | primary rows; and the season-cut counterfactual row, where it is the Holm p with that cut's p |
| `q_bh` | float64, null | | exploratory rows only |
| `rbar` | float64, null | | the correlation term of the row's KP variant: the clamped per-pair $\bar r$ for `kp_ow_t`; $\bar\nu\hat{\bar\rho}$ for `kpp_t` |
| `params_hash`, `code_commit` | string | | provenance |

No foreign keys; keyed by names. Committed: yes.

*Milestone 3 (built).* `result_id` hashes the key columns except `role`, so a role change after gate G1 keeps the id.
The rows:

- `family = event_test`: H1–H4 (daily, market-adjusted) with every statistic of ADR 0005 §4; the mean-adjusted twin of
  each primary (role robustness); exploratory rows (PERSIST_1 and _5, the front-expiry crush, BMO and AMC subgroups,
  the `mixed` and `coarse` samples) with BH q-values within each sample. `mixed` is one season, so its ramps have a
  `mean` row only. A primary whose G1 gate failed would have role `exploratory` and no `p_holm`.
  *Added after the milestone-3 review:* a robustness row whose statistic gate G1's calibrated design rejects above the
  band's top (6.30% at 2,000 replications) keeps `estimate`, `se` and `stat`, and has `p_value`, `ci_lo` and `ci_hi`
  null (ADR 0005 §4); its rate is the `validation` row `g1:calibrated` with the same `hypothesis` and `statistic`, and
  `tests.json` repeats it as `g1_size`. *Second fix round:* the band is the one for the replications the rate was
  measured on, and a rate within one point of 6.30% on 2,000 is re-measured on 10,000 and decided against 5.57%; that
  rate is the `validation` row `g1:calibrated_remeasured` (`n` = 10,000), and `tests.json` gives the count as
  `g1_reps`. A ramp primary on `rad_season_p` also gets a counterfactual row (role
  robustness, `subgroup_key = season_cut`, `subgroup_value = <last season>_into_<the one before>`) whose `p_holm` is
  the Holm p the hypothesis would get with that cut's p.
- `family = descriptive`: `aliv_path` per rel_day −10 … +10, `statistic = mean`, with two-way season × firm pointwise
  95% bands (`df`, `se`, `ci_*`; no p-value), for `all`, BMO and AMC, market- and mean-adjusted.
- `family = validation`: gate G1. `measure = g1:<design>`, `estimate` = the rejection rate, `n` = replications, role
  `primary` for the hypothesis's primary statistic and `robustness` for the others; `measure =
  g1_calibration:params` / `:measured` hold the calibrated design (`statistic` = the parameter, `rel_day` = the lag of a
  list), and `g1_calibration_sigma_d:params` / `:measured` the calibration of H4's own σ_d series (added after the
  milestone-3 review). `g1:calibrated_remeasured` holds the near-bar robustness rates re-measured on `n` = 10,000
  replications (second fix round). Among the measured rows, `dm_sd` (the sd of the daily change of ln VIX) and `beta_median` (the
  median company β) are Cboe-derived aggregates, committed under the owner's decision of 2026-10-29. The invariant
  skips validation rows.

*Milestone 4 (built).* `family = regression`: the crush regression of H5 and H6 (`model_id = crush_drivers`, daily,
market-adjusted; every named term's two-way t, H5's and H6's one-way date t, the mean-adjusted twin's two-way t of
those two terms), H7's model (`implied_realised`: the two Wald rows, the coefficient rows `a` (tested against 0) and
`b` (tested against 1: `stat` = (b − 1)/se), and `exceed_share` (`measure = abs_r0_over_implied`, the share against
0.425)), eight exploratory models (ADR 0005 §3's variants) and each model's `r2` row. H5–H7's primaries have role
`primary` and a `p_holm` over the declared family H1–H7 whatever G1's regression size check says (fix R1 after the
milestone-4 review; only an H1–H4 primary that fails its gate becomes `exploratory`, with its p-value and no
`p_holm`); a robustness row G1 finds mis-sized is withheld as at milestone 3, the twin by G1's key
`twoway_date_t:mean_adj`. BH q-values run within each (family, sample) over the exploratory rows only.
`family = descriptive`, `measure = holm_post_gate`: one row per hypothesis of the post-gate family (the declared one
without every hypothesis whose G1 primary failed), `estimate` = its Holm p over that family, `n` = the family's size,
and one row per season-cut counterfactual (`subgroup_key = season_cut`) with the cut's Holm p over it (a
sensitivity; the binding `p_holm` is the primary rows'). `family = validation`: G1's H5–H7 rates under
the same design names (H5/H6's stress designs share g1's names, own replications), `power_beta:<β>` and `power_b:<b>`
designs, and `g1_calibration_h7:params` / `:measured` (an infinite ν would be a null estimate).

**Invariant on the reference distribution** (added after the delta review, ledger N2; ADR 0005 §5, gate G1). For
every row whose `statistic` is a cluster-robust t (`twoway_*`, `cluster_*`, `sa_twoway_season_t`, and regression
`ols_coef` rows) or a cluster-robust Wald (`wald`, and since milestone 4 `twoway_date_wald` and `cluster_date_wald`,
whose df the first rule checks too):

- `df` = min(`n_clusters`, `n_clusters_firm`) − 1 for a two-way row, and `n_clusters` − 1 for a one-way row;
- `p_value` equals, to 1e-10, the two-sided $t_{df}$ tail of `stat`, or for `wald` the $F$ tail with `df` as the
  denominator degrees of freedom.

A fit left at statsmodels' default `use_t=False` breaks it, because its p-values are normal (χ² for Wald).

---

## 4. Python → app JSON contract

Every file is `app/public/data/<kind>.json` and uses the fixed envelope (`schema_version`, `kind`, `generated_at`,
`source_commit`, `data`). The per-view files below arrive with **schema_version 0.2.0** (milestone 1), were at
**0.3.0** at milestone 2 and **0.4.0** at milestone 3, and are at **0.5.0** since milestone 4; each bump is coordinated with `app/src/lib/contract.ts`. Every `data` object carries:

```
provenance: { params_hash: string, code_commit: string, sample_label: string,
              dolt_commits: { earnings: string, options: string } }
```

Numbers are rounded at export: IV and log quantities to 4 dp, moves to 5 dp, p-values to 4 significant figures. Missing
values are `null`, never NaN. Arrays indexed by `rel_days` have the same length as `rel_days`.

| File (`kind`) | `data` fields | Built from |
|---|---|---|
| `meta` (0.3.0; 0.2.0 at milestone 1) | `project`, `milestone`, `title`, `data_sources[] {name, uses, url, licence, committed}` (`uses` = the tables or series taken from the source), `data_licence {name, url, applies_to[], attribution}` (`applies_to` names the sources the licence covers; `attribution` is the text the About page shows), `sample {label, day0_from, day0_to, n_events, n_securities}` (`n_events` = the last funnel step), `params {event_window, baseline, baseline_exclusion, cm30_horizon_sessions, clock}`, `files[]` (kinds available), `provenance`. Written by `tools/export_app_data.py` and checked by `parseMetaData` in `app/src/lib/meta.ts`, which requires exactly these keys. | `tools/export_app_data.py` constants; `params.yaml`; the committed `data/derived/` tables |
| `sample_funnel` | `steps[] {step, label, n_events, n_removed, reason}`, `timing_status_counts {confirmed, corrected, inferred, date_corrected, no_document, not_checked, ambiguous}`, `timing_status_by_sample[] {sample, timing_status_counts}`, `by_move_tercile[] {sample, tercile, n_events, timing_status_counts, share_gap_contradicts, n_gap_check_changed, mean_crush_mean_adj}` or null, `by_move_tercile_status`, `evar_nonpositive {n, share}` or null, `evar_nonpositive_status`, `by_sample[] {sample, n_events}`, `lookups {n_done, complete}`, `caveats[]`, `provenance`. *Milestone 1 (0.2.0):* the steps are `calendar_events`, `timing_known` (which also removes `duplicate_row` rows, *since the milestone-1 delta review*), `daily_range`, `crush_observed`, `baseline_minimum` (`export/funnel.py`); `by_move_tercile` and `evar_nonpositive` are null, with a status string, until milestone 2 computes their inputs; the app accepts only null for them at 0.2.0. | `events` (`exclusion_reason`, `sample`, `timing_status`, `gap_check_changed`), `event_measures` (`eligible_*`, `ineligible_reason`, `abs_move_cand_max` for the terciles, `crush_mean_adj`), and `timing_check.gap_verdict_yf` for `share_gap_contradicts`. That share is an aggregate of a class-R input, so it falls under the §2.1 export rules. `by_move_tercile` is ADR 0002 §3's outcome-dependence check, per date sample, because `coarse` has a different look-up rule. *Revised after the delta review:* `unverified` is split into `no_document` and `not_checked`; the terciles are of `abs_move_cand_max`, not \|`realized_ret_0`\| (ledger N7); `sample` and `n_gap_check_changed` are new. *Milestone 2 (0.3.0):* a step `iv_usable` (a `cm30_iv` on day −1 and day 0) comes before `baseline_minimum`, whose clean sessions now need a `cm30_iv` (ADR 0004 §1 rule 2); `by_move_tercile` rows add `mean_abs_move` and `n_crush`, and their `share_gap_contradicts` is among the events with a gap verdict; `evar_nonpositive` is `{n_events, n_identified, n, share}` over the events of the last step (E at day −1, `n` of them ≤ 0); the inputs are `iv_daily`, `event_iv` (in place of `event_measures` until milestone 3) and the committed `timing_check.gap_verdict_yf`. |
| `iv_measures` (0.3.0, milestone 2) | `sample {label, n_events}`, `implied_move {units, n_identified, n_nonpositive, n, sqrt_mean_evar, quantiles {p10, p25, p50, p75, p90} or null, bin_edges[], counts[]}` (√E at day −1 of the primary events with E > 0; `sqrt_mean_evar` = √(mean E) over all events with an E, signed), `crush {units, n, mean, quantiles, bin_edges[], counts[]}` (`crush_mean_adj`), `caveats[]`, `provenance`. `len(bin_edges) = len(counts) + 1`, `sum(counts) = n`. | `event_iv` for the events of the funnel's last step (`export/iv_view.py`) |
| `event_paths` (0.4.0, milestone 3) | `rel_days[]` (−10…10), `series[] {measure, adjustment, units, subgroup_key, subgroup_value, n[], mean[], ci_lo[], ci_hi[]}`, `per_event[] {event_id, ticker, sector, day0, timing_used, values[]}` (`aliv_mean_adj` of cm30, for animated paths; the primary sample), `lookups {n_done, complete}`, `caveats[]`, `provenance` | `event_window_obs`, `results` (`aliv_path`). Market-adjusted `series[]` exist only for `all` and `timing` (§2.1 export rules); other subgroups' series are mean-adjusted. A suppressed rel_day is `null`, and its `n` is not shown. |
| `heatmap` (0.4.0, milestone 3) | `grids[] {id, title, measure, units, row_labels[], row_keys[], col_labels[], values[][], n[][], q[][] or null}`, `lookups`, `caveats[]`, `provenance`. *Milestone 3:* grid `company_by_event_day`: rows = companies (sector order), cols = rel_day −10…10, value = the company's mean `aliv_mean_adj` over its primary events, `n` = events in the cell. Grid `company_by_season`: cols = seasons, value = `crush_mean_adj` of the company's one primary event in that season (null and `n` shown when there is not exactly one). `q` is null (no cell is tested). The planned grid `sector_by_regime` could use `vix_regime` (filled since milestone 4); it is not built. | `event_window_obs`, `event_measures` |
| `terrain` (0.4.0, milestone 3) | `measure`, `units`, `rel_days[]`, `rows[] {security_id, ticker, sector, n_events}`, `values[][]` (rows × rel_days, mean `aliv_mean_adj`, null where missing), `row_order` (text), `lookups`, `caveats[]`, `provenance` | `event_window_obs` aggregated per security. A per-security mean covers ≈ 7 dates, so it is treated as per-event data and uses mean-adjusted values (§2.1). Matches `app/src/lib/terrain.ts` `values[company][eventDay]`. |
| `implied_vs_realised` (0.5.0, milestone 4) | `points[] {event_id, ticker, sector, day0, timing_used, event_var, implied_var_total, implied_move, implied_abs_move_total, realized_ret_0, abs_realized, implied_move_status, surprise_scaled}` (the primary events with a `realized_ret_0`; `implied_var_total` = E + σ_d²/252, H7's regressor), `summary {n, n_evar_nonpositive, n_with_implied_abs_move, share_exceed, share_exceed_se, share_exceed_p, share_exceed_benchmark (= 0.425), mean_log_ratio, median_ratio, regression {n, a, a_se, b, b_se, b_ci, wald_f, wald_df_num, wald_df, wald_p, role, p_holm, n_clusters_date, n_clusters_firm, wald_p_one_way, g1_rate, g1_pass, g1_bar, g1_rate_one_way, g1_pass_one_way}}`, `lookups`, `caveats[]`, `provenance` | `event_measures` (class F columns), `events`, `security`, `results` (H7's rows and G1's) (`export/driver_views.py`). `g1_bar` is the band's upper edge; `wald_p_one_way` is null exactly when `g1_pass_one_way` is false (withheld). `role` is `primary` with a `p_holm` while H7 is in the binding family (fix R1). `realized_ret_0` is the option-forward return (DoltHub), not Yahoo's |
| `tests` (0.4.0, milestone 3) | `rows[] {hypothesis, role, measure, statistic, estimand, sample, subgroup_key, subgroup_value, adjustment, rel_day, units, n, n_clusters, n_clusters_firm, estimate, se, stat, df, p_value, p_holm, q_bh, ci_lo, ci_hi, rbar, g1_size, g1_reps, note}`, `g1 {reps, band [lo, hi], calibrated[] {hypothesis, statistic, rejection_rate, pass}, designs[] {design, hypothesis, statistic, primary, rejection_rate}, power[] {hypothesis, shifts[], power[], detectable_80}, calibration {parameter: value}}`, `holm {family[], tested[], untested[], left_family[]}`, `lookups`, `caveats[]`, `provenance` | `results` where `family = event_test` (rows) and `family = validation` (g1) |
| `drivers` (0.5.0, milestone 4) | `models[] {model_id, adjustment, sample, label, dep_var, fixed_effects[], n, n_clusters_date, n_clusters_firm, r2, terms[] {term, label, hypothesis, role, statistic, cov_type, n, n_clusters_date, n_clusters_firm, coef, se, t, df, df_num, p_value, ci_lo, ci_hi, p_holm, q_bh, g1_size, g1_reps, note}}`, `g1 {reps, band, calibrated[] {hypothesis, statistic, primary, rejection_rate, reps, pass}, designs[] {design, hypothesis, statistic, primary, rejection_rate}, power[] {hypothesis, kind (beta or b), shifts[], power[], detectable_80}, calibration_h7}`, `holm {family[], left_family[], post_gate {family[], p_holm {hypothesis: p}, season_cut {hypothesis: p}}}`, `lookups`, `caveats[]`, `provenance` | `results` where `family = regression`, G1's H5–H7 validation rows and the `holm_post_gate` rows (`export/driver_views.py`). `terms[]` holds named regressors only; fixed-effect coefficients are never exported (`fixed_effects[]` lists their names only, §2.1). A withheld robustness term has `p_value`, `ci_lo` and `ci_hi` null and `g1_size`, `g1_reps` set; a primary term whose G1 size check failed keeps its p-value and `p_holm` and carries `g1_size`, `g1_reps` and a note (fix R1). `family` is the binding (declared) family; `post_gate` is a sensitivity. |
| `validation` | `vx[] {security_id, vx_index, n_days, corr_dlog, slope_dlog, slope_ci_lo, slope_ci_hi, mean_level_spread, crush_ratio_mean, crush_ratio_ci_lo, crush_ratio_ci_hi}`, `vendor_vs_ours {n, median_abs_diff, p95_abs_diff}`, `vol_history_maturity {best_tau_sessions, r2_by_tau[] {tau, r2}}`, `leak {mean_cm30_minus_blind_baseline, p95}`, `realised_vs_yahoo {n, median_abs_diff_bp}` | `results` where `family = validation`. **Statistics only, never a VX\* or Yahoo series.** |

---

## 5. Keys and cardinalities (the source for the ERD drawings)

Every FK is listed once, from the child column that holds it. "Parent : child" reads "how many parent rows one child
row points at : how many child rows point at one parent row". A nullable FK makes the parent side `0..1`. A row marked
**retired** keeps its number so that older references still resolve. Retired rows are not relationships and are not
drawn.

| # | Parent | Child | Child FK column(s) → parent key | Cardinality (parent : child) | Notes |
|---|---|---|---|---|---|
| R1 | `security` | `ticker_alias` | `security_id` → `security_id` | 1 : 1..* | |
| R2 | `security` | `events` | `security_id` → `security_id` | 1 : 0..* | |
| R3 | `security` | `eps` | `security_id` → `security_id` | 1 : 0..* | |
| R4 | — | — | — | — | **retired.** `chain_expiry` → `security` is implied by R11 + R5. |
| R5 | `security` | `iv_daily` | `security_id` → `security_id` | 1 : 0..* | |
| R6 | `session` | `market_daily` | `session_date` → `session_date` | 1 : 0..1 | |
| R7 | — | — | — | — | **retired.** `chain_expiry` → `session` is implied by R11 + R8. |
| R8 | `session` | `iv_daily` | `session_date` → `session_date` | 1 : 0..* | |
| R9a | `session` | `events` | `day0_session` → `session_date` | 0..1 : 0..* | nullable |
| R9b | `session` | `events` | `day_m1_session` → `session_date` | 0..1 : 0..* | nullable |
| R10 | `session` | `event_window_obs` | `session_date` → `session_date` | 1 : 0..* | |
| R11 | `iv_daily` | `chain_expiry` | (`security_id`, `session_date`) → (`security_id`, `session_date`) | 1 : 0..* | **Identifying**: the FK is the first two columns of the child's PK. 0 children iff `iv_daily.snapshot_status = missing`. |
| R12a | `chain_expiry` | `iv_daily` | (`security_id`, `session_date`, `front_expiry`) → (`security_id`, `session_date`, `expiration`) | 0..1 : 0..1 | "Expiry used". The referenced row is always a child of the same `iv_daily` row (R11). Checked in the stage cache only; `chain_expiry` is not committed. |
| R12b | `chain_expiry` | `iv_daily` | (`security_id`, `session_date`, `cm30_exp_lo`) → same | 0..1 : 0..1 | as R12a |
| R12c | `chain_expiry` | `iv_daily` | (`security_id`, `session_date`, `cm30_exp_hi`) → same | 0..1 : 0..1 | as R12a |
| R12d | `chain_expiry` | `iv_daily` | (`security_id`, `session_date`, `ev_exp1`) → same | 0..1 : 0..1 | as R12a |
| R12e | `chain_expiry` | `iv_daily` | (`security_id`, `session_date`, `ev_exp2`) → same | 0..1 : 0..1 | as R12a. Draw R12a–e as **one** line labelled "expiry used (5 roles)". |
| R13 | `events` | `eps` | `event_id` (unique, nullable) → `event_id` | 0..1 : 0..1 | **The only `events`–`eps` link.** Orphan periods have none. Invariants in §3.8. |
| R14 | — | — | — | — | **retired.** `events.fiscal_period_end` is a denormalised copy checked by the R13 invariants, not an FK. |
| R15 | `events` | `event_measures` | `event_id` → `event_id` | 1 : 1 | |
| R16 | `events` | `timing_check` | `event_id` → `event_id` | 1 : 0..1 | local only |
| R17 | `events` | `event_window_obs` | `event_id` → `event_id` | 1 : 0..71 | rel_day −60…+10 |
| R18a | `events` | `events` | `prev_event_id` → `event_id` | 0..1 : 0..1 | **Self-reference**, nullable, same security, ordered by `announce_date`. Invariants in §3.7. |
| R18b | `events` | `events` | `next_event_id` → `event_id` | 0..1 : 0..1 | Self-reference, the mirror of R18a. Draw R18a/b as one self-loop labelled "prev / next". |
| R19a | `events` | `iv_daily` | `next_event_id` → `event_id` | 0..1 : 0..* | |
| R19b | `events` | `iv_daily` | `prev_event_id` → `event_id` | 0..1 : 0..* | |
| R20 | `events` | `chain_expiry` | `next_event_id` → `event_id` | 0..1 : 0..* | |
| R21 | `events` | `event_measures_vx` | `event_id` → `event_id` | 1 : 0..1 | local only; the `cboe5` members |
| R22 | `security` | `session_snapshot` | `security_id` → `security_id` | 1 : 0..* | milestone 1; folded into `iv_daily` at milestone 2 |
| R23 | `session` | `session_snapshot` | `session_date` → `session_date` | 1 : 0..* | milestone 1 |
| R24 | `events` | `event_iv` | `event_id` → `event_id` | 1 : 1 | milestone 2; folded into `event_measures` (R15) at milestone 3 |
| — | `results` | — | — | — | aggregates; keyed by names, no FK |

Relationships-only sketch (the full attribute ERD is generated from §3 and the table above):

```mermaid
erDiagram
  SECURITY ||--|{ TICKER_ALIAS : "known as"
  SECURITY ||--o{ EVENTS : announces
  SECURITY ||--o{ EPS : reports
  SECURITY ||--o{ IV_DAILY : has
  SESSION ||--o| MARKET_DAILY : has
  SESSION ||--o{ IV_DAILY : on
  SESSION |o--o{ EVENTS : "day 0 / day -1"
  SESSION ||--o{ EVENT_WINDOW_OBS : on
  IV_DAILY ||--o{ CHAIN_EXPIRY : "expiries of the snapshot"
  CHAIN_EXPIRY |o--o| IV_DAILY : "expiry used (5 roles)"
  EVENTS |o--o| EPS : "reports period"
  EVENTS |o--o| EVENTS : "prev / next"
  EVENTS ||--|| EVENT_MEASURES : summarised
  EVENTS ||--o| EVENT_MEASURES_VX : "cboe5 member"
  EVENTS ||--o| TIMING_CHECK : "checked by"
  EVENTS ||--o{ EVENT_WINDOW_OBS : "window of"
  EVENTS |o--o{ IV_DAILY : "next / prev event of"
  EVENTS |o--o{ CHAIN_EXPIRY : "next event of"
  SECURITY ||--o{ SESSION_SNAPSHOT : "observed on"
  SESSION ||--o{ SESSION_SNAPSHOT : has
  EVENTS ||--|| EVENT_IV : "IV measures of"
```

---

## 6. Open questions this model depends on

1. ~~The hub cache path~~ **Resolved:** the hub's `STATUS.md` convention is followed. Downloads go to
   `$VOL_DATA_DIR/earnings-vol-study/raw/`; Dolt extracts and stages go to `$VOL_DATA_DIR/earnings-vol-study/cache/`
   (`config.raw_dir()` / `config.cache_dir()`). See ADR 0001 §2.
2. **Missing calendar events** (GS, COST). **Default taken 2026-10-29: leave them as orphan zones (no second
   source). The owner can override.** Measured at milestone 1 with the EPS match as revised after the milestone-1
   review (§3.8): 35 orphan periods of 1,359 expected (1,324 matched + 35), 2.58%, which is below the "about 3%" line
   of ADR 0002 ("How we'll know it's wrong"), so the decision stays optional and the owner flag is withdrawn. 18 of
   the 35 come from 8 sessions of early 2022 with no calendar row for any company; COST's 7 are its February
   quarters. The first window gave 43 (3.16%), 8 of them false. See ADR 0002 §3 and its milestone-1 note.
3. **Owner decision: how strictly to read the Yahoo/CBOE licence rule.** **Default taken 2026-10-29: strict, as
   described here. The owner can override.** The default is strict for numbers:
   market-adjusted per-row and per-event values and `s_abn_cboe` stay local, and small market-adjusted cells are
   suppressed. Labels (class F: timing, `vix_regime`) are committed. See §2.1 for both alternative readings. Decide
   before milestone 3, because the answer renames columns.
4. ~~Whether `dolt sql -r parquet` works on dolt v2.6.1~~ **Resolved 2026-10-29: it works.** Dates come back as
   timestamps, decimals as decimals and SQL NULL as a real null, so the CSV sentinel is gone. Its speed equals CSV's on
   one month of `option_chain` (40.75 s against 40.25 s; the month, 2025-10, holds 159,604 rows, *corrected after the milestone-1 delta review* from 160,584, a figure that could not be traced), so it was chosen for the types. pyarrow's direct
   decimal-to-float cast is not correctly rounded, so decimals are cast through their text form
   (`ingest/dolt.py`, `normalise`).
5. **`cboe5` before 2020.** VX\* history from 2011 cannot be used yet, for two reasons. The calendar starts on
   2020-01-22, so a second source of event dates is needed (the same owner decision as item 2). And `cboe5` members
   need a null `exclusion_reason`, so pre-2020 events would also need an exemption from `outside_samples`. See ADR
   0004 §5.
6. **SEC EDGAR as the primary timing source.** **Accepted by the owner 2026-10-28; runs once the owner's contact
   string is set.** Until `SEC_EDGAR_USER_AGENT` holds it, the EDGAR client refuses to run, no event has
   `timing_source = edgar`, `edgar_accession` / `edgar_accepted_utc` stay null, and the default rule (the press
   release, then the calendar label) is operative; `timing_status` stays class F (§2.1, §3.7). ADR 0002's milestone-1
   check of EDGAR (coverage ≥ 95%, the 50-event audit) runs when the string arrives.
7. **Whether about 415 press-release look-ups are practical.** Measured on 2026-10-29: the first 20 look-ups took
   10.72 minutes of agent wall-clock time in total, the sum of `lookup_minutes` (mean 0.54, median 0.35, range 0.27
   to 1.99 minutes). The default
   rule requires 473 look-ups for the 50 companies (`events.lookup_violations` before any look-up), which extrapolates
   to about 4.3 hours at the mean. **Default taken 2026-10-29: the remaining look-ups wait for EDGAR; the owner can
   override.** Until then every other event keeps the calendar label as `not_checked`, the build invariant is reported
   and not enforced (`params.yaml`: `timing.lookups_complete: false`), and the labels are marked provisional in the
   manifests, the funnel and the app.
8. ~~Owner question for the milestone that plans the VX\* validation (added after the milestone-2 review).~~ **Closed
   2026-10-29: covered by the owner's decision of 2026-10-29** (real data the app and the docs need may be committed;
   only bulk raw files stay out). The VX\* cross-check may be built and its values committed. The question was: Cboe's
   terms may restrict using Cboe data to verify other data: in the review's paraphrase (Channel A §G4), the website
   terms of use (last updated 2022-11-16) bar using the materials to verify or correct other data or information.
   ADR 0003's validation item 1 compares our `cm30_blind_iv` with the VX\* indices, and ADR 0001 §7 plans to export
   statistics such as a correlation with VXAPL. Whether the VX\* downloads fall under those website terms or under a separate data
   agreement is not checked; the owner's decision allows the comparison. It is not built at milestone 3 (no VX\* file has been
   downloaded; `docs/milestones/03-event-study.md` lists it as the next step).
