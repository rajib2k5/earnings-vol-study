"""Probe C5b, C5d and session-count facts quoted in ADR 0004 / data-model (533, 60-session lead, 1,713, 695).
Re-derives the gaps exactly as spacing.py does (its day-0 rule matched ADR 0002 on all 336 rows, see p01), then
asks what the 20.3% / 97.1% shares actually measure.
Run: UV_CACHE_DIR=<scratch>/uvcache uv run --no-sync --frozen --with exchange_calendars \
         python docs/validation/probes/m0-methodology/p05_spacing_check.py
"""
import json
from pathlib import Path

import exchange_calendars as xc
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
cal = xc.get_calendar("XNYS", start="2019-01-01", end="2027-12-31")
S = pd.DatetimeIndex(cal.sessions)
idx = {d.date().isoformat(): i for i, d in enumerate(S)}


def nxt(d):
    return S[S > pd.Timestamp(d)][0].date().isoformat()


rows = json.load(open(ROOT / "data/derived/earnings_calendar_30_large_caps.json"))["rows"]
by = {}
for r in rows:
    d = r["date"]
    d0 = nxt(d) if (r["when"] == "After market close" or d not in idx) else d
    by.setdefault(r["act_symbol"], []).append(idx[d0])
g = np.array([b - a for v in by.values() for a, b in zip(sorted(v), sorted(v)[1:])])
print("n", len(g), "median", np.median(g), "min", g.min())
print(f"P(g<=60)  day -60 on/before prev day 0            = {np.mean(g<=60):.3f}")
print(f"P(g<=70)  [-60,-20] overlaps prev [0,+10]           = {np.mean(g<=70):.3f}   <- the 97.1% figure")
print(f"P(60<=g<=70) day -60 INSIDE prev [0,+10] (ADR text) = {np.mean((g>=60)&(g<=70)):.3f}")
print(f"P(21<=g<=60) fixed [-60,-20] contains prev CRUSH change (-1->0 both inside) = {np.mean((g>=21)&(g<=60)):.3f}")
print(f"P(g<=81) [-60,-20] overlaps prev [0,+21]           = {np.mean(g<=81):.3f}")

# C5d: cm30 horizon (t, t+21] contains another event's day 0 iff d0 - t in [1, 21]  <=> u = t - d0 in [-21, -1]
u = np.arange(-30, 15)
contains = (-u >= 1) & (-u <= 21)
print("C5d: first u (rel. to other event's day 0) whose cm30 horizon contains it:", u[contains].min(),
      "| last:", u[contains].max(), "| ADR exclusion zone starts at -21")

# session-count facts
def n_sessions(a, b):
    return int(((S >= pd.Timestamp(a)) & (S <= pd.Timestamp(b))).sum())
print("sessions 2024-09-11..2026-10-26 (ADR 0004: 533):", n_sessions("2024-09-11", "2026-10-26"))
print("session 60 after 2024-09-11 (ADR 0004: 2024-12-05):", S[idx["2024-09-11"] + 60].date())
print("sessions 2020-01-02..2026-10-26 (data-model: 1,713):", n_sessions("2020-01-02", "2026-10-26"))
mwf = [d for d in S if pd.Timestamp("2020-01-06") <= d <= pd.Timestamp("2024-09-09") and d.day_of_week in (0, 2, 4)]
print("Mon/Wed/Fri sessions 2020-01-06..2024-09-09 (data-model: 695):", len(mwf))
d0_first_coarse = S[idx["2020-01-06"] + 60].date()
print("coarse era: first day 0 with a full [-60] inside the M/W/F era (ADR 0004: about 2020-04-01):", d0_first_coarse)
