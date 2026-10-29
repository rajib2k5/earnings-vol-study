# =============================================================================
# eps_match_sensitivity.py — How the EPS period match depends on its window's
# lower bound (milestone 1 §6.5, ADR 0002 §3).
#
# Run:  uv run python tools/eps_match_sensitivity.py
#
# Inputs: only committed files (data/derived/eps.parquet for the periods,
# data/derived/events.parquet for the announcements, without its duplicate
# rows, which no rule links: ADR 0002 note 3). The period set does not depend
# on the match, so any rule can be re-run on it.
#
# For each lower bound it prints: matched, orphan, pre_calendar, the orphan
# rate (orphan / (orphan + matched), ADR 0002 "How we'll know it's wrong"),
# and two kinds of wrong link:
#   later_q  a link with lag >= 70 days: a later quarter's report (the rule's
#            own links never exceed the printed max lag, 59 days at the
#            pinned commits);
#   earlier_q  a link to an event before the first day of the period end's
#            month: the quarter cannot have ended yet, so it is an earlier
#            quarter's report.
# `differs` counts the periods whose link or status differs from the rule.
# The rows "first in window" use the rule before the review: the first event
# in the window, a tie to the smaller lag (kept here only to compare); the
# first row is that rule exactly (+10 to +100 days). "first of the month + N"
# rows open the window N days after the first day of the period end's month:
# N = 0 is the rule between the milestone-1 review and its delta review, N = 14
# the rule now (params.yaml eps_match.window_start).
# =============================================================================

from collections import Counter
from datetime import timedelta
from pathlib import Path

from earnings_vol import params as params_mod, schema, store
from earnings_vol.events import eps as eps_mod

ROOT = Path(__file__).resolve().parent.parent
DERIVED = ROOT / "data" / "derived"


def old_rule(periods, events, calendar_start, lo=10):
    """The pre-review matcher: first event in [+lo, +100], smaller lag wins a tie."""
    prop = {pe: next(((d, e) for d, e in events if lo <= (d - pe).days <= 100), None) for pe in periods}
    claim: dict[str, list] = {}
    for pe, c in prop.items():
        if c:
            claim.setdefault(c[1], []).append(pe)
    out = {}
    for pe, c in prop.items():
        if c is None:
            out[pe] = (None, "pre_calendar" if pe + timedelta(days=lo) < calendar_start else "orphan")
        else:
            win = min(claim[c[1]], key=lambda q: (c[0] - q).days)
            out[pe] = (c[1], "matched") if win == pe else (None, "orphan")
    return out


def run(rule, eps, ev_by, ann, calendar_start, lag_max):
    res = {}
    for sid, g in eps.groupby("security_id"):
        periods, evs = sorted(g["fiscal_period_end"]), ev_by.get(sid, [])
        if isinstance(rule, tuple):
            m = old_rule(periods, evs, calendar_start, rule[1])
        else:
            m = eps_mod.match_periods(periods, evs, window_start=rule, lag_max=lag_max,
                                      calendar_start=calendar_start)
        res.update({(sid, pe): v for pe, v in m.items()})
    return res


def summary(res, ann, reference):
    st = Counter(v[1] for v in res.values())
    lags = [(ann[v[0]] - k[1]).days for k, v in res.items() if v[0]]
    later = sum(1 for x in lags if x >= 70)
    earlier = sum(1 for k, v in res.items() if v[0] and ann[v[0]] < k[1].replace(day=1))
    differs = sum(1 for k in res if res[k] != reference[k]) if reference else 0
    rate = st["orphan"] / (st["orphan"] + st["matched"])
    return st, rate, later, earlier, differs, max(lags)


def main() -> int:
    p = params_mod.load()
    cal0 = p.day("eps_match", "calendar_start")
    lag_max = int(p["eps_match"]["lag_max_days"])
    eps = store.read_table(DERIVED / "eps.parquet", schema.EPS)
    ev = store.read_table(DERIVED / "events.parquet", schema.EVENTS)
    ev = ev[ev["exclusion_reason"] != "duplicate_row"]
    ev_by = {s: sorted(zip(g["announce_date"], g["event_id"])) for s, g in ev.groupby("security_id")}
    ann = dict(zip(ev["event_id"], ev["announce_date"]))
    reference = run(p["eps_match"]["window_start"], eps, ev_by, ann, cal0, lag_max)
    print(f"rule: window_start={p['eps_match']['window_start']}, lag_max={lag_max}; {len(reference)} periods")
    print("| Lower bound | Assignment | Matched | Orphan | Pre-calendar | Orphan rate | Later-quarter links "
          "| Earlier-quarter links | Differs from the rule | Max lag |")
    print("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    rows = [("+10 days (before the review)", "first in window, tie to smaller lag", ("old", 10)),
            ("-31 days", "first in window, tie to smaller lag", ("old", -31))]
    rows += [(f"{b:+d} days", "one-to-one, nearest in total", b) for b in (10, 0, -10, -20, -31, -40)]
    rows += [("first of the month (before the delta review)", "one-to-one, nearest in total", "month_start")]
    rows += [(f"first of the month + {n} days" + (" (**the rule**)" if f"month_start+{n}" == p["eps_match"]
              ["window_start"] else ""), "one-to-one, nearest in total", f"month_start+{n}") for n in (7, 14, 21)]
    for label, kind, rule in rows:
        res = run(rule, eps, ev_by, ann, cal0, lag_max)
        st, rate, later, earlier, differs, mx = summary(res, ann, reference)
        print(f"| {label} | {kind} | {st['matched']:,} | {st['orphan']} | {st['pre_calendar']} | {rate:.2%} | "
              f"{later} | {earlier} | {differs} | {mx} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
