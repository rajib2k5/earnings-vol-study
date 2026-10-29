# Tests for the WIRING of the stats run (stats/run.py, stats/results.py): the lines that connect
# gate G1's report and calibrations to the results and to the simulation, run on a synthetic
# inputs.Frame instead of the committed parquet (second fix round, delta review defect 1: the
# first fix round's wiring mutants W1-W8 survived because only the committed parquet was read).
#
# The synthetic Frame: 24 made-up companies, each reporting once in each of 7 seasons and 12 of
# them in an eighth, day 0 spread over 20 sessions; ln cm30 and ln sigma_d simulated by g1.generate
# (random walk, quote noise 0.5, sigma 0.03 for cm30 and 0.06 for sigma_d, beta 0.4, one ln VIX
# path), sigma_d missing in 4% of the cells and on day 0 of three events. Every per-event value is
# computed from those matrices with the package's own panel/abnormal.py functions, as
# panel/window.py computes them. No real data is read.
#
# Mutations this module must catch (each seen to fail on a scratch copy, file restored and its
# SHA-256 checked; [d02 Wn] = docs/validation/probes/m3-delta/d02_wiring_mutants.py, [fix2] = this
# round's script, milestone page §9 second round):
#   - event_test_rows never withholds a mis-sized row [d02 W1]
#   - result_rows passes no mis-sized rows to event_test_rows [d02 W2]
#   - result_rows drops the season-cut counterfactual [d02 W3]
#   - g1_designs gives H4's calibrated design the cm30 calibration [d02 W4]
#   - design_and_calibration gives the sigma_d design the cm30 usable mask [d02 W5]
#   - design_and_calibration calibrates sigma_d on the cm30 series and CRUSH [d02 W6]
#   - g1_designs runs the calibrated design at the stress scale 0.03 [d02 W8]
#   - rep_args takes H4's parameters from the cm30 designs [fix2]
#   - g1_rows drops the re-measured rates [fix2]
#   - remeasure_plan re-uses the main run's first seed block [fix2]
#   - remeasure_plan re-measures every test, not only the near-bar ones [fix2]

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from earnings_vol import params
from earnings_vol.events import calendar
from earnings_vol.panel import abnormal, window
from earnings_vol.stats import g1, inputs, results, run

ST = dict(params.load()["stats"])
COMMON = {"params_hash": "h", "code_commit": "c"}
SIG0_CM30, SIG0_SD = 0.03, 0.06


def synthetic_frame(seed: int = 5, n_firms: int = 24, n_last: int = 12):
    """The synthetic inputs.Frame of the header."""
    rng = np.random.default_rng(seed)
    firm, day0, season = [], [], []
    for s in range(8):
        for f in range(n_firms if s < 7 else n_last):
            firm.append(f)
            day0.append(70 + 63 * s + int(rng.integers(0, 20)))
            season.append(f"S{s + 1}")
    firm, day0 = np.array(firm), np.array(day0)
    sess = day0[:, None] + abnormal.REL_DAYS[None]
    n, W = sess.shape
    inb = np.zeros(sess.shape, bool)
    for i in range(n):
        others = day0[(firm == firm[i]) & (np.arange(n) != i)]
        for j, rel in enumerate(abnormal.REL_DAYS):
            inb[i, j] = -60 <= rel <= -22 and not any(o - 21 <= sess[i, j] <= o + 10 for o in others)
    sector = np.arange(n_firms) % 4
    rows = np.arange(n)
    d = g1.build_design([f"F{k:02d}" for k in range(n_firms)], sector, sess, np.ones(sess.shape, bool), inb, firm,
                        day0, day0, np.array(season, object), sector[firm], {"H1": rows},
                        np.full(n_firms, 0.4), 0.07)
    dgp = dict(phi=1.0, rho_m=0.10, noise=0.5)
    x, m = g1.generate(rng, d, dict(dgp, sig0=SIG0_CM30))
    x2, _ = g1.generate(rng, d, dict(dgp, sig0=SIG0_SD), m=m)
    X = x[firm[:, None], d.sess]
    M = m[d.sess]
    lsd = x2[firm[:, None], d.sess]
    gone = rng.random(lsd.shape) < 0.04
    gone[:3, abnormal.col(0)] = True                      # three events without a day-0 sigma_d
    lsd = np.where(gone, np.nan, lsd)
    clean = abnormal.clean_changes(inb)
    sec_id = np.array([f"F{k:02d}" for k in firm], object)
    betas = abnormal.beta_by_security(sec_id, sess, abnormal.one_session_changes(X), abnormal.one_session_changes(M),
                                      clean)
    beta = np.array([betas[s][0] for s in sec_id])
    al, al0 = abnormal.aliv(X, M, inb, beta)
    e = abnormal.abnormal_changes(X, M, beta)
    s = abnormal.baseline_sd(e, clean)
    c0, cm1 = abnormal.col(0), abnormal.col(-1)
    dm = M[:, c0] - M[:, cm1]
    ds_raw = lsd[:, c0] - lsd[:, cm1]
    e_sd = window.sigma_d_baseline(np.exp(lsd), M, inb, beta)
    s_sd = abnormal.baseline_sd(e_sd, np.isfinite(e_sd))
    vals = {"crush": e[:, c0], "runup": al[:, cm1], "persist_1": al[:, abnormal.col(1)],
            "persist_5": al[:, abnormal.col(5)], "persist_10": al[:, abnormal.col(10)], "dsigma_d": ds_raw - beta * dm}
    days = [date(2024, 1, 1) + timedelta(days=k) for k in range(int(sess.max()) + 1)]
    ev = pd.DataFrame({
        "event_id": [f"E{i:03d}" for i in range(n)], "security_id": sec_id, "gics_sector": [f"Sec{k}" for k in sector[firm]],
        "sample": "daily", "season": season, "day0_session": [days[t] for t in day0],
        "timing_used": np.where(firm % 2 == 0, "BMO", "AMC"),
        "eligible_crush": True, "eligible_runup": True, "eligible_persist_10": True,
        **{inputs.VALUE[k]: v for k, v in vals.items()},
        **{inputs.SA[k]: v / (s_sd if k == "dsigma_d" else s) for k, v in vals.items()},
        "crush_mean_adj": X[:, c0] - X[:, cm1], "dsigma_d_mean_adj": ds_raw, "crush_front_fixed": 1.2 * (X[:, c0] - X[:, cm1]),
        "s_abn_cboe": s, "beta_vix_cboe": beta})
    f = inputs.Frame(ev, sess, np.ones(sess.shape, bool), inb, e, al, al0, np.exp(lsd), M, calendar.Sessions(days))
    return f


@pytest.fixture(scope="module")
def frame():
    return synthetic_frame()


def one(rows, **kw):
    """The single row whose columns equal kw."""
    got = [r for r in rows if all(r[k] == v for k, v in kw.items())]
    assert len(got) == 1, (kw, len(got))
    return got[0]


def test_event_test_rows_withholds_exactly_the_mis_sized_rows(frame):
    # [d02 W1] Two robustness rows are named mis-sized; each keeps estimate, se and statistic and
    # loses p-value and interval. Every other row keeps its p-value. Without the set, the same two
    # rows have a p-value and an interval: the withholding is what nulls them.
    gate = {h: True for h in g1.TESTS}
    first = results.event_test_rows(frame, ST, gate, COMMON)
    plain = {r["result_id"]: r for r in first}
    mis = {("H1", "cluster_date_t"): {"rate": 0.2}, ("H4", "gen_sign_z"): {"rate": 0.07}}
    got = results.event_test_rows(frame, ST, gate, COMMON, mis)
    assert len(got) == len(plain) == len(first) and len(got) > 30
    for r in got:
        k = (r["hypothesis"], r["statistic"], r["sample"], r["adjustment"], r["subgroup_value"])
        was = plain[r["result_id"]]
        if r["role"] == "robustness" and r["adjustment"] == "market" and (r["hypothesis"], r["statistic"]) in mis:
            assert was["p_value"] is not None
            assert r["p_value"] is None and r["ci_lo"] is None and r["ci_hi"] is None, k
            assert r["estimate"] == was["estimate"] and r["stat"] == was["stat"] and r["se"] == was["se"], k
        else:
            assert r == was, k
    held = sorted((r["hypothesis"], r["statistic"]) for r in got if r["role"] == "robustness" and r["p_value"] is None)
    assert held == [("H1", "cluster_date_t"), ("H4", "gen_sign_z")]
    # The one-way date t of H1 has an interval to lose (gen_sign_z has none).
    assert [r["ci_lo"] for r in first if r["hypothesis"] == "H1" and r["statistic"] == "cluster_date_t"][0] is not None


def synthetic_report(n_events: int) -> dict:
    """A gate-G1 report as run_g1 writes it, with made-up rates. H1 cluster_date_t (30% on 2,000)
    is oversized; H4 gen_sign_z (6.80%) and bmp_t (5.80%) are within one point of the 6.30% bar and
    re-measured on 10,000: 5.60% > 5.57% (withheld) and 5.50% (kept); H4 rank_t 4% is far below."""
    cal = {"H1": {"_primary": "twoway_date_t", "twoway_date_t": 0.045, "cluster_date_t": 0.30, "bmp_t": 0.02},
           "H2": {"_primary": "rad_season_p", "rad_season_p": 0.004, "twoway_season_t": 0.01, "date_cluster_t": 0.2},
           "H3": {"_primary": "rad_season_p", "rad_season_p": 0.005, "twoway_season_t": 0.01},
           "H4": {"_primary": "twoway_date_t", "twoway_date_t": 0.05, "gen_sign_z": 0.068, "bmp_t": 0.058,
                  "rank_t": 0.04}}
    return {"reps": 2000, "gate": {h: True for h in g1.TESTS}, "n_events_union": n_events,
            "rates": {"calibrated": cal, "D0": {h: dict(r) for h, r in cal.items()}},
            "remeasured": {"reps": 10000, "seed_block": g1.REMEASURE_BLOCK,
                           "rates": {"H4": {"gen_sign_z": 0.056, "bmp_t": 0.055}}},
            "calibration": {"params": {"phi": 0.98, "sig0": 0.03}, "measured": {"rho1": -0.2, "rhat": [-0.2, 0.01]}}}


def test_result_rows_withholds_by_the_report_and_adds_the_season_cut(frame):
    # [d02 W2, W3] The report's verdicts reach the rows: exactly H1 cluster_date_t (on 2,000) and H4
    # gen_sign_z (re-measured on 10,000, 5.60% > 5.57%) lose their p-values; H4 bmp_t (5.50% on
    # 10,000) keeps its. H2's primary is rad_season_p here (seasons of 24 and 12 events: 2 > 1.5),
    # so the run adds its season-cut row: S8 merged into S7, G - 1 = 7 clusters, with its Holm p.
    rows, summary = run.result_rows(frame, ST, synthetic_report(frame.ev.shape[0]), COMMON)
    ev = [r for r in rows if r["family"] == "event_test"]
    held = sorted((r["hypothesis"], r["statistic"]) for r in ev if r["role"] == "robustness" and r["p_value"] is None)
    assert held == [("H1", "cluster_date_t"), ("H4", "gen_sign_z")]
    assert one(ev, hypothesis="H4", statistic="bmp_t", adjustment="market", subgroup_key="all")["p_value"] is not None
    prim = {r["hypothesis"]: r for r in ev if r["role"] == "primary"}
    assert prim["H2"]["statistic"] == "rad_season_p" and prim["H2"]["n_clusters"] == 8
    cut = [r for r in ev if r["subgroup_key"] == "season_cut" and r["hypothesis"] == "H2"]
    assert len(cut) == 1 and cut[0]["subgroup_value"] == "S8_into_S7" and cut[0]["n_clusters"] == 7
    assert cut[0]["p_holm"] is not None and cut[0]["p_holm"] >= prim["H2"]["p_holm"]
    assert summary["holm_family"] == list(ST["holm_family"])
    # G1's own rows: the re-measured rates with their 10,000 replications.
    rem = [r for r in rows if r["family"] == "validation" and r["measure"] == f"g1:{results.REMEASURED}"]
    assert sorted((r["hypothesis"], r["statistic"], r["n"], r["estimate"]) for r in rem) == [
        ("H4", "bmp_t", 10000, 0.055), ("H4", "gen_sign_z", 10000, 0.056)]


def test_result_rows_moves_a_failed_primary_out_of_the_family(frame):
    # A gate that fails H3 makes its primary exploratory and drops H3 from Holm's family.
    rep = synthetic_report(frame.ev.shape[0])
    rep["gate"]["H3"] = False
    rows, summary = run.result_rows(frame, ST, rep, COMMON)
    assert "H3" not in summary["holm_family"] and "H3" not in summary["holm"]
    h3 = [r for r in rows if r["family"] == "event_test" and r["hypothesis"] == "H3" and r["subgroup_key"] == "all"
          and r["adjustment"] == "market" and r["statistic"] == "rad_season_p"]
    assert len(h3) == 1 and h3[0]["role"] == "exploratory" and h3[0]["p_holm"] is None


def test_design_and_calibration_gives_h4_its_own_mask_and_calibration(frame):
    # [d02 W5, W6] The sigma_d design's usable mask is where sigma_d exists (not cm30's, which is
    # everywhere here), and H4's calibration is estimated on the sigma_d series and DSIGMA_D:
    # simulated at sigma 0.06 against cm30's 0.03, so its sig0 reads about twice the cm30 one.
    des, cal, des_sd, cal_sd = run.design_and_calibration(frame, ST)
    assert des.firm.size == frame.ev.shape[0]                     # every event is in the union here
    assert des.usable.all() and (des_sd.usable == np.isfinite(frame.sigma_d)).all()
    assert not des_sd.usable.all()
    assert cal["params"]["sig0"] == pytest.approx(SIG0_CM30, rel=0.2)
    assert cal_sd["params"]["sig0"] == pytest.approx(SIG0_SD, rel=0.2)
    # The sigma_d calibration reads the sigma_d series: its company effect and jump come from DSIGMA_D.
    assert cal_sd["measured"]["sd_log_s"] != cal["measured"]["sd_log_s"]


CAL = {"params": dict(phi=0.97, rho_m=0.3, noise=0.7, sig0=0.0123, jump_k=2.0)}
CAL_SD = {"params": dict(phi=0.85, rho_m=0.14, noise=0.97, sig0=0.0456, jump_k=2.8)}


def test_g1_designs_put_each_calibration_where_it_belongs():
    # [d02 W4, W8] The calibrated design is the calibration as estimated, sig0 included; H4's series
    # gets its own sigma_d calibration there and in the crush power shifts, and the stress designs
    # (prototype scale, no sig0) are the same on both series. The power designs never show robust rows.
    designs, designs_sd, plan = run.g1_designs(CAL, CAL_SD, ST)
    assert designs["calibrated"] == CAL["params"] and designs["calibrated"]["sig0"] == 0.0123
    assert designs_sd["calibrated"] == CAL_SD["params"]
    for k in g1.STRESS:
        assert designs[k] == designs_sd[k] and "sig0" not in designs[k] and "_unbalanced" not in designs[k]
    mu = float(ST["g1_power_shifts"][0])
    assert designs[f"power_crush:{mu}"] == dict(CAL["params"], mu=mu, shift_on="crush")
    assert designs_sd[f"power_crush:{mu}"] == dict(CAL_SD["params"], mu=mu, shift_on="crush")
    assert designs[f"power_ramp:{mu}"] == dict(CAL["params"], mu=mu, shift_on="ramp")
    assert plan[0] == ("calibrated", True, "all") and ("D2 unbalanced", True, "unbalanced") in plan
    assert (f"power_crush:{mu}", False, "crush") in plan and (f"power_ramp:{mu}", False, "ramp") in plan
    assert len(plan) == 1 + len(g1.STRESS) + 2 * len(ST["g1_power_shifts"])


def test_rep_args_send_h4_to_the_sigma_d_design_with_its_parameters():
    designs, designs_sd, _ = run.g1_designs(CAL, CAL_SD, ST)
    des, des_sd = object(), object()
    a, b, c = np.arange(3), np.arange(4), np.arange(5)
    state = dict(design=des, design_sd=des_sd, designs=designs, designs_sd=designs_sd, alpha=0.05, st=ST,
                 sets={"all": {"H1": a, "H2": b, "H4": c}, "ramp": {"H2": b}})
    args = run.rep_args(state, "calibrated", 17, True, "all")
    assert args[0] is des and args[1] == CAL["params"] and set(args[2]) == {"H1", "H2"} and args[3:7] == (17, 0.05, ST, True)
    d2, p2, sets2 = args[7]
    assert d2 is des_sd and p2 == CAL_SD["params"] and list(sets2) == ["H4"] and sets2["H4"] is c
    assert run.rep_args(state, "D2", 1, True, "all")[7][1] == designs_sd["D2"]
    assert run.rep_args(state, "calibrated", 1, False, "ramp")[7] is None


def test_remeasure_plan_draws_fresh_seeds_for_the_near_bar_tests():
    # The re-measure block: REMEASURE_REPS replications of the calibrated design on the near-bar
    # tests' event sets only, with seeds from block REMEASURE_BLOCK, disjoint from every block of
    # the main run (blocks 1 .. len(plan), reps seeds each).
    sets = {"H1": np.arange(3), "H4": np.arange(5)}
    got_sets, tasks = run.remeasure_plan({"H4": ["gen_sign_z"]}, sets, 100)
    assert list(got_sets) == ["H4"] and got_sets["H4"] is sets["H4"]
    assert len(tasks) == g1.REMEASURE_REPS and tasks[0] == ("calibrated", 100 + 1_000_003 * g1.REMEASURE_BLOCK, True,
                                                            "remeasure")
    seeds = {t[1] for t in tasks}
    _, _, plan = run.g1_designs(CAL, CAL_SD, ST)
    main = {100 + 1_000_003 * (di + 1) + r for di in range(len(plan)) for r in range(int(ST["g1_reps"]))}
    assert len(seeds) == g1.REMEASURE_REPS and not seeds & main
