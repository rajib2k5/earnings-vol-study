# Tests for stats/eventtests.py and the R-hat of panel/abnormal.py (ADR 0005 §1, §2c-§2e,
# §2h, §5 items 1-2), on hand-worked four-event oracles.
#
# Mutations this module must catch (applied by hand, each seen to fail):
#   - BMP with the population sd (ddof 0) instead of ddof 1
#   - drop (1 - r) from the KP adjustment
#   - forget the clamp at 0 in kp_ow_t (a four-event case whose mean nu*rho is negative)
#   - kpp_t clamping its correlation at 0 (it is not clamped, as published)
#   - Pynnonen's rhobar with n_t^2 instead of n_t (n_t - 1) in the denominator
#   - Patell with L_i instead of L_i - 1 (the moment test: 1.3333 instead of 1.4000)
#   - the rank test's variance with L/(12 (L+1)) instead of L/(12 (L+2))
#   - a demeaned R-hat instead of the uncentred one
#   - R-hat pooling pairs that are not k sessions apart within one event
#   - no second spectral check after the Bartlett taper
#
# Added after the milestone-3 review (each seen to fail on a scratch copy, file restored and its
# SHA-256 checked; [p08 Mxx] = the review's probe docs/validation/probes/m3/p08_mutants.py,
# [fix] = the fix round's script, milestone page §9):
#   - the sign test's pooled share counting e <= 0 instead of e < 0 [p08 M04]
#   - kp_ow_t's short same-sector pair filled with the all-pairs mean [p08 M05]
#   - the Bartlett taper 1 - k/L instead of 1 - k/(L+1) [p08 M07]
# (the clamp bullet above was re-run too [fix]: still killed, by test_kp_ow_rbar_is_clamped_at_zero)

import math

import numpy as np
import pytest

from earnings_vol.panel import abnormal
from earnings_vol.stats import eventtests

SA = np.array([1.0, 2.0, 0.0, 3.0])


def test_bmp_hand_worked():
    # mean 6/4 = 1.5; deviations -0.5, 0.5, -1.5, 1.5, sum sq 0.25+0.25+2.25+2.25 = 5,
    # sd = sqrt(5/3) = 1.290994; se = 1.290994/2 = 0.645497; t = 1.5/0.645497 = 2.323790, df 3.
    r = eventtests.bmp(SA)
    assert r["estimate"] == 1.5 and r["df"] == 3
    assert r["se"] == pytest.approx(math.sqrt(5 / 3) / 2, abs=1e-15)
    assert r["stat"] == pytest.approx(1.5 / (math.sqrt(5 / 3) / 2), abs=1e-12)


def test_kp_adjust_hand_worked():
    # r = 0.1, N = 4: factor sqrt((1 - 0.1)/(1 + 3 * 0.1)) = sqrt(0.9/1.3) = 0.832050.
    # t = 2.323790 * 0.832050 = 1.933508; the se grows by the same factor so the CI stays on t_3.
    r = eventtests.kp_adjust(SA, 0.1)
    f = math.sqrt(0.9 / 1.3)
    assert r["stat"] == pytest.approx(1.5 / (math.sqrt(5 / 3) / 2) * f, abs=1e-12)
    assert r["se"] == pytest.approx(math.sqrt(5 / 3) / 2 / f, abs=1e-12) and r["rbar"] == 0.1


def test_kp_ow_rbar_is_clamped_at_zero():
    # Four events, two pairs on the same day 0: (0, 1) and (2, 3). Baselines over 25 dates:
    # events 0 and 1 share all 25 dates and are perfectly NEGATIVELY correlated (z1 = -z0), so
    # rho(0, 1) = -1; events 2 and 3 share only 10 dates (< 20), so theirs is a fallback; (0, 1)
    # is the only pair with 20 shared dates, so both fallback means are -1.
    # nu: 1 for (0,1) and (2,3), else 0. Mean over 6 pairs of nu*rho = (-1 + -1)/6 < 0 -> r = 0.
    z = np.full((4, 60), np.nan)
    base = np.sin(np.arange(25))
    z[0, :25], z[1, :25] = base, -base
    z[2, 30:40], z[3, 30:40] = base[:10], base[:10]
    nu = np.array([[0, 1, 0, 0], [1, 0, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0]], float)
    assert eventtests.kp_ow_rbar(z, nu, np.array(["A", "A", "B", "B"]), 20) == 0.0


def test_kp_ow_rbar_fills_a_short_same_sector_pair_with_the_sector_mean():
    # ADR 0005 §2e: a pair with nu > 0 and fewer than 20 shared dates takes the mean rho of
    # same-sector pairs (with 20 dates), and the all-pairs mean only when the sector has none.
    # Five events, sectors A A B A A, day 0 groups {0, 1}, {2}, {3, 4}:
    #   0 and 1 share 25 dates with z1 = z0: rho +1 (same sector);
    #   2 shares the same 25 dates with z2 = -z0: rho(0, 2) = rho(1, 2) = -1 (across sectors);
    #   3 and 4 share only 10 dates: the fallback.
    # Same-sector mean over pairs with 20 dates: (0, 1) only -> +1. All-pairs mean: (1 - 1 - 1)/3 = -1/3.
    # nu = 1 for (0, 1) and (3, 4): r = (1 + fallback)/10 pairs = (1 + 1)/10 = 0.2 with the sector
    # mean; the all-pairs mean would give (1 - 1/3)/10 = 0.0667.
    z = np.full((5, 60), np.nan)
    base = np.sin(np.arange(25))
    z[0, :25], z[1, :25], z[2, :25] = base, base, -base
    z[3, 30:40], z[4, 30:40] = base[:10], base[:10]
    nu = np.zeros((5, 5))
    nu[0, 1] = nu[1, 0] = nu[3, 4] = nu[4, 3] = 1.0
    assert eventtests.kp_ow_rbar(z, nu, np.array(["A", "A", "B", "A", "A"]), 20) == pytest.approx(0.2)
    # The short pair across sectors instead (3 in A, 4 in B): it takes the all-pairs mean -1/3,
    # r = (1 - 1/3)/10 = 1/15. (The same-sector mean pools every same-sector pair with 20 dates,
    # whatever its sector, as the ADR words it.)
    assert eventtests.kp_ow_rbar(z, nu, np.array(["A", "A", "B", "A", "B"]), 20) == pytest.approx(1 / 15)


def test_pynnonen_rhobar_and_kpp_hand_worked():
    # Two dates. Date 1: z = 1, 1, -1 (n = 3): (sum z)^2 - sum z^2 = 1 - 3 = -2; n(n-1) = 6.
    # Date 2: z = 2, 2 (n = 2): 16 - 8 = 8; n(n-1) = 2. rhobar = (-2 + 8)/(6 + 2) = 0.75.
    z = np.array([[1.0, 2.0], [1.0, 2.0], [-1.0, np.nan]])
    assert eventtests.pynnonen_rhobar(z) == pytest.approx(0.75)
    # nu for one-session weights: events 0 and 1 on one day, 2 on another: nu = 1, 0, 0 over the
    # three pairs, nubar = 1/3. KPP: v = 1/3 * 0.75 = 0.25 (no clamp), factor
    # sqrt(0.75 / (1 + 2 * 0.25)) = sqrt(0.5) for N = 3.
    a = np.array([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
    sa = np.array([1.0, 2.0, 3.0])            # mean 2, sd 1, se 1/sqrt(3), t_BMP = 2 sqrt(3)
    r = eventtests.kpp(sa, a, z)
    assert r["rbar"] == pytest.approx(0.25)
    assert r["stat"] == pytest.approx(2 * math.sqrt(3) * math.sqrt(0.5), abs=1e-12)
    # A negative correlation is NOT clamped: the factor then exceeds 1.
    zneg = np.array([[1.0], [-1.0], [np.nan]])
    assert eventtests.kpp(sa, a, zneg)["rbar"] < 0


def test_patell_variance_term_moment_test():
    # ADR 0005 §5 item 2: SA ~ t_d with d = L - 1, variance d/(d - 2). At L = 8, d = 7:
    # 7/5 = 1.4000; the mutation L instead of L - 1 gives 8/6 = 1.3333. 10^6 standardised values:
    # each is e_0 / s with s the sd (ddof 1) of 8 iid normal baseline changes.
    rng = np.random.default_rng(2026)
    n, L = 1_000_000, 8
    base = rng.standard_normal((n, L))
    sa = rng.standard_normal(n) / base.std(axis=1, ddof=1)
    assert abs((sa ** 2).mean() - 1.4) < 0.01
    # And the statistic divides by sqrt(sum d/(d - 2)) with d = L - 1: 4 events at L = 8:
    # sqrt(4 * 1.4) = 2.366432; SA sum 6 -> Z = 6 / 2.366432 = 2.535463.
    assert eventtests.patell(SA, np.full(4, 8))["stat"] == pytest.approx(6 / math.sqrt(5.6), abs=1e-12)


def test_sign_and_rank_hand_worked():
    # Baselines (pooled): 3 of 6 changes below 0 -> p = 0.5. Events: A = -1, -2, 0.5 -> w = 2,
    # N = 3: Z = (2 - 1.5)/sqrt(3 * 0.25) = 0.5/0.866025 = 0.577350.
    base = [np.array([-1.0, 1.0]), np.array([-2.0, 2.0]), np.array([-0.5, 0.5])]
    a = np.array([-1.0, -2.0, 0.5])
    g = eventtests.gen_sign(a, base)
    assert g["stat"] == pytest.approx(0.5 / math.sqrt(0.75)) and g["estimate"] == pytest.approx(2 / 3)
    # Ranks among baseline + itself (L = 2, so 3 values): event 1: -1 among (-1, 1, -1) -> ties
    # -1, -1 share ranks 1, 2 -> 1.5; event 2: -2 among (-2, 2, -2) -> 1.5; event 3: 0.5 among
    # (-0.5, 0.5, 0.5) -> 2.5. U = K/(L+2) - 1/2 = 1.5/4 - .5, 1.5/4 - .5, 2.5/4 - .5
    # = -0.125, -0.125, 0.125; sum -0.125. Var each L/(12 (L+2)) = 2/48; sum 6/48 = 0.125.
    # T = -0.125 / sqrt(0.125) = -0.353553.
    r = eventtests.rank_test(a, base)
    assert r["stat"] == pytest.approx(-0.125 / math.sqrt(0.125), abs=1e-12)


def test_sign_test_counts_baseline_changes_strictly_below_zero():
    # Cowan (1992): p-hat is the share of baseline changes with e < 0, strictly. Pooled baseline
    # -1, 0, 1, 2: one of four below 0 -> p = 0.25 (a zero is not below 0; counting it would give
    # 0.5). Events -1, -2, 0.5: w = 2, N = 3. Z = (2 - 0.75)/sqrt(3 x 0.25 x 0.75) = 1.25/0.75 = 5/3.
    g = eventtests.gen_sign(np.array([-1.0, -2.0, 0.5]), [np.array([-1.0, 0.0]), np.array([1.0, 2.0])])
    assert g["stat"] == pytest.approx(5 / 3, abs=1e-12)


def test_rhat_hand_worked_from_two_events():
    # Event 1 clean changes z = 1, -1, 1 at its columns 5..7 (the end of its row); event 2 z = 2, 2 at
    # its columns 0..1 (the start of its row). Uncentred: denominator sum z^2 = 1+1+1+4+4 = 11.
    # Lag 1 pairs inside one event: (1,-1), (-1,1) -> -2; (2,2) -> 4. rho_1 = 2/11.
    # Lag 2: (1,1) -> 1. rho_2 = 1/11. Lag 3: none -> 0.
    # Pooling pairs across the two events (the end of row 1 next to the start of row 2) would add
    # (1, 2) at lag 1 and (-1, 2), (1, 2) at lag 2: rho_1 = 4/11, rho_2 = 2/11.
    z = np.zeros((2, 8))
    ok = np.zeros((2, 8), bool)
    z[0, 5:8], ok[0, 5:8] = [1, -1, 1], True
    z[1, 0:2], ok[1, 0:2] = [2, 2], True
    rho = abnormal.rhat_raw(z, ok, 3)
    assert rho.tolist() == pytest.approx([2 / 11, 1 / 11, 0.0])
    # Demeaned per event (the refuted reading): event 1 centred 2/3, -4/3, 2/3, event 2 centred 0, 0;
    # lag 1 = -16/9 over 24/9 = -2/3, far from 2/11: the assertion above kills that mutant.


def test_rhat_psd_check_tapers_and_checks_again():
    # rho_1 = -0.9 alone: 1 + 2(-0.9) cos(lam) = -0.8 at lam = 0 -> taper by (1 - 1/2) for L = 1:
    # rho_1 = -0.45 -> 1 - 0.9 cos(lam) >= 0.1 everywhere: Bartlett passes.
    rho, flag = abnormal.rhat_psd(np.array([-0.9]))
    assert flag == "rhat_bartlett" and rho.tolist() == pytest.approx([-0.45])
    # ADR 0005 §1's own case, rho_1 = -0.9 with 10 lags: taper (1 - 1/11) gives -0.818,
    # 1 - 1.636 cos(lam) < 0 at 0: still negative, so R = I and the flag rhat_identity.
    rho, flag = abnormal.rhat_psd(np.array([-0.9] + [0.0] * 9))
    assert flag == "rhat_identity" and rho.tolist() == [0.0] * 10
    rho, flag = abnormal.rhat_psd(np.array([-0.25, -0.05]))
    assert flag == "" and rho.tolist() == [-0.25, -0.05]


def test_quad_form_hand_worked():
    # a = (1, 1, 0.5): Q0 = 1 + 1 + 0.25 = 2.25; Q1 = 1*1 + 1*0.5 = 1.5; Q2 = 1*0.5 = 0.5.
    # rho = (-0.2, 0.1): a'Ra = 2.25 + 2(-0.2 * 1.5 + 0.1 * 0.5) = 2.25 - 0.5 = 1.75.
    q = abnormal.lag_products(np.array([[1.0, 1.0, 0.5]]), 2)
    assert q.tolist() == [[2.25, 1.5, 0.5]]
    assert abnormal.quad_form(q, np.array([-0.2, 0.1])).tolist() == pytest.approx([1.75])
