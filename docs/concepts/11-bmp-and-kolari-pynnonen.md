# Standardised tests: BMP and the Kolari-Pynnönen family

Concept note for milestone 3. Written 2026-10-29. The decision is [ADR 0005 §1, §2c–§2e, §2h](../adr/0005-statistical-test-suite.md);
the code is `src/earnings_vol/stats/eventtests.py` and the R-hat functions of `panel/abnormal.py`; the tests are
`tests/test_eventtests.py`.

## 1. Standardising each event

Companies differ in how noisy their IV is. The classic event-study fix divides each event's value by its own baseline
scale before averaging:

$$SA_i = \frac{A_i}{s_i\sqrt{a_i^\top \hat R\, a_i}}$$

- $s_i$: the sd (ddof 1) of the event's clean baseline abnormal changes.
- $a_i^\top \hat R a_i$: the variance of a weighted sum of changes, in units of $s_i^2$, when changes are autocorrelated.
  For a one-session crush $a = (1)$ and the term is 1. For a ramp (run-up, persistence) it is the sum over the ramp's
  weights with the autocorrelations $\hat\rho_k$ (concept note 9, §5).

$\hat R$ is pooled over the test's event set: $\hat\rho_k = \sum z_t z_{t-k}/\sum z_t^2$ over pairs of clean changes of the
same event $k$ sessions apart, **uncentred** (the model has no drift; demeaning each 30-change baseline biases every
$\hat\rho_k$ by about $-1/30$). Measured on the primary sample: $\hat\rho_1 = -0.254$, the quote-noise signature
(the mid-quote IV has noise, and noise in a level is an MA(1) with a negative first autocorrelation in its changes).

**PSD check.** A Toeplitz $\hat R$ is a valid correlation matrix if its spectral density
$1 + 2\sum_k\hat\rho_k\cos k\lambda$ is non-negative. If not, taper by $(1-k/11)$ and check again; still negative, use
$\hat R = I$ and flag it. The real $\hat R$ passed untapered.

## 2. BMP (Boehmer, Musumeci & Poulsen 1991)

$$t_{BMP} = \frac{\overline{SA}}{s_{SA}/\sqrt N} \sim t_{N-1}.$$

It is robust to event-induced variance because the variance comes from the event values themselves. But it tests a
**different hypothesis**: that the mean of the *standardised* effects is 0, a mean weighted by $1/s_i$. If calm
companies react differently from noisy ones, BMP can reject while the equal-weighted mean is exactly 0 (ADR 0005
measured 49%). So BMP rows are labelled `precision_weighted` and are robustness only. The primary rows test the
equal-weighted mean the report shows.

## 3. Correlated events: Kolari & Pynnönen (2010) and Kolari, Pape & Pynnönen (2018)

If N standardised values have common variance and average pairwise correlation $\bar r$, then
$\operatorname{Var}(\overline{SA}) = \sigma^2[1+(N-1)\bar r]/N$ while $E[s^2_{SA}] = \sigma^2(1-\bar r)$, so

$$t_{KP} = t_{BMP}\sqrt{\frac{1-\bar r}{1+(N-1)\bar r}}.$$

With N = 350, an $\bar r$ of 0.01 already shrinks t by a factor of 2.1. Two versions are reported, one-session measures
only:

- **`kpp_t`** (KPP 2018, average overlap): $\bar r = \bar\nu\,\hat{\bar\rho}$. $\bar\nu$ is the mean overlap of two
  events' windows, $a_i^\top a_j/\sqrt{a_i^\top a_i\,a_j^\top a_j}$: for a one-session crush, 1 if the two share a day 0,
  else 0. $\hat{\bar\rho}$ is Pynnönen (2022)'s eq. 32 on the standardised baseline changes, clustered by calendar date:
  $\sum_t\sum_{i\ne j} z_{it}z_{jt}/\sum_t n_t(n_t-1)$. Not clamped, as published.
- **`kp_ow_t`** (the per-pair form, Pynnönen 2022 eq. 25): $\bar r = \max(0, \text{mean over pairs of } \nu_{ij}\hat\rho_{ij})$,
  with $\hat\rho_{ij}$ the Pearson correlation of the two events' baseline changes over their shared dates (at least 20;
  else the mean of same-sector pairs). The clamp stops a negative $\bar r$ born of noise from inflating t.

Hand-worked (in the test): z on two dates, (1, 1, −1) and (2, 2): $\hat{\bar\rho} = (-2 + 8)/(6 + 2) = 0.75$.

**Not for ramps.** For a 60-session ramp the correlation model needs $R$, and it rejected 9–16% under quote noise
(ADR 0005 §2g). Rows known to be mis-sized are not reported: no BMP, KP or KPP rows for RUNUP or PERSIST. The ramps'
precision-weighted answer is `sa_twoway_season_t`: the $SA_i$ with the same two-way season × company clustering as the
primary.

## 4. Patell, the sign test and the rank test

- **Patell (1976)**, CRUSH only: $Z = \sum SA_i / \sqrt{\sum d_i/(d_i-2)}$, $d_i = L_i - 1$. $SA_i$ is t-distributed
  with $d_i$ degrees of freedom, variance $d/(d-2)$: 1.4 at L = 8. The moment test draws 10⁶ values and checks 1.40,
  which the mutation "L instead of L − 1" (1.333) fails. Patell assumes the event does not raise the variance, which
  earnings obviously do, so it over-rejects and is shown only because readers expect it.
- **Generalised sign test (Cowan 1992)**: the number of events below 0 against the baseline's share below 0.
- **Rank test (Corrado 1989, Corrado & Zivney 1992)**: the event's rank among its own baseline changes.

All three assume independent events and are robustness. The crush is so large that they reject trivially; they matter
for ΔSIGMA_D, where heavy tails could drive a t-test.

**Measured at milestone 3, after both review rounds.** On gate G1's calibrated null design the crush's one-session
robustness rows reject far more than 5%: one-way date t 25.15%, BMP 27.55%, KP 17.40%, KPP 17.55%, Patell 65.75%, sign
21.90%, rank 39.45% (company effects and heavy-tailed day-0 changes, which only the two-way primary handles). For
ΔSIGMA_D, on its own σ_d series, only the rank test (13.65% on 2,000 replications) and the sign test (6.75% on 2,000,
re-measured at 5.68% on 10,000) are above the bar for the replications they were measured on (6.30% at 2,000, 5.57%
at 10,000); BMP (6.05% → 5.34%) and the one-way t (5.35% → 4.98%) were near the bar and kept their p-values on the
10,000 re-measure. Following ADR 0005 §4, the oversized rows keep their estimates and lose their p-values (milestone
page §6.3).
