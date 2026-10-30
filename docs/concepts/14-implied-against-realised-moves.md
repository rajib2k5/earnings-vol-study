# Implied against realised moves (H7)

Concept note for milestone 4. Written 2026-10-29. The decisions are [ADR 0005 §3](../adr/0005-statistical-test-suite.md)
("Implied vs realised") and [ADR 0003 §c "Units"](../adr/0003-iv-measures.md); the code is
`src/earnings_vol/stats/drivers.py` (`h7_inputs`, `h7_rows`, `exceed_rows`) and `stats/g1_drivers.py`; the tests are
`tests/test_drivers.py`, `tests/test_regression.py` and `tests/test_g1_drivers.py`.

## 1. What the options imply for the day-0 move

At day −1 the term structure gives E, the event variance, and σ_d, the ordinary volatility (ADR 0003 §c). Over the
one session from day −1 to day 0 the stock's log move r₀ has, if the options price it fairly,

$$E[r_0^2] = E + \sigma_d^2, \qquad \sigma_d^2 = \frac{\texttt{sigma\_d\_m1}^2}{252}\ \text{per session}.$$

**Units.** Both terms are squared log returns. The stored `sigma_d_m1` is an *annualised* volatility; adding its square
without the /252 would be wrong by 252× in that term. AAPL's worked example: 0.00088284 + 0.2442²/252 = **0.0011195**;
without the /252 it would be 0.0605. `test_h7_regressor_is_in_w_units` must fail if the /252 is dropped.

## 2. The regression

$$r_{0,i}^2 = a + b\,(E_i + \sigma_{d,i}^2) + u_i,\qquad H_0:\ a = 0,\ b = 1,$$

tested with the two-way (date × firm) Wald F on (2, min(G) − 1). Every event with an E is kept, including E ≤ 0
(four of 336): the regressor is still positive, and dropping them would select on the measure.

- **b < 1** means realised moves are smaller than implied (options are expensive on average); **b > 1** the opposite.
- **a ≠ 0** means a variance that does not scale with the implied one.

## 3. The 42.5% benchmark, not 50%

The stored "implied |move|" is the *expected absolute* move, $\sqrt{2/\pi}\sqrt v$ with v = E + σ_d². If r ~ N(0, v),

$$P\big(|r| > \sqrt{2/\pi}\sqrt v\big) = 2\big(1 - \Phi(0.798)\big) = 0.425.$$

So fair pricing of a normal move is exceeded 42.5% of the time. Fat tails push the share lower still (most moves
small, a few large), even when the variance is priced fairly. Comparing with 50% would call fair pricing expensive.

## 4. Why a regression of r² is fragile

r² of a normal move is a scaled χ² with one degree of freedom: skewed, with a variance of 2v². With a skewed regressor
too (here the implied variance has skewness 1.72, max/median 7.6), a few events carry the fit, and every sandwich
variance is too small at N = 336. Measured on the real design with moves that are exactly normal with variance x:
the two-way Wald rejects 11.80% at 5%, HC1 without clustering 11.22% (`research/prototypes/g1_regression_size.py`).
With the calibrated heavy tails (ν = 6.3) gate G1 measured 16.15%. So the test is liberal: H7 stays in the declared
Holm family with its real p-value (ADR 0005 §5, dated note of 2026-10-29), but a rejection by this test would not be
trusted. Its Holm p is 1.

## 5. What the data say

b = 0.767 (se 0.150; CI 0.465 to 1.069), a = 0.00083 (se 0.00080), Wald F(2, 49) = 1.33, p 0.275; the share beyond
the implied |move| is 0.401 (se 0.024) against 0.425. With E read at day −2, b = 0.922. Realised earnings-day
variance is about three quarters of what the options priced, but not measurably different from it with 336 events
and an oversized test. Milestone 4 page §6.4.

## 6. Pitfalls

- σ_d² without /252.
- 50% as the benchmark for the expected |move|.
- A χ² instead of an F for the Wald test with 50 clusters.
- Dropping E ≤ 0 events (selection on the regressor).
