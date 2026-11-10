# Cboe VX\* cross-check: pre-registration

Written on 2026-11-09, **before any VX\* file was downloaded**. The SHA-256 of this file is recorded in
`docs/validation/vx-ledger.md` before the first request to Cboe. A change to this file after the download is a
deviation, and the ledger must list it.

The four bars in §3 come from ADR 0003, "Validation plan (milestone 2)", item 1. They were written at milestone 2.
This file adds the details that the ADR left open: alignment, gaps, intervals and the meaning of "no breaks".

## 1. Series

| Name | Our series | Cboe series |
|---|---|---|
| AAPL | `iv_daily.cm30_blind_iv` | VXAPL |
| AMZN | `iv_daily.cm30_blind_iv` | VXAZN |
| GOOGL | `iv_daily.cm30_blind_iv` | VXGOG (built on GOOG, not GOOGL: noted, not corrected) |
| GS | `iv_daily.cm30_blind_iv` | VXGS |
| IBM | `iv_daily.cm30_blind_iv` | VXIBM |

- Ours: `data/derived/iv_daily.parquet`, a decimal. Cboe: the `CLOSE` column of
  `cdn.cboe.com/api/global/us_indices/daily_prices/<SYM>_History.csv`, divided by 100.
- The overlap is every session where both values exist. Our series starts on 2020-01-02.
- The VX\* series stay on this machine (`$VOL_DATA_DIR/earnings-vol-study/raw/cboe/`). Only the aggregate
  statistics below are committed.

## 2. Alignment and changes

- A Cboe row with date D is matched with our row whose `session_date` is D.
- **Primary changes:** Δln between two consecutive sessions where both series have a value on both days.
- **Secondary:** changes over gaps of more than one session, with the Cboe change over the same two dates.
- **Alignment falsifier:** the pooled correlation of changes at Cboe lags −1, 0 and +1 sessions. The primary
  numbers use lag 0. If lag ±1 is higher than lag 0, that is reported as a finding; the bars are still judged at
  lag 0.

## 3. Bars

| # | Statistic | Bar (ADR 0003) | Verdict rule |
|---|---|---|---|
| i | Pearson correlation of primary Δln VX on Δln ours, per name and pooled | > 0.8 | Pass per name when the point estimate is above 0.8. The 95% interval is reported beside it. |
| ii | OLS slope of Δln VX on Δln ours, per name and pooled | ≈ 1 | The ADR set no tolerance. Report the slope and its 95% interval, and whether the interval holds 1. This is descriptive, with no pass or fail. The reverse-regression slope is reported too, because noise in our series pulls the forward slope below 1. |
| iii | Level spread, VX − ours, in vol points | stable, no breaks | "No breaks" means every calendar year's median spread is within ±2.0 vol points of the name's median over all years. Also report the share of days where VX is above ours: the ADR expects VX to sit above ATM IV. |
| iv | Day-0 crush ratio | 1 ± 0.2 | R = mean of Δln VX(−1→0) ÷ mean of Δln ours(−1→0), over the primary-sample events of the five names. Day 0 follows ADR 0002, so it depends on the timing labels, and the SEC EDGAR look-ups have not run yet. Pass when R is in [0.8, 1.2]. The 95% interval is reported beside it. |

## 4. Intervals

- Bars i–iii: a moving-block bootstrap over session dates, with **block length 20 sessions** and 10,000
  repetitions. For pooled statistics, the same dates are resampled for all names. A block length of 60 sessions is
  reported as a sensitivity check.
- Bar iv: a bootstrap over events, with 10,000 repetitions. Events of one company are about a quarter apart.
- The seed is fixed and is recorded in the ledger.

## 5. Third check: `volatility_history.iv_current`

`iv_current` is read from the private mirror only, at the pinned options commit. Its maturity is undocumented.

1. Compare `iv_current` with VX\* and with our `cm30_blind_iv`: the bar-i correlation and the bar-iii median spread.
2. **Maturity:** this needs our ATM IV at several horizons on each day. If the committed or staged data hold
   per-expiry ATM IVs every day, interpolate the ATM total variance at horizons of 10, 15, 21, 30, 42 and 63
   sessions. The identified maturity is the horizon with the smallest median |level difference|; its change
   correlation is reported beside it. If those IVs do not exist every day, the maturity stays UNRESOLVED, and the
   ledger says so.

This is a third check only. It changes no verdict in §3.

## 6. What is not allowed after the download

- Changing a bar, the block length, the alignment or the event set.
- Dropping a name or a year.
- Any additional analysis must be labelled "exploratory, not pre-registered".
