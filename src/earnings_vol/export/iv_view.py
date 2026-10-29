# =============================================================================
# iv_view.py — The `iv_measures` view (data model §4, contract 0.3.0): how the
# milestone-2 measures are distributed over the primary sample. Aggregates
# only: counts, quantiles and histograms, never a per-event value.
#
# Pure: the inputs are committed tables (data/derived) and the primary sample
# from funnel.run_steps(), so app/public/data/iv_measures.json can be rebuilt
# and checked without the local cache.
#
# THE TWO HISTOGRAMS
#   implied_move  sqrt(E) at day -1 (event_iv.implied_move_m1) of the primary
#                 events with E > 0. The events with E <= 0 have no implied
#                 move; they are counted (n_nonpositive), never dropped
#                 silently. The group's implied move in variance space,
#                 sqrt(mean E) over ALL events with an E (signed), is given
#                 next to it (ADR 0003 §c: averaging sqrt(E) over E > 0 only
#                 would be biased upward).
#   crush         ln cm30(day 0) - ln cm30(day -1) (event_iv.crush_mean_adj).
#   Bins: fixed width (IMPLIED_MOVE_BIN, CRUSH_BIN) from the multiple of the
#   width at or below the smallest value to the one at or above the largest;
#   a value on an inner edge goes to the bin on its right (numpy.histogram).
#   Quantiles: numpy's default linear interpolation.
#
# Rounding (data model §4): moves 5 dp, log quantities 4 dp, shares 4 dp.
# =============================================================================

import math

import numpy as np
import pandas as pd

IMPLIED_MOVE_BIN = 0.005
CRUSH_BIN = 0.025
QUANTILES = (0.1, 0.25, 0.5, 0.75, 0.9)


def histogram(values: np.ndarray, width: float, digits: int) -> dict:
    """Fixed-width bins covering every value: {bin_edges, counts} (see the header)."""
    if values.size == 0:
        return {"bin_edges": [], "counts": []}
    lo = math.floor(round(values.min() / width, 9)) * width
    hi = math.ceil(round(values.max() / width, 9)) * width
    n_bins = max(1, int(round((hi - lo) / width)))
    edges = lo + width * np.arange(n_bins + 1)
    counts, _ = np.histogram(values, bins=edges)
    return {"bin_edges": [round(float(e), digits) for e in edges], "counts": [int(c) for c in counts]}


def quantiles(values: np.ndarray, digits: int) -> dict | None:
    if values.size == 0:
        return None
    return {f"p{int(q * 100)}": round(float(np.quantile(values, q)), digits) for q in QUANTILES}


def iv_measures_data(primary: pd.DataFrame, event_iv: pd.DataFrame, provenance: dict) -> dict:
    """The `iv_measures` payload for the primary events (`primary` holds their event_id)."""
    j = primary[["event_id"]].merge(event_iv, on="event_id", how="left")
    evar = j["evar_m1"].dropna().to_numpy(float)
    moves = j.loc[j["evar_m1"] > 0, "implied_move_m1"].to_numpy(float)
    crush = j["crush_mean_adj"].dropna().to_numpy(float)
    mean_e = float(evar.mean()) if evar.size else None
    return {
        "sample": {"label": "daily", "n_events": int(len(primary))},
        "implied_move": {
            "units": "decimal move (0.05 = 5%)",
            "n_identified": int(evar.size), "n_nonpositive": int((evar <= 0).sum()), "n": int(moves.size),
            "sqrt_mean_evar": round(math.sqrt(mean_e), 5) if mean_e is not None and mean_e > 0 else None,
            "quantiles": quantiles(moves, 5), **histogram(moves, IMPLIED_MOVE_BIN, 5),
        },
        "crush": {
            "units": "log change of the 30-day IV, day -1 to day 0",
            "n": int(crush.size), "mean": round(float(crush.mean()), 4) if crush.size else None,
            "quantiles": quantiles(crush, 4), **histogram(crush, CRUSH_BIN, 4),
        },
        "caveats": [
            "Day -1 quotes of an after-close announcement are often wide, so a single event's E is noisy; "
            "read the distribution, not one bar.",
            "The 30-day IV is event-aware: before day 0 it is interpolated between expiries that span the event "
            "only, so the crush is the event variance leaving the 30-day horizon plus any change in ordinary "
            "volatility (ADR 0004 §3).",
            "Timing labels are provisional (20 press releases checked), so a few events may sit on the wrong day 0.",
        ],
        "provenance": dict(provenance),
    }
