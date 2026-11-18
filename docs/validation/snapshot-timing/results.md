route: row 6 (a result that decides how the report shows the 2026 events) | primary: the single run of the hash-frozen plan | complement: verifier (Sonnet) re-measures every figure below from `aggregate.json`; Opus adversarial pass on the premise and the procedure (ledger §4) | not-run: a second run (the plan allows one) | stop: every figure re-measured once and attacked once

# The 2026 snapshot-timing check: results

The plan is [preregistration.md](preregistration.md) and the record of the freeze is [ledger.md](ledger.md). This
file gives the single run's aggregates. The full output is [aggregate.json](aggregate.json). It holds no event id,
no date and no per-day VX\* or IV value.

## 1. The run

| Item | Value |
|---|---|
| when | 2026-11-18T09:25:39−06:00, once; 17 s; exit code 0 |
| command | `.venv/bin/python -I tools/snapshot_timing_check.py`, from a clean tree |
| code | `f2d0d37`; its code equals the freeze commit `f59e5c5` (`f2d0d37` changes `ledger.md` only) |
| plan SHA-256 | `0e7663232df05a328444c3228b1fb04a80b91040d9676a215fba02e479c0ff55` (equal to ledger §1) |
| timing map SHA-256 | `ed633f2bc8932e8f1ea9cb3ffde16ec23838e8a007ac7433478416785cdcb0c8` (equal to ledger §1) |
| stage (params hash) | `d51877f495f7ae67` |
| map | 84 off, 8 late, 3 unknown of 1,222 sessions |
| bootstrap | restricted wild cluster bootstrap by ISO week for the tests and the identity check; unrestricted bootstrap-t for the intervals; Webb six-point weights, 9,999 draws, seed 20261118, 106 week clusters |
| deviations | none: the plan, the map and the check are unchanged since `f59e5c5`, so there is no `deviations.md` |

The counts and the block rows equal the plumbing run (ledger §2). **The real blocks are thinner than the simulation
of plan §12**, most of all for σ_d (block P 27 off rows against 35, block A 18 against 25). The simulated power is an
upper bound, most of all for H4, and the tests' size was measured with more treated rows than these blocks have.

## 2. The verdicts

The shift Δ is the mean change that the off sessions put into each primary (plan §9). The line L is the published
standard error of the primary. SMALL needs both one-sided tests at 5% and an identity check that does not reject
(plan §10).

| | n | Δ (shift) | se | 90% interval | 95% interval | L | t at −L; p_up | t at +L; p_dn | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| H1 CRUSH | 349 | +0.0027 | 0.0020 | −0.0009 to +0.0062 | −0.0016 to +0.0068 | 0.0112 | 6.87; 0 of 9,999 | −4.23; 0.0009 | **SMALL** |
| H2 RUNUP | 358 | −0.0005 | 0.0016 | −0.0033 to +0.0024 | −0.0040 to +0.0030 | 0.0170 | 10.53; 0 of 9,999 | −11.22; 0 of 9,999 | **SMALL** |
| H3 PERSIST_10 | 331 | +0.0005 | 0.0003 | −0.0000 to +0.0010 | −0.0001 to +0.0012 | 0.0234 | 84.14; 0 of 9,999 | −80.58; 0 of 9,999 | **SMALL** |
| H4 ΔSIGMA_D | 263 | −0.0000 | 0.0050 | −0.0098 to +0.0098 | −0.0119 to +0.0118 | 0.0112 | 2.23; 0.0399 | −2.23; 0.0356 | **SMALL** |

The verdicts before and after the identity gate are the same. As a share of the line, the 90% intervals reach at
most 0.55 lines (H1), 0.20 (H2), 0.04 (H3) and 0.88 (H4).

**The se and t columns read too precise for H1 and H4, and decide nothing.** They come from the stacked fit, whose one
CR1 factor (n − 1)/(n − k) is set mostly by block O's 16,879 rows. A fit of each series' own blocks gives t at −L of
6.18 for H1 and 1.92 for H4, against 6.87 and 2.23 here (11% and 16% smaller); H2 and H3, which use block O, move by
less than 1% ([post_run_sensitivity.json](post_run_sensitivity.json)). The p values and the intervals do not depend
on that factor: the bootstrap uses the same factor in the observed t and in every draw.

**H4 is SMALL by a narrow margin.** Its two p are 0.040 and 0.036 against 0.05. Its estimate is close to 0 because
two terms of about 0.0015 cancel: 49 events with day 0 off times b₀ = +0.0082, and 28 events with day −1 off times
b₋₁ = +0.0145, each divided by 263. Each term is noisy (§4). The plan's simulation gave H4 SMALL in only 10–35% of
replications with no shift (plan §12), so this outcome was not the likely one. Its 95% interval reaches past the
line on both sides. The verdict uses two one-sided tests at 5% each, which correspond to a 90% interval (plan §10).

**H4's verdict holds under the check's estimator only** (§2a): with the direct estimates of the level errors from
the crush rows, the same rule gives UNCLEAR for H4.

The shifts, from the coefficients of §4 and the counts of §3 (plan §9):

- H1: [67 × 0.019111 − 46 × 0.007593] / 349 = +0.002668.
- H2: [51 × 0.007593 − 56.580 × 0.010247] / 358 = −0.000538.
- H3: [59 − 42.663] × 0.010247 / 331 = +0.000506.
- H4: [49 × 0.008243 − 28 × 0.014481] / 263 = −0.000006.

## 2a. After the run: the direct estimator (exploratory, not pre-registered, changes no verdict)

The adversarial pass (ledger §4) recomputed the H1 and H4 shifts with block C's direct estimates of the level
errors (b₀ = β_C0, b₋₁ = −β_C1) in place of the neighbour estimates of plan §9. I reproduced it with the check's own
code, the same prepared inputs, draws and seed
([post_run_sensitivity.py](post_run_sensitivity.py), [post_run_sensitivity.json](post_run_sensitivity.json)):

| | Δ, direct | in lines | 90% interval, in lines | p_up at −L | p_dn at +L | §10's rule would give |
|---|---|---|---|---|---|---|
| H1 | +0.0058 | +0.52 | +0.06 to +0.98 | 0 of 9,999 | 0.0498 | SMALL, by 0.0002 |
| H4 | −0.0029 | −0.25 | −1.11 to +0.61 | 0.083 | 0.017 | UNCLEAR |

Block C estimates the errors in the crush rows themselves, so it is far noisier than the neighbour blocks (that is
why plan §7 uses it only for the identity check). The two estimators do not differ beyond the identity check's
noise (§4). But the direct estimate for H4 cannot exclude a shift of about one line, and the one for H1 puts the shift
at about half a line. The pre-registered verdicts stand; the report says that H4's rests on the neighbour estimate.

## 3. The counts

| | n | day 0 off | day −1 off | both | day +10 off | late at day −1, 0, +10 | Σ s_e |
|---|---|---|---|---|---|---|---|
| H1 | 349 | 67 | 46 | 15 | 53 | 0, 0, 1 | |
| H2 | 358 | 67 | 51 | 15 | 58 | 0, 0, 1 | 56.58 (151 late baseline sessions in 30 events; 215 events have an off baseline session) |
| H3 | 331 | 53 | 47 | 13 | 59 | 0, 0, 1 | 42.66 (151 late baseline sessions in 30 events; 187 events have an off baseline session) |
| H4 | 263 | 49 | 28 | 11 | 38 | 0, 0, 0 | |

No event has an unknown session at day −1, 0 or +10. The shifts count the late sessions with a level error of 0
(plan §5a).

## 4. The level errors and the identity check

Block coefficients (one-way CR1 se by ISO week; intervals descriptive). b is the level error of an off snapshot
against the close: b_ord on an ordinary day, b₀ on day 0, b₋₁ on day −1 (plan §7).

| X | b_ord = β_O | b₀ = −β_P | b₋₁ = β_A | b₀ direct = β_C0 | b₋₁ direct = −β_C1 |
|---|---|---|---|---|---|
| ln CM30 | +0.0102 (se 0.0058; 90% −0.0007 to +0.0212) | +0.0191 (se 0.0088; 90% +0.0031 to +0.0348) | +0.0076 (se 0.0099; 90% −0.0115 to +0.0274) | +0.0261 (se 0.0105; 90% +0.0048 to +0.0475) | −0.0061 (se 0.0111; 90% −0.0257 to +0.0138) |
| ln σ_d | (no block) | +0.0082 (se 0.0168; 90% −0.0268 to +0.0444) | +0.0145 (se 0.0354; 90% −0.0542 to +0.0811) | +0.0014 (se 0.0217; 90% −0.0389 to +0.0410) | +0.0292 (se 0.0262; 90% −0.0169 to +0.0739) |

The intervals of the derived columns are those of the block coefficient, with the sign changed where the column
changes it. On day 0, an off CM30 level sits about 1.9% above the close level (neighbour estimate; 90% interval
+0.3% to +3.5%), and the direct estimate in the crush rows agrees (+2.6%).

The identity check (plan §8: β_C0 = −β_P and β_C1 = −β_A, one Wald statistic per X, 2 restrictions):

| X | Wald | p, restricted bootstrap | p, analytic F | Rejected at 5% |
|---|---|---|---|---|
| ln CM30 | 0.615 | 0.625 | 0.543 | no |
| ln σ_d | 0.128 | 0.899 | 0.880 | no |

The check does not reject. Its power is low: a violation worth one line is caught 23% (CM30) and 17% (σ_d) of the
time (plan §12), so not rejecting is weak support for the plug-in.

The coefficients of Δln VIX: CM30 blocks O, P, A, C 0.386, 0.505, 0.311, 0.314; σ_d blocks P, A, C 0.494, 0.411,
0.233 (aggregate.json, `coefficients`).

## 5. Descriptive, no verdict

**The ordering of the snapshots** (plan §6): the OLS slope of pre on the overnight gap g (day −1) and of post on g
(day 0), clustered by day-0 date, 95% intervals on t(G − 1).

| | Off events | Close events (reference) |
|---|---|---|
| day −1: pre on g | +0.014 (95% −0.008 to +0.037; 46 events, 25 dates) | −0.001 (95% −0.004 to +0.002; 303 events, 149 dates) |
| day 0: post on g | 1.054 (95% 0.941 to 1.167; 67 events, 28 dates) | 0.961 (95% 0.893 to 1.030; 282 events, 146 dates) |
| events flagged (\|g\| ≥ 3% and on the wrong side) | 0 of 27 (day −1), 0 of 47 (day 0) | 0 of 187 (day −1), 0 of 167 (day 0) |

The off day −1 snapshots sit before the news, as the close ones do, and the off day 0 snapshots sit after it. That
is what any snapshot taken during the trading day gives, because every report comes after the close or before the
open; the description rules out only snapshots taken after hours or before the open.

**D1, the VX slope on close-timed changes** (pooled one-session slope of Δln VX on Δln ours, aggregates only):

| Changes | n | slope | r |
|---|---|---|---|
| both ends close, 2020–2025 | 2,602 | 0.799 | 0.811 |
| both ends close, 2026 | 396 | 0.809 | 0.877 |
| at least one end off, 2026 | 576 | 0.599 | 0.606 |

The prediction written in the plan holds: the 2026 close-close slope is within 0.05 of the 2020–2025 one (a
difference of 0.0105), and the slope with an off end is below both. The drop of the pooled 2026 VX slope (0.696, n
982, against 0.784, n 2,715, for 2020–2025, all pairs: [VX check results §4.8](../vx-iv-checks/results.md)) follows
the changes with an off end. The pairs left out here have a late or unknown end, or an off end before 2026. The
2020–2025 close-close slope stays below 1, so the timing is not the whole of 1 − slope.

**D2, the 2026 crush gap without the timing** (2026 minus 2025 mean-adjusted crush, company dummies, two-way
clustered by ISO week of day 0 and company, t on 49 df):

| Events | n (2026) | gap | se | 95% interval |
|---|---|---|---|---|
| all | 345 (155) | +0.0558 | 0.0137 | +0.0284 to +0.0833 |
| day −1 and day 0 both close | 247 (73) | +0.0511 | 0.0184 | +0.0141 to +0.0881 |

The gap stays when the events with an off day −1 or day 0 are taken out: the smaller 2026 crush is not mainly the
snapshot timing (taking those events out moves the gap by 0.005 of 0.056). The adversarial pass also found the gap
among the 2026 events before the first off day of 2026 (with season-quarter dummies; its measurement, not re-measured
here). The plan quoted +0.0546 (se 0.0099) for all events. That figure is the mean of the 50 companies' 2026 minus
2025 differences (re-derived on 2026-11-18: +0.0546, se 0.0099, smaller in 2026 for 80% of companies), a different
estimator from D2's regression. The two do not disagree.

## 6. What this does not cover

- H5, H6 and H7. The mean shifts do not bound a regression slope, and H7 uses E, which takes the whole rest-of-day
  variance of an off day −1 snapshot (plan §5). Plan §11 gives them the with-and-without columns at every outcome.
- The robustness, path and PERSIST_1/5 tables.
- A violation of the identity that offsets a real level error would hide the shift and could leave a verdict SMALL
  (plan §14). The check catches a violation worth one line only 17–23% of the time.
- One class per day: a company whose snapshot differs from its day's class adds noise (plan §14). The adversarial pass
  measured it on event days: on close days, 0–3.7% of company snapshots lean like an off one; on off days, 22% (day
  0) and 30% (day −1) look close-timed. b₀ and b₋₁ are estimated on the event rows, so that mix is inside them.
- The estimator (§2a): H4's SMALL rests on the neighbour estimate; the direct one gives UNCLEAR.
- The tool's helpers that count the events and build the σ_d levels (`counts`, `sigma_levels`, `event_frame`,
  `near_event_set` in `tools/snapshot_timing_check.py`) have no unit test. The adversarial pass recounted every count
  from the event windows independently and got the same numbers.

## 7. The action (plan §11)

All four primaries are SMALL. Their rows in the report do not change, and the 2026 events stay in. Report §3.2, §7
item 8 and §9 Q9 give each shift's estimate and 90% interval and cite the timing map and this check. For H2 and H3 they
say that the shift is shown to be inside one standard error. For H1 and H4 they add that this rests on the check's
neighbour estimate and on an identity check with little power; for H4, that the direct estimate cannot exclude a
shift of about one line (§2a). H5–H7 get the two descriptive columns, worded "not
covered by the timing check". results.md §4.8 of the VX check gets the per-day line with the two corrections of plan
§3. These edits wait for the validation of ledger §4.
