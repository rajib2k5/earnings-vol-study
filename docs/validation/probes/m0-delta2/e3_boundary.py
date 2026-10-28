"""Delta-2 probe e3 (claim 3): is the `not_checked` build invariant complete for `daily` and `mixed`?

Two written forms of the invariant:
  ADR  (ADR 0002 :330-331): error if not_checked and (D >= 2024-09-11, or label NULL and D in a sample's range).
  DM   (data model :480):   not_checked allowed only if (D < 2024-09-11 and label non-null) or the event is outside
                            every sample's date range. "Outside" is read as events.sample == 'none', which data model
                            :493 computes from day0_session (from the RECORDED label), or announce_date if day 0 is
                            null (NULL label).
For every calendar D (weekends included) near the boundaries, every recorded label (BMO / AMC / NULL), every true
timing, and a calendar date error of 0 or +-1..10 calendar days, the probe asks: may the event stay not_checked under
each form (no gap trigger assumed: a quiet event), while its TRUE day 0 lies in `mixed` or `daily`?
Sample ranges by day 0 (ADR 0004 :183-185): daily 2024-12-05..2026-10-26, mixed 2024-09-12..2024-12-04,
coarse ..2024-09-09. NYSE holidays used: 2024-09-02, 2024-11-28, 2024-12-25, 2026-09-07, 2026-11-26.
Falsifier: with the ADR boundary moved to 2024-09-12 the probe must report D = 2024-09-11 AMC as a hole.

Run from the repository root: .venv/bin/python docs/validation/probes/m0-delta2/e3_boundary.py
"""
from datetime import date, timedelta

HOL = {date(2024, 9, 2), date(2024, 11, 28), date(2024, 12, 25), date(2026, 9, 7), date(2026, 11, 26)}


def is_session(d):
    return d.weekday() < 5 and d not in HOL


def nxt(d):
    d += timedelta(1)
    while not is_session(d):
        d += timedelta(1)
    return d


def day0(D, timing):
    if not is_session(D):
        return nxt(D)
    return D if timing == "BMO" else nxt(D)


def sample(d0):
    if d0 is None:
        return "none"
    if date(2024, 12, 5) <= d0 <= date(2026, 10, 26):
        return "daily"
    if date(2024, 9, 12) <= d0 <= date(2024, 12, 4):
        return "mixed"
    if date(2020, 4, 1) <= d0 <= date(2024, 9, 9):
        return "coarse"
    return "none"


def in_some_range(D):
    return sample(D) != "none"


def holes(boundary):
    out = {"ADR": [], "DM": []}
    days = [date(2024, 8, 20) + timedelta(i) for i in range(130)] + [date(2026, 10, 10) + timedelta(i) for i in range(30)]
    for D in days:
        for rec in ("BMO", "AMC", None):
            for true_t in ("BMO", "AMC"):
                for err in [0] + [s * k for k in range(1, 11) for s in (1, -1)]:
                    Dtrue = D + timedelta(err)
                    if rec is not None and err == 0 and rec == true_t:
                        pass
                    true_s = sample(day0(Dtrue, true_t))
                    if true_s not in ("mixed", "daily"):
                        continue
                    adr_ok = not (D >= boundary or (rec is None and in_some_range(D)))
                    rec_d0 = day0(D, rec) if rec is not None else None
                    dm_sample = sample(rec_d0) if rec is not None else sample(D)
                    dm_ok = (D < date(2024, 9, 11) and rec is not None) or dm_sample == "none"
                    case = (str(D), D.strftime("%a"), rec or "NULL", true_t, err, true_s)
                    if adr_ok:
                        out["ADR"].append(case)
                    if dm_ok:
                        out["DM"].append(case)
    return out


h = holes(date(2024, 9, 11))
for form in ("ADR", "DM"):
    no_err = [c for c in h[form] if c[4] == 0]
    with_err = [c for c in h[form] if c[4] != 0]
    print(f"{form}: not_checked allowed but true day 0 in mixed/daily: {len(no_err)} cases without a date error, "
          f"{len(with_err)} with one")
    for c in no_err:
        print("    no date error:", c)
    for c in with_err[:4]:
        print("    date error   :", c)
f = holes(date(2024, 9, 12))
caught = any(c[0] == "2024-09-11" and c[3] == "AMC" and c[4] == 0 for c in f["ADR"])
print("falsifier (ADR boundary moved to 2024-09-12 must expose D=2024-09-11 AMC):", "exposed" if caught else "MISSED")
adr_complete_no_err = not [c for c in h["ADR"] if c[4] == 0]
dm_complete_no_err = not [c for c in h["DM"] if c[4] == 0]
print("RESULT: ADR form complete without date errors:", adr_complete_no_err,
      "| DM form complete without date errors:", dm_complete_no_err)
raise SystemExit(0 if (adr_complete_no_err and dm_complete_no_err and caught) else 1)
