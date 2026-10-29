# Abnormal IV and the market adjustment

Concept note for milestone 3. Written 2026-10-29. The decision is [ADR 0004 §2–§3](../adr/0004-baseline-and-event-windows.md)
and [ADR 0005 §1](../adr/0005-statistical-test-suite.md); the code is `src/earnings_vol/panel/abnormal.py` and
`panel/window.py`; the tests are `tests/test_panel.py` and `tests/test_ramp_identity.py`.

## 1. "Abnormal" means: compared with what?

An event study asks how a quantity behaves around an event **relative to what it would have done anyway**. For returns
the "anyway" is a market model. For implied volatility (IV) we use two references:

- **the event's own baseline**: its mean log IV over the clean sessions $B_i$ of rel_day [−60, −22], minus other events'
  zones, missing sessions and sessions without a 30-day IV (ADR 0004 §1);
- **the market's volatility**: ln VIX, the 30-day S&P 500 implied volatility, the same horizon as our `cm30_iv`.

## 2. Why logs

A crush is proportional. A 60%-IV name loses more vol points than a 20%-IV name on similar news, but about the same
**percentage**. So $x_t = \ln\sigma_t$, and differences of $x$ are percentage changes ("log points": −0.20 ≈ −20%).
Vol points (`aiv_level`) are kept for display only.

## 3. The formulas

For event $i$ of company $s$, with $m_t = \ln \text{VIX}_t$:

| Quantity | Formula | Role |
|---|---|---|
| baseline means | $\mu_i = \overline{x}_{B_i}$, $\mu^m_i = \overline{m}_{B_i}$ | the reference level |
| market beta | $\beta_s = \sum \Delta x\,\Delta m / \sum (\Delta m)^2$, **no intercept**, over the clean one-session baseline changes of **every** event of $s$ whose baseline passes the 20/15 minimum, each date once | how much the company's IV moves with VIX |
| abnormal change | $e_t = \Delta x_t - \beta_s\,\Delta m_t$ | the crush, the baseline scale |
| abnormal level (ALIV) | $(x_t-\mu_i) - \beta_s(m_t-\mu^m_i)$ | run-up, persistence, the paths |
| mean-adjusted twin | $x_t - \mu_i$ | robustness, and every committed per-event value |

**No intercept**: log IV mean-reverts rather than trends, and an intercept estimated from about 30 noisy changes would
add noise to every abnormal change without removing a bias (ADR 0004 §2).

**Pooled β**: one baseline has about 30 changes; pooling a company's passing baselines gives about 240 (measured:
median 238, range 118–297 over the 50 companies). The measured β has median 0.31 (range 0.07–0.52): a company's log IV
moves about a third as much as log VIX on a typical day, so β = 1 would over-adjust (one of ADR 0004's rejected
alternatives). *Corrected after the milestone-3 review:* the first build also pooled the changes of 632 events whose
baseline fails the minimum, which ADR 0004 §1 says "gets no baseline" (median 0.36 then).

**What β may use.** No session of any event window, its own event's or another of the company's: its changes all lie
in clean baselines. But it does use the baselines of the company's *later* events (1,209 of the 1,259 events have a β
change dated after their day +10). ADR 0004 §2 allows that, because the study describes the past rather than forecasts
it; "β uses no information from after the event" would be false.

## 4. What is tested, and why not "CAAIV"

| Name | Definition | Question |
|---|---|---|
| RUNUP | ALIV at day −1 | Is IV abnormally high at the last close before the news? |
| CRUSH | $e$ from day −1 to day 0 | How much does IV fall when the news arrives? |
| PERSIST_h | ALIV at day +h, h = 1, 5, 10 | Is IV back at its baseline h sessions later? |
| ΔSIGMA_D | ½ ln(σ_d²(0)/σ_d²(−1)) − β Δm₀ | Did *ordinary* volatility change? |

Summing abnormal **levels** (the returns-style "cumulative abnormal" quantity) would count a persistent shift once per
day; the sum of abnormal **changes** telescopes into a difference of two levels, which is exactly ALIV. So the levels
are tested directly (ADR 0004 §3).

## 5. One representation: weighted sums of changes, gaps included

Every tested quantity is $A_i = \sum_t a_{i,t}\, e_{i,t}$. For RUNUP and PERSIST the weights ramp up across the baseline:
walk the usable sessions $o_0 = \min B < o_1 < \dots < o_K = t$ and give the change into $o_k$ the weight
$n(o_k)/|B|$, with $n(o)$ the number of baseline sessions before $o$. Then

$$\text{ALIV}_t = \sum_k \frac{n(o_k)}{|B|}\Big[(x_{o_k}-x_{o_{k-1}}) - \beta (m_{o_k}-m_{o_{k-1}})\Big]$$

**exactly**, even across missing sessions, because $x_t - x_u$ telescopes over the changes after $u$ and every baseline
session is usable. Worked (in the code's header and in `test_header_worked_example`): B = {0, 1, 3}, usable
{0, 1, 3, 4, 6}, x = 0, 1, ·, 4, 2, ·, 5: weights 1/3, 2/3, 1, 1 give 1/3 + 2 − 2 + 3 = 10/3 = 5 − 5/3. The identity
is what lets one weight vector give both the value and its variance $s_i^2\,a^\top R a$ (concept note 11).

## 6. The licence consequence

$e_t$ and ALIV contain VIX, which is Cboe data. Committed next to the committed `d_ln_cm30` and β, a market-adjusted
per-event value would give back Δ ln VIX on its dates. So the per-row market-adjusted columns (`*_cboe`, and β itself
as `beta_vix_cboe`) stay local; only **aggregates** (means, tests, the mean path) are committed, under the owner's
decision of 2026-10-29. Every per-event and per-company number in the app is mean-adjusted.

## 7. What can go wrong

- **Megacaps move VIX themselves** (NVDA, AAPL, MSFT): the adjustment removes part of their own effect. Robustness in a
  later milestone: drop the 10 largest index weights.
- **Mean- and market-adjusted crushes should agree** for a one-session change (ADR 0004: within 10%). Measured at
  milestone 3: see the milestone page.
- **Common noise not explained by VIX.** The market-adjusted baseline changes of different companies on the same date
  are still correlated: 0.29 across sectors and 0.36 within (mean pairwise correlation), and Pynnönen's
  $\hat{\bar\rho}$ on the primary sample's baseline changes is 0.30, above ADR 0005's "about 0.2" warning line, which
  suggests either that VIX leaves much of the common factor in place (β ≈ 0.31) or a common data effect such as a
  shared snapshot time. It is open (milestone page, §8). Every primary test clusters by date (CRUSH) or season (ramps)
  as well as by company, which covers same-date correlation of any form.
