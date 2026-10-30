# A common date factor in single-stock IV, linearly unrelated to VIX

Concept note for milestone 4. Written 2026-10-29. The question is milestone 3's open item (its page §8): Pynnönen's
ρ̂̄ for the crush baselines is 0.30, above ADR 0005's warning line of about 0.2. The code is
`src/earnings_vol/stats/common_factor.py`, the measurement `research/prototypes/rhobar_crush.py` (output kept
beside it), the tests `tests/test_common_factor.py`.

## 1. What ρ̂̄ measures

For each event i, $z_{i,t} = e_{i,t}/s_i$ is its standardised clean baseline change on calendar date t: the abnormal
change of ln IV after the VIX adjustment ($e = \Delta x - \beta_s \Delta m$), divided by its baseline sd. Pynnönen's
eq. 32 pools, over dates, the cross-products of different events on the same date:

$$\hat{\bar\rho} = \frac{\sum_t \sum_{i\ne j} z_{i,t} z_{j,t}}{\sum_t n_t(n_t-1)} = \frac{\sum_t \big[(\sum_i z_{i,t})^2 - \sum_i z_{i,t}^2\big]}{\sum_t n_t(n_t-1)}.$$

It is the average same-date correlation of the standardised changes. ADR 0005 expected little after a market
adjustment: "above about 0.2 … suggests the VIX adjustment failed, or a common data error such as a stale snapshot".

## 2. Three questions, three measurements

1. **One bad date?** Split the numerator by date. On the real data 75.9% of the 489 dates have a positive
   cross-product; the top 10 dates hold 39.2% of it, and without them ρ̂̄ is still 0.19. Broad, with a few big days.
2. **A stale snapshot?** On each of the top 10 dates, every firm's snapshot is from that session with status `ok`,
   and no change is exactly zero. No.
3. **A factor VIX misses?** Build, for each event and date, the mean z of the *other* firms on that date (leave one
   firm out, so the event's own noise is not in its own factor), regress each firm's z on it through the origin,
   rescale the residuals and recompute ρ̂̄: **−0.028**. The loadings are near 1 (median 0.89). A sector-only factor
   leaves 0.030, because it carries the market-wide part too. *What this cannot show* (added after the milestone-4
   review, fix R6): one pure common date factor (ρ 0.3) plus noise, simulated in the real data's gaps, gives the same
   numbers (−0.032 after the leave-one-out step, 0.032 to 0.038 after the sector one; independent z give about 0).
   So the data show one common date component; they do not show a sector structure, or separate one factor from
   several.

## 3. What VIX does

The raw changes (no adjustment) have ρ̂̄ 0.374; after the VIX adjustment 0.301; with β = 1 for every company 0.658
(over-adjusted). The date mean of the adjusted z is uncorrelated with the change of ln VIX (−0.016 over 361 dates;
raw: +0.681). That near-zero is close to automatic: β is each company's least-squares slope of these same changes on
Δ ln VIX, so the residual is uncorrelated with Δ ln VIX by construction, and the date means inherit it. It does not
show that β is correct. What it shows is that the remaining common component is **linearly unrelated to Δ ln VIX**;
the "equal-weighted single-stock IV" of the other 49 firms takes it out. Whether it is a single-stock IV factor of
its own, or VIX entering in another form (non-linear, at another lag, with a β that changes over time), these
numbers cannot tell. *Softened 2026-10-29 after the milestone-4 review (fix R6).*

## 4. What it changes

- **H1's primary:** nothing. The two-way date × firm t lets the errors of one date be correlated in any way.
- **The KP family** (`kp_ow_t`, `kpp_t`, BMP) models same-date correlation explicitly and is mis-sized for the crush;
  their p-values stay withheld (milestone 3 §6.3).
- **The market model** (ADR 0004 §2): an equal-weighted IV index of the other firms as a second factor would remove
  the common part from every abnormal value. That is a change of definition for every market-adjusted number and an
  owner decision, not made here.

## 5. Pitfalls

- Counting each event's own product in the numerator ($S_t^2$ without subtracting $\sum z^2$).
- $n_t^2$ instead of $n_t(n_t - 1)$ pairs, which shrinks ρ̂̄ on thin dates.
- A factor that includes the event's own firm, which removes its own noise and fakes a fit.
