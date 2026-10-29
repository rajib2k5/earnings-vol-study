# pd06 (claims 3, 4b): exhaustive check of the can_enter_sample scope over every
# calendar date x label, and check_sample_ranges on broken range sets.
#
# Run: uv run --frozen python docs/validation/probes/m1-delta/pd06_scope_and_ranges.py
import sys
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "src"))
from earnings_vol import params as params_mod  # noqa: E402
from earnings_vol.events import calendar, events, timing  # noqa: E402

p = params_mod.load()
t = calendar.build_session_table(p.day("sessions", "start"), p.day("sessions", "end"), p["snapshot_eras"])
S = calendar.Sessions(t["session_date"].tolist())
R = {k: p.date_range("samples", k) for k in ("daily", "mixed", "coarse")}

# 3: an event that lands in a sample under ANY label must pass can_enter_sample.
hidden, n = [], 0
d = date(2019, 6, 1)
while d <= date(2027, 6, 30):
    for label in ("BMO", "AMC", None):
        d0, _ = calendar.day0(d, label, S)
        s = events.sample_of(d0 if d0 is not None else d, R)
        n += 1
        if s != "none" and not timing.can_enter_sample(d, S, R):
            hidden.append((d, label, s))
    d += timedelta(days=1)
print(f"3: {n} (date, label) cases; sampled but outside can_enter_sample: {len(hidden)} {hidden[:5]}")

# Converse (how wide the scope is): can_enter_sample true but no label gives a sample.
wide = []
d = date(2019, 6, 1)
while d <= date(2027, 6, 30):
    if timing.can_enter_sample(d, S, R) and all(
            events.sample_of(calendar.day0(d, lb, S)[0] or d, R) == "none" for lb in ("BMO", "AMC", None)):
        wide.append(d)
    d += timedelta(days=1)
print(f"   can_enter_sample true but no label samples it: {len(wide)} {wide[:5]}")

# Falsifier for the exhaustive check: a scope that looks only at next(D) must be caught.
orig = timing.can_enter_sample
timing.can_enter_sample = lambda a, s, r: any(lo <= s.next_after(a) <= hi for lo, hi in r.values())
hidden_m = []
d = date(2019, 6, 1)
while d <= date(2027, 6, 30):
    for label in ("BMO", "AMC", None):
        d0, _ = calendar.day0(d, label, S)
        if events.sample_of(d0 if d0 is not None else d, R) != "none" and not timing.can_enter_sample(d, S, R):
            hidden_m.append((d, label))
    d += timedelta(days=1)
timing.can_enter_sample = orig
print(f"   falsifier (next(D) only): hidden {len(hidden_m)} e.g. {hidden_m[:2]}")

# 4b: check_sample_ranges on broken sets.
D = date.fromisoformat
cases = {
    "as params": R,
    "gap of 2 days (coarse ends 09-09)": {**R, "coarse": (D("2020-04-01"), D("2024-09-09"))},
    "overlap of 1 day": {**R, "mixed": (D("2024-09-11"), D("2024-12-04"))},
    "empty range": {**R, "mixed": (D("2024-12-04"), D("2024-09-12"))},
    "daily before mixed": {"coarse": R["coarse"], "mixed": R["daily"], "daily": R["mixed"]},
    "gap between mixed and daily": {**R, "daily": (D("2024-12-06"), D("2026-10-26"))},
    "daily extends past data_end": {**R, "daily": (D("2024-12-05"), D("2027-12-31"))},
}
for name, rr in cases.items():
    try:
        events.check_sample_ranges(rr)
        print(f"4b: {name:32s} -> accepted")
    except ValueError as e:
        print(f"4b: {name:32s} -> refused: {e}")
