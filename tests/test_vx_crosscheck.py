# Tests for src/earnings_vol/stats/vx_crosscheck.py, the pure statistics of the Cboe VX* cross-check
# (docs/validation/vx-preregistration.md; decisions D1-D12 in docs/validation/vx-ledger.md).
#
# Every value here is made up. No Cboe number, no volatility_history number and no number of our real series
# appears in this file. Expected values are worked out by hand in the comments, or come from an independent oracle
# (numpy's corrcoef, polyfit and median on the repeated sample), never from the code under test.
#
# Mutations this module must catch (each applied by hand to the module, the test seen to fail, the file restored and
# its SHA-256 compared; the list and the runs are in docs/validation/vx-ledger.md §4, script
# docs/validation/probes/vx/mutants.py):
#   - V01 on_grid accepting a date that is not a session (silently dropped)
#   - V02 shift moving the wrong way (out[i] = values[i - lag])
#   - V03 matched_changes keeping a value of 0 (log of 0)
#   - V04 primary taking gap <= 2
#   - V05 block_counts circular (starts on [0, n)) instead of [0, n - block]
#   - V06 block_counts not cutting the joined blocks to n sessions
#   - V07 moment_stats' slope as cov / var(y) (the reverse slope)
#   - V08 weighted_median taking the lower middle value for an even total
#   - V09 spread_stats measuring each year against the mean, not the median, of all days
#   - V10 crush_ratio as the mean of the per-event ratios
#   - V11 verdict_bar_i passing r = 0.8 itself (>= instead of >)
#   - V12 verdict_bar_iv with the range [0.8, 1.25]
#   - V13 lag_finding reporting a tie with lag 0 as a finding
#   - V14 iv_at_horizon without the extrapolation limit
#   - V15 identify_maturity accepting a minimum on the longest horizon
#   - V16 percentile_ci keeping NaN replicates (np.percentile of NaN)
#   - V17 event_bootstrap_ratio dividing the mean ratio of each draw the other way round
#   - V18 verdict_bar_iii failing a deviation of exactly 2.0
#   - V19 bar_iv_provisional dropping the caveat while some (not all) events are still not_checked
#   (E01-E09, the exploratory functions at the end of the module, are listed in docs/validation/vx-ledger.md §9)

import math
from datetime import date

import numpy as np
import pandas as pd
import pytest

from earnings_vol.measures import termstructure
from earnings_vol.stats import vx_crosscheck as vx

D = [date(2030, 1, 2), date(2030, 1, 3), date(2030, 1, 6), date(2030, 1, 7)]


class FixedRng:
    """A stand-in for numpy's Generator: integers() returns the given array and records its arguments."""

    def __init__(self, values):
        self.values = np.asarray(values)
        self.calls = []

    def integers(self, low, high, size):
        self.calls.append((low, high, size))
        assert tuple(size) == self.values.shape
        return self.values


# --- the grid and the changes ------------------------------------------------------------------------------

def test_on_grid_places_values_and_refuses_strangers():
    g = vx.on_grid([D[2], D[0]], [0.3, 0.2], D)
    assert np.isnan(g[1]) and np.isnan(g[3])
    assert (g[0], g[2]) == (0.2, 0.3)
    with pytest.raises(ValueError, match="not a session"):
        vx.on_grid([date(2030, 1, 4)], [0.2], D)             # a Saturday
    with pytest.raises(ValueError, match="two values"):
        vx.on_grid([D[1], D[1]], [0.2, 0.3], D)


def test_shift_moves_cboe_by_whole_sessions():
    v = np.array([1.0, 2.0, 3.0, 4.0])
    # lag +1: our session i meets Cboe's session i + 1
    np.testing.assert_array_equal(vx.shift(v, 1), [2.0, 3.0, 4.0, np.nan])
    np.testing.assert_array_equal(vx.shift(v, -1), [np.nan, 1.0, 2.0, 3.0])
    np.testing.assert_array_equal(vx.shift(v, 0), v)


def test_matched_changes_worked_example():
    # The module header's example: ours 0.20, 0.22, -, 0.21; VX 0.25, 0.26, 0.27, 0.24.
    # M = {0, 1, 3}: a primary change 0 -> 1 and a secondary one 1 -> 3 (gap 2).
    ch = vx.matched_changes(np.array([0.20, 0.22, np.nan, 0.21]), np.array([0.25, 0.26, 0.27, 0.24]))
    assert ch["start"].tolist() == [0, 1] and ch["end"].tolist() == [1, 3] and ch["gap"].tolist() == [1, 2]
    assert ch["d_ours"].tolist() == pytest.approx([math.log(1.1), math.log(0.21 / 0.22)], abs=1e-15)
    assert ch["d_vx"].tolist() == pytest.approx([math.log(1.04), math.log(0.24 / 0.26)], abs=1e-15)
    assert vx.primary(ch)["end"].tolist() == [1]
    assert vx.secondary(ch)["end"].tolist() == [3]


def test_a_zero_or_missing_value_is_not_a_member_of_m():
    # ours 0.2, 0.0, 0.25: the zero is not a value (no log), so the only change is 0 -> 2 with gap 2
    ch = vx.matched_changes(np.array([0.2, 0.0, 0.25]), np.array([0.3, 0.3, 0.3]))
    assert ch["gap"].tolist() == [2]
    assert vx.primary(ch).empty


def test_primary_is_gap_one_only():
    ch = pd.DataFrame({"gap": [1, 2, 3, 1]})
    assert vx.primary(ch).index.tolist() == [0, 3]
    assert vx.secondary(ch).index.tolist() == [1, 2]


# --- the moving-block bootstrap ------------------------------------------------------------------------------

def test_block_counts_joins_blocks_and_cuts_to_n():
    # n = 5, block 2: ceil(5/2) = 3 blocks, starts drawn on [0, 5 - 2] (integers' high is exclusive: 4).
    # Starts 0, 3, 1 give sessions 0 1 | 3 4 | 1 2, cut to five: 0 1 3 4 1 -> counts 1, 2, 0, 1, 1.
    rng = FixedRng([[0, 3, 1]])
    c = vx.block_counts(5, 2, 1, rng)
    assert rng.calls == [(0, 4, (1, 3))]
    assert c.tolist() == [[1, 2, 0, 1, 1]]


def test_block_counts_rows_sum_to_n_and_a_whole_block_is_every_session_once():
    c = vx.block_counts(23, 5, 50, np.random.default_rng(1))
    assert c.shape == (50, 23) and (c.sum(axis=1) == 23).all()
    assert (vx.block_counts(7, 7, 3, np.random.default_rng(2)) == 1).all()   # one block: the whole series
    with pytest.raises(ValueError):
        vx.block_counts(5, 6, 1, np.random.default_rng(3))


def test_moment_stats_point_estimate_by_hand():
    # x 1 2 3 4, y 2 4 5 9: dx -1.5 -0.5 0.5 1.5, dy -3 -1 0 4.
    # Sxy = 4.5 + 0.5 + 0 + 6 = 11, Sxx = 5, Syy = 26.
    # slope (y on x) = 11/5 = 2.2; reverse (x on y) = 11/26; r = 11/sqrt(130).
    sums = vx.session_sums(np.arange(4), np.array([1.0, 2, 3, 4]), np.array([2.0, 4, 5, 9]), 4)
    m = vx.moment_stats(sums)
    assert m["n"][0] == 4
    assert m["slope"][0] == pytest.approx(2.2, abs=1e-12)
    assert m["reverse"][0] == pytest.approx(11 / 26, abs=1e-12)
    assert m["r"][0] == pytest.approx(11 / math.sqrt(130), abs=1e-12)


def test_moment_stats_weights_are_repeated_sessions():
    # Two names on three sessions; session counts (2, 0, 1) repeat every observation of session 0 twice and drop
    # session 1. The oracle is numpy on the repeated sample.
    pos = np.array([0, 0, 1, 1, 2, 2])
    x = np.array([0.01, -0.02, 0.03, 0.00, -0.01, 0.02])
    y = np.array([0.02, -0.01, 0.05, -0.01, -0.02, 0.01])
    m = vx.moment_stats(vx.session_sums(pos, x, y, 3), np.array([[2, 0, 1]]))
    keep = np.repeat(np.arange(6), [2, 2, 0, 0, 1, 1])
    xr, yr = x[keep], y[keep]
    assert m["n"][0] == 6
    assert m["r"][0] == pytest.approx(np.corrcoef(xr, yr)[0, 1], abs=1e-12)
    assert m["slope"][0] == pytest.approx(np.polyfit(xr, yr, 1)[0], abs=1e-12)
    assert m["reverse"][0] == pytest.approx(np.polyfit(yr, xr, 1)[0], abs=1e-12)
    # no observation drawn: undefined, not an error
    assert np.isnan(vx.moment_stats(vx.session_sums(pos, x, y, 3), np.array([[0, 0, 0]]))["r"][0])


def test_weighted_mean_counts_sessions():
    # values 1, 3 on session 0 and 10 on session 1; counts (1, 2): (1 + 3 + 2 * 10) / 4 = 6
    assert vx.weighted_mean(np.array([0, 0, 1]), np.array([1.0, 3.0, 10.0]), 2, np.array([[1, 2]]))[0] == 6.0
    assert vx.weighted_mean(np.array([0, 0, 1]), np.array([1.0, 3.0, 10.0]), 2)[0] == pytest.approx(14 / 3)


def test_weighted_median_is_the_median_of_the_repeated_sample():
    v = np.array([5.0, 1.0, 3.0, 2.0])
    w = np.array([[1, 1, 1, 1],      # 1 2 3 5 -> (2 + 3) / 2 = 2.5
                  [0, 2, 1, 0],      # 1 1 3 -> 1
                  [3, 0, 0, 1],      # 2 5 5 5 -> 5
                  [0, 0, 0, 0]])     # nothing -> NaN
    out = vx.weighted_median(v, w)
    assert out[:3].tolist() == [2.5, 1.0, 5.0] and np.isnan(out[3])
    rng = np.random.default_rng(7)
    for _ in range(25):
        vals = rng.normal(size=9)
        ws = rng.integers(0, 4, size=(1, 9))
        if ws.sum():
            assert vx.weighted_median(vals, ws)[0] == np.median(np.repeat(vals, ws[0]))


def test_percentile_ci_drops_and_counts_undefined_replicates():
    vals = np.append(np.arange(101, dtype=float), [np.nan, np.inf])
    lo, hi, dropped = vx.percentile_ci(vals)
    assert (lo, hi, dropped) == (2.5, 97.5, 2)
    lo, hi, dropped = vx.percentile_ci(np.array([np.nan]))
    assert math.isnan(lo) and math.isnan(hi) and dropped == 1


# --- bar iii ------------------------------------------------------------------------------------------------

def test_spread_stats_point_and_weighted():
    # 2020: 3 4 5 (median 4); 2021: 10 -1 2 (median 2); all days -1 2 3 4 5 10: median 3.5.
    # |4 - 3.5| = 0.5, |2 - 3.5| = 1.5: the largest deviation is 1.5. Five of six spreads are above 0.
    s = np.array([3.0, 4.0, 5.0, 10.0, -1.0, 2.0])
    yrs = np.array([2020, 2020, 2020, 2021, 2021, 2021])
    pt = vx.spread_stats(s, yrs)
    assert pt["median"][0] == 3.5 and pt["max_abs_dev"][0] == 1.5
    assert pt["years"][2020][0] == 4.0 and pt["years"][2021][0] == 2.0
    assert pt["share_above"][0] == pytest.approx(5 / 6)
    # a replicate that draws only the three 2020 sessions: all-days median 4, 2021 undefined, deviation 0
    bt = vx.spread_stats(s, yrs, np.arange(6), np.array([[1, 1, 1, 0, 0, 0]]))
    assert bt["median"][0] == 4.0 and np.isnan(bt["years"][2021][0]) and bt["max_abs_dev"][0] == 0.0
    assert bt["share_above"][0] == 1.0
    # without years: the median and the share only
    assert vx.spread_stats(s)["years"] == {}


# --- bar iv -------------------------------------------------------------------------------------------------

def test_crush_ratio_is_a_ratio_of_means():
    # means -0.2 and -0.25: R = 0.8 (the mean of the per-event ratios would be (0.4 + 1.2) / 2 = 0.8 too, so the
    # second case tells them apart: means -0.2 / -0.2 = 1, per-event ratios (1/3 + 3) / 2 = 1.667)
    assert vx.crush_ratio(np.array([-0.1, -0.3]), np.array([-0.25, -0.25])) == pytest.approx(0.8)
    assert vx.crush_ratio(np.array([-0.1, -0.3]), np.array([-0.3, -0.1])) == pytest.approx(1.0)
    assert math.isnan(vx.crush_ratio(np.array([-0.1, 0.1]), np.array([0.2, -0.2])))


def test_event_bootstrap_resamples_whole_events():
    # draws (0, 0), (1, 1), (0, 1): ratios -0.1/-0.3, -0.3/-0.1, -0.2/-0.2
    rng = FixedRng([[0, 0], [1, 1], [0, 1]])
    out = vx.event_bootstrap_ratio(np.array([-0.1, -0.3]), np.array([-0.3, -0.1]), 3, rng)
    assert out.tolist() == pytest.approx([1 / 3, 3.0, 1.0])
    assert rng.calls == [(0, 2, (3, 2))]


# --- verdicts -----------------------------------------------------------------------------------------------

def test_verdicts_at_their_boundaries():
    assert vx.verdict_bar_i(0.8) == "fail" and vx.verdict_bar_i(0.8001) == "pass"
    assert vx.verdict_bar_i(float("nan")) == "not computable"
    assert vx.holds(0.7, 1.0) and not vx.holds(0.7, 0.99) and vx.holds(1.0, 1.3)
    assert vx.verdict_bar_iii(2.0) == "pass" and vx.verdict_bar_iii(2.001) == "fail"
    assert vx.verdict_bar_iv(0.8) == "pass" and vx.verdict_bar_iv(1.2) == "pass"
    assert vx.verdict_bar_iv(0.799) == "fail" and vx.verdict_bar_iv(1.201) == "fail"
    assert vx.verdict_bar_iv(float("nan")) == "not computable"


def test_bar_iv_provisional_follows_the_timing_labels():
    assert vx.bar_iv_provisional({"not_checked": 3}).startswith("Bar iv is provisional")
    assert "for every one of these events" in vx.bar_iv_provisional({"not_checked": 3})
    assert "for 1 of the 4 events" in vx.bar_iv_provisional({"not_checked": 1, "confirmed": 3})
    # once no event is not_checked, the caveat goes
    done = vx.bar_iv_provisional({"confirmed": 3, "corrected": 1})
    assert "provisional" not in done and "every one of the 4 events has a checked timing label" in done


def test_lag_finding():
    assert vx.lag_finding({-1: 0.1, 0: 0.8, 1: 0.05}) == {
        "highest_lag": 0, "lags_above_lag0": [], "finding": "lag 0 has the highest correlation"}
    f = vx.lag_finding({-1: 0.85, 0: 0.8, 1: 0.2})
    assert f["highest_lag"] == -1 and f["lags_above_lag0"] == [-1] and f["finding"] == "lag -1 is higher than lag 0"
    # a tie with lag 0 is not a finding
    assert vx.lag_finding({-1: 0.8, 0: 0.8, 1: 0.1})["lags_above_lag0"] == []


# --- §5: the maturity ---------------------------------------------------------------------------------------

E = termstructure.Expiry


def test_iv_at_horizon_interpolates_like_cm30_blind():
    ex = [E(date(2030, 2, 1), 10, 0.004, 0.3, False), E(date(2030, 3, 1), 30, 0.010, 0.3, True)]
    # h = 21: w = 0.004 + (21 - 10) / 20 * 0.006 = 0.0073; IV = sqrt(252 * 0.0073 / 21) = sqrt(0.0876)
    assert vx.iv_at_horizon(ex, 21, 10) == pytest.approx(math.sqrt(0.0876), abs=1e-15)
    assert vx.iv_at_horizon(ex, 21, 10) == math.sqrt(252 * termstructure._blind(ex, termstructure.TermParams()) / 21)
    # h = 38: 8 sessions beyond the longest expiry (allowed): w = 0.004 + 28 / 20 * 0.006 = 0.0124
    assert vx.iv_at_horizon(ex, 38, 10) == pytest.approx(math.sqrt(252 * 0.0124 / 38), abs=1e-15)
    # h = 42: 12 sessions beyond it, over the limit of 10
    assert vx.iv_at_horizon(ex, 42, 10) is None
    # one expiry: flat sigma within 10 sessions, w = 0.006 * 21 / 15 = 0.0084, IV = sqrt(0.1008)
    one = [E(date(2030, 2, 1), 15, 0.006, 0.3, False)]
    assert vx.iv_at_horizon(one, 21, 10) == pytest.approx(math.sqrt(0.1008), abs=1e-15)
    assert vx.iv_at_horizon(one, 30, 10) is None
    # a negative interpolated variance gives no IV
    assert vx.iv_at_horizon([E(date(2030, 2, 1), 10, 0.004, 0.3, False),
                             E(date(2030, 3, 1), 20, 0.001, 0.3, False)], 30, 10) is None


def test_identify_maturity_interior_and_edges():
    base = {10: 2.0, 15: 1.0, 21: 0.5, 30: 1.2, 42: 2.0, 63: float("nan")}
    got = vx.identify_maturity(base)
    assert (got["status"], got["horizon"], got["argmin"]) == ("identified", 21, 21)
    assert got["measurable"] == [10, 15, 21, 30, 42]                       # 63 has no value
    edge = vx.identify_maturity({**base, 42: 0.3})
    assert (edge["status"], edge["horizon"], edge["argmin"]) == ("UNRESOLVED", None, 42)
    assert "at or beyond 42" in edge["reason"]
    low = vx.identify_maturity({**base, 10: 0.1})
    assert (low["status"], low["argmin"]) == ("UNRESOLVED", 10) and "at or below 10" in low["reason"]
    assert vx.identify_maturity({**base, 15: 0.5})["argmin"] == 15         # a tie goes to the shorter horizon
    assert vx.identify_maturity({21: 0.5})["status"] == "UNRESOLVED"
    assert vx.identify_maturity({21: float("nan")})["status"] == "UNRESOLVED"


# --- the exploratory analyses (not pre-registered; ledger §9) ---------------------------------------------------

# A grid of seven sessions: Fri, Mon, Tue, Wed, Thu, Fri, Mon (made up: 2030-01-04 to 2030-01-14).
G = [date(2030, 1, 4), date(2030, 1, 7), date(2030, 1, 8), date(2030, 1, 9), date(2030, 1, 10), date(2030, 1, 11),
     date(2030, 1, 14)]


def test_weekdays_and_the_start_of_the_daily_era():
    np.testing.assert_array_equal(vx.weekdays_of(G), [4, 0, 1, 2, 3, 4, 0])      # Monday is 0
    assert vx.era_start(G, date(2030, 1, 9)) == 3            # the first session on or after the cut
    assert vx.era_start(G, date(2030, 1, 8)) == 2            # a session itself counts
    assert vx.era_start(G, date(2030, 2, 1)) == 7            # no session after it: len(sessions)


def test_snapshot_calendar_counts_monday_changes_and_their_means():
    # Three changes ending at sessions 1 (Mon), 2 (Tue) and 6 (Mon); the daily era starts at session 3.
    ch = pd.DataFrame({"start": [0, 1, 5], "end": [1, 2, 6], "d_vx": [0.10, 0.02, 0.06], "d_ours": [-0.02, 0.01, 0.00]})
    got = vx.snapshot_calendar(ch, vx.weekdays_of(G), 3)
    assert (got["n"], got["n_end_monday"]) == (3, 2)                                # ends 1 and 6
    assert (got["n_before_era"], got["n_before_era_end_monday"]) == (2, 1)          # ends 1 and 2; only 1 is a Monday
    assert got["mean_dln_vx_end_monday"] == pytest.approx((0.10 + 0.06) / 2, abs=1e-15)
    assert got["mean_dln_ours_end_monday"] == pytest.approx((-0.02 + 0.00) / 2, abs=1e-15)
    assert got["mean_dln_vx_other"] == pytest.approx(0.02, abs=1e-15)
    assert got["mean_dln_ours_other"] == pytest.approx(0.01, abs=1e-15)
    # no Monday change: the Monday means are NaN, not 0
    none = vx.snapshot_calendar(ch.iloc[[1]], vx.weekdays_of(G), 3)
    assert none["n_end_monday"] == 0 and math.isnan(none["mean_dln_vx_end_monday"])


def test_keep_end_weekdays_and_drop_ends_at_filter_on_the_later_session():
    ch = pd.DataFrame({"start": [0, 1, 4, 5], "end": [1, 2, 5, 6], "d_ours": [0.1, 0.2, 0.3, 0.4],
                       "d_vx": [0.1, 0.2, 0.3, 0.4]})
    wd = vx.weekdays_of(G)                                   # ends: Mon, Tue, Fri, Mon
    assert vx.keep_end_weekdays(ch, wd, (1, 2, 3, 4))["end"].tolist() == [2, 5]      # Tuesday to Friday
    assert vx.keep_end_weekdays(ch, wd, (0,))["end"].tolist() == [1, 6]
    assert vx.drop_ends_at(ch, {2, 6})["end"].tolist() == [1, 5]
    assert vx.drop_ends_at(ch, set())["end"].tolist() == [1, 2, 5, 6]


def test_stepped_changes_are_non_overlapping_and_need_both_ends():
    ours = np.array([0.20, np.nan, 0.22, 0.21, 0.23, 0.24, 0.25, 0.26])
    vxv = np.array([0.25, 0.26, 0.27, 0.24, 0.28, 0.29, np.nan, 0.30])
    # M = {0, 2, 3, 4, 5, 7}. k = 2 from session 0: grid 0, 2, 4, 6; the step 4 -> 6 has no value at 6.
    ch = vx.stepped_changes(ours, vxv, 0, 2)
    assert ch["start"].tolist() == [0, 2] and ch["end"].tolist() == [2, 4]
    np.testing.assert_allclose(ch["d_ours"], [math.log(0.22 / 0.20), math.log(0.23 / 0.22)], atol=1e-15)
    np.testing.assert_allclose(ch["d_vx"], [math.log(0.27 / 0.25), math.log(0.28 / 0.27)], atol=1e-15)
    # the grid starts at the first member of M on or after from_pos: from 1 that is 2, so grid 2, 4, 6
    assert vx.stepped_changes(ours, vxv, 1, 2)["start"].tolist() == [2]
    # k = 1: every pair of consecutive members, (2, 3), (3, 4), (4, 5)
    assert vx.stepped_changes(ours, vxv, 0, 1)["end"].tolist() == [3, 4, 5]
    assert len(vx.stepped_changes(ours, vxv, 8, 2)) == 0
    with pytest.raises(ValueError, match="at least 1"):
        vx.stepped_changes(ours, vxv, 0, 0)


def test_ols_summary_against_numpy():
    x, y = np.array([1.0, 2.0, 3.0, 4.0]), np.array([2.0, 4.0, 5.0, 9.0])
    got = vx.ols_summary(x, y)
    assert got["n"] == 4
    assert got["r"] == pytest.approx(np.corrcoef(x, y)[0, 1], abs=1e-12)
    assert got["slope"] == pytest.approx(np.polyfit(x, y, 1)[0], abs=1e-12)                   # y on x
    assert got["reverse_slope_reciprocal"] == pytest.approx(1 / np.polyfit(y, x, 1)[0], abs=1e-12)   # 1 / (x on y)
    assert got["reverse_slope_reciprocal"] > got["slope"]                                     # always: slope * reverse = r^2 <= 1
    empty = vx.ols_summary(np.array([]), np.array([]))
    assert empty["n"] == 0 and math.isnan(empty["slope"])
    flat = vx.ols_summary(np.array([1.0, 1.0, 1.0]), np.array([1.0, 2.0, 3.0]))              # no variance in x
    assert math.isnan(flat["slope"]) and math.isnan(flat["r"])


def test_iv_at_calendar_days_interpolates_total_variance_in_calendar_days():
    tau, w = [14, 28, 49], [0.0023, 0.0071, 0.0106]
    # 30 days: between 28 and 49, w = 0.0071 + 2 / 21 * 0.0035; IV = sqrt(365 w / 30)
    assert vx.iv_at_calendar_days(tau, w, 30) == pytest.approx(
        math.sqrt(365 * (0.0071 + 2 / 21 * 0.0035) / 30), abs=1e-15)
    assert vx.iv_at_calendar_days([49, 14, 28], [0.0106, 0.0023, 0.0071], 30) == vx.iv_at_calendar_days(tau, w, 30)
    assert vx.iv_at_calendar_days(tau, w, 28) == pytest.approx(math.sqrt(365 * 0.0071 / 28), abs=1e-15)
    assert vx.iv_at_calendar_days(tau, w, 10) is None        # before the first expiry: no extrapolation
    assert vx.iv_at_calendar_days(tau, w, 60) is None        # after the last
    assert vx.iv_at_calendar_days([], [], 30) is None
    assert vx.iv_at_calendar_days([20, 40], [0.001, -0.003], 30) is None      # w = -0.001: no IV


def test_extrapolation_side():
    taus = [10, 19, 33]
    assert vx.extrapolation_side(taus, 5) == -1               # before the first listed expiry
    assert vx.extrapolation_side(taus, 10) == 0               # on the first
    assert vx.extrapolation_side(taus, 21) == 0
    assert vx.extrapolation_side(taus, 33) == 0               # on the last
    assert vx.extrapolation_side(taus, 34) == 1
    assert vx.extrapolation_side([], 21) == 0
