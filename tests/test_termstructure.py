# Tests for measures/termstructure.py (ADR 0003 §a-§c): the event-aware
# 21-session IV, the event variance E and the implied moves, on made-up total
# variances from the two-component model w_j = sigma_d^2 tau_j + E [spanning].
# Every expected number is worked in a comment.
#
# Mutations this module must catch (applied by hand, each seen to fail):
#   - cm30 mixing a clean and a spanning expiry (the class split removed)
#   - the "horizon holds the event" test at < 21 instead of <= 21
#   - extrapolation allowed beyond 10 sessions
#   - two_component taking sigma_d^2 from the shortest clean expiry instead of the longest
#   - E from the two LONGEST spanning expiries instead of the two shortest
#   - implied_abs_move without sqrt(2/pi)
#   - implied_abs_move_total adding the annualised sigma_d^2 (x 252) instead of the per-session one
#   - implied_move set for E <= 0 (sqrt of |E|)
#   - day_measures accepting an expiry with tau < 5 (its guard removed)
# Milestone-2 review (claim 8, mutant R4):
#   - sigma_d without E taken from the two LONGEST clean expiries instead of the two shortest
#   - sigma_d without E taken from the first and the last clean expiry

import math
from datetime import date, timedelta

import pytest

from earnings_vol.measures import termstructure as ts
from earnings_vol.measures.termstructure import Expiry

S2, E = 0.0002, 0.002          # sigma_d^2 per session, event variance
D0 = date(2026, 1, 2)          # expiration dates are labels only here


def ex(tau, spans, w=None):
    """An expiry tau sessions out; w from the two-component model unless given."""
    w = S2 * tau + (E if spans else 0.0) if w is None else w
    return Expiry(D0 + timedelta(days=tau), tau, w, math.sqrt(252 * w / tau), spans)


def test_interpolate_bracket_extrapolation_and_its_limit():
    a, b, c = ex(10, False, 0.002), ex(19, False, 0.0038), ex(35, False, 0.007)
    # Bracket 19 / 35 around 21: 0.0038 + (21 - 19)/(35 - 19) * (0.007 - 0.0038) = 0.0038 + 0.125 * 0.0032 = 0.0042.
    w, lo, hi, extrap = ts.interpolate([c, a, b], 21, 10)
    assert (w, lo.tau, hi.tau, extrap) == (pytest.approx(0.0042, abs=1e-15), 19, 35, False)
    # Below only: the line through 10 and 19, 2 sessions beyond 19: 0.0038 + 2/9 * 0.0018 = 0.0042.
    w, lo, hi, extrap = ts.interpolate([a, b], 21, 10)
    assert (w, lo.tau, hi.tau, extrap) == (pytest.approx(0.0042, abs=1e-15), 10, 19, True)
    # Above only, nearest 35 is 14 sessions away: more than 10, no value.
    assert ts.interpolate([c, ex(40, False)], 21, 10) is None
    # ... and 31 is exactly 10 away: allowed. Line through (31, 0.0062) and (40, 0.008) at 21:
    # 0.0062 + (21 - 31)/9 * 0.0018 = 0.0062 - 0.002 = 0.0042.
    w, *_ = ts.interpolate([ex(31, False), ex(40, False)], 21, 10)
    assert w == pytest.approx(0.0042, abs=1e-15)
    assert ts.interpolate([a], 21, 10) is None


def test_cm30_before_the_event_uses_spanning_expiries_only():
    # 5 sessions to day 0, so the 21-session horizon holds the event. Expiries 8, 18, 35 all span it:
    # w = 0.0002 tau + 0.002 -> 0.0036, 0.0056, 0.009. Bracket 18 / 35:
    # 0.0056 + 3/17 * 0.0034 = 0.0062 = 0.0002 * 21 + 0.002 exactly (linear inside one class).
    # cm30_iv = sqrt(252 * 0.0062 / 21) = sqrt(0.0744) = 0.2727636.
    out, flags = ts.day_measures([ex(8, True), ex(18, True), ex(35, True)], 5)
    assert out["cm30_method"] == "interp_spanning"
    assert out["cm30_iv"] == pytest.approx(0.2727636, abs=1e-7)
    assert (out["cm30_exp_lo"], out["cm30_exp_hi"]) == (D0 + timedelta(days=18), D0 + timedelta(days=35))
    assert flags == set()


def test_cm30_far_from_the_event_never_borrows_event_variance():
    # 25 sessions to day 0: the horizon does not hold it. Clean 10 and 19 (w 0.002, 0.0038), spanning 30
    # (w = 0.006 + 0.002 = 0.008). Event-aware: clean only, extrapolated 2 sessions beyond 19:
    # 0.0038 + 2/9 * 0.0018 = 0.0042 = 0.0002 * 21 (no E). cm30_iv = sqrt(252 * 0.0042 / 21) = sqrt(0.0504) = 0.2244994.
    # Blind: bracket 19 / 30: 0.0038 + 2/11 * (0.008 - 0.0038) = 0.0045636; the leak is E * 2/11 = 0.0003636
    # (ADR 0003 §b). cm30_blind_iv = sqrt(252 * 0.0045636 / 21) = sqrt(0.0547636) = 0.2340163.
    out, _ = ts.day_measures([ex(10, False), ex(19, False), ex(30, True)], 25)
    assert out["cm30_method"] == "extrap_clean"
    assert out["cm30_iv"] == pytest.approx(0.2244994, abs=1e-7)
    assert out["cm30_blind_iv"] == pytest.approx(0.2340163, abs=1e-7)
    # One spanning expiry only: E is not identified. sigma_d from the two clean ones: (0.0038 - 0.002)/9 = 0.0002,
    # sqrt(252 * 0.0002) = sqrt(0.0504) = 0.2244994.
    assert out["event_var"] is None and out["implied_move_status"] == "not_identified"
    assert out["sigma_d_iv"] == pytest.approx(0.2244994, abs=1e-7)


def test_the_horizon_holds_the_event_from_21_sessions_out():
    # At 21 sessions to day 0 the horizon (t, t + 21] holds day 0: spanning class. At 22 it does not.
    # Spanning 25 and 40 (w 0.007, 0.010); clean 10 and 19 (0.002, 0.0038).
    xs = [ex(10, False), ex(19, False), ex(25, True), ex(40, True)]
    at21, _ = ts.day_measures(xs, 21)
    at22, _ = ts.day_measures(xs, 22)
    assert at21["cm30_method"] == "extrap_spanning" and at22["cm30_method"] == "extrap_clean"
    # Spanning, 4 sessions below 25: 0.007 + (21 - 25)/15 * 0.003 = 0.0062.
    assert at21["cm30_iv"] == pytest.approx(math.sqrt(252 * 0.0062 / 21), abs=1e-12)


def test_sigma_d_without_e_comes_from_the_two_shortest_clean_expiries():
    # One spanning expiry (30, w 0.008): E is not identified, so sigma_d falls back to the clean class.
    # Clean 6, 10 and 19 with w 0.0012, 0.002 and 0.0047, so the forward variance differs by pair:
    #   two shortest (6, 10):  (0.002 - 0.0012)/4 = 0.0002 -> sigma_d_iv = sqrt(252 * 0.0002) = sqrt(0.0504) = 0.2244994
    #   two longest (10, 19):  (0.0047 - 0.002)/9 = 0.0003 -> sqrt(0.0756) = 0.2749545
    #   first and last (6, 19): (0.0047 - 0.0012)/13 = 0.0002692 -> sqrt(0.0678462) = 0.2604730
    xs = [ex(19, False, 0.0047), ex(30, True), ex(6, False, 0.0012), ex(10, False, 0.002)]
    out, flags = ts.day_measures(xs, 15)
    assert out["event_var"] is None and out["implied_move_status"] == "not_identified"
    assert out["sigma_d_iv"] == pytest.approx(0.2244994, abs=1e-7)
    assert flags == set()
    # The same with no spanning expiry at all (far from the event).
    out, _ = ts.day_measures([x for x in xs if not x.spans], 50)
    assert out["sigma_d_iv"] == pytest.approx(0.2244994, abs=1e-7)


def test_cm30_two_component_and_flat_sigma():
    # 15 sessions to day 0. One spanning expiry (30: w 0.008) and clean 6 and 10 (0.0012, 0.002).
    # two_component: sigma_d^2 from the LONGEST clean expiry, 0.002 / 10 = 0.0002; E = 0.008 - 0.0002 * 30
    # = 0.002; w* = 0.0002 * 21 + 0.002 = 0.0062. (From the 6-session one: 0.0012/6 = 0.0002 as well here,
    # so the clean w of the longest is made different below.)
    out, _ = ts.day_measures([ex(6, False, 0.0015), ex(10, False), ex(30, True)], 15)
    assert out["cm30_method"] == "two_component"
    assert out["cm30_iv"] == pytest.approx(math.sqrt(252 * 0.0062 / 21), abs=1e-12)
    assert (out["cm30_exp_lo"], out["cm30_exp_hi"]) == (D0 + timedelta(days=10), D0 + timedelta(days=30))
    # flat_sigma: far from the event, one clean expiry 15 sessions out, w 0.003: w* = 0.003 * 21/15 = 0.0042.
    out, _ = ts.day_measures([ex(15, False, 0.003), ex(40, True)], 50)
    assert out["cm30_method"] == "flat_sigma" and out["cm30_exp_lo"] == out["cm30_exp_hi"]
    assert out["cm30_iv"] == pytest.approx(math.sqrt(252 * 0.0042 / 21), abs=1e-12)
    # ... but not from 40 sessions out, 19 beyond the horizon.
    out, _ = ts.day_measures([ex(40, False)], 60)
    assert out["cm30_method"] == "none" and out["cm30_iv"] is None


def test_event_variance_and_implied_moves_hand_worked():
    # Spanning 8, 18, 35: E from the two SHORTEST, (w1 tau2 - w2 tau1)/(tau2 - tau1)
    # = (0.0036 * 18 - 0.0056 * 8)/10 = (0.0648 - 0.0448)/10 = 0.002; sigma_d^2 = 0.002/10 = 0.0002.
    # implied_move = sqrt(0.002) = 0.0447214; implied_abs_move = sqrt(2/pi) * 0.0447214 = 0.7978846 * 0.0447214
    # = 0.0356825; implied_abs_move_total = 0.7978846 * sqrt(0.002 + 0.0002) = 0.7978846 * 0.0469042 = 0.0374241.
    # (With the 3rd expiry as T2, (0.0036 * 35 - 0.009 * 8)/27 = 0.002 as well: the model is exact, so a
    # wrong pair is caught by the noisy variant below.)
    out, _ = ts.day_measures([ex(35, True), ex(8, True), ex(18, True)], 3)
    assert (out["ev_tau1"], out["ev_tau2"]) == (8, 18)
    assert out["event_var"] == pytest.approx(0.002, abs=1e-15)
    assert out["sigma_d_iv"] == pytest.approx(math.sqrt(252 * 0.0002), abs=1e-12)
    assert out["implied_move"] == pytest.approx(0.0447214, abs=1e-7)
    assert out["implied_abs_move"] == pytest.approx(0.0356825, abs=1e-7)
    assert out["implied_abs_move_total"] == pytest.approx(0.0374241, abs=1e-7)
    assert out["implied_move_status"] == "ok"
    # Off the model: the 35-session w is 0.010 instead of 0.009. The two shortest still give E = 0.002;
    # the pair (8, 35) would give (0.0036 * 35 - 0.010 * 8)/27 = (0.126 - 0.08)/27 = 0.0017037.
    out, _ = ts.day_measures([ex(8, True), ex(18, True), ex(35, True, 0.010)], 3)
    assert out["event_var"] == pytest.approx(0.002, abs=1e-15) and out["ev_exp2"] == D0 + timedelta(days=18)
    # The front expiry and the slope: front = 8, ts_slope = ln(iv8 / iv18),
    # iv8 = sqrt(252 * 0.0036/8) = 0.3367492, iv18 = sqrt(252 * 0.0056/18) = 0.2800000; ln(1.2026756) = 0.1845487.
    assert (out["front_tau"], out["front_atm_iv"]) == (8, pytest.approx(0.3367492, abs=1e-7))
    assert out["ts_slope"] == pytest.approx(0.1845487, abs=1e-7)


def test_nonpositive_event_variance_is_stored_signed_without_a_move():
    # sigma_1 <= sigma_2: tau 10 w 0.002 and tau 20 w 0.0045:
    # E = (0.002 * 20 - 0.0045 * 10)/10 = (0.04 - 0.045)/10 = -0.0005.
    out, _ = ts.day_measures([ex(10, True, 0.002), ex(20, True, 0.0045)], 2)
    assert out["event_var"] == pytest.approx(-0.0005, abs=1e-15)
    assert out["implied_move_status"] == "nonpositive_event_variance"
    assert out["implied_move"] is None and out["implied_abs_move"] is None and out["implied_abs_move_total"] is None
    # E = 0 exactly is non-positive too.
    assert ts.implied_moves(0.0, 0.0002)["implied_move_status"] == "nonpositive_event_variance"


def test_negative_forward_variance_is_flagged_not_rooted():
    # tau 10 w 0.004 > tau 20 w 0.003: sigma_d^2 = -0.0001 < 0. E = (0.004 * 20 - 0.003 * 10)/10 = 0.005 > 0,
    # implied_move = sqrt(0.005) = 0.0707107, but sigma_d_iv and implied_abs_move_total have no value.
    out, flags = ts.day_measures([ex(10, True, 0.004), ex(20, True, 0.003)], 2)
    assert flags == {"negative_forward_variance"}
    assert out["sigma_d_iv"] is None and out["implied_abs_move_total"] is None
    assert out["implied_move"] == pytest.approx(0.0707107, abs=1e-7)


def test_day_measures_refuses_unusable_expiries_and_handles_none():
    with pytest.raises(ValueError, match="usable"):
        ts.day_measures([ex(4, True)], 2)
    out, flags = ts.day_measures([], None)
    assert out["cm30_method"] == "none" and out["implied_move_status"] == "not_identified"
    assert out["front_expiry"] is None and flags == set()
