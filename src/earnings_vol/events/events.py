# =============================================================================
# events.py — `events`: one row per announcement (data model §3.7).
#
# THE ORDER INSIDE THE LAYER (ADR 0001 §1)
#   base events (calendar rows resolved to securities)
#   -> timing (documents, then the calendar label)          timing.py
#   -> duplicate rows of one release (duplicate_rows)
#   -> day 0 / day -1, prev/next links, gap_sessions_prev   calendar.py
#   -> EPS matching (duplicate rows are skipped)            eps.py
#   -> orphan_nearby, season, sample
#   -> exclusion_reason (last, because it needs sample; duplicate_row is
#      set first, in build_events, because the EPS match needs it)
#
# EXCLUSION REASONS, in order
#   duplicate_row       a second calendar row of another event's release
#                       (ADR 0002 §3, note 3: BRK.B 2024-11-01 beside the
#                       2024-11-02 release). It has no EPS link, and no
#                       zone of its own in other events' baselines: the
#                       release's zone is the kept row's (export/funnel.py).
#   timing_ambiguous    looked up, no document, no label: day 0 unknown
#   timing_not_checked  NOT LOOKED UP and no label, on a session day: day 0
#                       unknown. Within the samples it exists only while
#                       the look-ups are incomplete (owner default
#                       2026-10-29); with every look-up done, the build
#                       invariant forbids it for every event that can enter
#                       a sample (timing.can_enter_sample). A NULL-label
#                       date scheduled after the data end keeps it.
#   outside_samples     day 0 outside every sample range (ADR 0004 §5)
# =============================================================================

from datetime import date

import numpy as np
import pandas as pd

from earnings_vol.events import calendar, securities
from earnings_vol.events.calendar import Sessions
from earnings_vol.events.timing import Reading, lookup_reasons, parse_when, resolve_timing

COLUMNS = ["event_id", "security_id", "ticker_at_event", "announce_date", "announce_date_used", "timing_raw",
           "timing_used", "timing_status", "timing_source", "gap_check_changed", "edgar_accession",
           "edgar_accepted_utc", "day0_session", "day_m1_session", "fiscal_period_end", "prev_event_id",
           "next_event_id", "gap_sessions_prev", "orphan_nearby", "season", "sample", "exclusion_reason",
           "calendar_commit"]

# Which row of a duplicate group is the release: the one with the strongest
# timing evidence (a document beats a calendar label, which beats nothing).
EVIDENCE = {"press_release": 2, "edgar": 2, "calendar": 1}


def base_events(cal: pd.DataFrame, aliases: pd.DataFrame, universe_ids: set[str]) -> pd.DataFrame:
    """Calendar rows (act_symbol, date, when) -> event_id, security_id, ticker_at_event,
    announce_date, timing_raw. Rows of tickers outside the universe are dropped."""
    rows = []
    for r in cal.itertuples(index=False):
        sid = securities.resolve_on(r.act_symbol, r.date, aliases)
        if sid is None or sid not in universe_ids:
            continue
        rows.append({"event_id": f"{sid}:{r.date.isoformat()}", "security_id": sid,
                     "ticker_at_event": r.act_symbol, "announce_date": r.date, "timing_raw": parse_when(r.when)})
    # dtype=object keeps None as None: pandas would otherwise store a text
    # column with a missing value as its own string type with NaN.
    df = pd.DataFrame(rows, columns=["event_id", "security_id", "ticker_at_event", "announce_date", "timing_raw"],
                      dtype=object)
    if df["event_id"].duplicated().any():
        raise ValueError(f"two calendar rows give one event: {df[df['event_id'].duplicated()]['event_id'].tolist()}")
    return df.sort_values(["security_id", "announce_date"], kind="mergesort").reset_index(drop=True)


def readings_by_event(checks: pd.DataFrame) -> dict[str, list[Reading]]:
    out: dict[str, list[Reading]] = {}
    for r in checks.itertuples(index=False):
        eid = f"{r.security_id}:{r.announce_date.isoformat()}"
        out.setdefault(eid, []).append(Reading(r.found, r.release_date, r.label, r.reread, r.checked_on))
    return out


def check_sample_ranges(ranges: dict[str, tuple[date, date]]) -> None:
    """The three day-0 ranges of ADR 0004 §5 must tile one span: coarse, then
    mixed from the next day, then daily from the day after mixed ends. A gap
    would leave day 0s in no sample (the milestone-1 review found 2024-09-10
    and 09-11); an overlap would put one day 0 in two."""
    order = [ranges[k] for k in ("coarse", "mixed", "daily")]
    for lo, hi in order:
        if lo > hi:
            raise ValueError(f"sample range {lo} .. {hi} is empty")
    for (_, hi), (lo, _) in zip(order, order[1:]):
        if (lo - hi).days != 1:
            raise ValueError(f"sample ranges are not contiguous: one ends {hi}, the next starts {lo}")


def duplicate_rows(ev: pd.DataFrame, within_days: int) -> dict[str, str]:
    """{duplicate event_id: the event_id of the row kept as the release}.

    Calendar rows of one security whose dates in use (announce_date_used) lie
    within `within_days` calendar days of the next one form one group: one
    release (ADR 0002 §3; two real releases of one company are at least 63
    days apart in the data). The kept row is the group's only row with the
    strongest timing evidence (EVIDENCE). When two rows tie for it, the build
    stops: which row is the release is then a look-up's to decide, not a
    guess.
    """
    out: dict[str, str] = {}
    for sid, g in ev.groupby("security_id", sort=True):
        rows = sorted(g.itertuples(index=False), key=lambda r: (r.announce_date_used, r.event_id))
        groups: list[list] = []
        for r in rows:
            if groups and (r.announce_date_used - groups[-1][-1].announce_date_used).days <= within_days:
                groups[-1].append(r)
            else:
                groups.append([r])
        for grp in groups:
            if len(grp) < 2:
                continue
            rank = {r.event_id: EVIDENCE.get(r.timing_source, 0) for r in grp}
            best = max(rank.values())
            top = [e for e, k in rank.items() if k == best]
            if len(top) != 1:
                raise ValueError(f"{sid}: calendar rows {[r.event_id for r in grp]} lie within {within_days} days "
                                 f"of each other (one release), and {top} have equally strong timing evidence: "
                                 "look the release up (ADR 0002 §3)")
            out.update({r.event_id: top[0] for r in grp if r.event_id != top[0]})
    return out


def sample_of(d: date, ranges: dict[str, tuple[date, date]]) -> str:
    for name in ("daily", "mixed", "coarse"):
        lo, hi = ranges[name]
        if lo <= d <= hi:
            return name
    return "none"


def build_events(base: pd.DataFrame, checks: pd.DataFrame, sessions: Sessions, *, calendar_commit: str,
                 sample_ranges: dict[str, tuple[date, date]], duplicate_days: int) -> pd.DataFrame:
    """Steps up to the prev/next links, and the duplicate rows (exclusion_reason
    `duplicate_row`, None otherwise). EPS-dependent columns and the other
    exclusion reasons are filled by finish_events()."""
    by_event = readings_by_event(checks)
    unknown = sorted(set(by_event) - set(base["event_id"]))
    if unknown:
        raise ValueError(f"press-release checks for events not in the calendar: {unknown}")
    rows = []
    for r in base.itertuples(index=False):
        t = resolve_timing(r.announce_date, r.timing_raw, by_event.get(r.event_id, []), sessions)
        d0, dm1 = calendar.day0(t["announce_date_used"], t["timing_used"], sessions)
        rows.append({**r._asdict(), **t, "edgar_accession": None, "edgar_accepted_utc": None,
                     "day0_session": d0, "day_m1_session": dm1, "calendar_commit": calendar_commit})
    ev = pd.DataFrame(rows, dtype=object)
    dup = duplicate_rows(ev, duplicate_days)
    ev["exclusion_reason"] = pd.Series(["duplicate_row" if e in dup else None for e in ev["event_id"]],
                                       dtype=object, index=ev.index)
    # prev/next: every calendar row of the security (duplicates included), ordered by announce_date.
    ev = ev.sort_values(["security_id", "announce_date"], kind="mergesort").reset_index(drop=True)
    prev_ids, next_ids, gaps = [], [], []
    for _, g in ev.groupby("security_id", sort=False):
        ids, d0s = g["event_id"].tolist(), g["day0_session"].tolist()
        for i in range(len(ids)):
            prev_ids.append(ids[i - 1] if i > 0 else None)
            next_ids.append(ids[i + 1] if i + 1 < len(ids) else None)
            gaps.append(sessions.between(d0s[i - 1], d0s[i]) if i > 0 and d0s[i] is not None
                        and d0s[i - 1] is not None else None)
    ev["prev_event_id"], ev["next_event_id"] = prev_ids, next_ids
    ev["gap_sessions_prev"] = pd.Series(gaps, dtype=object)
    eff = [calendar.effective_day0(a, d, sessions) for a, d in zip(ev["announce_date_used"], ev["day0_session"])]
    ev["season"] = [calendar.season(d) for d in eff]
    # sample uses day 0, or announce_date when day 0 is null (data model §3.7).
    ev["sample"] = [sample_of(d if d is not None else a, sample_ranges)
                    for d, a in zip(ev["day0_session"], ev["announce_date"])]
    return ev


def finish_events(ev: pd.DataFrame, eps: pd.DataFrame, zones: dict, sessions: Sessions,
                  window: tuple[int, int]) -> pd.DataFrame:
    """fiscal_period_end (from the EPS link), orphan_nearby and exclusion_reason."""
    ev = ev.copy()
    link = {e: pe for e, pe in zip(eps["event_id"], eps["fiscal_period_end"]) if e is not None}
    ev["fiscal_period_end"] = pd.Series([link.get(e) for e in ev["event_id"]], dtype=object)
    near = []
    for sid, a, d0 in zip(ev["security_id"], ev["announce_date_used"], ev["day0_session"]):
        c = sessions.index[calendar.effective_day0(a, d0, sessions)]
        lo, hi = c + window[0], c + window[1]
        near.append(any(z0 <= hi and lo <= z1 for z0, z1 in zones.get(sid, [])))
    ev["orphan_nearby"] = near
    reasons = []
    for first, st, used, a, s in zip(ev["exclusion_reason"], ev["timing_status"], ev["timing_used"],
                                     ev["announce_date_used"], ev["sample"]):
        if first == "duplicate_row":
            reasons.append("duplicate_row")
        elif st == "ambiguous":
            reasons.append("timing_ambiguous")
        elif st == "not_checked" and used is None and sessions.is_session(a):
            reasons.append("timing_not_checked")
        elif s == "none":
            reasons.append("outside_samples")
        else:
            reasons.append(None)
    ev["exclusion_reason"] = pd.Series(reasons, dtype=object)
    for c in ("timing_used", "timing_source", "day0_session", "day_m1_session", "prev_event_id", "next_event_id",
              "timing_raw"):
        ev[c] = pd.Series([None if v is None or (isinstance(v, float) and np.isnan(v)) else v for v in ev[c]],
                          dtype=object, index=ev.index)
    return ev[COLUMNS]


def check_chain(ev: pd.DataFrame) -> list[str]:
    """The prev/next invariants of data model §3.7. Returns the problems found ([] if none)."""
    problems = []
    by_id = ev.set_index("event_id")
    for eid, r in by_id.iterrows():
        for col, back in (("next_event_id", "prev_event_id"), ("prev_event_id", "next_event_id")):
            other = r[col]
            if other is None:
                continue
            if other not in by_id.index:
                problems.append(f"{eid}.{col} -> {other} does not exist")
                continue
            o = by_id.loc[other]
            if o[back] != eid:
                problems.append(f"{eid}.{col} -> {other}, but {other}.{back} = {o[back]}")
            if o["security_id"] != r["security_id"]:
                problems.append(f"{eid}.{col} -> {other} crosses securities")
        if r["prev_event_id"] is not None and not by_id.loc[r["prev_event_id"], "announce_date"] < r["announce_date"]:
            problems.append(f"{eid}: prev is not earlier")
    for sid, g in ev.groupby("security_id"):
        firsts = g[g["prev_event_id"].isna()]["event_id"].tolist()
        lasts = g[g["next_event_id"].isna()]["event_id"].tolist()
        if len(firsts) != 1 or len(lasts) != 1:
            problems.append(f"{sid}: {len(firsts)} first and {len(lasts)} last events")
            continue
        seen, cur = [], firsts[0]
        while cur is not None and cur not in seen:
            seen.append(cur)
            cur = by_id.loc[cur, "next_event_id"]
        expected = g.sort_values("announce_date")["event_id"].tolist()
        if seen != expected:
            problems.append(f"{sid}: following next_event_id visits {len(seen)} of {len(expected)} events in order")
    return problems


def lookup_violations(ev: pd.DataFrame, triggered: dict, sessions: Sessions, lookup_from: date,
                      sessions_before: int, ranges: dict[str, tuple[date, date]]) -> list[dict]:
    """The events that ADR 0002 §3's default rule requires to be looked up, but
    that are still `not_checked` (the build invariant)."""
    out = []
    for r in ev.itertuples(index=False):
        reasons = lookup_reasons(r.announce_date, r.timing_raw, triggered.get(r.event_id, False),
                                 sessions, lookup_from, sessions_before, ranges)
        if r.timing_status == "not_checked" and reasons:
            out.append({"event_id": r.event_id, "sample": r.sample, "reasons": reasons})
    return out


def enforce_lookup_invariant(violations: list[dict], lookups_complete: bool) -> None:
    """Stop the build when the look-ups are declared complete but some are missing.

    While params.timing.lookups_complete is false (owner default 2026-10-29)
    the violations are only reported, and the manifest marks the labels as
    provisional.
    """
    if lookups_complete and violations:
        raise RuntimeError(f"{len(violations)} events need a press-release look-up (ADR 0002 §3 build "
                           f"invariant), e.g. {violations[0]['event_id']}")
