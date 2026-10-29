# Tests for measures/tables.py, measures/event_iv.py, measures/report.py and
# export/iv_view.py, and the synthetic-truth test of ADR 0001 §6: prices built
# from a two-component model with known E and sigma_d on a sparse, irregular
# strike grid, run through the whole measures path, must give back E and
# sigma_d. All values are made up.
#
# The synthetic prices come from `price76` (tests/test_iv_atom.py), a forward
# model written with scipy.stats.norm and checked there against hand-worked
# numbers. The assertions land on what the pipeline recovers, so a bug in the
# inversion, the ATM step, the clock or the E formula fails them.
#
# Mutations this module must catch (applied by hand, each seen to fail):
#   - usable expiries with tau < 5 (the 4-session expiry becoming the front)
#   - chain_rows marking spans with expiration > day 0 instead of >= (via as_of)
#   - event_anchors setting spans_from = day 0 (an expiry on an AMC announcement day classed clean;
#     milestone-2 review, claim 7)
#   - neighbours putting day 0 itself on the "next" side
#   - event_anchors keeping duplicate rows
#   - event_row without the day -2 fallback for pre
#   - event_row reading E when pre's next event is another event
#   - front_fixed extrapolating when T1* is not listed (no bracket)
#   - forward_move without the carry term, or with the end day's rate
#   - abs_move_cand_max taking the first leg only
#   - vendor_gap comparing with the session-annualised IV on the calendar line
#   - the histogram dropping the values on the last edge
#   - sqrt_mean_evar averaging E > 0 only (it must use every E, signed)

import math
from datetime import date, timedelta
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from earnings_vol.events import calendar
from earnings_vol.export import iv_view
from earnings_vol.measures import chain, event_iv, report, tables, termstructure
from test_iv_atom import price76


@pytest.fixture(scope="module")
def sessions():
    t = calendar.build_session_table(date(2025, 1, 1), date(2026, 12, 31),
                                     {"weekly_from": "2019-02-09", "mwf_from": "2020-01-06",
                                      "daily_from": "2024-09-11", "data_end": "2026-10-26"})
    return calendar.Sessions(t["session_date"].tolist())


# --- the synthetic truth --------------------------------------------------------------------

S2_TRUE, E_TRUE, R, F_TRUE = 0.00025, 0.0015, 0.04, 271.4
# A sparse grid like AAPL's (no 270 strike), about 25 strikes.
GRID = [190, 205, 215, 225, 230, 237.5, 245, 250, 255, 260, 262.5, 265, 267.5, 272.5, 275, 277.5, 280, 285, 290,
        300, 310, 320, 340, 355]


def synthetic_quotes(session: date, expiries: dict) -> dict:
    """{expiration: ExpiryQuotes} with w flat across strikes per expiry ({expiration: w})."""
    out = {}
    for exp, w in expiries.items():
        df = math.exp(-R * (exp - session).days / 365)
        rows = []
        for k in GRID:
            otm = price76(F_TRUE, k, w, df, k >= F_TRUE)
            other = otm - df * (F_TRUE - k) if k >= F_TRUE else otm + df * (F_TRUE - k)
            c, p = (otm, other) if k >= F_TRUE else (other, otm)
            rows.append((k, c - 0.01, c + 0.01, p - 0.01, p + 0.01))
        a = np.array(rows, float)
        nan = np.full(len(rows), np.nan)
        out[exp] = chain.ExpiryQuotes(a[:, 0], a[:, 1], a[:, 2], a[:, 3], a[:, 4], nan, nan)
    return out


def test_synthetic_truth_is_recovered(sessions):
    # Session Thu 2025-10-30; day 0 of the next event Fri 2025-11-07: 6 sessions away, inside the horizon.
    # Expiries: 11-05 (tau 4: Oct 31, Nov 3, 4, 5; clean, as it settles before day 0; NOT usable),
    # 11-14 (tau 11), 11-28 (tau 20), 12-19 (tau 20 + 15 = 35), all three spanning.
    # w = 0.00025 tau + 0.0015 for spanning, 0.00025 tau for clean.
    t, d0 = date(2025, 10, 30), date(2025, 11, 7)
    taus = {date(2025, 11, 5): 4, date(2025, 11, 14): 11, date(2025, 11, 28): 20, date(2025, 12, 19): 35}
    w = {e: S2_TRUE * tau + (E_TRUE if e >= d0 else 0.0) for e, tau in taus.items()}
    # Both events are AMC on a Thursday: spans_from is the Thursday, day 0 the Friday.
    anchors = [tables.Anchor(d0, "Z:2025-11-06", date(2025, 11, 6)),
               tables.Anchor(date(2026, 2, 6), "Z:2026-02-05", date(2026, 2, 5))]
    rows = tables.chain_rows("Z", t, t, False, synthetic_quotes(t, w), R, sessions, anchors[0], chain.AtomParams())
    assert [(r["expiration"], r["tau_sessions"], r["spans_next_event"]) for r in rows] == [
        (e, taus[e], e >= d0) for e in sorted(taus)]
    for r in rows:
        assert r["status"] == "ok" and r["w_atm"] == pytest.approx(w[r["expiration"]], abs=1e-12)
        assert r["forward"] == pytest.approx(F_TRUE, abs=1e-9)
    day = tables.iv_daily_row("Z", t, t, "ok", rows, anchors, sessions, termstructure.TermParams())
    assert day["sessions_to_next_event"] == 6 and day["next_event_id"] == "Z:2025-11-06"
    assert day["front_tau"] == 11                                  # the 4-session expiry is not usable
    assert day["event_var"] == pytest.approx(E_TRUE, abs=1e-9)
    assert day["sigma_d_iv"] ** 2 / 252 == pytest.approx(S2_TRUE, abs=1e-9)
    # Inside the spanning class w is linear in tau, so cm30 is exact: sqrt(252 (0.00025 * 21 + 0.0015)/21).
    assert day["cm30_method"] == "interp_spanning"
    assert day["cm30_iv"] == pytest.approx(math.sqrt(252 * (S2_TRUE * 21 + E_TRUE) / 21), abs=1e-9)
    # After the event every expiry is clean: cm30 = sigma_d,ann = sqrt(252 * 0.00025) = 0.2509980, no E.
    t2 = date(2025, 11, 10)
    w2 = {e: S2_TRUE * chain.tau_sessions(t2, e, sessions) for e in (date(2025, 11, 21), date(2025, 12, 5),
                                                                        date(2025, 12, 26))}
    rows2 = tables.chain_rows("Z", t2, t2, False, synthetic_quotes(t2, w2), R, sessions, anchors[1],
                              chain.AtomParams())
    day2 = tables.iv_daily_row("Z", t2, t2, "ok", rows2, anchors, sessions, termstructure.TermParams())
    assert day2["cm30_iv"] == pytest.approx(0.2509980, abs=1e-7) and day2["event_var"] is None
    assert day2["prev_event_id"] == "Z:2025-11-06" and day2["sessions_since_prev_event"] == 1


# --- tables ---------------------------------------------------------------------------------

def test_event_anchors_skip_duplicates_and_anchor_an_unplaced_event_on_next_d(sessions):
    ev = pd.DataFrame([
        ("Z:2025-05-01", "Z", date(2025, 5, 1), date(2025, 5, 2), None),
        ("Z:2025-04-29", "Z", date(2025, 4, 29), None, "duplicate_row"),
        # No day 0 (a NULL label on a session day): anchored on next(D) = Fri 2025-08-01.
        ("Z:2025-07-31", "Z", date(2025, 7, 31), None, "timing_not_checked"),
    ], columns=["event_id", "security_id", "announce_date_used", "day0_session", "exclusion_reason"]).astype(object)
    # spans_from is the first session on or after D: Thu 05-01 and Thu 07-31 (see the next test).
    assert tables.event_anchors(ev, sessions) == {"Z": [(date(2025, 5, 2), "Z:2025-05-01", date(2025, 5, 1)),
                                                        (date(2025, 8, 1), "Z:2025-07-31", date(2025, 7, 31))]}


def test_an_expiry_on_an_amc_announcement_day_spans_the_event(sessions):
    # ADR 0003 §b (milestone-2 review, claim 7). Three releases of one company, each a different case:
    #   AMC Thu 2025-05-01: day 0 Fri 05-02, spans_from Thu 05-01 (exercise is decided until 5:30 p.m.,
    #                       after the release, so the 05-01 expiry holds the news);
    #   BMO Thu 2025-07-31: day 0 = spans_from = Thu 07-31;
    #   Sat 2025-11-01:     not a session, day 0 Mon 11-03 = spans_from (a Friday 10-31 expiry is clean).
    ev = pd.DataFrame([
        ("Z:2025-05-01", "Z", date(2025, 5, 1), date(2025, 5, 2), None),
        ("Z:2025-07-31", "Z", date(2025, 7, 31), date(2025, 7, 31), None),
        ("Z:2025-11-01", "Z", date(2025, 11, 1), date(2025, 11, 3), None),
    ], columns=["event_id", "security_id", "announce_date_used", "day0_session", "exclusion_reason"]).astype(object)
    amc, bmo, weekend = tables.event_anchors(ev, sessions)["Z"]
    assert amc == (date(2025, 5, 2), "Z:2025-05-01", date(2025, 5, 1))
    assert bmo == (date(2025, 7, 31), "Z:2025-07-31", date(2025, 7, 31))
    assert weekend == (date(2025, 11, 3), "Z:2025-11-01", date(2025, 11, 3))
    # Session Mon 2025-04-21 before the AMC event. Expiries Wed 04-30 (tau: 04-22..04-30 = 7), Thu 05-01
    # (the announcement day, tau 8) and Fri 05-02 (day 0, tau 9). Only 04-30 is clean; with spans_from =
    # day 0 (the rule before the review) 05-01 would be clean too.
    t = date(2025, 4, 21)
    w = {date(2025, 4, 30): 0.002, date(2025, 5, 1): 0.004, date(2025, 5, 2): 0.0045}
    rows = tables.chain_rows("Z", t, t, False, synthetic_quotes(t, w), R, sessions, amc, chain.AtomParams())
    assert [(r["expiration"], r["tau_sessions"], r["spans_next_event"]) for r in rows] == [
        (date(2025, 4, 30), 7, False), (date(2025, 5, 1), 8, True), (date(2025, 5, 2), 9, True)]
    # The same three expiries against the BMO and the weekend anchors.
    assert [tables.spans(e, bmo, sessions) for e in sorted(w)] == [False, False, False]   # all before 07-31
    assert tables.spans(date(2025, 7, 31), bmo, sessions) and not tables.spans(date(2025, 7, 30), bmo, sessions)
    assert not tables.spans(date(2025, 10, 31), weekend, sessions)
    assert tables.spans(date(2025, 11, 3), weekend, sessions)


def test_neighbours_put_day_0_on_the_previous_side():
    a = [(date(2025, 5, 2), "A"), (date(2025, 8, 1), "B")]
    assert tables.neighbours(a, date(2025, 5, 1)) == ((date(2025, 5, 2), "A"), None)
    assert tables.neighbours(a, date(2025, 5, 2)) == ((date(2025, 8, 1), "B"), (date(2025, 5, 2), "A"))
    assert tables.neighbours(a, date(2025, 9, 1)) == (None, (date(2025, 8, 1), "B"))


def test_chain_rows_skip_dead_expiries_and_mark_spans_and_staleness(sessions):
    # Session Thu 2025-04-17. Expiries 04-17 (today: no row), 04-18 (Good Friday: as_of = 04-17, tau 0: no
    # row), 04-25 (tau: 04-21..04-25 = 5), 05-16. Next event day 0 Fri 04-25: the 04-25 expiry settles at
    # day 0's close, so it spans (>=); 05-16 spans too.
    t = date(2025, 4, 17)
    w = {date(2025, 4, 17): 0.001, date(2025, 4, 18): 0.001, date(2025, 4, 25): 0.003, date(2025, 5, 16): 0.006}
    rows = tables.chain_rows("Z", t, t, False, synthetic_quotes(t, w), R, sessions,
                             tables.Anchor(date(2025, 4, 25), "Z:x", date(2025, 4, 25)), chain.AtomParams())
    assert [(r["expiration"], r["tau_sessions"], r["tau_cal_days"], r["spans_next_event"]) for r in rows] == [
        (date(2025, 4, 25), 5, 8, True), (date(2025, 5, 16), 20, 29, True)]
    assert rows[0]["df"] == pytest.approx(math.exp(-0.04 * 8 / 365), abs=1e-15)
    stale = tables.chain_rows("Z", t, t, True, synthetic_quotes(t, w), R, sessions, None, chain.AtomParams())
    assert {r["status"] for r in stale} == {"stale"} and {r["spans_next_event"] for r in stale} == {None}


def test_iv_daily_row_uses_ok_rows_with_tau_at_least_5(sessions):
    base = {"forward": 100.0, "spans_next_event": True}
    rows = [{"expiration": date(2025, 6, 6), "tau_sessions": 4, "status": "ok", "w_atm": 0.002, "iv_atm": 0.35, **base},
            {"expiration": date(2025, 6, 13), "tau_sessions": 9, "status": "no_atm", "w_atm": None, "iv_atm": None,
             **base},
            {"expiration": date(2025, 6, 20), "tau_sessions": 14, "status": "ok", "w_atm": 0.004, "iv_atm": 0.27, **base}]
    anchors = [tables.Anchor(date(2025, 6, 4), "Z:a", date(2025, 6, 4))]
    day = tables.iv_daily_row("Z", date(2025, 6, 2), date(2025, 6, 2), "ok", rows, anchors, sessions,
                              termstructure.TermParams())
    assert day["front_expiry"] == date(2025, 6, 20) and day["event_var"] is None   # one usable spanning expiry
    missing = tables.iv_daily_row("Z", date(2025, 6, 2), None, "missing", [], anchors, sessions,
                                  termstructure.TermParams())
    assert missing["cm30_iv"] is None and missing["cm30_method"] == "none" and missing["sessions_to_next_event"] == 2


# --- event_iv on made-up rows ---------------------------------------------------------------

def crow(exp, tau, w, iv, fwd=None, spans=False):
    return {"expiration": exp, "tau_sessions": tau, "status": "ok", "w_atm": w, "iv_atm": iv, "forward": fwd,
            "spans_next_event": spans}


def drow(status="ok", nxt="Z:2025-01-16", **kw):
    base = {"snapshot_status": status, "next_event_id": nxt, "event_var": None, "implied_move": None,
            "implied_abs_move_total": None, "implied_move_status": "not_identified", "sigma_d_iv": None,
            "cm30_iv": None, "ts_slope": None, "ev_exp1": None, "ev_exp2": None, "sessions_to_next_event": 60}
    return {**base, **kw}


EV = SimpleNamespace(event_id="Z:2025-01-16", security_id="Z", announce_date_used=date(2025, 1, 16),
                     day_m1_session=date(2025, 1, 16), day0_session=date(2025, 1, 17), exclusion_reason=None)
J15, J16, J17 = date(2025, 1, 15), date(2025, 1, 16), date(2025, 1, 17)
E24, E28, E31, F07, F21 = (date(2025, 1, 24), date(2025, 1, 28), date(2025, 1, 31), date(2025, 2, 7),
                           date(2025, 2, 21))


# The anchors of EV (AMC Thu 01-16) and of the next release (BMO Tue 04-15, 60 sessions after 01-17).
ANCHORS = {"Z": [tables.Anchor(J17, "Z:2025-01-16", J16),
                 tables.Anchor(date(2025, 4, 15), "Z:2025-04-15", date(2025, 4, 15))]}


def inputs(sessions, daily, chains, rate=None):
    rate = rate or {d: 0.0365 for d in (J15, J16, J17, date(2025, 1, 21))}
    return event_iv.EventInputs(daily, chains, rate, sessions, termstructure.TermParams(), ANCHORS)


def test_event_row_falls_back_to_day_minus_2_and_interpolates_the_front_expiry(sessions):
    # AMC Thu 01-16: day -1 = 01-16 (no snapshot here), day 0 = Fri 01-17. pre = 01-15 (day -2), post = 01-17.
    daily = {("Z", J15): drow(event_var=0.003, implied_move=math.sqrt(0.003), implied_move_status="ok",
                              cm30_iv=0.40, ev_exp1=E24, ev_exp2=E31),
             ("Z", J16): drow(status="missing"),
             ("Z", J17): drow(nxt="Z:2025-04-15", cm30_iv=0.32, sessions_to_next_event=60)}
    # T1* = the shortest pre expiry with tau >= 5 after day 0: 01-24 has (01-17, 01-24] = 01-21..24 = 4
    # (MLK day 01-20 closed), too few; 01-31 has 4 + 5 = 9: T1* = 01-31, IV 0.50 at pre.
    # At post the vendor lists 01-28 (tau 6) and 02-07 (tau 14), not 01-31 (tau 9): interpolated
    # w = 0.006 + (9 - 6)/(14 - 6) * (0.010 - 0.006) = 0.0075, IV sqrt(252 * 0.0075 / 9) = sqrt(0.21) = 0.4582576;
    # crush_front_fixed = ln(0.4582576 / 0.50) = ln(0.9165151) = -0.0871767.
    chains = {("Z", J15): [crow(E24, 6, 0.004, 0.52, 100.0, True), crow(E31, 11, 0.007, 0.50, 100.0, True),
                           crow(F21, 26, 0.012, 0.34, 100.0, True)],
              ("Z", J17): [crow(E28, 6, 0.006, 0.50, 103.0), crow(F07, 14, 0.010, 0.42, 103.0),
                           crow(F21, 24, 0.011, 0.34, 103.0)]}
    # The rate differs by day (made up), so the carry must take the START day's.
    row, flags = event_iv.event_row(EV, inputs(sessions, daily, chains, {J15: 0.0365, J17: 0.0730}))
    assert flags == {"pre_is_m2"}
    assert (row["pre_session"], row["post_session"], row["crush_span_sessions"]) == (J15, J17, 2)
    assert row["evar_m1"] == 0.003 and row["evar_m2"] == 0.003           # day -2 is 01-15 itself
    # crush ln(0.32/0.40) = ln(0.8) = -0.2231436.
    assert row["crush_mean_adj"] == pytest.approx(-0.2231436, abs=1e-7)
    assert row["front_fixed_expiry"] == E31 and row["front_fixed_interpolated"]
    assert row["front_fixed_iv_0"] == pytest.approx(0.4582576, abs=1e-7)
    assert row["crush_front_fixed"] == pytest.approx(-0.0871767, abs=1e-7)
    # Realised: the only expiry with a forward on both days is 02-21 (tau 24 >= 5 at post):
    # ln(103/100) + 0.0365 * 2/365 = 0.0295588 + 0.0002 = 0.0297588 (the rate of the START day, 01-15;
    # 01-17's 0.073 would give 0.0299588).
    assert row["realized_ret_0"] == pytest.approx(0.0297588, abs=1e-7)
    # E's pair 01-24 / 01-31 is not listed at post: no dsigma.
    assert row["dsigma_d_mean_adj"] is None


def test_event_row_reads_no_e_when_pre_belongs_to_another_event(sessions):
    daily = {("Z", J16): drow(nxt="Z:other", event_var=0.003, cm30_iv=0.40), ("Z", J17): drow(cm30_iv=0.32)}
    row, flags = event_iv.event_row(EV, inputs(sessions, daily, {}))
    assert row["evar_m1"] is None and "next_event_differs" in flags
    assert row["crush_mean_adj"] == pytest.approx(math.log(0.8), abs=1e-12)


def test_front_fixed_never_extrapolates(sessions):
    # As above, but at post only 02-07 (14) and 02-21 (24): tau 9 lies below both, no bracket, no value.
    daily = {("Z", J16): drow(cm30_iv=0.40), ("Z", J17): drow(nxt="Z:2025-04-15", cm30_iv=0.32)}
    chains = {("Z", J16): [crow(E31, 10, 0.007, 0.50, 100.0, True)],
              ("Z", J17): [crow(F07, 14, 0.010, 0.42, 103.0), crow(F21, 24, 0.011, 0.34, 103.0)]}
    row, _ = event_iv.event_row(EV, inputs(sessions, daily, chains))
    assert row["front_fixed_iv_m1"] == 0.50 and row["front_fixed_iv_0"] is None and row["crush_front_fixed"] is None


def test_abs_move_cand_max_takes_the_larger_of_the_two_legs(sessions):
    # D = Thu 01-16, all three days observed, forwards of 02-21: 100, 101, 99.
    # prev(D) -> D: ln(101/100) + 0.0365/365 = 0.0099503 + 0.0001 = 0.0100503
    # D -> next(D): ln(99/101) + 0.0365/365 = -0.0200007 + 0.0001 = -0.0199007 -> |.| = 0.0199007 (the max).
    daily = {("Z", d): drow() for d in (J15, J16, J17)}
    chains = {("Z", d): [crow(F21, 25, 0.01, 0.3, f)] for d, f in ((J15, 100.0), (J16, 101.0), (J17, 99.0))}
    inp = inputs(sessions, daily, chains)
    assert event_iv.abs_move_cand_max(inp, "Z", J16) == pytest.approx(0.0199007, abs=1e-7)
    # A Saturday D (01-18): one move, prev(D) = 01-17 -> next(D) = Tue 01-21 (MLK day closed), unobserved here.
    assert event_iv.abs_move_cand_max(inp, "Z", date(2025, 1, 18)) is None
    # With 01-21 observed (forward 97): |ln(97/99) + 0.0365 * 4/365| = |-0.0204089 + 0.0004| = 0.0200089.
    daily[("Z", date(2025, 1, 21))] = drow()
    chains[("Z", date(2025, 1, 21))] = [crow(F21, 23, 0.01, 0.3, 97.0)]
    assert event_iv.abs_move_cand_max(inputs(sessions, daily, chains), "Z", date(2025, 1, 18)) == pytest.approx(
        0.0200089, abs=1e-7)
    # A duplicate row has no measures at all.
    dup = SimpleNamespace(**{**vars(EV), "exclusion_reason": "duplicate_row"})
    assert event_iv.event_row(dup, inp)[0]["abs_move_cand_max"] is None


# --- report.vendor_gap ----------------------------------------------------------------------

def test_vendor_gap_on_non_event_days():
    # Two front rows on non-event days, one on day -1 (left out).
    # Row a: w 0.0036, 15 calendar days: calendar IV sqrt(365 * 0.0036/15) = sqrt(0.0876) = 0.2959730;
    #        vendor 0.2930 -> -0.0029730 (-0.2972972 points); session IV 0.30 -> -0.0070.
    # Row b: w 0.0040, 14 days: sqrt(365 * 0.004/14) = sqrt(0.1042857) = 0.3229330; vendor 0.3250 -> +0.0020670
    #        (+0.2067013 points).
    iv = pd.DataFrame({"security_id": ["Z", "Z", "Z"], "session_date": [date(2025, 3, 3), date(2025, 3, 4),
                                                                        date(2025, 3, 5)],
                       "snapshot_status": ["ok"] * 3, "front_expiry": [date(2025, 3, 18), date(2025, 3, 18),
                                                                      date(2025, 3, 18)],
                       "sessions_to_next_event": pd.Series([30, 29, 1], dtype=object),
                       "sessions_since_prev_event": pd.Series([20, 21, 50], dtype=object)})
    ce = pd.DataFrame({"security_id": ["Z"] * 3, "session_date": iv["session_date"],
                       "expiration": [date(2025, 3, 18)] * 3, "atm_method": ["bracket_linear"] * 3,
                       "vendor_iv_atm": [0.2930, 0.3250, 0.9], "w_atm": [0.0036, 0.0040, 0.0040],
                       "tau_cal_days": [15, 14, 13], "iv_atm": [0.30, 0.31, 0.40]})
    got = report.vendor_gap(ce, iv)
    cal = got["calendar_clock"]
    assert cal["n"] == 2
    # mean of -0.2972972 and +0.2067013 points = -0.0452980; |.| median (0.2972972 + 0.2067013)/2 = 0.2519992.
    assert cal["mean_vol_pts"] == pytest.approx(-0.0452980, abs=1e-6)
    assert cal["median_abs_vol_pts"] == pytest.approx(0.2519992, abs=1e-6)
    assert cal["share_vendor_below"] == 0.5
    # Session clock: 0.2930 - 0.30 = -0.70 points, 0.3250 - 0.31 = +1.50: mean +0.40.
    assert got["session_clock"]["mean_vol_pts"] == pytest.approx(0.40, abs=1e-9)


# --- export/iv_view -------------------------------------------------------------------------

def test_histogram_and_quantiles_hand_worked():
    # Width 0.005: min 0.012 -> lower edge 0.010, max 0.030 -> upper edge 0.030 exactly (a value on the last
    # edge belongs to the last bin). Bins [0.010, 0.015), [0.015, 0.020), [0.020, 0.025), [0.025, 0.030].
    vals = np.array([0.012, 0.016, 0.019, 0.025, 0.030])
    h = iv_view.histogram(vals, 0.005, 5)
    assert h == {"bin_edges": [0.01, 0.015, 0.02, 0.025, 0.03], "counts": [1, 2, 0, 2]}
    # Quantiles (linear): p50 = 0.019; p25 at position 1 = 0.016; p90 at 3.6 = 0.025 + 0.6 * 0.005 = 0.028.
    q = iv_view.quantiles(vals, 5)
    assert (q["p25"], q["p50"], q["p90"]) == (0.016, 0.019, 0.028)
    assert iv_view.histogram(np.array([]), 0.005, 5) == {"bin_edges": [], "counts": []}


def test_iv_view_counts_nonpositive_e_and_averages_in_variance_space():
    # Three events: E = 0.0016 (move 0.04), E = 0.0004 (move 0.02), E = -0.0002 (no move); one event not in
    # the primary sample. sqrt(mean E) over all three = sqrt((0.0016 + 0.0004 - 0.0002)/3) = sqrt(0.0006)
    # = 0.0244949, exported at 5 dp as 0.02449 (never the mean of the two moves, 0.03).
    eiv = pd.DataFrame({"event_id": ["a", "b", "c", "x"], "evar_m1": [0.0016, 0.0004, -0.0002, 0.09],
                        "implied_move_m1": [0.04, 0.02, None, 0.3], "crush_mean_adj": [-0.2, -0.1, None, -0.9]})
    out = iv_view.iv_measures_data(pd.DataFrame({"event_id": ["a", "b", "c"]}), eiv, {})
    im = out["implied_move"]
    assert (im["n_identified"], im["n_nonpositive"], im["n"]) == (3, 1, 2)
    assert im["sqrt_mean_evar"] == 0.02449
    assert sum(im["counts"]) == 2 and out["crush"]["n"] == 2 and out["crush"]["mean"] == -0.15
    assert out["sample"]["n_events"] == 3
