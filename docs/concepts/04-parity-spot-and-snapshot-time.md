# When was the snapshot taken? The put-call-parity spot

Concept note for milestone 1. Written 2026-10-29. The check is in
[ADR 0002, "How we'll know it's wrong"](../adr/0002-day-zero-convention.md); the code is
`src/earnings_vol/measures/forward.py` and `src/earnings_vol/measures/snapshot_close.py`.

## 1. Why it matters

Day 0 assumes each option snapshot shows the market **at the close**. If the vendor took it later, from after-hours
quotes, an after-close announcement would already be in "day −1", and the crush would be measured on the wrong pair of
days. The option data has no timestamp and no stock price, so the time has to be inferred.

## 2. Put-call parity gives the stock price the options imply

For a European call C and put P on the same strike K and expiry,

$$
C - P = DF\,(F - K) \quad\Longrightarrow\quad F = K + \frac{C - P}{DF},
$$

where F is the forward price for that expiry and DF the discount factor, $e^{-r\,\text{days}/365}$. The forward is the
spot carried to expiry, minus the dividends paid before it, so

$$
S = F \cdot DF + \text{PV(dividends before expiry)} .
$$

Each strike gives one estimate $F_K$. Far from the money one leg is deep in the money and carries an early-exercise
premium and a wide spread, so the code takes the 4 strikes with the smallest |C − P| (near the money) and the median
of their $F_K$ (ADR 0003 §0). The ADR's worked example (AAPL, 2025-10-31, F = 270.55, 14 days at 3.9%, a $0.26
dividend) gives S = 270.405, within a few cents of the official close (a Yahoo value, so not quoted here). A
unit test reproduces the 270.405.

## 3. The test

On an after-close announcement day D the news arrives after 16:00, often with a large move by the next morning.

- If the snapshot is at the close, $\ln(S/\text{Close}_D)$ is just quote noise, about as big as on any day, and it
  does not depend on what happened after hours.
- If the snapshot is late, $\ln(S/\text{Close}_D)$ moves *with* the overnight gap $\ln(\text{Open}_{D+1}/\text{Close}_D)$.

So the check compares the typical |ln(S/Close)| on AMC days with ordinary days, and regresses ln(S/Close) on the next
overnight gap.

## 4. What milestone 1 found (every AMC event of the daily era)

- The median |ln(S/Close)| is larger on AMC days: 11.2 bp against 6.3 bp on ordinary days; the difference, 4.9 bp, has
  a bootstrap 95% interval of 3.0 to 7.4 bp. By the ADR's rule as written, that exceeds its noise.
- But it does not follow the overnight move: the slope is 0.0018 (standard error 0.0030), while the median overnight
  move on those days is 594 bp. A late snapshot would show a slope well above zero.

Read together: the snapshots are at the close; quotes are wider into a release (ADR 0002 already noted this for
AAPL), which makes the parity spot noisier on those days. The ADR's rule reads the first number alone and would call
it a leak, so the result is flagged for the owner rather than settled here.

Yahoo closes and opens are used for this on this machine only. Only the summary numbers above are published.

## 5. Things to be able to say in an interview

- Put-call parity, and why the forward needs no stock price and no dividend forecast.
- Why the 4 strikes nearest the money.
- Why a "level" test (bigger noise) and a "direction" test (co-movement with the gap) answer different questions.
