# Cluster-robust inference, one-way and two-way

Concept note for milestone 3. Written 2026-10-29. The decision is [ADR 0005 §2b, §2f](../adr/0005-statistical-test-suite.md);
the code is `src/earnings_vol/stats/clustering.py`; the tests are `tests/test_clustering.py` (a hand-worked four-event
oracle, and statsmodels with `use_t=True` as an independent check).

## 1. The problem: events are not independent

The textbook t-test of a mean, $t = \bar A / (s_A/\sqrt N)$, assumes N independent values. Earnings events break that in
two ways:

- **through calendar dates.** Companies that report on the same day share that day's market news. A run-up spans about
  60 sessions, so it shares dates with every event of its *season*, not just those on its own day 0.
- **through companies.** A company's events share its persistent features: a drift in its IV, or a reaction that is
  always larger than average.

Positive correlation between the values makes $s_A^2/N$ too small, so the t-test rejects too often. ADR 0005's
simulations at the real design measured 35–41% false rejections for the run-up under a modest same-date correlation.

## 2. One-way cluster-robust variance (CR1)

Group the events into clusters $c$ that may be correlated inside but are independent across. With $u_i = A_i - \bar A$:

$$
\hat V_g = \frac{G}{G-1}\,\frac{1}{N^2}\sum_{c=1}^{G}\Big(\sum_{i\in c}u_i\Big)^2 .
$$

Squaring the cluster *sum* keeps every within-cluster cross product $u_iu_j$, whatever its sign: no model of the
correlation is needed. $G/(G-1)$ is the small-sample correction (it makes the estimator unbiased when the cluster sums
are iid). The reference distribution is $t_{G-1}$, not the normal: with 7 clusters the 5% critical value is 2.447, not
1.96, and using 1.96 rejected 10–11% (ADR 0005, delta review).

Worked (the test's oracle): A = 0.1, 0.3, −0.2, 0.6; mean 0.2; dates d1, d1, d2, d3. Date sums of $u$: 0, −0.4, 0.4,
so $\hat V = \tfrac32 \times 0.32/16 = 0.03$, t = 0.2/0.1732 = 1.155 on 2 df.

## 3. Two-way clustering (Cameron, Gelbach & Miller 2011)

When dependence runs along two dimensions (time A and company B), add the two one-way variances and subtract the part
counted twice, the variance clustered by their intersection:

$$\hat V = \hat V_A + \hat V_B - \hat V_{A\cap B},\qquad t \sim t_{\min(G_A,G_B)-1}.$$

The same four events with companies F1, F2, F1, F2: $\hat V_A = 0.03$, $\hat V_B = 0.0625$, $\hat V_{A\cap B} = 0.02833$,
so $\hat V = 0.06417$ and t = 0.790 on min(3, 2) − 1 = 1 df. If $\hat V \le 0$ (it can happen in small samples), use
$\max(\hat V_A, \hat V_B)$. statsmodels gives the same standard error with `cov_type="cluster"` and a two-column `groups`,
but its default `use_t=False` prints a normal p-value; the results invariant refuses such a row.

**Which dimensions** (ADR 0005 §2b):

| Measure | Time dimension | Why |
|---|---|---|
| CRUSH, ΔSIGMA_D (one session) | day-0 date | a one-session change shares only its own date's news |
| RUNUP, PERSIST (ramps over ~60 sessions) | **season** (calendar quarter of day 0) | a ramp overlaps every event of its season |

Company is always the second dimension. Seasons with fewer than 10 events join the neighbour with the nearest median day
0. Measured at milestone 3: the RUNUP set has 8 merged seasons, the smallest (2026Q4, 19 events) far below the largest
(50), so its p-value comes from §4.

## 4. Few or unbalanced clusters: the Rademacher enumeration

Seven or eight seasons are few. When the largest season has more than 1.5 times the events of the smallest, the
season-clustered t mis-sizes (9% in ADR 0005's simulation), and the primary p-value comes from **rad_season_p**:

1. Under H0 (mean 0), each season's sum $S_g$ could have come with either sign.
2. Enumerate **all** $2^G$ sign vectors $v$, compute the CR1 t of the season sums $v_gS_g$ for each.
3. p = the share of vectors with $|t^*| \ge |t|$.

It is exact when seasons are independent and symmetric. Its smallest value is $2/2^G$ (the observed signs and their
mirror): 0.0078 with G = 8. It does not model the company dimension: with a strong company drift it rejected 8.0% in
G1's stress design "D2 + drift 0.0015" (6.3–6.7% in ADR 0005's prototype). The calibrated design measured no company
drift, so the gate, which binds on the calibrated design, does not see that case.

Hand-worked (in the test): G = 3, one event per season, A = (3, 1, 1): t = 2.5; of the 8 sign vectors only (+,+,+) and
(−,−,−) reach |t*| = 2.5, so p = 2/8.

## 5. Why not date clusters for ramps, or KP-type corrections as primary

Date clusters treat two run-ups whose day 0s are a week apart as independent, although they share most of their 55
sessions: the smoke test in `tests/test_g1.py` shows the date-clustered row rejecting well above 5% where the two-way
season × company row does not (ADR 0005 measured 32–36% at the real design). KP-type corrections need a model of the
correlation of overlapping ramps, and every estimate tried left them mis-sized (concept note 11).
