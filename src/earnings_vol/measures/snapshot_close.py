# =============================================================================
# snapshot_close.py — Is each option snapshot taken at the CLOSE? Widened from
# one event (ADR 0002, Context) to every after-close event of the daily era.
#
# THE TEST (ADR 0002, "How we'll know it's wrong", first bullet)
#   On an AMC announcement day D the news comes out after 16:00. If the
#   vendor's snapshot of D were taken after the news (from after-hours
#   quotes), the parity-implied spot on D would sit away from D's official
#   close, in the direction of the next morning's move. So compare
#       diff = ln(S_parity / Close_D)
#   on AMC days with the same quantity on ordinary days (no event nearby):
#     - median |diff| on AMC days minus median |diff| on ordinary days, with a
#       bootstrap 95% interval. A difference above its interval's noise means
#       the snapshot leaks after-hours information, and day 0 must change.
#     - the slope of diff on the next overnight gap ln(Open_{D+1}/Close_D) on
#       AMC days. A leak gives a positive slope (up to 1 for a full leak).
#
# THE PARITY SPOT
#   S = F * DF + PV(dividends with ex-date after t and on or before expiry),
#   from the shortest expiry with at least 5 sessions to go. Yahoo closes and
#   dividends are LOCAL ONLY: every per-day number here stays on this machine;
#   only the summary statistics are reported.
# =============================================================================

import math

import numpy as np


def parity_spot(forward: float, df: float, dividends: list[tuple[int, float]], r_cont: float) -> float:
    """F * DF plus the present value of each (calendar days to ex-date, amount)."""
    pv = sum(amount * math.exp(-r_cont * days / 365.0) for days, amount in dividends)
    return forward * df + pv


def bootstrap_median_gap(a: np.ndarray, b: np.ndarray, reps: int = 2000, seed: int = 20261029) -> dict:
    """median(a) - median(b) and a percentile bootstrap 95% interval.

    a and b are resampled independently (they are different days). The seed
    is fixed, so the interval is the same on every run.
    """
    a, b = np.asarray(a, float), np.asarray(b, float)
    rng = np.random.default_rng(seed)
    point = float(np.median(a) - np.median(b))
    sims = np.empty(reps)
    for i in range(reps):
        sims[i] = np.median(rng.choice(a, a.size)) - np.median(rng.choice(b, b.size))
    lo, hi = np.percentile(sims, [2.5, 97.5])
    return {"difference": point, "ci_lo": float(lo), "ci_hi": float(hi), "reps": reps, "seed": seed}


def ols_slope(x: np.ndarray, y: np.ndarray) -> dict:
    """Slope of y on x with an intercept, its plain OLS standard error, and the correlation."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    xc, yc = x - x.mean(), y - y.mean()
    slope = float((xc * yc).sum() / (xc * xc).sum())
    resid = yc - slope * xc
    se = float(math.sqrt((resid * resid).sum() / (x.size - 2) / (xc * xc).sum()))
    corr = float((xc * yc).sum() / math.sqrt((xc * xc).sum() * (yc * yc).sum()))
    return {"slope": slope, "se": se, "corr": corr, "n": int(x.size)}
