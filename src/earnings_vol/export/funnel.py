# =============================================================================
# funnel.py — The `sample_funnel` view (data model §4): how many events
# survive each rule on the way to the primary (daily) sample.
#
# Pure: every input is a committed table from data/derived/ plus params.yaml,
# so the committed app/public/data/sample_funnel.json can be rebuilt and
# checked without the local cache.
#
# THE STEPS (milestone 1; step 5 and the IV rule of step 6 since milestone 2)
#   1 calendar_events   every calendar row of the 50 securities, 2020-2026,
#                       scheduled future dates included
#   2 timing_known      minus duplicate calendar rows of one release
#                       (duplicate_row) and events whose day 0 cannot be
#                       placed (timing_ambiguous, timing_not_checked)
#   3 daily_range       minus day 0 outside the daily range (ADR 0004 §5)
#   4 crush_observed    minus a missing snapshot on day -1 or day 0
#   5 iv_usable         minus no cm30_iv on day -1 or day 0 (iv_daily)
#   6 baseline_minimum  minus fewer than 20 clean baseline sessions or 15
#                       clean one-session changes (ADR 0004 §1), where a clean
#                       session now also needs a cm30_iv (rule 4)
#
# THE MILESTONE-2 FIELDS
#   by_move_tercile   ADR 0002 §3 job 3, per date sample: the events of the
#                     sample (duplicate rows aside) with an abs_move_cand_max,
#                     cut into terciles of it by rank (ties by event_id): rank
#                     r of n goes to tercile 1 + floor(3 r / n). Per tercile:
#                     the timing status counts, the gap-triggered label
#                     changes, the mean abs_move_cand_max, the mean
#                     crush_mean_adj, and the share of gap contradictions:
#                     events whose timing_check.gap_verdict_yf (a Yahoo-gap
#                     verdict, committed since the owner's decision of
#                     2026-10-29) is `contradicts`, among those with a verdict.
#   evar_nonpositive  over the events of the last step: how many have an E at
#                     day -1 (event_iv.evar_m1), and how many of those E <= 0.
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
    "A baseline session counts only with an observed option snapshot and a 30-day IV (cm30_iv), so the last count "
    "is the primary sample before the milestone-3 eligibility rules of each measure.",
    "Implied moves are read on day -1, from the two shortest option expiries that span day 0; when that day's "
    "quotes are wide, the estimate is noisy (ADR 0003).",
]
TERCILE_NOTE = ("terciles of abs_move_cand_max by rank within each date sample; share_gap_contradicts is "
                "among the events with a Yahoo-gap verdict on the label in use")


def _status_counts(series: pd.Series) -> dict:
    vc = series.value_counts()
    return {s: int(vc.get(s, 0)) for s in TIMING_STATUS}


def usable_sessions(iv_daily: pd.DataFrame) -> pd.Series:
    """ADR 0004 §1 rules 3 and 4: an ok snapshot and a cm30_iv."""
    return (iv_daily["snapshot_status"] == "ok") & iv_daily["cm30_iv"].notna()


def baseline_counts(events: pd.DataFrame, iv_daily: pd.DataFrame, eps: pd.DataFrame, sessions: calendar.Sessions,
                    windows: dict) -> dict:
    """{event_id: BaselineCount} for every event with a day 0.

    A duplicate_row is a second calendar row of another event's release
    (events.duplicate_rows): it blocks no session of its own, because the
    release's zone is the kept row's.
    """
    zone = tuple(windows["exclusion_zone"])
    orphans = orphan_zones(eps, sessions, tuple(windows["orphan_zone_sessions"]))
    use = usable_sessions(iv_daily)
    observed = {sid: {sessions.index[d] for d in g.loc[use[g.index], "session_date"]}
                for sid, g in iv_daily.groupby("security_id")}
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


def move_terciles(events: pd.DataFrame, event_iv: pd.DataFrame, timing_check: pd.DataFrame) -> list[dict]:
    """ADR 0002 §3 job 3: per date sample and tercile of abs_move_cand_max (see the header)."""
    j = events.merge(event_iv[["event_id", "abs_move_cand_max", "crush_mean_adj"]], on="event_id", how="left") \
        .merge(timing_check[["event_id", "gap_verdict_yf"]], on="event_id", how="left")
    j = j[(j["exclusion_reason"] != "duplicate_row") & j["abs_move_cand_max"].notna()]
    out = []
    for sample in ("daily", "mixed", "coarse"):
        g = j[j["sample"] == sample].sort_values(["abs_move_cand_max", "event_id"], kind="mergesort")
        n = len(g)
        tercile = [1 + (3 * r) // n for r in range(n)]
        g = g.assign(tercile=tercile)
        for t in (1, 2, 3):
            c = g[g["tercile"] == t]
            crush = c["crush_mean_adj"].dropna()
            verdict = c["gap_verdict_yf"].dropna()
            share = round(float((verdict == "contradicts").mean()), 4) if len(verdict) else None
            out.append({"sample": sample, "tercile": t, "n_events": int(len(c)),
                        "timing_status_counts": _status_counts(c["timing_status"]),
                        "share_gap_contradicts": share,
                        "n_gap_check_changed": int(c["gap_check_changed"].sum()),
                        "mean_abs_move": round(float(c["abs_move_cand_max"].mean()), 5) if len(c) else None,
                        "n_crush": int(len(crush)),
                        "mean_crush_mean_adj": round(float(crush.mean()), 4) if len(crush) else None})
    return out


def run_steps(events: pd.DataFrame, iv_daily: pd.DataFrame, eps: pd.DataFrame, session_tbl: pd.DataFrame,
              p) -> tuple[list[dict], pd.DataFrame]:
    """The funnel steps, and the events left after the last one (the primary sample)."""
    sessions = calendar.Sessions(session_tbl["session_date"].tolist())
    status = {(s, d): st for s, d, st in zip(iv_daily["security_id"], iv_daily["session_date"],
                                             iv_daily["snapshot_status"])}
    has_iv = {(s, d) for s, d, ok in zip(iv_daily["security_id"], iv_daily["session_date"],
                                         usable_sessions(iv_daily)) if ok}
    w = p["windows"]
    counts = baseline_counts(events, iv_daily, eps, sessions, w)

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
    iv_ok = [(s, m) in has_iv and (s, z) in has_iv
             for s, m, z in zip(s4["security_id"], s4["day_m1_session"], s4["day0_session"])]
    s5 = step("iv_usable", "A 30-day IV on day -1 and day 0", s4[iv_ok], s4, "no_cm30_m1|no_cm30_0")
    ok = [counts[e].passes(w["baseline_min_sessions"], w["baseline_min_changes"]) for e in s5["event_id"]]
    s6 = step("baseline_minimum",
              f"At least {w['baseline_min_sessions']} clean baseline sessions and {w['baseline_min_changes']} changes",
              s5[ok], s5, "short_baseline")
    return steps, s6


def funnel_data(events: pd.DataFrame, iv_daily: pd.DataFrame, eps: pd.DataFrame, session_tbl: pd.DataFrame,
                event_iv: pd.DataFrame, timing_check: pd.DataFrame, p, provenance: dict) -> dict:
    steps, s6 = run_steps(events, iv_daily, eps, session_tbl, p)
    evar = s6[["event_id"]].merge(event_iv[["event_id", "evar_m1"]], on="event_id", how="left")["evar_m1"]
    n_id = int(evar.notna().sum())
    n_np = int((evar <= 0).sum())
    return {
        "steps": steps,
        "timing_status_counts": _status_counts(events["timing_status"]),
        "timing_status_by_sample": [{"sample": s, "timing_status_counts": _status_counts(
            events.loc[events["sample"] == s, "timing_status"])} for s in SAMPLES],
        "by_sample": [{"sample": s, "n_events": int((events["sample"] == s).sum())} for s in SAMPLES],
        "by_move_tercile": move_terciles(events, event_iv, timing_check),
        "by_move_tercile_status": "computed: " + TERCILE_NOTE,
        "evar_nonpositive": {"n_events": int(len(s6)), "n_identified": n_id, "n": n_np,
                             "share": round(n_np / n_id, 4) if n_id else None},
        "evar_nonpositive_status": (f"computed: E at day -1 over the {len(s6)} events of the last step; "
                                    f"{len(s6) - n_id} have no E at day -1 (fewer than two usable expiries "
                                    "span day 0)"),
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
