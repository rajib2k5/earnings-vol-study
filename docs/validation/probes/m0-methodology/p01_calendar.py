"""Probe C1a-e, C3f, C5c: ADR 0002 day-0 oracle table, worked.py session counts, spacing.py holiday list
and day-0 rule, all checked against exchange_calendars XNYS.

Run (repo root; exchange_calendars is NOT a project dependency, so it is overlaid ephemerally):
  UV_CACHE_DIR=<scratch>/uvcache uv run --no-sync --frozen --with exchange_calendars \
      python docs/validation/probes/m0-methodology/p01_calendar.py [--mutate]
--mutate replaces the ADR rule with a deliberately wrong one (AMC day 0 = next weekday, ignoring holidays)
to show the oracle comparison can fail. (A first mutant, "D + 1 calendar day rolled forward to a session",
was an EQUIVALENT mutant and passed all rows; it was discarded as PROBE_INVALID.)
"""
import ast
import json
import sys
from pathlib import Path

import exchange_calendars as xc
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
MUTATE = "--mutate" in sys.argv
cal = xc.get_calendar("XNYS", start="2023-01-01", end="2027-12-31")
print("exchange_calendars", xc.__version__, "pandas", pd.__version__, "numpy", np.__version__)
S = pd.DatetimeIndex(cal.sessions)
SS = set(d.date().isoformat() for d in S)


def is_session(d):
    return d in SS


def next_session(d):  # first session strictly after d
    return S[S > pd.Timestamp(d)][0].date().isoformat()


def prev_session(d):  # last session strictly before d
    return S[S < pd.Timestamp(d)][-1].date().isoformat()


def close_et(d):
    c = cal.session_close(pd.Timestamp(d))
    return c.tz_convert("America/New_York").strftime("%H:%M")


def day0_rule(D, label):
    """ADR 0002 §2 table."""
    if not is_session(D):
        return prev_session(D), next_session(D)
    if label == "BMO":
        return prev_session(D), D
    if label == "AMC":
        if MUTATE:  # non-equivalent mutant: next WEEKDAY, ignoring exchange holidays
            return D, str(np.busday_offset(np.datetime64(D), 1, roll="forward"))
        return D, next_session(D)
    raise ValueError(label)


print("\n-- C1a-c: calendar facts")
for d in ["2025-10-13", "2025-11-26", "2025-11-27", "2025-11-28", "2025-07-03", "2025-07-04", "2025-07-07",
          "2025-05-02", "2025-05-03", "2025-05-05"]:
    print(d, pd.Timestamp(d).day_name()[:3], "session" if is_session(d) else "CLOSED",
          close_et(d) if is_session(d) else "")

print("\n-- C1d: ADR 0002 oracle table (D, label used, expected day -1, expected day 0)")
oracle = [
    ("2025-10-30", "AMC", "2025-10-30", "2025-10-31"),
    ("2025-10-14", "BMO", "2025-10-13", "2025-10-14"),
    ("2025-11-07", "AMC", "2025-11-07", "2025-11-10"),
    ("2025-11-26", "AMC", "2025-11-26", "2025-11-28"),
    ("2025-07-03", "AMC", "2025-07-03", "2025-07-07"),
    ("2025-05-03", "AMC", "2025-05-02", "2025-05-05"),  # 'any' label: test both
    ("2025-05-03", "BMO", "2025-05-02", "2025-05-05"),
    ("2024-10-29", "AMC", "2024-10-29", "2024-10-30"),  # GOOGL after correction
]
bad = 0
for D, lab, em1, e0 in oracle:
    m1, d0 = day0_rule(D, lab)
    ok = (m1, d0) == (em1, e0)
    bad += not ok
    print(f"{D} {lab}: got (-1,0)=({m1},{d0}) expected ({em1},{e0}) {'OK' if ok else 'MISMATCH'}")
print("oracle mismatches:", bad)

print("\n-- C3f: worked.py session counts tau = #sessions in (snapshot, expiry]")
for snap, exp, td_claim, cd_claim in [("2025-10-30", "2025-11-14", 11, 15), ("2025-10-30", "2025-11-28", 20, 29),
                                      ("2025-10-31", "2025-11-14", 10, 14), ("2025-10-31", "2025-11-28", 19, 28)]:
    tau = int(((S > pd.Timestamp(snap)) & (S <= pd.Timestamp(exp))).sum())
    cd = (pd.Timestamp(exp) - pd.Timestamp(snap)).days
    print(snap, exp, "tau", tau, "claim", td_claim, "| cal", cd, "claim", cd_claim,
          "OK" if (tau, cd) == (td_claim, cd_claim) else "MISMATCH")

print("\n-- C1e: spacing.py holiday list vs XNYS full-day weekday closures 2024-2026")
src = (ROOT / "research/prototypes/spacing.py").read_text()
hol_line = src[src.index("hol = ["):src.index("]", src.index("hol = [")) + 1]
hol = set(ast.literal_eval(hol_line.split("=", 1)[1].strip()))
wk = pd.bdate_range("2024-01-01", "2026-12-31")
xnys_closed = set(d.date().isoformat() for d in wk if d.date().isoformat() not in SS)
print("in spacing.py not XNYS-closed:", sorted(hol - xnys_closed))
print("XNYS-closed not in spacing.py:", sorted(xnys_closed - hol))
early = [d.date().isoformat() for d in S if close_et(d.date().isoformat()) != "16:00" and "2024" <= d.date().isoformat()[:4] <= "2026"]
print("XNYS early closes 2024-2026:", early)

print("\n-- C5c: spacing.py day0 rule vs ADR 0002 rule on all 336 calendar rows")
rows = json.load(open(ROOT / "data/derived/earnings_calendar_30_large_caps.json"))["rows"]
busc = np.busdaycalendar(holidays=sorted(hol))


def day0_spacing(d, when):  # verbatim logic of spacing.py
    d = np.datetime64(d)
    if when == "After market close":
        return str(np.busday_offset(d, 1, roll="forward", busdaycal=busc))
    return str(np.busday_offset(d, 0, roll="forward", busdaycal=busc))


nonsession = [r for r in rows if not is_session(r["date"])]
print("rows whose date is not an XNYS session:", [(r["act_symbol"], r["date"], r["when"]) for r in nonsession])
diff = []
for r in rows:
    lab = "AMC" if r["when"] == "After market close" else "BMO"
    a = day0_spacing(r["date"], r["when"])
    b = day0_rule(r["date"], lab)[1]
    if a != b:
        diff.append((r["act_symbol"], r["date"], r["when"], a, b))
print("rows where spacing.py day0 != ADR day0:", len(diff), diff[:10])
sys.exit(1 if bad else 0)
