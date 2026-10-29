# ADR 0003: IV measures (front ATM, event-aware 30-day, event variance and implied move)

- **Status:** Accepted (milestone 0), **revised 2026-10-28 after the milestone-0 methodology review**, and again
  after the milestone-0 delta review (notes below); validated at milestone 2, and revised after the milestone-2 review
  (note below: the forward tie, the quadratic fallback, AMC expiries, the E pair)
- **Date:** 2026-10-28
- **Related:** [0002 day 0](0002-day-zero-convention.md), [0004 windows](0004-baseline-and-event-windows.md),
  [data model](../architecture/data-model.md) (`chain_expiry`, `iv_daily`)

> **Revised after milestone-0 review** ([ledger](../validation/m0-methodology-ledger.md)).
>
> 1. **Refuted: "the worked example is the hand-worked oracle for the test" (ledger N1).** The table was produced by
>    `research/prototypes/worked.py`, which took the median parity forward over *all* strikes. §0 step 2 takes it over
>    the 4 strikes with the smallest $|C-P|$. On the 10-30 / 11-14 expiry (7 strikes) that moved $F$ from 271.69 to
>    271.42 and $E$ from 0.00069327 to **0.00088284 (+27%)**.
>    - **Decision:** keep the 4-strike rule (reasons in §0 step 2).
>    - The script now follows it, and the worked example below is the re-run.
>    - Every number derived from the example changed. The implied move went from 2.63% to 2.97%, and the
>      calendar-clock effect on the variance from +48% to +36%.
> 2. **Refuted: the prototype's "identity check" (N4).** It compared an expression with itself and could not fail. It is
>    replaced by a check against the IV form, run once more with a planted bug that it must catch (§c, "Units").
> 3. **Unspecified (claim 4):** a quote can pass the §0 filter and still leave Brent's method with no root. The rule is
>    now in §0 step 3.
> 4. **Inconsistent (claim 13):** T1\* allowed τ = 4 at day 0, against the τ ≥ 5 usability rule. T1\* now needs τ ≥ 5
>    at day 0 (§a).
> 5. **Inconsistent (claim 13):** σ_d² meant per-session in some formulas and annualised in others. Notation is fixed in
>    §c "Units", with the units of every stored σ_d column.
> 6. **Understated (N3):** the leak of blind interpolation was quoted for one grid point (0.26 / 1.1 vol points). Its
>    range on the vendor grid is 0–0.66 / 0–2.73 vol points (§b).

> **Revised after the milestone-0 delta review** ([delta ledger](../validation/m0-delta-ledger.md), claims 3b, 10c,
> N6, 9d). The worked values all re-ran identically (3a). Two statements about the checks were wrong:
>
> 1. **Refuted (10c): "a second, independent oracle"** (§c, "Units"). The 4-decimal recomputation of $E$ uses the IVs
>    printed in the same table, which come from the same forward, $w$ and session counts. It moved with ledger N1's
>    forward bug (mutant m2). It is renamed a consistency check on rounded inputs.
> 2. **Overstated by omission (3b, N6): what the identity check protects.** It catches a lost 252 and a wrong
>    $E$-formula denominator. It does not catch a wrong forward, a wrong session count, a wrong ATM interpolation or a
>    wrong discount factor. §c now lists these, with the $E$ each mutant prints and the independent check that
>    protects each.
> 3. **Hygiene (9d):** §e called the −0.38% cross-check "Yahoo's close-to-close". It is the official close-to-close,
>    and it is now called that.

> **Milestone 2, 2026-10-29: built and checked** ([walkthrough](../milestones/02-iv-measures.md)).
>
> - **The oracle reproduces** through the pipeline's own code (`tests/test_iv_worked_example.py`, reading
>   `worked.py`'s quotes): E = 0.00088284, and every row of the table below. On the real chain with the FRED rate E is
>   0.00088307. That rate is `market_daily.r_cont` = 3.83% on 2025-10-30, the continuous rate converted from a raw
>   DTB3 of 3.76% on a discount basis; the table below uses 3.9%. *(Wording corrected after the milestone-2 review: it
>   said "the FRED rate (3.83% …)" as if DTB3 itself were 3.83%.)*
> - **Validation item 2 (the vendor `vol`)**: on 53,135 front-expiry days away from events, the vendor is 0.16 vol
>   points below ours on the calendar clock (median 0.11, median |difference| 0.17, p95 0.94): under the 0.5-point
>   line. Items 1 (VX\*) and 3 (`iv_current`) are not run yet.
> - **"How we'll know it's wrong"**: the blind 30-day IV sits 0.23 vol points above the event-aware one in the
>   sessions 22–60 before an event, above the 0.1 line, so the event-aware series stays. E ≤ 0 on day −1 for 1.15% of
>   the primary sample, far below 25%.
> - **Choices the text left open**, made in the code and listed in the walkthrough §2: the w used to draw the
>   quadratic's window (the too-wide bracket's linear w); spans by `as_of(expiration)`; `sigma_d_iv` from E's pair,
>   else the two shortest clean expiries; the vendor ATM interpolated in vol at the bracket; T1\* among `ok` expiries
>   and never extrapolated; the realised move's expiry and the start day's rate. Interpolating C + P across the kink at
>   K = F biases the straddle IV up; 20% of `ok` expiries carry `straddle_gap`. The straddle stays a cross-check only.
>   (Numbers in this note re-measured after the milestone-2 review below.)

> **Revised after the milestone-2 review** ([ledger](../validation/m2-ledger.md), claims 2a, 3b, 7, 8). Four rules
> changed or were written down; every number of the milestone-2 page was re-measured after them.
>
> 1. **Refuted (2a): ties to the lower strike.** The code ranked the float |C − P|, and an exact tie in cents could
>    break the wrong way (|0.005 − 0.010| = 0.005 but |0.010 − 0.015| = 0.004999999999999999). §0 step 2 now ranks
>    2|C − P| as a whole number of cents. On the real data this changed 89 of 180,055 forwards (at most 0.56, 0.43%),
>    and the IV of those 89 expiries by a median of 0.05 and at most 2.99 vol points (PLTR 2025-06-27, expiry
>    2025-07-25: 63.59% → 60.61%).
> 2. **Refuted as sound (3b): the quadratic fallback.** 166 of its 293 uses fitted strikes on one side of the money
>    only, so the ATM w was extrapolated. §0 step 4 now requires a bracket and at least one valid strike on each side
>    of k = 0 in the window; otherwise the status is `no_atm`. The weights stay inverse **relative** spread, and the
>    text now says so (it said "inverse spread"). The hold-out evidence is under §0 step 4. Effect: 127 quadratic rows
>    remain, 166 became `no_atm`, and one primary event (RTX 2025-04-22, whose day-0 front expiry was a one-sided fit)
>    has no 30-day IV on day 0 any more: the primary sample is 347, not 348.
> 3. **Contested (7): an AMC announcement on an expiry day.** The exercise decision runs until 5:30 p.m. ET (FINRA Rule
>    2360), after an after-close release, so an expiry on the announcement day D is now classed **spanning**,
>    conservatively (§b, "The problem"). The same holds for an event without a label, anchored on next(D). 157
>    `chain_expiry` rows changed class: 31 (27 usable) for 7 AMC events and 126 (114 usable) for 16 unlabelled
>    (`timing_not_checked`) events.
> 4. **Undocumented (8): which expiries E uses.** T1 and T2 are the two shortest **usable** spanning expiries (`ok`,
>    τ ≥ 5); an expiry without an ATM w is skipped (§c, "Which expiries": 235 of 19,601 E rows skip one). The
>    `sigma_d_iv` fallback (the two shortest clean expiries) is now pinned by a test.
> 5. **Inaccurate:** §0 step 3 said the lower root bound always holds; it does not above F ≈ 1,253 (corrected there).

## In one paragraph

We recompute every IV ourselves from bid/ask mids. We do not trust the vendor's `vol` column. The method is
**Black-76 on the put-call-parity forward** of the same snapshot. The forward makes the calculation independent of
the spot price, dividends and the snapshot time. The basic stored quantity is the **ATM total implied variance**
`w = σ²T` of each expiry, interpolated in log-moneyness from the out-of-the-money option at each strike. Time is
counted in **NYSE sessions**, not calendar days. All other measures are built from `w`:

1. an *event-anchored* front-expiry ATM IV;
2. an **event-aware 30-day constant-maturity IV**, the primary daily series, which never borrows event variance from
   an expiry on the wrong side of the earnings date;
3. the **event variance E** à la Dubinsky & Johannes (2006), with **implied move √E**.

E is stored signed. When E ≤ 0 there is no implied move, and averages are taken in variance space. CBOE VX\*
indices and the vendor columns are used only to validate.

## Context: what the option data actually looks like

Measured on 2026-10-28 through the DoltHub API. Schemas are in [data-model.md §1](../architecture/data-model.md#1-source-tables-as-found).

- **No underlying price, no open interest, no volume.** `option_chain` has `date, act_symbol, expiration, strike,
  call_put ('Call'|'Put'), bid, ask, vol, delta, gamma, theta, vega, rho`. Vega is per vol point, theta per
  calendar day and rho per 1%; we checked this against the AAPL 272.5 call on 2025-10-30.
- **Only 3–4 expirations per snapshot, chosen by the vendor per date and identical across symbols.** On 2025-10-30
  every symbol we checked (AAPL, GS, HSY, IBM, JPM, KO, MSFT, NVDA) had exactly 2025-11-14 (15 days), 2025-11-28 (29
  days) and 2025-12-19 (50 days). AAPL's sets over two weeks:

  | snapshot | expirations (calendar days to expiry) |
  |---|---|
  | 2025-10-27 | 11-07 (11), 11-21 (25), 12-19 (53) |
  | 2025-10-29 | 11-14 (16), 11-28 (30), 12-19 (51) |
  | 2025-10-31 | 11-14 (14), 11-28 (28), 12-19 (49) |
  | 2025-11-10 | 11-21 (11), 12-05 (25), 12-26 (46) |
  | 2025-11-17 | 11-28 (11), 12-12 (25), 12-26 (39), 2026-01-16 (60) |

  The front expiry is always about 10–16 calendar days out (7–11 sessions). **The weekly that expires right after an
  earnings date is usually absent.** The set can change completely from one session to the next: 10-27 and 10-29
  share only 12-19. The 2021 chains have the same structure.
- **Sparse, irregular strikes, about 19–27 per expiry.** AAPL 2025-11-14 on 2025-10-30 runs 190, 205, 215, 225, 230,
  237.5, 245, 250, 255, 260, 262.5, 265, 267.5, **(no 270)**, 272.5, 275 and on to 355, with the stock at about 271.
  The 270 strike is there on 10-29 and 10-31. "Nearest strike" therefore jumps around from day to day.
- **The vendor's IV is internally inconsistent.** At the same strike, call and put IV differ by 0.1–0.3 vol points on
  a normal day. On the announcement day they differ by up to **3.1 vol points** (2025-10-30, K = 265: call 0.3457 vs
  put 0.3144). Deep in-the-money rows have meaningless IVs (the 190 call shows 0.8653). The vendor's spot, dividend,
  rate and day-count inputs are not published.
- `volatility_history.iv_current` has an undocumented maturity. For AAPL it was 0.2564 on 2025-10-30 and 0.2252 on
  10-31. Our ATM IV for the ~29-day expiry on those dates was 0.2659 and 0.2334, annualised on the calendar like the
  vendor. That fits roughly 30 days, about 1 vol point lower, and is **unconfirmed**.

## Decision

### 0. The atom: ATM total variance per (symbol, session, expiry)

For each snapshot (mapped to a session per ADR 0002) and each expiry:

1. **Quote filter.** Keep a quote when $0 < bid < ask$, $mid = (bid+ask)/2 \ge 0.05$, and the relative spread
   $(ask-bid)/mid \le 0.5$. After step 2, also require $|\ln(K/F)| \le 0.5$ and the price to sit inside the no-arbitrage
   bounds $\max(DF(F-K),0) \le C \le DF\cdot F$ (similarly for puts).
2. **Forward from put-call parity.** For a European option $C - P = DF\,(F - K)$, so every strike quoted on both sides
   gives $F_K = K + (C_{mid} - P_{mid})/DF$. Take $F$ = the median of $F_K$ over the 4 strikes with the smallest
   $|C_{mid}-P_{mid}|$, among strikes whose call and put both pass the first part of the filter. Ties go to the lower
   strike. *Revised after the milestone-2 review:* $|C-P|$ is ranked as the whole number of cents
   $|(bid+ask)_C - (bid+ask)_P| = 2|C-P|$, so an exact decimal tie is a tie; a float can order it the other way.
   With fewer than 4 such strikes use all of them; with none, the status is `no_forward`. Flag
   `fwd_dispersion` if $(\max F_K - \min F_K)/F > 0.5\%$ over the strikes used.
   - *Why 4 strikes nearest the money, not all strikes* (revised; the prototype used all strikes, ledger N1):
     - Away from the money, one leg of every pair is in the money. It carries the early-exercise premium, which
       biases $C-P$ and so $F_K$, in opposite directions on the two sides of $F$. It also has the widest spreads.
     - $|C-P|$ is the smallest exactly where both legs are near the money, so it picks those strikes without needing
       $F$ first.
     - The median of 4 survives one bad quote.
     - *What would make "all strikes" win:* a dense, liquid strip whose wing pairs pass the filter, with a measured
       $F_K$ that shows no trend in $K$.
   - On the worked example the choice moves $E$ by 27%. The rule is therefore part of the oracle test, and the test
     must fail if the forward uses all strikes.

   The discount factor is
   $DF = e^{-r\,\tau_{cal}/365}$, with $r$ the FRED 3-month T-bill rate (DTB3) converted to continuous compounding.
   **Interest accrues on calendar days; variance accrues on sessions.** These are two different clocks for two
   different things.
3. **Implied total variance per strike.** Use the out-of-the-money side: puts for $K<F$, calls for $K \ge F$. Solve
   $\text{mid} = \text{Black76}(F, K, w, DF)$ for $w$ with Brent's method on $[10^{-8}, 4]$. Black-76 depends on
   $\sigma$ and $T$ only through $\sigma\sqrt T = \sqrt w$, so **the price pins down $w$, and no day-count enters the
   variance clock here.** The one day count left is $DF$'s calendar clock, from step 2.
   - **No root (added after the review, ledger claim 4).** Black-76 is increasing in $w$, so a root exists exactly when
     $\text{Black76}(w = 10^{-8}) < \text{mid} < \text{Black76}(w = 4)$.
   - The lower end holds in practice, but not always (*corrected after the milestone-2 review*; this said it always
     holds): at $w = 10^{-8}$ an out-of-the-money price is about 0 against mid ≥ 0.05, except near the money on a
     high-priced stock. At $K = F$ the price at $w = 10^{-8}$ is about $DF\cdot F\cdot 4\times10^{-5}$, which reaches
     0.05 at $F \approx 1{,}253$; 2,437 `chain_expiry` rows (AMZN, AVGO, GOOGL, LLY, NFLX) have a forward above that.
     The code tests both ends (`black.has_root`), so nothing depends on it.
   - The upper end can fail. A call priced above Black76$(w = 4)$, which is $0.599\,DF\,F$ at the ledger's
     example, passes the bound $C \le DF\cdot F$, but has no root.
   - Such a strike is **invalid** (flag `iv_no_root`). It is dropped from the bracket and the quadratic fit. It is
     never solved on a wider interval and never clipped to $w = 4$.
4. **ATM by interpolation in log-moneyness.** With $k = \ln(K/F)$, take the closest valid strikes on each side,
   $k_{lo} \le 0 < k_{hi}$, and set $w_{atm} = w_{lo} + \frac{0-k_{lo}}{k_{hi}-k_{lo}}(w_{hi}-w_{lo})$. The bracket must
   satisfy $k_{hi}-k_{lo} \le 1.5\sqrt{w}$, meaning the two strikes are at most 1.5 standard deviations apart.
   Otherwise fit a quadratic in $k$, weighted by inverse **relative** spread $(ask-bid)/mid$ of the out-of-the-money
   quote, through valid strikes with $|k| \le 2\sqrt w$, with $w$ the bracket's own linear $w_{atm}$ (at least 4
   strikes, **at least one on each side of $k = 0$**, and $w(0) > 0$), and read $w(0)$ (`atm_method = quadratic`). With
   no valid strike on one side of the money there is no bracket and no fit. If that also fails, return null (status
   `no_atm`). **The ATM w is never extrapolated.**
   - *Revised after the milestone-2 review (claim 3b).* The fit used to run without a bracket too, on the strikes of
     one side, with its window drawn from the nearest strike's w. 166 of its 293 uses were such extrapolations.
     Hold-out on real chains (every `bracket_linear` expiry with τ ≥ 5 of the stage before the fix, 177,388 of them:
     hide strikes, run the fallback, compare with the known bracket IV; a scratch analysis, numbers in vol points):

     | Fallback | Hold-out fits | Median error | Median \|error\| | p95 \|error\| | Max \|error\| | Above 1 point |
     |---|---:|---:|---:|---:|---:|---:|
     | Quadratic on one side only (every strike on one side hidden) | 286,742 | +0.147 | 0.251 | 1.53 | 41.6 | 11.0% |
     | Two-sided quadratic, bracket too wide (one bracket strike hidden) | 2,812 | −0.109 | 0.199 | 1.15 | 11.7 | 6.4% |
     | Linear across the same too-wide brackets ("widen the bracket") | 2,812 | +0.218 | 0.273 | 1.16 | 9.8 | 6.9% |
     | The two-sided fit weighted by 1/absolute spread instead | 2,812 | −0.156 | 0.239 | 1.25 | 12.0 | 7.7% |
     | The two-sided fit unweighted | 2,812 | −0.133 | 0.215 | 1.15 | 11.8 | 6.7% |

     - So one-sided extrapolation is refused, and with it the nearest-strike w, which drew only its window.
     - On a too-wide bracket the two-sided quadratic and linear interpolation have the same p95. The quadratic has
       half the bias, because the chord of a convex smile lies above it. So the quadratic stays.
     - The review's 0.80 vol points for "widening the bracket" came from brackets that stayed under 1.5 sd once a
       strike was hidden: an ordinary bracket, not a too-wide one.
     - Of the three weightings, inverse relative spread has the smallest median and maximum error and the fewest
       misses above 1 point; its p95 ties the unweighted fit's (1.148 against 1.146).
   - The review's probe `p03` re-run on the fixed code, on its own 3,135 hold-out expiries:
     - with every strike at or below the money hidden, 3,109 now get no ATM, where 2,605 got a one-sided quadratic
       (p95 error 1.57, max 7.26);
     - with the lower bracket strike hidden, 3,055 stay `bracket_linear` (p95 0.80), and 24 get a two-sided quadratic
       (p95 1.18, max 1.49), where 31 got one before (p95 2.32, max 3.28).
5. **Time to expiry** $\tau$ = the number of NYSE sessions in $(t, \text{expiry}]$. The expiry session counts and the
   snapshot session does not, because it has already closed. Half sessions count as 1 (sensitivity: 0.5). An expiry
   is usable only if $\tau \ge 5$.
6. **Reported IV** $= \sqrt{252\,w/\tau}$ (session-annualised). It differs from calendar-annualised quotes for short
   expiries across holidays. AAPL 2025-11-14 on 2025-10-30: 28.3% session-annualised against 29.1% calendar-annualised.

We store $F$, $DF$, $\tau$, $\tau_{cal}$, $w_{atm}$, the bracket strikes and spreads, the vendor IV interpolated the same
way (for validation), and the interpolated ATM-forward straddle mid (for the cross-check in (c)).

### (a) Front ATM IV: two different things under one name

- **`front_atm_iv` (daily display series):** the shortest usable expiry ($\tau \ge 5$). It **rolls**, so it is used for
  display and vendor comparison only. It is never differenced across a roll.
- **`front_fixed_iv` (event-anchored):** for event $i$, fix **T1\*** = the shortest expiry on the day −1 snapshot with
  **τ ≥ 5 at day 0**, i.e. at least 5 sessions in (day 0, expiry].
  - *Revised after the review (ledger claim 13).* This said "at least 4 sessions to spare". That allowed τ = 4 at
    day 0, below the τ ≥ 5 usability rule of §0 step 5 that every other measure obeys. The two rules now agree on both
    crush days: τ ≥ 6 at day −1 and τ ≥ 5 at day 0. The vendor's front expiry is 7–11 sessions out, so the change
    rarely binds.
  - Follow *that same expiry* through the window while τ ≥ 5. After that, `front_fixed_iv` is null.
  - On a day when the vendor did not list T1\*, interpolate $w$ at $\tau(T1^*)$ from that day's expiries **of the same
    event class** (see (b)) and flag it `interpolated`.
  - The trader's crush is $\ln\sigma_{T1^*}(0) - \ln\sigma_{T1^*}(-1)$.

Why "first expiry after the event" and not "nearest expiry": the nearest pre-event expiry can expire *before* the
event, so it carries no event variance. It also rolls, which creates a fake jump. Why front crush is only secondary:
with the two-component model in (c), the front crush in variance terms is

$$
\sigma^2_{T1}(-1) - \sigma^2_{T1}(0) \approx \frac{252\,E}{\tau_1} + (\sigma^2_{d,\text{ann,pre}} - \sigma^2_{d,\text{ann,post}}),
$$

with every term an annualised variance (notation in (c), "Units"),

so its size scales with $1/\tau_1$, and $\tau_1$ is whatever the vendor listed (7–11 sessions here, not the 1–5 of a
weekly). It is not comparable across events, and it is smaller than what traders see on weekly options.

### (b) 30-day constant-maturity IV, event-aware (`cm30_iv`, primary daily series)

Target horizon $\tau^* = 21$ sessions (≈ 30 calendar days).

**The problem.** An earnings date splits a day's expiries into two classes. *Clean* expiries end before the next
event's day 0. *Spanning* expiries contain it: expiration ≥ day 0, because an expiry that settles at day 0's close
already reflects the news.

- *Revised after the milestone-2 review (claim 7): an AMC announcement on an expiry day.* With an after-close release
  on D, day 0 is the next session, but an expiry on D is not clean: its holders decide whether to exercise until
  5:30 p.m. ET (FINRA Rule 2360), after the news; and Cboe BZX's 2026 filing (SR-CboeBZX-2026-007) declines to list
  its extra expiries on a day with an after-close earnings release, citing the post-close volatility (both read by the
  review's Channel A). So an expiry spans when its last trading day, `as_of(expiration)`, is on or
  after **the first session on or after D**: day 0 for a BMO release or a release on a non-session day, D itself for
  an AMC release. An event without a label is anchored on next(D) and treated the same way, since under either label
  the expiry on D holds the news. This is conservative: a clean measure never reads such an expiry. At milestone 2 it
  moved 157 `chain_expiry` rows (141 usable) from clean to spanning, for 7 AMC and 16 unlabelled events.
- The horizon test of the rule below still counts sessions to day 0. A 21-session horizon that ends on an AMC day D is
  clean, and the expiry on D, now spanning, is not used for it: the clean measure stays free of the news.

Ordinary interpolation in total variance between a clean expiry $a$ and a spanning expiry
$b$, when the 21-session horizon itself *excludes* the event, gives

$$
w_{blind}(\tau^*) = \sigma_d^2\tau^* + E\,\frac{\tau^*-\tau_a}{\tau_b-\tau_a},
$$

**a leak of a fraction of E into a horizon that should not contain it.** ($\sigma_d^2$ is per session here, as in every
$w$; see (c), "Units".) On the vendor's grid the third expiry is 27–42 sessions out, so the leak starts about 40
sessions before the event, right inside the baseline.

**Size** (revised after the review, ledger N3; `research/prototypes/leak_grid.py`, output kept beside it). The first
version quoted one grid point, $\tau_a = 19$, $\tau_b = 32$: 0.26 vol points for E = 0.0007 and 1.1 for E = 0.003. The
range is wider. Assumptions:

- the clean expiry $a$ is the vendor's second, at 17–21 sessions;
- the spanning expiry $b$ is the third, at 27–42 sessions;
- each of the 80 $(\tau_a, \tau_b)$ pairs counts once;
- flat $\sigma_{d,\text{ann}}$ = 25%.

The leaked fraction $f = (21-\tau_a)/(\tau_b-\tau_a)$ then runs from 0 (whenever $\tau_a = 21$) to 0.40 (at 17, 27),
with median 0.13. The leaked IV is $\sqrt{\sigma_{d,\text{ann}}^2 + 252\,E f/21}$.

| E | median leak | maximum leak |
|---|---|---|
| 0.0007 | 0.21 vol points | **0.66** |
| 0.000883 (the worked example below) | 0.27 | 0.83 |
| 0.003 (a stock pricing a 5.5% move) | 0.90 | **2.73** |

That would contaminate the baseline and fake an "IV ends below baseline" result after the event.

**The rule:**

1. If the horizon contains the event (sessions from $t$ to day 0 $\le 21$), use only **spanning** expiries. Otherwise use
   only **clean** expiries.
2. Within the chosen class, interpolate $w$ linearly in $\tau$ between the expiries that bracket $\tau^*$. If there is no
   bracket but there are at least 2 expiries, extrapolate linearly, at most 10 sessions beyond the nearest.
3. If the class has a single expiry: for a *spanning* target, use the two-component fit from (c), taking $\sigma_d^2$ from
   the longest clean expiry and $E$ from the spanning one, so $w^* = \sigma_d^2\tau^* + E$. For a *clean* target, use
   flat $\sigma$, $w^* = w_C\,\tau^*/\tau_C$, if $|\tau^*-\tau_C| \le 10$. Otherwise return null.
4. Post-event, no listed expiry contains the *next* event. That event is about 63 sessions away and the longest listed
   expiry about 42. So post-event `cm30_iv` is plain interpolation over clean expiries.

**Why this is exact under the model.** If every expiry in a class has $w_j = \sigma_d^2\tau_j + c$ with the same $c$
($c=0$ for clean, $c=E$ for spanning), then $w$ is linear in $\tau$ inside the class, and linear interpolation reproduces
it exactly. Mixing classes breaks the linearity. That is where the leak comes from.

**Interpretation that must appear next to every run-up chart.** For $t \in [-21,-1]$,
$\sigma^2_{cm30} = \sigma_{d,\text{ann}}^2 + 252E/21$ in annualised variance terms. Most of the run-up in 30-day IV is *mechanical*:
it is the event variance entering the 30-day horizon. It is not evidence that the market grows more nervous. The
decomposition below is what separates the two.

`cm30_blind_iv` is the same session clock with all expiries interpolated, as CBOE does. It is kept as the series to
compare with VX\* and as a robustness variant. The gap between it and `cm30_iv` *measures* the leak.

### (c) Event variance E and implied move

**Model.** At time $t$, for each expiry $j$ with $\tau_j$ sessions to go,

$$
w_j = \sigma_d^2\,\tau_j + E\cdot\mathbb 1[\text{expiry } j \text{ spans the event}]
$$

Here $\sigma_d^2$ is the ordinary (diffusive) variance per session, assumed flat across the term structure, and $E$ is the
extra variance of the event-day jump, in squared-log-return units.

**Derivation with two spanning expiries** $\tau_1 < \tau_2$:

$$
w_1 = \sigma_d^2\tau_1 + E,\qquad w_2 = \sigma_d^2\tau_2 + E
$$
$$
\Rightarrow\quad \sigma_d^2 = \frac{w_2-w_1}{\tau_2-\tau_1}\qquad\text{(the forward variance between the two expiries, which contains no event)}
$$
$$
\Rightarrow\quad E = w_1 - \sigma_d^2\tau_1 = \frac{w_1\tau_2 - w_2\tau_1}{\tau_2-\tau_1}.
$$

**Units** (notation fixed after the review, ledger claim 13: the first version used $\sigma_d^2$ for both a per-session
and an annualised variance, so H7 in ADR 0005 was off by 252× if implemented with the stored column).

- $w_j$ and $E$ are in squared-log-return units (dimensionless). $\tau_j$ counts sessions.
- **$\sigma_d^2$ always means the diffusive variance per session**, as in the model above.
- **$\sigma_{d,\text{ann}}^2 = 252\,\sigma_d^2$** is the annualised variance. It appears next to $252E/\tau$ in (a) and
  (b) above, and in ADR 0004 §3.
- **Every stored σ_d column is $\sigma_{d,\text{ann}}$, an annualised volatility** (a decimal like an IV, not a variance):
  `iv_daily.sigma_d_iv`, `event_window_obs.sigma_d_iv`, `event_measures.sigma_d_m1`. The per-session variance is
  therefore $\sigma_d^2 = \texttt{sigma\_d}^2/252$.
- Wherever $E$ and the ordinary variance are *added*, both are in $w$ units: $E + \sigma_d^2 = E +
  \texttt{sigma\_d}^2/252$. That is the case in `implied_abs_move_total` below and in ADR 0005's H7.
- `dsigma_d_*` is a log change, $\tfrac12\ln$ of a variance ratio, so it has no units.

The IVs the pipeline reports are **session-annualised**: $\sigma_j = \sqrt{252\,w_j/\tau_j}$ (step 6 of §0), so
$w_j = \sigma_j^2\,\tau_j/252$. In terms of reported IVs the textbook form therefore carries a factor 252:

$$
E = \frac{\tau_1\tau_2\,(\sigma_1^2-\sigma_2^2)}{252\,(\tau_2-\tau_1)},\qquad
\sigma_{d,\text{ann}}^2 = 252\,\sigma_d^2 = \frac{\sigma_2^2\tau_2-\sigma_1^2\tau_1}{\tau_2-\tau_1}.
$$

This matches the brief's formula $E = T_1T_2(\sigma_1^2-\sigma_2^2)/(T_2-T_1)$ when time is in **years**,
$T_j = \tau_j/252$. Writing it with $\tau$ in sessions and *without* the 252, while keeping annualised σ, is wrong by
a factor of 252. On the worked example below that gives 0.2225 instead of 0.000883. Check by substitution, with
$w_j = \sigma_j^2T_j$: $\sigma_1^2T_1 - T_1\frac{\sigma_2^2T_2-\sigma_1^2T_1}{T_2-T_1}
= \frac{\sigma_1^2T_1T_2 - \sigma_2^2T_1T_2}{T_2-T_1}$ ✓.

**The unit test, and why it can fail** (revised after the review, ledger N4). The prototype's first "identity check"
set $s_j = w_j/\tau_j$ and compared $E$ with an expression that reduces to the same formula, so it could not fail.

- **What the test does.** It feeds the $w$-form the stored $w_j$. It feeds the textbook form the IVs the pipeline
  *reports*, $\sigma_j = \sqrt{252\,w_j/\tau_j}$ from the same function that writes `iv_atm`, with $T_j = \tau_j/252$
  in years. The two must agree to a relative 1e-12.
- **Result on the worked example.** They differ by 3.4e-18 on the unrounded $w$.
- **What it catches.** If the reporting function or the textbook form loses its 252, the two differ by exactly that
  factor.
- **Proof that it can fail.** The test runs a second time with the planted bug ($T$ in sessions). It must fail
  there, and `worked.py` shows it does (0.2225 against 0.000883).
- **A consistency check on rounded inputs (not independent).** The 4-decimal IVs printed in the table below give
  $11\cdot20\,(0.2826^2-0.2660^2)/(252\cdot9) = 0.000883$. This agrees with $E$ to within rounding: 0.00088337
  against 0.00088284. *Corrected after the delta review (10c, 3b):* this was called "a second, independent oracle".
  It is not independent. The printed IVs come from the same $w$, forward and session counts as $E$, so it only
  confirms that the table and $E$ agree with each other.
- **What the identity check does not catch** (delta ledger 3b, N6; re-run for this revision with
  `docs/validation/probes/m0-delta/d3_worked_mutants.py`, which plants each bug in a copy of `worked.py`). With each
  of these, the script still exits 0:
  - **a wrong forward:** the median over all strikes instead of the 4 nearest the money, ledger N1's own bug. It
    gives E = 0.00069327.
  - **a wrong session count:** 12 sessions instead of 11 in $E$, giving E = 0.00029116. The check feeds both of its
    formulas the literals 11 and 20, not the count $E$ used.
  - **a wrong ATM interpolation:** the lower strike's $w$ only, giving E = 0.00008131.
  - **a wrong discount factor:** a 360-day year, giving E = 0.00088266.
  - *Added after the delta-2 review (claim 6):* **a wrong Black-76 $d_1$** (+w instead of +w/2: E = 0.00087993),
    **the ITM side instead of OTM** (E = 0.00192540, +118%), and **bid instead of mid** (E = 0.00053567). Each also
    exits 0, so the IV inversion, the side choice and the quote mid each need their own milestone-2 oracle too.

  The rounded-input check above is done by hand and is not automated. It would flag the session-count bug, whose
  $E$ disagrees with the table's τ = 11. It would not flag a forward, interpolation or session count that is wrong
  in the table and in $E$ alike, because the printed IVs then move with $E$.

  What protects these lies outside both checks. The forward rule has an independent hand selection of the 4 strikes
  (delta ledger 3a: the mid $|C-P|$ values select 267.5, 272.5, 275 and 277.5, median 271.42). The other three have
  no independent check yet. So the milestone-2 unit tests of the forward, the session count to expiry (11 and 20
  here, countable by hand on the NYSE calendar), the ATM interpolation and the discount factor each need their own
  hand-worked oracle. The identity check does not stand in for them.

**The clock matters, and here is exactly how.** The prices fix $w_1$ and $w_2$. The clock only enters through the ratio
$\rho = \tau_2/\tau_1$:

$$
E = w_1 - \frac{w_2-w_1}{\rho - 1}.
$$

A larger $\rho$ gives a larger $E$. Calendar days count a weekend as 3 days and Thanksgiving as 1, so $\rho$ moves with
whichever interval happens to hold more non-trading days. **Decision: sessions.** Variance accrues mainly while the
market trades. French & Roll (1986) found weekend return variance far smaller than three weekdays' worth. Dubinsky &
Johannes count trading days. Option desks use business-day time. Sensitivity: weight each non-session calendar day at
0.1 of a session (`params.nonsession_weight`).

**When.** E is read at day −1. For AMC events, day −1 *is* the announcement day, and its closing quotes are visibly
wider (AAPL 2025-10-30). So E is also computed at day −2 as a robustness check. Under the model it is the same quantity,
since τ counts sessions. If AMC events show a markedly larger gap between E(−1) and E(−2) than BMO events do, E(−2)
becomes primary for AMC events.

**Which expiries.** On day −1, T1 = the shortest spanning expiry with $\tau \ge 5$, and T2 = the next spanning expiry.
*Made explicit after the milestone-2 review (claim 8):* both are **usable** expiries, `ok` with $\tau \ge 5$, so a
spanning expiry without an ATM $w$ (`no_atm`, `no_forward`) is skipped and the next usable one takes its place. E needs
each expiry's $w$, and under the model any two spanning expiries give the same E; the cost is a longer T2, so $\sigma_d^2$
is the forward variance over a longer stretch. Dropping E on such a day instead would lose it on 235 of the 19,601
`iv_daily` rows with an E (re-measured after the review's fixes; 207 of 19,573 before them). Without two usable
spanning expiries, `sigma_d_iv` falls back to the forward variance of the **two shortest** clean expiries
(`termstructure.day_measures`; the test `test_sigma_d_without_e_comes_from_the_two_shortest_clean_expiries` fails if
it takes the two longest). With
three spanning expiries, also fit $(\sigma_d^2, E)$ by least squares on all three as a robustness check. The residual
diagnoses curvature in the diffusive term structure. E is also stored daily in `iv_daily` whenever two spanning
expiries exist, so the path of E through the run-up can be plotted.

**Worked example (this is the hand-worked oracle for the test).** AAPL Q4 FY25, AMC 2025-10-30, so day −1 = 2025-10-30
and day 0 = 2025-10-31. Mid quotes are from DoltHub `options` (CC BY-SA 4.0), r = 3.9%, OTM side, linear in $k$, and
the forward from the 4 strikes with the smallest $|C-P|$ (§0 step 2). Re-run on 2026-10-28 with
`research/prototypes/worked.py` (output in `worked.out.txt`) after the review found that the first table did not
follow step 2.

| snapshot | expiry | strikes in the forward ($F_K$) | $F$ (parity) | bracket | $w_{atm}$ | $\tau$ sessions / cal days | IV (×252/τ) | IV (×365/cal) |
|---|---|---|---|---|---|---|---|---|
| 10-30 (−1) | 11-14 | 267.5, 272.5, 275, 277.5 (272.06, 271.35, 271.49, 271.34) | 271.42 | 267.5 / 272.5 | 0.003486 | 11 / 15 | 0.2826 | 0.2913 |
| 10-30 (−1) | 11-28 | 265, 270, 275, 280 | 272.06 | 270 / 275 | 0.005616 | 20 / 29 | 0.2660 | 0.2659 |
| 10-31 (0) | 11-14 | 267.5, 270, 272.5, 275 | 270.55 | 270 / 272.5 | 0.002217 | 10 / 14 | 0.2364 | 0.2404 |
| 10-31 (0) | 11-28 | 265, 270, 275, 280 | 270.95 | 270 / 275 | 0.004179 | 19 / 28 | 0.2354 | 0.2334 |

Only the first row changed. Its 7 quoted strikes give $F_K$ from 271.34 to 272.09. The 4 nearest the money give a
median of 271.42, where all 7 gave 271.69. The other expiries have exactly 4 strikes in the example.

Session clock, computed from the **unrounded** $w$ (the exact values, and the test oracle):

- $\sigma_d^2 = (w_2-w_1)/9 = 2.3667\times10^{-4}$ per session, which is $\sigma_{d,\text{ann}}$ = 24.4%.
- $E = w_1 - 11\,\sigma_d^2 = 0.000883$ (0.00088284).
- Redoing the arithmetic with the table's 6-decimal $w$ gives $E$ = 0.00088267. The difference is rounding in the
  table, not a different method.

**Implied move $\sqrt E$ = 2.97%.** The expected absolute event move, $\sqrt{2/\pi}\sqrt E$, is 2.37%.

- **The clock.** With the calendar clock instead, $E = 0.001204$ and $\sqrt E$ = 3.47%. **The clock alone changes the
  implied move by 17%** (the variance by 36%).
- **What happened.** The realised close-to-close return on day 0 was −0.38%, after a +2.06% overnight gap that faded.
  The front fixed-expiry IV went from 28.3% to 23.6%, a crush of 4.6 vol points (−0.179 in logs).

*The 10-30 quotes were wide, so this example demonstrates the arithmetic. It is not a claim about AAPL's typical
implied move. The forward rule alone moved $E$ by 27% here, which is a measure of how much wide announcement-day
quotes can matter. It is one more reason to compute $E$ at day −2 too (below).*

**Implied move definitions** (all stored):

- `implied_move` $= \sqrt E$: the standard deviation of the event jump (D-J's definition).
- `implied_abs_move` $= \sqrt{2/\pi}\,\sqrt E \approx 0.798\sqrt E$: the expected $|\text{jump}|$ if the jump is normal.
- `implied_abs_move_total` $= \sqrt{2/\pi}\,\sqrt{E + \sigma_d^2}$, with $\sigma_d^2$ per session
  ($= \texttt{sigma\_d\_m1}^2/252$): the expected $|r_0|$. The realised day-0 return spans one ordinary session *and*
  the news, so **this** is what $|r_0|$ is compared against. In the example it is 2.67%.

**When E ≤ 0.** This happens exactly when the session-annualised IVs satisfy $\sigma_1 \le \sigma_2$, i.e. no inverted term structure.
The causes are a small event lost in quote noise, an upward-sloping diffusive term structure (for example an FOMC
meeting inside T2 only), or a wrong date. Policy:

- **Store E signed.** `implied_move` is null when E ≤ 0, with status `nonpositive_event_variance`.
- **Aggregate in variance space.** The average implied move of a group is $\sqrt{\overline{E}}$ over *all* its events, with
  E signed. Averaging $\sqrt E$ over the E > 0 subset only would be selection and would bias upward. Flooring at 0 would
  also bias upward.
- **Test unbiasedness in variance space**: regress $r_0^2$ on $E + \sigma_d^2$, with $\sigma_d^2$ per session (slope 1,
  intercept 0 under unbiasedness).
  This uses every event. Ratios like $|r_0|$ / `implied_abs_move_total` use E > 0 events only, and say so.
- Report the share of E ≤ 0 per subgroup. A high share is a finding in itself.

**Straddle cross-check.** The ATM-forward straddle ($K = F$) is exactly

$$
\Pi = C+P = 2\,DF\,F\,\big[2N(\tfrac{\sqrt w}{2})-1\big] \approx DF\cdot F\cdot\sqrt{2/\pi}\,\sqrt w ,
$$

since $2N(x)-1 \approx 2x/\sqrt{2\pi}$ for small $x$; this is Brenner & Subrahmanyam's 0.8·F·σ√T. It has two uses:

1. *Consistency:* invert $\Pi$ to get $w_{straddle}$ and compare it with $w_{atm}$. Flag differences above 0.5 vol points.
2. *Explaining the headline number:* $\Pi_{T1}/(DF\,F)$ is the "implied move" that trading platforms quote. It covers T1's
   whole life. In the example it is $0.798\sqrt{0.003486}$ = **4.71%**, against an event-only 2.37%.
   - **Three quarters of T1's variance is ordinary diffusion** over the 11 sessions to T1 ($E/w_1$ = 25%).
   - So the event-only expected move is about half the quoted one.
   - On weekly options the diffusion share would be much smaller. That is why we do not use the straddle as our
     implied move.

### (d) Recompute from mids; never trust the vendor `vol`

Measured on AAPL 2025-11-14, 2025-10-31 snapshot. The vendor `vol` sits against our IV at the same strike, solved
calendar-annualised like the vendor's:

| strike | vendor call / put | ours |
|---|---|---|
| 267.5 | 0.2402 / 0.2394 | 0.2422 |
| 270.0 | 0.2398 / 0.2377 | 0.2405 |
| 272.5 | 0.2384 / 0.2374 | 0.2403 |
| 275.0 | 0.2386 / 0.2374 | 0.2405 |

The vendor is 0.1–0.3 vol points lower, and its calls and puts disagree. Ours agree by construction, because the parity
forward makes call and put identical in a European model. Small, but systematic, and on announcement days the vendor
disagreement reaches 3 vol points.

**American exercise.** Black-76 is European, while US single-stock options are American. We measured the error with a
2,000-step binomial tree (S = 271.4, σ = 27%, r = 3.9%, no dividends):

| put | early-exercise premium | IV bias | bias in the parity forward |
|---|---|---|---|
| 1.5% OTM, 15 days | $0.016 | 0.08 vol points | 0.6 bp |
| ATM, 15 days | $0.026 | 0.12 vol points | 1.0 bp |
| 1.5% OTM, 50 days | $0.079 | 0.20 vol points | 2.9 bp |
| ATM, 50 days | $0.103 | 0.26 vol points | 3.8 bp |

Using the OTM side keeps us near the top rows. The bias is a level shift that largely cancels in crushes and term
differences.

- **Propagation into E.** The review pushed the tree prices through this pipeline (4-strike parity, OTM side, linear
  in $k$) and measured −2.5% of E at three spot levels around the AAPL example (ledger claim 4; the European control
  gave +0.04% to −0.01%).
- The share grows as $E/w_1$ falls, so names with small events are biased more.
- It is documented, not corrected.

**Validation plan (milestone 2), in order of independence:**

1. **CBOE VX\*** (VXAPL, VXAZN, VXGOG, VXGS, VXIBM; daily CSVs, still published, last modified 2026-10-27 according
   to a HEAD request; the 2011 start date was not verified). These are VIX-method 30-day indices built from the *whole*
   OTM strip, so they sit *above* ATM IV by a skew/convexity spread. Compare `cm30_blind_iv` with VX\* on: (i) the
   correlation of daily log changes (expect > 0.8); (ii) the slope of VX\* changes on ours (expect ≈ 1); (iii) a stable
   level spread with no breaks; (iv) the day-0 crush ratio (expect 1 ± 0.2). VXGOG is on GOOG; our universe holds
   GOOGL. The two share classes trade nearly identical IV; noted. Only aggregate statistics are exported, never the series.
2. **The vendor `vol`**, run through the same ATM interpolation on non-event days: median |difference| < 0.5 vol points,
   with outliers listed.
3. **`volatility_history.iv_current`**: regress it on our ATM IV at horizons of 10…60 sessions to *identify* its maturity.
   This is a third check only.

### (e) Realised move

$r_0 = \ln(S_0/S_{-1})$ is computed **from the same option snapshots**. For an expiry T quoted on both days:

$$
r_0 = \ln\frac{F_0(T)}{F_{-1}(T)} + r\,\frac{\Delta_{cal}}{365}.
$$

The carry term is about 1 bp per calendar day. Because the forward already nets out dividends, this is a total return, even
across an ex-dividend date. Example: $\ln(270.55/271.42) + 0.011\% = -0.31\%$, within 0.1 point of the official close-to-close return (a Yahoo value, so not quoted). Yahoo
closes are used locally to cross-check, with the median |difference| reported. Why not use Yahoo directly: (1) a per-event
realised move then counts as Yahoo data in the exported scatter (ADR 0001 §7); (2) the parity spot is taken at the *same
instant* as the IVs it is compared with.

## Consequences

- Good: every IV number is reproducible from public quotes, with no vendor inputs we cannot see.
- Good: the crush splits into two parts: event variance removed, $E$, and a change in ordinary vol, $\Delta\sigma_d$. That
  split is what makes "persistence" and "drivers" interpretable.
- Cost: four nested concepts (atom, class, horizon, decomposition) to explain. Each gets its own pure function and
  hand-worked test.
- Cost: the session clock means our IV levels differ from broker quotes for short expiries across holidays. The difference
  is documented, and log changes are unaffected.
- Risk: the flat-σ_d assumption. An upward-sloping diffusive term structure biases E down; a downward one biases it up. The
  market-condition split (VIX regime) in milestone 4 will show it.

## Alternatives rejected

| Alternative | Why rejected | What would make it win |
|---|---|---|
| Trust the vendor `vol` and greeks | Opaque inputs, call/put disagreement up to 3 vol points on event days, unknown day count. It cannot be defended line by line. | The vendor documents its method and it reproduces our numbers within 0.1 vol points. |
| Black-Scholes with Yahoo spot and a dividend yield | Needs an as-of, unadjusted spot taken at the same instant as the options, plus a dividend forecast. The parity forward gets both from the snapshot itself. | No strike is quoted on both sides. |
| American binomial with discrete dividends | Correct for early exercise, but it needs a dividend schedule and is slower. The measured bias of the European shortcut is ≤ 0.26 vol points in level and mostly cancels. | A result depends on IV *levels* at the ~0.3 vol-point scale. |
| ATM = nearest strike | The strike grid is sparse and changes daily (the 270 strike missing on 10-30). The nearest strike can jump 1–2% in moneyness, which with skew creates fake day-to-day IV changes. | Strikes are dense (every 1%) and stable. |
| Average of call and put IV at each strike | Equivalent in a European world with the parity forward. In the American world the ITM leg carries the early-exercise premium and wider spreads. | Never better than OTM-side. |
| ATM at 50-delta | Delta needs σ (circular), and the vendor delta is unreliable. | Never here. |
| Calendar-day clock | Treats weekends and holidays as full variance days. In the AAPL example it inflates E by 36%. | Evidence that weekend variance ≈ 3 weekdays' worth, which it is not. |
| Event-blind 30-day interpolation as primary | Leaks a fraction of E into baseline days 40 sessions before the event. Kept as validation and robustness. | The measured leak averages < 0.1 vol points (see below). |
| Model-free (VIX-style) variance from our chain | 19–27 irregular strikes with thin wings; the truncation error is unknown. | The chain gains dense wings. It may be added later for a like-for-like VX\* comparison. |
| Drop events with E ≤ 0, floor E at 0, or use \|E\| | Each one biases the average implied move upward (selection or truncation). \|E\| is meaningless. | Never. |

## How we'll know it's wrong

- **The VX\* checks fail**: correlation of daily changes < 0.8, slope outside [0.8, 1.2], or the day-0 crush ratio outside
  [0.8, 1.2] for most of the five names. Then the atom (forward, filters, interpolation) is wrong before anything else is.
- **`cm30_iv` and `cm30_blind_iv` differ by less than 0.1 vol points on average in the baseline**: the event-aware machinery is
  unnecessary complexity. Switch to the blind version and say so.
- **E ≤ 0 for more than about 25% of events with clean data**, or E ≤ 0 clusters in particular VIX regimes: the
  flat-diffusive-term-structure assumption is failing. Move to the 3-expiry fit with a term-structure slope.
- **The parity-forward realised move disagrees with Yahoo by more than 10 bp in median**: the forward is noisier than
  assumed. Use the Yahoo close locally and export only binned aggregates.
- **The synthetic-truth test** (a two-component surface on the real sparse strike grid) fails to recover E and σ_d to 1e-6:
  there is a bug, whatever the real data says.

## References

- Dubinsky, A. & Johannes, M., *Earnings announcements and equity options*, working paper, Columbia Business School (the PDF
  read for docs/concepts/00-background.md is dated September 2004; later versions circulated as *Fundamental uncertainty,
  earning announcements and equity options*, 2006). Published version: Dubinsky, Johannes, Kaeck & Seeger (2019), *Option
  pricing of earnings announcement risks*, Review of Financial Studies 32(2), doi:10.1093/rfs/hhy060.
- Patell, J. & Wolfson, M. (1979), *Anticipated information releases reflected in call option prices*, J. Accounting & Economics.
- French, K. & Roll, R. (1986), *Stock return variances: the arrival of information and the reaction of traders*, J. Financial Economics.
- Brenner, M. & Subrahmanyam, M. (1988), *A simple formula to compute the implied standard deviation*, Financial Analysts Journal.
- Black, F. (1976), *The pricing of commodity contracts*, J. Financial Economics.
- CBOE, *VIX White Paper* (methodology used by the single-stock VX\* indices).
