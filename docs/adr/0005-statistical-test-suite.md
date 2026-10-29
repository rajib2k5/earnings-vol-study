# ADR 0005: Statistical test suite

- **Status:** Accepted (milestone 0), **revised 2026-10-28 after the milestone-0 methodology review**, and again
  after the milestone-0 delta review (notes below).
  - No statistics code existed in `src/` at milestone 0. *Milestone 3 (2026-10-29)* built it
    (`src/earnings_vol/stats/`), and gate G1 passed for all four primaries on the calibrated design; the measured
    numbers, and the places where the real design differs from what this ADR expected (8 RUNUP seasons, unbalanced,
    so `rad_season_p` is H2's primary; $\hat{\bar\rho}$ = 0.30 for the crush), are in
    [`docs/milestones/03-event-study.md`](../milestones/03-event-study.md).
  - Every rejection rate quoted here comes from a prototype in `research/prototypes/`. Each prototype re-runs with
    fixed seeds and has its output kept beside it (§2g).
  - Gate G1 of §5 is a milestone-3 deliverable. It must pass before any test result is reported.
  - *Revised 2026-10-29, after the milestone-3 review* ([ledger](../validation/m3-ledger.md); fixes in the milestone
    page's §9). G1 still passes for all four primaries on the calibrated design (4.60 / 0.40 / 0.50 / 4.60% after the
    second fix round below; 4.45 / 0.40 / 0.50 / 4.75% after the first). Three things changed or are now stated:
    - **H4 is gated on its own statistic.** The first build simulated H4 as the day-0 change of the same cm30 series
      as H1, with the cm30 calibration, on H4's 262 events: evidence about the crush process, not about ΔSIGMA_D. G1
      now simulates a σ_d series per company with the σ_d usable mask and a calibration from the real σ_d baseline
      changes and ΔSIGMA_D values (ρ₁ −0.33, same-date correlation 0.08/0.16, φ 0.87, jump 2.8). The DGP's scale is
      calibrated too, so shifts and company effects are in real log points.
    - **The calibrated DGP does not reproduce every moment.** The AR coefficient of the baseline levels is not
      reproduced: the corrected estimator reads 0.9984 ± 0.0043 on panels simulated at the calibrated φ against 0.985
      on the real data (z −3.1; σ_d: 0.919 against 0.868, z −2.9), and 0.96 in a round trip at φ = 0.90. The real data
      mean-revert more than the design, which is the stricter side for the ramps. ρ₁ is 2.1 (cm30) and 1.3 (σ_d)
      simulation sd too weak; the other moments are within one sd (`research/prototypes/g1_moments.py`, re-run after
      the second fix round).
    - **H3's comfortable pass rests on mean reversion.** With only φ changed (`research/prototypes/g1_phi.py`, 10,000
      replications per φ, seeds recorded), PERSIST_10's primary rejects 0.47% at the calibrated φ = 0.985, 0.72% at
      0.99, 1.64% at 0.995 and 5.57% at φ = 1. **At φ = 1 it is liberal**: §5 sets the bar for the replications used,
      and at 10,000 that bar is 5.57% (`g1.binom_band(10000)`), not 2,000's 6.30%. On the first fix round's
      calibration it read 5.63% (the delta review's fresh seeds) and 5.86% (the first fix round's five blocks), above
      that bar; on this round's (the day-0 jump no longer reads H1's mean, below) it reads 5.57%, on the bar's edge
      and 2.6 se above 5%. It does not bind: at the real corrected φ (≈ 0.985) and at 0.995 (1.64% here; 1.65–1.82%
      on the earlier calibration) it is well inside the band. *Corrected 2026-10-29, second fix round:* the first fix
      round wrote "5.86% … inside the 6.30% bar", applying the 2,000-replication bar to 10,000 replications (delta
      review, [ledger](../validation/m3-delta-ledger.md) claim 3).
  - *Revised again 2026-10-29, after the delta review of the fix round* ([ledger](../validation/m3-delta-ledger.md);
    the milestone page's §9, second round). G1 now mirrors production in two more places and decides near-bar
    robustness rows on more replications:
    - **The day-0 jump no longer reads the tested mean.** `calibrate()`'s day-0 variance ratio is taken over
      (A_i − Ā)/s_i around company means, not A_i/s_i, so H1's mean crush cannot enter the calibrated jump through s_i
      varying within a company: cm30 ratio 4.70 → 3.32, jump 2.70 → 2.14 (σ_d 2.785 → 2.789). H1's calibrated rate
      4.45 → 4.60%; H1's robustness rates rise 1–3 points; no verdict changes.
    - **H4's series is adjusted as production adjusts ΔSIGMA_D**: with the cm30 β estimated on the replication's cm30
      series and on the same ln VIX path, not with a β re-estimated on σ_d (`g1.second_series`). H4's calibrated rate
      4.75 → 4.60%.
    - **Near-bar robustness rows are re-measured** (§4, dated note of the second fix round).
- **Date:** 2026-10-28
- **Related:** [0004](0004-baseline-and-event-windows.md) (what is tested), [0003](0003-iv-measures.md) (E, σ_d),
  [data model](../architecture/data-model.md) (`event_measures`, `results`)

> **Revised after milestone-0 review** ([ledger](../validation/m0-methodology-ledger.md)). Five claims of the first
> version were refuted or stale. Two fixes were then themselves refuted: the reviewer's interim proposal, and the first
> draft of this revision, which a second adversarial review attacked.
>
> 1. **Refuted (claim 7d, N7): "the primary statistic for every event test is BMP with an overlap-weighted KP
>    adjustment".**
>    - For RUNUP and PERSIST_10 that statistic, `kp_ow_t`, needs the autocorrelation matrix $R$, whose estimator the
>      milestone-0 text left open.
>    - Read as "pooled, demeaned per baseline", it rejected 0.9–1.5% when events were correlated, at the real design
>      (N = 352, §2g). Read as uncentred, it rejected 5.0–6.7%. Under mean reversion it rejected 0–0.1% either way.
>    - **Changed:** the primary statistic is a **two-way cluster-robust t** (§2b): day-0 date × firm for H1/H4, season ×
>      firm for H2/H3. Neither uses $\hat R$. $\hat R$ is now specified exactly (§1) and enters robustness rows only.
> 2. **Refuted (7b): "a wrong ŝ_i costs efficiency, not size".**
>    - That is true only when every event's effect is 0. BMP tests the *precision-weighted* mean.
>    - When the equal-weighted mean of RUNUP was exactly 0 but effects grew with $s_i$, BMP rejected 49.1% (§2g, D5).
>    - **Changed:** H1–H4 are stated as **equal-weighted** means, the quantity the report shows. Every BMP-based
>      statistic is robustness, labelled with its estimand.
> 3. **Refuted (claim 9): "this generalisation is ours, and we know of no published procedure that matches it".**
>    - Kolari, Pape & Pynnönen (2018) adjust the KP test for the average overlap of event windows.
>    - Pynnönen (2022) gives the per-pair overlap weight and an estimator of the average correlation.
>    - **Changed:** `kp_ow_t` is restated as the per-pair form of their adjustment, kept for one-session measures only.
>      The KP-2010 row `kp_t` (r̄ over all pairs) is deleted, and their average-overlap statistic `kpp_t` replaces it
>      (§2e).
> 4. **Refuted (claim 6): "ALIV_t equals the ramp-weighted sum of one-session abnormal changes, exactly".** It is exact
>    only when every session in the span is observed. **Changed:** §1 uses span changes across gaps.
> 5. **Stale (N2, N12).**
>    - The KP prototypes *are* in `research/prototypes/` and re-run identically. The first version said they were lost.
>    - The Patell mutation "L instead of L−1" moves size only to 5.03%, which the 2,000-replication band cannot catch.
>      §5 adds a moment test that can.
> 6. **Tested and rejected: the reviewer's interim fix, a *date*-clustered cross-sectional t as primary for H2/H3.**
>    - At the real design it rejects **31.9–36.4%** for RUNUP and PERSIST_10 under ρ = 0.1 (§2g). A ramp spans about
>      60 sessions, so it shares dates with the other events of its season, not just those on its own day 0.
>    - ISO-week clusters fail too (23.5–28.2%).
>    - The second review re-ran this with 8,000 replications. Date clusters still rejected 9.5–10.4% at ρ = 0.01 and
>      22.7–25.2% at ρ = 0.05.
> 7. **Refuted by the second review: the first draft of this revision used a *one-way* season-clustered t for H2/H3
>    and a one-way date-clustered t for H1/H4, with a Webb wild bootstrap as fallback.** Verified by re-measuring
>    (`research/prototypes/h2h3_followup_sim.py`, §2g, table 3):
>    - **Firm-level persistence.** When firms differ in a drift of abnormal log IV, or in their mean effect, the events
>      of one firm are correlated across seasons and dates, and one-way clusters miss it.
>      - Season clusters with a firm drift of sd 0.0015 per session: 6.55/6.80%.
>      - Date clusters with random firm effects on CRUSH: 9.4% at sd 0.01, 28.1% at sd 0.03.
>    - **The fix holds.** Two-way clustering with firm as the second dimension (Cameron, Gelbach & Miller 2011; Petersen
>      2009) holds 4.3–6.1% in those designs.
>    - **The fallback was worse than the statistic it replaced.** The Webb wild cluster bootstrap rejected more often
>      than CR1 in every random-walk design (6.45% against 5.95% for PERSIST_10 in D2). It is deleted. §5 now says what
>      happens if gate G1 fails.
>    - **The size band.** The band quoted as "binomial 99%", [3.74, 6.26], was the normal approximation. §5 now uses
>      the exact binomial quantiles.

> **Revised after the milestone-0 delta review** ([delta ledger](../validation/m0-delta-ledger.md), claims 1b, 1c,
> 1d / N2). The formulas and the simulated sizes survived. Three statements did not:
>
> 1. **Refuted citation (1b): "the $t_{\min(G)-1}$ reference follows Cameron & Miller (2015)"** (§2b). The critical
>    value from the smaller cluster count is Cameron, Gelbach & Miller's (2011). Cameron & Miller (2015, §VI.E) know
>    of no ideal approach for multiway clustering with few clusters. §2b now says both.
> 2. **Refuted (1c): "`rad_season_p` can pass Holm only from the fourth step on"** (§2f and §4). Re-derived for
>    $m = 7$: step 4's threshold is 0.05/4 = 0.0125, below the floor 2/128 = 0.0156. The floor first passes at the
>    **fifth** step (0.05/3), after four other rejections. Checked with statsmodels' Holm.
> 3. **Gap (N2): the planned statsmodels check did not pin the reference distribution** (§3, "Standard errors").
>    statsmodels' cluster covariance defaults to normal p-values (`use_t=False`), which at G = 7 rejected
>    10.35–11.22%. G1's size designs caught that only for the intercept-only H1–H4. **Changed:** the 4-event check
>    requires `use_t=True` and asserts the degrees of freedom and the p-value. G1 adds a reference-distribution check
>    on every reported row, regressions included (§5). The mutation table now quotes the measured 10.35 / 11.22%
>    instead of "not yet measured".
>
> Not changed here: ledger N3 (the non-PSD fallback can return $\hat V = 0$), N4 (G1's 6.30% bar cannot separate 5%
> from 6% at 2,000 replications), N5 and N11. They were not in this round's brief and stay open.

## In one paragraph

Every tested quantity is a weighted sum of abnormal one-session changes, $A_i = \sum_t a_{i,t} e_{i,t}$ (ADR 0004).
The four event hypotheses are about the **equal-weighted mean** of $A_i$ in log points, which is what the report shows.
Two kinds of dependence matter:

- **Through calendar dates:** events whose windows share dates are correlated.
- **Through firms:** the same firm's events share its persistent features, such as a drift in its abnormal IV or a
  firm-specific size of reaction.

The primary statistic is therefore a **two-way cluster-robust t** (Cameron, Gelbach & Miller 2011; Petersen 2009).
CR1 in each dimension, combined as $V_A + V_B - V_{A\cap B}$, with $t_{\min(G)-1}$ critical values.

- **One-session measures** (CRUSH and ΔSIGMA_D) cluster by **day-0 date × firm**.
- **Run-up and persistence ramps** cluster by **season × firm**. A ramp spans about 60 sessions and shares dates with
  the other events of its season.

Simulated at the real daily design (N = 352, every input estimated, §2g):

- **the one-session primary:** 4.75–5.80% in the nine size designs, and 4.15–5.80% across all twelve designs
  (inside the exact 99% binomial band [4.12, 5.90]), including firm drift, firm effects and mean
  reversion;
- **the ramp primary:** 4.3–6.1% with random-walk levels, with and without firm drift and firm effects;
- **when IV levels mean-revert:** 1.7–2.3% for the ramps. That is conservative, not mis-sized.
- **The two known weak spots:** PERSIST_10 runs about one point liberal (6.0–6.1%) under random-walk levels at
  ρ = 0.1, and very unbalanced seasons break the season clustering (§2b states the rule for them).

The Kolari-Pynnönen family is reported as robustness and labelled with its estimand, the precision-weighted mean. That
family is BMP standardisation with the KP (2010) or KPP (2018) adjustment.

Companions:

- robustness rows per hypothesis (§4): the one-way clustered t; the KPP average-overlap statistic and its per-pair
  form; BMP; the two-way clustered standardised mean; a Rademacher randomisation p-value by season; Patell for the
  crush; a generalised sign test and a rank test;
- regressions with two-way firm × date standard errors (firm × season for ramp outcomes), and one-way date clustering
  as robustness;
- a seven-hypothesis primary family corrected with Holm. Everything else is labelled exploratory.

## Context

- The returns event-study toolkit (Patell 1976; BMP 1991; KP 2010; KPP 2018) assumes abnormal returns that are
  uncorrelated over time. It also assumes events correlated only on shared calendar days (Pynnönen 2022, Assumption 1).
- Our setting breaks the first assumption and stretches the second:
  1. **IV is persistent.** Level measures (run-up, persistence) are long weighted sums of daily changes. Daily changes
     of mid-quote IV are negatively autocorrelated, because quote noise in a level shows up as an MA(1) in changes. Over
     weeks, IV levels also mean-revert.
  2. **Events cluster partially.** About 50 names report across 3–5 weeks per season. The real daily design has 352
     events on 187 distinct day-0 dates in 7 seasons (§2g). A one-session crush shares a date only with events on the
     same day 0. A 60-session ramp shares dates with almost every event of its season.
- The owner must be able to write each formula on a whiteboard and say what it assumes.

## Decision

### 1. One representation for all tested quantities

With $e_{i,t}$ the abnormal one-session change of event $i$ on rel_day $t$ (ADR 0004 §2) and $s_i$ its baseline
standard deviation:

| Quantity | Weights $a_{i,t}$ |
|---|---|
| CRUSH | $a_{i,0}=1$, all others 0 |
| RUNUP $=\text{ALIV}_{-1}$ | $a_{i,t} = n_{i,t}/\lvert B_i\rvert$ for $t \in (\min B_i, -1]$, where $n_{i,t}$ = the number of baseline sessions before $t$. It ramps from 0 to 1 across the baseline, then stays 1 up to −1. |
| PERSIST_h | the same ramp, continued to $+h$ |
| ΔSIGMA_D | $a_{i,0}=1$ on the σ_d series |

**Exactness, and gaps** (revised after the review, ledger claim 6).
$\text{ALIV}_{t} = \frac{1}{\lvert B\rvert}\sum_{u\in B}(x_t-x_u)$, minus the same for VIX, and each $x_t-x_u$
telescopes into a sum of changes.

- **Every session observed.** If every session in $(\min B_i, t]$ is observed, those changes are one-session changes
  and the table is exact. The first version claimed exactness in general. With 3 unobserved sessions the one-session
  sum was off by 0.038 log points, because the changes into and out of a missing session do not exist.
- **The rule across gaps.** Walk the *observed* sessions $o_0 = \min B_i < o_1 < \dots < o_K = t$ of the closed
  interval $[\min B_i, t]$. For $k = 1, \dots, K$ use the **span change**
  $e_{i,k} = (x_{o_k} - x_{o_{k-1}}) - \beta_s (m_{o_k} - m_{o_{k-1}})$, with weight
  $a_{i,k} = n_{i,o_k}/\lvert B_i\rvert$.
  - $\min B_i$ is always observed, because $B_i$ holds observed sessions only, and the first change starts there.
  - *Corrected after the second review.* The first draft walked "the observed sessions of $(\min B_i, t]$". That drops
    the change out of $\min B_i$, which is off by 1.4e-4 to 1.7e-3 in the reviewer's cases.
- **Why that is exact.** ADR 0004 §1 removes unobserved sessions from $B_i$, so no baseline session lies strictly
  inside a gap. The one-session weights inside the gap are therefore all equal, and the gap's changes collapse into
  one span change with that **constant weight**. The review's probe confirms it to 1.7e-16 (`p06_identity.py`).
- **For the variance algebra below,** the span change is written back on the one-session grid with the same weight on
  every session it spans. Its variance is then $s_i^2\,\mathbf 1^\top R_{h}\mathbf 1$, with $R_h$ the $h\times h$ block
  of $R$. One weight vector therefore serves both the value and its variance. The two options the review named ("span
  changes with their own $R$" and "a weight held constant across the gap") are the same thing here.
- **The coarse (Mon/Wed/Fri) sample** is all span changes. Its run-up and persistence use this rule, and its 2-session
  crush is $a = (1,1)$ over its span.
- **Holes.** A zone excluded *inside* $B_i$ (another event's or an orphan's) removes that zone's levels from the
  baseline mean, but its net level change still enters $A_i$ with weight $n/\lvert B_i\rvert$. That adds variance, not
  bias, as long as IV returns across the zone to the level it left. Such holes are rare: with spacing of at least 53
  sessions, a same-security zone always falls at the start of $B_i$ (ADR 0004).

**Unit test** (planned, `tests/test_ramp_identity.py`). It uses a random path with an excluded hole inside $B$, then
adds three cases:

- three unobserved sessions inside $(\min B, t]$;
- the Mon/Wed/Fri pattern;
- an unobserved session at $t-1$.

It asserts that the span-change sum equals $\text{ALIV}_t$ to 1e-12 in every case. It must be seen to **fail** at
that tolerance in three cases:

- when one-session changes are used across a gap;
- when the weight is $n/(\lvert B\rvert-1)$;
- when the walk starts after $\min B_i$.

The review measured differences of 4.0e-4 to 2.1e-2 for these mutants, so no looser threshold (such as 1e-3) would do.
Two more cases come from the second review: a gap at $\min B + 1$, and an unobserved session inside an excluded
zone. The review checked the rule on all of them to 1.1e-16.

**Variance under autocorrelation.** If $e_{i,t}$ is stationary under H0 with variance $s_i^2$ and autocorrelations
$\rho_k$, then
$$
\operatorname{Var}(A_i) = s_i^2\; a_i^\top R\, a_i,\qquad R_{tu}=\rho_{\lvert t-u\rvert},\qquad
SA_i = \frac{A_i}{s_i\sqrt{a_i^\top \hat R\, a_i}} .
$$

- **Where $\hat R$ is used.** $SA_i$ and $\hat R$ enter **only the robustness rows** that standardise: BMP, `kp_ow_t`,
  `kpp_t`, `sa_twoway_season_t`, Patell. **No primary statistic uses $\hat R$** (§2b).
- **One-session measures.** For CRUSH and ΔSIGMA_D, $a^\top R a = 1$, so $\hat R$ does not enter at all. For the coarse
  2-session crush it is $2 + 2\hat\rho_1$.

**$\hat R$, exactly** (specified after the review, ledger N7; the first version left the estimator open):

- $z_{i,t} = e_{i,t}/s_i$ over the **clean baseline one-session changes** of event $i$. Those are changes whose two
  sessions are both in $B_i$. $s_i$ is their sample sd (ddof = 1), as in ADR 0004 §2.
- $$\hat\rho_k = \frac{\sum_i \sum_{t} z_{i,t}\,z_{i,t-k}}{\sum_i\sum_t z_{i,t}^2},\qquad k = 1,\dots,10.$$
  The numerator runs over pairs of clean baseline changes **of the same event** that are $k$ sessions apart. The
  denominator runs over all clean baseline changes. It is pooled over every event in the test's event set, about
  10,000 changes in the daily sample.
- **Uncentred.** Neither $z$ is demeaned. The model has no drift (ADR 0004 §2, "No intercept"), so the mean-zero
  estimator is the consistent one.
  - Per-baseline demeaning biases each $\hat\rho_k$ by about $-1/L$ (L ≈ 30). Over 10 lags along a 60-session ramp,
    that roughly halves $a^\top\hat Ra$.
  - Measured: `kp_ow_t` rejected 0.9–1.5% with the demeaned $\hat R$, against 5.0–6.7% with the uncentred one (§2g).
- $\hat\rho_k = 0$ for $k > 10$.
- **Positive semi-definiteness.** If $1 + 2\sum_k\hat\rho_k\cos k\lambda < 0$ anywhere on a 512-point grid of
  $[0,\pi]$, multiply each $\hat\rho_k$ by $(1-k/11)$ (Bartlett) and **check again**. If it is still negative, use
  $\hat R = I$ and flag the run `rhat_identity`.
  - A non-negative spectral density makes every Toeplitz section of $\hat R$ PSD.
  - The second check was added after the second review. A single taper can leave the density negative: for
    $\hat\rho_1 = -0.9$ it gives $1 - 1.64\cos\lambda$.
  - This affects robustness rows only.
- **The coarse sample** cannot see one-session lags. It takes $\hat\rho_k$ from the daily sample, assuming
  stationarity. Its per-session scale is
  $s_i^2 = \frac{1}{K}\sum_k e_{i,k}^2 / (\mathbf 1^\top \hat R_{h_k}\mathbf 1)$ over its $K$ baseline span changes of
  length $h_k$. This is the "autocorrelation correction" ADR 0004 §4 refers to.
- **Truncation.** Truncating at lag 10 ignores mean reversion beyond 10 sessions, so $a^\top\hat Ra$ overstates the
  variance of a ramp. That makes $SA_i$ too small for RUNUP and PERSIST.
  - *Revised:* the first version called this "conservative for Patell and irrelevant to the validity of BMP". That
    claim was derived, not measured, and it is withdrawn.
  - It matters only for the standardised robustness rows, and §2g measures them.

### 2. Event tests: formulas

$N$ events with values $A_i$; $\bar A = \frac1N\sum A_i$. Every two-sided test is at 5%.

**(a) Cross-sectional t** (equal-weighted mean, raw units):
$$
t_{CS} = \frac{\bar A}{s_A/\sqrt N},\qquad s_A^2 = \tfrac{1}{N-1}\sum (A_i-\bar A)^2 \quad\sim t_{N-1}.
$$
It is robust to event-induced and heterogeneous variance, because the variance comes from the event values
themselves. It assumes independent events.

- At the real design it rejects 35–41% for the ramps and 6.6–7.4% for the crush under ρ = 0.1 (§2g).
- It is **not reported** as a test.
- Its numerator is the estimate every primary row reports.

**(b) Two-way cluster-robust t: PRIMARY for H1–H4.** Same estimate $\bar A$, residuals $u_i = A_i - \bar A$. For a
clustering $g$ with $G$ groups, the one-way CR1 variance is
$$
\hat V_g = \frac{G}{G-1}\,\frac{1}{N^2}\sum_{c=1}^{G}\Big(\sum_{i\in c}u_i\Big)^2 .
$$
The two-way variance for dimensions $A$ and $B$ (Cameron, Gelbach & Miller 2011) is
$$
\hat V = \hat V_A + \hat V_B - \hat V_{A\cap B},\qquad t = \frac{\bar A}{\sqrt{\hat V}}\quad\text{compared with } t_{\min(G_A, G_B)-1}.
$$
If $\hat V \le 0$, use $\max(\hat V_A, \hat V_B)$. The $t_{\min(G)-1}$ reference follows Cameron, Gelbach & Miller
(2011), who take the critical value from the smaller cluster count. *Corrected after the delta review (1b):* this
sentence credited Cameron & Miller (2015), which gives no degrees of freedom for multiway clustering. For multiway
clustering with few clusters, Cameron & Miller (2015, §VI.E.3) say they are "not aware of an ideal approach" (as
read by the delta review's literature channel). That is why §2g and gate G1 measure the size at our G instead of
assuming it.

- **`twoway_date_t`, for one-session measures (CRUSH, ΔSIGMA_D; H1, H4).** $A$ = day-0 date, $B$ = firm
  (`security_id`).
  - Same-date dependence of any kind is covered. That includes dependence that appears only on announcement days
    (sector news, contagion between reporters), which a correlation estimated on baselines cannot see.
  - So is firm-level dependence: a firm whose reactions are persistently larger or smaller than the mean.
  - There are about 187 date clusters in the prototype design and 50 firms, so $t_{49}$. The 187 is inflated by the
    synthetic firms' ±3-session jitter. Milestone 1 counts the real figure, and it will be lower.
  - **Why firm as well as date** (second review, measured). With random firm effects on CRUSH, date-only clusters
    rejected 9.4% (sd 0.01) and 28.1% (sd 0.03). Two-way held 4.75%. Firms differ in how much they crush, so this
    is the realistic case.
- **`twoway_season_t`, for ramp measures (RUNUP, PERSIST_h; H2, H3).** $A$ = season, $B$ = firm.
  - The season is `events.season` (calendar quarter of day 0). A season with fewer than 10 events in the test's event
    set is merged into the neighbouring season whose median day 0 is nearest, repeated until none is left.
  - The daily design has 7 seasons of 49–52 events after merging. The December reporters join January's season, and
    the October 2026 tail joins July's. So $t_6$ = 2.447.
    - *Corrected 2026-10-29, after the milestone-3 review (F1):* the prediction about the tail was wrong. In the real
      RUNUP set the October 2026 tail has **19** events (≥ 10), so the merge rule above correctly keeps it as its own
      season: **8** seasons (50/46/49/50/48/45/49/19), unbalanced, and H2's p comes from `rad_season_p` (below). The
      PERSIST_10 set ends earlier and has 7. The rule did not change; only this sentence's expectation did. Because
      `rad_season_p` then sits on its floor $2/2^G$, H2's Holm verdict depends on G: see the correction in §4.
  - Within a season it allows any dependence: overlap, autocorrelation, lagged and contagion effects. Within a firm it
    allows any dependence across seasons.
  - It still assumes that *different* firms in *different* seasons are roughly independent. That is not exact. Of the
    off-diagonal overlap mass $\sum_{i\ne j}a_i^\top a_j$, 4.6% (RUNUP) and 9.4% (PERSIST_10) falls between
    seasons (second review; re-measured).
    - Of that cross-season mass, 67% (RUNUP) and 48% (PERSIST_10) involves the off-cycle reporters (ORCL, ADBE, COST
      and their synthetic copies), which are only 30 of the 352 events.
    - That is the likely reason PERSIST_10 runs at 6.0–6.1% in the random-walk design (§2g). The reason is inferred,
      not tested.
  - **Why firm as well as season** (second review, measured). ADR 0004 fits no drift, so a firm whose abnormal IV
    trends puts the same sign into all of its events. With a firm drift of sd 0.0015 per session, season-only
    clusters rejected 6.55/6.80% and two-way 4.38/4.25%.
- **Unbalanced seasons.** If the largest season cluster in a test's event set is more than **1.5×** the smallest, the
  two-way t is not used. The p-value comes from `rad_season_p` (§2f) instead.
  - With 3 of 7 seasons cut to 12 events, the two-way t rejected 9.1/9.0%, the one-way t 8.6/8.8% and `rad_season_p`
    5.2/5.7%.
  - The primary sample's seasons are balanced (49–52). The rule matters for subgroups and for samples with partial
    seasons.
- **No ramp p-value when the season dimension has $G < 5$.** The `mixed` sample is a single season, so it reports ramp
  estimates only.
- **Why not date clusters for ramps** (the reviewer's interim suggestion). Two RUNUP ramps whose day-0 dates are one
  to four weeks apart share most of their roughly 55 sessions. Day-0 clusters ignore that, and rejected 31.9–36.4%
  (§2g).
- **Why not KP-type adjustments as primary.** They need a model of $\operatorname{Corr}(A_i,A_j)$. For a ramp that
  model needs $R$, and every estimate of $R$ we tried left the statistic mis-sized (§2g).

**(c) Patell (1976)**, reported **for CRUSH only**:
$$
Z_P = \frac{\sum_i SA_i}{\sqrt{\sum_i \frac{d_i}{d_i-2}}},\qquad d_i = L_i - 1 .
$$

- **Distribution.** $SA_i \sim t_{d_i}$ under H0, with variance $d_i/(d_i-2)$. Here $L_i$ = the number of baseline
  changes, and one degree of freedom goes because $s_i$ is a sample standard deviation. The review confirmed
  $d/(d-2)$: 1.3999 against 1.4000 at L = 8 over 10⁷ draws.
- β is pooled over about 200 changes, so its own estimation error is ignored.
- **Weakness.** It assumes the event does **not** raise the variance. Event days obviously do, so Patell
  over-rejects. It is shown only because readers expect it.
- **Not for level measures.** Their variance input, $a^\top \hat R a$ with a truncated $\hat R$, is a model, so Patell
  is not reported for them.

**(d) BMP (1991): standardised cross-sectional test.** Robustness.
$$
t_{BMP} = \frac{\overline{SA}}{s_{SA}/\sqrt N},\qquad s_{SA}^2 = \tfrac{1}{N-1}\sum (SA_i-\overline{SA})^2 .
$$

**Its estimand** (revised after the review, ledger claim 7b). BMP tests
$H_0: \frac1N\sum_i E[A_i]/(s_i\sqrt{a_i^\top Ra_i}) = 0$, the mean of *standardised* effects. That is a mean
weighted by $1/s_i$, a precision-weighted mean.

- **Under the sharp null** (every event's effect is 0), a wrong $\hat s_i$ only re-weights events and costs efficiency,
  not size. That much of the first version was right.
- **Under heterogeneous effects** that move with $s_i$, the precision-weighted mean can differ from 0 while the
  equal-weighted mean is 0, and BMP then rejects a hypothesis we did not state.
  - The review measured 40% (crush-shaped effects, N = 350).
  - §2g measured 49.1% (RUNUP) and 35.4% (PERSIST_10).
- So BMP is not a test of "mean X = 0" as H1–H4 state it. It is reported, labelled "precision-weighted mean". The
  first version's sentences "A wrong ŝ costs efficiency, not size" and "the autocorrelation model cannot break BMP"
  are withdrawn.

**(e) The Kolari-Pynnönen family: robustness, citation-backed.**

*Prior art* (corrected after the review, ledger claim 9; Pynnönen 2022 read in full on 2026-10-28):

- **Kolari, Pape & Pynnönen (2018)**, SSRN 10.2139/ssrn.3167271, *Event study testing with cross-sectional correlation
  due to partially overlapping event windows*.
  - Their abstract says they "modify their test statistics to adjust for the average percentage of overlaps in event
    windows".
  - The full text was not reachable (SSRN returned 403), so their exact parametric statistic is known only through
    Pynnönen (2022).
- **Pynnönen (2022)**, *Non-Parametric Statistic for Testing Cumulative Abnormal Stock Returns*, J. Risk Financial
  Management 15(4):149, doi:10.3390/jrfm15040149 (CC BY 4.0).
  - Very likely its working-paper version: SSRN 10.2139/ssrn.3802405 (2021), *Nonparametric rank tests in event
    studies with partially overlapping event windows*. It has the same author and a nearly identical abstract
    (compared through Crossref), but the journal article does not cite it, so the link is inferred.
  - What the paper gives:
  - **Assumption 1 (eq. 1):** abnormal returns are serially uncorrelated and independent across firms on different
    calendar days.
  - **Overlap count:** $\tau_{ij}$ = the number of calendar days the two event windows share. Then
    $\operatorname{cov}(U_i, U_j) = \tau_{ij}\rho_{ij}$, and **eq. 25** gives the per-pair correlation of the two
    window sums: $(\tau_{ij}/\tau)\,\rho_{ij}$, times a rank-specific factor $(T-1)/(T-\tau)$.
  - **Eq. 26** assumes overlap and correlation are unrelated, so that $\sum\tau_{ij}\rho_{ij} = n(n-1)\bar\tau\bar\rho$,
    and gets an inflation factor $1+(n-1)\delta\bar\rho$.
  - **For standardised cumulative abnormal returns** (the text before eq. 40) the factor is $1+(n-1)\nu\bar\rho$ with
    $\nu = \bar\tau/\tau$. Pynnönen credits this result to Kolari et al. (2018).
  - **Eqs. 32–35** estimate $\bar\rho$ by clustering on calendar days:
    $\hat{\bar\rho} = \frac1M\sum_t\sum_{i\ne j} U_{it}U_{jt}$ with $M = \sum_t n_t(n_t-1)$, on standardised ranks
    $U$. **Eq. 27** is the Edgerton-Toops identity behind it. This ADR applies the same estimator to standardised
    changes $z_{i,t}$ instead of ranks. That is an adaptation, not the paper's own use.
  - **§2** names KPP's correction as the one for BMP when events cluster partially.
  - The paper does not clamp $\bar\rho$ at 0.
- **What that means for this ADR.** The first version's overlap weight is KPP's per-pair overlap fraction in
  different clothes. Here is how it compares:
  - $\omega_{ij} = a_i^\top a_j/\sqrt{a_i^\top Ra_i\,a_j^\top Ra_j}$ equals $\tau_{ij}/\tau$ exactly when the two
    windows are uniform, of equal length, and $R = I$.
  - Our changes were at most refinements: per-pair instead of averaged, non-uniform (ramp) weights, and own
    autocorrelation in the denominator.
  - The third refinement is the one that failed in practice (§2g).

Two statistics are reported, both on $t_{BMP}$, so both test the precision-weighted mean of (d):

- **`kpp_t`: KPP's average-overlap statistic, as published.** It replaces the deleted `kp_t`.
  $$
  t_{KPP} = t_{BMP}\sqrt{\frac{1-\bar\nu\hat{\bar\rho}}{1+(N-1)\bar\nu\hat{\bar\rho}}},\qquad
  \bar\nu = \frac{2}{N(N-1)}\sum_{i<j}\nu_{ij},\quad \nu_{ij} = \frac{a_i^\top a_j}{\sqrt{a_i^\top a_i\;a_j^\top a_j}},
  $$
  - $\nu_{ij} = \tau_{ij}/\tau$ for uniform windows. For a one-session measure it is $\mathbb 1[\text{same day 0}]$.
  - $\hat{\bar\rho}$ is Pynnönen's eq. 32 on the standardised clean baseline changes $z_{i,t}$, pooled by calendar date.
  - **No clamp**, as published.
  - The $(1-\bar\nu\hat{\bar\rho})$ numerator follows KP (2010)'s algebra for an estimated cross-sectional variance. We
    have not seen KPP's own parametric formula, so whether they keep that term is **unverified**. In design D1 of §2g
    (ρ = 0.1), $\bar\nu\hat{\bar\rho} \approx 0.0005$ for the crush, so the term moves $t$ by less than 0.1%.
  - **Reported for one-session measures only.** For ramps it rejected 9.2–15.5% under quote noise (§2g), because
    Assumption 1 rules out the negative autocorrelation that IV changes have. A row known to be that far off would
    only mislead, which is why the old `kp_t` was deleted.
- **`kp_ow_t`: the per-pair form, for one-session measures only.**
  $$
  t_{KP,ow} = t_{BMP}\sqrt{\frac{1-\bar r}{1+(N-1)\bar r}},\qquad
  \bar r = \max\!\Big(0,\; \frac{2}{N(N-1)}\sum_{i<j} \nu_{ij}\,\hat\rho_{ij}\Big),
  $$
  - It is the sum of Pynnönen's eq. 25 over pairs, before the averaging step of eq. 26.
  - $\hat\rho_{ij}$ is the Pearson correlation of $z_{i,t}$ and $z_{j,t}$ over their shared clean baseline dates, at
    least 20 of them. Events on the same day 0 share their whole baseline. If $\nu_{ij} > 0$ and fewer than 20 dates
    are shared, use the mean $\hat\rho$ of same-sector pairs, or of all pairs if there are none.
  - **Why per pair.** KPP's averaging assumes overlap and correlation are unrelated. But same-sector firms report on
    the same days (the banks open every season together), so pairs that overlap are the ones most correlated.
  - **Why the clamp at 0.** A negative $\bar r$ born of noise inflates $t$. In the N = 50 prototype at ρ = 0, the
    clamp mattered for the all-pairs r̄ (6.1–7.1% unclamped, 4.3% clamped). It mattered little for this per-pair form
    (5.1–5.5% unclamped, 4.7–5.3% clamped).
  - **Ramp form withdrawn.** For RUNUP and PERSIST the first version's ramp form, $\omega_{ij}$ with $\hat R$ in the
    denominator, is not reported (§2g: 0.9–1.5% with the demeaned $\hat R$, 5.0–6.7% with the uncentred one, 0–0.1%
    under mean reversion).

The KP (2010) derivation behind both rows still holds. Suppose $N$ variables have **common variance** and average
pairwise correlation $\bar r$. Then $\operatorname{Var}(\overline{SA}) = \sigma^2[1+(N-1)\bar r]/N$ and
$E[s^2_{SA}] = \sigma^2(1-\bar r)$, exactly.

- Pynnönen (2022) eq. 27 is the same identity.
- With unequal variances it is only approximate. In the review's example (event-induced variance with lognormal sd
  0.6) the true $t^2$ inflation was 5.44 against KP's 6.59 (ledger claim 7c). That is one more reason these rows are
  robustness, not primary.

**(f) Robustness rows for the ramps.**

- **`cluster_season_t`.** The one-way season-clustered CR1 t, kept so that the firm dimension's contribution is
  visible.
- **`rad_season_p`.** A wild cluster *restricted* bootstrap by season that enumerates **all $2^G$ Rademacher sign
  vectors** (128 at $G = 7$).
  - When seasons are independent and symmetric it is an exact randomisation test.
  - Its smallest attainable two-sided p is $2/2^G$ = 0.0156. So it can never pass Holm's first step at 0.05/7. With
    $m = 7$, Holm's step $k$ compares the $k$-th smallest p with $0.05/(8-k)$: 0.0071, 0.0083, 0.0100, 0.0125,
    **0.0167**, 0.025, 0.05. The floor first passes at the **fifth** step (0.0156 ≤ 0.05/3), which needs four
    other hypotheses rejected first. *Corrected after the delta review (1c):* this said "from the fourth step", but
    step 4's threshold is 0.05/4 = 0.0125 < 0.0156. Checked with statsmodels 0.15.0 `multipletests(method="holm")`:
    the floor is rejected only with four smaller p-values, where its Holm-adjusted p is 0.0469; with three it is
    0.0625.
    *Added 2026-10-29, after the milestone-3 review (F1):* all of this is for $G = 7$. At $G = 8$ the floor is
    $2/256$ = 0.0078, which passes at the **second** step (0.0078 ≤ 0.05/6 = 0.0083), so a G = 8 primary on its
    floor passes Holm after one other rejection. The verdict of a p on its floor is a function of G alone.
  - It is the p-value used when seasons are unbalanced (§2b).
  - It does not model the firm dimension.
  - Measured: 4.6/5.7% (D2), 5.2/5.7% unbalanced, 6.3/6.7% with firm drift of sd 0.0015.
- **Deleted after the second review: `wcr_season_p`**, the Webb six-point bootstrap. In every random-walk design it
  rejected more often than CR1 (D2 PERSIST_10: 6.45% against 5.95%), so it was never a safe fallback.
- **`sa_twoway_season_t`.** The standardised values $SA_i$ (BMP's estimand, the precision-weighted mean) with the
  same two-way season × firm clustering. It is how the report shows the precision-weighted answer for ramps without
  BMP's invalid variance.
  - Its one-way form held 4.5–6.1% in D0–D3 and rejected 11.2% in D5, correctly, because the precision-weighted mean
    there is not 0.
  - Its one-way form had more power than the equal-weighted primary: 93.8% against 82.4% at a 0.05 shift.
  - The two-way form is **not separately simulated**. That is an open item for gate G1.

**(g) Measured evidence.** Every prototype below is in `research/prototypes/`, runs from the repository root with
`uv run --no-sync --frozen python research/prototypes/<script>`, and has its output kept beside it.

*1. One-session, N = 50* (`kp_sim.py`, `kp_partial.py`, `kp_partial_clamp.py`; outputs `*.out.txt`). These scripts
were written before the review and re-run identically by it (ledger claim 7e). Their design:

- one-session measure only;
- N = 50 events, each with a 36-session baseline, iid N(0, 1) residuals plus a common daily factor (ρ on the same
  date, nothing across dates, $R = I$);
- "all on one date": 4,000 replications (seed 7). "15 / 40 candidate dates": 3,000 replications (seed 11), with
  about 14.5 / 28.7 occupied dates;
- normal critical value 1.96; MC standard error 0.40 pp at 3,000 replications and 0.34 pp at 4,000.

The column labels are corrected after the review. The old "published KP" column is KP (2010) with r̄ over all pairs,
which is the published procedure only when every event shares one date.

| design | ρ | plain BMP | KP 2010, r̄ over all pairs (deleted) | **per-pair overlap (`kp_ow_t`)** | date-clustered t |
|---|---|---|---|---|---|
| all on one date (4,000 reps) | 0 | 5.3% | 5.8% | n/a (same thing) | – |
| all on one date | 0.05 | 31.2% | 6.7% | n/a | – |
| all on one date | 0.15 | 53.5% | 5.9% | n/a | – |
| 15 candidate dates (3,000 reps) | 0 | 4.9% | 6.1% (clamped: 4.3%) | **5.1%** (clamped: **4.7%**) | 7.5% |
| 15 candidate dates | 0.10 | 8.5% | **0.0%** | **4.7%** | 6.9% |
| 15 candidate dates | 0.20 | 13.4% | **0.0%** | **5.3%** | 8.1% |
| 40 candidate dates | 0 | 5.5% | 7.1% (clamped: 4.3%) | **5.5%** (clamped: **5.3%**) | 5.9% |
| 40 candidate dates | 0.10 | 6.8% | **0.0%** | **5.3%** | 6.4% |
| 40 candidate dates | 0.20 | 8.4% | **0.0%** | **5.5%** | 6.8% |

At N = 50 with 15–29 uneven clusters the date-clustered t was liberal (5.9–8.1%, normal critical values). That is
the few-cluster problem, and it is gone at the real design below, which has 187 date clusters.

*2. The real daily design, every input estimated* (`h2h3_size_sim.py`, output `h2h3_size_sim.out.txt`, 2,000
replications per design, MC standard error 0.49 pp, written for this revision). This is the first size evidence for
any ramp statistic.

**The design.**

- Events: the day-0 dates of the 30 large caps in `data/derived/earnings_calendar_30_large_caps.json`, using the
  ADR 0002 rule.
- 20 synthetic firms each copy a random real firm's schedule and sector, with every day 0 jittered by up to ±3
  sessions.
- Day 0 falls in [2024-12-05, 2026-10-12]. That gives **N = 352** events on 187 distinct day-0 dates, in 71 ISO weeks
  and 7 season clusters of 49–52 events.
- Baselines are [−60, −22] minus same-firm zones, with a median of 30 sessions.
- Each replication estimates $s_i$, $\hat R$, $\hat\rho_{ij}$ and $\hat{\bar\rho}$ again.
- The identity $A_i = x_{target} - \bar x_{B_i}$ is asserted on the first replication of every design.

**The data-generating processes.** Each is an abnormal log-IV *level* = a latent level + quote noise. The latent
innovations load on a market-residual factor, a sector factor and an idiosyncratic part.

| | latent level | same-date ρ | quote noise (lag-1 acf of changes) | other |
|---|---|---|---|---|
| D0 | random walk | 0 | none | |
| D1 | random walk | 0.10 | none | Pynnönen's Assumption 1 holds exactly |
| D2 | random walk | 0.10 | ≈ −0.17 | |
| D3 | random walk | 0.10 | ≈ −0.28 | |
| D4 | AR(1), φ = 0.98 | 0.05 market + 0.15 within sector | ≈ −0.17 | firm sd lognormal (0.4); event-day jumps of 3 sd (event-induced variance) |
| D5 | as D4 | as D4 | as D4 | plus a level step $\mu_i \propto s_i - \bar s$ on [−21, +10], so the **equal-weighted** mean of RUNUP and PERSIST_10 is exactly 0 |
| D6 | AR(1), φ = 0.98 | 0.10 | none | |
| P1–P3 | as D4 | as D4 | as D4 | plus a common shift μ = 0.03 / 0.05 / 0.08 on RUNUP and PERSIST_10 |
| P4 | as D2 | as D2 | as D2 | plus μ = 0.03 |

Tables 1–3 below are the one-way and robustness statistics of this run. The two-way primaries are in table 4.

*Table 1. Ramps: size in %, RUNUP / PERSIST_10.* The exact binomial 99% band for 2,000 replications is [3.80, 6.30].

| statistic | D0 | D1 | D2 | D3 | D4 | D5 | D6 |
|---|---|---|---|---|---|---|---|
| `cluster_season_t` (one-way; was primary in the first draft) | 4.3 / 4.7 | 4.5 / 4.8 | 5.2 / 6.2 | 5.5 / 5.9 | 0.8 / 0.4 | 0.9 / 0.2 | 1.2 / 0.6 |
| Webb wild bootstrap by season, 999 draws (deleted) | 4.5 / 5.0 | 5.1 / 5.5 | 5.9 / 6.7 | 5.7 / 6.6 | 0.9 / 0.5 | 1.1 / 0.3 | 1.5 / 0.7 |
| standardised $SA_i$, one-way season (precision-weighted) | 4.5 / 4.7 | 5.0 / 5.2 | 5.3 / 5.9 | 5.5 / 6.1 | 0.8 / 0.3 | 11.2 / 5.1 † | 1.2 / 0.6 |
| date-clustered t (reviewer's interim) | 5.5 / 5.3 | 31.9 / 35.2 | 32.6 / 36.0 | 32.6 / 36.4 | 6.2 / 2.3 | 5.6 / 2.0 | 9.5 / 5.9 |
| ISO-week-clustered t | 5.6 / 5.3 | 24.1 / 27.1 | 23.5 / 27.2 | 24.7 / 28.2 | 4.0 / 1.6 | 3.4 / 1.0 | 5.2 / 3.1 |
| `kp_ow_t` ramp form, demeaned $\hat R$ (one reading of the milestone-0 text) | 4.7 / 4.5 | 1.1 / 0.9 | 1.1 / 1.1 | 1.5 / 1.3 | 0.0 / 0.0 | 0.4 / 0.0 | 0.0 / 0.0 |
| `kp_ow_t` ramp form, uncentred $\hat R$ | 5.1 / 4.9 | 5.5 / 5.0 | 6.4 / 6.0 | 6.7 / 6.6 | 0.1 / 0.0 | 4.2 / 0.1 | 0.0 / 0.0 |
| `kpp_t` (KPP average overlap) | 5.5 / 5.9 | 4.8 / 4.7 | 9.3 / 9.2 | 14.2 / 15.5 | 0.5 / 0.0 | 13.2 / 2.9 | 0.1 / 0.0 |
| BMP | 5.5 / 5.5 | 35.3 / 37.5 | 35.4 / 38.4 | 35.3 / 39.4 | 9.1 / 3.6 | 49.1 / 35.4 | 11.8 / 7.0 |
| CS-t | 5.3 / 5.4 | 35.4 / 37.9 | 36.4 / 38.7 | 36.0 / 40.6 | 7.8 / 3.1 | 6.7 / 2.4 | 12.0 / 8.0 |
| overlap covariance in raw units (rejected, see below) | 5.3 / 5.7 | 5.0 / 4.7 | 5.5 / 5.4 | 5.6 / 5.6 | 0.1 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 |
| calendar-time Driscoll-Kraay, 1 lag (rejected) | 5.2 / 4.8 | 4.8 / 4.7 | 4.7 / 4.8 | 5.2 / 5.7 | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 |

† Correct for its estimand: in D5 the precision-weighted mean is not 0.

*Table 2. Ramps: power in %, RUNUP / PERSIST_10.*

| statistic | P1: μ = 0.03 (D4) | P2: μ = 0.05 (D4) | P3: μ = 0.08 (D4) | P4: μ = 0.03 (D2) |
|---|---|---|---|---|
| `cluster_season_t` (one-way) | 34.6 / 23.9 | 82.4 / 65.8 | 99.7 / 98.1 | 26.8 / 20.3 |
| standardised $SA_i$, one-way season | 51.0 / 36.2 | 93.8 / 83.8 | 100 / 99.8 | 26.8 / 20.2 |
| overlap covariance, raw units | 30.6 / 8.8 | 92.2 / 72.3 | 100 / 100 | 34.4 / 23.4 |
| Driscoll-Kraay, 1 lag | 24.1 / 4.7 | 86.8 / 58.0 | 100 / 99.8 | 32.1 / 21.8 |

*Table 3. One-session (CRUSH): size in %.* The P designs leave CRUSH unchanged. There the one-way date t rejected 5.1,
4.8, 5.7 and 4.6%.

| statistic | D0 | D1 | D2 | D3 | D4 | D5 | D6 |
|---|---|---|---|---|---|---|---|
| `cluster_date_t` (one-way; was primary in the first draft) | 4.5 | 5.4 | 5.5 | 5.9 | 5.0 | 4.6 | 3.6 |
| `kp_ow_t` (per pair) | 4.8 | 4.8 | 5.1 | 5.5 | 4.3 | 4.0 | 3.2 |
| `kpp_t` | 4.8 | 4.7 | 5.1 | 5.7 | 4.3 | 4.2 | 3.4 |
| BMP | 4.8 | 7.4 | 6.7 | 6.3 | 5.2 | 5.4 | 4.7 |
| CS-t | 4.4 | 7.4 | 6.7 | 6.6 | 5.3 | 4.5 | 5.2 |

*3. The follow-up after the second review* (`h2h3_followup_sim.py`, output `h2h3_followup_sim.out.txt`, same event
design, 4,000 replications per design, MC standard error 0.34 pp, exact binomial 99% band [4.12, 5.90]).

- **Firm drift:** a linear trend in each firm's abnormal log IV, drawn N(0, sd) per firm.
- **Random firm effects:** a level step of N(0, sd) per firm from day 0 to +10. It shifts CRUSH and PERSIST_10 by the
  firm's draw.
- **Unbalanced:** 3 of the 7 seasons cut to 12 events (N = 239).

*Table 4. Ramps (RUNUP / PERSIST_10) and CRUSH: size and power in %.*

| design | one-way season | **two-way season × firm (primary)** | `rad_season_p` | Webb bootstrap (deleted) | CRUSH one-way date | **CRUSH two-way date × firm (primary)** |
|---|---|---|---|---|---|---|
| D2 | 5.10 / 5.95 | **5.08 / 6.05** | 4.58 / 5.65 | 5.62 / 6.45 | 4.88 | **4.75** |
| D2 + firm drift, sd 0.0005 | 5.33 / 5.65 | **5.10 / 5.53** | 5.33 / 5.05 | 5.97 / 6.12 | 5.73 | **5.80** |
| D2 + firm drift, sd 0.0015 | 6.55 / 6.80 | **4.38 / 4.25** | 6.30 / 6.65 | 7.05 / 7.55 | 5.85 | **5.80** |
| D2, unbalanced seasons | 8.62 / 8.80 (CR2 with Imbens-Kolesár df: 6.22 / 6.05) | 9.12 / 8.95 | **5.22 / 5.65** | 6.40 / 6.48 | 5.20 | **5.58** |
| D4 | 0.83 / 0.30 | **1.75 / 1.65** | 0.73 / 0.35 | 0.97 / 0.43 | 4.92 | **5.05** |
| D4 + firm drift, sd 0.0005 | 1.03 / 0.50 | **2.00 / 2.25** | 1.03 / 0.57 | 1.20 / 0.73 | 5.03 | **5.15** |
| D2 + random firm effects, sd 0.01 | 5.53 / 6.10 | **5.55 / 6.08** | 5.47 / 6.05 | 6.22 / 6.83 | 9.43 | **4.78** |
| D2 + random firm effects, sd 0.03 | 5.60 / 6.30 | **5.62 / 5.97** | 5.00 / 6.02 | 6.02 / 6.78 | 28.05 | **4.75** |
| D4 + random firm effects, sd 0.03 | 0.60 / 0.35 | **1.95 / 1.80** | 0.65 / 0.40 | 0.90 / 0.50 | 9.85 | **5.27** |
| P1 power: D4 + μ = 0.03 | 34.3 / 20.2 | **41.3 / 32.6** | 31.2 / 18.7 | 35.3 / 21.2 | (size) 5.30 | 5.45 |
| P2 power: D4 + μ = 0.05 | 82.6 / 66.8 | **86.2 / 76.2** | 78.8 / 62.6 | 83.0 / 67.8 | (size) 4.90 | 5.05 |
| P4 power: D2 + μ = 0.03 | 28.4 / 21.9 | **28.7 / 22.2** | 26.5 / 20.5 | 29.3 / 22.8 | (size) 4.25 | 4.15 |

The CR2 variance has a closed form for an intercept-only model: $\hat V = \sum_c S_c^2/(1-n_c/N)/N^2$. With balanced
clusters it equals CR1, so CR2 only matters for the unbalanced design.

What the numbers say:

- **The one-session primary (`twoway_date_t`) holds 4.75–5.80% in the nine size designs** (4.15–5.80% if the three
  power designs, where the crush is unshifted, are counted). That includes the firm-effect
  designs that break date-only clustering (9.4–28.1%).
- **The ramp primary (`twoway_season_t`) holds 4.25–6.08% under random-walk levels.**
  - The 6.05–6.08% for PERSIST_10 (D2, and D2 with firm effects of sd 0.01) is about one point liberal. It lies outside
    the 4,000-replication band and inside the 2,000-replication one. The cross-season overlap described in §2b is the
    likely cause. Gate G1 decides (§5).
- **Unbalanced seasons break both season clusterings.** Only the randomisation p-value holds (5.2/5.7%), hence the
  1.5× rule in §2b.
- **Under mean reversion (D4–D6) every ramp statistic that is right under random-walk levels becomes conservative.**
  Mean-reverting levels make cross-date covariances negative, and clusters and overlap models ignore them.
  - The two-way primary is the least conservative of them (1.65–2.25%).
  - It is also the most powerful equal-weighted statistic in D4: 86.2/76.2% at μ = 0.05, against 82.6/66.8% one-way.
- **The weakness is power, measured, not assumed.** With 7 seasons, the two-way primary detects μ = 0.05 log points
  86% of the time for RUNUP and 76% for PERSIST_10 (D4). Under random-walk levels it detects μ = 0.03 only 29% and
  22% of the time.
  - The mechanical run-up alone is larger. In the AAPL example of ADR 0003,
    $\ln(\sigma_{cm30}/\sigma_{d,\text{ann}}) \approx 0.08$.
  - A persistence effect of a few log points may not be detectable. That is an honest limit of 7 seasons of daily
    data.
- **What no design here covers:**
  - real baseline holes and missing sessions;
  - the coarse sample;
  - the sector-mean fallback;
  - cross-firm lagged correlation from stale quotes;
  - **persistent common changes.** The second review found the one-way season t at 5.8/6.4% when the residual common
    factor's *changes* follow an AR(0.9), and 16.4/17.3% at AR(0.98). Date-clustered CRUSH reached 6.9% at AR(0.5).

  Gate G1 adds them all.

**(h) Nonparametric**, for CRUSH and ΔSIGMA_D, where a one-session baseline analogue exists:

- *Generalised sign test* (Cowan 1992): $\hat p$ = the pooled share of baseline changes with $e_{i,t}<0$, and $w$ = the
  number of events with $A_i<0$.
  $Z_{GS} = (w - N\hat p)/\sqrt{N\hat p(1-\hat p)}$.
- *Rank test* (Corrado 1989, with the Corrado-Zivney standardisation for unequal $L_i$): $K_i$ = the rank of $e_{i,0}$ among
  its $L_i$ baseline values plus itself, and $U_i = K_i/(L_i+2) - \tfrac12$.
  $T_{rank} = \sum_i U_i \big/ \sqrt{\sum_i L_i/(12(L_i+2))}$, using the variance of a uniform rank.

Both assume independent events and are reported as robustness. The crush is so large that they will reject trivially.
They matter for ΔSIGMA_D, where heavy tails could drive a t-test. Pynnönen (2022) gives rank tests that are robust to
partial overlap. Adopting them is left open; see "Alternatives rejected".

### 3. Regressions: what drives the reaction

$$
Y_i = \alpha + \beta_1 z(|SURP_i|) + \beta_2 z(\ln\sigma_{d,i}(-1)) + \beta_3 z(SLOPE_i) + \beta_4 z(SIZE_i) + \gamma^\top \text{SECTOR}_i + \delta^\top\text{SEASON}_i + \varepsilon_i
$$

The variables:

| Variable | Definition | Source and notes |
|---|---|---|
| $Y$ (primary) | CRUSH: cm30, log, market-adjusted | ADR 0004 |
| $Y$ (decomposition) | ΔSIGMA_D | the only part of CRUSH that *can* respond to the news; the event-variance part is fixed at −1 |
| $\lvert SURP\rvert$ | $\lvert\text{reported}-\text{estimate}\rvert / P_{-1}$, winsorised at 1%/99% | `eps_history`; stored as `event_measures.abs_surprise_scaled_w` (it needs the day −1 option forward, so it is built in the `panel` layer). $P_{-1}$ = the parity spot on day −1 (`event_measures.price_ref`), which is as-of and unadjusted. **`eps_history` is not split-adjusted** (NVDA: 6.12 for the quarter ending 2024-04-30, then 0.68 after the 10:1 split), so the price must be the as-of price, and a split-adjusted Yahoo close would be wrong by the split factor. |
| robustness surprises | $SUE^{hist}$: the price-scaled surprise minus the mean of the firm's previous 8, over their sd (at least 4 required). Dispersion-scaled: $(\text{reported}-\text{consensus})/(\text{high}-\text{low})$ when count ≥ 3. The signed surprise. | price-scaling each quarter makes the history immune to splits. `eps_estimate` is weekly; use the last snapshot on or before day −1. |
| prior vol level | $\ln\sigma_{d,\text{ann}}(-1)$ (`sigma_d_m1`), the *ordinary* IV excluding the event | ADR 0003. Variant: $\ln\sigma_{cm30}(-1)$ as in the brief, **flagged as mechanically linked**, since a higher level with the same E means a smaller event share and so a smaller log crush. |
| $SLOPE$ | $\ln(\sigma_{T1}/\sigma_{T2})$ at −1 | proxies the event share $E/\sigma_d^2$. E and SLOPE are not both included (collinear). |
| $SIZE$ | ln market cap at −1 | `_yf`. Only coefficients are exported. |
| SECTOR, SEASON | GICS sector FE; calendar-quarter-of-day-0 FE | season FE absorb market-wide shocks per season. The *market-conditions* variant drops them for VIX-tercile dummies and interactions. Under the licensing rules (data-model §2.1) every dummy coefficient on a market-adjusted outcome counts as a fixed effect and is not exported. |

Regressors are z-scored so the coefficients are comparable ("one sd more surprise → β log points of crush"). Percent
surprise $(\text{rep}-\text{est})/\lvert\text{est}\rvert$ is rejected because it explodes near zero EPS.

**Standard errors.** Revised after the second review: firm becomes a clustering dimension for the primary, as in §2b.

- **Primary for one-session outcomes (CRUSH, ΔSIGMA_D): two-way firm × day-0 date** (Cameron, Gelbach & Miller
  2011), $\hat V = \hat V_{firm} + \hat V_{date} - \hat V_{firm\cap date}$, with $t_{\min(G)-1}$ critical values.
  - Events announced on the same day share that day's shock to $Y$. Events of the same firm share its persistent
    residual.
  - The firm residual matters most when a regressor is itself persistent within a firm (Petersen 2009), and
    $\ln\sigma_{d}(-1)$ is.
  - A firm has at most one event per date, so the intersection term is the event-level HC1 estimate.
  - With about 50 firms and about 150–190 dates, both dimensions have enough clusters.
  - The implementation checks that statsmodels' two-column `groups` gives the CGM formula on a hand-worked 4-event
    example. *Tightened after the delta review (N2):* the fit must pass **`use_t=True`**. statsmodels' cluster
    covariance defaults to `use_t=False`, which gives normal p-values and, for a Wald test, a χ² instead of an F.
    Measured in statsmodels 0.15.0: the default fit reports `use_t = False` with `df_resid_inference` already
    min(G) − 1, so checking the df attribute alone would not catch it. At G = 7, normal critical values rejected
    10.35 / 11.22% (delta ledger, design U4). The check therefore asserts:
    - `res.use_t is True` and `res.df_resid_inference == min(G_A, G_B) - 1`;
    - the reported p equals the two-sided $t_{\min(G)-1}$ tail of the reported t;
    - for H7's Wald test, that it is an F test with `df_denom == min(G_A, G_B) - 1`.

    Gate G1 repeats the last two on every reported row (§5).
  - *Was:* date-clustered primary, with two-way as robustness. The change rests on the intercept-only measurements of
    §2g, table 4, where date-only clustering rejected 9.4–28.1% under firm effects. For regressions it is the same
    mechanism, but **not separately simulated**.
- **Robustness: one-way date clusters.**
- **Multi-session $Y$ (run-up, persistence): two-way firm × season** (§2b), with $t_{G_{season}-1}$, and the 1.5×
  unbalanced-season rule of §2b.
  - *Revised after the review.* This said "cluster by ISO week of day 0, with a wild bootstrap by season as a stress
    test".
  - ISO-week clusters rejected 23.5–28.2% for ramp means at the real design (§2g), and the Webb bootstrap is
    deleted (§2f).
- Firm fixed effects (instead of sector) are a robustness check. SIZE then identifies only from within-firm variation.

**Implied vs realised** (milestone 4). Units fixed after the review (ledger claim 13); see ADR 0003 §c, "Units":

$$
r_{0,i}^2 = a + b\,\big(E_i + \sigma_{d,i}^2\big) + u_i,\qquad \sigma_{d,i}^2 = \frac{\texttt{sigma\_d\_m1}_i^{\,2}}{252}\ \text{(per session)},\qquad H_0: a=0,\; b=1 \quad(\text{Wald, two-way firm} \times \text{date}).
$$

- Both terms are in $w$ units, squared log returns.
- The stored `sigma_d_m1` is an annualised volatility. Adding its square to $E$ without the /252 would be wrong by a
  factor of 252 in the second term.
- The unit test computes the regressor for the ADR 0003 worked example: $0.00088284 + 0.2442^2/252 = 0.0011195$. It
  must fail if the /252 is dropped.

This uses every event, including those with E ≤ 0. Also reported: the share of events with
$\lvert r_0\rvert$ > `implied_abs_move_total`, compared with its **correct benchmark of 42.5%, not 50%**. If
$r\sim N(0,v)$, then $P(\lvert r\rvert > \sqrt{2/\pi}\sqrt v) = 2(1-\Phi(0.798)) = 0.425$. Fat-tailed jumps push the share
lower still, even when pricing is fair on average.

### 4. Multiple testing

**Primary family**, declared now before any data is seen and Holm-corrected at 5%. Each hypothesis has one primary
statistic. H1–H4 are about **equal-weighted** means (revised after the review, ledger claim 7b; see §2d):

| | Hypothesis | Primary statistic | Robustness rows (not in the correction) |
|---|---|---|---|
| H1 | equal-weighted mean CRUSH (cm30) = 0 | `twoway_date_t` | `cluster_date_t`, `kp_ow_t`, `kpp_t`, `bmp_t`, `patell_z`, `gen_sign_z`, `rank_t` |
| H2 | equal-weighted mean RUNUP = 0 | `twoway_season_t` | `cluster_season_t`, `rad_season_p`, `sa_twoway_season_t` |
| H3 | equal-weighted mean PERSIST_10 = 0 | `twoway_season_t` | `cluster_season_t`, `rad_season_p`, `sa_twoway_season_t` |
| H4 | equal-weighted mean ΔSIGMA_D = 0 | `twoway_date_t` | `cluster_date_t`, `kp_ow_t`, `kpp_t`, `bmp_t`, `gen_sign_z`, `rank_t` |
| H5 | $\beta_{\lvert SURP\rvert} = 0$ in the CRUSH regression | two-way firm × date t | date-clustered t |
| H6 | $\beta_{\text{prior vol}} = 0$ in the CRUSH regression | two-way firm × date t | date-clustered t |
| H7 | $a=0, b=1$ in the implied-vs-realised regression | two-way firm × date Wald | date-clustered Wald |

If a season cluster in the primary sample turns out more than 1.5× another (§2b), H2/H3 use `rad_season_p`. That p
cannot fall below 0.0156, so H2/H3 could then pass Holm only from the fifth step on (0.05/3), after four other
hypotheses have been rejected (§2f; corrected after the delta review, which found "fourth"). The report says so if it
happens.

> *Corrected 2026-10-29, after the milestone-3 review (F1).* "Only from the fifth step" is **false at G = 8**, and the
> real RUNUP set has 8 seasons (§2b). Its floor $2/2^8$ = 0.0078 passes Holm's second step, and H2 was rejected with
> p_holm 0.0469 (H1 the only smaller p). With the tail merged as §2b expected (G = 7, still unbalanced at 68 against
> 45) the floor is 0.0156 and p_holm would be 0.0938: not rejected. Every season sum has the same sign, so the p is on
> its floor and the verdict is a property of the cluster count. The report therefore prints the G = 7 counterfactual
> next to H2's Holm p everywhere it appears (`results` row `season_cut = 2026Q4_into_2026Q3`, README, milestone page
> §6.2, the `note` of H2's row in `tests.json`, the app's Results page); the direction of the run-up rests on the
> two-way t (13.4) and on all 8 season means being positive, not on the Holm verdict.

- **What changed for H1.** The milestone-0 primary was `kp_ow_t`. The review item asked about H2–H4, but H1 has the
  same estimand problem, so it moves too. The first draft of this revision moved it to a one-way date-clustered t.
  The second review led to two-way date × firm (§2b).
  - The crush is expected to have the same sign for nearly every event, so the choice should change no conclusion.
    That is an expectation, not a measurement. What the change guarantees is that the test and the reported estimate
    are the same quantity.
  - `kp_ow_t` stays as H1's first robustness row.
- **Robustness rows are not more hypotheses.** They are reported but do not enter the correction. Reporting all of
  them, rather than picking the best, is what protects against forking paths.
- **Rows dropped because they are known to be mis-sized** (§2g), so that no reader is misled:
  - the naive CS-t and BMP p-values for ramps;
  - `kpp_t` for ramps;
  - the ramp form of `kp_ow_t`.
  The estimates behind them (the equal-weighted and the precision-weighted means) are still shown.
  - *Added 2026-10-29, after the milestone-3 review (F6):* the same rule now applies to every robustness row that
    gate G1's calibrated design finds mis-sized, that is, rejecting more often than the upper edge of the exact
    binomial band (6.30% at 2,000 replications). Such a row keeps its estimate, se and statistic; its p-value and its
    confidence interval are set to null, and `tests.json` gives its G1 rejection rate (`g1_size`) and a note instead.
    At milestone 3 that is nine rows (numbers after the second fix round): for H1 the one-way date t (25.15%), BMP
    (27.55%), KP per pair (17.40%), KPP (17.55%), Patell (65.75%), the sign test (21.90%) and the rank test (39.45%);
    for H4 the sign test (5.68% on 10,000 replications, see below) and the rank test (13.65%). Code:
    `stats/results.py` `oversized()` and `withhold()`.
  - *Added 2026-10-29, second fix round (after the delta review, [ledger](../validation/m3-delta-ledger.md) claim 1
    and defect 3): which bar, and rows near it.* **A robustness row is withheld when its G1 rate is above the 99.5%
    binomial bar for the number of replications it was measured on** (`g1.binom_band`: 6.30% at 2,000, 5.57% at
    10,000). **Any robustness row within one percentage point of the 2,000-replication bar (5.30% to 7.30%) is
    re-measured on 10,000 fresh replications of the calibrated design and decided against 5.57%.** A rate measured on
    2,000 replications has a binomial sd of about 0.5 points near 6%, so a row within a point of the bar is decided
    by one block's luck otherwise: the delta review found H4's sign test at 6.45% (withheld) and BMP at 6.00% (kept)
    on 2,000, and 6.06% and 6.03% on 10,000. The run re-measures automatically (`g1.near_bar`, `g1.size_verdicts`,
    `stats/run.py` `run_g1`; constants `g1.REMEASURE_REPS`, `REMEASURE_MARGIN`, `REMEASURE_BLOCK`); the re-measured
    rates are the `results` rows `g1:calibrated_remeasured` (`n` = 10,000), and `tests.json` stores the count beside
    each withheld rate (`g1_reps`). At milestone 3, after the second fix round, three H4 rows were within a point:
    the one-way date t (5.35% on 2,000 → 4.98% on 10,000, kept), BMP (6.05% → 5.34%, kept) and the sign test
    (6.75% → 5.68%, withheld). The primaries are not affected: their gate is §5's.
    **Disclosure.** The first fix round's calibrated scale `sig0` (milestone page §9 F5) did not move the primaries
    (10,000 paired replications: H1 −0.08, H4 +0.08 points, both within 1.5 se) but lowered every H4 robustness rate by
    0.6–1.3 points (BMP 6.99 → 6.03%, sign 6.62 → 6.06%, rank 15.08 → 13.80% in the delta review's paired run), and
    moved H4's BMP from withheld (7.20%) to kept (6.00%) on the production seeds. The first fix round credited that
    move to the σ_d series alone.
- **Everything else is exploratory:** other rel_days, other IV measures, subgroups, every heatmap cell, the coarse and
  CBOE samples. These get Benjamini-Hochberg q-values within each exploratory family, and `tests.json` and the app
  label them so. Exploratory tests use the same primary statistic as their measure's hypothesis.

### 5. How the test code itself is validated

1. **Hand-worked oracles.** Each statistic is checked on four events, with every intermediate written in the test's
   comment: cluster sums, $G/(G-1)$, $t_{G-1}$, $\hat{\bar\rho}$, $\bar\nu$ and $\hat R$ from a 2-event baseline.
2. **A moment test for Patell's variance term** (added after the review, ledger N12).
   - The size band cannot catch "use $L_i$ instead of $L_i-1$": at L = 31 and N = 350 it moves size only to 5.03%.
   - So a separate test draws $10^6$ standardised values at L = 8. It requires $\lvert\overline{SA^2} - 1.4000\rvert <
     0.01$, where $d/(d-2)$ = 1.4000. The mutation gives 1.3333, and the probe's 10⁷ draws gave 1.3999.
3. **Per-statistic seeded Monte Carlo** (2,000 reps; rejection at 5% inside the **exact** binomial 99% band
   **[3.80%, 6.30%]**, the 0.5% and 99.5% quantiles of Binomial(2000, 0.05)/2000). *Corrected after the second
   review:* the milestone-0 band [3.74, 6.26] is the normal approximation. For $R$ replications, use the exact quantiles
   of Binomial($R$, 0.05); at 4,000 replications they are [4.12%, 5.90%].
   - Designs: iid normal changes; event-induced variance ×3; partial date clustering at ρ = 0.1.
   - The clustering design fits the statistic. One-session statistics get 15 or 40 candidate dates. Season-clustered
     statistics get 7 seasons of 15 candidate dates each, so that $G = 7$, with 50 firms that report once per
     season.
   - Each test covers the measures the statistic is reported for.
4. **Gate G1: the size gate for the primary statistics at the real design.** It must pass at milestone 3, before any
   H1–H4 p-value is reported. It rebuilds `research/prototypes/h2h3_size_sim.py` as a seeded test with three changes:
   - **Events:** the real event set after milestones 1–2. That means the actual day-0 dates, $N$, baselines with
     their real holes and missing sessions, and the merged season clusters.
   - **Estimators:** the package's own functions compute every input in every replication.
   - **Data-generating processes:** the **stress designs** are D0–D6 of §2g and the follow-up designs of table 4:
     firm drift, random firm effects, unbalanced seasons. Two more come from the second review:
     - **persistent common changes:** AR(0.5) and AR(0.9) in the residual common factor's changes;
     - **a cross-firm lag-1 correlation** of 0.02 and 0.05, for stale quotes.

     The **calibrated design** has every parameter estimated from the real pooled clean baselines:
     - same-date correlation within and across sectors;
     - the lag-1 autocorrelation of changes, and the lag-1 *cross-firm* correlation;
     - the autocorrelation of the cross-sectional mean of baseline changes at lags 1–10, which is how persistent
       common changes would show;
     - the AR coefficient of abnormal log-IV levels, from the baseline levels;
     - the spread of per-firm drift (the slope of each firm's baseline levels on time) and of per-firm mean crush;
     - the dispersion of $s_i$;
     - the day-0 variance ratio.

   **Pass criteria.**
   - The **calibrated design is binding**. Each primary statistic's size must be at most the upper exact binomial
     quantile for the replications used (6.30% at 2,000).
   - The stress designs are reported in full, and any rate above the band is explained in the report. They are not
     pass/fail: some of them deliberately exceed what the data show (ρ = 0.1, AR(0.98) changes).
   - Under mean reversion, conservatism is accepted and reported.
   - The calibrated design also reports, for H1–H4, the shift detectable with 80% power. That is not a pass/fail item.
   - **The reference-distribution check** (added after the delta review, N2). The size designs cover only the
     intercept-only H1–H4. So G1 also reads every `results` row whose statistic is a cluster-robust t or Wald,
     regressions included (H5–H7, the ramp regressions, robustness rows), and requires:
     - `df` = min(`n_clusters`, `n_clusters_firm`) − 1 for a two-way row, and `n_clusters` − 1 for a one-way row;
     - `p_value` equal, to 1e-10, to the two-sided $t_{df}$ tail of `stat`, or for a Wald row to the $F$ tail with
       `df` as the denominator degrees of freedom;
     - the confidence interval on the same reference: `(ci_hi − estimate)/se` equal to $t_{df,0.975}$ (delta-2
       review, claim 5; the default fit uses 1.960 here);
     - for a Wald row, its numerator degrees of freedom stored in `results` and used in the $F$ tail.

     The same checks run as a `results` invariant on every write, so milestone-4 rows (H5–H7) are covered too.

     A fit left at statsmodels' default `use_t=False` fails it, because its p-values come from the normal (or χ²)
     distribution. This is pass/fail. A failure is a code bug, fixed before any p-value is reported, not a reason
     to drop a hypothesis.

   **On failure** (revised after the second review, which showed that the first draft's fallback, the Webb
   bootstrap, rejected more often than the statistic it replaced):
   - A primary that fails the calibrated design **leaves the confirmatory family**. Its hypothesis is reported as
     exploratory, with its estimate, its p-value and the failed gate stated next to it. Holm then runs on the
     remaining hypotheses.
   - No substitute statistic is promoted after seeing the gate's result, because that would be a forking path.
   - For unbalanced seasons, the pre-declared rule of §2b (`rad_season_p`) applies whatever G1 says.
5. **Mutations to try at review, and what must catch each:**

   | Mutation | Caught by |
   |---|---|
   | day-0 clusters for a ramp | G1 (32–36%) |
   | one-way instead of two-way clusters | G1's firm-drift and firm-effect designs (6.6–6.8% for ramps, 9.4–28.1% for the crush) |
   | the intersection term of the two-way variance added instead of subtracted | the oracle |
   | normal instead of $t_{G-1}$ critical values, including statsmodels' default `use_t=False` | For H1–H4, G1's size designs at $G = 7$: 1.96 against 2.447, measured at 10.35 / 11.22% by the delta review (design U4; it was "not yet measured"). For every row, regressions included: G1's reference-distribution check, and the `use_t` assertion of the 4-event statsmodels check (§3). |
   | drop $G/(G-1)$ | the oracle |
   | no season merge | the oracle (cluster count) |
   | $L_i$ instead of $L_i-1$ | the moment test |
   | drop $(1-\bar r)$ | the oracle |
   | forget the clamp in `kp_ow_t` | the oracle, with a 4-event case whose r̄ is negative. The Monte Carlo cannot catch it: unclamped, the per-pair form rejected 5.1–5.5% at ρ = 0. |
   | demeaned $\hat R$ | the oracle |
   | one-session changes across a gap | the ramp-identity test of §1 |
   | /252 missing in H7's regressor | the H7 unit test |
   | a span walk that starts after $\min B_i$ | the ramp-identity test of §1 |
   | Rademacher draws sampled instead of fully enumerated | the oracle (it checks for exactly $2^G$ sign vectors) |

## Consequences

- Good: one framework, $A=\sum a e$, handles autocorrelation, unequal baselines, gaps, the coarse 2-session crush and
  partial clustering, and every piece of it can be tested.
- Good: the primary statistics are standard, citation-backed procedures. They need no model of the autocorrelation or
  of the cross-sectional correlation, and they test the same equal-weighted mean the report shows.
- Good: the overlap literature is cited for what it is. KPP (2018) and Pynnönen (2022) supply the robustness rows.
  Nothing in this ADR is described as new.
- Cost: **H2 and H3 rest on 7 season clusters.**
  - Power at a 0.05 shift is 86% (RUNUP) and 76% (PERSIST_10) under mean reversion (D4). Under random-walk levels a
    0.03 shift is detected only 22–29% of the time.
  - Under mean reversion the test is conservative (1.65–2.25% size).
  - PERSIST_10 runs about one point liberal under random-walk levels at ρ = 0.1.
  - A small persistence effect may go undetected. The report must say so when H3 is not rejected.
- Cost: the `mixed` sample has one season, so it reports ramp estimates without p-values.
- Cost: the primary family's estimand (equal-weighted) gives high-variance names more influence than BMP would. The
  precision-weighted answer is always shown beside it (`sa_twoway_season_t`, `kp_ow_t`).
- Cost: seven primary hypotheses with Holm means a nominal p of about 0.007 for the first to be rejected. With
  N ≈ 350 that is fine for the crush. It may be too strict for the driver hypotheses, and that would be an honest
  outcome.

## Alternatives rejected

| Alternative | Why rejected | What would make it win |
|---|---|---|
| BMP with the overlap-weighted KP adjustment as primary (the milestone-0 decision) | For ramps it needs $\hat R$, and it was mis-sized with every $\hat R$ we tried: 0.9–1.5% demeaned, 5.0–6.7% uncentred, 0–0.1% under mean reversion. Its estimand is the precision-weighted mean, not the stated one. | An estimator of $a^\top Ra$ for 60-session ramps that passes G1, *and* hypotheses restated as precision-weighted. |
| Date-clustered t for ramps (the reviewer's interim proposal) | 31.9–36.4% at ρ = 0.1: ramps overlap across day-0 dates. | Ramps shorter than the gap between report dates. |
| ISO-week clusters for ramps (the milestone-0 rule for multi-session regressions) | 23.5–28.2% at ρ = 0.1. | The same as above. |
| One-way season clusters for ramps (the first draft of this revision) | Misses firm-level dependence. It rejected 6.55 / 6.80% under firm drift of sd 0.0015, where two-way rejected 4.38 / 4.25%. It is also less powerful in D4 (82.6 / 66.8% against 86.2 / 76.2% at μ = 0.05). It stays as a robustness row. | No firm-level persistence in the calibrated G1 design (drift and firm-effect spreads near 0). |
| One-way date clusters for one-session measures (the first draft of this revision) | 9.4–28.1% under random firm effects on the crush, where two-way held 4.75%. It stays as a robustness row. | As above. |
| Webb wild cluster bootstrap by season as robustness or fallback (the first draft) | More liberal than CR1 in every random-walk design (D2 PERSIST_10: 6.45% against 5.95%). | Never as specified. |
| CR2 (Bell-McCaffrey) with Imbens-Kolesár degrees of freedom, season clusters | For an intercept-only model with balanced clusters it equals CR1 exactly. With unbalanced seasons it helped (6.22 / 6.05% against 8.62 / 8.80%) but did not reach the band, and it has no firm dimension. | A design with unbalanced seasons *and* no firm-level persistence. |
| KPP average-overlap (`kpp_t`) as primary for ramps | 9.2–15.5% under quote noise. Its Assumption 1 rules out the negative autocorrelation IV changes have. | Changes that are serially uncorrelated, which mid-quote IV changes are not. |
| Overlap covariance in raw units: $\hat V = s_A^2/N + \sum_{i\ne j}\hat\rho_{f(i)f(j)} s_i s_j\, a_i^\top a_j / (N(N-1))$, with firm-pair correlations pooled over all clean baselines | Needs no $\hat R$. It is right under random-walk levels (4.7–5.7%) and has more power there (P4: 34.4% against 26.8%). But it is 0–0.1% under mean reversion, it assumes event-season covariances equal baseline ones, and it is weaker at small shifts in D4 (P1: 30.6 / 8.8 against 34.6 / 23.9). | G1's calibrated design shows little mean reversion over 60 sessions (AR coefficient ≥ 0.995) and it passes G1. Then it buys 5–10 points of power. |
| Calendar-time Driscoll-Kraay (1998) on $c_t = \frac1N\sum_i a_{it}e_{it}$ | The same pattern: 4.7–5.7% under random walk, 0% under mean reversion, least power in D4. | As above. |
| Patell as primary | Not robust to event-induced variance, which earnings obviously cause. | Never for earnings. |
| Calendar-time portfolios (Jaffe 1974; Fama 1998) | Handle cross-correlation fully, but built for long-horizon returns. Applying them to persistent IV levels with 21-session windows needs its own design and is harder to explain. | Long-horizon persistence questions (months). |
| Pynnönen (2022) rank tests ($z_\tau$, $z_{\tau,grank}$) or GRANK (Kolari & Pynnönen 2011) as nonparametric robustness | Built for partial overlap, but under the same Assumption 1, and their simulated size for 11–21-day windows was 6.5–8.6% in that paper. Sign and rank cover the one-session measures. | A nonparametric result becomes decisive for a ramp measure. |
| Firm-clustered SE only | Ignores the dominant shock, the shared announcement date. | Never here; firm is the *second* dimension of the primary. |

## How we'll know it's wrong

- **Gate G1 fails** for a primary statistic in the calibrated design. Then its hypothesis leaves the confirmatory
  family (§5), and the report says so.
- **The calibrated G1 design shows little mean reversion** (an AR coefficient of abnormal log IV ≥ 0.995 over 60
  sessions). Season clustering then costs power for nothing. Re-evaluate the raw-units overlap covariance (rejected
  above) on G1.
- **Cross-firm lag-1 correlation of baseline changes above about 0.02, or a lag-1 autocorrelation of the
  cross-sectional mean change above about 0.3** (stale quotes or persistent common changes). Date clusters then miss
  adjacent-date dependence for the crush.
  - *Revised after the second review:* the trigger was 0.05. At that level of persistent common changes (AR(0.5),
    ρ = 0.1), the review measured 6.9% for the date-clustered crush.
  - The remedy is to cluster one-session measures by ISO week × firm (71 weeks in the prototype design) and re-run
    G1.
- **$\hat{\bar\rho}$ on real data is above about 0.2 for the crush.** That is far more correlation than market
  adjustment should leave. It suggests the VIX adjustment failed, or a common data error such as a stale snapshot
  shared by all symbols on a date.
- **The equal-weighted primary and a precision-weighted robustness row disagree in sign** for any of H1–H4. Then
  effects are heterogeneous and related to $s_i$. Report both and investigate the events that drive the difference.
- **Two-way SEs are no larger than one-way SEs in the calibrated design and on real data**, for every H1–H7 row. Then
  firm-level persistence is negligible and the one-way rows were enough. That changes no result, since two-way is
  not smaller in expectation, but it should be said.
- **A firm's events dominate a two-way cell.** With 7 events per firm, one firm with extreme drift can carry the firm
  term. List the firms with the largest firm-cluster scores next to H2/H3.

## References

- Patell, J. (1976), *Corporate forecasts of earnings per share and stock price behavior*, J. Accounting Research.
- Boehmer, E., Musumeci, J. & Poulsen, A. (1991), *Event-study methodology under conditions of event-induced variance*, J. Financial Economics 30: 253–272.
- Kolari, J. & Pynnönen, S. (2010), *Event study testing with cross-sectional correlation of abnormal returns*, Review of Financial Studies 23(11): 3996–4025, doi:10.1093/rfs/hhq072.
- Kolari, J., Pape, B. & Pynnönen, S. (2018), *Event study testing with cross-sectional correlation due to partially overlapping event windows*, SSRN working paper, doi:10.2139/ssrn.3167271. Abstract read; full text not reachable.
- Pynnönen, S. (2022), *Non-parametric statistic for testing cumulative abnormal stock returns*, J. Risk and Financial Management 15(4): 149, doi:10.3390/jrfm15040149 (CC BY 4.0). Read in full. Very likely the published version of *Nonparametric rank tests in event studies with partially overlapping event windows* (2021), doi:10.2139/ssrn.3802405 (same author, near-identical abstract; not cited by the article).
- Kolari, J. & Pynnönen, S. (2011), *Nonparametric rank tests for event studies*, J. Empirical Finance 18: 953–971.
- Harrington, S. & Shrider, D. (2007), *All events induce variance: analyzing abnormal returns when effects vary across firms*, J. Financial and Quantitative Analysis 42: 229–256 (as cited by Pynnönen 2022).
- Corrado, C. (1989), *A nonparametric test for abnormal security-price performance in event studies*, J. Financial Economics; Corrado, C. & Zivney, T. (1992), J. Financial and Quantitative Analysis.
- Cowan, A. (1992), *Nonparametric event study tests*, Review of Quantitative Finance and Accounting.
- Cameron, A. C., Gelbach, J. & Miller, D. (2008), *Bootstrap-based improvements for inference with clustered errors*, Review of Economics and Statistics 90(3): 414–427.
- Cameron, A. C., Gelbach, J. & Miller, D. (2011), *Robust inference with multiway clustering*, J. Business & Economic Statistics.
- Cameron, A. C. & Miller, D. (2015), *A practitioner's guide to cluster-robust inference*, J. Human Resources 50(2): 317–372.
- MacKinnon, J. & Webb, M. (2017), *Wild bootstrap inference for wildly different cluster sizes*, J. Applied Econometrics 32(2): 233–254.
- Webb, M. (2023), *Reworking wild bootstrap-based inference for clustered errors*, Canadian J. Economics 56(3): 839–858.
- Imbens, G. & Kolesár, M. (2016), *Robust standard errors in small samples: some practical advice*, Review of Economics and Statistics 98(4): 701–712.
- Driscoll, J. & Kraay, A. (1998), *Consistent covariance matrix estimation with spatially dependent panel data*, Review of Economics and Statistics 80(4): 549–560 (rejected alternative).
- Petersen, M. (2009), *Estimating standard errors in finance panel data sets: comparing approaches*, Review of Financial Studies 22(1): 435–480, doi:10.1093/rfs/hhn053.
- Bell, R. & McCaffrey, D. (2002), *Bias reduction in standard errors for linear regression with multi-stage samples*, Survey Methodology 28(2) (as cited by Imbens & Kolesár 2016; not read).
- Holm, S. (1979); Benjamini, Y. & Hochberg, Y. (1995).
