# =============================================================================
# eps.py — `eps`: one row per (security, fiscal period), matched to the event
# that announced it (data model §3.8, ADR 0002 §3).
#
# WHY A WINDOW AND NOT A DATE JOIN
#   eps_history stores period ends as MONTH-ENDS: Apple's quarter that ended on
#   Saturday 2025-12-27 is stored as 2025-12-31, and Costco's that ended on
#   Sunday 2025-05-11 as 2025-05-31 (data model §1.1). The calendar stores the
#   announcement date. Nothing in the data links the two.
#
# THE WINDOW (ADR 0002 §3, revised after the milestone-1 and delta reviews)
#   The stored end is the last day of the month the quarter ended in, so the
#   true end is no earlier than the FIRST DAY OF THAT MONTH, and a report
#   comes after the true end. A report can therefore come before the stored
#   end: Costco reported the quarter above on 2025-05-29, a lag of -2 days.
#   The window runs from 14 days after the first of the month
#   (params: window_start "month_start+14", lag -13 to -16) to 100 days after
#   the stored end. The earliest report in the data comes 24 days after the
#   first of its month (Costco, 2023-05-25), so 14 days leaves 10 days of
#   margin. The old lower bound, +10 days after the stored end, missed
#   Oracle's and Cisco's reports 8-9 days after a month-end and Costco's in
#   the same month. The 14 days keep a report out of the NEXT period's window
#   until it is at least 74 days late (see below).
#
# THE ASSIGNMENT: ONE-TO-ONE, IN ORDER, NEAREST IN TOTAL
#   Each period gets at most one event and each event at most one period, and
#   a later period never gets an earlier event. Among those assignments the
#   one with the smallest total distance is taken, where a link costs |lag|
#   days and a period left without an event costs lag_max + 1 (more than any
#   link it could have had, and the smallest such cost; it is derived, not a
#   parameter). So a link is never given up for nothing, and when one report
#   is missing the remaining event goes to the period it is nearest to:
#   Costco's 2025-02-28 period (report absent from the calendar) does not take
#   2025-05-29 (lag 90) from the 2025-05-31 period (lag -2).
#
# WHEN A LINK CAN STILL MOVE TO THE NEXT PERIOD (delta review, claim 1b)
#   Only when the report lies in the next period's window: at least 74 days
#   after its own stored end (60 days to the first of the month two months on,
#   for a December or January end, 62-63 otherwise, plus the 14). Then the
#   minimum total can move it: always when the next period's own report is
#   missing (moving lowers the cost once the lag passes about 45 days), and
#   also when that report is present but the late lag is long enough (from
#   81-82 days when the next report comes 30 days after its period). The
#   longest lag in the data is 59 days (Berkshire's Q4). A move to the
#   PREVIOUS period is never cheaper unless a second calendar row of the same
#   release sits beside it, which is why duplicate rows are removed first.
#
# DUPLICATE CALENDAR ROWS (ADR 0002 §3 and note 3)
#   Two calendar rows of one security within a few days of each other are one
#   release (BRK.B has a Friday 2024-11-01 row next to its Saturday 2024-11-02
#   release). events.duplicate_rows() marks the extra row `duplicate_row`
#   before matching, and build_eps() never links it.
#
# ORPHANS AND PRE_CALENDAR
#   A period left without an event is an ORPHAN: its announcement is missing
#   from the calendar. It is PRE_CALENDAR instead when its window starts
#   before the calendar does (2020-01-22) and no event at all lies in it: its
#   event was not missed, the calendar simply does not reach back that far. A
#   period whose window holds an event that went to another period is an
#   orphan even before the calendar start: its own event is the missing one.
#
# TICKER CHANGES
#   DoltHub has FB and META rows for the same quarters (and UTX and RTX). Two
#   rows of one security and period are merged when they agree; when they
#   disagree the period is `ticker_conflict` and both EPS values are set to
#   null (ADR 0002 §4). It keeps its event.
# =============================================================================

import re
from datetime import date, timedelta

import numpy as np
import pandas as pd

from earnings_vol.events import securities


def dedupe_history(hist: pd.DataFrame, aliases: pd.DataFrame) -> pd.DataFrame:
    """eps_history rows -> one row per (security_id, period_end) with a conflict flag."""
    hist = hist.copy()
    hist["security_id"] = [securities.resolve_any(t, aliases) for t in hist["act_symbol"]]
    if hist["security_id"].isna().any():
        raise ValueError(f"unresolved EPS tickers: {sorted(set(hist.loc[hist['security_id'].isna(), 'act_symbol']))}")
    rows = []
    for (sid, pe), g in hist.groupby(["security_id", "period_end_date"], sort=True):
        pairs = {(None if pd.isna(r) else round(float(r), 4), None if pd.isna(e) else round(float(e), 4))
                 for r, e in zip(g["reported"], g["estimate"])}
        conflict = len(pairs) > 1
        rep, est = (None, None) if conflict else next(iter(pairs))
        rows.append({"security_id": sid, "fiscal_period_end": pe, "reported": rep, "estimate": est,
                     "ticker_conflict": conflict})
    return pd.DataFrame(rows, columns=["security_id", "fiscal_period_end", "reported", "estimate", "ticker_conflict"])


def window(period_end: date, window_start: str | int, lag_max: int) -> tuple[date, date]:
    """The dates an announcement of this period can have, both ends inclusive.

    window_start "month_start+N" opens the window N days after the first day
    of the period end's month; the rule is "month_start+14" (params.yaml).
    "month_start" alone is N = 0, the rule between the milestone-1 review and
    the delta review. An int is a fixed lag in days after the stored end. The
    last two are kept for the sensitivity table of milestone 1 §6.5.
    """
    if isinstance(window_start, int) and not isinstance(window_start, bool):
        lo = period_end + timedelta(days=window_start)
    elif isinstance(window_start, str) and (m := re.fullmatch(r"month_start(?:\+(\d{1,2}))?", window_start)):
        lo = period_end.replace(day=1) + timedelta(days=int(m.group(1) or 0))
    else:
        raise ValueError(f"window_start must be 'month_start', 'month_start+N' or an int, got {window_start!r}")
    return lo, period_end + timedelta(days=lag_max)


def match_periods(period_ends: list[date], events: list[tuple[date, str]], *, window_start: str | int,
                  lag_max: int, calendar_start: date) -> dict[date, tuple[str | None, str]]:
    """Match one security's periods to its events.

    `events` is a list of (announce_date, event_id). Returns
    {period_end: (event_id or None, "matched" | "orphan" | "pre_calendar")}.

    A period can take an event inside its window(). Among the one-to-one,
    order-keeping assignments, the one with the smallest total cost is taken:
    |lag| days per link, lag_max + 1 per period left without an event. On
    equal cost the earliest period takes the earliest event it can. An
    unlinked period is pre_calendar if its window starts before the calendar
    and holds no event; otherwise orphan.
    """
    pes, evs = sorted(period_ends), sorted(events)
    wins = [window(pe, window_start, lag_max) for pe in pes]
    unlinked = lag_max + 1
    n, m = len(pes), len(evs)
    # cost[i][j]: the best cost of periods i.. with events j.. still free.
    cost = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        cost[i][m] = cost[i + 1][m] + unlinked
        for j in range(m - 1, -1, -1):
            best = min(cost[i + 1][j] + unlinked, cost[i][j + 1])
            lo, hi = wins[i]
            if lo <= evs[j][0] <= hi:
                best = min(best, abs((evs[j][0] - pes[i]).days) + cost[i + 1][j + 1])
            cost[i][j] = best
    # Walk the table forwards. A link is preferred on a tie, then skipping the
    # event, so equal costs give the earlier event to the earlier period.
    link: dict[date, str] = {}
    i = j = 0
    while i < n and j < m:
        lo, hi = wins[i]
        if lo <= evs[j][0] <= hi and cost[i][j] == abs((evs[j][0] - pes[i]).days) + cost[i + 1][j + 1]:
            link[pes[i]] = evs[j][1]
            i, j = i + 1, j + 1
        elif cost[i][j] == cost[i][j + 1]:
            j += 1
        else:
            i += 1
    out = {}
    for pe, (lo, hi) in zip(pes, wins):
        if pe in link:
            out[pe] = (link[pe], "matched")
        elif lo < calendar_start and not any(lo <= d <= hi for d, _ in evs):
            out[pe] = (None, "pre_calendar")
        else:
            out[pe] = (None, "orphan")
    return out


def build_eps(hist: pd.DataFrame, estimates: pd.DataFrame, aliases: pd.DataFrame, events: pd.DataFrame,
              *, window_start: str | int, lag_max: int, calendar_start: date) -> pd.DataFrame:
    """The `eps` table. `events` needs event_id, security_id, announce_date, day_m1_session,
    announce_date_used and exclusion_reason. Only securities that have events are kept.

    A `duplicate_row` event (events.duplicate_rows) is a second calendar row of
    another event's release, not a release: it is never linked.
    """
    events = events[events["exclusion_reason"] != "duplicate_row"]
    dedup = dedupe_history(hist, aliases)
    dedup = dedup[dedup["security_id"].isin(set(events["security_id"]))]
    ev_by_sec = {sid: list(zip(g["announce_date"], g["event_id"])) for sid, g in events.groupby("security_id")}
    ev_info = events.set_index("event_id")
    est = estimates.copy()
    est["security_id"] = [securities.resolve_any(t, aliases) for t in est["act_symbol"]]
    est = est[est["period"] == "Current Quarter"]
    est_groups = {k: g.sort_values("date") for k, g in est.groupby(["security_id", "period_end_date"])}

    rows = []
    for sid, g in dedup.groupby("security_id", sort=True):
        matches = match_periods(list(g["fiscal_period_end"]), ev_by_sec.get(sid, []),
                                window_start=window_start, lag_max=lag_max, calendar_start=calendar_start)
        for r in g.itertuples(index=False):
            eid, status = matches[r.fiscal_period_end]
            if r.ticker_conflict:
                status = "ticker_conflict"
            lag = None
            cons = dict(consensus=np.nan, consensus_high=np.nan, consensus_low=np.nan,
                        consensus_count=None, consensus_date=None)
            if eid is not None:
                info = ev_info.loc[eid]
                lag = (info["announce_date"] - r.fiscal_period_end).days
                # The last weekly consensus dated on or before day -1. Without a
                # day -1 (timing unknown), the calendar day before D is used.
                cutoff = info["day_m1_session"] if info["day_m1_session"] is not None \
                    else info["announce_date_used"] - timedelta(days=1)
                eg = est_groups.get((sid, r.fiscal_period_end))
                if eg is not None:
                    eg = eg[eg["date"] <= cutoff]
                    if not eg.empty:
                        last = eg.iloc[-1]
                        cons = dict(consensus=_f(last["consensus"]), consensus_high=_f(last["high"]),
                                    consensus_low=_f(last["low"]),
                                    consensus_count=None if pd.isna(last["count"]) else int(last["count"]),
                                    consensus_date=last["date"])
            rep, est_v = _f(r.reported), _f(r.estimate)
            surprise = round(rep - est_v, 4) if np.isfinite(rep) and np.isfinite(est_v) else np.nan
            disp = np.nan
            if (np.isfinite(rep) and np.isfinite(cons["consensus"]) and cons["consensus_count"] is not None
                    and cons["consensus_count"] >= 3 and cons["consensus_high"] > cons["consensus_low"]):
                disp = (rep - cons["consensus"]) / (cons["consensus_high"] - cons["consensus_low"])
            rows.append({"security_id": sid, "fiscal_period_end": r.fiscal_period_end, "event_id": eid,
                         "match_status": status, "lag_days": lag, "reported": rep, "estimate": est_v,
                         "surprise": surprise, **cons, "surprise_disp": disp})
    cols = ["security_id", "fiscal_period_end", "event_id", "match_status", "lag_days", "reported", "estimate",
            "surprise", "consensus", "consensus_high", "consensus_low", "consensus_count", "consensus_date",
            "surprise_disp"]
    out = pd.DataFrame(rows, columns=cols)
    for c in ("lag_days", "consensus_count"):
        out[c] = pd.Series([None if v is None or (isinstance(v, float) and np.isnan(v)) else int(v)
                            for v in out[c]], dtype=object, index=out.index)
    for c in ("event_id", "consensus_date"):
        out[c] = pd.Series([None if v is None or (isinstance(v, float) and np.isnan(v)) else v for v in out[c]],
                           dtype=object, index=out.index)
    return out


def _f(v) -> float:
    return np.nan if v is None or pd.isna(v) else float(v)


def orphan_zones(eps: pd.DataFrame, sessions, zone: tuple[int, int]) -> dict[str, list[tuple[int, int]]]:
    """{security_id: [(first, last) session index]} of orphan and pre_calendar periods.

    The zone runs from period end + zone[0] to + zone[1] sessions (ADR 0002 §3),
    counted from the first session on or after the period end. A zone that
    starts outside the session table is skipped.
    """
    out: dict[str, list[tuple[int, int]]] = {}
    for r in eps[eps["match_status"].isin(["orphan", "pre_calendar"])].itertuples(index=False):
        try:
            base = sessions.index[sessions.first_on_or_after(r.fiscal_period_end)]
        except ValueError:
            continue
        out.setdefault(r.security_id, []).append((base + zone[0], base + zone[1]))
    return out
