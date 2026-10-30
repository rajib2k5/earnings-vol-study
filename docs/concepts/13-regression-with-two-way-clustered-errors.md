# Regression with two-way clustered errors, and why its size can fail

Concept note for milestone 4. Written 2026-10-29. The decisions are [ADR 0005 §3 and §5](../adr/0005-statistical-test-suite.md);
the code is `src/earnings_vol/stats/regression.py`, `stats/drivers.py` and `stats/g1_drivers.py`; the tests are
`tests/test_regression.py`, `tests/test_drivers.py` and `tests/test_g1_drivers.py`.

## 1. The model

For event i, $y_i = x_i^\top b + u_i$, with N events and K columns in X: an intercept, the z-scored regressors, and
fixed-effect dummies. OLS gives $\hat b = (X^\top X)^{-1}X^\top y$ and residuals $\hat u = y - X\hat b$.

- **z-scores.** Each named regressor is $(v - \bar v)/s_v$ over the model's own events (sd with ddof 1). A
  coefficient then reads "one standard deviation more of the regressor goes with b log points more of the outcome",
  so |SURP| and ln σ_d can be compared.
- **Fixed effects** are dummy columns, one level dropped. A sector dummy is a per-sector mean of a market-adjusted
  outcome, so its coefficient is never exported (data model §2.1).
- **Why the crush is the outcome.** H5 and H6 ask what moves the size of the crush. The crush is negative (−0.199
  on average), so a positive coefficient means a *smaller* fall.

## 2. Clustered variance: the sandwich

With independent errors of any variance, $\hat V = (X^\top X)^{-1}\big(\sum_i x_i x_i^\top \hat u_i^2\big)(X^\top X)^{-1}$
(the "sandwich", HC0). When errors are correlated *within* groups (all events on one date, all events of one firm),
sum the scores $x_i\hat u_i$ inside each group first:

$$\hat V_g = c_g\,(X^\top X)^{-1}\Big[\sum_{c=1}^{G}\Big(\sum_{i\in c} x_i\hat u_i\Big)\Big(\sum_{i\in c} x_i\hat u_i\Big)^{\!\top}\Big](X^\top X)^{-1},
\qquad c_g = \frac{G}{G-1}\cdot\frac{N-1}{N-K}.$$

$c_g$ is the CR1 small-sample factor statsmodels uses. For an intercept-only model (K = 1) it is the milestone-3
`clustering.cr1_variance` of a mean.

**Two-way** (Cameron, Gelbach & Miller 2011): $\hat V = \hat V_{date} + \hat V_{firm} - \hat V_{date\,\cap\,firm}$.
A pair of events on the same date *and* of the same firm is counted in both one-way terms, so it is subtracted once.
Here no firm reports twice on one day, so the intersection term is the event-level HC1.

**Reference distribution.** t on $\min(G_{date}, G_{firm}) - 1$ degrees of freedom (49 with 50 firms), never the
normal; the CI is $\hat b \pm t_{df,0.975}\,se$. statsmodels' default `use_t=False` gives normal p-values; the
`results` invariant refuses such a row.

**Hand-worked** (in `test_two_way_covariance_hand_worked`): x = 0, 1, 2, 3; y = 1, 3, 3, 8; dates d1, d1, d2, d2;
firms f1, f2, f1, f2. Then b = 2.1, a = 0.6, residuals 0.4, 0.3, −1.8, 1.1, and
V = V_A + V_B − V_AB = [[0.6728, −0.3852], [−0.3852, 0.3618]], so se(b) = 0.6015 and t = 3.49 on 1 df.

## 3. The Wald test of several coefficients

H7 tests a = 0 and b = 1 together: with R = I and r = (0, 1),

$$F = \frac{(R\hat b - r)^\top (R\hat V R^\top)^{-1}(R\hat b - r)}{q} \sim F(q, \min(G)-1).$$

In the 4-event case F = 15.2862/2 = 7.643 on (2, 1). A χ² with q degrees of freedom is the large-G limit, and too
liberal with 50 clusters.

## 4. Why the size can fail: leverage

The sandwich estimates the variance from the residuals, and the residuals of high-leverage events are too small:
OLS pulls the fit toward them. With few clusters, or a regressor whose values are concentrated in a few clusters, the
variance is under-stated and the t is too large.

At this design, gate G1 measured it (milestone 4 page §6.1):

- |SURP| is skewed (2.46 after z-scoring) and persistent within a company. With y simply iid normal, its two-way t
  rejects 7.60% at 5%; firm clusters alone 7.30%, date clusters alone 5.95%. The company dimension is where the size
  goes.
- With the calibrated crush (heavy-tailed day-0 jumps, company effects, the real company scales) it rejects 9.55%
  (H5) and 8.10% (H6), above the 6.30% bar for 2,000 replications.

**What was not done, and why.** CR2 (Bell-McCaffrey) corrects the residuals for leverage, and Imbens-Kolesár degrees
of freedom shrink the reference with the design. A wild cluster bootstrap is another route. ADR 0005 §5 forbids
switching to any of them *after* the gate failed: that would be choosing a test after seeing how the first one
behaved on this data. So H5–H7 keep their declared statistics: they stay in Holm's family (ADR 0005 declared G1's
size designs for H1–H4 only; fix R1 after the milestone-4 review) with their G1 size printed beside them, and a
rejection by them would not be trusted. A better statistic would need its own ADR decision and its own gate, ideally
on a fresh sample. The same two-way t gives every exploratory regression p-value and q-value; G1 sized it only for
H5's and H6's coefficients (8.10% and 9.55%), not for the others, SLOPE's included.

## 5. Gate G1 for a regression

The simulated crush does not depend on the real regressors, so every true coefficient is 0. Regress it on the real
X, test, repeat 2,000 times: the share of rejections is the size. Two exact shortcuts:

- **Other coefficients do not matter.** Adding $X\gamma$ to y leaves the residuals unchanged, so the size of $b_1$'s
  test is the same whatever the true $b_2, b_3, \dots$ are.
- **Power for free.** Adding $\beta z_j$ to y moves $\hat b_j$ by exactly β and leaves the residuals: the t at β is
  $(\hat b_j + \beta)/se_j$ from the null replication.

## 6. Pitfalls

- A wrong reference distribution (normal, χ², max(G) − 1) — the invariant and the oracle catch it.
- The intersection term added instead of subtracted — the oracle.
- A small-sample factor without (N − 1)/(N − K) — the statsmodels comparison.
- Reading a regression p-value at face value when the gate says the test is oversized.
