# Holm's correction and the size gate G1

Concept note for milestone 3. Written 2026-10-29. The decisions are [ADR 0005 §4 and §5](../adr/0005-statistical-test-suite.md);
the code is `src/earnings_vol/stats/multiple.py` and `stats/g1.py`; the tests are `tests/test_multiple.py` and
`tests/test_g1.py`.

## 1. Seven hypotheses, one 5%

Test seven true null hypotheses at 5% each and the chance that at least one rejects by luck is up to
$1 - 0.95^7 = 30\%$. ADR 0005 declares a **primary family before seeing any data**: H1 CRUSH, H2 RUNUP, H3 PERSIST_10,
H4 ΔSIGMA_D (milestone 3), and H5–H7, the driver and implied-versus-realised regressions (milestone 4). Everything else
is exploratory and gets Benjamini-Hochberg q-values instead.

## 2. Holm (1979), step down

Sort the p-values, $p_{(1)} \le \dots \le p_{(m)}$. Reject $H_{(1)}$ if $p_{(1)} \le \alpha/m$, then $H_{(2)}$ if also
$p_{(2)} \le \alpha/(m-1)$, and so on; stop at the first failure. The adjusted p-value is

$$\tilde p_{(k)} = \max_{j\le k}\min\big(1, (m-j+1)\,p_{(j)}\big),$$

and $H_{(k)}$ is rejected exactly when $\tilde p_{(k)} \le \alpha$. Holm controls the family-wise error under any
dependence and is uniformly more powerful than Bonferroni.

Hand-worked (in the test): m = 7, p = 0.001, 0.004, 0.02, 0.03 and three untested: 0.007, 0.024, 0.1, 0.12, 1, 1, 1.

**Untested members at milestone 3.** H5–H7 have no p-value yet. They enter as p = 1. The adjusted p-value never
increases when another p-value decreases (each term $(m-j+1)p_{(j)}$ can only fall), so these p_holm values are **upper
bounds**: a rejection now stays a rejection whatever milestone 4 finds. Leaving them out (m = 4) would be invalid: it
would shrink the multiplier after seeing part of the family. `test_an_untested_hypothesis_at_one_is_an_upper_bound`
checks the bound on 200 random cases.

**A floor.** `rad_season_p` cannot fall below $2/2^G$. With G = 7 seasons that is 0.0156, which passes Holm only at the
fifth step (0.05/3 = 0.0167), after four other rejections. At milestone 3 the RUNUP set has G = 8, so the floor is
0.0078, which passes from the second step (0.05/6 = 0.0083). So when every season sum has the same sign, the Holm
verdict depends on G alone: H2 passes with p_holm 0.0469 at G = 8, and would fail with 0.0938 had the October 2026
tail been merged into July (G = 7), as ADR 0005 expected. The report prints both (milestone page §6.2 and §9 F1).

## 3. Why a size gate

Every rejection rate quoted in ADR 0005 came from simulations of a *prototype* design. Gate G1 re-measures the size of
each primary statistic at the **real** design, with the package's own code, before any H1–H4 p-value is read:

1. **The real event structure.** The 359 daily events behind H1–H4, their day-0 dates, companies, sectors, merged
   seasons, and baselines with their real holes and missing sessions (a simulated value is dropped wherever the real
   30-day IV is missing).
2. **Every input estimated.** Each replication simulates ln IV and ln VIX, then runs `panel/abnormal.py` (β, ALIV, e,
   s_i, R-hat, SA) and `stats/suite.py` (every statistic): the same code that makes the reported rows. H4 (ΔSIGMA_D)
   is simulated on a σ_d series of its own, with its own calibration; before the milestone-3 review it was the day-0
   change of the cm30 series, which gated the crush process instead of ΔSIGMA_D.
3. **A calibrated null design**, every parameter estimated from the real pooled clean baselines: quote noise from
   $\hat\rho_1$; the same-date correlation within and across sectors; the cross-company lag-1 correlation (negative on
   the real data, so the design gets a *common* quote-noise share rather than stale quotes); the AR coefficient of the
   levels (corrected for noise and for the short-window bias); company drift and company crush dispersion; the spread
   and the scale of $s_i$; the day-0 variance ratio. Not every moment comes back: simulated panels reproduce the
   correlations, the company dispersion and the day-0 ratio, but their AR of levels reads higher than the data's
   (0.998 against 0.985), so the design mean-reverts less than the data, the stricter side for the ramps.
4. **Stress designs** that deliberately go further than the data (random-walk levels, ρ = 0.1, persistent common
   changes, firm drift, unbalanced seasons). They are reported, not pass/fail.

**The pass rule.** At 2,000 replications a correct 5% test rejects between 76 and 126 times in 99% of runs (the exact
binomial quantiles), so the calibrated rate must be at most 126/2000 = 6.30%. A primary that fails leaves the
confirmatory family and is reported as exploratory with its failed gate beside it; no substitute statistic is promoted
afterwards, because choosing a test after seeing how tests behave on the data is a forking path.

**The bar depends on the replications.** The 99.5% quantile of Binomial(R, 0.05)/R shrinks as R grows: 6.30% at
2,000, 5.57% at 10,000 (557 rejections; the normal approximation 0.05 + 2.576·√(0.0475/10,000) = 5.56% rounds up to
the next count). A rate measured on 10,000 replications is judged against 5.57%, never against 2,000's 6.30%. The
robustness rows use the same rule (ADR 0005 §4): a row is withheld when its rate is above the bar for its own
replications, and a row within one point of 6.30% on 2,000 (where one block's luck decides it, binomial sd ≈ 0.5
points) is re-measured on 10,000 first.

**The reference-distribution check.** The size designs cover the intercept-only H1–H4. Every stored row whose statistic
is a t is also checked, on every write, against its own reference: df from the cluster counts, the p-value from the t
tail, the CI half-width from $t_{df,0.975}$ (`src/earnings_vol/invariants.py`). A fit left at statsmodels' default
`use_t=False` fails it.

## 4. Power

The calibrated design is also run with a common shift of 0.01–0.08 log points: on day 0 for the one-session measures, on
[−21, +10] for the ramps. The shift detectable with 80% power is interpolated from that curve (milestone page, §6).
A test that cannot see a 3-log-point persistence effect is an honest limit of seven seasons of daily data, and the
report must say so when H3 is not rejected.
