# Total variance, event variance and the implied move

Concept note for milestone 2. Written 2026-10-29. The decision is [ADR 0003 §c](../adr/0003-iv-measures.md); the
code is `src/earnings_vol/measures/termstructure.py` (`event_variance`, `implied_moves`) and `event_iv.py`; the tests
are `tests/test_termstructure.py` and `tests/test_iv_worked_example.py`.

## 1. Variances add, volatilities do not

Over independent stretches of time, variances of log returns add. So the **total variance** to an expiry,
$w = \sigma^2 T$, is the natural quantity to split: ordinary days contribute a little each, and an earnings day
contributes one extra lump. Volatilities (square roots) do not add, which is why every formula here works in w and
takes a square root only at the end.

## 2. The two-component model

At session t, for an expiry j with $\tau_j$ sessions to go,

$$
w_j = \sigma_d^2\,\tau_j + E \cdot \mathbb 1[\text{expiry } j \text{ spans the event}],
$$

with $\sigma_d^2$ the ordinary ("diffusive") variance **per session** and E the extra variance of the event-day jump.
An expiry **spans** the event when it settles on or after day 0: an expiry that settles at day 0's close already holds
the news. One edge case is classed spanning too, conservatively: an expiry on the day of an after-close (AMC) release,
because its holders decide whether to exercise until 5:30 p.m. ET, after the news (ADR 0003 §b, revised after the
milestone-2 review).

## 3. Two spanning expiries identify E

With $\tau_1 < \tau_2$, both spanning:

$$
\sigma_d^2 = \frac{w_2 - w_1}{\tau_2 - \tau_1},\qquad E = w_1 - \sigma_d^2\,\tau_1 = \frac{w_1\tau_2 - w_2\tau_1}{\tau_2 - \tau_1}.
$$

The difference of the two removes E (both contain it once), which gives the per-session variance; then E is what is
left of $w_1$. The worked example (AAPL, day −1 = 2025-10-30): $w_1 = 0.0034863$ at 11 sessions, $w_2 = 0.0056163$ at
20, so $\sigma_d^2 = 0.0021300/9 = 2.3667\times10^{-4}$ and $E = 0.0034863 - 11 \times 2.3667\times10^{-4} = 0.00088284$.

**The clock matters.** With calendar days (15 and 29) instead of sessions the same prices give E = 0.00120404, 36%
more. Only the ratio $\tau_2/\tau_1$ enters, and calendar days count a weekend as 3 days (ADR 0003 §c).

## 4. From E to moves

| Quantity | Formula | AAPL example | Meaning |
|---|---|---|---|
| implied move | $\sqrt E$ | 2.971% | standard deviation of the event jump |
| implied absolute move | $\sqrt{2/\pi}\,\sqrt E$ | 2.371% | expected \|jump\| if the jump is normal |
| implied absolute move, total | $\sqrt{2/\pi}\,\sqrt{E + \sigma_d^2}$ | 2.670% | expected \|day-0 return\|: one ordinary session plus the news |

$\sqrt{2/\pi} = 0.7979$ is $E|Z|$ for a standard normal Z. $\sigma_d^2$ is per session here (the stored `sigma_d_iv` is
annualised, so the per-session variance is $\texttt{sigma\_d\_iv}^2/252$).

## 5. When E ≤ 0

E ≤ 0 happens exactly when the shorter expiry's IV is not above the longer one's (no inverted term structure). Quote
noise around a small event, an upward-sloping ordinary term structure, or a wrong date can do it. The rule:

- **E is stored signed.** There is no implied move (`implied_move_status = nonpositive_event_variance`).
- **Averages are taken in variance space**: a group's implied move is $\sqrt{\overline{E}}$ over all its events,
  E signed. Averaging $\sqrt E$ over the E > 0 events only would be selection; flooring E at 0 would also push it up.
  The app's IV page prints this $\sqrt{\overline E}$ next to the histogram of the E > 0 events.

Measured at milestone 2: 4 of the 347 primary (daily) events have E ≤ 0 on day −1 (1.15%); in the Mon/Wed/Fri sample
33 of 712 (4.6%).

## 6. Why not the straddle's "implied move"?

Trading platforms quote the at-the-money straddle over the front expiry's whole life, about
$\sqrt{2/\pi}\sqrt{w_1}$: 4.71% in the example, against an event-only 2.37%. Three quarters of $w_1$ is ordinary
diffusion over the 11 sessions. E separates the event from the diffusion; the straddle does not.

## 7. What to remember

- Work in total variance w; variances add.
- Two spanning expiries give $\sigma_d^2$ from their difference and E from what is left.
- Sessions, not calendar days, for τ.
- E ≤ 0 is kept signed and averaged in variance space; it is never dropped or floored.
