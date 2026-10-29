# =============================================================================
# funnel.py — The `sample_funnel` view (data model §4): how many events
# survive each rule on the way to the primary (daily) sample.
#
# Pure: every input is a committed table from data/derived/ plus params.yaml,
# so the committed app/public/data/sample_funnel.json can be rebuilt and
# checked without the local cache.
#
# THE STEPS (milestone 1)
#   1 calendar_events   every calendar row of the 50 securities, 2020-2026,
#                       scheduled future dates included
#   2 timing_known      minus duplicate calendar rows of one release
#                       (duplicate_row) and events whose day 0 cannot be
#                       placed (timing_ambiguous, timing_not_checked)
#   3 daily_range       minus day 0 outside the daily range (ADR 0004 §5)
#   4 crush_observed    minus a missing snapshot on day -1 or day 0
#   5 baseline_minimum  minus fewer than 20 clean baseline sessions or 15
#                       clean one-session changes (ADR 0004 §1)
#   Step 5 cannot yet drop sessions without an IV (milestone 2), so its count
#   is an upper bound.
# =============================================================================

import pandas as pd

from earnings_vol.events import calendar
from earnings_vol.events.eps import orphan_zones
from earnings_vol.panel.baseline import clean_baseline, zones_of_events
from earnings_vol.schema import SAMPLES, TIMING_STATUS

CAVEATS = [
    "Survivorship: the 50 companies are today's largest S&P 500 members by market cap, so firms that shrank or "
    "left the index since 2020 are missing and firms that grew are over-represented.",
    "Timing labels are provisional: only 20 press releases were looked up (owner default, 2026-10-29); every other "
    "event keeps the calendar label as not_checked until SEC EDGAR is set up.",
    "The baseline step counts observed option snapshots only. Sessions without a usable IV are removed at "
    "milestone 2, so the last count is an upper bound.",
]


def _status_counts(series: pd.Series) -> dict:
    vc = series.value_counts()
    return {s: int(vc.get(s, 0)) for s in TIMING_STATUS}


def baseline_counts(events: pd.DataFrame, snap: pd.DataFrame, eps: pd.DataFrame, sessions: calendar.Sessions,
                    windows: dict) -> dict:
    """{event_id: BaselineCount} for every event with a day 0.

    A duplicate_row is a second calendar row of another event's release
    (events.duplicate_rows): it blocks no session of its own, because the
    release's zone is the kept row's.
    """
    zone = tuple(windows["exclusion_zone"])
    orphans = orphan_zones(eps, sessions, tuple(windows["orphan_zone_sessions"]))
    observed = {sid: {sessions.index[d] for d in g.loc[g["snapshot_status"] == "ok", "session_date"]}
                for sid, g in snap.groupby("security_id")}
    out = {}
    for sid, g in events.groupby("security_id"):
        centres = []
        for r in g.itertuples(index=False):
            if r.exclusion_reason == "duplicate_row":
                continue
            if r.day0_session is not None:
                centres.append((r.event_id, [sessions.index[r.day0_session]]))
            else:
                a = r.announce_date_used
                cands = [sessions.next_after(a)] + ([a] if sessions.is_session(a) else [])
                centres.append((r.event_id, [sessions.index[c] for c in cands]))
        ez = zones_of_events(centres, zone)
        for r in g.itertuples(index=False):
            if r.day0_session is None:
                continue
            out[r.event_id] = clean_baseline(sessions.index[r.day0_session], r.event_id, ez, orphans.get(sid, []),
                                             observed.get(sid, set()), tuple(windows["baseline"]))
    return out


def funnel_data(events: pd.DataFrame, snap: pd.DataFrame, eps: pd.DataFrame, session_tbl: pd.DataFrame,
                p, provenance: dict) -> dict:
    sessions = calendar.Sessions(session_tbl["session_date"].tolist())
    status = {(s, d): st for s, d, st in zip(snap["security_id"], snap["session_date"], snap["snapshot_status"])}
    w = p["windows"]
    counts = baseline_counts(events, snap, eps, sessions, w)

    steps = []

    def step(code, label, kept, prev, reason):
        steps.append({"step": code, "label": label, "n_events": int(len(kept)),
                      "n_removed": int(len(prev) - len(kept)), "reason": reason})
        return kept

    s1 = step("calendar_events", "Calendar events of the 50 companies", events, events, None)
    s2 = step("timing_known", "One row per release, and day 0 can be placed",
              s1[~s1["exclusion_reason"].isin(["duplicate_row", "timing_ambiguous", "timing_not_checked"])], s1,
              "duplicate_row|timing_ambiguous|timing_not_checked")
    s3 = step("daily_range", "Day 0 in the daily range " + " to ".join(p["samples"]["daily"]),
              s2[s2["sample"] == "daily"], s2, "outside_daily_range")
    obs = [status.get((s, m)) == "ok" and status.get((s, z)) == "ok"
           for s, m, z in zip(s3["security_id"], s3["day_m1_session"], s3["day0_session"])]
    s4 = step("crush_observed", "Snapshots on day -1 and day 0", s3[obs], s3, "missing_m1|missing_0")
    ok = [counts[e].passes(w["baseline_min_sessions"], w["baseline_min_changes"]) for e in s4["event_id"]]
    step("baseline_minimum",
         f"At least {w['baseline_min_sessions']} clean baseline sessions and {w['baseline_min_changes']} changes",
         s4[ok], s4, "short_baseline")

    return {
        "steps": steps,
        "timing_status_counts": _status_counts(events["timing_status"]),
        "timing_status_by_sample": [{"sample": s, "timing_status_counts": _status_counts(
            events.loc[events["sample"] == s, "timing_status"])} for s in SAMPLES],
        "by_sample": [{"sample": s, "n_events": int((events["sample"] == s).sum())} for s in SAMPLES],
        "by_move_tercile": None,
        "by_move_tercile_status": "not_computed: abs_move_cand_max needs the option forwards of milestone 2",
        "evar_nonpositive": None,
        "evar_nonpositive_status": "not_computed: the event variance is a milestone-2 measure",
        "lookups": {"n_done": int((events["timing_status"] != "not_checked").sum()),
                    "complete": bool(p["timing"]["lookups_complete"])},
        "caveats": list(CAVEATS),
        "provenance": dict(provenance),
    }


def sample_summary(events: pd.DataFrame, funnel: dict, p) -> dict:
    """meta.json's `sample` object: the primary sample after the last funnel step."""
    lo, hi = p["samples"]["daily"]
    last = funnel["steps"][-1]
    daily = events[events["sample"] == "daily"]
    return {"label": "daily", "day0_from": lo, "day0_to": hi, "n_events": last["n_events"],
            "n_securities": int(daily["security_id"].nunique())}
