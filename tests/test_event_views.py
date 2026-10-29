# Tests for export/event_views.py (contract 0.4.0) on hand-built tables, every expected value
# worked out in the comments.
#
# Mutations this module must catch (applied by hand, each seen to fail):
#   - the company grid averaging over every event instead of the primary sample (eligible_crush, daily)
#   - the company grid ordered by ticker instead of sector, then security_id
#   - a G1 calibrated row marked passing above the band's top (6.30% at 2,000)
#   - power rows taken from a robustness statistic instead of the primary
#   - a company x season cell filled when the company has two events in that season
#   - p-values rounded to 4 decimals instead of 4 significant figures
#   - the oversized-row caveat left empty (re-run in the fix round [fix])
#
# Added after the milestone-3 review (each seen to fail on a scratch copy, file restored and its
# SHA-256 checked; [p08 Mxx] = the review's probe docs/validation/probes/m3/p08_mutants.py,
# [fix] = the fix round's script, milestone page §9):
#   - a withheld row's g1_size dropped [fix]
#   - the season-cut verdict compared the wrong way round [fix]
#   - the season-cut labels swapped (the earlier season named as merged into the later) [fix]
#
# Added in the second fix round (each seen to fail on a scratch copy, file restored and its SHA-256
# checked; [fix2] = this round's script, milestone page §9 second round):
#   - a withheld row's g1_reps dropped [fix2]
#   - a re-measured row that keeps its p-value left without a note [fix2]
#   - the re-measured rates listed among the 2,000-replication designs [fix2]
#   - a row the verdicts call oversized that keeps a p-value passed through silently [fix2]

from datetime import date

import pandas as pd
import pytest

from earnings_vol import params, schema
from earnings_vol.export import event_views
from earnings_vol.stats import results

P = params.load()


def tables():
    # Three companies: B (Financials), A and C (Information Technology). Primary events: A1, A2, B1, C1;
    # A3 is daily but not crush-eligible, X1 is coarse: both are left out of every grid.
    ev = pd.DataFrame({
        "event_id": ["A1", "A2", "A3", "B1", "C1", "X1"],
        "security_id": ["A", "A", "A", "B", "C", "A"],
        "ticker_at_event": ["AA", "AA", "AA", "BB", "CC", "AA"],
        "sample": ["daily"] * 5 + ["coarse"],
        "season": ["2025Q1", "2025Q1", "2025Q2", "2025Q1", "2025Q2", "2021Q1"],
        "day0_session": [date(2025, 2, 3), date(2025, 3, 3), date(2025, 5, 1), date(2025, 2, 4), date(2025, 5, 2),
                         date(2021, 2, 1)],
        "timing_used": ["AMC", "BMO", "AMC", "BMO", "AMC", "BMO"],
        "timing_status": ["confirmed"] + ["not_checked"] * 5})
    em = pd.DataFrame({"event_id": ev["event_id"], "eligible_crush": [True, True, False, True, True, True],
                       "crush_mean_adj": [-0.1, -0.3, -0.9, -0.2, -0.4, -0.9]})
    sec = pd.DataFrame({"security_id": ["A", "B", "C"], "gics_sector": ["Information Technology", "Financials",
                                                                      "Information Technology"]})
    rows = []
    for eid, vals in {"A1": (0.10, -0.02), "A2": (0.30, None), "A3": (5.0, 5.0), "B1": (0.05, 0.01),
                      "C1": (0.20, -0.10), "X1": (9.0, 9.0)}.items():
        for rel in range(-10, 11):
            v = vals[0] if rel == -1 else vals[1] if rel == 0 else 0.0
            rows.append({"event_id": eid, "rel_day": rel, "aliv_mean_adj": v})
    return ev, em, sec, pd.DataFrame(rows)


def test_company_grid_means_over_primary_events_in_sector_order():
    ev, em, sec, ewo = tables()
    rows, values, ns = event_views.company_grid(ewo, ev, em, sec)
    # Sector order: Financials (B), then Information Technology (A, C).
    assert [r["security_id"] for r in rows] == ["B", "A", "C"]
    assert [r["n_events"] for r in rows] == [1, 2, 1]
    j_m1, j_0 = 9, 10                                    # rel_day -1 and 0 in -10 .. +10
    # A at day -1: mean(0.10, 0.30) = 0.20 over n = 2; at day 0 A2 is missing: -0.02 alone, n = 1.
    assert values[1][j_m1] == pytest.approx(0.2) and ns[1][j_m1] == 2
    assert values[1][j_0] == pytest.approx(-0.02) and ns[1][j_0] == 1
    assert values[0][j_m1] == pytest.approx(0.05) and values[2][j_0] == pytest.approx(-0.10)


def test_heatmap_season_grid_needs_exactly_one_event_per_cell():
    ev, em, sec, ewo = tables()
    h = event_views.heatmap_data(ewo, ev, em, sec, P, {})
    g = {x["id"]: x for x in h["grids"]}["company_by_season"]
    assert g["col_labels"] == ["2025Q1", "2025Q2"] and g["row_keys"] == ["B", "A", "C"]
    # A has two primary events in 2025Q1 (A1, A2): no single event, so null with n = 2.
    assert g["values"] == [[-0.2, None], [None, None], [None, -0.4]]
    assert g["n"] == [[1, 0], [2, 0], [0, 1]]
    assert h["lookups"] == {"n_done": 1, "complete": False}
    assert "provisional" in h["caveats"][0]


def g1_row(design, h, stat, rate, role="primary", n=2000):
    return results.row(family="validation", hypothesis=h, role=role, measure=f"g1:{design}", statistic=stat,
                       sample="daily", subgroup_key="all", subgroup_value="all", adjustment="market", n=n,
                       estimate=rate, params_hash="h", code_commit="c")


def test_tests_view_g1_verdicts_power_and_rounding():
    ev, *_ = tables()
    rows = [
        # The binding rates: 6.30% passes (126/2000 is the band's top), 6.35% does not.
        g1_row("calibrated", "H1", "twoway_date_t", 0.063), g1_row("calibrated", "H3", "twoway_season_t", 0.0635),
        g1_row("calibrated", "H1", "cluster_date_t", 0.20, role="robustness"),
        # Power: primary rows only, sorted by shift; 80% between 0.02 (0.6) and 0.03 (0.9): 0.02 + 0.2/0.3 * 0.01.
        g1_row("power_crush:0.03", "H1", "twoway_date_t", 0.9), g1_row("power_crush:0.02", "H1", "twoway_date_t", 0.6),
        g1_row("power_crush:0.02", "H1", "cluster_date_t", 0.99, role="robustness"),
        results.row(family="event_test", hypothesis="H1", role="primary", measure="crush_cm30",
                    statistic="twoway_date_t", estimand="equal_weighted", sample="daily", subgroup_key="all",
                    subgroup_value="all", adjustment="market", n=347, n_clusters=150, n_clusters_firm=50, df=49.0,
                    estimate=-0.21234567, se=0.01, stat=-21.234567, p_value=1.23456789e-26, p_holm=8.6419e-26,
                    ci_lo=-0.23, ci_hi=-0.19, params_hash="h", code_commit="c"),
    ]
    out = event_views.tests_data(results.frame(rows), ev, P, {})
    cal = {c["hypothesis"]: c for c in out["g1"]["calibrated"]}
    assert cal["H1"]["pass"] is True and cal["H3"]["pass"] is False
    assert out["g1"]["band"] == [0.038, 0.063]
    assert out["g1"]["power"] == [{"hypothesis": "H1", "shifts": [0.02, 0.03], "power": [0.6, 0.9],
                                   "detectable_80": pytest.approx(0.0267, abs=1e-4)}]
    assert out["holm"]["left_family"] == ["H3"] and "H3" not in out["holm"]["family"]
    r = out["rows"][0]
    # 4 decimals for log quantities, 4 significant figures for p-values.
    assert r["estimate"] == -0.2123 and r["p_value"] == 1.235e-26 and r["n_clusters_firm"] == 50
    assert r["units"] == "log change of the 30-day IV"
    assert set(out) == {"rows", "g1", "holm", "lookups", "caveats", "provenance"}
    # The robustness row above the band (H1 cluster_date_t, 20%) is named in a caveat; the primary is not.
    assert any("H1 cluster_date_t 20.00%" in c for c in out["caveats"])
    assert not any("twoway_date_t" in c for c in out["caveats"])
    assert set(schema.RESULTS.names) >= {"df_num"}


def test_withheld_rows_and_the_season_cut_get_notes():
    # A robustness row G1 found oversized (H1 cluster_date_t at 24.1% > 6.30%) arrives from the
    # stats layer with its p-value and interval null: it gets g1_size 0.241 and a note naming the
    # rate. The H2 primary on its rad_season_p floor (G = 8, 2/256 = 0.0078125) gets a note with its
    # season-cut counterfactual (G = 7: p 0.015625, Holm p 0.09375 > 0.05, not rejected) and the
    # two-way t; the counterfactual row explains its own p_holm.
    ev, *_ = tables()
    common = dict(family="event_test", sample="daily", adjustment="market", params_hash="h", code_commit="c")
    rows = [
        g1_row("calibrated", "H1", "twoway_date_t", 0.046), g1_row("calibrated", "H2", "rad_season_p", 0.004),
        g1_row("calibrated", "H1", "cluster_date_t", 0.241, role="robustness"),
        results.row(hypothesis="H1", role="robustness", measure="crush_cm30", statistic="cluster_date_t",
                    subgroup_key="all", subgroup_value="all", n=347, n_clusters=172, df=171.0, estimate=-0.2,
                    se=0.0064, stat=-31.0, **common),
        results.row(hypothesis="H2", role="primary", measure="runup", statistic="rad_season_p", subgroup_key="all",
                    subgroup_value="all", n=356, n_clusters=8, estimate=0.23, stat=17.3, p_value=0.0078125,
                    p_holm=0.046875, **common),
        results.row(hypothesis="H2", role="robustness", measure="runup", statistic="twoway_season_t",
                    subgroup_key="all", subgroup_value="all", n=356, n_clusters=8, n_clusters_firm=50, df=7.0,
                    estimate=0.23, se=0.0167, stat=13.82, p_value=2.5e-6, ci_lo=0.19, ci_hi=0.27, **common),
        results.row(hypothesis="H2", role="robustness", measure="runup", statistic="rad_season_p",
                    subgroup_key="season_cut", subgroup_value="2026Q4_into_2026Q3", n=356, n_clusters=7,
                    estimate=0.23, stat=15.0, p_value=0.015625, p_holm=0.09375, **common),
    ]
    out = event_views.tests_data(results.frame(rows), ev, P, {})
    by = {(r["hypothesis"], r["statistic"], r["subgroup_key"]): r for r in out["rows"]}
    w = by[("H1", "cluster_date_t", "all")]
    assert w["p_value"] is None and w["g1_size"] == 0.241 and "24.10%" in w["note"] and "6.30%" in w["note"]
    assert w["g1_reps"] == 2000 and "over 2,000 replications" in w["note"]
    h2 = by[("H2", "rad_season_p", "all")]
    assert h2["g1_size"] is None and "8 season clusters" in h2["note"] and "0.007812" in h2["note"]
    assert "2026Q4 merged into 2026Q3 (7 clusters" in h2["note"] and "0.09375: not rejected" in h2["note"]
    assert "two-way t is 13.8" in h2["note"]
    cut = by[("H2", "rad_season_p", "season_cut")]
    assert cut["p_holm"] == 0.09375 and "not a test of its own" in cut["note"]
    assert by[("H2", "twoway_season_t", "all")]["note"] is None
    assert any("withheld" in c and "H1 cluster_date_t 24.10%" in c for c in out["caveats"])


def near_bar_tables(bmp_p=0.92, bmp_again=0.0534):
    """H4 with three robustness rates on 2,000 replications: the sign test 6.75% and BMP 6.05%, both
    within one point of 6.30%, re-measured on 10,000 at 5.68% and 5.34%; the rank test 13.65%, far
    above, decided on 2,000."""
    common = dict(family="event_test", sample="daily", adjustment="market", subgroup_key="all", subgroup_value="all",
                  n=262, params_hash="h", code_commit="c", hypothesis="H4", measure="dsigma_d")
    return [
        g1_row("calibrated", "H4", "twoway_date_t", 0.046),
        g1_row("calibrated", "H4", "gen_sign_z", 0.0675, role="robustness"),
        g1_row("calibrated", "H4", "bmp_t", 0.0605, role="robustness"),
        g1_row("calibrated", "H4", "rank_t", 0.1365, role="robustness"),
        g1_row("calibrated_remeasured", "H4", "gen_sign_z", 0.0568, role="robustness", n=10000),
        g1_row("calibrated_remeasured", "H4", "bmp_t", bmp_again, role="robustness", n=10000),
        results.row(role="primary", statistic="twoway_date_t", estimate=0.003, se=0.011, stat=0.28, df=46.0,
                    p_value=0.78, p_holm=1.0, ci_lo=-0.02, ci_hi=0.03, n_clusters=134, n_clusters_firm=47, **common),
        results.row(role="robustness", statistic="gen_sign_z", estimate=0.47, stat=-0.6, **common),
        results.row(role="robustness", statistic="bmp_t", estimate=0.05, se=0.5, stat=0.1, p_value=bmp_p,
                    ci_lo=-0.9, ci_hi=1.0, **common),
        results.row(role="robustness", statistic="rank_t", estimate=-0.015, stat=-0.9, **common),
    ]


def test_a_near_bar_rate_is_decided_on_its_remeasured_replications():
    # The sign test: 5.68% on 10,000 is above 5.57% (that count's bar) although 6.75% on 2,000 was
    # what put it near 6.30%: withheld, g1_size 0.0568 with g1_reps 10,000. BMP: 5.34% on 10,000 is
    # inside: it keeps its p-value and says why. The rank test: 13.65% on 2,000, withheld on 2,000.
    ev, *_ = tables()
    out = event_views.tests_data(results.frame(near_bar_tables()), ev, P, {})
    by = {r["statistic"]: r for r in out["rows"]}
    s = by["gen_sign_z"]
    assert (s["g1_size"], s["g1_reps"], s["p_value"]) == (0.0568, 10000, None)
    assert "5.68%" in s["note"] and "over 10,000 replications" in s["note"] and "5.57%" in s["note"]
    b = by["bmp_t"]
    assert b["p_value"] == 0.92 and b["g1_size"] is None and b["g1_reps"] is None
    assert b["note"].startswith("p-value kept") and "5.34%" in b["note"] and "10,000" in b["note"]
    r = by["rank_t"]
    assert (r["g1_size"], r["g1_reps"]) == (0.1365, 2000) and "6.30%" in r["note"]
    assert by["twoway_date_t"]["g1_size"] is None and by["twoway_date_t"]["note"] is None
    # g1.reps and the designs stay the 2,000-replication run's; the re-measure is in the rows and the caveats.
    assert out["g1"]["reps"] == 2000 and {d["design"] for d in out["g1"]["designs"]} == {"calibrated"}
    assert any("H4 gen_sign_z 5.68% (on 10,000)" in c and "H4 rank_t 13.65%" in c for c in out["caveats"])
    assert any("H4 bmp_t 5.34% on 10,000, p-value kept" in c for c in out["caveats"])


def test_a_row_the_gate_calls_oversized_but_that_keeps_its_p_value_is_refused():
    # BMP re-measured at 6.00% on 10,000 (> 5.57%) must have arrived withheld; with a p-value the
    # export stops instead of showing a p-value the rule drops.
    ev, *_ = tables()
    with pytest.raises(ValueError, match="H4 bmp_t: G1 finds it oversized but it keeps a p-value"):
        event_views.tests_data(results.frame(near_bar_tables(bmp_again=0.06)), ev, P, {})
