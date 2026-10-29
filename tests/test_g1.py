# Tests for gate G1 (stats/g1.py; ADR 0005 §5 item 4). The full gate runs from the command line
# (`python -m earnings_vol.stats.run --g1`, 2,000 replications per design, ~5 minutes on 20 cores)
# and its rates are committed as `results` rows (family validation); these tests check the
# machinery, the moments of the data-generating process, and the committed verdicts.
#
# Mutations this module must catch (applied by a script, each seen to fail, file restored by SHA-256):
#   - the band from the normal approximation instead of the exact binomial quantiles
#   - stale_psi taking the larger root
#   - the common quote noise without its sqrt(kappa) share (wrong cross-firm lag-1 moment)
#   - calibrate's kappa = rho1 / c1 instead of c1 / rho1
#   - day-0 date clusters for a ramp: stats/suite.py's ramp clustering by day 0 instead of the
#     merged season makes the smoke run's two-way row reject far above 5%
#   - a primary whose calibrated rate is above the band kept in the confirmatory family: the
#     committed H3 calibrated rate set to 0.07 in data/derived/results.parquet (restored by checksum)
#
# Added after the milestone-3 review (each seen to fail on a scratch copy, file restored and its
# SHA-256 checked; [p08 Mxx] = the review's probe docs/validation/probes/m3/p08_mutants.py,
# [fix] = the fix round's script, milestone page §9):
#   - G1 using the DGP's true beta instead of re-estimating it [p08 M12]
#   - the AR of levels without Kendall's correction [p08 M13]
#   - the company-effect sd without the sampling-variance correction [p08 M14]
#   - the DGP dropping the day-0 jumps [p08 M15]
#   - the band at the 99% quantile instead of 99.5% [p08 M16]
#   - sig0 without the change-variance factor sqrt(2/(1 + phi) + 2 n^2) [fix]
#   - generate() ignoring the calibrated sig0 [fix]
#   - oversized() counting a rate equal to the band's top [fix]
#   - oversized() keeping date_cluster_t, the rejected mutant [fix]
#   - withhold() keeping the confidence interval [fix]
#   - season_cut_rows merging the first two seasons instead of the last two [fix]
#   - season_cut_rows' Holm p computed with the reported p instead of the cut's [fix]
#   - data: an oversized robustness row keeping its p-value in results.parquet [fix]
#   - data: the season-cut row's p_holm set to the reported Holm p [fix]
#
# Added in the second fix round (milestone page §9, second round; [d02 W7] = the delta review's
# docs/validation/probes/m3-delta/d02_wiring_mutants.py, anchor moved to the new line; [fix2] = this
# round's script):
#   - replicate() evaluating H4 on the first (cm30) series [d02 W7]
#   - second_series() re-estimating beta on the sigma_d series [fix2]
#   - second_series() drawing its own ln VIX path [fix2]
#   - replicate() evaluating the second series without the cm30 beta (est dropped) [fix2]
#   - calibrate_from's day-0 ratio reading A_i / s_i instead of (A_i - mean A) / s_i [fix2]
#   - near_bar() with a strict margin (a rate exactly one point from the bar not re-measured) [fix2]
#   - size_verdicts() deciding a re-measured rate against the 2,000-replication bar [fix2]
#   - size_verdicts() falling back to the 2,000 rate when a near-bar rate was not re-measured [fix2]
#   - generate() ignoring a given ln VIX path [fix2]
#   - estimate() ignoring a given beta [fix2]
#   - results.oversized() returning every verdict, not only the oversized ones [fix2]
#   - data: H4 gen_sign_z's re-measured rate set inside the bar in results.parquet [fix2]

import dataclasses
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from earnings_vol import params, schema, store
from earnings_vol.events import calendar
from earnings_vol.panel import abnormal
from earnings_vol.stats import clustering, g1, inputs, multiple, results

DERIVED = Path(__file__).resolve().parents[1] / "data" / "derived"


def test_exact_binomial_band():
    # The 0.5% and 99.5% quantiles of Binomial(2000, 0.05) are 76 and 126: [3.80%, 6.30%].
    # At 4,000: 165 and 236, [4.125%, 5.90%] (ADR 0005 §5). The normal approximation gave
    # [3.74, 6.26] at 2,000.
    assert g1.binom_band(2000) == (0.038, 0.063)
    assert g1.binom_band(4000) == (0.04125, 0.059)
    # At 10,000 (the re-measure count): 445 and 557, [4.45%, 5.57%]; the normal approximation's top,
    # 0.05 + 2.576 sqrt(0.0475 / 10000) = 5.561%, rounds up to the next count, 557.
    assert g1.binom_band(10000) == (0.0445, 0.0557)


def test_stale_psi_hand_worked():
    # rho_m = 0.10, c1 = 0.05: 0.05 psi^2 * 0.10 - 0.10 psi + 0.05 = 0 ->
    # psi = (0.1 - sqrt(0.01 - 4 * 0.1 * 0.0025)) / (2 * 0.1 * 0.05) = (0.1 - 0.0948683)/0.01 = 0.513167.
    psi = g1.stale_psi(0.10, 0.05)
    assert psi == pytest.approx((0.1 - np.sqrt(0.009)) / 0.01, abs=1e-12)
    assert 0.10 * psi / (1 + 0.10 * psi ** 2) == pytest.approx(0.05, abs=1e-12)
    # Beyond the largest attainable c1, sqrt(0.1)/2 = 0.158: capped at psi = 1/sqrt(rho_m).
    assert g1.stale_psi(0.10, 0.2) == pytest.approx(1 / np.sqrt(0.1)) and g1.stale_psi(0.1, -0.02) == 0.0


def test_detectable_shift_interpolates():
    # Power 0.7 at 0.02 and 0.9 at 0.03: 80% at 0.02 + (0.8 - 0.7) / (0.9 - 0.7) * 0.01 = 0.025.
    assert g1.detectable_shift([0.01, 0.02, 0.03], [0.3, 0.7, 0.9]) == pytest.approx(0.025)
    assert g1.detectable_shift([0.01, 0.02], [0.3, 0.5]) is None
    assert g1.detectable_shift([0.01, 0.02], [0.85, 0.99]) == 0.01


def bare_design(n_firms=40, T=3000) -> g1.Design:
    """A design with firms and no events: only the DGP's moments are read from it."""
    z = np.zeros((0, 71), int)
    return g1.Design([f"F{i}" for i in range(n_firms)], np.arange(n_firms) % 4, T, 0, np.zeros(0, int), z,
                     z.astype(bool), z.astype(bool), np.zeros(0, int), np.zeros(0), np.zeros(0, object),
                     np.zeros(0, int), {}, {}, {}, np.zeros(n_firms), 0.07)


def test_the_dgp_moments_are_the_ones_calibrate_inverts():
    # Random walk, noise n = 0.5, kappa = 0.3, rho_m = 0.1, no sector part, sigma the same for all.
    # Changes: latent sigma eta_t plus noise n sigma (e_t - e_{t-1}), e = sqrt(.7) eps_f + sqrt(.3) nu.
    #   var = sigma^2 (1 + 2 n^2) = 1.5 sigma^2
    #   own lag 1: -n^2 = -0.25 -> acf -0.25 / 1.5 = -0.1667
    #   same date, two firms: rho_m + 2 kappa n^2 = 0.1 + 0.15 = 0.25 -> corr 0.25 / 1.5 = 0.1667
    #   firm i at t, firm j at t-1: -kappa n^2 = -0.075 -> corr -0.05 = kappa * acf
    d = bare_design()
    x, _ = g1.generate(np.random.default_rng(11), d, dict(phi=1.0, rho_m=0.10, noise=0.5, noise_common=0.3))
    dx = np.diff(x, axis=1)
    z = dx / dx.std(axis=1, keepdims=True)
    acf1 = float((z[:, 1:] * z[:, :-1]).sum() / (z[:, :-1] ** 2).sum())
    assert acf1 == pytest.approx(-0.25 / 1.5, abs=0.01)
    every = np.zeros(z.shape[0])                       # one group: every pair counts as "across"
    assert g1._mean_pair_corr(z, every, True, 20) == pytest.approx(0.25 / 1.5, abs=0.01)
    assert g1.lag1_cross_corr(z, 20) == pytest.approx(-0.05, abs=0.01)
    # calibrate() must invert these three moments back to the DGP's parameters:
    #   noise^2 = -rho1 / (1 + 2 rho1) = 0.1667 / 0.6667 = 0.25, kappa = c1 / rho1 = -0.05 / -0.1667 = 0.3,
    #   rho_m = corr infl - 2 kappa n^2 = 0.1667 * 1.5 - 2 * 0.3 * 0.25 = 0.1.
    # The other inputs only feed other parameters; they are given flat stand-ins.
    flat = [np.array([0.0, 0.1, -0.1])] * z.shape[0]
    cal = g1.calibrate(z, d.firm_sector, acf1, [np.arange(30.0)], flat, flat, flat, flat, 20)
    assert cal["params"]["noise"] == pytest.approx(0.5, abs=0.03)
    assert cal["params"]["noise_common"] == pytest.approx(0.3, abs=0.06)
    assert cal["params"]["rho_m"] == pytest.approx(0.1, abs=0.03)
    assert cal["params"]["psi"] == 0.0 and cal["params"]["rho_s"] == pytest.approx(0.0, abs=0.03)


def synthetic_design(seed=4, n_firms=40, beta=0.4) -> g1.Design:
    """n_firms firms, each reporting once in each of 7 seasons 63 sessions apart, day 0 spread
    over 20 sessions; baselines [-60, -22] minus the firm's other events' [-21, +10] zones;
    every firm's true market beta `beta`."""
    rng = np.random.default_rng(seed)
    seasons = 7
    firm, day0, season = [], [], []
    for f in range(n_firms):
        for s in range(seasons):
            firm.append(f)
            day0.append(70 + 63 * s + int(rng.integers(0, 20)))
            season.append(f"S{s}")
    firm, day0 = np.array(firm), np.array(day0)
    sess = day0[:, None] + abnormal.REL_DAYS[None]
    usable = np.ones(sess.shape, bool)
    inb = np.zeros(sess.shape, bool)
    for i in range(firm.size):
        others = day0[(firm == firm[i]) & (np.arange(firm.size) != i)]
        for j, rel in enumerate(abnormal.REL_DAYS):
            t = sess[i, j]
            inb[i, j] = -60 <= rel <= -22 and not any(o - 21 <= t <= o + 10 for o in others)
    rows = np.arange(firm.size)
    return g1.build_design([f"F{i}" for i in range(n_firms)], np.arange(n_firms) % 4, sess, usable, inb, firm,
                           day0, day0, np.array(season, object), np.arange(n_firms)[firm] % 4,
                           {"H1": rows, "H2": rows}, np.full(n_firms, float(beta)), 0.07)


def test_a_seeded_smoke_run_catches_date_clusters_for_a_ramp():
    # ADR 0005 §5's mutation table: day-0 clusters for a ramp rejected 32-36% at rho = 0.1
    # (§2g, D1-D3). On this 280-event design under D1, 120 seeded replications: the date-clustered
    # RUNUP row is far above 5% while the two-way season x firm row is not.
    d = synthetic_design()
    st = dict(params.load()["stats"])
    res = [g1.replicate((d, dict(phi=1.0, rho_m=0.10), d.sets, 7000 + r, 0.05, st, False)) for r in range(120)]
    rates = g1.rates(res)
    assert rates["H2"]["_primary"] == "twoway_season_t"          # 7 seasons of 40: balanced
    assert rates["H2"]["date_cluster_t"] > 0.15
    assert rates["H2"]["twoway_season_t"] < 0.12
    assert rates["H1"]["twoway_date_t"] < 0.12


@pytest.fixture(scope="module")
def committed_results():
    return store.read_table(DERIVED / "results.parquet", store.committed_schema(schema.RESULTS))


def test_the_committed_gate_decides_the_roles(committed_results):
    # The calibrated design is binding: a primary at most the band's top (6.30% at 2,000) stays
    # primary; one above it leaves the family and its row is exploratory (ADR 0005 §5).
    r = committed_results
    cal = r[(r["family"] == "validation") & (r["measure"] == "g1:calibrated") & (r["role"] == "primary")]
    assert sorted(cal["hypothesis"]) == ["H1", "H2", "H3", "H4"] and (cal["n"] == 2000).all()
    _, hi = g1.binom_band(2000)
    for row in cal.itertuples(index=False):
        tested = r[(r["family"] == "event_test") & (r["hypothesis"] == row.hypothesis) & (r["adjustment"] == "market")
                   & (r["statistic"] == row.statistic) & (r["subgroup_value"] == "all")]
        assert len(tested) == 1
        assert tested["role"].iloc[0] == ("primary" if row.estimate <= hi else "exploratory"), row.hypothesis
        assert (tested["p_holm"].notna().iloc[0]) == (row.estimate <= hi)


def test_estimate_re_estimates_beta_from_the_simulated_data():
    # ADR 0005 §5: every input is estimated in every replication, as the production run does.
    # The DGP adds beta_true * m to each firm. Simulate with beta 0.9, then hand estimate() (which
    # evaluate() calls) a design that says beta_true = 0.2, a planted wrong value: the beta it
    # uses must be the data's 0.9. Its sampling error is about 0.035 / (0.07 sqrt(250)) = 0.03
    # per firm (residual sd of a change / (sd of dln VIX x sqrt(clean changes))), so 0.1 is >3 se.
    d = synthetic_design(beta=0.9)
    x, m = g1.generate(np.random.default_rng(3), d, dict(phi=1.0, rho_m=0.10, noise=0.5))
    planted = dataclasses.replace(d, beta_true=np.full(len(d.firms), 0.2))
    beta = g1.estimate(planted, x, m)["beta"]
    assert np.abs(beta - 0.9).max() < 0.1
    # One beta per firm: every event of a firm gets the same value.
    assert all(np.ptp(beta[d.firm == f]) == 0 for f in range(len(d.firms)))


@pytest.fixture(scope="module")
def round_trip_inputs():
    # 400 firms x 7 seasons = 2,800 events, simulated from known parameters, the inputs
    # re-estimated by estimate() and passed to calibrate_from(), the function the production run
    # calibrates with (stats/run.py calibrate_on).
    d = synthetic_design(n_firms=400)
    truth = dict(phi=0.9, rho_m=0.10, noise=0.5, jump_k=3.0, firm_fx=0.03)
    x, m = g1.generate(np.random.default_rng(0), d, truth)
    est = g1.estimate(d, x, m)
    e = np.where(est["clean"] & np.isfinite(est["e"]), est["e"], np.nan)
    crush = est["e"][:, abnormal.col(0)]
    return (e, est["s"], est["aliv"], d.in_baseline, d.sess, d.firm, d.firm_sector[d.firm]), crush


@pytest.fixture(scope="module")
def round_trip(round_trip_inputs):
    args, crush = round_trip_inputs
    return g1.calibrate_from(*args, crush)


def test_calibrate_round_trip_recovers_phi_from_the_side_it_errs_on(round_trip):
    # True phi 0.90. A plain pooled AR(1) of ~30-session demeaned baselines is biased down by
    # Kendall's (1 + 3 phi)/L = 0.12, and quote noise in the lag-0 sum biases it down further:
    # measured over seeds 0-4 the plain estimate reads 0.76-0.77, the noise-corrected one without
    # Kendall's step 0.83-0.84, and with both corrections 0.956-0.965. The estimator errs HIGH
    # (less mean reversion than the truth), which makes the calibrated design the stricter one
    # for the ramps; this is the gap the milestone-3 review measured on real data (corrected
    # 0.98 vs a simulated 0.999). Dropping Kendall's step would read 0.84 here.
    ms = round_trip["measured"]
    assert 0.90 < round_trip["params"]["phi"] < 0.99
    assert ms["ar_levels_raw"] < 0.80


def test_calibrate_round_trip_recovers_the_company_effect(round_trip):
    # True sd of the company mean crush 0.03. Each company's mean crush over its 7 events also
    # carries sampling noise: per-event crush variance ~ 0.03^2 (1.05 + 2 x 0.25 + 9) = 0.0095
    # (AR changes, quote noise, the day-0 jump), / 7 = 0.00135. Without the correction the sd
    # would read sqrt(0.0009 + 0.00135) = 0.047 (measured 0.045-0.050 over seeds 0-4); with it
    # 0.025-0.034.
    assert round_trip["params"]["firm_fx"] == pytest.approx(0.03, abs=0.008)


def test_calibrate_round_trip_recovers_the_day0_jump(round_trip):
    # True jump 3 sigma on each day 0: variance ratio of CRUSH / s_i around company means
    # 1 + 9 / (1 + 2 n^2) at a random walk, and jump_k = sqrt((ratio - 1)(1 + 2 n^2)) gives 3
    # back (measured 3.10-3.16 over seeds 0-4). A DGP that drops the jumps reads 0.28-0.46.
    assert round_trip["params"]["jump_k"] == pytest.approx(3.0, abs=0.4)
    assert round_trip["measured"]["day0_variance_ratio"] > 5


def test_calibrate_round_trip_recovers_the_scale(round_trip):
    # The DGP's sigma is 0.03 here (SIG0, no dispersion). A change has variance
    # sigma^2 (2/(1 + phi) + 2 n^2), so sig0 = exp(mean ln s_i) / sqrt(that factor) gives 0.03
    # back (measured 0.0294-0.0296 over seeds 0-2); exp(mean ln s_i) itself is about 0.037.
    assert round_trip["params"]["sig0"] == pytest.approx(0.03, abs=0.002)


def test_oversized_and_withhold():
    # ADR 0005 §4 (dated notes of both fix rounds): a robustness statistic whose calibrated G1 rate
    # is above the band's top for the replications it was measured on keeps its estimate, se and
    # statistic and loses its p-value and interval. Exactly the top is not above; a primary is the
    # gate's business, not this rule's; date_cluster_t is G1's rejected mutant, never a reported row.
    # 6.35% and 6.30% on 2,000 are within one point of 6.30%, so they are decided on 10,000: 5.58%
    # is above 5.57%, 5.57% is not.
    report = {"reps": 2000, "rates": {"calibrated": {
        "H1": {"_primary": "twoway_date_t", "twoway_date_t": 0.07, "cluster_date_t": 0.0635, "bmp_t": 0.063,
               "patell_z": 0.5},
        "H2": {"_primary": "rad_season_p", "rad_season_p": 0.004, "date_cluster_t": 0.2, "cluster_season_t": 0.01}}},
        "remeasured": {"reps": 10000, "rates": {"H1": {"cluster_date_t": 0.0558, "bmp_t": 0.0557}}}}
    assert results.oversized(report, 0.05) == {
        ("H1", "cluster_date_t"): {"rate": 0.0558, "reps": 10000, "bar": 0.0557, "oversized": True},
        ("H1", "patell_z"): {"rate": 0.5, "reps": 2000, "bar": 0.063, "oversized": True}}
    r = dict(p_value=0.01, ci_lo=-1.0, ci_hi=1.0, estimate=0.5, se=0.1, stat=5.0, p_holm=None)
    assert results.withhold(r) == dict(r, p_value=None, ci_lo=None, ci_hi=None)


def test_the_committed_rows_withhold_exactly_the_oversized_statistics(committed_results):
    # The committed rows against the rule, applied by hand here: above 6.30% on 2,000, or, for a
    # rate within one point of 6.30%, above 5.57% on its 10,000 re-measured replications.
    r = committed_results
    _, hi = g1.binom_band(2000)
    hi10 = g1.binom_band(10000)[1]
    cal = r[(r["family"] == "validation") & (r["measure"] == "g1:calibrated") & (r["role"] == "robustness")
            & (r["statistic"] != "date_cluster_t")]
    rem = r[(r["family"] == "validation") & (r["measure"] == "g1:calibrated_remeasured")]
    again = {(h, s): x for h, s, x in zip(rem["hypothesis"], rem["statistic"], rem["estimate"])}
    assert (rem["n"] == 10000).all()
    over = set()
    for h, s, x in zip(cal["hypothesis"], cal["statistic"], cal["estimate"]):
        if abs(x - hi) <= 0.01 + 1e-12:
            assert (h, s) in again, (h, s)
            over |= {(h, s)} if again[(h, s)] > hi10 else set()
        elif x > hi:
            over.add((h, s))
    rob = r[(r["family"] == "event_test") & (r["role"] == "robustness") & (r["adjustment"] == "market")
            & (r["subgroup_value"] == "all")]
    assert over, "the calibrated design names no oversized robustness row"
    for row in rob.itertuples(index=False):
        if (row.hypothesis, row.statistic) in over:
            assert pd.isna(row.p_value) and pd.isna(row.ci_lo) and pd.notna(row.estimate), row.statistic
        else:
            assert pd.notna(row.p_value), (row.hypothesis, row.statistic)


def test_the_committed_season_cut_row_is_the_holm_counterfactual(committed_results):
    # H2's primary sits on the rad_season_p floor 2/2^G; the season-cut row merges the last season
    # into the one before (G - 1) and its p_holm is Holm over the declared family with that p.
    r = committed_results
    ev = r[(r["family"] == "event_test") & (r["adjustment"] == "market")]
    prim = ev[(ev["role"] == "primary")].set_index("hypothesis")
    cut = ev[ev["subgroup_key"] == "season_cut"]
    assert len(cut) == 1 and cut["hypothesis"].iloc[0] == "H2"
    c = cut.iloc[0]
    g = int(prim.loc["H2", "n_clusters"])
    assert prim.loc["H2", "p_value"] == 2 / 2 ** g and int(c["n_clusters"]) == g - 1
    assert c["statistic"] == "rad_season_p" and c["p_value"] >= 2 / 2 ** (g - 1)
    pv = {h: (prim.loc[h, "p_value"] if h in prim.index else None) for h in params.load()["stats"]["holm_family"]}
    pv["H2"] = c["p_value"]
    assert c["p_holm"] == pytest.approx(multiple.holm(pv)["H2"], abs=1e-15)


def test_generate_uses_the_calibrated_scale():
    # sigma_f = sig0 e^{N(0, sig_disp)}: with sig0 = 0.06, no noise, no dispersion and a random walk,
    # every one-session change of a firm has sd 0.06 (the stress designs' default is 0.03).
    d = bare_design(n_firms=20, T=2000)
    x, _ = g1.generate(np.random.default_rng(5), d, dict(phi=1.0, sig0=0.06))
    assert np.diff(x, axis=1).std() == pytest.approx(0.06, rel=0.02)
    x, _ = g1.generate(np.random.default_rng(5), d, dict(phi=1.0))
    assert np.diff(x, axis=1).std() == pytest.approx(g1.SIG0, rel=0.02)


def test_season_cut_rows_merge_the_last_season_into_the_one_before():
    # Eight seasons of a RUNUP set, 10 events each, the last (S8) 12; values of mixed sign by season
    # so that WHICH two seasons are merged changes the randomisation p. The counterfactual row
    # merges S8 into S7 (G = 7; 22 against 10 events, unbalanced, so rad_season_p stays the
    # statistic), and its p_holm is Holm over the family with that p, the others as given.
    days = [date(2025, 1, 2) + timedelta(days=k) for k in range(400)]
    sess = calendar.Sessions(days)
    season, d0, a = [], [], []
    signs = [1.0, -0.4, 0.9, 0.2, -0.3, 0.8, 0.5, -0.6]
    for k, sg in enumerate(signs):
        for j in range(12 if k == 7 else 10):
            season.append(f"S{k + 1}")
            d0.append(days[40 * k + j])
            a.append(sg + 0.01 * j)
    ev = pd.DataFrame({"sample": "daily", "eligible_runup": True, "runup_cboe": a, "day0_session": d0,
                       "season": season, "security_id": [f"F{j % 10}" for j in range(len(a))]})
    f = inputs.Frame(ev, None, None, None, None, None, None, None, None, sess)
    st = dict(params.load()["stats"])
    prim = results.row(family="event_test", hypothesis="H2", role="primary", measure="runup", statistic="rad_season_p",
                       sample="daily", subgroup_key="all", subgroup_value="all", adjustment="market", n=82,
                       n_clusters=8, p_value=0.3, params_hash="h", code_commit="c")
    h1 = dict(prim, hypothesis="H1", statistic="twoway_date_t", p_value=0.001)
    family = ["H1", "H2", "H3"]
    got = results.season_cut_rows(f, st, [h1, prim], family, dict(params_hash="h", code_commit="c"))
    assert len(got) == 1
    r = got[0]
    cut = np.array(season, dtype=object)
    cut[cut == "S8"] = "S7"
    want = clustering.rademacher_p(np.array(a), cut)
    assert (r["subgroup_key"], r["subgroup_value"], r["statistic"]) == ("season_cut", "S8_into_S7", "rad_season_p")
    assert r["n_clusters"] == 7 and r["p_value"] == want["p_value"] and r["role"] == "robustness"
    # Merging the first two seasons instead would give another p here.
    first = np.array(season, dtype=object)
    first[first == "S1"] = "S2"
    assert clustering.rademacher_p(np.array(a), first)["p_value"] != want["p_value"]
    assert r["p_holm"] == multiple.holm({"H1": 0.001, "H2": want["p_value"], "H3": None})["H2"]
    # A primary that is not rad_season_p gets no counterfactual.
    assert results.season_cut_rows(f, st, [h1, dict(prim, statistic="twoway_season_t")], family, {}) == []


def test_the_day0_jump_does_not_read_the_mean_of_the_tested_value(round_trip_inputs, round_trip):
    # Second fix round (delta review defect 4): the gate simulates the null, so its jump must not
    # depend on the mean of the tested value (the effect under test). The day-0 ratio is read from
    # (A_i - mean A) / s_i around company means; s_i varies within a company, so with A_i / s_i a
    # common shift c would add c (1/s_i - mean over the company of 1/s_i) to the deviations. Here a
    # shift of -0.2 (a crush the size of H1's) leaves the ratio, the jump and the company effect
    # unchanged to 1e-9; read from A_i / s_i the ratio would read 7.79 instead of 7.20 here
    # (measured on this fixture's data).
    args, crush = round_trip_inputs
    shifted = g1.calibrate_from(*args, crush - 0.2)
    for k in ("day0_variance_ratio", "firm_crush_sd"):
        assert shifted["measured"][k] == pytest.approx(round_trip["measured"][k], abs=1e-9), k
    assert shifted["params"]["jump_k"] == pytest.approx(round_trip["params"]["jump_k"], abs=1e-9)


def two_series(beta_cm30=0.9, beta_sd=0.1, seed=3):
    """The synthetic design (one sigma_d cell in 20 missing on the second series), a first series
    simulated at beta 0.9, and a second design whose DGP loads ln VIX with beta 0.1."""
    d = synthetic_design(beta=beta_cm30)
    gone = np.random.default_rng(1).random(d.usable.shape) < 0.05
    d2 = dataclasses.replace(d, usable=d.usable & ~gone, beta_true=np.full(len(d.firms), float(beta_sd)))
    x, m = g1.generate(np.random.default_rng(seed), d, dict(phi=1.0, rho_m=0.10, noise=0.5))
    return d, d2, x, m


def test_the_second_series_shares_vix_and_takes_the_cm30_beta():
    # Second fix round (delta review defect 7): production computes DSIGMA_D = dln sigma_d - beta
    # dln VIX with the beta of the cm30 series (panel/window.py measures()), and one VIX. So the
    # second series is simulated on the first series' ln VIX path and adjusted with the first
    # series' beta (about 0.9 here), not with its own (about 0.1: the sigma_d DGP loads 0.1).
    d, d2, x, m = two_series()
    est = g1.estimate(d, x, m)
    p2 = dict(phi=1.0, rho_m=0.10, noise=0.5)
    x2, m2, est2 = g1.second_series(11, d, est, d2, p2, m)
    assert np.array_equal(m2, m)
    want_x2, _ = g1.generate(np.random.default_rng([11, 2]), d2, p2, m=m)
    assert np.array_equal(x2, want_x2)
    assert np.array_equal(est2["beta"], est["beta"]) and np.abs(est["beta"] - 0.9).max() < 0.1
    X2 = np.where(d2.usable, x2[d2.firm[:, None], d2.sess], np.nan)
    want = abnormal.abnormal_changes(X2, m[d2.sess], est["beta"])
    assert np.array_equal(est2["e"], want, equal_nan=True)
    assert np.isnan(est2["e"][~d2.usable]).all() and np.isfinite(est2["e"][d.usable & ~d2.usable]).sum() == 0
    own = g1.estimate(d2, x2, m2)["beta"]
    assert np.abs(own - 0.1).max() < 0.1                     # what re-estimating on sigma_d would use


def test_replicate_evaluates_h4_on_the_second_series_with_the_cm30_beta():
    # [d02 W7] H4's decisions come from the second series: its DGP has a day-0 shift of 0.5 (about
    # 15 sd of a change) and the first series none, so H4 rejects in every replication while H1, the
    # same events on the first series, rejects in at most 2 of 10 (5% each: P(> 2) = 1.2%).
    d, d2, _, _ = two_series()
    st = dict(params.load()["stats"])
    rows = np.arange(d.firm.size)
    p = dict(phi=1.0, rho_m=0.10, noise=0.5)
    out = [g1.replicate((d, p, {"H1": rows}, 500 + r, 0.05, st, False, (d2, dict(p, mu=0.5, shift_on="crush"),
                                                                          {"H4": rows}))) for r in range(10)]
    assert all(o["H4"]["twoway_date_t"] for o in out)
    assert sum(o["H1"]["twoway_date_t"] for o in out) <= 2
    # And with the cm30 beta: H4's robust decisions are those of evaluate() on second_series()'s inputs,
    # which differ from the decisions on the sigma_d series' own beta in at least one replication here
    # (the sigma_d DGP loads ln VIX with 0.1, the cm30 beta is 0.9).
    differs = 0
    for r in range(6):
        seed = 900 + r
        got = g1.replicate((d, p, {}, seed, 0.05, st, True, (d2, p, {"H4": rows})))["H4"]
        x, m = g1.generate(np.random.default_rng(seed), d, p)
        x2, m2, est2 = g1.second_series(seed, d, g1.estimate(d, x, m), d2, p, m)
        assert got == g1.evaluate(d2, x2, m2, {"H4": rows}, 0.05, st, True, est=est2)["H4"]
        differs += got != g1.evaluate(d2, x2, m2, {"H4": rows}, 0.05, st, True)["H4"]
    assert differs >= 1


def test_near_bar_and_size_verdicts_re_measure_within_one_point():
    # Second fix round (ADR 0005 §4 dated note): within one point of the 2,000 bar (6.30%) means
    # 5.30% to 7.30%, ends included. 7.29% and 5.30% are in; 5.29% and 7.31% are out; a primary and
    # date_cluster_t never are.
    cal = {"H1": {"_primary": "twoway_date_t", "twoway_date_t": 0.063, "cluster_date_t": 0.0729, "bmp_t": 0.053,
                  "kp_ow_t": 0.0529, "date_cluster_t": 0.06},
           "H4": {"_primary": "twoway_date_t", "twoway_date_t": 0.05, "gen_sign_z": 0.0645, "rank_t": 0.0731}}
    assert g1.near_bar(cal, 2000) == {"H1": ["cluster_date_t", "bmp_t"], "H4": ["gen_sign_z"]}
    with pytest.raises(ValueError, match="not re-measured"):
        g1.size_verdicts(cal, 2000, 0.05)
    rem = {"reps": 10000, "rates": {"H1": {"cluster_date_t": 0.0558, "bmp_t": 0.0557}, "H4": {"gen_sign_z": 0.0606}}}
    v = g1.size_verdicts(cal, 2000, 0.05, rem)
    assert set(v) == {("H1", "cluster_date_t"), ("H1", "bmp_t"), ("H1", "kp_ow_t"), ("H4", "gen_sign_z"),
                      ("H4", "rank_t")}
    # Decided on 10,000 against 5.57%: 5.58% withheld, 5.57% kept, and 6.06% withheld although it is
    # below the 2,000 bar.
    assert v[("H1", "cluster_date_t")] == {"rate": 0.0558, "reps": 10000, "bar": 0.0557, "oversized": True}
    assert v[("H1", "bmp_t")]["oversized"] is False and v[("H1", "bmp_t")]["reps"] == 10000
    assert v[("H4", "gen_sign_z")] == {"rate": 0.0606, "reps": 10000, "bar": 0.0557, "oversized": True}
    # Outside the margin: decided on 2,000 against 6.30%.
    assert v[("H1", "kp_ow_t")] == {"rate": 0.0529, "reps": 2000, "bar": 0.063, "oversized": False}
    assert v[("H4", "rank_t")] == {"rate": 0.0731, "reps": 2000, "bar": 0.063, "oversized": True}
