# Tests for stats/regression.py (ADR 0005 §3): OLS with one-way and two-way (Cameron, Gelbach &
# Miller 2011) cluster-robust covariance, t with min(G) - 1 df, and the Wald F of H7. A hand-worked
# 4-event case with every intermediate in the comments, the same case and a larger one against
# statsmodels' OLS with cov_type "cluster" and use_t=True (ADR 0005 §3: the fit must use the t and
# F references; statsmodels' default use_t=False gives normal and chi-square p-values), and H7's
# regressor in w units (ADR 0003 §c "Units").
#
# Mutations this module must catch (each applied to a scratch copy, the test seen to fail, the file
# restored and its SHA-256 checked; milestone page appendix):
#   - the intersection term added instead of subtracted (V_A + V_B + V_AB)
#   - the small-sample factor without (N-1)/(N-K) (G/(G-1) only)
#   - the small-sample factor without G/(G-1)
#   - df = max(G_A, G_B) - 1 instead of min
#   - the CI with 1.96 instead of t_{df,0.975}
#   - the Wald F not divided by q
#   - the Wald p from chi-square(q) instead of F(q, df)
#   - zscore with ddof 0
#   - dummies keeping every level (no level dropped)
#   - implied_variance without /252 (drivers.implied_variance)
#   - wald_test's fallback taking the one-way block with the SMALLER trace (the milestone-4 review's
#     surviving mutant M03: the 2x2 fallback branch had no test)

import numpy as np
import pytest
import statsmodels.api as sm
from scipy import stats

from earnings_vol.stats import drivers, regression

# The 4-event case. x = 0, 1, 2, 3; y = 1, 3, 3, 8; X = [1, x].
#   x-bar 1.5, y-bar 3.75; Sxx = 5, Sxy = (-1.5)(-2.75) + (-0.5)(-0.75) + (0.5)(-0.75) + (1.5)(4.25) = 10.5
#   b = 2.1, a = 3.75 - 2.1 * 1.5 = 0.6; fitted 0.6, 2.7, 4.8, 6.9; u = 0.4, 0.3, -1.8, 1.1
#   X'X = [[4, 6], [6, 14]], det 20, (X'X)^-1 = [[0.7, -0.3], [-0.3, 0.2]]
#   x_i u_i rows: [0.4, 0], [0.3, 0.3], [-1.8, -3.6], [1.1, 3.3]
# Date A: events 0, 1 on d1 and 2, 3 on d2. Sums [0.7, 0.3], [-0.7, -0.3]; meat [[0.98, 0.42], [0.42, 0.18]]
#   (X'X)^-1 meat (X'X)^-1 = [[0.32, -0.12], [-0.12, 0.045]]; c = G/(G-1) (N-1)/(N-K) = 2 * 3/2 = 3
#   V_A = [[0.96, -0.36], [-0.36, 0.135]]
# Firm B: events 0, 2 in f1 and 1, 3 in f2. Sums [-1.4, -3.6], [1.4, 3.6]; meat [[3.92, 10.08], [10.08, 25.92]]
#   sandwich [[0.02, -0.06], [-0.06, 0.18]]; c = 3; V_B = [[0.06, -0.18], [-0.18, 0.54]]
# Intersection (one event per cell, so HC1): meat = sum of outer products = [[4.70, 10.20], [10.20, 23.94]]
#   sandwich [[0.1736, -0.0774], [-0.0774, 0.1566]]; c = 4/3 * 3/2 = 2; V_AB = [[0.3472, -0.1548], [-0.1548, 0.3132]]
# V = V_A + V_B - V_AB = [[0.6728, -0.3852], [-0.3852, 0.3618]]
#   se(b) = sqrt(0.3618) = 0.601498, t = 3.491283; se(a) = sqrt(0.6728) = 0.820244, t = 0.731490
#   df = min(2, 2) - 1 = 1
# Wald (a, b) = (0, 1): d = [0.6, 1.1], det V = 0.6728 * 0.3618 - 0.3852^2 = 0.09504
#   d' V^-1 d = (0.3618 * 0.36 + 2 * 0.3852 * 0.66 + 0.6728 * 1.21) / 0.09504 = 1.4528 / 0.09504 = 15.28620
#   F = 15.28620 / 2 = 7.643098 against F(2, 1)
# One-way by date: se(b) = sqrt(0.135) = 0.367423, t = 5.715476, df = 1.
Y4 = np.array([1.0, 3.0, 3.0, 8.0])
X4 = np.column_stack([np.ones(4), [0.0, 1.0, 2.0, 3.0]])
DATE4, FIRM4 = ["d1", "d1", "d2", "d2"], ["f1", "f2", "f1", "f2"]


def test_two_way_covariance_hand_worked():
    f = regression.fit(Y4, X4)
    assert f["b"] == pytest.approx([0.6, 2.1], abs=1e-12)
    assert f["u"] == pytest.approx([0.4, 0.3, -1.8, 1.1], abs=1e-12)
    c = regression.covariance(f, X4, DATE4, FIRM4)
    assert c["V_a"] == pytest.approx(np.array([[0.96, -0.36], [-0.36, 0.135]]), abs=1e-12)
    assert c["V_b"] == pytest.approx(np.array([[0.06, -0.18], [-0.18, 0.54]]), abs=1e-12)
    assert c["V"] == pytest.approx(np.array([[0.6728, -0.3852], [-0.3852, 0.3618]]), abs=1e-12)
    assert c["df"] == 1.0 and c["g_a"] == 2 and c["g_b"] == 2
    b = regression.coef_test(f, c, 1)
    assert b["se"] == pytest.approx(0.601498129672902, abs=1e-12)
    assert b["stat"] == pytest.approx(3.4912826763767186, abs=1e-12)
    assert b["p_value"] == pytest.approx(2 * stats.t.sf(3.4912826763767186, 1), abs=1e-14)
    q = stats.t.ppf(0.975, 1)                     # 12.7062, not 1.96
    assert b["ci_hi"] - b["estimate"] == pytest.approx(q * 0.601498129672902, abs=1e-10)
    assert (b["n"], b["n_clusters"], b["n_clusters_firm"], b["fallback"]) == (4, 2, 2, False)
    a = regression.coef_test(f, c, 0)
    assert a["se"] == pytest.approx(0.820243866176394, abs=1e-12) and a["stat"] == pytest.approx(0.73148977, abs=1e-8)


def test_wald_and_one_way_hand_worked():
    f = regression.fit(Y4, X4)
    w = regression.wald_test(f, regression.covariance(f, X4, DATE4, FIRM4), np.eye(2), np.array([0.0, 1.0]))
    assert w["stat"] == pytest.approx(7.643098, abs=1e-6)
    assert (w["df"], w["df_num"]) == (1.0, 2.0)
    assert w["p_value"] == pytest.approx(stats.f.sf(7.6430976430976365, 2, 1), abs=1e-14)
    assert w["p_value"] != pytest.approx(stats.chi2.sf(2 * 7.6430976430976365, 2), abs=1e-3)
    one = regression.coef_test(f, regression.covariance(f, X4, DATE4), 1)
    assert one["se"] == pytest.approx(np.sqrt(0.135), abs=1e-12) and one["stat"] == pytest.approx(5.7154760664940945)
    assert one["n_clusters_firm"] is None and one["df"] == 1.0


def _statsmodels(y, X, ga, gb=None):
    groups = np.column_stack([ga, gb]) if gb is not None else np.asarray(ga)
    return sm.OLS(y, X).fit(cov_type="cluster", cov_kwds={"groups": groups}, use_t=True)


def test_statsmodels_with_use_t_agrees_on_the_hand_worked_case():
    # ADR 0005 §3: assert use_t, the df statsmodels uses for inference, the p of the t and the F.
    res = _statsmodels(Y4, X4, np.array([0, 0, 1, 1]), np.array([0, 1, 0, 1]))
    assert res.use_t is True and res.df_resid_inference == 1
    f = regression.fit(Y4, X4)
    c = regression.covariance(f, X4, DATE4, FIRM4)
    assert res.cov_params() == pytest.approx(c["V"], abs=1e-12)
    assert res.pvalues[1] == pytest.approx(regression.coef_test(f, c, 1)["p_value"], abs=1e-12)
    wt = res.wald_test((np.eye(2), np.array([0.0, 1.0])), use_f=True, scalar=True)
    w = regression.wald_test(f, c, np.eye(2), np.array([0.0, 1.0]))
    assert wt.df_denom == 1 and wt.df_num == 2
    assert float(wt.fvalue) == pytest.approx(w["stat"], abs=1e-10) and float(wt.pvalue) == pytest.approx(w["p_value"])


def test_statsmodels_agrees_on_a_larger_unbalanced_design():
    # 120 made-up events on up to 30 dates (29 drawn) and 13 firms (unbalanced), K = 4: two-way and
    # one-way, every coefficient's se, p and CI, and the Wald F of two coefficients, to 1e-10.
    rng = np.random.default_rng(3)
    n = 120
    da, fi = rng.integers(0, 30, n), rng.integers(0, 13, n)
    X = np.column_stack([np.ones(n), rng.normal(size=n), rng.normal(size=n), rng.exponential(size=n)])
    y = X @ np.array([0.1, 0.5, -0.2, 0.0]) + rng.normal(size=n) + 0.5 * rng.normal(size=30)[da] + rng.normal(size=13)[fi]
    f = regression.fit(y, X)
    for gb in (fi, None):
        res = _statsmodels(y, X, da, gb)
        c = regression.covariance(f, X, da, gb)
        g_date, g_firm = len(set(da.tolist())), len(set(fi.tolist()))
        assert (g_date, g_firm) == (29, 13)
        assert res.use_t is True and res.df_resid_inference == (min(g_date, g_firm) if gb is not None else g_date) - 1
        assert c["df"] == res.df_resid_inference
        for j in range(4):
            got = regression.coef_test(f, c, j)
            assert got["se"] == pytest.approx(res.bse[j], rel=1e-10) and got["p_value"] == pytest.approx(res.pvalues[j])
            lo, hi = res.conf_int()[j]
            assert (got["ci_lo"], got["ci_hi"]) == pytest.approx((lo, hi), rel=1e-10)
        R = np.array([[0, 1.0, 0, 0], [0, 0, 1.0, 0]])
        wt = res.wald_test((R, np.zeros(2)), use_f=True, scalar=True)
        w = regression.wald_test(f, c, R, np.zeros(2))
        assert float(wt.fvalue) == pytest.approx(w["stat"], rel=1e-10) and wt.df_denom == w["df"]


def test_zscore_and_dummies():
    # zscore: mean 0, sd 1 with ddof 1: [1, 2, 3, 6] -> mean 3, sd sqrt((4+1+0+9)/3) = 2.160247
    z = regression.zscore(np.array([1.0, 2.0, 3.0, 6.0]))
    assert z == pytest.approx(np.array([-2, -1, 0, 3]) / np.sqrt(14 / 3), abs=1e-12)
    d, names = regression.dummies(["b", "a", "c", "b"], "sector")
    assert names == ["sector:b", "sector:c"]                     # level "a" (first sorted) dropped
    assert d.tolist() == [[1, 0], [0, 0], [0, 1], [1, 0]]


def test_rank_deficient_design_is_refused():
    X = np.column_stack([np.ones(4), [1.0, 2, 3, 4], [2.0, 4, 6, 8]])
    with pytest.raises(ValueError, match="rank"):
        regression.fit(Y4, X)


def test_a_non_positive_two_way_variance_falls_back_to_the_larger_one_way():
    # y = 1, 2, 4, 7 on x = 0..3: u = 0.5, -0.5, -0.5, 0.5; V_A[b,b] = 0.06, V_B[b,b] = 0.24,
    # V_AB[b,b] = 0.10, so V = 0.20 > 0 for b, but the 2x2 block of (a, b) has
    # det(V) = 0.325 * 0.20 - 0.30^2 = -0.025 < 0: the Wald test uses the one-way block with the
    # larger trace (V_B, trace 0.78 against V_A's 0.195), and says so.
    y = np.array([1.0, 2.0, 4.0, 7.0])
    f = regression.fit(y, X4)
    c = regression.covariance(f, X4, DATE4, FIRM4)
    assert c["V"] == pytest.approx(np.array([[0.325, -0.30], [-0.30, 0.20]]), abs=1e-12)
    w = regression.wald_test(f, c, np.array([[0.0, 1.0]]), np.array([0.0]))
    assert not w["fallback"] and w["stat"] == pytest.approx(2.0 ** 2 / 0.20)
    c2 = dict(c, V=c["V"] - np.diag([0.0, 0.25]))                  # b's variance -0.05: fall back to max(V_A, V_B)
    t = regression.coef_test(f, c2, 1)
    assert t["fallback"] and t["se"] == pytest.approx(np.sqrt(0.24))


def test_a_non_positive_definite_wald_block_falls_back_to_the_larger_trace_one_way_block():
    # Fix R3 (milestone-4 review, mutant M03). Twelve made-up events, 4 dates x 3 firms (one event per
    # cell), x = 0..4 repeating, y below. The two-way V of (a, b) has a negative eigenvalue, so the joint
    # Wald test of a = 0, b = 1 falls back to a one-way block: the one with the LARGER trace, here the
    # date block (trace 0.0740 against the firm block's 0.0088, which with 3 clusters is nearly
    # singular and would give F about 1.6e5 instead of 65.07).
    dates = np.repeat(["d1", "d2", "d3", "d4"], 3)
    firms = np.tile(["f1", "f2", "f3"], 4)
    X = np.column_stack([np.ones(12), np.arange(12.0) % 5])
    y = np.array([0.9, 0.1, -0.7, -0.9, -0.5, 0.2, -1.0, -0.2, -0.2, 0.5, 0.2, 0.4])
    f = regression.fit(y, X)
    c = regression.covariance(f, X, dates, firms)
    assert np.linalg.eigvalsh(c["V"]).min() < 0
    assert np.trace(c["V_a"]) == pytest.approx(0.073963, abs=1e-6) and np.trace(c["V_b"]) == pytest.approx(0.008781,
                                                                                                          abs=1e-6)
    w = regression.wald_test(f, c, np.eye(2), np.array([0.0, 1.0]))
    d = f["b"] - np.array([0.0, 1.0])
    assert w["fallback"] is True
    assert w["stat"] == pytest.approx(float(d @ np.linalg.solve(c["V_a"], d)) / 2) == pytest.approx(65.0747522, abs=1e-6)
    assert w["p_value"] == pytest.approx(stats.f.sf(w["stat"], 2, 2))       # df still min(4, 3) - 1
    assert float(d @ np.linalg.solve(c["V_b"], d)) / 2 > 1e5                 # the smaller block's F, for contrast


def test_h7_regressor_is_in_w_units():
    # ADR 0003 §c "Units" and ADR 0005 §3: the AAPL worked example, E = 0.00088284 and
    # sigma_d = 0.2442 annualised: 0.00088284 + 0.2442^2 / 252 = 0.00088284 + 0.00023664 = 0.0011195.
    # Without the /252 it would be 0.0605.
    got = drivers.implied_variance(np.array([0.00088284]), np.array([0.2442]))[0]
    assert got == pytest.approx(0.0011195, abs=5e-8)
    assert got != pytest.approx(0.00088284 + 0.2442 ** 2, abs=1e-3)
