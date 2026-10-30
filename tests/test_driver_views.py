# Tests for the milestone-4 views (export/driver_views.py: drivers.json and implied_vs_realised.json,
# contract 0.5.0) and the tests.json changes (export/event_views.py: Holm's family after gate G1),
# built from the results of the synthetic stats Frame of test_stats_wiring.py and a made-up gate
# report (no real data), then checked against the committed files.
#
# Mutations this module must catch (each applied to a scratch copy, the test seen to fail, the file
# restored and its SHA-256 checked; milestone page appendix):
#   - term_note not withholding the note of a mis-sized robustness row (g1_size missing)
#   - term_note mapping the twin to the primary's statistic instead of TWIN_KEY
#   - term_note silent on a primary that failed the gate
#   - holm_family never finding a hypothesis that left the family (owner's gating) [fix R1]
#   - term_note silent on a primary whose size check failed (no note, no g1_size) [fix R1]
#   - term_note's failed-check primary without its g1_size [fix R1]
#   - post_gate() reading the season-cut row as a main row [fix R1]
#   - implied_vs_realised_data's one-way G1 verdict missing [fix R4]
#   - tests_data's family dropping the hypotheses whose size check failed [fix R1]
#   - holm_caveat silent on the hypotheses that stay in the family with a failed check [fix R1]
#   - implied_vs_realised_data's implied variance without /252
#   - implied_vs_realised_data keeping events without a realised move
#   - tests_data counting H5-H7 as untested once they have rows
#   - tests_data's power curves including H5-H7
#   - g1_summary writing a re-measured statistic's 2,000-replication rate beside its 10,000 reps

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from earnings_vol import contract, params
from earnings_vol.export import driver_views, event_views
from earnings_vol.stats import g1_drivers, results, run
from test_stats_wiring import COMMON, DP, ST, synthetic_frame, synthetic_report

P = params.load()
ROOT = Path(__file__).resolve().parents[1]
PROV = {"params_hash": "h", "code_commit": "c", "sample_label": "daily", "dolt_commits": {"earnings": "e", "options": "o"}}


def driver_part(gate_ok: bool) -> dict:
    """A made-up H5-H7 gate report (run.driver_report's shape): H5's and H6's two-way t pass or fail
    with the flag; their one-way date t is oversized (20%); the twin of H5 is oversized (9%); H7's
    Wald fails (16%), its one-way Wald too."""
    t2 = 0.05 if gate_ok else 0.09
    cal = {"H5": {"_primary": "twoway_date_t", "twoway_date_t": t2, "cluster_date_t": 0.2, g1_drivers.TWIN_KEY: 0.09},
           "H6": {"_primary": "twoway_date_t", "twoway_date_t": t2, "cluster_date_t": 0.2, g1_drivers.TWIN_KEY: 0.05},
           "H7": {"_primary": "twoway_date_wald", "twoway_date_wald": 0.16, "cluster_date_wald": 0.17}}
    res = {"calibrated": (cal, {"H5": {0.01: 0.3, 0.05: 1.0}, "H6": {0.01: 0.2, 0.05: 0.9}, "H7": {0.8: 0.5}})}
    return run.driver_report(res, 2000, 0.05, (0.01, 0.05), (0.8,), None,
                             {"params": {"nu": 6.0, "rho_d": 0.0, "firm_sd": 0.0}, "measured": {"n": 10}},
                             {"H5": 1, "H6": 1, "H7": 1})


def built(frame, gate_ok: bool):
    h14 = synthetic_report(frame.ev.shape[0])
    h14.update(primary={h: r["_primary"] for h, r in h14["rates"]["calibrated"].items()}, power={})
    rep = g1_drivers.merge(h14, driver_part(gate_ok))
    rows, summary = run.result_rows(frame, ST, rep, COMMON, DP)
    return results.frame(rows), rep, summary


@pytest.fixture(scope="module")
def frame():
    return synthetic_frame()


@pytest.fixture(scope="module")
def failed(frame):
    return built(frame, False)


def test_g1_summary_pairs_a_remeasured_rate_with_its_replications():
    # Made-up rates: H5's one-way t is near the 2,000-replication bar (6.30%), so it was re-measured
    # on 10,000 replications at 5.20%, under that count's bar (5.57%).
    row = dict(family="validation", hypothesis="H5", role="robustness")
    val = pd.DataFrame([
        dict(row, measure="g1:calibrated", statistic="twoway_date_t", role="primary", n=2000, estimate=0.05),
        dict(row, measure="g1:calibrated", statistic="cluster_date_t", n=2000, estimate=0.065),
        dict(row, measure="g1:calibrated_remeasured", statistic="cluster_date_t", n=10000, estimate=0.052)])
    got = {c["statistic"]: c for c in driver_views.g1_summary(val, 0.05)["calibrated"]}
    assert (got["cluster_date_t"]["rejection_rate"], got["cluster_date_t"]["reps"]) == (0.052, 10000)
    assert got["cluster_date_t"]["pass"] is True
    assert (got["twoway_date_t"]["rejection_rate"], got["twoway_date_t"]["reps"]) == (0.05, 2000)


def tables(frame):
    ev = frame.ev
    events = ev[["event_id", "security_id", "sample", "season", "day0_session", "timing_used"]].assign(
        ticker_at_event=ev["security_id"], timing_status="not_checked")
    measures = ev[["event_id", "eligible_crush", "evar_m1", "sigma_d_m1", "implied_abs_move_total_m1",
                   "realized_ret_0", "surprise_scaled"]].assign(
        implied_move_m1=np.sqrt(np.clip(ev["evar_m1"], 0, None)),
        implied_move_status=np.where(ev["evar_m1"] > 0, "ok", "nonpositive_event_variance"))
    security = ev[["security_id", "gics_sector"]].drop_duplicates()
    return events, measures, security


def test_drivers_data_after_a_failed_gate(frame, failed):
    res, rep, summary = failed
    events, _, _ = tables(frame)
    d = driver_views.drivers_data(res, events, P, PROV)
    # Fix R1: the declared family binds; H5-H7 stay in it with their failed size check shown.
    assert d["holm"]["family"] == ["H1", "H2", "H3", "H4", "H5", "H6", "H7"] and d["holm"]["left_family"] == []
    pg = d["holm"]["post_gate"]
    assert pg["family"] == ["H1", "H2", "H3", "H4"] and sorted(pg["p_holm"]) == pg["family"]
    want = res[(res["measure"] == "holm_post_gate") & (res["subgroup_key"] == "all")]
    assert pg["p_holm"] == {r["hypothesis"]: event_views._sig(r["estimate"]) for r in want.to_dict("records")}
    assert sorted(pg["season_cut"]) == ["H2", "H3"]
    assert [(m["model_id"], m["adjustment"]) for m in d["models"][:3]] == [
        ("crush_drivers", "market"), ("crush_drivers", "mean"), ("implied_realised", "none")]
    prim = [m for m in d["models"] if (m["model_id"], m["adjustment"], m["sample"]) == ("crush_drivers", "market", "daily")][0]
    assert prim["fixed_effects"] == ["sector", "season"] and prim["r2"] is not None
    by = {(t["term"], t["statistic"]): t for t in prim["terms"]}
    h5 = by[("abs_surprise", "twoway_date_t")]
    assert h5["role"] == "primary" and h5["hypothesis"] == "H5" and h5["p_value"] is not None
    assert h5["p_holm"] is not None and h5["q_bh"] is None and h5["g1_size"] == 0.09 and h5["g1_reps"] == 2000
    assert "Size check failed" in h5["note"] and "9.00%" in h5["note"] and "would not be trusted" in h5["note"]
    assert ("not rejected" in h5["note"]) == (h5["p_holm"] > 0.05)
    r5 = by[("abs_surprise", "cluster_date_t")]
    assert r5["p_value"] is None and r5["g1_size"] == 0.2 and r5["g1_reps"] == 2000 and "withheld" in r5["note"]
    twin = [m for m in d["models"] if m["adjustment"] == "mean"][0]
    tby = {t["term"]: t for t in twin["terms"]}
    assert tby["abs_surprise"]["p_value"] is None and tby["abs_surprise"]["g1_size"] == 0.09   # twin of H5 oversized
    assert tby["ln_sigma_d"]["p_value"] is not None and tby["ln_sigma_d"]["note"] is None       # twin of H6 is not
    assert [c for c in d["g1"]["calibrated"] if c["hypothesis"] == "H7" and c["primary"]][0]["pass"] is False
    assert {pw["hypothesis"]: pw["kind"] for pw in d["g1"]["power"]} == {"H5": "beta", "H6": "beta", "H7": "b"}
    assert any("stay in the declared Holm family" in c for c in d["caveats"])
    assert any("8.10%" not in c and "liberal here" in c and "9.00% to 9.00%" in c and "the slope's included" in c
               for c in d["caveats"])
    contract.dumps(contract.envelope("drivers", d, generated_at=pd.Timestamp("2026-10-29", tz="UTC").to_pydatetime(),
                                     source_commit="c"))                                     # finite, JSON-safe


def test_drivers_data_after_a_passed_gate_keeps_h5_h6_in_the_family(frame):
    res, rep, summary = built(frame, True)
    events, _, _ = tables(frame)
    d = driver_views.drivers_data(res, events, P, PROV)
    assert d["holm"]["family"] == ["H1", "H2", "H3", "H4", "H5", "H6", "H7"] and d["holm"]["left_family"] == []
    assert d["holm"]["post_gate"]["family"] == ["H1", "H2", "H3", "H4", "H5", "H6"]       # H7 failed its check
    prim = [m for m in d["models"] if (m["model_id"], m["adjustment"], m["sample"]) == ("crush_drivers", "market", "daily")][0]
    h6 = [t for t in prim["terms"] if t["term"] == "ln_sigma_d" and t["statistic"] == "twoway_date_t"][0]
    assert h6["role"] == "primary" and h6["p_holm"] is not None and h6["note"] is None and h6["g1_size"] is None
    t = event_views.tests_data(res, events, P, PROV)
    assert t["holm"]["tested"] == ["H1", "H2", "H3", "H4", "H5", "H6", "H7"] and t["holm"]["left_family"] == []
    assert t["holm"]["untested"] == [] and any("(7 hypotheses)" in c for c in t["caveats"])
    assert any("H7 (16.00%) failed gate G1's regression size check" in c for c in t["caveats"])


def test_drivers_data_when_the_owner_gates_h5_h7(frame):
    # The owner's alternative (decisions table): H5-H7 gated like H1-H4, so a failed primary leaves the
    # binding family and its row is exploratory with the "left" note.
    h14 = synthetic_report(frame.ev.shape[0])
    h14.update(primary={h: r["_primary"] for h, r in h14["rates"]["calibrated"].items()}, power={})
    rep = g1_drivers.merge(h14, driver_part(False))
    rows, _ = run.result_rows(frame, ST, rep, COMMON, DP, gated=tuple(ST["holm_family"]))
    res = results.frame(rows)
    events, _, _ = tables(frame)
    d = driver_views.drivers_data(res, events, P, PROV)
    assert d["holm"]["family"] == ["H1", "H2", "H3", "H4"] and d["holm"]["left_family"] == ["H5", "H6", "H7"]
    prim = [m for m in d["models"] if (m["model_id"], m["adjustment"], m["sample"]) == ("crush_drivers", "market", "daily")][0]
    h5 = [t for t in prim["terms"] if t["term"] == "abs_surprise" and t["statistic"] == "twoway_date_t"][0]
    assert h5["role"] == "exploratory" and h5["p_holm"] is None and "left the binding Holm family" in h5["note"]
    assert any("left the binding Holm family" in c for c in d["caveats"])
    t = event_views.tests_data(res, events, P, PROV)
    assert t["holm"]["family"] == ["H1", "H2", "H3", "H4"] and t["holm"]["left_family"] == ["H5", "H6", "H7"]
    assert t["holm"]["tested"] == ["H1", "H2", "H3", "H4"]


def test_implied_vs_realised_points_and_summary(frame, failed):
    res, _, _ = failed
    events, measures, security = tables(frame)
    d = driver_views.implied_vs_realised_data(res, events, measures, security, P, PROV)
    n = frame.ev.shape[0]
    assert d["summary"]["n"] == len(d["points"]) == n
    pt = {x["event_id"]: x for x in d["points"]}
    ev0 = frame.ev.iloc[0]
    assert pt[ev0["event_id"]]["implied_var_total"] == pytest.approx(ev0["evar_m1"] + ev0["sigma_d_m1"] ** 2 / 252,
                                                                     abs=1e-8)
    assert d["summary"]["n_evar_nonpositive"] == 2 and d["summary"]["n_with_implied_abs_move"] == n - 2
    reg = res[(res["family"] == "regression") & (res["model_id"] == "implied_realised")]
    w = reg[reg["statistic"] == "twoway_date_wald"].iloc[0]
    assert d["summary"]["regression"]["wald_f"] == pytest.approx(round(w["stat"], 4))
    g = d["summary"]["regression"]
    assert g["role"] == "primary" and g["g1_pass"] is False and g["p_holm"] is not None
    assert (g["g1_rate"], g["g1_bar"], g["g1_rate_one_way"], g["g1_pass_one_way"]) == (0.16, 0.063, 0.17, False)
    assert g["wald_p_one_way"] is None                                       # withheld: G1 failed it
    assert any("stays in the declared Holm family" in c for c in d["caveats"])
    assert d["summary"]["share_exceed_benchmark"] == 0.425
    # An event without a realised move is not a point.
    m2 = measures.copy()
    m2.loc[0, "realized_ret_0"] = np.nan
    assert len(driver_views.implied_vs_realised_data(res, events, m2, security, P, PROV)["points"]) == n - 1


def test_tests_data_counts_h5_h7_and_keeps_power_to_h1_h4(frame, failed):
    res, rep, _ = failed
    events, _, _ = tables(frame)
    rep_h14 = dict(rep, power={})
    t = event_views.tests_data(res, events, P, PROV)
    # H5-H7 failed their size check but stay in the binding family with primary rows: tested.
    assert t["holm"]["tested"] == ["H1", "H2", "H3", "H4", "H5", "H6", "H7"]
    assert t["holm"]["untested"] == [] and t["holm"]["left_family"] == []
    assert t["holm"]["family"] == ["H1", "H2", "H3", "H4", "H5", "H6", "H7"]
    (cav,) = [c for c in t["caveats"] if c.startswith("Holm runs over")]
    assert cav.startswith("Holm runs over H1, H2, H3, H4, H5, H6, H7 (7 hypotheses). H5 (9.00%), H6 (9.00%), "
                          "H7 (16.00%) failed gate G1's regression size check")
    assert "over the family without them (H1, H2, H3, H4)" in cav and "H2's season cut" in cav
    assert {pw["hypothesis"] for pw in t["g1"]["power"]} <= {"H1", "H2", "H3", "H4"}
    assert rep_h14["gate"]["H5"] is False


def test_the_committed_files_are_at_the_new_version():
    for kind in ("drivers", "implied_vs_realised", "tests", "meta"):
        env = json.loads((ROOT / "app" / "public" / "data" / f"{kind}.json").read_text())
        assert env["schema_version"] == contract.SCHEMA_VERSION == "0.5.0" and env["kind"] == kind
    meta = json.loads((ROOT / "app" / "public" / "data" / "meta.json").read_text())["data"]
    assert meta["milestone"] == 4 and "drivers" in meta["files"] and "implied_vs_realised" in meta["files"]
