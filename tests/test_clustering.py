# Tests for stats/clustering.py (ADR 0005 §2b, §2f), on hand-worked oracles with every
# intermediate in the comments, and against statsmodels with use_t=True (ADR 0005 §3: the
# 4-event check must pass use_t=True and assert the df and the p-value).
#
# Mutations this module must catch (applied by hand, each seen to fail):
#   - the intersection term of the two-way variance added instead of subtracted
#   - G/(G-1) dropped from CR1
#   - normal instead of t_{min(G)-1} critical values (the p-value and the CI)
#   - df = max(G_A, G_B) - 1 instead of min
#   - no fallback when V <= 0 (or the fallback taking min instead of max)
#   - no season merge (merge_small_seasons returning the raw seasons)
#   - a merged season joining the farther neighbour
#   - the unbalanced rule using >= instead of >
#   - Rademacher draws sampled instead of fully enumerated (the 2^G count)
#   - rad_season_p counting |t*| > |t| (strict), which loses the floor 2/2^G
#
# Added after the milestone-3 review (each seen to fail on a scratch copy, file restored and its
# SHA-256 checked; [p08 Mxx] = the review's probe docs/validation/probes/m3/p08_mutants.py,
# [fix] = the fix round's script, milestone page §9):
#   - CR1 residuals not demeaned [p08 M01]
#   - rad_season_p's t* variance not re-centred per sign vector [p08 M02]
#   - the latest small season merged first instead of the earliest [p08 M03]

import math

import numpy as np
import pytest
import statsmodels.api as sm
from scipy import stats

from earnings_vol.stats import clustering

# Four events: A = 0.1, 0.3, -0.2, 0.6, so mean 0.8/4 = 0.2 and u = A - 0.2 = -0.1, 0.1, -0.4, 0.4.
A = np.array([0.1, 0.3, -0.2, 0.6])
DATES = ["d1", "d1", "d2", "d3"]
FIRMS = ["F1", "F2", "F1", "F2"]


def test_oneway_cr1_hand_worked():
    # Date sums of u: d1 -0.1 + 0.1 = 0, d2 -0.4, d3 0.4; G = 3.
    # V = 3/2 * (0^2 + 0.16 + 0.16) / 4^2 = 1.5 * 0.32 / 16 = 0.03; se = sqrt(0.03) = 0.173205.
    # t = 0.2 / 0.173205 = 1.154701, df = G - 1 = 2.
    # t_2 tail: P(|T_2| > t) = 1 - t / sqrt(2 + t^2) = 1 - 1.154701 / sqrt(3.333333) = 0.367544.
    v, g = clustering.cr1_variance(A, DATES)
    assert g == 3 and v == pytest.approx(0.03, abs=1e-15)
    r = clustering.oneway(A, DATES)
    assert r["df"] == 2 and r["n_clusters"] == 3 and r["n_clusters_firm"] is None
    assert r["stat"] == pytest.approx(0.2 / math.sqrt(0.03), abs=1e-12)
    assert r["p_value"] == pytest.approx(1 - 1.154700538 / math.sqrt(2 + 1.154700538 ** 2), abs=1e-9)
    # t_{2, 0.975} = 4.302653: the CI is 0.2 +- 4.302653 * 0.173205
    assert r["ci_hi"] - 0.2 == pytest.approx(4.302652730 * math.sqrt(0.03), abs=1e-8)


def test_twoway_cgm_hand_worked():
    # Dates (above): V_A = 0.03, G_A = 3.
    # Firms: F1 = -0.1 - 0.4 = -0.5, F2 = 0.1 + 0.4 = 0.5; G_B = 2.
    #   V_B = 2/1 * (0.25 + 0.25) / 16 = 0.0625.
    # Date x firm cells: (d1,F1) -0.1, (d1,F2) 0.1, (d2,F1) -0.4, (d3,F2) 0.4; G = 4.
    #   V_AB = 4/3 * (0.01 + 0.01 + 0.16 + 0.16) / 16 = 4/3 * 0.02125 = 0.0283333.
    # V = 0.03 + 0.0625 - 0.0283333 = 0.0641667; se = 0.2533114; t = 0.2 / se = 0.7895420.
    # df = min(3, 2) - 1 = 1: a Cauchy, P(|T_1| > t) = 1 - 2 atan(t) / pi = 0.5744333.
    # t_{1, 0.975} = tan(0.475 pi) = 12.7062047.
    r = clustering.twoway(A, DATES, FIRMS)
    assert (r["v_a"], r["v_b"]) == (pytest.approx(0.03), pytest.approx(0.0625))
    assert r["v_ab"] == pytest.approx(4 / 3 * 0.02125, abs=1e-15)
    v = 0.03 + 0.0625 - 4 / 3 * 0.02125
    assert r["se"] == pytest.approx(math.sqrt(v), abs=1e-15) and not r["fallback"]
    assert (r["df"], r["n_clusters"], r["n_clusters_firm"]) == (1, 3, 2)
    t = 0.2 / math.sqrt(v)
    assert r["stat"] == pytest.approx(t, abs=1e-12)
    assert r["p_value"] == pytest.approx(1 - 2 * math.atan(t) / math.pi, abs=1e-12)
    assert r["ci_hi"] - 0.2 == pytest.approx(math.tan(0.475 * math.pi) * math.sqrt(v), abs=1e-9)
    assert 0.2 - r["ci_lo"] == pytest.approx(r["ci_hi"] - 0.2, abs=1e-12)


def test_twoway_falls_back_to_the_larger_one_way_variance_when_v_is_not_positive():
    # u = 1, -0.25, -1.5, 0.75 (sum 0; A = u + 0.75, mean 0.75); dates d1 d1 d2 d2; firms F1 F2 F1 F2.
    # Dates: d1 0.75, d2 -0.75 -> V_A = 2/1 * 1.125 / 16 = 0.140625.
    # Firms: F1 1 - 1.5 = -0.5, F2 -0.25 + 0.75 = 0.5 -> V_B = 2/1 * 0.5 / 16 = 0.0625.
    # Cells all distinct: V_AB = 4/3 * (1 + 0.0625 + 2.25 + 0.5625) / 16 = 4/3 * 3.875 / 16 = 0.322917.
    # V = 0.203125 - 0.322917 < 0 -> max(V_A, V_B) = 0.140625, se 0.375, t = 0.75 / 0.375 = 2.
    # (min would give se 0.25 and t = 3.)
    a = np.array([1.75, 0.5, -0.75, 1.5])
    r = clustering.twoway(a, ["d1", "d1", "d2", "d2"], ["F1", "F2", "F1", "F2"])
    assert r["fallback"] and r["se"] == pytest.approx(0.375) and r["stat"] == pytest.approx(2.0)
    assert r["df"] == 1


def test_statsmodels_with_use_t_gives_the_same_two_way_t_df_and_p():
    # ADR 0005 §3: statsmodels' two-column `groups` must give the CGM formula on this case,
    # with use_t=True; its default (use_t=False) reports normal p-values. An intercept-only
    # OLS: statsmodels' small-sample factor (G/(G-1)) (N-1)/(N-K) is G/(G-1) when K = 1.
    codes = np.column_stack([np.unique(DATES, return_inverse=True)[1], np.unique(FIRMS, return_inverse=True)[1]])
    res = sm.OLS(A, np.ones((4, 1))).fit(cov_type="cluster", cov_kwds={"groups": codes}, use_t=True)
    ours = clustering.twoway(A, DATES, FIRMS)
    assert res.use_t is True
    assert res.df_resid_inference == min(3, 2) - 1 == ours["df"]
    assert res.bse[0] == pytest.approx(ours["se"], abs=1e-12)
    assert res.pvalues[0] == pytest.approx(2 * stats.t.sf(abs(res.tvalues[0]), 1), abs=1e-12)
    assert res.pvalues[0] == pytest.approx(ours["p_value"], abs=1e-12)
    # The default fit: the same se, but a normal p-value, which is the mutation G1's invariant catches.
    default = sm.OLS(A, np.ones((4, 1))).fit(cov_type="cluster", cov_kwds={"groups": codes})
    assert default.use_t is False
    assert default.pvalues[0] == pytest.approx(2 * stats.norm.sf(abs(default.tvalues[0])), abs=1e-12)
    assert abs(default.pvalues[0] - ours["p_value"]) > 0.1


def test_merge_small_seasons_joins_the_nearest_median():
    # Q1: 12 events, day-0 ordinals 1..12 (median 6.5); Q2: 3 events at 29, 30, 31 (median 30);
    # Q3: 12 events at 33..44 (median 38.5). Q2 has < 10: |38.5 - 30| = 8.5 < |6.5 - 30| = 23.5,
    # so it joins Q3, which then has 15. Two clusters remain.
    season = ["Q1"] * 12 + ["Q2"] * 3 + ["Q3"] * 12
    d0 = list(range(1, 13)) + [29, 30, 31] + list(range(33, 45))
    got = clustering.merge_small_seasons(season, d0, 10)
    assert got.tolist() == ["Q1"] * 12 + ["Q3"] * 15
    # Q2 nearer Q1 instead: it joins Q1.
    got = clustering.merge_small_seasons(season, list(range(1, 13)) + [13, 14, 15] + list(range(60, 72)), 10)
    assert got.tolist() == ["Q1"] * 15 + ["Q3"] * 12


def test_merge_takes_the_earliest_small_season_first():
    # The order matters when two seasons are small: merging one moves its neighbour's median.
    # S1: 4 events at 0..3; S2: 30 at 100..129 (median 114.5); S3: 4 at 163, 164, 164, 165 (median 164);
    # S4: 30 at 200..229 (median 214.5).
    # Earliest first (the rule): S1 joins S2 (its only neighbour), whose 34 days have median
    # (112 + 113)/2 = 112.5; then S3 is 51.5 from S2 and 50.5 from S4, so it joins S4.
    # Latest first: S3 is 49.5 from S2 and 50.5 from S4, so it would join S2.
    season = ["S1"] * 4 + ["S2"] * 30 + ["S3"] * 4 + ["S4"] * 30
    d0 = [0, 1, 2, 3] + list(range(100, 130)) + [163, 164, 164, 165] + list(range(200, 230))
    got = clustering.merge_small_seasons(season, d0, 10)
    assert got.tolist() == ["S2"] * 34 + ["S4"] * 34


def test_unbalanced_rule_boundary():
    # 15 against 10 is exactly 1.5 times: not more, so balanced; 16 against 10 is unbalanced.
    assert not clustering.unbalanced(["a"] * 15 + ["b"] * 10, 1.5)
    assert clustering.unbalanced(["a"] * 16 + ["b"] * 10, 1.5)


def test_rademacher_enumerates_every_sign_vector_hand_worked():
    # One event per season, G = 3, A = (3, 1, 1): mean 5/3. For sign vector v the season sums are
    # v * A and t* = mean / sqrt(3/2 * sum (v A - mean)^2 / 9):
    #   (+,+,+): sums 3,1,1, mean 5/3, devs 4/3,-2/3,-2/3, sum sq 24/9, var 1.5*24/81 = 4/9, t = 2.5
    #   (+,+,-): 3,1,-1, mean 1, devs 2,0,-2, sum sq 8, var 1.5*8/9 = 4/3, |t| = 1/sqrt(4/3) = 0.8660
    #   (+,-,+): the same, 0.8660;   (+,-,-): 3,-1,-1, mean 1/3, sum sq 96/9, var 16/9, t = 0.25
    # and their mirrors. Observed t = 2.5: 2 of 8 vectors reach it, p = 2/8 = 0.25 = 2/2^3 (the floor).
    r = clustering.rademacher_p(np.array([3.0, 1.0, 1.0]), ["a", "b", "c"])
    assert r["n_vectors"] == 8 and r["n_clusters"] == 3
    assert r["stat"] == pytest.approx(2.5) and r["p_value"] == pytest.approx(0.25)
    # A = (3, 1, -1): t = 0.8660; |t*| >= 0.8660 for 2 (2.5) + 4 (0.866) = 6 of 8 -> p = 0.75.
    r = clustering.rademacher_p(np.array([3.0, 1.0, -1.0]), ["a", "b", "c"])
    assert r["stat"] == pytest.approx(1 / math.sqrt(4 / 3)) and r["p_value"] == pytest.approx(0.75)
    assert clustering.sign_vectors(7).shape == (128, 7)
