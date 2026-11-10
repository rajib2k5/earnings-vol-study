# VX\* cross-check: EGV claims ledger (pre-registered)

Frozen on 2026-11-09, before either channel ran. Neither channel may add, drop or reword a claim. Environment:
`env-pin.txt` in this folder. Every material claim starts **REJECTED**.

Scope: the claims about external data products and about the bootstrap algorithm that the cross-check's numbers
rest on. The values of the agreement statistics are not EGV claims (a documentation channel cannot see a number):
they go to the verifier and the adversarial re-derivation (router rows 5 and 6).

| ID | Cat | Mat | Claim |
|---|---|---|---|
| C1 | Semantic | material | Cboe's VXAPL, VXAZN, VXGOG, VXGS and VXIBM each measure the 30-day expected volatility of one stock. |
| C2 | Semantic | material | These five indices are computed with the VIX method from a strip of out-of-the-money options. |
| C3 | Semantic | minor | VXGOG is computed from options on GOOG (Class C shares), not on GOOGL. |
| C4 | Environmental | material | `https://cdn.cboe.com/api/global/us_indices/daily_prices/<SYM>_History.csv` serves each of the five series as daily rows with a `CLOSE` column. |
| C5 | Semantic | material | The `CLOSE` value is annualised volatility in percentage points, so `CLOSE / 100` is on the same scale as a decimal implied volatility. |
| C6 | Semantic | material | A row dated D holds the index value at the end of trading session D, so it pairs with our row whose `session_date` is D without a shift. |
| C7 | Environmental | material | Each of the five series has a value on most sessions from 2020-01-02 to 2026-10-26, the span of our `cm30_blind_iv`. |
| C8 | Semantic | material | DoltHub `post-no-preference/options` documents no maturity for `volatility_history.iv_current`. |
| C9 | Algorithmic | material | The cross-check's moving-block bootstrap draws overlapping blocks of fixed length with replacement and joins them until the series length is reached (Künsch 1989). |
| C10 | Algorithmic | material | For pooled statistics, the bootstrap resamples the same dates for all five names in each repetition. |

Code under validation, for C9 and C10: the module the builder adds under `src/earnings_vol/` for the cross-check (path
given to each channel when the build ends).
