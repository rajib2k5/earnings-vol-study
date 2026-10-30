# data/derived

This folder holds **small tables derived from two DoltHub databases**:

- [post-no-preference/earnings](https://www.dolthub.com/repositories/post-no-preference/earnings)
- [post-no-preference/options](https://www.dolthub.com/repositories/post-no-preference/options)

The pipeline tables are made by the code in `src/` and `tools/`, not by hand. Each file is the committed part of a
table in the schema registry (`src/earnings_vol/schema.py`): class-R columns (Yahoo or CBOE values, names ending in
`_yf` or `_cboe`) are dropped by `store.write_derived`, which also refuses local-only tables, except the class-R
columns a table names in `keep_restricted` (owner decision of 2026-10-29; at milestone 2 only
`timing_check.gap_verdict_yf`). The same inputs give the same bytes.

| File | What it is | Made by |
|---|---|---|
| `security.parquet` | The 499 S&P 500 constituents of Wikipedia revision 1382178819 (one share class per company): name, GICS sector and sub-industry, CIK, and the universe flag (the 50 of the study, chosen by a one-time Yahoo market-cap rank; the flag is a class-F label under Yahoo's terms, not CC BY-SA, see below; the rank itself is not committed) | `python -m earnings_vol.events.run` |
| `ticker_alias.parquet` | ticker → security over time (FB → META, UTX → RTX) | same |
| `session.parquet` | NYSE sessions 2016–2027 from `exchange_calendars` (XNYS), with half days and the snapshot era | same |
| `events.parquet` | 1,353 announcements of the 50 companies from `earnings_calendar`, with day 0, the timing label and its status, links, sample and exclusion reason. Timing labels are provisional: 20 were checked against press releases (`data/manual/press_release_checks.csv`), the rest are the calendar's (`not_checked`) | same |
| `eps.parquet` | one row per company and fiscal period from `eps_history`, matched to its announcement, with the last weekly consensus before day −1 from `eps_estimate` | same |
| `session_snapshot.parquet` | for every company and session 2020-01-02 → 2026-10-26: is an option snapshot there (`ok`, `stale_repeat`, `missing`)? From `option_chain` | `python -m earnings_vol.measures.run --only snapshots` |
| `iv_daily.parquet` | milestone 2: one row per company and session 2020-01-02 → 2026-10-26 (85,650 rows, 4.7 MB): the front ATM IV, the event-aware and the blind 30-day IV, the event variance E and the implied move, the diffusive IV, the expiries used. Recomputed from `option_chain` bid/ask mids with Black-76 on the put-call-parity forward (ADR 0003); the discount rate is FRED's `DTB3` (an input, not a stored value; see the licence below) | `python -m earnings_vol.measures.run --only iv` |
| `event_iv.parquet` | milestone 2: one row per announcement (1,353): E and the implied move on day −1, the 30-day and front-expiry crushes, the realised day-0 move from the parity forwards, the label-free move used for the funnel's terciles | same |
| `event_window_obs.parquet` | milestone 3: one row per announcement and session, rel_day −60 … +10 around day 0, for the 1,259 announcements with no exclusion (89,389 rows, 2.8 MB): observed, in the clean baseline (and why not), the 30-day IV, its log and change, the **mean-adjusted** abnormal log IV and IV level, the front-expiry IV in the event window, σ_d and E. The VIX-adjusted columns stay local | `python -m earnings_vol.panel.run` |
| `event_measures.parquet` | milestone 3: one row per announcement (1,353): per-measure eligibility and its reason, the baseline counts and means, the mean-adjusted crushes, and the IV columns of `event_iv`; since milestone 4 the regressors `price_ref`, `surprise_scaled`, `abs_surprise_scaled_w`, `sue_hist`, `sue_hist_n` (DoltHub option forwards and EPS) and `vix_regime` (a VIX tercile label: Cboe's terms, below). The VIX-adjusted measures (`*_cboe`), β, the scales and the Yahoo columns (`*_yf`) stay local | same |
| `results.parquet` | milestone 3: every aggregate the report and the app show: the event tests H1–H4 with their robustness rows, the mean-adjusted twins and the exploratory rows, the mean abnormal paths with their bands, and gate G1's rejection rates and calibration; since milestone 4 the regressions (H5–H7 and the exploratory models) and G1's H5–H7 rows. **The market-adjusted rows are statistics over values computed with the Cboe VIX index (FRED `VIXCLS`)**; Cboe's terms apply to them, not CC BY-SA (see the licence below) | `python -m earnings_vol.stats.run --g1`, then `python -m earnings_vol.stats.run` |
| `timing_check.parquet` | milestone 2: one row per announcement with `gap_verdict_yf`, the verdict of the Yahoo overnight price gap on the timing label in use (`supports`, `contradicts`, `quiet`, or null). **A Yahoo-derived label, committed under the owner's decision of 2026-10-29**; Yahoo's terms apply to it, not CC BY-SA (see the licence below and the root `DATA.md`). The gaps and z-scores behind it stay local | `python -m earnings_vol.events.run` |
| `earnings_calendar_30_large_caps.json` | 336 rows of `earnings_calendar` (`act_symbol`, `date`, `when`) for 30 large caps, queried for 2024-01-01 → 2026-10-27 (the rows run 2024-01-12 → 2026-10-27), as returned by DoltHub's SQL API (milestone 0) | The exact query and the commit it ran against are inside the file: `commit_ref` is only the branch name (`master`, which moves), and `resolved_commit` is the commit hash that `master` pointed to when the file was fetched, with `resolved_commit_note` saying how it was chosen. It is the input to `research/prototypes/spacing.py`, the gap analysis behind ADR 0004. |

The DoltHub commits read are pinned in `params.yaml` (`dolt`), and every table records them (`events.calendar_commit`;
the stage manifests). The Wikipedia columns of `security.parquet` are CC BY-SA 4.0 as well (attribution: Wikipedia,
"List of S&P 500 companies", revision 1382178819).

## Licence: CC BY-SA 4.0 (ShareAlike), with two named exceptions

Both DoltHub repositories declare the licence *Attribution-ShareAlike 4.0
International* (each has a `LICENSE.md` with that title). Files here are
**derived / modified** from them, so they are shared under the same licence:

- **Attribution**: the original data is from DoltHub, repositories
  `post-no-preference/earnings` and `post-no-preference/options` (links above).
  We selected and filtered it. DoltHub and the original authors do not endorse
  our changes.
- **ShareAlike**: if you build on these files, share your version under
  CC BY-SA 4.0 or a compatible licence.
- Licence text: <https://creativecommons.org/licenses/by-sa/4.0/legalcode>

See [`LICENSE`](LICENSE) in this folder. The code in the rest of the repository
is MIT-licensed (root `LICENSE`); the MIT licence does not apply here.

### Columns from other sources

Every column of every file here is DoltHub-, Wikipedia- or calendar-derived and under CC BY-SA 4.0, except the
columns this table says otherwise. It lists every committed column derived from Yahoo, Cboe or FRED data (data model
§2.1; the schema registry marks each column's class).

| Column | Source | Terms | Why it is here |
|---|---|---|---|
| `timing_check.gap_verdict_yf` | **Yahoo Finance** daily prices: the overnight gap on the candidate day 0, as a three-level verdict | **Yahoo's terms of service, not CC BY-SA** | the app's sample funnel shows the share of `contradicts` per move tercile (`sample_funnel.json`, built from this column). Owner decision of 2026-10-29 |
| `security.in_universe` | **Yahoo Finance** market caps: a one-time rank picks the 50 companies (the rank itself stays local) | **Yahoo's terms of service, not CC BY-SA** | it says which companies the study covers |
| Every IV, variance and move in `iv_daily` and `event_iv` (`front_atm_iv`, `cm30_iv`, `cm30_blind_iv`, `sigma_d_iv`, `event_var`, `ev_w1`, `ev_w2`, the `implied_*` columns, `ts_slope`, `forward_front`; `evar_*`, `sigma_d_m1`, `cm30_*`, the crushes, `front_fixed_iv_*`, `realized_ret_0`, `abs_ret_over_implied`, `abs_move_cand_max`) | DoltHub option quotes, with **FRED `DTB3`** as an input (the discount factor and the carry). No column holds a FRED value | CC BY-SA 4.0 (DoltHub-derived). `DTB3` is public domain; FRED asks for the citation in `LICENSE` | the study's measures |
| `security.cboe_vx_index` | the name of the **Cboe** single-stock index that exists for the company (VXAPL and four others) | a name, not Cboe data: CC BY-SA 4.0 with the rest of the table | it marks the companies with a VX\* index |
| `event_measures.vix_regime` (milestone 4) | a three-level label (`low`, `mid`, `high`) of the **Cboe VIX** close at day −1, terciles within each sample | **Cboe's terms, not CC BY-SA** | the VIX-tercile regression variant; owner decision of 2026-10-29 |
| `results` coefficients of the term `size` (milestone 4) | regressions on ln market cap at day −1, built from **Yahoo Finance** (the rank date's market cap and closes; the per-event values stay local) | **Yahoo's terms of service, not CC BY-SA** | the drivers regression; owner decision of 2026-10-29 |
| `results` numbers of the market-adjusted rows (`adjustment = market`): `estimate`, `se`, `stat`, `p_value`, `ci_lo`, `ci_hi`, `p_holm`, `q_bh`, `rbar`; and the G1 rows (`family = validation`) | statistics over values adjusted with the **Cboe VIX** close (FRED `VIXCLS`), milestone 3; the G1 calibration rows include `dm_sd` (the sd of the daily change of ln VIX) and `beta_median` (the median company β) | **Cboe's terms, not CC BY-SA**; FRED's citation is in `LICENSE` | the event tests, the mean paths and gate G1. Owner decision of 2026-10-29. The VIX series and every per-event or per-company VIX-adjusted value stay local |

No other column is derived from Yahoo, Cboe or FRED data (H7's rows, `adjustment = none`, use DoltHub-derived
moves only). The mean-adjusted values of `event_window_obs` and
`event_measures` contain no VIX value. The timing labels in `events.parquet` (`timing_used`,
`timing_status`, `timing_source`, `gap_check_changed`, day 0 and what depends on it) come from the DoltHub calendar
and from company press releases; a Yahoo gap only decides which events are looked up or read a second time, so they
are class-F labels shared under CC BY-SA (data model §2.1). **No VIX or VX\* value is committed** in this folder or
anywhere else in the repository; only the aggregates above are.

## What is never committed here

Raw downloads are never committed: the Yahoo prices and market caps read with `yfinance`, FRED's `DTB3` and `VIXCLS`
series, the Cboe VX\* files, the raw Dolt extracts and clones. They live under `VOL_DATA_DIR` (see
`src/earnings_vol/config.py`), outside the repository, and `.gitignore` also blocks `data/raw/` and `data/cache/`.
Every other class-R column (a Yahoo or Cboe value: the gaps and z-scores of `timing_check`, the VIX columns of
`market_daily`, the VIX-adjusted `*_cboe` columns of `event_window_obs` and `event_measures`) is dropped by
`store.write_derived`, which keeps only the columns a table names in `keep_restricted`
(owner decision of 2026-10-29). `tools/licensing/check_data_files.py` refuses any file here that is not a committed
registry table with its committed columns, this README, the licence or the milestone-0 calendar JSON. Since the
milestone-1 review the worked examples in ADR 0002 and `research/prototypes/worked.py` no longer quote Yahoo prices.
If you want the raw data, get it from the sources yourself and follow their terms.
