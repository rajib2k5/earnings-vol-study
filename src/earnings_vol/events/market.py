# =============================================================================
# market.py — `market_daily`: the interest rate and VIX per session
# (data model §3.4). Pure: the FRED series are passed in.
#
# THE RATE
#   FRED DTB3 is the 3-month Treasury bill rate in percent, quoted on a BANK
#   DISCOUNT basis: a bill paying $1 in 91 days costs
#       P = 1 - (d/100) * 91/360.
#   The continuously compounded rate over those 91 days, on a 365-day year
#   (the clock used for discounting, ADR 0003 §0), is
#       r_cont = -ln(P) * 365/91.
#   Example: d = 4.05 gives P = 1 - 0.0405*91/360 = 0.98976250 and
#   r_cont = 0.0102900 * 365/91 = 0.041273. Rates move slowly, so a session
#   without a DTB3 value takes the last value on or before it.
#
# VIX (class R: CBOE data republished by FRED)
#   VIXCLS for that session only. A missing value stays null and is never
#   carried forward: a carried value would be a fake zero change.
# =============================================================================

import math
from datetime import date

import numpy as np
import pandas as pd

BILL_DAYS = 91


def discount_to_continuous(d_percent: float) -> float:
    """DTB3 (percent, bank discount, 91 days) -> continuously compounded rate (decimal)."""
    price = 1.0 - (d_percent / 100.0) * BILL_DAYS / 360.0
    if price <= 0:
        raise ValueError(f"discount rate {d_percent}% gives a non-positive bill price")
    return -math.log(price) * 365.0 / BILL_DAYS


def build_market_daily(sessions: list[date], dtb3: pd.DataFrame, vix: pd.DataFrame) -> pd.DataFrame:
    """One row per session. `dtb3` and `vix` have columns date, value (NaN = missing)."""
    rate = dtb3.dropna(subset=["value"]).sort_values("date")
    rate_dates = rate["date"].tolist()
    rate_vals = rate["value"].tolist()
    vix_by_date = dict(zip(vix["date"], vix["value"]))
    rows = []
    j = -1
    for d in sorted(sessions):
        while j + 1 < len(rate_dates) and rate_dates[j + 1] <= d:
            j += 1
        if j < 0:
            raise ValueError(f"no DTB3 value on or before {d}")
        r = float(rate_vals[j])
        v = vix_by_date.get(d, np.nan)
        v = float(v) if v is not None and not (isinstance(v, float) and math.isnan(v)) else np.nan
        rows.append({
            "session_date": d,
            "r_dtb3": r,
            "r_cont": discount_to_continuous(r),
            "vix_close_cboe": v,
            "ln_vix_cboe": math.log(v) if not math.isnan(v) else np.nan,
        })
    return pd.DataFrame(rows, columns=["session_date", "r_dtb3", "r_cont", "vix_close_cboe", "ln_vix_cboe"])
