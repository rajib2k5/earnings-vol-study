# Tests for stats/common_factor.py (milestone 4: where the crush baselines' rho-bar of 0.30 sits;
# research/prototypes/rhobar_crush.py prints what these functions measure on the real data).
# Hand-worked fixtures with made-up numbers.
#
# Mutations this module must catch (each applied to a scratch copy, the test seen to fail, the file
# restored and its SHA-256 checked; milestone page appendix):
#   - date_contributions' cross-product without subtracting sum z^2 (own products counted)
#   - rhobar over n_t^2 instead of n_t (n_t - 1)
#   - loo_factor including the event's own firm
#   - loo_factor ignoring the groups (a sector factor equal to the market one)
#   - residualise without rescaling to mean square 1
#   - residualise with one loading for all firms

import numpy as np
import pytest

from earnings_vol.stats import common_factor, eventtests

# Three events (firms a, b, c), three dates:
#   date 0: z = 1, 2, NaN   -> n 2, sum 3, sumsq 5, cross 9 - 5 = 4 (= 2 * 1 * 2), pairs 2
#   date 1: z = -1, 1, 2    -> n 3, sum 2, sumsq 6, cross 4 - 6 = -2 (= 2 (-1 - 2 + 2)), pairs 6
#   date 2: z = 3, NaN, NaN -> n 1, cross 0, pairs 0
#   rho-bar = (4 - 2) / (2 + 6) = 0.25
Z = np.array([[1.0, -1.0, 3.0], [2.0, 1.0, np.nan], [np.nan, 2.0, np.nan]])


def test_date_contributions_and_rhobar_hand_worked():
    c = common_factor.date_contributions(Z)
    assert c["n"].tolist() == [2, 3, 1] and c["cross"].tolist() == [4.0, -2.0, 0.0]
    assert c["pairs"].tolist() == [2, 6, 0]
    assert common_factor.rhobar(Z) == pytest.approx(0.25)
    assert common_factor.rhobar(Z) == pytest.approx(eventtests.pynnonen_rhobar(Z))


def test_loo_factor_leaves_the_own_firm_out_and_respects_groups():
    # A fourth event, firm a again (row 3: 5, 7, NaN). Market factor: a's row 0 at date 1 sees b and
    # c: (1 + 2)/2 = 1.5; b at date 0 sees firm a's two events: (1 + 5)/2 = 3. Firm a's two events
    # never see each other: row 3 at date 0 sees b only (2), at date 1 b and c (1.5).
    z = np.vstack([Z, [[5.0, 7.0, np.nan]]])
    firm = ["a", "b", "c", "a"]
    m = common_factor.loo_factor(z, firm)
    assert m[0, 1] == pytest.approx(1.5) and m[1, 0] == pytest.approx(3.0)
    assert np.isnan(m[0, 2])                                  # nobody else on date 2
    assert m[3, 0] == pytest.approx(2.0) and m[3, 1] == pytest.approx(1.5)
    # Groups {a, b} and {c}: a at date 1 sees b only (1); c sees nobody in its group.
    g = common_factor.loo_factor(z, firm, ["s1", "s1", "s2", "s1"])
    assert g[0, 1] == pytest.approx(1.0) and np.isnan(g[2, 1])


def test_residualise_per_firm_loading_and_rescaling():
    # Firm a: z = 2f exactly (loading 2) -> residual 0 everywhere; firm b: z = -f + noise.
    f = np.array([[1.0, -2.0, 0.5], [1.0, 2.0, -1.0]])
    z = np.array([[2.0, -4.0, 1.0], [-1.0, -1.0, 2.0]])
    res, load = common_factor.residualise(z, f, ["a", "b"])
    assert load["a"] == pytest.approx(2.0)
    # b: slope = (-1 - 2 - 2) / (1 + 4 + 1) = -5/6; residuals -1 + 5/6, -1 + 10/6, 2 - 5/6 =
    # -1/6, 4/6, 7/6; mean square (1 + 16 + 49)/36/3 = 66/108; rescaled by its root.
    assert load["b"] == pytest.approx(-5 / 6)
    raw = np.array([-1 / 6, 4 / 6, 7 / 6])
    assert res[1] == pytest.approx(raw / np.sqrt(np.mean(raw ** 2)))
    assert np.nanmean(res[1] ** 2) == pytest.approx(1.0)
    assert np.isnan(res[0]).all()                              # a residual of exactly 0 has no scale


def test_a_pure_common_factor_is_removed():
    # 30 firms, 200 dates, z = f_t + small own noise: rho-bar estimates E[z_i z_j] = the mean of f_t^2
    # over the dates (eq. 32 is not normalised); after the leave-one-out factor, about 0.
    rng = np.random.default_rng(0)
    ft = rng.standard_normal(200)
    z = ft[None, :] + 0.2 * rng.standard_normal((30, 200))
    firm = [f"F{k}" for k in range(30)]
    assert common_factor.rhobar(z) == pytest.approx(np.mean(ft ** 2), abs=0.01)
    res, _ = common_factor.residualise(z, common_factor.loo_factor(z, firm), firm)
    assert abs(common_factor.rhobar(res)) < 0.05
