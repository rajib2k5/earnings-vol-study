# =============================================================================
# tables.py — Assemble the rows of `chain_expiry` and `iv_daily` (data model
# §3.5, §3.6) from the pure pieces: chain.expiry_atom() for one expiry and
# termstructure.day_measures() for one session. Pure: run.py reads the quotes
# and the tables, this module only arranges them.
#
# THE NEXT EVENT OF A SESSION
#   Each security's events are anchored on their day 0. An event without a
#   day 0 (timing ambiguous, or a NULL label nobody looked up) is anchored on
#   its EFFECTIVE day 0, next(D), the later candidate (data model §3.5): it
#   still splits the expiries into clean and spanning. A `duplicate_row` is a
#   second calendar row of another event's release, not an event: it has no
#   anchor. The next event of session t is the first anchor > t; the previous
#   event is the last anchor <= t (on day 0 itself the event just happened).
#
# WHICH EXPIRIES SPAN THE NEXT EVENT (ADR 0003 §b; milestone-2 review, claim 7)
#   An expiry spans the event when its last trading day, as_of(expiration),
#   is on or after spans_from = the first session on or after the
#   announcement date D:
#     BMO on a session D   spans_from = D = day 0: the expiry trades after
#                          the news.
#     AMC on a session D   spans_from = D, one session BEFORE day 0. The
#                          expiry's last close comes before the news, but its
#                          holders may decide to exercise until 5:30 p.m. ET
#                          (FINRA Rule 2360), after an after-close release. So
#                          an expiry on D is classed spanning, conservatively:
#                          a clean measure never reads it.
#     no label, session D  the same as AMC: under either label the expiry on D
#                          holds the news.
#     D not a session      spans_from = day 0, the first session after D.
#   Every other expiry is clean.
# =============================================================================

from bisect import bisect_right
from datetime import date
from typing import NamedTuple

from earnings_vol.events import calendar
from earnings_vol.measures import chain, forward, termstructure


class Anchor(NamedTuple):
    """One event on the session clock: its (effective) day 0, its id, and spans_from (see the header)."""

    day0: date
    event_id: str
    spans_from: date


def event_anchors(events, sessions: calendar.Sessions) -> dict[str, list[Anchor]]:
    """{security_id: [Anchor(effective day 0, event_id, spans_from), ...] sorted}, without duplicate rows.

    `events` is the events table (or any frame with its columns event_id,
    security_id, announce_date_used, day0_session, exclusion_reason).
    """
    out: dict[str, list[Anchor]] = {}
    for r in events.itertuples(index=False):
        if r.exclusion_reason == "duplicate_row":
            continue
        d0 = calendar.effective_day0(r.announce_date_used, r.day0_session, sessions)
        out.setdefault(r.security_id, []).append(
            Anchor(d0, r.event_id, sessions.first_on_or_after(r.announce_date_used)))
    for v in out.values():
        v.sort()
    return out


def neighbours(anchors: list[Anchor], session: date) -> tuple[Anchor | None, Anchor | None]:
    """(next anchor with day 0 > session, previous anchor with day 0 <= session); None where there is none."""
    i = bisect_right([a[0] for a in anchors], session)
    return (anchors[i] if i < len(anchors) else None), (anchors[i - 1] if i >= 1 else None)


def spans(expiration: date, anchor: Anchor, sessions: calendar.Sessions) -> bool:
    """Does an expiry hold the anchor's event? Its last trading day is on or after spans_from (header)."""
    return sessions.as_of(expiration) >= anchor.spans_from


def chain_rows(security_id: str, session: date, snapshot_date: date, stale: bool,
               quotes: dict[date, chain.ExpiryQuotes], r_cont: float, sessions: calendar.Sessions,
               next_anchor: Anchor | None, p: chain.AtomParams) -> list[dict]:
    """The chain_expiry rows of one (security, session): one per expiration after the session."""
    rows = []
    for exp in sorted(quotes):
        if exp <= session:
            continue                       # expired or expiring today: no time left, no row
        tau = chain.tau_sessions(session, exp, sessions)
        if tau < 1:
            continue                       # an expiration on a holiday right after the session
        tau_cal = (exp - session).days
        df = forward.discount_factor(r_cont, tau_cal)
        atom = chain.stale_atom() if stale else chain.expiry_atom(quotes[exp], df, tau, p)
        spans_next = None if next_anchor is None else spans(exp, next_anchor, sessions)
        rows.append({"security_id": security_id, "session_date": session, "expiration": exp,
                     "snapshot_date": snapshot_date, "tau_sessions": tau, "tau_cal_days": tau_cal, "df": df,
                     **atom, "next_event_id": None if next_anchor is None else next_anchor[1],
                     "spans_next_event": spans_next})
    return rows


def iv_daily_row(security_id: str, session: date, snapshot_date: date | None, snapshot_status: str,
                 rows: list[dict], anchors: list[Anchor], sessions: calendar.Sessions,
                 p: termstructure.TermParams) -> dict:
    """The iv_daily row of one (security, session), from its chain_expiry rows."""
    nxt, prv = neighbours(anchors, session)
    out = {"security_id": security_id, "session_date": session, "snapshot_date": snapshot_date,
           "snapshot_status": snapshot_status,
           "next_event_id": nxt[1] if nxt else None,
           "sessions_to_next_event": sessions.between(session, nxt[0]) if nxt else None,
           "prev_event_id": prv[1] if prv else None,
           "sessions_since_prev_event": sessions.between(prv[0], session) if prv else None}
    usable = [termstructure.Expiry(r["expiration"], r["tau_sessions"], r["w_atm"], r["iv_atm"],
                                   bool(r["spans_next_event"]))
              for r in rows if r["status"] == "ok" and r["tau_sessions"] >= p.tau_min_sessions]
    if snapshot_status == "ok":
        measures, flags = termstructure.day_measures(usable, out["sessions_to_next_event"], p)
    else:
        measures, flags = termstructure.day_measures([], None, p)
    out.update(measures)
    front = next((r for r in rows if r["expiration"] == out["front_expiry"]), None)
    out["forward_front"] = None if front is None else front["forward"]
    out["vendor_iv_current"] = None        # volatility_history is not extracted (milestone 2 note)
    out["flags"] = "|".join(sorted(flags))
    return out
