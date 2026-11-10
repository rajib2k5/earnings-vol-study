# =============================================================================
# vx_crosscheck.py — The Cboe VX* cross-check of our 30-day IV: pure statistics.
#
# The plan is docs/validation/vx-preregistration.md (ADR 0003, "Validation
# plan (milestone 2)", items 1 and 3); the decisions it left open are D1-D12
# of docs/validation/vx-ledger.md. tools/vx_crosscheck.py reads the files
# and writes data/derived/vx_crosscheck.json; everything here is pure.
#
# THE OBJECTS
#   A series lives on the session grid: one float per NYSE session, NaN where
#   it has no value (on_grid). Ours is cm30_blind_iv (a decimal); Cboe's is
#   the VX* close / 100. Lag L moves Cboe by L sessions (shift).
#   matched_changes(): M = the sessions where both series have a value;
#   consecutive members of M give one change of each ln series. gap 1 is a
#   primary change, gap > 1 a secondary one (D4).
#
# THE BARS (pre-registration §3)
#   i    Pearson r of primary changes                pass when r > 0.8
#   ii   OLS slope of dln VX on dln ours, and the    descriptive: does the
#        reverse slope (dln ours on dln VX)          interval hold 1?
#   iii  spread VX - ours in vol points: the largest pass when <= 2.0
#        |calendar-year median - all-days median|
#   iv   R = mean dln VX(-1->0) / mean dln ours(-1->0) over the events
#                                                    pass when 0.8 <= R <= 1.2
#
# THE INTERVALS (pre-registration §4, D1-D3)
#   block_counts() draws a moving-block bootstrap over the session axis: how
#   often each session is drawn in each replicate. A statistic of
#   observations dated by session is then a weighted statistic, the weight of
#   an observation being its session's count. Moments go through per-session
#   sums (session_sums), so a 10,000 x 1,713 count matrix serves every name
#   at once, and the pooled statistics resample the same dates for all names.
#   weighted_median() gives np.median of the repeated multiset exactly.
#   Bar iv resamples events (event_bootstrap_ratio).
#
# WORKED (made-up numbers, tests/test_vx_crosscheck.py)
#   ours 0.20, 0.22, nan, 0.21 and VX 0.25, 0.26, 0.27, 0.24 on four sessions:
#   M = {0, 1, 3}; one primary change (0->1: ln 1.1 and ln 1.04) and one
#   secondary change over a gap of 2 (1->3: ln(0.21/0.22) and ln(0.24/0.26)).
# =============================================================================

import math
from datetime import date

import numpy as np
import pandas as pd

from earnings_vol.measures import termstructure

BAR_I_MIN_R = 0.8
BAR_III_TOLERANCE_VOL_POINTS = 2.0
BAR_IV_RANGE = (0.8, 1.2)
ADR_SLOPE_BAND = (0.8, 1.2)         # ADR 0003 "How we'll know it's wrong"; exploratory here (D12)
LAGS = (-1, 0, 1)
BLOCK_PRIMARY = 20
BLOCK_SENSITIVITY = 60
REPS = 10_000
SEED = 20261109
HORIZONS = (10, 15, 21, 30, 42, 63)
CI_LEVELS = (2.5, 97.5)

# The columns of session_sums(), in order.
_MOMENTS = ("n", "x", "y", "xx", "yy", "xy")


# --- the session grid -------------------------------------------------------------

def on_grid(dates, values, sessions: list[date]) -> np.ndarray:
    """values placed on the session grid, NaN where there is none. A date that is not a session is an error."""
    pos = {d: i for i, d in enumerate(sessions)}
    out = np.full(len(sessions), np.nan)
    for d, v in zip(dates, values):
        if d not in pos:
            raise ValueError(f"{d} is not a session of the grid")
        if not np.isnan(out[pos[d]]):
            raise ValueError(f"two values for {d}")
        out[pos[d]] = np.nan if v is None else float(v)
    return out


def shift(values: np.ndarray, lag: int) -> np.ndarray:
    """out[i] = values[i + lag]; NaN where i + lag falls off the grid (D5)."""
    v = np.asarray(values, dtype=float)
    out = np.full_like(v, np.nan)
    if lag == 0:
        out[:] = v
    elif lag > 0:
        out[:-lag] = v[lag:]
    else:
        out[-lag:] = v[:lag]
    return out


def matched_changes(ours: np.ndarray, vx: np.ndarray) -> pd.DataFrame:
    """One row per pair of consecutive sessions of M (both values there and > 0): start, end, gap, d_ours, d_vx."""
    a, b = np.asarray(ours, dtype=float), np.asarray(vx, dtype=float)
    with np.errstate(invalid="ignore"):
        ok = np.isfinite(a) & np.isfinite(b) & (a > 0) & (b > 0)
    idx = np.flatnonzero(ok)
    start, end = idx[:-1], idx[1:]
    return pd.DataFrame({"start": start, "end": end, "gap": end - start,
                         "d_ours": np.log(a[end]) - np.log(a[start]),
                         "d_vx": np.log(b[end]) - np.log(b[start])})


def primary(changes: pd.DataFrame) -> pd.DataFrame:
    return changes[changes["gap"] == 1]


def secondary(changes: pd.DataFrame) -> pd.DataFrame:
    return changes[changes["gap"] > 1]


# --- the moving-block bootstrap ---------------------------------------------------

def block_counts(n: int, block: int, reps: int, rng: np.random.Generator) -> np.ndarray:
    """(reps, n) counts: how often each of n sessions is drawn by a moving-block bootstrap (D2).

    ceil(n / block) blocks of `block` consecutive sessions, each start uniform
    on [0, n - block], joined and cut to n sessions (not circular).
    """
    if not 1 <= block <= n:
        raise ValueError(f"block {block} must be between 1 and n = {n}")
    nb = n // block
    starts = rng.integers(0, n - block + 1, size=(reps, nb))
    out = np.empty((reps, n), dtype=np.int32)
    step = 1000
    for r0 in range(0, reps, step):
        s = starts[r0:r0 + step]
        idx = (s[:, :, None] + np.arange(block)).reshape(len(s), nb * block)[:, :n]
        flat = (np.arange(len(s))[:, None] * n + idx).ravel()
        out[r0:r0 + step] = np.bincount(flat, minlength=len(s) * n).reshape(len(s), n)
    return out


def session_sums(pos: np.ndarray, x: np.ndarray, y: np.ndarray, n: int) -> np.ndarray:
    """(n, 6) per-session sums of 1, x, y, x², y², xy for observations dated at positions `pos`.

    x and y are centred on their full-sample means first, so the moments of
    small log changes lose no precision.
    """
    x = np.asarray(x, dtype=float) - np.mean(x)
    y = np.asarray(y, dtype=float) - np.mean(y)
    cols = (np.ones_like(x), x, y, x * x, y * y, x * y)
    return np.column_stack([np.bincount(pos, weights=c, minlength=n) for c in cols])


def moment_stats(sums: np.ndarray, counts: np.ndarray | None = None) -> dict[str, np.ndarray]:
    """r, slope (y on x), reverse slope (x on y) and n from session sums, weighted by each row of `counts`.

    counts None means every session once (the point estimate). A replicate
    with no observation or no variance gives NaN.
    """
    c = np.ones((1, sums.shape[0])) if counts is None else np.atleast_2d(counts)
    m = c @ sums
    n, sx, sy, sxx, syy, sxy = (m[:, i] for i in range(6))
    with np.errstate(invalid="ignore", divide="ignore"):
        mx, my = sx / n, sy / n
        vxx, vyy, vxy = sxx / n - mx * mx, syy / n - my * my, sxy / n - mx * my
        vxx = np.where(vxx > 0, vxx, np.nan)
        vyy = np.where(vyy > 0, vyy, np.nan)
        return {"n": n, "r": vxy / np.sqrt(vxx * vyy), "slope": vxy / vxx, "reverse": vxy / vyy}


def weighted_mean(pos: np.ndarray, v: np.ndarray, n: int, counts: np.ndarray | None = None) -> np.ndarray:
    """The mean of v (dated at `pos`) under each row of counts (None: every session once)."""
    c = np.ones((1, n)) if counts is None else np.atleast_2d(counts)
    num = c @ np.bincount(pos, weights=np.asarray(v, dtype=float), minlength=n)
    den = c @ np.bincount(pos, minlength=n).astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        return num / den


def weighted_median(values: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """Per row of integer weights: the median of the multiset in which value i appears weights[i] times.

    Equal to np.median(np.repeat(values, w)), including the mean of the two
    middle values when the total is even. NaN for a row with no weight.
    """
    v = np.asarray(values, dtype=float)
    w = np.atleast_2d(np.asarray(weights))
    if w.shape[1] != len(v):
        raise ValueError("one weight per value")
    if len(v) == 0:
        return np.full(w.shape[0], np.nan)
    order = np.argsort(v, kind="mergesort")
    vs, cum = v[order], np.cumsum(w[:, order], axis=1)
    total = cum[:, -1]
    k1, k2 = (total + 1) // 2, total // 2 + 1
    j1 = np.minimum((cum < k1[:, None]).sum(axis=1), len(v) - 1)
    j2 = np.minimum((cum < k2[:, None]).sum(axis=1), len(v) - 1)
    out = (vs[j1] + vs[j2]) / 2
    return np.where(total > 0, out, np.nan)


def percentile_ci(values: np.ndarray) -> tuple[float, float, int]:
    """(2.5%, 97.5%) of the finite values, and how many were not finite (D1)."""
    v = np.asarray(values, dtype=float)
    fin = v[np.isfinite(v)]
    if len(fin) == 0:
        return float("nan"), float("nan"), int(len(v))
    lo, hi = np.percentile(fin, CI_LEVELS)
    return float(lo), float(hi), int(len(v) - len(fin))


# --- bar iii: the level spread ----------------------------------------------------

def spread_stats(spread: np.ndarray, years: np.ndarray | None = None, pos: np.ndarray | None = None,
                 counts: np.ndarray | None = None, chunk: int = 1000) -> dict:
    """Bar iii on one name's days: all-days median, each year's median, the largest |year - all|, share > 0.

    `spread` is VX - ours in vol points per day of M, dated at session
    positions `pos`; `counts` (reps, n_sessions) the bootstrap draw (None:
    the point estimate). Without `years` only the median and the share.
    """
    s = np.asarray(spread, dtype=float)
    yrs = np.zeros(len(s), dtype=int) if years is None else np.asarray(years)
    reps = 1 if counts is None else counts.shape[0]
    year_list = [] if years is None else sorted(set(yrs.tolist()))
    out = {"median": [], "share_above": [], "max_abs_dev": [], "years": {y: [] for y in year_list}}
    for r0 in range(0, reps, chunk):
        wc = (np.ones((1, len(s)), dtype=np.int64) if counts is None
              else np.asarray(counts[r0:r0 + chunk])[:, np.asarray(pos)])
        med = weighted_median(s, wc)
        tot = wc.sum(axis=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            out["share_above"].append((wc * (s > 0)).sum(axis=1) / tot)
        devs = []
        for y in year_list:
            sel = yrs == y
            ym = weighted_median(s[sel], wc[:, sel])
            out["years"][y].append(ym)
            devs.append(np.abs(ym - med))
        with np.errstate(invalid="ignore"):
            out["max_abs_dev"].append(np.nanmax(np.vstack(devs), axis=0) if devs else np.full(len(wc), np.nan))
        out["median"].append(med)
    return {"median": np.concatenate(out["median"]), "share_above": np.concatenate(out["share_above"]),
            "max_abs_dev": np.concatenate(out["max_abs_dev"]),
            "years": {y: np.concatenate(v) for y, v in out["years"].items()}}


# --- bar iv: the day-0 crush ratio --------------------------------------------------

def crush_ratio(d_vx: np.ndarray, d_ours: np.ndarray) -> float:
    """R = mean dln VX(-1 -> 0) / mean dln ours(-1 -> 0); NaN when the denominator is 0."""
    den = float(np.mean(d_ours))
    return float(np.mean(d_vx)) / den if den != 0 else float("nan")


def event_bootstrap_ratio(d_vx: np.ndarray, d_ours: np.ndarray, reps: int, rng: np.random.Generator) -> np.ndarray:
    """R in each of `reps` resamples of the events, drawn with replacement (pre-registration §4)."""
    a, b = np.asarray(d_vx, dtype=float), np.asarray(d_ours, dtype=float)
    idx = rng.integers(0, len(a), size=(reps, len(a)))
    den = b[idx].mean(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den != 0, a[idx].mean(axis=1) / den, np.nan)


# --- verdicts -----------------------------------------------------------------------

def verdict_bar_i(r: float) -> str:
    if not np.isfinite(r):
        return "not computable"
    return "pass" if r > BAR_I_MIN_R else "fail"


def holds(lo: float, hi: float, value: float = 1.0) -> bool:
    """Does the interval [lo, hi] hold `value` (bar ii: 1)?"""
    return bool(lo <= value <= hi)


def verdict_bar_iii(max_abs_dev: float, tolerance: float = BAR_III_TOLERANCE_VOL_POINTS) -> str:
    if not np.isfinite(max_abs_dev):
        return "not computable"
    return "pass" if max_abs_dev <= tolerance else "fail"


def verdict_bar_iv(ratio: float) -> str:
    if not np.isfinite(ratio):
        return "not computable"
    return "pass" if BAR_IV_RANGE[0] <= ratio <= BAR_IV_RANGE[1] else "fail"


def bar_iv_provisional(timing_status_counts: dict[str, int]) -> str:
    """Bar iv's caveat, from the timing status of its events: day 0 (ADR 0002) moves when a label is corrected, so
    the ratio stays provisional while any event still rests on the calendar's label alone (``not_checked``)."""
    n = sum(timing_status_counts.values())
    left = timing_status_counts.get("not_checked", 0)
    if n == 0:
        return "Bar iv has no events."
    if left == 0:
        return (f"Bar iv: every one of the {n} events has a checked timing label "
                "(no timing_status not_checked); day 0 follows ADR 0002.")
    which = "every one of these events" if left == n else f"{left} of the {n} events"
    return (f"Bar iv is provisional: day 0 follows ADR 0002 and rests on the calendar's timing label for {which} "
            "(timing_status not_checked); it moves when a label is corrected.")


def lag_finding(r_by_lag: dict[int, float]) -> dict:
    """Which lag has the highest pooled r; a finding when lag -1 or +1 beats lag 0 (pre-registration §2)."""
    best = max(r_by_lag, key=lambda k: (r_by_lag[k], k == 0))
    higher = sorted(k for k in r_by_lag if k != 0 and r_by_lag[k] > r_by_lag[0])
    return {"highest_lag": int(best), "lags_above_lag0": [int(k) for k in higher],
            "finding": ("lag 0 has the highest correlation" if not higher
                        else "lag " + ", ".join(f"{k:+d}" for k in higher) + " is higher than lag 0")}


# --- §5: the maturity of volatility_history.iv_current ------------------------------

def iv_at_horizon(expiries: list[termstructure.Expiry], horizon: int, max_extrap: int) -> float | None:
    """Our blind ATM IV at `horizon` sessions, as cm30_blind_iv is made at 21 (termstructure._blind).

    Linear in total variance between the expiries that bracket the horizon,
    or extrapolated at most `max_extrap` sessions; one expiry alone gives its
    flat sigma when it is within `max_extrap` sessions. IV = sqrt(252 w / h).
    """
    r = termstructure.interpolate(expiries, horizon, max_extrap)
    if r is not None:
        w = r[0]
    elif len(expiries) == 1 and abs(horizon - expiries[0].tau) <= max_extrap:
        w = expiries[0].w * horizon / expiries[0].tau
    else:
        return None
    return math.sqrt(252.0 * w / horizon) if w > 0 else None


def identify_maturity(median_abs_diff: dict[int, float]) -> dict:
    """The horizon with the smallest median |level difference| (pre-registration §5.2, D10).

    Only horizons with a finite median count. A smallest value on the
    longest or the shortest measurable horizon is UNRESOLVED: the maturity
    may lie beyond it.
    """
    measurable = sorted(h for h, v in median_abs_diff.items() if np.isfinite(v))
    if not measurable:
        return {"status": "UNRESOLVED", "horizon": None, "argmin": None, "measurable": [],
                "reason": "no horizon has a value"}
    best = min(measurable, key=lambda h: (median_abs_diff[h], h))
    out = {"argmin": int(best), "measurable": [int(h) for h in measurable]}
    if len(measurable) == 1:
        return {**out, "status": "UNRESOLVED", "horizon": None, "reason": "only one horizon has a value"}
    if best in (measurable[0], measurable[-1]):
        edge = "at or beyond" if best == measurable[-1] else "at or below"
        return {**out, "status": "UNRESOLVED", "horizon": None,
                "reason": f"the smallest median |difference| is on the {'longest' if best == measurable[-1] else 'shortest'}"
                          f" measurable horizon, so the maturity is {edge} {best} sessions"}
    return {**out, "status": "identified", "horizon": int(best), "reason": "an interior minimum"}
