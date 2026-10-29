"""p11b: P6 (the vendor vol against ours) recomputed, and a test of "the +0.70 is a clock difference".

Claim 11 (P6). Independent of measures/report.py: the non-event days, the front expiry and the
two clocks are recomputed here from chain_expiry and iv_daily (stage).
If the vendor annualises on calendar days, the vendor's implied clock T_v = w_ours / vendor^2 (years)
should sit at tau_cal/365, and vendor - ours_cal should not trend with the clock ratio.
Run from the repository root:  python docs/validation/probes/m2/p11_vendor_clock.py <stage dir>
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

stage = Path(sys.argv[1])
ce = pd.read_parquet(stage / "chain_expiry.parquet")
iv = pd.read_parquet(stage / "iv_daily.parquet")
far = lambda v: v is None or pd.isna(v) or v > 2
ne = iv[(iv["snapshot_status"] == "ok") & iv["front_expiry"].notna() & iv["sessions_to_next_event"].map(far)
        & iv["sessions_since_prev_event"].map(far)]
m = ne[["security_id", "session_date", "front_expiry"]].merge(
    ce, left_on=["security_id", "session_date", "front_expiry"], right_on=["security_id", "session_date", "expiration"])
m = m[(m["atm_method"].astype(str) == "bracket_linear") & m["vendor_iv_atm"].notna()].copy()
m["cal"] = np.sqrt(365 * m["w_atm"] / m["tau_cal_days"])
m["snapdays"] = (pd.to_datetime(m["expiration"]) - pd.to_datetime(m["snapshot_date"])).dt.days
m["cal_snap"] = np.sqrt(365 * m["w_atm"] / m["snapdays"])
m["tr252"] = np.sqrt(252 * m["w_atm"] / m["tau_sessions"])
v = m["vendor_iv_atm"]


def s(x):
    x = x * 100
    return f"mean {x.mean():+.3f} median {x.median():+.3f} median|.| {x.abs().median():.3f} p95|.| {x.abs().quantile(.95):.3f} below {(x < 0).mean():.1%}"


print(f"n = {len(m)}")
print("vendor - ours, calendar clock from the session date :", s(v - m["cal"]))
print("vendor - ours, calendar clock from the snapshot date:", s(v - m["cal_snap"]))
print("vendor - ours, session clock (252)                  :", s(v - m["tr252"]))
print("snapshot_date - session_date (days):", (pd.to_datetime(m["snapshot_date"]) - pd.to_datetime(m["session_date"])).dt.days.value_counts().to_dict())
# implied vendor clock
tv = m["w_atm"] / v ** 2                                   # years
print(f"vendor implied T*365 / tau_cal: median {(tv * 365 / m['tau_cal_days']).median():.4f}; "
      f"T*252 / tau_sessions: median {(tv * 252 / m['tau_sessions']).median():.4f}")
# does the gap trend with the clock ratio?
ratio = m["tau_cal_days"] * 252 / (m["tau_sessions"] * 365)
for name, gap in (("cal", v - m["cal"]), ("session", v - m["tr252"])):
    b = np.polyfit(ratio, gap * 100, 1)[0]
    print(f"slope of (vendor - ours_{name}) on the clock ratio tau_cal*252/(tau*365): {b:+.2f} vol pts per unit; "
          f"corr {np.corrcoef(ratio, gap)[0, 1]:+.3f}")
for lo, hi in ((0, 0.95), (0.95, 1.0), (1.0, 1.05), (1.05, 9)):
    g = m[(ratio >= lo) & (ratio < hi)]
    if len(g):
        print(f"  clock ratio [{lo}, {hi}): n={len(g)} vendor-cal {((g['vendor_iv_atm'] - g['cal']) * 100).median():+.3f} "
              f"vendor-session {((g['vendor_iv_atm'] - g['tr252']) * 100).median():+.3f}")
