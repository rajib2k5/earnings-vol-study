# =============================================================================
# forward.py — The put-call-parity forward of one snapshot and expiry
# (ADR 0003 §0, steps 1 and 2). Milestone 1 needs it for one check: is the
# snapshot taken at the close? Milestone 2 builds chain_expiry on it.
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
# =============================================================================

import math

import numpy as np
import pandas as pd

N_STRIKES = 4


def quote_ok(bid: np.ndarray, ask: np.ndarray) -> np.ndarray:
    """Step 1, first part: the quote filter, before F is known."""
    with np.errstate(divide="ignore", invalid="ignore"):
        mid = (bid + ask) / 2.0
        rel = (ask - bid) / mid
    return (bid > 0) & (bid < ask) & (mid >= 0.05) & (rel <= 0.5)


def parity_forward(quotes: pd.DataFrame, df: float) -> tuple[float, int, float] | None:
    """(F, strikes used, dispersion) from one expiry's quotes, or None.

    `quotes` has columns strike, call_put ('Call'/'Put'), bid, ask.
    dispersion = (max F_K - min F_K) / F over the strikes used.
    """
    q = quotes[quote_ok(quotes["bid"].to_numpy(float), quotes["ask"].to_numpy(float))]
    q = q.assign(mid=(q["bid"] + q["ask"]) / 2.0)
    calls = q[q["call_put"] == "Call"].groupby("strike")["mid"].first()
    puts = q[q["call_put"] == "Put"].groupby("strike")["mid"].first()
    both = calls.index.intersection(puts.index)
    if len(both) == 0:
        return None
    pair = pd.DataFrame({"strike": both.to_numpy(float), "c": calls[both].to_numpy(float),
                         "p": puts[both].to_numpy(float)})
    pair["gap"] = (pair["c"] - pair["p"]).abs()
    chosen = pair.sort_values(["gap", "strike"], kind="mergesort").head(N_STRIKES)
    fk = chosen["strike"] + (chosen["c"] - chosen["p"]) / df
    f = float(np.median(fk))
    return f, int(len(chosen)), float((fk.max() - fk.min()) / f)


def discount_factor(r_cont: float, cal_days: int) -> float:
    return math.exp(-r_cont * cal_days / 365.0)
