route: row 6 (a result that decides how the report shows the 2026 events) + row 2 (the check's code, under tests with hand mutants) | primary: this hash-frozen plan, pushed before the run; code frozen to §6–§12 and pushed before the run; one run | complement: an Opus adversarial review of the first draft (procedure only, synthetic data; ledger §1.2) and a power and coverage simulation of the revised design on synthetic data (§12); after the run, a verifier (Sonnet) re-measures every figure and an Opus adversarial pass attacks the premise and the procedure | not-run: dual-channel EGV (no API-existence or library-semantics claim) | stop: the verdicts of §10 reached once, every reported figure re-measured once and attacked once

# The 2026 snapshot timing and the event measures: pre-registration

Written on 2026-11-18, **before the check below was run.** No event measure (crush, abnormal IV level, ΔSIGMA_D)
was split by session class to write it. §2 lists everything that was looked at first. The ledger
([ledger.md](ledger.md)) records the SHA-256 of this file at its push. A change to this file after that is a
deviation (§13).

## 1. Why, and what the owner decided

The pre-registered IV checks after the VX\* slope result ended UNCLEAR
([results.md](../vx-iv-checks/results.md) §1). As an exploratory result they found that the vendor's 2026 option
snapshots are often taken during the day, before the close (results.md §4.8): the median |forward change − close
change| is 3 to 9 bp a year in 2020 to 2025 and 14 to 41 bp in 2026, and the pooled one-session VX slope is 0.784 in
2020 to 2025 and 0.696 in 2026. 155 of the 349 events of the primary (daily) sample have day 0 in 2026.

Report §9 Q9 gave three choices. **Owner decision, 2026-11-18 (relayed by the hub session): option 3**, "first check
the 2026 snapshot timing and its effect on the event measures, with its own pre-registration". The strike rule stays
UNCLEAR and nothing is widened. The owner did not answer Q1, Q2, Q3, Q5, Q7, Q8 or the exploratory H5 line; they
stay open and nothing here answers them.

The question: **does the timing of the snapshots move the published event results by more than their own
sampling error?** For each of H1–H4: if the check shows that the effect is small, the report says so with this
evidence and the 2026 events stay in. If it shows that the effect is large, or cannot show that it is small, the
report flags the affected events for that hypothesis (§11). H5–H7 are outside what this check can bound, and the
report flags them in every case (§11).

## 2. What was looked at before this was written

Event-measure numbers already seen, all exploratory and in the repository or its ledgers:

- The published primaries (report §4.1): H1 −0.1985 (se 0.0112, n 349), H2 +0.2314 (two-way season se 0.0170,
  n 358), H3 +0.0089 (se 0.0234, n 331), H4 +0.0028 (se 0.0112, n 263), and their distributions in the report.
- The 2026 crush by year: the mean mean-adjusted crush is −0.167 for 2026 day 0s (155 events) and −0.224 for 2025
  (190); within company, 2026 is smaller by +0.0546 (se 0.0099, 50 companies)
  ([edgar-coarse-ledger.md](../edgar-coarse-ledger.md) §9, item 5). The same item reports a reviewer's split: most
  of the +0.0546 follows the smaller day −1 event variance, with a rest of +0.020 ± 0.015.
- **The ordering of the 2026 snapshots** (edgar-coarse-ledger §9, item 6, a reviewer's measurement): of the 102
  events of 2026 with an overnight gap above 3%, no day −1 snapshot sits past halfway from the pre-news close to the
  post-news open, and the day-0 snapshot is inside day 0's high-low range for every after-close event and all but
  one before-open event. So the answer to §6's question was known before this plan. §6 is descriptive for that
  reason and two others (§6).
- The VX slopes by period and name (results.md §4.8).

Looked at for this plan (**phase 0**), with no event measure split by class:

- The parity spot against the close on every snapshot session of every company (forwards from `chain_expiry`,
  Yahoo closes): the timing map of §3. This found that the timing is a property of the **day**, not of the year (§3).
- From the map and the event tables only: how many events have a session of each class at each event day (§4).
- The day-to-day noise of ln CM30 and ln σ_d on **close** sessions in the daily era, event days included (robust sd
  0.044 and 0.068). This read one-session changes on close sessions only. No change on an off session and no
  difference between classes was computed.
- An Opus adversarial review of the first draft (ledger §1.2). It read the map, the counts, Cboe VIX on off and close
  days (aggregates) and per-company gaps on event days by class (gaps, not IV), and it simulated the design on
  synthetic data. It read no event measure split by class. Its findings changed §4, §6, §7, §8, §10, §11, §12 and
  §14.
- The power and coverage simulation of §12: synthetic levels on the real calendar, events and classes.

**The check's code was drafted alongside this plan** (the review found it on disk while it worked). It has run only
on synthetic data: the tests, and the simulation of §12, which reads the real calendar, event dates and session
classes and no IV, price or measure value. It is pushed with this file as a draft; §13 says when it is frozen.

Not computed before this file was frozen: any level-error estimate (§7), any contrast of an event measure between
session classes, the identity check (§8), the ordering description (§6), any shift (§9) or any with/without estimate
(§11).

## 3. The timing map (frozen)

`tools/snapshot_timing_map.py` writes [timing_map.json](timing_map.json) (rule in
`earnings_vol.stats.snapshot_timing`, tests in `tests/test_snapshot_timing.py`). For each company and snapshot
session t, **gap** = ln(S_parity / Close_t), with S_parity from the parity forward of the nearest expiry with at least
5 sessions to go (the spot of ADR 0002's snapshot-close test), and r = ln(Close_t / Close_{t−1}). Across the
companies of one session: n, gap_bp = median |gap| in bp, ret_bp = median |r| in bp, ratio = gap_bp / ret_bp, and
the OLS slope of gap on −r.

| Class | Rule | Meaning |
|---|---|---|
| unknown | n < 20 | too few companies to tell |
| off | gap_bp > 20 and ratio > 0.2 | the snapshot is not at the close: during the day it leans on −r with the share of the day still to come |
| late | off and slope ≥ 0.8 | the snapshot carries the previous session's close (gap = −r) |
| close | otherwise | at the close |

The ratio keeps a close-timed day in a crash from reading as off: in March 2020 gap_bp reaches 36 bp at a ratio of
0.07. **Margins** (timing_map.json): close days reach gap_bp 7.5 where the ratio is above 0.2, and a ratio of 0.146
where gap_bp is above 20; off and late days start at gap_bp 24.9 and a ratio of 0.253; late days have slopes of 0.87
and above, off days 0.74 and below.

**Result, 1,222 sessions from 2020-01-03 to 2026-10-26.** 84 off, 8 late, 3 unknown (2020-06-08, 2021-05-27,
2021-06-15: weekly era, no daily event). Off: 1 in 2024 (2024-12-26), 7 in 2025 (2025-05-20, 10-13, 10-17, 10-31,
11-19, 11-21, 12-04), 76 in 2026. Late: 2020-06-09, the six sessions 2025-03-24 to 2025-03-31, and 2026-10-07.

What this changes against results.md §4.8:

- **The 2026 timing is a property of the day.** From 2026-01-02 to 2026-02-18 every session is close. From
  2026-02-19, 76 of the 2026 sessions are off and the others are close. A yearly split mixes the two.
- **The 2025 episode is 6 sessions, 2025-03-24 to 2025-03-31.** 2025-04-01 is close. The changes "to 2025-04-01" of
  results.md §4.8 include it because the change into 2025-04-01 starts from the late 2025-03-31.
- **2025 has 7 off days too** (16 of the 2025 events touch one, §4).

The review checked the class against each company (ledger §1.2): from 2026-02-19, every company's own slope of gap
on −r is positive on off days (0.16 to 0.46) and near 0 on close days (−0.01 to 0.06). Limit: the class is one per
day, from the median company (§14).

## 4. Words, and the events each class touches

| Word | Meaning here |
|---|---|
| session class | close, off, late or unknown, from the timing map |
| X | ln CM30 (`cm30_iv` of `iv_daily`, the 30-day IV), per company; or ln σ_d **per event**: ½ ln of the forward variance between the event's expiry pair (E's pair at day −1, held fixed on every day, as H4's ΔSIGMA_D holds it: `measures/event_iv.py`), from the `chain_expiry` rows. Both on `ok` snapshots only |
| M | ln VIX, Cboe's close (`market_daily.ln_vix_cboe`); the snapshot timing does not touch it |
| Δ_t | X(t) − X(t−1), t−1 the NYSE session before t, both `ok` |
| level error b | on an off session, X(snapshot) − X(what a close snapshot would have shown) |
| measure sessions | the sessions whose levels a measure uses: CRUSH and ΔSIGMA_D day −1 and day 0; RUNUP day −1 and the baseline; PERSIST_10 day +10 and the baseline |
| shift Δ_M | the change in a published estimate that the level errors cause |
| line L_M | the published standard error of that estimate (§10) |

The primary (daily) sample: 349 crush events, of which 46 have day −1 off, 67 have day 0 off, 98 one or both, 15
both (16 of the 98 in 2025, 82 in 2026). No crush event has day −1 or day 0 late or unknown. RUNUP: 51 of 358 have
day −1 off. PERSIST_10: 59 of 331 have day +10 off. ΔSIGMA_D: 66 of 263 have day −1 or day 0 off. In the mixed and
coarse samples no event has day −1, 0 or +1 off or late; one coarse day 0 and three coarse day −1s are on unknown
sessions (the review's count, which also reproduced every count above).

## 5. The model

On an off session the snapshot level is the close level plus an error b. The VIX side of the market adjustment uses
Cboe's close and is not affected. So every event measure in log points moves by a signed sum of level errors:

- CRUSH and ΔSIGMA_D: b(day 0) − b(day −1);
- RUNUP: b(day −1) − the mean of b over the baseline sessions;
- PERSIST_10: b(day +10) − the mean of b over the baseline sessions.

b is 0 on a close session. Its mean on an off session may differ by the kind of session, so §7 estimates three means
for each X: **b₀** on day 0 (after the news), **b₋₁** on day −1 (before the news), **b_ord** on ordinary sessions.
A snapshot during day 0 misses the IV move between the snapshot and the close, and one during day −1 misses the move
into day −1's close, so a smaller measured crush is possible. The test assumes no sign.

An intraday snapshot also adds the rest of the day's variance to the total variance of every expiry. For ln CM30
this is inside b. In σ_d² (a difference of two expiries) it cancels. All of it goes into the event variance E, which
H1–H4 do not use and H7 does (§11).

On a late session b = −Δ(true change), with a mean of about 0. Late and unknown sessions are kept out of every
estimate in §7 (a late session is a different fault, §5a).

### 5a. The 2025-03-24 to 2025-03-31 episode: excluded from the estimates, left in the main study

- **Excluded from §7:** its sessions carry the previous close. That is not the intraday timing this check measures,
  and as an off session it would pull b_ord toward the mean daily change.
- **Left in the main study:** no crush, RUNUP, PERSIST_10 or ΔSIGMA_D event uses a late session as day −1 or day 0.
  One event (MU, day 0 2025-03-21) has day +1 on 2025-03-24, and day +1 enters no primary measure. One event has day
  +10 on a late session, and 151 baseline sessions of 30 events are late. On a late session the level is the previous
  close, so the error is minus one day's change, with a mean of about 0; in a baseline of at least 20 sessions it adds
  noise, not a shift. The run reports these counts again; the shifts of §9 count the late sessions with a level error
  of 0.

## 6. The ordering description (no verdict)

For every crush event of the primary sample, from the local chain forwards and Yahoo prices: g = ln(Open_0 /
Close_−1), the overnight gap that holds the news (after-close and before-open reports alike); pre = ln(S_−1 /
Close_−1); post = ln(S_0 / Close_−1), S the parity spot of §3. A day −1 snapshot before the news has pre unrelated
to g, and one after the news has pre ≈ θ·g. A day 0 snapshot after the news has post ≈ g plus the day's drift, and
one before the news has post ≈ 0.

Reported for the events whose session is off and, as the reference, for those whose session is close: the OLS slope
of pre on g (day −1) and of post on g (day 0), one-way clustered by day-0 date, with 95% intervals on t(G − 1); and
the count of events with |g| ≥ 3% and pre/g ≥ 0.5, or post/g ≤ 0.25 with ln(Close_0/Close_−1)/g ≥ 0.5.

**No verdict, for three reasons.** Its answer for 2026 was known before this plan (§2). A snapshot on the wrong side
of the news is a level error like any other, so its mean effect is inside b₀ or b₋₁ and the shifts of §9. And the
review's simulation found that a fixed bar on the post slope (the first draft's 0.75) fires 15.6% of the time with
no fault when the gap partly reverses during day 0 (ledger §1.2).

## 7. The level errors

One stacked OLS of 7 blocks: O, P, A and C for X = ln CM30, and P, A and C for X = ln σ_d. No shift uses an
ordinary-day σ_d error, and σ_d is defined per event, so σ_d has no block O.

| Block | Rows | Outcome | Regressors | Coefficient | Estimates |
|---|---|---|---|---|---|
| O | company-sessions t of the daily era (from `snapshot_eras.daily_from`), t−1, t, t+1 consecutive and `ok`, t−1 and t+1 close, t close or off, t outside [−2, +2] of any day 0 of that company | h = (Δ_t − Δ_{t+1}) / 2 | weekday of t (dummies), the same h of M, 1[t off] | β_O | b_ord |
| P | crush events (for σ_d: the 263 ΔSIGMA_D events), day 0 and day +1 `ok`, day +1 close, day 0 close or off | Δ_{+1} = X(+1) − X(0) | company, season and weekday-of-day-+1 dummies, M(+1) − M(0), 1[day 0 off] | β_P | −b₀ |
| A | the same events, day −2 and day −1 `ok`, day −2 close, day −1 close or off | Δ_{−1} = X(−1) − X(−2) | company, season and weekday-of-day-−1 dummies, M(−1) − M(−2), 1[day −1 off] | β_A | b₋₁ |
| C | the same events, day −1 and day 0 close or off | X(0) − X(−1): exactly `crush_mean_adj` (ln CM30) or `dsigma_d_mean_adj` (ln σ_d); the run stops if a row differs | company, season and weekday-of-day-0 dummies, M(0) − M(−1), 1[day 0 off], 1[day −1 off] | β_C0, β_C1 | b₀, −b₋₁ (direct, for §8) |

A weekday dummy that the other columns already span is dropped, the last weekday first. (BRK.B reports on
Saturdays, so its day −1 is always a Friday; in block A no other event's day −1 is a Friday.) The off and M columns
are never dropped. Any other linear dependence stops the run. Season = `events.season`.

**Why the neighbours.** Δ_{+1} runs from day 0 to a close session, so it carries −b₀ and no other error. Δ_{−1}
runs from a close session to day −1 and carries +b₋₁. h on an ordinary off day with close neighbours carries +b plus
half the negative second difference of the true level, whose mean is the same on close days. These one-session
changes are far less noisy than the crush, so blocks O, P and A estimate the errors more precisely than block C.

**Why M and the weekday.** Off days are busier market days: from 2026-02-19, mean |Δ ln VIX| is 0.067 on off days
against 0.048 on close days (Welch p 0.020, the review's figures; re-measured as 0.0667 and 0.0483). Of the
day-0-off events, 25% (17 of 67) are Fridays, against 15% (14 of 95) of the 2026 day-0-close events. M takes out the
market part of each change. The weekday dummies take out the weekend in a change that spans one.

**Inference.** The stacked fit gives the same coefficients as the seven separate fits; the stack gives the joint
covariance. Standard errors are one-way CR1 by ISO week of the row's end session (O: t; P: day +1; A: day −1; C: day
0). Rows a session apart share shocks: h_t holds Δ_{t+1}, and a crush row and its Δ_{+1} row are one session apart.
The review found week and date clusters alike.

**Tests** (§8, §10) use the **restricted wild cluster bootstrap by ISO week**: Webb's six-point weights, 9,999
draws, seed 20261118, the null imposed. For H0: w′β = c, the least-squares fit under the null, β̃, and its residuals
ũ give the draws y* = Xβ̃ + v_g·ũ, refitted without the restriction: t* = (w′β* − c)/se*, against the observed
t = (w′β̂ − c)/se. p_up = P*(t* ≥ t) tests H0: w′β ≤ c, and p_dn = P*(t* ≤ t) tests H0: w′β ≥ c. Every test uses
the same draws.

**Description:** each coefficient and shift also gets its 90% and 95% unrestricted bootstrap-t interval (same
weights, draws and seed): [w′β̂ − q_hi·se, w′β̂ − q_lo·se], with q_lo and q_hi the bootstrap quantiles of
t* = w′(β* − β̂)/se*, y* = Xβ̂ + v_g·û. These intervals decide nothing.

**Why.** The off rows fall in few weeks: the day-0-off events fall in 20 ISO weeks. The first draft's two-way CGM
intervals covered 87–94% at a nominal 95% across the review's 9 configurations, and 91.0–93.7% in a re-run on new
seeds (ledger §1.2). The unrestricted bootstrap-t intervals did little better: 86–90% at a nominal 90% and 91–94% at
95% (ledger §1.1). Imposing the null changes what the draws centre on; §12 measures how its tests do here.

## 8. The identity check

If the off sessions are as good as random with respect to the events (the vendor's timing does not know the
calendar), blocks C and P/A estimate the same errors: β_C0 = −β_P and β_C1 = −β_A. For each X separately, one Wald
statistic of these two restrictions, with its p from the restricted bootstrap of §7 (R β = 0 imposed: the share of
draws whose Wald statistic is at least the observed one). A rejection at 5% means the plug-in of §9 is not trusted for that X: H1–H3
(ln CM30) or H4 (ln σ_d) cannot be SMALL (§10). The analytic F's p is reported beside it.

## 9. The shifts

From the §7 coefficients and the counts of §4 (recounted in the run):

- **H1** (CRUSH, n = 349): Δ_H1 = [−k₀·β_P − k₋₁·β_A] / n, with k₀ = events with day 0 off (67), k₋₁ = with day −1
  off (46), X = ln CM30.
- **H4** (ΔSIGMA_D, n = 263): the same formula with X = ln σ_d and H4's own k₀, k₋₁.
- **H2** (RUNUP, n = 358): Δ_H2 = [k₋₁′·β_A − (Σ_e s_e)·β_O] / n, k₋₁′ = events with day −1 off (51), s_e = the
  share of event e's baseline sessions (the clean baseline the measure uses) that are off.
- **H3** (PERSIST_10, n = 331): Δ_H3 = [k₊₁₀·β_O − (Σ_e s_e)·β_O] / n, k₊₁₀ = events with day +10 off (59).

Each Δ is a linear combination w′β. Its tests are those of §10; its 90% and 95% intervals (§7) are descriptive. The market adjustment of
every primary uses close VIX and is untouched. Its β is estimated on baseline changes that include off sessions;
this plug-in ignores that (§14).

## 10. The lines, and the verdicts

For each primary M ∈ {H1, H2, H3, H4}, the line L_M is the published standard error of M's estimate: H1 0.0112,
H2 0.0170 (the two-way season row; H2's primary is a randomisation p with no se), H3 0.0234, H4 0.0112. Each is the
`results` row with sample `daily`, subgroup `all` and adjustment `market`: H1 `twoway_date_t` 0.011237, H2
`twoway_season_t` (robustness) 0.017046, H3 `twoway_season_t` 0.023384, H4 `twoway_date_t` 0.011169.

Why one standard error: a shift below it stays inside the sampling uncertainty the report already prints. At the
line, the published 95% interval still covers the corrected value 83% of the time; above it, readers should see the
alternative.

Each measure gets its own verdict from two restricted-bootstrap tests (§7): one with Δ_M = −L_M imposed, one with
Δ_M = +L_M imposed. SMALL is the two one-sided tests of equivalence at 5%: |Δ_M| < L_M is shown when both
Δ_M > −L_M and Δ_M < +L_M are shown, each at 5%.

| Verdict of M | When |
|---|---|
| SMALL | p_up at −L_M < 0.05 and p_dn at +L_M < 0.05, and the identity check of M's X (§8) does not reject |
| LARGE | p_dn at −L_M < 0.05 (Δ_M < −L_M shown) or p_up at +L_M < 0.05 (Δ_M > +L_M shown) |
| UNCLEAR | otherwise |

The rule asks for evidence before it says SMALL. A noisy estimate gives UNCLEAR, not SMALL. There is no overall
verdict: each hypothesis carries its own. (The first draft used the 95% interval and one verdict for all four; under
its design the review measured an overall P(SMALL) of about 0.25 with no shift. A later draft used the 90%
unrestricted bootstrap-t interval, which under-covered in its own simulation, ledger §1.1. §12 gives this design's
figures.)

## 11. The action for each outcome

| Case | The report |
|---|---|
| H1, H2, H3 or H4 SMALL | its row does not change. §3.2, §7 item 8 and §9 Q9 say that the timing's shift of it is shown to be inside one standard error, give the shift's estimate and 90% interval, and cite the timing map and this check. Its 2026 events stay in. |
| H1, H2, H3 or H4 LARGE | §4.1's table gains, for that hypothesis, two descriptive columns: **without the events whose measure sessions include an off session** (H1, H4: day −1 or day 0; H2: day −1; H3: day +10) and **without the 2026 events**. Each shows the estimate and its 95% interval from the primary's own statistic (H1, H4: two-way date-company t; H2, H3: two-way season-company t), with no Holm correction and no G1 check, so no verdict. The text gives the verdict and the shift. The binding row stays as it is. |
| H1, H2, H3 or H4 UNCLEAR | as LARGE, worded "this check could not show that the timing effect is small". |
| H5, H6, H7 (every outcome) | the same two columns (without the events with day −1 or day 0 off; without the 2026 events; the primary regression), worded "not covered by the timing check". The mean shifts of §9 do not bound a regression slope, and H7 uses E, which takes the whole rest-of-day variance of an off day −1 snapshot (§5). |

Every outcome also adds a line to results.md §4.8: the timing is per day (§3), with the two corrections of §3 to that
file. The robustness, path and PERSIST_1/5 tables are not checked here, and the report says so once.

## 12. Descriptive, no verdict; and the power of the design

- **D1, the VX slope on close-timed changes.** The pooled one-session slope of Δln VX on Δln ours (bar ii of the VX
  check, same pairs) for: changes with both ends close, 2020–2025; both ends close, 2026; at least one end off, 2026.
  Changes with a late or unknown end are left out. **Prediction, written now:** if the off days cause the 2026 drop,
  the 2026 close-close slope is within 0.05 of the 2020–2025 close-close slope, and the slope with an off end is
  below both. The 2020–2025 slopes stay below 1, so the timing cannot be the whole of 1 − slope (results.md §4.8);
  this tests only the 2026 part. Aggregates only (VX\* stays local).
- **D2, the 2026 crush gap without the timing.** Within company, the 2026 minus 2025 mean-adjusted crush among
  events whose day −1 and day 0 are both close, beside the same for all events (+0.0546 known): mean-adjusted crush on
  1[day 0 in 2026] and company dummies, 2025 and 2026 day 0s, two-way clustered by ISO week of day 0 and by company.

### Power and coverage (measured on synthetic data, not on this sample)

[power/power_sim.py](power/power_sim.py) runs the check's own code (`earnings_vol.stats.snapshot_timing`) on
synthetic ln levels laid on the real calendar, the real H1 events and H4 subset, and the real session classes. It
reads no IV, price or measure value. The generator follows the review's: a market factor seen in M with noise,
company factor loadings, a persistent company component, measurement noise, and per event a run-up, a crush and a
post-event drift. On off sessions it adds a level error with a common daily part. The σ_d series is 1.55 times as
noisy (the ratio of the phase-0 robust sds). The replications, draws and seeds are in [power/](power/).

Measured: 400 replications per configuration, 999 draws per bootstrap (the run uses 9,999), seeds in the script,
outputs in [power/results/](power/results/). The true shift is the realised mean planted error, in lines. The Monte
Carlo se of a 5% rate is about 1.1 points.

| Configuration | true shift H1 / H4 (lines) | H1 SMALL / LARGE % | H4 SMALL / LARGE % | identity rejects cm30 / σ % |
|---|---|---|---|---|
| null_gauss: no shift, Gaussian noise | +0.00 / -0.01 | 87.2 / 0.0 | 35.0 / 0.2 | 6.2 / 5.8 |
| null_t3: no shift, t(3) noise | -0.01 / +0.00 | 63.7 / 0.0 | 10.0 / 0.0 | 7.0 / 5.0 |
| null_common: no shift, market factor twice as large | -0.00 / +0.01 | 74.2 / 0.0 | 13.8 / 0.2 | 5.2 / 6.0 |
| null_offvol: no shift, off days 1.4× as volatile | +0.00 / -0.01 | 87.8 / 0.0 | 30.5 / 0.0 | 4.5 / 5.0 |
| at_line: shift of −1 line | -1.00 / -1.00 | 5.8 / 5.8 | 6.5 / 6.2 | 6.2 / 5.2 |
| at_line_t3: shift of −1 line, t(3) noise | -1.00 / -0.99 | 6.0 / 3.5 | 2.0 / 4.8 | 5.0 / 4.0 |
| half_line: shift of −½ line | -0.50 / -0.50 | 53.8 / 0.0 | 25.2 / 0.2 | 6.0 / 6.5 |
| viol_drift_1line: no shift; §8 violated: drift on off day 0 worth 1 line | +0.00 / +0.00 | 5.0 / 6.0 | 5.8 / 7.5 | 23.2 / 16.5 |

| Configuration | H1 rejects at the truth, up / down % | H4 up / down % | H1 cover 90 / 95 % | H4 cover 90 / 95 % | identity, analytic F, cm30 / σ % |
|---|---|---|---|---|---|
| null_gauss | 4.2 / 5.8 | 5.5 / 4.2 | 89.0 / 94.2 | 89.5 / 93.5 | 16.2 / 15.8 |
| null_t3 | 5.5 / 3.0 | 3.5 / 3.5 | 90.5 / 94.2 | 91.5 / 96.8 | 13.5 / 15.5 |
| null_common | 7.0 / 7.0 | 5.5 / 6.2 | 85.5 / 92.8 | 86.5 / 93.2 | 14.8 / 16.5 |
| null_offvol | 4.5 / 4.2 | 4.2 / 3.8 | 89.0 / 95.2 | 91.0 / 95.2 | 12.8 / 13.8 |
| at_line | 6.0 / 5.2 | 6.8 / 5.0 | 88.2 / 94.2 | 86.5 / 91.2 | 15.0 / 15.5 |
| at_line_t3 | 5.2 / 2.8 | 3.5 / 4.5 | 91.0 / 95.0 | 90.5 / 94.8 | 14.8 / 14.2 |
| half_line | 3.8 / 4.8 | 6.2 / 3.5 | 90.8 / 95.8 | 88.5 / 94.8 | 12.5 / 15.5 |
| viol_drift_1line | 0.0 / 95.5 | 0.0 / 63.7 | 4.2 / 7.2 | 32.5 / 46.8 | 41.5 / 29.2 |

What this says:

- **The verdict's tests hold their size.** With a true shift of one line, H1 is SMALL 5.8% of the time and H4 6.5%
  (6.0% and 2.0% with t(3) noise). The one-sided tests at the true shift reject 2.8–7.0% of the time at a nominal 5%.
- **Power is good for H1 and poor for H4.** With no shift, H1 is SMALL 64–88% of the time and H4 10–35%; with half a
  line, 54% and 25%. An UNCLEAR for H4 is the likely result even with no effect. H2 and H3 are not simulated: their
  shifts weigh β_A and β_O by small shares (§9), and by the review's formula their se is about 0.002, against lines of
  0.017 and 0.023.
- **The identity check holds its size and has little power.** With no violation, the restricted bootstrap rejects
  4.0–7.0% of the time (the analytic F 12.5–16.5%, too often). A violation worth one line is caught 23% (cm30) and
  17% (σ) of the time. The simulated violation makes the check see a shift of one line where there is none, so it
  rarely says SMALL (5.0% and 5.8%). A violation in the other direction would hide a real shift; it is not simulated,
  and §14 names it.
- **The descriptive intervals under-cover a little:** 85.5–91.5% at a nominal 90% and 91.2–96.8% at 95%, outside the
  violation. They decide nothing.

## 13. Procedure

1. Push this file, the timing map (with its tool and tests) and the check's draft code. The ledger records this
   file's SHA-256 and the map's.
2. Finish the check to §6–§12 (`earnings_vol.stats.snapshot_timing` for the pure parts,
   `tools/snapshot_timing_check.py` for the files). Test it on synthetic data with planted level errors, a planted
   market loading, a planted violation of §8's identity and the bootstrap against a refit per draw, each with a hand
   mutant that must fail a test. Before the run, the tool may run on the real inputs only with `--plumbing`: it
   stops before any fit and prints the sample sizes, the counts of §4, the block row counts and the block-C equality
   check, no outcome. Its output goes in the ledger. Push the code; the ledger records its commit before the run.
3. Run once on commit-pinned inputs: the stage cache of the current params, the timing map of step 1, and the Cboe
   files of the VX check. Write `results.md` and `aggregate.json` (aggregates only).
4. A change to this file or the map after step 1's push, or to the check after step 2's push, is a deviation: listed
   in `deviations.md` with its reason and its effect on every figure. A verdict computed after a deviation says so.
5. Validation after the run: a verifier (Sonnet) re-measures every figure of results.md from the saved outputs. An
   Opus adversarial pass attacks the premise (as good as random, the neighbour identity, the map's day-level class)
   and the procedure. A blocker it raises is reproduced before anything acts on it.
6. The report follows §11 and is rebuilt once; the app data are exported from a clean clone.

## 14. Limits

- One class per day (§3). A company whose snapshot differs from its day's class adds noise and, if it clusters on
  event days, bias. In the review's per-company check, 1.7–3.1% of company-sessions on close days lean like an off
  snapshot each year (the noise floor of a one-session measurement).
- **As good as random.** The plug-in assumes that the off days do not change the true path of IV around an event
  beyond what M and the weekday take out. If, say, the post-event drift on day +1 differs on off days, β_P carries it
  and the shift is wrong. The identity check of §8 is the only guard. It holds its size, but it catches a violation
  worth one line only 17–23% of the time (§12), so passing it is weak support. A violation that offsets a real level
  error (say, an off-day drift of the opposite sign) would hide the shift and could leave the verdict SMALL.
- An error that is not repaid by day +1 (part of b₀ still in X(+1)) biases β_P toward 0. By the definition of the
  class, a close day carries no level error; such an error comes only from a company whose own day +1 snapshot is
  off (the first limit). The review's simulation of a half-repaid error recovered about half the shift.
- The plug-in ignores the off sessions' effect on each company's β of the market adjustment (a few percent of β; its
  effect on the shifts is below 0.001 by the review's formula) and on the τ count inside one session (a snapshot
  hours before the close is treated as at the close by ADR 0003's session count; that error is inside b).
- b₀ and b₋₁ come from events whose neighbour session is close; the shift applies them to every event with that
  session off.
- Eligibility depends on the class a little: in 2025–26, `crush:missing_0` drops 5 of 98 events that touch an off
  session, against 4 of 250 that do not (the review's count). The check does not model that selection.
- The bootstrap clusters by week only. Rows of one company in different weeks are treated as independent; the
  company dummies of blocks P, A and C take out each company's mean.
- Nothing here re-opens the VX\* falsifier or the strike rule; D1 is descriptive.
