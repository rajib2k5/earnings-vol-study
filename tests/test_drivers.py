# Tests for stats/drivers.py (milestone 4: H5-H7, ADR 0005 §3-§4) and its wiring into the results
# run (stats/run.py result_rows, stats/results.py Holm and BH), on the synthetic stats Frame of
# test_stats_wiring.py: made-up companies and values, no real data.
#
# Mutations this module must catch (each applied to a scratch copy, the test seen to fail, the file
# restored and its SHA-256 checked; milestone page appendix):
#   - model_inputs not z-scoring a term
#   - model_inputs dropping the complete-case rule for a regressor (NaN kept)
#   - model_inputs not winsorising abs_disp inside the model
#   - crush_rows giving H5's primary row the one-way covariance
#   - crush_rows never withholding a mis-sized robustness row
#   - crush_rows keeping a failed-gate primary as primary
#   - h7_rows testing b = 0 instead of b = 1 (shift_null dropped)
#   - h7_inputs dropping the events with E <= 0
#   - exceed_rows comparing with 0.5 instead of 0.425
#   - exceed_rows keeping events with E <= 0
#   - result_rows leaving out the regression rows (Holm then sees H5-H7 at p = 1)
#   - apply_holm over event tests only
#   - season_cut_rows' Holm p with H5-H7 at p = 1
#   - apply_bh pooling regression and event-test rows in one family
#   - model_inputs giving the mean-adjusted twin the market-adjusted crush (the milestone-4 review's
#     surviving mutant M05: the twin rows then equal the primary's)
#   - result_rows without require_verdicts (a missing H5-H7 verdict read as a pass) [fix R2]
#   - binding_family dropping a hypothesis outside SIZE_GATED on a failed check (H5-H7 out) [fix R1]
#   - binding_family ignoring `gated` (the owner's alternative cannot drop H7) [fix R1]
#   - holm_post_gate_rows over the binding family instead of the post-gate one [fix R1]
#   - holm_post_gate_rows' season cut with the binding family's p-values [fix R1]
#   - post_gate_family keeping the hypotheses whose check failed [fix R1]
#   - apply_bh putting the primaries in a BH family again [fix R1]
#   - crush_rows reading H5's and H6's family membership with a default of True [fix R2]
#   - h7_rows reading H7's family membership with a default of True [fix R2]
#   - apply_holm dropping a family member without a primary row (review mutant M18) [fix R3]
#   - holm_post_gate_rows dropping a family member without a primary row [fix R3]

import numpy as np
import pytest
from scipy import stats

from earnings_vol.stats import drivers, multiple, regression, results, run
from test_stats_wiring import COMMON, DP, ST, synthetic_frame, synthetic_report

W = tuple(DP["surprise_winsor"])
IN = {"H5": True, "H6": True, "H7": True}         # H5-H7 in the binding Holm family


@pytest.fixture(scope="module")
def frame():
    return synthetic_frame()


def test_model_inputs_builds_the_primary_design(frame):
    m = drivers.model_inputs(frame, drivers.PRIMARY, W)
    n = frame.ev.shape[0]
    assert m["rows"].size == n                                     # every synthetic event is in H1's set
    # const, 4 z-scored terms, 3 sector dummies (4 sectors), 7 season dummies (8 seasons)
    assert m["names"][:5] == ["const", "abs_surprise", "ln_sigma_d", "slope", "size"]
    assert m["X"].shape == (n, 15) and sum(":" in c for c in m["names"]) == 10
    for j in range(1, 5):
        assert m["X"][:, j].mean() == pytest.approx(0, abs=1e-12) and m["X"][:, j].std(ddof=1) == pytest.approx(1)
    raw = np.log(frame.ev["sigma_d_m1"].to_numpy(float))
    assert m["X"][:, 2] == pytest.approx(regression.zscore(raw))
    assert m["y"] == pytest.approx(frame.ev["crush_cboe"].to_numpy(float))
    assert list(m["date"][:2]) == [str(d) for d in frame.ev["day0_session"][:2]]


def test_model_inputs_keeps_complete_cases_and_winsorises_inside_the_model(frame):
    ev = frame.ev.copy()
    ev.loc[[0, 5], "sigma_d_m1"] = np.nan
    ev.loc[3, "surprise_disp"] = 1e6                              # a wild dispersion surprise
    f2 = type(frame)(ev, *[getattr(frame, k) for k in ("sess", "usable", "in_baseline", "e", "aliv", "aliv0",
                                                        "sigma_d", "M", "sessions")])
    m = drivers.model_inputs(f2, drivers.PRIMARY, W)
    assert m["rows"].size == ev.shape[0] - 2 and 0 not in m["rows"] and 5 not in m["rows"]
    spec = [s for s in drivers.EXPLORATORY if s.model_id == "crush_disp"][0]
    md = drivers.model_inputs(f2, spec, W)
    v = np.abs(ev["surprise_disp"].to_numpy(float))[md["rows"]]
    want = regression.zscore(np.clip(v, np.quantile(v, W[0]), np.quantile(v, W[1])))
    assert md["X"][:, 1] == pytest.approx(want)


def test_crush_rows_roles_statistics_and_withholding(frame):
    m = drivers.model_inputs(frame, drivers.PRIMARY, W)
    fit = regression.fit(m["y"], m["X"])
    two = regression.covariance(fit, m["X"], m["date"], m["firm"])
    one = regression.covariance(fit, m["X"], m["date"])
    rows = drivers.crush_rows(frame, drivers.PRIMARY, W, IN, COMMON, True, {("H5", "cluster_date_t"): {}})
    by = {(r["term"], r["statistic"]): r for r in rows}
    h5 = by[("abs_surprise", "twoway_date_t")]
    assert (h5["hypothesis"], h5["role"], h5["family"], h5["model_id"]) == ("H5", "primary", "regression",
                                                                            "crush_drivers")
    assert h5["se"] == pytest.approx(regression.coef_test(fit, two, 1)["se"]) and h5["n_clusters_firm"] == 24
    h6 = by[("ln_sigma_d", "twoway_date_t")]
    assert (h6["hypothesis"], h6["role"]) == ("H6", "primary")
    r5 = by[("abs_surprise", "cluster_date_t")]
    assert r5["role"] == "robustness" and r5["p_value"] is None and r5["ci_lo"] is None    # withheld
    assert r5["se"] == pytest.approx(regression.coef_test(fit, one, 1)["se"]) and r5["n_clusters_firm"] is None
    r6 = by[("ln_sigma_d", "cluster_date_t")]
    assert r6["p_value"] is not None and r6["df"] == r6["n_clusters"] - 1
    assert by[("slope", "twoway_date_t")]["role"] == "exploratory" and by[("slope", "twoway_date_t")]["hypothesis"] is None
    assert ("slope", "cluster_date_t") not in by
    assert by[(None, "r2")]["estimate"] == pytest.approx(fit["r2"])
    # A hypothesis out of the binding family makes the primary exploratory (ADR 0005 §5).
    failed = drivers.crush_rows(frame, drivers.PRIMARY, W, dict(IN, H6=False), COMMON, True, {})
    assert [r["role"] for r in failed if r["term"] == "ln_sigma_d" and r["statistic"] == "twoway_date_t"] == ["exploratory"]
    # A missing hypothesis is an error, not a pass (fix R2: it used to read as in the family).
    with pytest.raises(KeyError):
        drivers.crush_rows(frame, drivers.PRIMARY, W, {"H6": True}, COMMON, True, {})
    # The twin: two-way rows of H5's and H6's terms only, robustness, mean-adjusted.
    twin = drivers.crush_rows(frame, drivers.TWIN, W, {}, COMMON, True, {})
    assert sorted((r["term"], r["role"], r["adjustment"]) for r in twin) == [
        ("abs_surprise", "robustness", "mean"), ("ln_sigma_d", "robustness", "mean")]


def test_the_twin_regresses_the_mean_adjusted_crush(frame):
    # Fix R3 (milestone-4 review, mutant M05): the twin's outcome is crush_mean_adj, not crush_cboe.
    m = drivers.model_inputs(frame, drivers.TWIN, W)
    y = frame.ev["crush_mean_adj"].to_numpy(float)[m["rows"]]
    assert m["y"] == pytest.approx(y)
    assert m["y"] != pytest.approx(frame.ev["crush_cboe"].to_numpy(float)[m["rows"]])
    fit = regression.fit(y, m["X"])
    two = regression.covariance(fit, m["X"], m["date"], m["firm"])
    twin = {r["term"]: r for r in drivers.crush_rows(frame, drivers.TWIN, W, {}, COMMON, True, {})}
    prim = {r["term"]: r for r in drivers.crush_rows(frame, drivers.PRIMARY, W, IN, COMMON, True, {})
            if r["statistic"] == "twoway_date_t"}
    for j, t in ((1, "abs_surprise"), (2, "ln_sigma_d")):
        want = regression.coef_test(fit, two, j)
        assert twin[t]["estimate"] == pytest.approx(want["estimate"]) and twin[t]["se"] == pytest.approx(want["se"])
        assert twin[t]["estimate"] != pytest.approx(prim[t]["estimate"])    # not the primary's number


def test_h7_rows_test_a_zero_and_b_one_with_every_event(frame):
    m = drivers.h7_inputs(frame)
    ev = frame.ev
    want_x = ev["evar_m1"].to_numpy(float) + ev["sigma_d_m1"].to_numpy(float) ** 2 / 252
    assert m["rows"].size == ev.shape[0] and m["x"] == pytest.approx(want_x)       # E <= 0 kept
    assert m["y"] == pytest.approx(ev["realized_ret_0"].to_numpy(float) ** 2)
    rows = drivers.h7_rows(frame, IN, COMMON, {})
    by = {(r["term"], r["statistic"]): r for r in rows}
    w2 = by[("a=0,b=1", "twoway_date_wald")]
    fit = regression.fit(m["y"], m["X"])
    want = regression.wald_test(fit, regression.covariance(fit, m["X"], m["date"], m["firm"]), np.eye(2),
                                np.array([0.0, 1.0]))
    assert (w2["hypothesis"], w2["role"], w2["adjustment"]) == ("H7", "primary", "none")
    assert w2["stat"] == pytest.approx(want["stat"]) and w2["df_num"] == 2 and w2["df"] == min(
        w2["n_clusters"], w2["n_clusters_firm"]) - 1
    assert by[("a=0,b=1", "cluster_date_wald")]["role"] == "robustness"
    b = by[("b", "twoway_date_t")]
    assert b["stat"] == pytest.approx((b["estimate"] - 1.0) / b["se"])
    assert b["p_value"] == pytest.approx(2 * stats.t.sf(abs(b["stat"]), b["df"]))
    a = by[("a", "twoway_date_t")]
    assert a["stat"] == pytest.approx(a["estimate"] / a["se"]) and a["role"] == "exploratory"
    with pytest.raises(KeyError):                                # fix R2: no H7 entry is an error, not a pass
        drivers.h7_rows(frame, {"H5": True, "H6": True}, COMMON, {})
    held = drivers.h7_rows(frame, IN, COMMON, {("H7", "cluster_date_wald"): {}})
    assert [r["p_value"] for r in held if r["statistic"] == "cluster_date_wald"] == [None]
    m2 = drivers.h7_rows(frame, {}, COMMON, {}, "evar_m2")
    assert {r["model_id"] for r in m2} == {"implied_realised_m2"} and {r["role"] for r in m2} == {"exploratory"}
    assert not [r for r in m2 if r["statistic"] == "cluster_date_wald"]


def test_exceed_share_against_0425_over_positive_e(frame):
    # Events with E <= 0 are left out even when an implied |move| is there (the stored one is null for
    # them; here one is planted to see the rule).
    ev = frame.ev.copy()
    ev.loc[0, "implied_abs_move_total_m1"] = 0.0
    f2 = type(frame)(ev, *[getattr(frame, k) for k in ("sess", "usable", "in_baseline", "e", "aliv", "aliv0",
                                                        "sigma_d", "M", "sessions")])
    keep = ev["evar_m1"].to_numpy(float) > 0
    ind = (np.abs(ev["realized_ret_0"].to_numpy(float)) > ev["implied_abs_move_total_m1"].to_numpy(float))[keep]
    (r,) = drivers.exceed_rows(f2, COMMON)
    assert r["n"] == keep.sum() == ev.shape[0] - 2
    assert r["estimate"] == pytest.approx(ind.mean())
    assert r["stat"] == pytest.approx((ind.mean() - 0.425) / r["se"])
    assert drivers.H7_BENCHMARK == pytest.approx(2 * stats.norm.sf(np.sqrt(2 / np.pi)), abs=5e-4)


def test_driver_rows_lists_every_model(frame):
    rows = drivers.driver_rows(frame, DP, IN, COMMON)
    models = {(r["model_id"], r["adjustment"], r["sample"]) for r in rows}
    want = {("crush_drivers", "market", "daily"), ("crush_drivers", "mean", "daily"),
            ("implied_realised", "none", "daily"), ("implied_realised_m2", "none", "daily")}
    want |= {(s.model_id, "market", "daily") for s in drivers.EXPLORATORY if s.sample == "daily"}
    assert models == want                      # no coarse events here: the coarse model has no rows
    assert {r["hypothesis"] for r in rows if r["role"] == "primary"} == {"H5", "H6", "H7"}
    vix = [r for r in rows if r["model_id"] == "crush_vix" and r["statistic"] == "twoway_date_t"]
    assert sorted(r["term"] for r in vix) == sorted(drivers.BASE_TERMS + ("abs_surprise_x_mid", "abs_surprise_x_high"))


def test_result_rows_holm_runs_over_h1_to_h7_with_the_real_h5_h7(frame):
    rows, summary = run.result_rows(frame, ST, synthetic_report(frame.ev.shape[0]), COMMON, DP)
    prim = results.primary_rows(rows)
    assert sorted(prim) == ["H1", "H2", "H3", "H4", "H5", "H6", "H7"]
    assert prim["H5"]["family"] == "regression" and prim["H7"]["statistic"] == "twoway_date_wald"
    want = multiple.holm({h: prim[h]["p_value"] for h in ST["holm_family"]})
    assert {h: prim[h]["p_holm"] for h in prim} == pytest.approx(want)
    assert summary["holm"] == pytest.approx(want)
    # Each p_holm can only fall from milestone 3's upper bound (H5-H7 at p = 1).
    upper = multiple.holm({h: (prim[h]["p_value"] if h in ("H1", "H2", "H3", "H4") else None)
                           for h in ST["holm_family"]})
    assert all(prim[h]["p_holm"] <= upper[h] + 1e-15 for h in ("H1", "H2", "H3", "H4"))
    # The season-cut counterfactual uses the family's real p-values, H5-H7 included.
    cut = [r for r in rows if r["subgroup_key"] == "season_cut"][0]
    pv = {h: prim[h]["p_value"] for h in ST["holm_family"]}
    pv[cut["hypothesis"]] = cut["p_value"]
    assert cut["p_holm"] == pytest.approx(multiple.holm(pv)[cut["hypothesis"]])
    # BH: the regression rows of a sample are their own family.
    reg = [r for r in rows if r["family"] == "regression" and r["role"] == "exploratory" and r["p_value"] is not None]
    assert [r["q_bh"] for r in reg] == pytest.approx(multiple.bh([r["p_value"] for r in reg]))
    evt = [r for r in rows if r["family"] == "event_test" and r["role"] == "exploratory" and r["p_value"] is not None
           and r["sample"] == "daily"]
    assert [r["q_bh"] for r in evt] == pytest.approx(multiple.bh([r["p_value"] for r in evt]))


def test_a_failed_driver_size_check_keeps_h5_h7_in_the_binding_family(frame):
    # Fix R1 after the milestone-4 review: G1's size designs were declared for H1-H4 only (ADR 0005 §5 at
    # milestone 0), so a failed H5-H7 size check is reported, not a reason to leave Holm's family. The
    # declared family H1-H7 binds with H5-H7's real p-values; their primaries keep the role primary.
    rep = synthetic_report(frame.ev.shape[0])
    rep["gate"].update(H5=False, H6=False, H7=False)
    rows, summary = run.result_rows(frame, ST, rep, COMMON, DP)
    assert summary["holm_family"] == list(ST["holm_family"])
    prim = results.primary_rows(rows)
    assert sorted(prim) == list(ST["holm_family"])
    want = multiple.holm({h: prim[h]["p_value"] for h in ST["holm_family"]})
    assert {h: prim[h]["p_holm"] for h in prim} == pytest.approx(want) and summary["holm"] == pytest.approx(want)
    w = [r for r in rows if r["statistic"] == "twoway_date_wald" and r["model_id"] == "implied_realised"]
    assert len(w) == 1 and w[0]["role"] == "primary" and w[0]["p_holm"] == pytest.approx(want["H7"])
    # No primary is in a BH family: BH runs over exploratory rows only.
    assert all(r["q_bh"] is None for r in prim.values())
    # The owner's alternative (decisions table): gate H5-H7 too, and a failed H7 leaves the family.
    rows2, summary2 = run.result_rows(frame, ST, rep, COMMON, DP, gated=tuple(ST["holm_family"]))
    assert summary2["holm_family"] == ["H1", "H2", "H3", "H4"] and "H7" not in summary2["holm"]
    w2 = [r for r in rows2 if r["statistic"] == "twoway_date_wald" and r["model_id"] == "implied_realised"]
    assert len(w2) == 1 and w2[0]["role"] == "exploratory" and w2[0]["hypothesis"] == "H7" and w2[0]["p_holm"] is None


@pytest.mark.parametrize("drop", [("gate", "H5"), ("gate", "H7"), ("calibrated", "H6"), ("gate", "H2"),
                                  ("none", "H6")])
def test_result_rows_refuses_a_report_without_a_verdict(frame, drop):
    # Fix R2 after the milestone-4 review: a G1 report without a verdict for a hypothesis that gets rows
    # (here: a milestone-3 report, or one with a verdict stored as null) used to give it the primary role,
    # Holm over all seven and no withheld rows. Now result_rows raises before computing a row.
    rep = synthetic_report(frame.ev.shape[0])
    where, h = drop
    if where == "gate":
        del rep["gate"][h]
    elif where == "calibrated":
        del rep["rates"]["calibrated"][h]
    else:
        rep["gate"][h] = None
    with pytest.raises(ValueError, match=f"no verdict for {h}"):
        run.result_rows(frame, ST, rep, COMMON, DP)


def test_holm_counts_a_family_member_without_a_primary_row_as_p_one():
    # A hypothesis of the family with no primary row (not tested) enters Holm as p = 1, in the binding
    # Holm and in the post-gate sensitivity alike; it is not dropped (that would shrink m). The milestone-4
    # review's mutant M18 survived because every family member had a primary row.
    rows = [results.row(family="event_test", hypothesis="H1", role="primary", statistic="twoway_date_t",
                        subgroup_key="all", adjustment="market", p_value=0.01, **COMMON)]
    assert results.apply_holm(rows, ["H1", "H2"]) == pytest.approx({"H1": 0.02, "H2": 1.0})
    assert rows[0]["p_holm"] == pytest.approx(0.02)
    pg = results.holm_post_gate_rows(rows, ["H1", "H2", "H3"], COMMON)
    assert {r["hypothesis"]: r["estimate"] for r in pg} == pytest.approx({"H1": 0.03, "H2": 1.0, "H3": 1.0})


def test_holm_post_gate_is_a_sensitivity_over_the_family_without_the_failed_primaries(frame):
    # The descriptive rows give the Holm p of the family without every hypothesis whose G1 primary
    # failed (here H5-H7: H1-H4 remain), from the primary rows' p-values, and the season cut's Holm p
    # over that family. The crush is made to depend on |SURP| (0.2 log points per sd) so that H5's p is
    # tiny, and shifted by +0.03 so that H1's p is small (about 0.005): H1's binding p_holm (6 x p, H5
    # ranked first among seven) is then above its post-gate one (4 x p among four). The run-up is shifted
    # by +0.3 so that H2's season-cut p is small too (about 2e-5, as in the next test): its post-gate Holm
    # p (4 x p) then differs from its binding one (6 x p), so the two cannot be confused.
    ev = frame.ev.copy()
    ev["crush_cboe"] = ev["crush_cboe"] + 0.03 + 0.2 * regression.zscore(ev["abs_surprise_scaled_w"].to_numpy(float))
    ev["runup_cboe"] = ev["runup_cboe"] + 0.3
    f2 = type(frame)(ev, *[getattr(frame, k) for k in ("sess", "usable", "in_baseline", "e", "aliv", "aliv0",
                                                        "sigma_d", "M", "sessions")])
    rep = synthetic_report(frame.ev.shape[0])
    rep["gate"].update(H5=False, H6=False, H7=False)
    rows, summary = run.result_rows(f2, ST, rep, COMMON, DP)
    pg = [r for r in rows if r["measure"] == "holm_post_gate"]
    main = {r["hypothesis"]: r for r in pg if r["subgroup_key"] == "all"}
    assert sorted(main) == ["H1", "H2", "H3", "H4"] and summary["holm_post_gate_family"] == ["H1", "H2", "H3", "H4"]
    assert all(r["family"] == "descriptive" and r["p_value"] is None and r["p_holm"] is None and r["n"] == 4
               for r in pg)
    prim = results.primary_rows(rows)
    want = multiple.holm({h: prim[h]["p_value"] for h in ("H1", "H2", "H3", "H4")})
    assert {h: r["estimate"] for h, r in main.items()} == pytest.approx(want)
    assert prim["H5"]["p_value"] < prim["H1"]["p_value"] < 0.01
    assert all(want[h] <= prim[h]["p_holm"] + 1e-15 for h in want)
    assert want["H1"] == pytest.approx(4 * prim["H1"]["p_value"])
    assert prim["H1"]["p_holm"] == pytest.approx(6 * prim["H1"]["p_value"])   # binding: H5 is in the family
    # The season cut over the post-gate family: its p in place of H2's.
    cuts = {r["hypothesis"]: r for r in rows if r["subgroup_key"] == "season_cut" and r["family"] == "event_test"}
    pcuts = {r["hypothesis"]: r for r in pg if r["subgroup_key"] == "season_cut"}
    assert sorted(pcuts) == sorted(cuts) == ["H2", "H3"]          # both ramps sit on rad_season_p here
    cut, pcut = cuts["H2"], pcuts["H2"]
    assert pcut["subgroup_value"] == cut["subgroup_value"]
    pv = {h: prim[h]["p_value"] for h in ("H1", "H2", "H3", "H4")}
    pv["H2"] = cut["p_value"]
    assert cut["p_value"] < 0.001
    assert pcut["estimate"] == pytest.approx(multiple.holm(pv)["H2"])
    assert pcut["estimate"] < cut["p_holm"] - 1e-9                      # not the binding cut's Holm p
    pv7 = {h: prim[h]["p_value"] for h in ST["holm_family"]}
    pv7["H2"] = cut["p_value"]
    assert cut["p_holm"] == pytest.approx(multiple.holm(pv7)["H2"])     # the binding cut: all seven


def test_the_season_cut_holm_counts_a_small_h5_p(frame):
    # The counterfactual season-cut row's Holm p must use H5's real p-value. Here the run-up is shifted
    # by +0.3, so H2's cut p is small (with S8 merged into S7 the seasons are 24 and 36 events, balanced,
    # so the cut uses the two-way t: p about 2e-5), and the crush is made to depend strongly on |SURP|
    # (0.2 log points per sd), so H5's p is smaller still and comes before the cut in Holm's order. With
    # H5 at p = 1 the cut would move up one rank and get a larger multiplier.
    ev = frame.ev.copy()
    ev["runup_cboe"] = ev["runup_cboe"] + 0.3
    ev["crush_cboe"] = ev["crush_cboe"] + 0.2 * regression.zscore(ev["abs_surprise_scaled_w"].to_numpy(float))
    f2 = type(frame)(ev, *[getattr(frame, k) for k in ("sess", "usable", "in_baseline", "e", "aliv", "aliv0",
                                                        "sigma_d", "M", "sessions")])
    rows, _ = run.result_rows(f2, ST, synthetic_report(ev.shape[0]), COMMON, DP)
    prim = results.primary_rows(rows)
    cut = [r for r in rows if r["subgroup_key"] == "season_cut" and r["hypothesis"] == "H2"][0]
    assert prim["H5"]["p_value"] < cut["p_value"] < 0.001
    pv = {h: prim[h]["p_value"] for h in ST["holm_family"]}
    pv["H2"] = cut["p_value"]
    assert cut["p_holm"] == pytest.approx(multiple.holm(pv)["H2"])
    pv["H5"] = None
    assert cut["p_holm"] < multiple.holm(pv)["H2"]
