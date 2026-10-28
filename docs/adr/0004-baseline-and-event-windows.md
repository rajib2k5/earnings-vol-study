# ADR 0004: Event window, baseline and the definition of abnormal IV

- **Status:** Accepted (milestone 0), **revised 2026-10-28 after the milestone-0 methodology review** (note below)
- **Date:** 2026-10-28
- **Related:** [0002 day 0](0002-day-zero-convention.md), [0003 IV measures](0003-iv-measures.md),
  [0005 tests](0005-statistical-test-suite.md), [data model](../architecture/data-model.md) (`event_window_obs`, `event_measures`)

> **Revised after milestone-0 review** ([ledger](../validation/m0-methodology-ledger.md)).
>
> 1. **Refuted wording: "day −60 falls inside the previous event's [0, +10] window in 97.1%" (ledger claim 5).** The
>    numbers reproduce, but 97.1% is P(gap ≤ 70). That is the share of gaps in which the fixed [−60, −20] baseline
>    **overlaps** the previous report's [0, +10] window. Day −60 itself lies inside that window in 83.3% of gaps.
>    - Corrected statement: *a fixed [−60, −20] baseline overlaps the previous report's [0, +10] window in 97.1% of
>      gaps and contains its day 0 in 20.3%.*
>    - The decision does not change.
> 2. **Changed with ADR 0003's worked example (ledger N1).** The AAPL crush split in §3 is now −12.3% = −4.1% − 8.2%.
>    It was −12.4% = −6.1% − 6.3%.
> 3. **Notation (ledger claim 13).** §3 now writes the annualised diffusive variance as σ²_d,ann (ADR 0003 §c, "Units").
> 4. **Gaps (ledger claim 6).** The coarse sample's span changes and the run-up/persistence representation across
>    unobserved sessions are specified in ADR 0005 §1.

## In one paragraph

The event window is [−10, +10] sessions. The baseline is **[−60, −22]**, minus every session that falls in another
event's [−21, +10] zone, and it must keep at least 20 clean sessions. The end moves from −20 to −22 because the 30-day
horizon of `cm30_iv` already contains day 0 from session −21 onward. The exclusion is needed because quarterly events are
about 63 sessions apart. A fixed [−60, −20] baseline would overlap the *previous* report's [0, +10] window in 97% of
gaps and contain its day 0, the crush itself, in 20%.
Abnormal IV is measured in **log IV, market-adjusted with VIX** (β estimated per firm from its pooled clean baselines). It
is also shown in vol points. **CAAIV is not tested.** IV is a level, not a flow, so summing abnormal levels counts one
persistent shift many times. The cumulative sum of abnormal *changes* collapses to a difference of two levels, so we test
those levels directly:

- **run-up** at −1;
- **crush** from −1 to 0;
- **persistence** at +1, +5 and +10;
- the **event variance** E;
- the **change in ordinary volatility** Δσ_d.

## Context

- The brief proposed an event window of [−10, +10] and a baseline of [−60, −20], and asked about the overlap.
- **Measured spacing between consecutive events** for 30 large S&P 500 names (calendar 2024-01 → 2026-10, day 0 per
  ADR 0002, NYSE sessions; 306 gaps):

  | min | p5 | p25 | median | p75 | max |
  |---:|---:|---:|---:|---:|---:|
  | 53 | 57 | 61 | **63** | 64 | 127 |

  With a gap of g sessions, a fixed [−60, −20] baseline sits at [g − 60, g − 20] relative to the previous report's day
  0, so:
  - it **overlaps the previous report's [0, +10] window in 97.1%** of gaps (20 ≤ g ≤ 70);
  - it **contains the previous report's day 0 in 20.3%** (20 ≤ g ≤ 60).

  An earlier version said day −60 falls *inside* the previous [0, +10] window in 97.1%. That share is 83.3%
  (60 ≤ g ≤ 70); the 97.1% is the overlap. The gaps above 80 sessions come from missing calendar events (GS: 127 and
  123; COST: 113 and 114; ADR 0002). Costco's normal 16-week quarter gives 82.
- **The 30-day horizon.** At session t, `cm30_iv` covers the sessions (t, t+21]. At t = −21 that range includes day 0,
  and at t = −22 it does not. The front expiry (7–11 sessions) contains the event only from about day −11.
- **IV is persistent.** Today's level is mostly yesterday's level. Daily changes are much closer to independent than
  levels are, though quote noise probably makes them somewhat negatively autocorrelated (ADR 0005 §1). Event-study
  formulas written for returns (flows) do not carry over to levels unchanged.
- **Daily data** runs 2024-09-11 → 2026-10-26: 533 sessions, measured with an NYSE holiday list.

## Decision

### 1. Windows

- **Event window:** rel_day ∈ [−10, +10]. That is long enough to show the front expiry absorbing the event (from about
  −11) and two weeks of afterwards. Any longer and the post-window runs into the next event's 30-day run-up (+42 at a
  spacing of 63).
- **Baseline:** start from [−60, −22], then remove every session that is
  1. inside **[−21, +10] of any other event of the same security**: that event's 30-day run-up or its event window.
     Orphan-period and pre-calendar zones from ADR 0002 count as events here. An event whose timing stayed
     ambiguous (ADR 0002 §2) has no day 0, so its zone is [−21, +10] around **both** candidate days.
  2. not observed (`missing` or `stale_repeat`, ADR 0002 §1), or missing `cm30_iv`.
- **Minimum:** at least 20 clean sessions and at least 15 one-session changes (both ends clean). Below that, the event
  gets no baseline and is excluded from every measure that needs one. Measured on the spacing above, *before* data
  gaps: the clean count is min 21, p5 25, **median 31**, and 100% have at least 20. In practice the baseline is about
  [−52, −22].

### 2. Abnormal IV, precisely

Notation for event *i* of security *s*:

- $\sigma_t$ = `cm30_iv` on session $t$ (primary); $x_t = \ln \sigma_t$.
- $m_t = \ln \text{VIX}_t$ (FRED VIXCLS; 30-day S&P 500 implied vol, the same horizon as cm30).
- $B_i$ = the clean baseline sessions; $\Delta x_t = x_t - x_{t-1}$, used only when both sessions are observed.

| Quantity | Formula | Units | Role |
|---|---|---|---|
| baseline log level | $\mu_i = \frac{1}{\lvert B_i\rvert}\sum_{t\in B_i} x_t$ | log | reference |
| VIX baseline | $\mu^m_i = \frac{1}{\lvert B_i\rvert}\sum_{t\in B_i} m_t$ | log | reference |
| market beta | $\beta_s$ = OLS slope of $\Delta x_t$ on $\Delta m_t$ over **all clean baseline sessions of all of security s's non-excluded events** (≈ 7 × 30 ≈ 200 changes) | – | adjustment |
| abnormal one-session change | $e_t = \Delta x_t - \beta_s\,\Delta m_t$ | log | crush, baseline scale |
| baseline scale | $s_i = \operatorname{sd}_{t\in B_i}(e_t)$ | log | standardisation (ADR 0005) |
| **abnormal log IV (primary)** | $\text{ALIV}_t = (x_t-\mu_i) - \beta_s\,(m_t - \mu^m_i)$ | log ≈ % | run-up, persistence, paths |
| abnormal log IV, mean-adjusted | $\text{ALIV}^{0}_t = x_t-\mu_i$ | log | robustness |
| abnormal IV level (display) | $\text{AIV}_t = \sigma_t - \frac{1}{\lvert B_i\rvert}\sum_{B_i}\sigma_u$ | vol points | charts, intuition |

Choices inside the table, and why:

- **Logs are primary.** Crushes are proportional: a 60%-IV name loses more vol points than a 20%-IV name on similar news.
  Log changes are percentage changes, comparable across names, and closer to normal. Vol points stay on screen because
  traders think in them.
- **Market-model adjustment is primary.** Run-up and persistence are measured over 20 to 30 sessions. Market volatility
  moves a lot over such spans: in April 2025 VIX went from the low 20s to above 50 and back within weeks. Every event of
  a season gets hit at once. That biases the mean and correlates events with each other. The one-session crush is barely
  affected, so mean-adjusted and market-adjusted crushes must agree, and that agreement is a check.
- **β is pooled across one firm's baselines.** One baseline gives about 30 changes and a noisy β. Pooling one firm's
  clean baselines gives about 200 changes and still keeps firm-specific sensitivity. Using later baselines to adjust
  earlier events is harmless here: this is a description of the past, not a forecast.
- **No intercept (drift) term.** Log IV mean-reverts; it does not trend. An intercept estimated from about 30 noisy changes
  would add noise of order $s_i/\sqrt{30}$ to every abnormal change and remove no bias.
- **Caveat: megacaps move VIX themselves.** NVDA, AAPL and MSFT are large enough that their own news moves S&P 500 vol,
  so the adjustment removes part of their own effect. Robustness check: rerun without the 10 largest index weights.

### 3. What we test, and why not CAAIV

| Name | Definition | Question it answers |
|---|---|---|
| **RUNUP** | $\text{ALIV}_{-1}$ | Is IV abnormally high at the last close before the news? |
| **CRUSH** | $e_0 = \Delta x_0 - \beta_s\Delta m_0$ | How much does IV fall when the news arrives? (primary: `cm30_iv`; secondary: `front_fixed_iv`) |
| **PERSIST_h**, h = 1, 5, 10 | $\text{ALIV}_{+h}$ | Is IV back to its baseline h sessions later? Negative means it undershoots. |
| **EVAR** | $E$ at −1 (ADR 0003) | How large a move did options price? |
| **ΔSIGMA_D** | $\tfrac12\ln\frac{\sigma_d^2(0)}{\sigma_d^2(-1)} - \beta_s\Delta m_0$, with $\sigma_d^2$ = forward variance between the same two expiries on both days | Did *ordinary* volatility change because of the news? |

**How the crush splits.** Under ADR 0003's model, $\sigma^2_{cm30}(-1) = \sigma_{d,\text{ann}}^2(-1) + 252E/21$ and
$\sigma^2_{cm30}(0) = \sigma_{d,\text{ann}}^2(0)$, all annualised (ADR 0003 §c, "Units"). So, before the market
adjustment,

$$
\text{CRUSH} \approx \underbrace{\tfrac12\ln\frac{\sigma_{d,\text{ann}}^2(0)}{\sigma_{d,\text{ann}}^2(-1)}}_{\Delta\sigma_d\ \text{term}} \;-\; \underbrace{\tfrac12\ln\Big(1+\frac{252\,E}{21\,\sigma_{d,\text{ann}}^2(-1)}\Big)}_{\text{event variance leaving the 30-day horizon}}.
$$

The ratio inside the first term is unit-free, so the $\Delta\sigma_d$ term is the same with per-session variances.

AAPL 2025-10-30/31, model numbers from ADR 0003's two front expiries (re-run with ADR 0003's forward rule, see the note
above): CRUSH ≈ −12.3% = −4.1% (ordinary vol fell) − 8.2% (event variance gone). **The split separates "the event happened" from "the market became calmer about the stock",
and the drivers question (milestone 4) needs exactly that.**

**Why CAAIV is not a test.**

1. In a returns event study, $\text{CAR}(t_1,t_2) = \sum AR_t$ makes sense because returns are *flows*: adding up daily
   abnormal returns gives the abnormal price change over the window.
2. IV is a *level*. $\text{ALIV}_t$ is *already* the accumulated deviation from the baseline at $t$. Summing levels counts
   a persistent deviation once per day. A single permanent +2-point shift on day −10 contributes $2 \times 11 = 22$
   "vol-point-days" to CAAIV(−10, 0). Nobody trades that unit, and a small long-lived shift looks like a large brief one.
3. The return-study variance $\operatorname{Var}(\text{CAR}) = L\sigma^2$ assumes independent daily terms. With IV levels
   the daily terms are almost perfectly correlated, so the true variance is close to $L^2\sigma^2_{level}$. A test using
   $L\sigma^2$ would reject far too often.
4. The object that *does* make sense is the cumulative abnormal **change**. It collapses to two levels:
   $\sum_{t=t_1+1}^{t_2} e_t = \text{ALIV}_{t_2} - \text{ALIV}_{t_1}$ (with the market term handled the same way). That is
   exactly RUNUP, CRUSH and PERSIST, which we test directly.

**Decision:** no CAAIV. The **mean abnormal path** $\overline{\text{ALIV}}_t$ by rel_day is plotted with pointwise
95% bands, as description only. Only the quantities in the table are tested.

- The bands are **two-way clustered by season × firm** (ADR 0005 §2b), because each $\text{ALIV}_t$ is a
  multi-session ramp.
- *Revised after the review.* This said "date-clustered". At the real design, date clusters reject 32–36% for a ramp
  under ρ = 0.1 (ADR 0005 §2g), so date-clustered bands would be far too narrow.

### 4. The coarse sample (Mon/Wed/Fri, 2020-01-06 → 2024-09-09)

- Event time stays in sessions, and unobserved sessions are null. Under Mon/Wed/Fri, day −1 and day 0 are both observed
  only when day 0 is a Monday (day −1 = Friday). For day 0 on Wednesday or Friday the last pre-news snapshot is −2. For
  Tuesday or Thursday the first post-news snapshot is +1. **The coarse crush therefore usually spans 2 sessions.** It is
  defined as $x(\text{first obs} \ge 0) - x(\text{last obs} \le -1)$, with each end at most one session from its target.
  The span is stored and enters the standardisation (ADR 0005).
- E is measured at the last pre-news snapshot (−1 or −2). That is unbiased under the model, because τ counts sessions.
- Baseline changes over 1-session (Fri→Mon) and 2-session (Mon→Wed, Wed→Fri) gaps are converted to per-session scale
  via the autocorrelation correction in ADR 0005 §1 ("Gaps"), not by naive √span. ALIV across unobserved sessions is a
  sum of these span changes with the ramp weight held constant across each gap. That is exact (ADR 0005 §1).
- RUNUP and PERSIST use the nearest observed session within ±1 of the target, flagged.
- Day 0 must allow a complete [−60, +10] inside the Mon/Wed/Fri era, so day 0 is on or after about 2020-04-01. The weekly
  (Saturday) era is never used. **Coarse results are reported separately and never pooled into a primary test.**

### 5. Samples

| Label | Day-0 range | What is daily | Use |
|---|---|---|---|
| `daily` | 2024-12-05 → 2026-10-26 | everything from −60 onward | **primary.** Per-measure eligibility: PERSIST_h needs +h ≤ 2026-10-26, so PERSIST_10 needs day 0 ≤ 2026-10-12 |
| `mixed` | 2024-09-12 → 2024-12-04 | the crush, not the whole baseline | robustness (the Oct–Nov 2024 season) |
| `coarse` | ≈ 2020-04-01 → 2024-09-09 (day 0 in the Mon/Wed/Fri era; a post-window that runs past 2024-09-10 is simply denser) | none | robustness, longer history |
| `cboe5` | about 2020-04 → 2026-10-26, five names | VX\* only | robustness on the VX\* series (ADR 0003) |

The first three labels **partition events by day-0 date** (`events.sample`, with `none` for events outside every
range). `cboe5` is **not** part of that partition. It is an overlay, an analysis sample that can contain events from
all three date samples, measured on VX\* instead of `cm30_iv`. So it appears only in `results.sample`, and membership is a row in
the local-only `event_measures_vx` (data model §3.12). Membership needs a null `exclusion_reason`, so `cboe5` inherits
the day-0 ranges of the three date samples. It starts around 2020-04-01, not 2011 as first written. That start is
the coarse sample's boundary, 60 sessions after the Mon/Wed/Fri option data begins on 2020-01-06. It is a limit of the
option data, not of VX\*. Using VX\* before 2020 would need two things: an exemption from `outside_samples` for
`cboe5`, and a second source of event dates, since the calendar starts on 2020-01-22. The second is the owner's
milestone-1 decision in ADR 0002 §3.

2024-12-05 is the session 60 sessions after 2024-09-11, the first daily snapshot, measured with the NYSE holiday list.
**Expected primary N:** about 7.3 seasons × 50 names ≈ **365 before losses** (missing calendar events, timing exclusions,
data gaps, IV failures), so about 330–360 is realistic. **This is fewer than the brief's ≈400**, which counted from about
October 2024 and ignored the baseline's 60-session lead.

## Consequences

- Good: the baseline never contains another event's run-up, crush or after-period. That is a rule, not a hope, and the
  data model can show it is satisfied (`in_baseline`, `baseline_excluded_reason` per session).
- Good: every tested quantity has a plain-language question, a formula and a sign convention. CAAIV's double counting is
  avoided.
- Cost: the baseline is effectively about 31 sessions, not 41, so the scale estimates are noisier. ADR 0005's
  autocorrelation correction pools across firms to compensate.
- Cost: market adjustment adds a modelling choice (VIX, pooled β). Mean-adjusted results are always reported next to it.
- Cost: a market-adjusted per-event value, together with the committed `cm30_iv` and β, gives back Δln VIX on that
  date. Under the strict licensing default (ADR 0001 §7) those values (`aliv_cboe`, `crush_cboe`, …) therefore stay
  local, and only their aggregates are published. The committed per-event values are the mean-adjusted twins.

## Alternatives rejected

| Alternative | Why rejected | What would make it win |
|---|---|---|
| Keep the fixed [−60, −20] | Overlaps the previous report's [0, +10] window in 97% of gaps and contains its day 0 (the crush) in 20%. That inflates the baseline scale by a crush-sized change and biases the mean. | Events more than about 85 sessions apart. |
| Shorten to [−40, −22] | 19 sessions, and it still overlaps when spacing is 53–61. Rule-based exclusion adapts to the actual spacing instead. | Never better than the rule. |
| A baseline *after* the event (e.g. [+11, +40]) | Then testing persistence against the baseline is circular, since the baseline is itself post-event. It also runs into the next run-up. | The question is only about the run-up. |
| End the baseline at −20 (the brief) | At −21 and −20 the 30-day horizon already contains the event. | Using only front-expiry IV, which absorbs the event later. |
| Mean-adjusted as primary | Fails over multi-week spans in volatile seasons (spring 2025), and correlates events within a season. | VIX flat throughout the sample. |
| Market-adjusted with β = 1 | Assumes single-stock log IV moves one-for-one with log VIX. Not measured yet; we expect it to be < 1, which would over-adjust. | Measured pooled β ≈ 1. |
| Matched non-announcing peers as the control | Peer sets change daily, peers have their own run-ups, and the "market" is built from our own measured series. | A larger universe with plenty of quiet same-sector peers. |
| CAAIV (sum of abnormal levels) | Double counts persistent shifts, has unusable units and a wrong variance formula (§3). | Never for levels. The changes version collapses to what we test anyway. |

## How we'll know it's wrong

- **More than 5% of events** fail the 20-clean-session minimum once real data gaps are included. Then the exclusion zone
  [−21, +10] is too wide; consider [−21, +5] (median 36 clean sessions).
- **β is unstable:** per-firm β from the first and second halves of its baselines differ by more than 2 SE for many firms.
  Then use one pooled cross-firm β.
- **Mean-adjusted and market-adjusted mean CRUSH differ by more than 10%.** The market factor is then tangled up with the
  events (megacap feedback, or announcement clustering on macro days). Investigate before reporting.
- **The leak check from ADR 0003** (`cm30_iv` vs `cm30_blind_iv` in the baseline) shows less than 0.1 vol points on average.
  Then the [−22] end and the event-aware series are more care than the data needs. Simplify and say so.
- **The SPY placebo fails:** run the identical mean-adjusted pipeline on SPY's chain at the real day-0 dates (SPY has no
  earnings). Its "RUNUP", "CRUSH" and "PERSIST" should be indistinguishable from 0. If not, earnings seasons coincide with
  market-vol patterns that the mean-adjusted variant would wrongly credit to the events.
