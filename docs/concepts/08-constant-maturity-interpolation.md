# Constant-maturity IV, and why it must not cross the event

Concept note for milestone 2. Written 2026-10-29. The decision is [ADR 0003 §b](../adr/0003-iv-measures.md); the code
is `src/earnings_vol/measures/termstructure.py` (`interpolate`, `_cm30`, `_blind`); the tests are
`tests/test_termstructure.py`.

## 1. Why a constant maturity

The vendor lists 3 or 4 expiries per day, 7 to 42 sessions out, and the set changes from one day to the next. The IV
of "the front expiry" therefore jumps when the front rolls. A **constant-maturity** IV reads the term structure at a
fixed horizon every day: 21 sessions (about 30 calendar days) here, the horizon of VIX.

## 2. Interpolate in total variance, linearly in τ

Between two expiries a and b with $\tau_a \le 21 < \tau_b$:

$$
w^* = w_a + \frac{21 - \tau_a}{\tau_b - \tau_a}\,(w_b - w_a),\qquad \text{cm30\_iv} = \sqrt{252\,w^*/21}.
$$

Interpolating w (not σ) keeps variance additive. Without a bracket the line through the two nearest expiries is
extended, at most 10 sessions beyond the nearer one; with one expiry, its flat σ is used (also at most 10 sessions
away).

## 3. The leak

If expiry a ends before day 0 (clean) and b after it (spanning), $w_b$ contains E and $w_a$ does not. Interpolating
between them puts a fraction of E into a horizon that does not contain the event:

$$
w_{blind}(21) = \sigma_d^2 \cdot 21 + E\,\frac{21 - \tau_a}{\tau_b - \tau_a}.
$$

Worked (`test_cm30_far_from_the_event_never_borrows_event_variance`): $\sigma_d^2 = 0.0002$, E = 0.002, 25 sessions to
day 0, clean expiries at 10 and 19, a spanning one at 30. Blind: $0.0038 + \tfrac{2}{11}(0.008 - 0.0038) = 0.0045636$,
a leak of $E \cdot 2/11 = 0.0003636$, IV 0.2340. Event-aware: 0.2245.

## 4. The event-aware rule

1. If the 21-session horizon holds the next day 0 (21 sessions or fewer away), use only **spanning** expiries;
   otherwise only **clean** ones.
2. Inside one class, $w_j = \sigma_d^2\tau_j + c$ with the same c, so w is linear in τ and the interpolation is exact.
3. With a single spanning expiry, the two-component fit: $\sigma_d^2$ from the longest clean expiry, E from the
   spanning one, $w^* = \sigma_d^2 \cdot 21 + E$.

Before the event, for t in [−21, −1], the event-aware IV is $\sqrt{\sigma_{d,\text{ann}}^2 + 252E/21}$: most of the
run-up in 30-day IV is the event variance entering the horizon, not a market growing nervous.

## 5. Measured at milestone 2

- In the sessions 22 to 60 before an event (the baseline zone of ADR 0004), the blind IV sits above the event-aware one
  by 0.23 vol points on average (p95 1.37); in 76% of those sessions the two are equal, because no clean and spanning
  pair straddles 21 sessions. ADR 0003's "how we'll know it's wrong" line is 0.1 vol points: the event-aware machinery
  is needed.
- In the 21 sessions before an event, the blind IV is 0.22 vol points *below* the event-aware one on average.

## 6. What to remember

- Interpolate total variance, linearly in sessions.
- Never mix a clean and a spanning expiry: that leaks event variance into a horizon without the event.
- The gap between the blind and the event-aware series measures the leak.
