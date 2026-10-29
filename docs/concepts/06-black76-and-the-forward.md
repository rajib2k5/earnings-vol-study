# Black-76 on the parity forward, and the ATM total variance

Concept note for milestone 2. Written 2026-10-29. The decision is [ADR 0003 §0](../adr/0003-iv-measures.md); the
code is `src/earnings_vol/measures/black.py`, `forward.py` and `chain.py`; the tests are `tests/test_iv_atom.py` and
`tests/test_iv_worked_example.py`.

## 1. The problem

The option data has bids and asks, but no stock price, no dividends and no time stamp. The vendor's own `vol` column
has undocumented inputs, and its call and put IVs disagree at the same strike. We want one number per expiry that says
how much variance the market prices until that expiry, computed from the quotes alone.

## 2. The forward replaces the spot

Put-call parity (European options, same strike K and expiry) says

$$
C - P = DF\,(F - K) \quad\Longrightarrow\quad F_K = K + \frac{C - P}{DF}.
$$

Every strike quoted on both sides gives an estimate $F_K$ of the forward F. The code keeps the 4 strikes with the
smallest $|C - P|$ (both legs near the money, little early-exercise premium, tight spreads; an exact tie, counted in
whole cents, goes to the lower strike) and takes the median. The
forward already nets out dividends and is read at the same instant as the options, which is why no spot price is
needed (concept note 04 uses the same forward for the snapshot time).

The discount factor runs on the **calendar** clock, $DF = e^{-r\,\text{days}/365}$, with r the FRED 3-month bill rate:
interest accrues every day.

## 3. Black-76 prices on the forward

$$
d_1 = \frac{\ln(F/K) + w/2}{\sqrt w},\quad d_2 = d_1 - \sqrt w,\qquad
C = DF\,[F\,N(d_1) - K\,N(d_2)],\quad P = DF\,[K\,N(-d_2) - F\,N(-d_1)].
$$

Here $w = \sigma^2 T$ is the **total variance** to expiry. The price depends on σ and T only through w. So the price
pins down w, and no day count enters the variance yet. The clock appears only when w is turned into an annualised IV.

Worked by hand (`tests/test_iv_atom.py`): F = K = 100, w = 0.04, DF = 1 gives $d_1 = 0.1$, $d_2 = -0.1$ and
$C = 100\,(2N(0.1) - 1) = 7.965567$. A bug that writes $+w$ instead of $+w/2$ in $d_1$ gives 7.926, and the test fails.

## 4. From a price to w: Brent's method, and when there is no root

Each price increases with w, so $\text{mid} = \text{Black76}(w)$ has exactly one root on $[10^{-8}, 4]$ when the mid lies
strictly between the prices at the two ends. Brent's method finds it. A mid outside that range has **no root**; the
strike is dropped and flagged `iv_no_root`. It is never solved on a wider interval and never clipped to 4. At K = F
and DF = 1 the price at w = 4 is $100\,(2N(1) - 1) = 68.27$, so a call quoted at 70 has no root although it is below the
no-arbitrage bound of 100.

## 5. Which quote: the out-of-the-money side, at the mid

At each strike the code uses the put when $K < F$ and the call when $K \ge F$. The in-the-money leg carries the
early-exercise premium of an American option and a wider spread. In the test chain the in-the-money put at 103 carries
a made-up premium of 0.10; taking the in-the-money legs instead moves the ATM w from 0.0044376 to 0.004585 (the
mutation check of `tests/test_iv_atom.py`). The mid, not the bid, is the
price: a wider spread around the same mids leaves w unchanged.

## 6. ATM: interpolate in log-moneyness

With $k = \ln(K/F)$, take the nearest valid strikes with $k_{lo} \le 0 < k_{hi}$ and interpolate linearly:

$$
w_{atm} = w_{lo} + \frac{0 - k_{lo}}{k_{hi} - k_{lo}}\,(w_{hi} - w_{lo}).
$$

The strike grid is sparse and changes daily (AAPL had no 270 strike on 2025-10-30), so "the nearest strike" would jump
around; interpolating at k = 0 does not. If the two strikes are more than 1.5 standard deviations ($1.5\sqrt{w}$) apart,
a quadratic in k is fitted instead, weighted by 1/(relative spread), through the valid strikes within $2\sqrt{w}$ (at
least 4, and at least one on each side of k = 0). With no valid strike on one side of the money there is no ATM: the
fit would extrapolate, and on real chains a one-sided fit missed the known ATM IV by more than 1.5 vol points about one
time in twenty (ADR 0003 §0 step 4, revised after the milestone-2 review).

Worked (`test_atom_hand_worked_bracket`): bracket 98 / 103 around F = 100, $k_{lo} = -0.0202027$,
$k_{hi} = 0.0295588$, so the weight is 0.4059906 and $w_{atm} = 0.0046 - 0.4059906 \times 0.0004 = 0.0044376$.

## 7. The clock: sessions, then annualise

The time to expiry τ counts **NYSE sessions** in (snapshot, expiry]: the expiry counts, the snapshot does not.
The reported IV is $\sqrt{252\,w/\tau}$. From Thursday 2025-10-30 to Friday 2025-11-28 that is 20 sessions (Thanksgiving
is closed), against 29 calendar days. Why sessions: variance arrives while the market trades (concept note 07, and
ADR 0003 §c "The clock matters").

## 8. What to remember

- The forward from put-call parity replaces the spot, the dividends and the time stamp.
- Black-76 gives the **total variance** w; the price fixes it with no day count.
- Out-of-the-money side, at the mid; ATM by interpolation in log-moneyness.
- Interest on the calendar clock (DF), variance on the session clock (τ).
