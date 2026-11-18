route: rows 4 + 6 | primary: the frozen phase-2 run (`probes/phase2.py --reference`; gates G1 to G4, then every rule on GOOGL, GS, IBM) | complement: robustness rerun, blocks of 60, seed 20261118 | row 6: verifier (S) re-ran phase 2 and agrees on every number; adversarial (O) confirmed the outcome and found the 2026 snapshot timing (§4.8) and four write-up errors, now corrected (§8) | not-run: `--widen` and §10 steps 1 and 2 (they apply only to a FAULT) | stop: phase 2 run once, outcome UNCLEAR

# IV checks after the VX\* slope result: phase-2 results

Run on 2026-11-18, after the freeze at 02:15:34Z, by the frozen `probes/phase2.py` with `--reference`. It ended
at 02:28:08Z. The rules and the thresholds are in [preregistration.md](preregistration.md). Every number below
comes from [aggregate.json](aggregate.json) (SHA-256 `b1e70843f1064bb955cf5dd6b3c63258ad2a8245e26ddf646d822e89383e5d16`; see §7).
It holds aggregates only. The per-name results, with dates, stay local in
`$VOL_DATA_DIR/earnings-vol-study/vx-iv-checks/`.

## 1. Outcome (§10): UNCLEAR

- **The strike rule is UNCLEAR on all three names.** Its interval crosses 0.10 on each: the upper bound is above
  0.10 and the lower bound is below it. The any-reference guard did not cause this; the clean-reference interval
  alone is too wide.
- **Every other rule passes on all three names.** The differential (a) is MATCH. The synthetic truth and the
  forward-vs-close line (b) are NO FAULT. The forward, filter and roll shares (c) are NO FAULT.
- **The robustness rerun** (blocks of 60) gives the same verdict for every rule and name.
- So, per §10: do not widen. The owner decides the next step: accept the result, or run the same frozen rules on
  sessions after 2026-10-26 that nobody has seen yet.

Why the strike interval is wide: most strike observations have no clean reference and are left out (§5). The
share left out is 0.66 (GOOGL), 0.82 (GS) and 0.53 (IBM). For GS only 336 observations remain.

A narrow pass to note: IBM's forward share is 0.072, and its widened upper bound is 0.0998. That is NO FAULT by a
margin of 0.0002. The frozen seed decides it. On 20 other bootstrap seeds, the adversarial review got an upper
bound of 0.10008 to 0.10025 (UNCLEAR) on 3 (exploratory). So this pass sits inside the bootstrap's own noise.

**Read §4.8 before you read "forward vs close: NO FAULT".** The vendor's option snapshots are not taken at the
close in 2026, on all five names. Rule (b) passes only because the window is pooled.

## 2. Gates

```
earnings_vol from <clone>/src/earnings_vol/__init__.py
clone f5904a91f80a, src and params.yaml clean, venv = env.freeze.txt (8dcc667ee497e82a...)
17 frozen files match; run_probes.py seed 1 reproduced (exit 0)
loader.py SHA-256 d985d717085fb904796be5229017b1246ab3cbd5a090af98eaa8931068f530ed (recorded, not checked)
15 input files and the 82 option-chain files match
G4 GOOGL: 3826 chain_expiry rows and 1210 iv_daily rows on 1210 ok sessions equal
G4 GS: 3837 chain_expiry rows and 1214 iv_daily rows on 1214 ok sessions equal
G4 IBM: 3837 chain_expiry rows and 1214 iv_daily rows on 1214 ok sessions equal
G4 AAPL: 3851 chain_expiry rows and 1219 iv_daily rows on 1219 ok sessions equal
G4 AMZN: 3840 chain_expiry rows and 1215 iv_daily rows on 1215 ok sessions equal
```

(`aggregate.json` holds the first line with the full local path; it is shortened here.) G5: `aggregate.json` holds
no date and no per-day value.

## 3. Verdicts per name and rule

The sample is the changes between consecutive `ok` sessions outside the event zone: GOOGL 703, GS 701, IBM 689.
The rest were left out because a snapshot was not `ok` (975, 971, 972) or because a day was in the event zone (34,
40, 51).

For the (c) rules:

- "raw" is the bootstrap bound: lo at the 0.05/12 quantile, hi at the 0.95 quantile.
- "widened" moves both bounds away from the share by the rule's factor c (forward 1.35, filter 1.1, strike 1.35,
  roll 1.2). The widened bounds decide the verdict.
- FAULT when lo > 0.10. NO FAULT when hi < 0.10. Otherwise UNCLEAR.

| Name | Rule | n | Share | Raw [lo, hi] | Widened [lo, hi] | Verdict | Left out |
|---|---|---:|---:|---|---|---|---|
| GOOGL | (a) differential | 3,826 atoms, 1,210 sessions | 0 mismatches | | | MATCH | |
| GOOGL | (b) synthetic truth | 1,210 sessions | worst error 7.2e-15 | | | NO FAULT | |
| GOOGL | (b) forward vs close | 682 | median \|d\| 5.89 bp | [4.85, 7.49] (95%) | | NO FAULT | |
| GOOGL | (c) forward | 1,905 | 0.043 | [0.024, 0.060] | [0.018, 0.066] | NO FAULT | 5 dropped; σ_f 6.68 bp |
| GOOGL | (c) filter | 631 | 0.006 | [−0.014, 0.020] | [−0.016, 0.022] | NO FAULT | no clean reference 0.659 |
| GOOGL | (c) strike | 631 | 0.221 | [−0.024, 0.375] | [−0.110, 0.428] | **UNCLEAR** | no clean reference 0.659 |
| GOOGL | (c) roll | 675 | 0.016 | [−0.057, 0.064] | [−0.072, 0.074] | NO FAULT | class switch 17, no common expiry 11 |
| GS | (a) differential | 3,837 atoms, 1,214 sessions | 0 mismatches | | | MATCH | |
| GS | (b) synthetic truth | 1,214 sessions | worst error 1.0e-14 | | | NO FAULT | |
| GS | (b) forward vs close | 682 | median \|d\| 6.32 bp | [5.39, 7.66] (95%) | | NO FAULT | |
| GS | (c) forward | 1,975 | 0.023 | [0.013, 0.032] | [0.010, 0.035] | NO FAULT | 0 dropped; σ_f 4.56 bp |
| GS | (c) filter | 336 | (1 switch; bound 0.002) | | | NO FAULT | no clean reference 0.824 |
| GS | (c) strike | 336 | 0.051 | [−0.078, 0.132] | [−0.123, 0.160] | **UNCLEAR** | no clean reference 0.824 |
| GS | (c) roll | 680 | 0.019 | [−0.009, 0.045] | [−0.015, 0.050] | NO FAULT | class switch 12, no common expiry 9 |
| IBM | (a) differential | 3,837 atoms, 1,214 sessions | 0 mismatches | | | MATCH | |
| IBM | (b) synthetic truth | 1,213 sessions | worst error 7.2e-15 | | | NO FAULT | |
| IBM | (b) forward vs close | 665 | median \|d\| 7.96 bp | [6.00, 10.20] (95%) | | NO FAULT | |
| IBM | (c) forward | 1,881 | 0.072 | [0.049, 0.093] | [0.040, 0.0998] | NO FAULT | 0 dropped; σ_f 7.59 bp |
| IBM | (c) filter | 843 | 0.001 | [−0.009, 0.006] | [−0.010, 0.0065] | NO FAULT | no clean reference 0.531 |
| IBM | (c) strike | 843 | 0.023 | [−0.132, 0.094] | [−0.186, 0.119] | **UNCLEAR** | no clean reference 0.531 |
| IBM | (c) roll | 656 | 0.015 | [−0.040, 0.053] | [−0.051, 0.060] | NO FAULT | class switch 10, no common expiry 11, no value 12 |

Notes on the table:

- **Filter switches are rare.** GOOGL has 16, GS 1 and IBM 11. All three have fewer than 30, so the small-group
  bound decides on all three names (§6): 0.022, 0.002 and 0.010, each below 0.10. The bootstrap intervals printed
  for GOOGL and IBM do not decide. (*Correction, 2026-11-17: the first version said that only GS was below 30.*)
- **The any-reference guard** (strike) reads GOOGL 0.095 [−0.102, 0.231], GS 0.115 [−0.004, 0.210] and IBM 0.004
  [−0.168, 0.092]. The guard can only stop a NO FAULT. Here the clean reference is already UNCLEAR.
- **Robustness, blocks of 60** (does not decide), strike: GOOGL [−0.132, 0.438], GS [−0.116, 0.149], IBM
  [−0.184, 0.104]. All UNCLEAR. Every other rule stays NO FAULT.

## 4. Descriptive numbers (§11, no verdict)

### 4.1 AAPL and AMZN, the descriptive reference

They have the same pattern: everything passes except strike, which is UNCLEAR.

| Name | Forward | Filter | Strike | Roll | Forward vs close |
|---|---|---|---|---|---|
| AAPL | 0.021 [0.009, 0.034] | 0.016 [−0.002, 0.029] | 0.103 [−0.017, 0.184] UNCLEAR | −0.031 [−0.080, −0.013] | 5.16 bp |
| AMZN | 0.021 [0.010, 0.030] | 0 switches | 0.036 [−0.116, 0.129] UNCLEAR | 0.024 [−0.017, 0.061] | 4.54 bp |

Both are (a) MATCH and (b) NO FAULT.

### 4.2 Splits of the strike share, and the forward share at the 30-day level

In §4.2 and in the last two columns of §4.3, the brackets are the widened bounds of §3: lo at the 0.05/12 quantile
and hi at the 0.95 quantile, both moved away from the share by the rule's factor. They are not 95% intervals.

| Name | Listing | Other | Forward on `cm30_iv` | Forward on `cm30_blind_iv` |
|---|---|---|---|---|
| GOOGL | 0.229 [−0.025, 0.398] | −0.019 [−0.107, 0.047] | 0.028 [0.010, 0.044] | 0.032 [0.012, 0.053] |
| GS | 0.048 [−0.090, 0.136] | 0.004 [−0.051, 0.041] | 0.021 [0.006, 0.037] | 0.019 [0.005, 0.035] |
| IBM | 0.040 [−0.107, 0.109] | −0.020 [−0.099, 0.018] | 0.031 [0.017, 0.044] | 0.033 [0.018, 0.045] |
| AAPL | 0.054 [−0.012, 0.094] | 0.035 [−0.036, 0.098] | 0.015 [0.006, 0.023] | 0.014 [0.006, 0.022] |
| AMZN | 0.040 [−0.060, 0.106] | −0.004 [−0.073, 0.035] | 0.013 [0.005, 0.020] | 0.012 [0.005, 0.018] |

For GOOGL, most of the clean-reference strike share is in listing switches (a strike listed on one day only).
That reading uses the 34% of observations that have a clean reference. The any-reference listing share over all
observations is 0.103 [−0.024, 0.210]. The 2026 sessions add about nothing to it (clean share 0.002, exploratory),
so it is not a snapshot-timing effect (adversarial review, not checked again here).

### 4.3 to 4.6 The blind series, beside the VX slope

- **1 − slope** comes from the published VX\* slopes in [vx-ledger.md](../vx-ledger.md) §5. That comparison used
  its own sample of days, not the changes used here.
- **−2ρ1** is −2 × the lag-1 autocorrelation of the daily changes of `cm30_blind_iv`, with a 95% interval. It is
  the noise share if our series is truth plus independent day-to-day noise, and the true changes are not
  autocorrelated (§11.4).
- **The residual line** is the sum of the tested shares that reach `cm30_blind_iv`: forward, roll and strike (§11.6).
  The sum uses a joint bootstrap and has a 95% interval.

| Name | 1 − slope | −2ρ1, `cm30_blind_iv` | −2ρ1, `cm30_iv` | Residual line | Roll on `cm30_blind_iv` | Strike on `cm30_blind_iv` |
|---|---:|---|---|---|---|---|
| GOOGL | 0.227 | 0.357 [0.156, 0.554] | 0.352 [0.169, 0.541] | 0.239 [0.013, 0.515] | 0.034 [−0.046, 0.089] | 0.172 [−0.258, 0.477] |
| GS | 0.214 | 0.262 [0.036, 0.494] | 0.305 [0.084, 0.537] | 0.178 [0.052, 0.347] | 0.025 [−0.009, 0.056] | 0.134 [−0.089, 0.305] |
| IBM | 0.342 | −0.016 [−0.228, 0.209] | 0.124 [−0.077, 0.346] | −0.032 [−0.353, 0.232] | 0.205 [0.055, 0.300] | −0.270 [−0.894, 0.032] |
| AAPL | 0.166 | 0.118 [−0.077, 0.318] | 0.117 [−0.085, 0.338] | 0.181 [0.105, 0.269] | 0.019 [−0.027, 0.052] | 0.148 [0.014, 0.239] |
| AMZN | 0.186 | 0.142 [−0.050, 0.339] | 0.219 [0.063, 0.385] | 0.273 [0.104, 0.461] | 0.116 [0.013, 0.197] | 0.145 [−0.152, 0.341] |

What this shows, read with care (every reading here is exploratory):

- **GOOGL and GS.** −2ρ1 is about as large as 1 − slope, and so is the residual line. So day-to-day noise in our
  blind series could explain their low slopes. Which component carries the noise is not settled: the strike share
  on the blind series is 0.172 and 0.134, but its brackets hold 0, and its base groups are only 71 and 43. Reading
  −2ρ1 as the noise share also assumes that the true IV changes have no lag-1 autocorrelation. Nobody compared it
  with the −2ρ1 of Cboe's own series.
- **IBM.** −2ρ1 of the blind series is near 0, and so is the residual line. These checks do show one candidate:
  the roll share on the blind series is 0.205, with a widened lower bound of 0.055, above 0. §12.4 says that pair
  switches of this kind lower the slope and make no lag-1 autocorrelation, which fits −2ρ1 ≈ 0. The residual line is
  near 0 because 0.033 (forward) + 0.205 (roll) − 0.270 (strike) = −0.032, and the negative strike share is
  estimator noise. The roll share is a design property of the blind series, not a rule (§11.3).
  (*Correction, 2026-11-17: the first version said "these checks do not show what" makes IBM's slope low.*)
- **The shares have different denominators**, so the residual line is an approximation, not an identity (§11.6).

### 4.7 Common-mode forward error, upper bound: not informative

| Name | σ_c | Share at fixed expiries | `cm30_iv` | `cm30_blind_iv` |
|---|---:|---|---|---|
| GOOGL | 46.1 bp | 0.774 [0.049, 1.319] | 0.604 | 0.744 |
| GS | 45.5 bp | 0.787 [−0.024, 1.464] | 0.799 | 0.643 |
| IBM | 50.3 bp | 1.525 [0.172, 2.482] | 0.920 | 1.009 |
| AAPL | 40.4 bp | 0.842 [0.046, 1.495] | 0.734 | 0.734 |
| AMZN | 48.3 bp | 0.880 [−0.003, 1.492] | 0.714 | 0.745 |

σ_c² = var(d)/2, where d is the forward-vs-close series. The bound is valid but too loose to use: several shares are
above 1.

sd(d) = √2 σ_c is 57 to 71 bp, but the median |d| is only 4.5 to 8.0 bp. The first version said "a few large values
of d set var(d)". *Correction, 2026-11-17: that was wrong.* The large values are a regime, not a few days: most of
var(d) comes from 2026, when the snapshots are not taken at the close (§4.8). So σ_c measures snapshot timing, not
forward error, and the bound is not an upper bound on a forward error. With a robust scale of d (exploratory, from
the adversarial review) σ is 6.3, 6.6 and 8.2 bp, and the share at that σ would be about 0.014, 0.017 and 0.040.
The bound cannot rule out a common-mode forward error, and it does not show that one exists.

### 4.8 The vendor's snapshot timing changes in 2026 (exploratory, found by the adversarial review)

Not pre-registered. §14 makes every cut by period exploratory, and none of this changes a verdict.

- **The forward-vs-close gap is a regime.** In the frozen sample (adversarial review), the median |d| is 4.73,
  4.93 and 5.45 bp in 2020 to 2025 (GOOGL, GS, IBM), and **26.1, 24.4 and 50.8 bp in 2026** (n 183, 177, 175). In
  2026, 41% to 51% of the changes have |d| above 50 bp, against 0% to 4% in 2020 to 2024. My own re-derivation (a
  separate script on all `ok` sessions, nearest expiry with τ ≥ 5, event zones kept) gives the same picture on all
  five names: a median |d| of 3 to 9 bp a year in 2020 to 2025, and 13.6 (AMZN) to 41.0 (IBM) bp in 2026.
- **The 2026 snapshots are taken during the day, before the close.** Regress the forward change on the close
  returns of days t − 1, t and t + 1 (my run). In 2020 to 2025 the loadings are about 0.00, 0.98 to 1.00 and 0.00
  on every name. In 2026 they are 0.11 to 0.22, 0.75 to 0.89 and 0.04 to 0.07 (IBM: 0.02, 0.89, 0.02). The
  adversarial review also found that the 2026 parity spot is inside the day's high-low range on 99% to 100% of the
  days. A snapshot taken at the same time of day on both days, before the close, gives this pattern.
- **One episode is a full day late.** From 2025-03-24 to 2025-04-01, the snapshot dated t carries the close of t − 1
  (adversarial review; not checked again here).
- **Rule (b) passes only because the window is pooled.** 2026 alone is 2.4 to 5 times the 10 bp line. A run of
  the frozen rules on sessions after 2026-10-26 would be all in this regime.
- **It lowers the VX slope, but it is not the whole gap.** Before the run I wrote the prediction: if the timing
  lowers the slope, the 2026 slope is clearly lower than the 2020 to 2025 slope on most names and pooled. One-session
  slopes of dln VX on dln ours, no intervals:

  | Name | 2020 to 2025 | 2026 | All |
  |---|---:|---:|---:|
  | AAPL | 0.854 | 0.723 | 0.834 |
  | AMZN | 0.837 | 0.748 | 0.814 |
  | GOOGL | 0.794 | 0.633 | 0.773 |
  | GS | 0.814 | 0.638 | 0.786 |
  | IBM | 0.647 | 0.692 | 0.658 |
  | Pooled | 0.784 (n 2,715) | 0.696 (n 982) | 0.767 |

  The prediction holds on 4 of 5 names and pooled; IBM is the exception. But the 2020 to 2025 slopes are still well
  below 1, so the timing explains part of 1 − slope, not all of it.
- **ADR 0002's "the snapshots are closing quotes"** came from a pooled median of 6.3 bp. It holds for 2020 to 2025
  and not for 2026.
- **The main study:** 155 of the 349 events in the primary (daily) sample have day 0 in 2026. A snapshot taken
  during day t, before the close, still falls before an after-close announcement on day t and after a before-open
  announcement on day t. So the pre/post order of the crush sessions should hold. That is an inference, not a
  measurement. The 2025 episode touches one crush-eligible event (MU, day 0 2025-03-21; its day +1 is 2025-03-24).
- **Since 2026-11-18: the timing is per day** (the pre-registered
  [snapshot-timing check](../snapshot-timing/results.md), its frozen map). Two corrections to this section. (1) The
  2026 timing is a property of the day, not of the year: from 2026-01-02 to 2026-02-18 every session is at the close;
  from 2026-02-19, 76 sessions of 2026 are off and the others at the close (2025 has 7 off days, 2024 one). A yearly
  split mixes the two: on changes with both ends at the close the pooled 2026 slope is 0.809, against 0.799 for
  2020 to 2025, and 0.599 on 2026 changes with an off end. (2) The late episode is 6 sessions, 2025-03-24 to
  2025-03-31; 2025-04-01 is at the close (a change into it starts from the late 2025-03-31). The check finds the
  timing's shift of the event measures H1–H4 inside one standard error, and the inference above about the pre/post
  order holds in the data: the off day −1 snapshots sit before the news and the off day 0 ones after it.

### 4.9 Components no rule can see

These are unchanged from §11.8: mid noise at fixed strikes, partial staleness, common-mode forward error, `r_cont`
and the τ-interpolation of `cm30_blind_iv`. The result says nothing about them.

## 5. Deviations

No change to the frozen code. The only change after the freeze is the loader (`loader.py`, SHA-256
`d985d717085fb904796be5229017b1246ab3cbd5a090af98eaa8931068f530ed`), which §3 and §14 allow.

G4 passed on the first loader version, so no fix was needed. The loader's choices are listed in
[deviations.md](deviations.md). The main one: the Yahoo close is the close as quoted on its own day.

One disclosure was missing from the first version (adversarial review, checked here). Between the freeze (02:15:34Z)
and the run, two scratch scripts besides `g4dev.py` read real stage data while the loader was written:
`explore.py` (02:17:43Z: the columns and types of the stage tables, the security and alias rows, the snapshot
status counts per name, the event counts per name) and `time1.py` (02:18:41Z: the time to parse one option-chain
file). They computed no statistic of any rule, and they did not read Yahoo. [deviations.md](deviations.md) now names
them.

## 6. Run time and memory (measured)

- **The whole run took 382 s** (6 min 23 s): gates G1 to G3, the loader, G4 and every rule plus the robustness rerun
  on five names. Peak memory was 1.0 GB.
- **The pre-registration estimated 15 to 30 minutes per name** (§13). That estimate was wrong. The real chains have
  about 3.2 atoms a session, like the synthetic ones, so the cost per session is similar.

## 7. Not done, and limits

- §10 steps 1 and 2 (mechanism trace, minimal reproduction) and `--widen` were not run, because they apply only
  to a FAULT.
- IBM's truth check covers 1,213 sessions, not 1,214: one `ok` session has no forward (`no_forward_day` 1).
- The strike rule cannot decide with this window. Its UNCLEAR is a statement about power, not evidence of a fault
  or of no fault.
- `aggregate.json`'s `gates[0]` line held the full local path of the scratch clone, which includes the local user
  name. In the committed copy that one string reads `earnings_vol from <clone>/src/earnings_vol/__init__.py`;
  nothing else changed. The SHA-256 at the top is the committed copy's; the run's own file had SHA-256
  `4b1509b8db7c7b877b3f862edd3a04e230d8ae4177fa0ace6e84ae308e546461`.

## 8. Validation (row 6)

- **Verifier (Sonnet).** It re-ran the frozen phase 2 from the frozen files and re-derived every verdict. It agrees
  on every number in §1 to §4.7, and on the widening arithmetic to 0.0. It could not check the per-name session
  counts without the raw data.
- **Adversarial review (Opus).** It re-derived every verdict from the aggregates, ran the frozen forward rule
  again, rebuilt d separately, and attacked the loader (split days, the IBM spin-off, ex-dates, `r_cont` units). The
  §10 outcome UNCLEAR survives, and the loader survives. It refuted one sentence ("a few large values of d set
  var(d)") and found the 2026 snapshot timing (§4.8), the missing disclosure (§5), the incomplete filter note (§3)
  and IBM's undersold reading (§4.3). I checked each before changing the text: the filter group sizes and IBM's roll
  numbers in `aggregate.json`, the scratch scripts' times and contents, and the regime and the lag loadings with my
  own scripts.
