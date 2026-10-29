# pd02 (claims 1b, 1c): adversarial shapes for events/eps.match_periods, and a
# brute-force optimality / one-to-one check on random instances.
#
# Run: uv run --frozen python docs/validation/probes/m1-delta/pd02_eps_shapes.py
import itertools
import random
import sys
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "src"))
from earnings_vol.events.eps import match_periods, window  # noqa: E402

CAL0 = date(2020, 1, 22)


def m(periods, events):
    return match_periods(periods, events, window_start="month_start", lag_max=100, calendar_start=CAL0)


def show(name, periods, events, truth):
    out = m(periods, events)
    got = {pe: out[pe][0] for pe in periods}
    ok = got == truth
    print(f"{'OK  ' if ok else 'FAIL'} {name}")
    for pe in periods:
        print(f"      {pe}  linked={got[pe]!s:6}  truth={truth[pe]!s:6}  status={out[pe][1]}")
    return ok


d = date
results = {}
# S1: a slow reporter (lag 66 days); the Q2 report is missing from the calendar.
results["S1 slow reporter, next report missing"] = show(
    "S1 slow reporter (lag 66), Q2 report missing",
    [d(2024, 3, 31), d(2024, 6, 30), d(2024, 9, 30)],
    [(d(2024, 6, 5), "Q1"), (d(2024, 12, 5), "Q3")],
    {d(2024, 3, 31): "Q1", d(2024, 6, 30): None, d(2024, 9, 30): "Q3"})
# S2: the same reporter, every report present, plus the previous year's Q4 report.
results["S2 slow chain complete"] = show(
    "S2 slow reporter (lags 65-66), all reports present",
    [d(2023, 12, 31), d(2024, 3, 31), d(2024, 6, 30), d(2024, 9, 30)],
    [(d(2024, 3, 5), "Q4"), (d(2024, 6, 5), "Q1"), (d(2024, 9, 4), "Q2"), (d(2024, 12, 5), "Q3")],
    {d(2023, 12, 31): "Q4", d(2024, 3, 31): "Q1", d(2024, 6, 30): "Q2", d(2024, 9, 30): "Q3"})
# S3: Berkshire-shaped duplicate: a Friday calendar row (no label) next to the real Saturday release.
results["S3 duplicate row one day early"] = show(
    "S3 BRK.B duplicate: Fri 2024-11-01 row + real Sat 2024-11-02 release",
    [d(2024, 9, 30)],
    [(d(2024, 11, 1), "dup_fri"), (d(2024, 11, 2), "real_sat")],
    {d(2024, 9, 30): "real_sat"})
# S4: Berkshire Q4 released on Saturday 1 March (60 days) and the Q1 report missing.
results["S4 BRK Q4 on Mar 1, Q1 missing"] = show(
    "S4 BRK-shaped Q4 release on Sat 2025-03-01 (lag 60), Q1 report missing",
    [d(2024, 12, 31), d(2025, 3, 31), d(2025, 6, 30)],
    [(d(2025, 3, 1), "Q4"), (d(2025, 8, 2), "Q2")],
    {d(2024, 12, 31): "Q4", d(2025, 3, 31): None, d(2025, 6, 30): "Q2"})
# S5: Costco 53-week year: FY2023 ended Sun 2023-09-03 but is stored 2023-08-31 (eps_history).
results["S5 COST 53-week"] = show(
    "S5 COST FY2023 (53 weeks, true end 09-03, stored 08-31)",
    [d(2023, 5, 31), d(2023, 8, 31), d(2023, 11, 30)],
    [(d(2023, 5, 25), "Q3"), (d(2023, 9, 26), "Q4"), (d(2023, 12, 14), "Q1")],
    {d(2023, 5, 31): "Q3", d(2023, 8, 31): "Q4", d(2023, 11, 30): "Q1"})
# S6: a 52/53-week year ending Sat 2022-01-01, stored 2021-12-31; report 2022-01-27.
results["S6 year ends Jan 1"] = show(
    "S6 52/53-week year ending 2022-01-01 stored 2021-12-31",
    [d(2021, 9, 30), d(2021, 12, 31)],
    [(d(2021, 10, 28), "Q3"), (d(2022, 1, 27), "Q4")],
    {d(2021, 9, 30): "Q3", d(2021, 12, 31): "Q4"})
# S7: a quarter ending mid-month (the 15th, stored month-end) with a fast report 5 days later, and the
# previous quarter's report missing.
results["S7 mid-month end, fast report, previous missing"] = show(
    "S7 quarters end the 15th (stored month-end); report 5 days after the true end; previous report missing",
    [d(2024, 1, 31), d(2024, 4, 30), d(2024, 7, 31)],
    [(d(2024, 4, 20), "Q2"), (d(2024, 7, 20), "Q3")],
    {d(2024, 1, 31): None, d(2024, 4, 30): "Q2", d(2024, 7, 31): "Q3"})
# S8: PLTR-shaped: two private-company periods before the listing, then reports.
results["S8 PLTR pre-IPO"] = show(
    "S8 PLTR: 2020-03-31 and 06-30 periods before the 2020-09-30 listing",
    [d(2020, 3, 31), d(2020, 6, 30), d(2020, 9, 30)],
    [(d(2020, 11, 12), "Q3")],
    {d(2020, 3, 31): None, d(2020, 6, 30): None, d(2020, 9, 30): "Q3"})
print("PLTR statuses:", {k: v[1] for k, v in m([d(2020, 3, 31), d(2020, 6, 30), d(2020, 9, 30)],
                                                [(d(2020, 11, 12), "Q3")]).items()})


# --- brute force: all order-keeping one-to-one partial assignments ------------------
def brute(pes, evs, lag_max=100):
    pes, evs = sorted(pes), sorted(evs)
    wins = [window(pe, "month_start", lag_max) for pe in pes]
    best = None
    n, m_ = len(pes), len(evs)
    # choose k periods and k events (both increasing), pair them in order
    for k in range(0, min(n, m_) + 1):
        for ps in itertools.combinations(range(n), k):
            for es in itertools.combinations(range(m_), k):
                if not all(wins[i][0] <= evs[j][0] <= wins[i][1] for i, j in zip(ps, es)):
                    continue
                c = sum(abs((evs[j][0] - pes[i]).days) for i, j in zip(ps, es)) + (n - k) * (lag_max + 1)
                if best is None or c < best:
                    best = c
    return best


def cost_of(pes, evs, out, lag_max=100):
    ann = {e: dd for dd, e in evs}
    c = 0
    for pe in pes:
        e = out[pe][0]
        c += (lag_max + 1) if e is None else abs((ann[e] - pe).days)
    return c


def check(matcher, trials, seed):
    rng = random.Random(seed)
    bad = {"cost": 0, "dup": 0, "order": 0, "window": 0}
    first = None
    for _ in range(trials):
        n = rng.randint(1, 5)
        start = d(2021, rng.randint(1, 12), 1)
        q = []
        y, mo = start.year, start.month
        for _k in range(n):
            nxt = d(y + (mo // 12), mo % 12 + 1, 1)
            q.append(nxt - timedelta(days=1))          # a month-end
            mo += 3
            y += (mo - 1) // 12
            mo = (mo - 1) % 12 + 1
        evs = []
        for k in range(rng.randint(0, 6)):
            dd = q[0] - timedelta(days=40) + timedelta(days=rng.randint(0, 100 * n + 80))
            evs.append((dd, f"E{k}"))
        evs = sorted(set(evs), key=lambda t: t[0])
        evs = [(dd, f"E{k}") for k, (dd, _) in enumerate({t[0]: t for t in evs}.values())]
        out = matcher(q, evs)
        linked = [out[pe][0] for pe in sorted(q) if out[pe][0] is not None]
        ann = {e: dd for dd, e in evs}
        if len(linked) != len(set(linked)):
            bad["dup"] += 1
        if [ann[e] for e in linked] != sorted(ann[e] for e in linked):
            bad["order"] += 1
        for pe in q:
            e = out[pe][0]
            if e is not None and not (window(pe, "month_start", 100)[0] <= ann[e] <= window(pe, "month_start", 100)[1]):
                bad["window"] += 1
        if cost_of(q, evs, out) != brute(q, evs):
            bad["cost"] += 1
            if first is None:
                first = (q, evs, out, cost_of(q, evs, out), brute(q, evs))
    return bad, first


bad, first = check(m, 20000, 7)
print("\nbrute force vs match_periods, 20000 random instances:", bad)


def greedy(periods, events):
    # falsifier: first event in the window, one-to-one, in order
    out, used = {}, set()
    for pe in sorted(periods):
        lo, hi = window(pe, "month_start", 100)
        pick = next((e for dd, e in sorted(events) if lo <= dd <= hi and e not in used), None)
        if pick:
            used.add(pick)
        out[pe] = (pick, "matched" if pick else "orphan")
    return out


bad_g, first_g = check(greedy, 20000, 7)
print("falsifier (greedy first-in-window) through the same checker:", bad_g)
print("\nshape results:", {k: ("OK" if v else "FAIL") for k, v in results.items()})
