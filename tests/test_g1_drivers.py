# Tests for gate G1's H5-H7 part (stats/g1_drivers.py, the wiring in stats/run.py; ADR 0005 §5),
# on made-up designs: the H7 null process and its calibration, the H5/H6 evaluation and its power
# shortcut, the seeded replication, g1.generate's pinned firm scale, and the pure wiring (designs,
# merge into the H1-H4 report, the gate, the seed blocks, the design built from a stats Frame).
#
# Mutations this module must catch (each applied to a scratch copy, the test seen to fail, the file
# restored and its SHA-256 checked; milestone page appendix):
#   - std_t not scaled to variance 1
#   - h7_generate's firm multiplier without the -tau^2/2 (mean exp(tau^2/2), not 1)
#   - calibrate_h7 reading the level of r^2 (no rescaling to mean square 1)
#   - calibrate_h7's rho without the pair count (sum of products over n_t^2)
#   - evaluate_h56 testing the twin on the market-adjusted crush
#   - the power shortcut (b_j + beta)/se_j with se from the one-way covariance
#   - replicate drawing H7 from the cm30 series' generator
#   - g1.generate ignoring sig_firm
#   - g1.generate with sig_firm skipping the random draw (the stream shifts)
#   - merge not merging a design's H5-H7 rates (they replace H1-H4's)
#   - merge's gate keeping only H1-H4
#   - driver_report's gate with < instead of <= at the band's top
#   - driver_tasks re-using a block of the H1-H4 run
#   - driver_design taking the Frame rows instead of the design's event indices
#   - sig_firm not centred on the mean over firms
#   - calibrate_h7's rho correction exp(+tau^2/4) with the wrong sign (the milestone-4 review's
#     surviving mutant M09: the round trip at tau 0.3 could not see it)

import numpy as np
import pytest

from earnings_vol.stats import drivers, g1, g1_drivers, regression, run
from test_stats_wiring import DP, ST, synthetic_frame


def _design(n=4000, n_dates=400, n_firms=50, seed=0):
    rng = np.random.default_rng(seed)
    return g1_drivers.DriverDesign(np.arange(3), np.ones((3, 1)), {}, None, None, np.zeros(1),
                                   rng.exponential(0.004, n) + 1e-4, rng.integers(0, n_dates, n).astype(str),
                                   rng.integers(0, n_firms, n).astype(str), 0)


def test_std_t_has_variance_one():
    rng = np.random.default_rng(1)
    for nu in (5.0, 10.0, np.inf):
        v = g1_drivers.std_t(rng, nu, 400_000)
        assert v.var() == pytest.approx(1.0, abs=0.03), nu        # nu = 5: var t = 5/3 before scaling


def test_h7_null_holds_exactly_on_average():
    # E[r^2 | x] = x: over 400 replications of 4,000 events the mean of r^2/x is 1 within 0.01, with
    # heavy tails (nu 6), a same-date correlation (0.2) and a firm multiplier (tau 0.4).
    dd = _design()
    p = {"nu": 6.0, "rho_d": 0.2, "firm_sd": 0.4}
    ratio = [np.mean(g1_drivers.h7_generate(np.random.default_rng(k), dd, p) ** 2 / dd.x7) for k in range(400)]
    assert np.mean(ratio) == pytest.approx(1.0, abs=0.01)


def test_calibrate_h7_round_trip_and_scale_free():
    # Simulated at nu 10, rho 0.2, tau 0.3 on 40,000 events (400 dates, 200 firms), the calibration
    # reads them back roughly (measured: nu 10.2, rho 0.218, tau 0.290); and it does not read the level of r^2 (the tested b): r scaled by 2
    # gives the same calibration.
    dd = _design(n=40_000, n_dates=400, n_firms=200, seed=4)
    r = g1_drivers.h7_generate(np.random.default_rng(9), dd, {"nu": 10.0, "rho_d": 0.2, "firm_sd": 0.3})
    cal = g1_drivers.calibrate_h7(r, dd.x7, dd.date7, dd.firm7)
    assert cal["params"]["rho_d"] == pytest.approx(0.2, abs=0.03)
    assert cal["params"]["firm_sd"] == pytest.approx(0.3, abs=0.08)
    assert 6.0 < cal["params"]["nu"] < 25.0
    twice = g1_drivers.calibrate_h7(2 * r, dd.x7, dd.date7, dd.firm7)
    assert twice["params"] == pytest.approx(cal["params"]) and twice["measured"] == pytest.approx(cal["measured"])
    # Three events per date (n_t (n_t - 1) = 6 pairs, not n_t^2 = 9): rho still read back.
    d3 = _design(n=30_000, n_dates=10_000, n_firms=200, seed=6)
    d3.date7[:] = (np.arange(30_000) // 3).astype(str)
    r3 = g1_drivers.h7_generate(np.random.default_rng(8), d3, {"nu": 10.0, "rho_d": 0.2, "firm_sd": 0.0})
    assert g1_drivers.calibrate_h7(r3, d3.x7, d3.date7, d3.firm7)["params"]["rho_d"] == pytest.approx(0.2, abs=0.03)
    # Normal moves, no dependence: rho 0, tau 0, nu inf (or very large).
    rn = g1_drivers.h7_generate(np.random.default_rng(2), dd, {"nu": np.inf, "rho_d": 0.0, "firm_sd": 0.0})
    c0 = g1_drivers.calibrate_h7(rn, dd.x7, dd.date7, dd.firm7)["params"]
    assert c0["rho_d"] <= 0.01 and c0["firm_sd"] <= 0.05 and c0["nu"] > 30


def test_calibrate_h7_reads_the_same_rho_whatever_the_firm_dispersion():
    # Fix R3 (milestone-4 review, mutant M09). A firm multiplier m_f = exp(tau N - tau^2/2) shrinks the
    # same-date product of standardised moves by E[sqrt(m_f m_g)] = exp(-tau^2/4); calibrate_h7 undoes
    # that with exp(+tau^2/4). The same made-up design and the same seed (the same date shocks) at
    # tau 0 and tau 0.8 must give the same rho, about 0.3 (measured: 0.300 and 0.293, tau read as 0.77; the
    # raw product falls from 0.300 to 0.253);
    # with the sign flipped the tau-0.8 read is about 0.22, 0.08 below. The paired design removes the
    # date-shock noise that made the tau-0.3 round trip too loose (+-0.03 against a 2% effect).
    dd = _design(n=120_000, n_dates=1200, n_firms=300, seed=4)
    got = {}
    for tau in (0.0, 0.8):
        r = g1_drivers.h7_generate(np.random.default_rng(14), dd, {"nu": 10.0, "rho_d": 0.3, "firm_sd": tau})
        got[tau] = g1_drivers.calibrate_h7(r, dd.x7, dd.date7, dd.firm7)
    assert got[0.0]["params"]["rho_d"] == pytest.approx(0.3, abs=0.02)
    assert got[0.8]["params"]["firm_sd"] == pytest.approx(0.8, abs=0.1)
    assert got[0.8]["measured"]["rho_d_raw"] < got[0.0]["measured"]["rho_d_raw"] - 0.03       # the shrinkage is real
    assert got[0.8]["params"]["rho_d"] == pytest.approx(got[0.0]["params"]["rho_d"], abs=0.02)


def test_evaluate_h7_power_is_r_squared_scaled():
    # The power at b reads the Wald test of b * r^2: the same as simulating variance b x.
    dd = _design(n=600, n_dates=120, n_firms=40, seed=3)
    r = g1_drivers.h7_generate(np.random.default_rng(5), dd, {"nu": np.inf, "rho_d": 0.0, "firm_sd": 0.0})
    out, pw = g1_drivers.evaluate_h7(dd, r, 0.05, (0.5,))
    X = np.column_stack([np.ones(dd.x7.size), dd.x7])
    fit = regression.fit(0.5 * r ** 2, X)
    w = regression.wald_test(fit, regression.covariance(fit, X, dd.date7, dd.firm7), np.eye(2), np.array([0.0, 1.0]))
    assert pw["H7"][0.5] == bool(w["p_value"] <= 0.05)
    assert out["H7"]["_primary"] == "twoway_date_wald" and set(out["H7"]) == {"_primary", "twoway_date_wald",
                                                                              "cluster_date_wald"}


@pytest.fixture(scope="module")
def frame():
    return synthetic_frame()


@pytest.fixture(scope="module")
def built(frame):
    des, cal, _, _ = run.design_and_calibration(frame, ST)
    dd, cal7 = run.driver_design(frame, des, ST, DP)
    return des, cal, dd, cal7


def test_driver_design_maps_the_model_into_the_g1_design(frame, built):
    des, cal, dd, cal7 = built
    sets_f, union = run.primary_sets(frame)
    m = drivers.model_inputs(frame, drivers.PRIMARY, tuple(DP["surprise_winsor"]))
    assert (union[dd.rows] == m["rows"]).all()
    # With event 0 in no primary set, the design's events are the Frame rows 1, 2, ...: H5's events must
    # be mapped to the design's indices, not used as Frame rows.
    ev = frame.ev.copy()
    ev.loc[0, ["eligible_crush", "eligible_runup", "eligible_persist_10"]] = False
    f2 = type(frame)(ev, *[getattr(frame, k) for k in ("sess", "usable", "in_baseline", "e", "aliv", "aliv0",
                                                        "sigma_d", "M", "sessions")])
    d2, _, _, _ = run.design_and_calibration(f2, ST)
    dd2, _ = run.driver_design(f2, d2, ST, DP)
    _, union2 = run.primary_sets(f2)
    m2 = drivers.model_inputs(f2, drivers.PRIMARY, tuple(DP["surprise_winsor"]))
    assert union2[0] == 1 and (union2[dd2.rows] == m2["rows"]).all() and dd2.rows[0] == 0
    assert dd.X == pytest.approx(m["X"]) and dd.j == {"H5": 1, "H6": 2}
    # sig_firm: each firm's mean ln s_i over H1's events, centred on the mean over firms.
    ls = np.log(frame.ev["s_abn_cboe"].to_numpy(float))
    firm = frame.ev["security_id"].to_numpy(object)
    means = np.array([ls[sets_f["H1"]][firm[sets_f["H1"]] == f].mean() for f in des.firms])
    assert dd.sig_firm == pytest.approx(means - means.mean())
    h7 = drivers.h7_inputs(frame)
    assert dd.x7 == pytest.approx(h7["x"]) and dd.n_floored == 0
    assert set(cal7["params"]) == {"nu", "rho_d", "firm_sd"}


def test_sig_firm_hand_worked():
    # Firm a: ln s 1, 3 -> 2; firm b: 4 -> 4; mean over firms 3: a -1, b +1, c (no event) 0.
    got = g1_drivers.sig_firm(["a", "b", "c"], ["a", "a", "b"], [1.0, 3.0, 4.0])
    assert got.tolist() == [-1.0, 1.0, 0.0]


def test_generate_pins_the_firm_scale_without_moving_the_stream(built):
    des, cal, dd, _ = built
    p = dict(phi=1.0, rho_m=0.1, noise=0.5, sig0=0.03)
    x0, m0 = g1.generate(np.random.default_rng(7), des, p)
    sf = np.zeros(len(des.firms))
    x1, m1 = g1.generate(np.random.default_rng(7), des, dict(p, sig_firm=sf))
    assert np.array_equal(x0, x1) and np.array_equal(m0, m1)               # sig_disp 0: the same draws
    sf[0] = np.log(2.0)
    x2, m2 = g1.generate(np.random.default_rng(7), des, dict(p, sig_firm=sf))
    beta_m = des.beta_true[:, None] * m0[None]
    assert np.array_equal(m2, m0)
    assert (x2 - beta_m)[0] == pytest.approx(2.0 * (x0 - beta_m)[0])        # firm 0's scale doubled
    assert (x2 - beta_m)[1:] == pytest.approx((x0 - beta_m)[1:])


def test_evaluate_h56_rejects_a_real_effect_and_its_twin_reads_the_raw_change(built):
    des, cal, dd, _ = built
    x, m = g1.generate(np.random.default_rng(3), des, dict(cal["params"]))
    est = g1.estimate(des, x, m)
    out, pw = g1_drivers.evaluate_h56(dd, des, x, est, 0.05, (0.0, 0.5))
    assert set(out) == {"H5", "H6"}
    assert set(out["H5"]) == {"_primary", "twoway_date_t", "cluster_date_t", g1_drivers.TWIN_KEY}
    # beta 0 in the shortcut is the null decision itself; a shift of 0.5 log points per sd rejects.
    assert pw["H5"][0.0] == out["H5"]["twoway_date_t"] and pw["H5"][0.5] and pw["H6"][0.5]
    # The shortcut equals refitting Y + beta z_j, on a grid of shifts that puts the two-way t at 0, 0.005,
    # ..., 4 in steps of 0.005 (so across the critical value 2.01 finely enough that a se off by 0.5% shows).
    A = est["e"][dd.rows, 0 + 60]
    fit0 = regression.fit(A, dd.X)
    t0 = regression.coef_test(fit0, regression.covariance(fit0, dd.X, dd.date, dd.firm), 1)
    grid = tuple(float(k * t0["se"] - t0["estimate"]) for k in np.linspace(0.0, 4.0, 801))
    _, pwg = g1_drivers.evaluate_h56(dd, des, x, est, 0.05, grid)
    for b in grid:
        fit = regression.fit(A + b * dd.X[:, 1], dd.X)
        t = regression.coef_test(fit, regression.covariance(fit, dd.X, dd.date, dd.firm), 1)
        assert pwg["H5"][b] == bool(t["p_value"] <= 0.05), b
    # The twin: x moved by a firm-day amount that the market-adjusted crush does not see changes only
    # the twin's decision inputs: shift ln cm30(0) of H5's events by 0.3 * z(|SURP|) in x, so the raw
    # change moves while est (computed before) is the same: the twin rejects, the primary does not move.
    x_shift = x.copy()
    rows = dd.rows
    x_shift[des.firm[rows], des.sess[rows, 60]] += 0.3 * dd.X[:, 1]
    o2, _ = g1_drivers.evaluate_h56(dd, des, x_shift, est, 0.05, ())
    assert o2["H5"][g1_drivers.TWIN_KEY] and o2["H5"]["twoway_date_t"] == out["H5"]["twoway_date_t"]


def test_replicate_is_seeded_and_h7_has_its_own_stream(built):
    des, cal, dd, cal7 = built
    a = g1_drivers.replicate((des, dd, dict(cal["params"]), dict(cal7["params"]), 11, 0.05, (0.01,), (0.8,)))
    b = g1_drivers.replicate((des, dd, dict(cal["params"]), dict(cal7["params"]), 11, 0.05, (0.01,), (0.8,)))
    assert a == b
    only7 = g1_drivers.replicate((des, dd, None, dict(cal7["params"]), 11, 0.05, (), (0.8,)))
    assert only7["H7"] == a["H7"] and only7["_power"]["H7"] == a["_power"]["H7"] and "H5" not in only7
    # H7's draws come from the generator seeded (seed, 7), not from the cm30 series' seed: over 30 seeds
    # the decisions are exactly evaluate_h7 on that stream.
    p7 = {"nu": 6.0, "rho_d": 0.1, "firm_sd": 0.2}
    for seed in range(30):
        got = g1_drivers.replicate((des, dd, None, p7, seed, 0.3, (), (0.9, 1.1)))
        want = g1_drivers.evaluate_h7(dd, g1_drivers.h7_generate(np.random.default_rng([seed, 7]), dd, p7), 0.3,
                                      (0.9, 1.1))
        assert got["H7"] == want[0]["H7"] and got["_power"] == want[1], seed
    sizes, power = g1_drivers.rates([a, b, only7 | {"H5": a["H5"], "H6": a["H6"],
                                                    "_power": a["_power"]}])
    assert sizes["H5"]["_primary"] == "twoway_date_t" and power["H5"][0.01] in (0.0, 1.0)


CAL = {"params": dict(phi=0.97, rho_m=0.3, noise=0.7, sig0=0.0123, jump_k=2.0)}
CAL7 = {"params": {"nu": 6.0, "rho_d": 0.05, "firm_sd": 0.1}}


def test_designs_put_the_pinned_scale_and_h7_where_they_belong():
    sf = np.array([0.1, -0.1])
    dz = g1_drivers.designs(CAL, CAL7, sf)
    assert dz["calibrated"]["cm30"]["sig_firm"].tolist() == [0.1, -0.1] and dz["calibrated"]["h7"] == CAL7["params"]
    assert "sig_firm" not in dz["calibrated_random_scale"]["cm30"] and dz["calibrated_random_scale"]["h7"] is None
    for k in g1_drivers.CM30_STRESS:
        assert dz[k]["cm30"] == {kk: v for kk, v in g1.STRESS[k].items() if not kk.startswith("_")} and dz[k]["h7"] is None
    assert dz["h7:normal"] == {"cm30": None, "h7": {"nu": np.inf, "rho_d": 0.0, "firm_sd": 0.0}}
    assert dz["h7:t4.5"]["h7"] == dict(CAL7["params"], nu=4.5)


def test_driver_report_and_merge():
    cal = {"H5": {"_primary": "twoway_date_t", "twoway_date_t": 0.063, "cluster_date_t": 0.2,
                  g1_drivers.TWIN_KEY: 0.05},
           "H6": {"_primary": "twoway_date_t", "twoway_date_t": 0.0635, "cluster_date_t": 0.05},
           "H7": {"_primary": "twoway_date_wald", "twoway_date_wald": 0.04, "cluster_date_wald": 0.07}}
    res = {"calibrated": (cal, {"H5": {0.01: 0.5, 0.02: 0.9}, "H6": {0.01: 0.4, 0.02: 0.7}, "H7": {0.8: 0.6}}),
           "D0": ({"H5": dict(cal["H5"])}, {})}
    rep = run.driver_report(res, 2000, 0.05, (0.01, 0.02), (0.8,), None, CAL7, {"H5": 3})
    assert rep["gate"] == {"H5": True, "H6": False, "H7": True}          # 6.30% passes, 6.35% does not
    assert rep["power_summary"]["H5"]["detectable_80"] == pytest.approx(0.0175)
    assert rep["power_summary"]["H7"] == {"shifts": [0.8], "power": [0.6], "detectable_80": None}
    h14 = {"reps": 2000, "gate": {"H1": True}, "primary": {"H1": "twoway_date_t"}, "power": {"H1": {}},
           "rates": {"calibrated": {"H1": {"_primary": "twoway_date_t", "twoway_date_t": 0.046}},
                     "D0": {"H1": {"_primary": "twoway_date_t", "twoway_date_t": 0.05}}},
           "remeasured": {"reps": 10000, "seed_block": 1000, "rates": {"H4": {"bmp_t": 0.0534}}}}
    rep["remeasured"] = {"reps": 10000, "seed_block": 3000, "rates": {"H6": {"cluster_date_t": 0.06}}}
    out = g1_drivers.merge(h14, rep)
    assert set(out["rates"]["calibrated"]) == {"H1", "H5", "H6", "H7"} and set(out["rates"]["D0"]) == {"H1", "H5"}
    assert out["rates"]["power_beta:0.01"] == {"H5": {"_primary": "twoway_date_t", "twoway_date_t": 0.5},
                                               "H6": {"_primary": "twoway_date_t", "twoway_date_t": 0.4}}
    assert out["rates"]["power_b:0.8"] == {"H7": {"_primary": "twoway_date_wald", "twoway_date_wald": 0.6}}
    assert out["gate"] == {"H1": True, "H5": True, "H6": False, "H7": True}
    assert out["primary"]["H7"] == "twoway_date_wald"
    assert out["remeasured"]["rates"] == {"H4": {"bmp_t": 0.0534}, "H6": {"cluster_date_t": 0.06}}
    assert out["remeasured"]["seed_block"] == 1000 and out["remeasured"]["seed_block_drivers"] == 3000
    assert h14["rates"]["calibrated"] == {"H1": {"_primary": "twoway_date_t", "twoway_date_t": 0.046}}   # not mutated
    rep["remeasured"]["reps"] = 5000
    with pytest.raises(ValueError, match="same number"):
        g1_drivers.merge(h14, rep)


def test_driver_tasks_use_fresh_seed_blocks():
    seed0, reps = 100, int(ST["g1_reps"])
    tasks = run.driver_tasks(["calibrated", "D0"], reps, seed0, int(DP["g1_seed_block"]))
    assert len(tasks) == 2 * reps and tasks[0] == ("calibrated", seed0 + 1_000_003 * int(DP["g1_seed_block"]))
    seeds = {s for _, s in tasks}
    _, _, plan = run.g1_designs({"params": {}}, {"params": {}}, ST)
    h14 = {seed0 + 1_000_003 * (di + 1) + r for di in range(len(plan)) for r in range(reps)}
    h14 |= {seed0 + 1_000_003 * g1.REMEASURE_BLOCK + r for r in range(g1.REMEASURE_REPS)}
    remeasure = {seed0 + 1_000_003 * (int(DP["g1_seed_block"]) + 1000) + r for r in range(g1.REMEASURE_REPS)}
    assert len(seeds) == 2 * reps and not seeds & h14 and not seeds & remeasure
