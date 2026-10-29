# =============================================================================
# event_iv.py — The per-event IV measures: one row of `event_iv` per event
# (data model §3.11a). They are the IV columns of `event_measures`, built at
# milestone 2 from iv_daily and chain_expiry, as session_snapshot was built
# early at milestone 1. Milestone 3 (panel) adds the baseline, the market
# adjustment and eligibility around them.
#
# THE TWO SESSIONS OF THE CRUSH (ADR 0004 §4)
#   pre  = the last observed session at day -1, or day -2 if -1 is unobserved;
#   post = the first observed session at day 0, or day +1 if 0 is unobserved.
#   Each end is at most one session from its target. In the daily sample they
#   are day -1 and day 0; in the Mon/Wed/Fri sample the crush often spans two
#   sessions, and crush_span_sessions says how many.
#
# THE COLUMNS
#   evar_m1, implied moves, sigma_d_m1, cm30_m1, ts_slope_m1   iv_daily at pre
#                    (only if iv_daily's next event at pre IS this event)
#   evar_m2          E at day -2 (robustness: wide announcement-day quotes)
#   crush_mean_adj   ln cm30(post) - ln cm30(pre). The mean adjustment of a
#                    one-step change is nothing, so this is the plain log
#                    change (ADR 0004 §2; the market-adjusted crush_cboe is
#                    milestone 3 and stays local).
#   dsigma_d_mean_adj  1/2 ln(sigma_d^2(post) / sigma_d^2(pre)), sigma_d^2 the
#                    forward variance between the SAME two expiries (E's pair
#                    at pre) on both days.
#   front fixed      T1* = the shortest ok expiry at pre with tau >= 5 at day 0
#                    (ADR 0003 §a). Its IV at pre and at post; at post, if the
#                    vendor did not list T1*, w is interpolated (never
#                    extrapolated) at tau(T1*) from that day's usable expiries
#                    of T1*'s class (tables.spans, the rule chain_expiry uses),
#                    and front_fixed_interpolated is set.
#                    crush_front_fixed = ln iv_T1*(post) - ln iv_T1*(pre).
#   realized_ret_0   ADR 0003 §e: ln(F_post(T) / F_pre(T)) + r * days / 365 for
#                    the shortest expiry T with a forward on both days and
#                    tau >= 5 at post. The forward nets out dividends, so this
#                    is a total return; the carry term adds back the interest.
#   abs_move_cand_max  the label-free move of ADR 0002 §3 job 3: with D the
#                    announcement date used, max(|r(prev(D) -> D)|,
#                    |r(D -> next(D))|) for a session D, |r(prev(D) -> next(D))|
#                    otherwise. Each start is the last observed session at its
#                    target or one before; each end the first observed at its
#                    target or one after. Null if a move cannot be measured.
#
# WORKED (the AAPL example): pre 2025-10-30, post 2025-10-31; T1* = 2025-11-14
# (10 sessions after day 0); iv 0.2826 -> 0.2364, crush_front_fixed =
# ln(0.2364/0.2826) = -0.1787; realized_ret_0 = ln(270.55/271.42) + 0.039/365 =
# -0.3112%; dsigma_d_mean_adj = 1/2 ln(((0.004179 - 0.002217)/9) /
# ((0.005616 - 0.003486)/9)) = -0.0410.
# =============================================================================

import math
from datetime import date

from earnings_vol.events import calendar
from earnings_vol.measures import chain, tables, termstructure

# The value columns event_row() fills, in the registry's order (schema.EVENT_IV).
EVENT_FIELDS = ("pre_session", "post_session", "crush_span_sessions", "evar_m1", "evar_m2", "implied_move_m1",
                "implied_abs_move_total_m1", "implied_move_status", "sigma_d_m1", "cm30_m1", "cm30_0",
                "ts_slope_m1", "crush_mean_adj", "dsigma_d_mean_adj", "front_fixed_expiry", "front_fixed_iv_m1",
                "front_fixed_iv_0", "front_fixed_interpolated", "crush_front_fixed", "realized_ret_0",
                "abs_ret_over_implied", "abs_move_cand_max")


class EventInputs:
    """The tables event_row() reads, as look-ups.

    daily    {(security_id, session): iv_daily row}
    chains   {(security_id, session): [chain_expiry rows]}
    rate     {session: r_cont}
    anchors  {security_id: [tables.Anchor, ...]} (tables.event_anchors)
    """

    def __init__(self, daily: dict, chains: dict, rate: dict, sessions: calendar.Sessions,
                 p: termstructure.TermParams, anchors: dict):
        self.daily, self.chains, self.rate, self.sessions, self.p = daily, chains, rate, sessions, p
        self.anchors = anchors

    def observed(self, sid: str, d: date) -> bool:
        row = self.daily.get((sid, d))
        return row is not None and row["snapshot_status"] == "ok"

    def first_observed(self, sid: str, candidates: list[date]) -> date | None:
        return next((d for d in candidates if self.observed(sid, d)), None)

    def start_of(self, sid: str, target: date) -> date | None:
        """The last observed session at `target` or one before."""
        return self.first_observed(sid, [target, self.sessions.shift(target, -1)])

    def end_of(self, sid: str, target: date) -> date | None:
        """The first observed session at `target` or one after."""
        return self.first_observed(sid, [target, self.sessions.shift(target, 1)])

    def ok_rows(self, sid: str, d: date) -> list[dict]:
        return [r for r in self.chains.get((sid, d), []) if r["status"] == "ok"]


def forward_move(inp: EventInputs, sid: str, a: date, b: date) -> float | None:
    """ln(F_b / F_a) + r_a * (b - a).days / 365 on the shortest expiry with a forward on
    both days and tau >= 5 at b (ADR 0003 §e), or None."""
    fa = {r["expiration"]: r["forward"] for r in inp.chains.get((sid, a), []) if r["forward"] is not None}
    fb = {r["expiration"]: (r["forward"], r["tau_sessions"]) for r in inp.chains.get((sid, b), [])
          if r["forward"] is not None}
    common = sorted(e for e in fa if e in fb and fb[e][1] >= inp.p.tau_min_sessions)
    if not common:
        return None
    t = common[0]
    return math.log(fb[t][0] / fa[t]) + inp.rate[a] * (b - a).days / 365.0


def abs_move_cand_max(inp: EventInputs, sid: str, d: date) -> float | None:
    """The larger |move| over the two candidate day-0 sessions of announcement date d (label-free)."""
    s = inp.sessions
    if s.is_session(d):
        legs = [(s.prev_before(d), d), (d, s.next_after(d))]
    else:
        legs = [(s.prev_before(d), s.next_after(d))]
    moves = []
    for lo, hi in legs:
        a, b = inp.start_of(sid, lo), inp.end_of(sid, hi)
        m = None if a is None or b is None else forward_move(inp, sid, a, b)
        if m is None:
            return None
        moves.append(abs(m))
    return max(moves)


def _w_at_tau(rows: list[dict], tau: int, spans: bool, tau_min: int) -> float | None:
    """w at `tau` interpolated in tau between the usable expiries of one class (no extrapolation)."""
    ex = [termstructure.Expiry(r["expiration"], r["tau_sessions"], r["w_atm"], r["iv_atm"], bool(r["spans_next_event"]))
          for r in rows if r["tau_sessions"] >= tau_min and bool(r["spans_next_event"]) == spans]
    got = termstructure.interpolate(ex, tau, 0)
    return None if got is None else got[0]


def front_fixed(inp: EventInputs, sid: str, day0: date, pre: date, post: date) -> dict:
    """T1*, its IV at pre and post, the interpolation flag and the front crush."""
    out = {"front_fixed_expiry": None, "front_fixed_iv_m1": None, "front_fixed_iv_0": None,
           "front_fixed_interpolated": False, "crush_front_fixed": None}
    s, tau_min = inp.sessions, inp.p.tau_min_sessions
    cands = sorted(r["expiration"] for r in inp.ok_rows(sid, pre) if chain.tau_sessions(day0, r["expiration"], s)
                   >= tau_min)
    if not cands:
        return out
    t1 = cands[0]
    out["front_fixed_expiry"] = t1
    out["front_fixed_iv_m1"] = next(r["iv_atm"] for r in inp.ok_rows(sid, pre) if r["expiration"] == t1)
    tau_post = chain.tau_sessions(post, t1, s)
    if tau_post < tau_min:
        return out                         # ADR 0003 §a: followed only while tau >= 5
    listed = [r for r in inp.ok_rows(sid, post) if r["expiration"] == t1]
    if listed:
        out["front_fixed_iv_0"] = listed[0]["iv_atm"]
    else:
        nxt, _ = tables.neighbours(inp.anchors.get(sid, []), post)
        spans = nxt is not None and tables.spans(t1, nxt, s)
        w = _w_at_tau(inp.ok_rows(sid, post), tau_post, spans, tau_min)
        if w is not None and w > 0:
            out["front_fixed_iv_0"] = chain.annualised_iv(w, tau_post)
            out["front_fixed_interpolated"] = True
    if out["front_fixed_iv_0"] is not None:
        out["crush_front_fixed"] = math.log(out["front_fixed_iv_0"] / out["front_fixed_iv_m1"])
    return out


def _sigma_d2_same_pair(inp: EventInputs, sid: str, d: date, e1: date, e2: date) -> float | None:
    rows = {r["expiration"]: r for r in inp.ok_rows(sid, d)}
    if e1 not in rows or e2 not in rows:
        return None
    a, b = rows[e1], rows[e2]
    return (b["w_atm"] - a["w_atm"]) / (b["tau_sessions"] - a["tau_sessions"])


def event_row(ev, inp: EventInputs) -> tuple[dict, set]:
    """The event_iv value columns (EVENT_FIELDS) of one event, and its flags.

    `ev` is a row of the events table (attribute access).
    """
    out = {f: None for f in EVENT_FIELDS}
    out["front_fixed_interpolated"] = False
    flags: set[str] = set()
    sid, s = ev.security_id, inp.sessions
    if ev.exclusion_reason == "duplicate_row":
        return out, flags                  # not an event: another row's release
    out["abs_move_cand_max"] = abs_move_cand_max(inp, sid, ev.announce_date_used)
    if ev.day0_session is None:
        return out, flags
    pre, post = inp.start_of(sid, ev.day_m1_session), inp.end_of(sid, ev.day0_session)
    out.update(pre_session=pre, post_session=post)
    if pre is None or post is None:
        return out, flags
    out["crush_span_sessions"] = s.between(pre, post)
    if pre != ev.day_m1_session:
        flags.add("pre_is_m2")
    if post != ev.day0_session:
        flags.add("post_is_p1")

    m1, p0 = inp.daily[(sid, pre)], inp.daily[(sid, post)]
    if m1["next_event_id"] == ev.event_id:
        out.update(evar_m1=m1["event_var"], implied_move_m1=m1["implied_move"],
                   implied_abs_move_total_m1=m1["implied_abs_move_total"],
                   implied_move_status=m1["implied_move_status"], sigma_d_m1=m1["sigma_d_iv"])
    else:
        flags.add("next_event_differs")
    m2_day = s.shift(ev.day0_session, -2)
    m2 = inp.daily.get((sid, m2_day))
    if m2 is not None and m2["snapshot_status"] == "ok" and m2["next_event_id"] == ev.event_id:
        out["evar_m2"] = m2["event_var"]
    out.update(cm30_m1=m1["cm30_iv"], cm30_0=p0["cm30_iv"], ts_slope_m1=m1["ts_slope"])
    if out["cm30_m1"] is not None and out["cm30_0"] is not None:
        out["crush_mean_adj"] = math.log(out["cm30_0"] / out["cm30_m1"])
    if m1["ev_exp1"] is not None and m1["next_event_id"] == ev.event_id:
        before = _sigma_d2_same_pair(inp, sid, pre, m1["ev_exp1"], m1["ev_exp2"])
        after = _sigma_d2_same_pair(inp, sid, post, m1["ev_exp1"], m1["ev_exp2"])
        if before is not None and after is not None and before > 0 and after > 0:
            out["dsigma_d_mean_adj"] = 0.5 * math.log(after / before)
    out.update(front_fixed(inp, sid, ev.day0_session, pre, post))
    out["realized_ret_0"] = forward_move(inp, sid, pre, post)
    if out["realized_ret_0"] is not None and out["implied_abs_move_total_m1"] is not None:
        out["abs_ret_over_implied"] = abs(out["realized_ret_0"]) / out["implied_abs_move_total_m1"]
    return out, flags
