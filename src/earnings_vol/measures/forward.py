# =============================================================================
# forward.py — The put-call-parity forward of one snapshot and expiry
# (ADR 0003 §0, steps 1 and 2). Milestone 1 needed it for one check: is the
# snapshot taken at the close? Milestone 2 builds chain_expiry on it
# (measures/chain.py calls forward_from_pairs on arrays).
#
# PUT-CALL PARITY
#   For European options on the same strike K and expiry,
#       C - P = DF * (F - K)    so    F_K = K + (C - P) / DF,
#   where DF = exp(-r * days/365) discounts on the CALENDAR clock (interest
#   accrues every day; variance only on sessions, ADR 0003 §0).
#
# WHICH STRIKES
#   Only quotes with 0 < bid < ask, mid >= 0.05 and (ask - bid)/mid <= 0.5.
#   Of the strikes where both the call and the put pass, take the 4 with the
#   smallest |C_mid - P_mid| (ties: the lower strike). Near the money both legs
#   are cheap and liquid, and neither carries much early-exercise premium.
#   F = the median of their F_K. With fewer than 4 such strikes use all; with
#   none there is no forward.
#
# TIES ARE COUNTED IN TICKS, NOT FLOATS (milestone-2 review, claim 2a)
#   Quotes are whole cents, so bid + ask of each leg is a whole number of
#   cents, and 2 |C - P| = |(bid + ask)_call - (bid + ask)_put| is an integer
#   number of cents. The ranking uses that integer. On floats, an exact tie
#   can break the wrong way: |0.005 - 0.010| = 0.005 but |0.010 - 0.015| =
#   0.004999999999999999, which sent the tie to the HIGHER strike. As
#   integers both are 1, and the stable sort keeps the lower strike first.
# =============================================================================

import math

import numpy as np
import pandas as pd

N_STRIKES = 4
MIN_MID = 0.05
MAX_REL_SPREAD = 0.5


def quote_ok(bid: np.ndarray, ask: np.ndarray, min_mid: float = MIN_MID,
             max_rel_spread: float = MAX_REL_SPREAD) -> np.ndarray:
    """Step 1, first part: the quote filter, before F is known. A NaN quote fails."""
    with np.errstate(divide="ignore", invalid="ignore"):
        mid = (bid + ask) / 2.0
        rel = (ask - bid) / mid
    return (bid > 0) & (bid < ask) & (mid >= min_mid) & (rel <= max_rel_spread)


def forward_from_pairs(strike: np.ndarray, c_mid: np.ndarray, p_mid: np.ndarray, df: float,
                       n_strikes: int = N_STRIKES) -> tuple[float, int, float] | None:
    """(F, strikes used, dispersion) from the strikes whose call AND put passed the filter.

    `strike` is sorted ascending. The `n_strikes` smallest |C - P| are chosen,
    ties to the lower strike (a stable sort keeps the strike order). |C - P|
    is ranked as the integer 2 |C - P| in cents (see the header).
    """
    if len(strike) == 0:
        return None
    gap_cents = np.rint(2.0 * 100.0 * np.abs(c_mid - p_mid)).astype(np.int64)
    chosen = np.argsort(gap_cents, kind="mergesort")[:n_strikes]
    fk = strike[chosen] + (c_mid[chosen] - p_mid[chosen]) / df
    f = float(np.median(fk))
    return f, int(len(chosen)), float((fk.max() - fk.min()) / f)


def parity_forward(quotes: pd.DataFrame, df: float) -> tuple[float, int, float] | None:
    """(F, strikes used, dispersion) from one expiry's quotes, or None.

    `quotes` has columns strike, call_put ('Call'/'Put'), bid, ask.
    dispersion = (max F_K - min F_K) / F over the strikes used.
    """
    q = quotes[quote_ok(quotes["bid"].to_numpy(float), quotes["ask"].to_numpy(float))]
    q = q.assign(mid=(q["bid"] + q["ask"]) / 2.0)
    calls = q[q["call_put"] == "Call"].groupby("strike")["mid"].first()
    puts = q[q["call_put"] == "Put"].groupby("strike")["mid"].first()
    both = calls.index.intersection(puts.index).sort_values()
    return forward_from_pairs(both.to_numpy(float), calls[both].to_numpy(float), puts[both].to_numpy(float), df)


def discount_factor(r_cont: float, cal_days: int) -> float:
    return math.exp(-r_cont * cal_days / 365.0)
