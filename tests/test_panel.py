# Tests for the panel layer (panel/abnormal.py, panel/window.py; ADR 0004 §1-§4, data model
# §3.10-§3.11): hand-worked fixtures, then invariants of the committed tables.
#
# Mutations this module must catch (applied by a script, each seen to fail, file restored by SHA-256):
#   - beta counting a (security, session) change twice when two baselines share it
#   - ALIV with the VIX term added instead of subtracted
#   - the baseline mean over every usable session instead of B
#   - s_i with ddof 0
#   - the coarse change count allowing a span across another event's zone
#   - the daily crush accepting day -2 as its pre session
#   - persist_10 eligible beyond the data end
#
# Added after the milestone-3 review (each seen to fail on a scratch copy, file restored and its
# SHA-256 checked; [p08 Mxx] = the review's probe docs/validation/probes/m3/p08_mutants.py,
# [fix] = the fix round's script, milestone page §9):
#   - beta pooling the changes of baselines below the 20/15 minimum [fix, F2]
#   - a coarse change spanning a null_iv session [p08 M08]
#   - coarse PERSIST trying +h+1 before +h-1 [p08 M09]
#   - daily PERSIST falling back to +-1 like coarse [p08 M10]

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from earnings_vol import params, schema, store
from earnings_vol.events import calendar
from earnings_vol.export import funnel
from earnings_vol.panel import abnormal, window

DERIVED = Path(__file__).resolve().parents[1] / "data" / "derived"


def test_beta_through_the_origin_counts_each_session_once():
    # One security, two events whose windows both hold sessions 10, 11, 12. Event a has the
    # clean change into 11 (dX 0.02, dM 0.04); event b has the same change into 11 and one into
    # 12 (dX -0.01, dM 0.01). Each (security, session) once: (0.02, 0.04) and (-0.01, 0.01):
    #   beta = (0.02*0.04 + -0.01*0.01) / (0.04^2 + 0.01^2) = (0.0008 - 0.0001)/0.0017 = 0.411765.
    # Counting session 11 twice would give (0.0016 - 0.0001)/0.0033 = 0.454545.
    sess = np.array([[10, 11, 12], [10, 11, 12]])
    dX = np.array([[np.nan, 0.02, np.nan], [np.nan, 0.02, -0.01]])
    dM = np.array([[np.nan, 0.04, np.nan], [np.nan, 0.04, 0.01]])
    clean = np.isfinite(dX)
    got = abnormal.beta_by_security(np.array(["S", "S"]), sess, dX, dM, clean)
    assert got["S"][0] == pytest.approx(0.0007 / 0.0017) and got["S"][1] == 2


def test_aliv_and_the_baseline_sd_hand_worked():
    # x = 0.10, 0.12, 0.11, 0.30 with B = the first three; m = 0, 0.1, 0.0, 0.2; beta = 0.5.
    # mu = 0.11, mu^m = 0.1/3 = 0.033333. ALIV_3 = (0.30 - 0.11) - 0.5 (0.2 - 0.033333) = 0.106667.
    # e: dx 0.02, -0.01, 0.19; dm 0.1, -0.1, 0.2 -> e = -0.03, 0.04, 0.09. Clean (both ends in B):
    # columns 1 and 2 -> e = -0.03, 0.04, mean 0.005, sd (ddof 1) = sqrt((0.035^2*2)/1) = 0.049497.
    x = np.array([[0.10, 0.12, 0.11, 0.30]])
    m = np.array([[0.0, 0.1, 0.0, 0.2]])
    b = np.array([[True, True, True, False]])
    al, al0 = abnormal.aliv(x, m, b, np.array([0.5]))
    assert al[0, 3] == pytest.approx(0.19 - 0.5 * (0.2 - 0.1 / 3), abs=1e-15)
    assert al0[0, 3] == pytest.approx(0.19, abs=1e-15)
    e = abnormal.abnormal_changes(x, m, np.array([0.5]))
    assert e[0, 1:].tolist() == pytest.approx([-0.03, 0.04, 0.09])
    assert abnormal.baseline_sd(e, abnormal.clean_changes(b))[0] == pytest.approx(np.sqrt(2 * 0.035 ** 2), abs=1e-15)


# --- a two-event fixture, one security, every number by hand -------------------------------------
@pytest.fixture(scope="module")
def fixture():
    eras = {"weekly_from": "2019-02-09", "mwf_from": "2020-01-06", "daily_from": "2024-09-11",
            "data_end": "2026-10-26"}
    tbl = calendar.build_session_table(date(2024, 1, 1), date(2026, 12, 31), eras)
    s = calendar.Sessions(tbl["session_date"].tolist())
    d1 = s.index[date(2025, 6, 2)]
    d2 = d1 + 63
    old = s.index[date(2024, 3, 1)]
    # x_t = 0.01 t, minus 0.2 from E1's day 0 on; m_t = 0.02 t. Every session usable except E2's
    # day -1 (d2 - 1). So every clean baseline change has dX = 0.01, dM = 0.02 and beta = 0.5.
    look = {"observed": set(), "cm30": {}, "sigma_d": {}, "event_var": {}, "ln_vix": {}}
    for t in range(old - 70, d2 + 20):
        look["ln_vix"][t] = 0.02 * t
        if t == d2 - 1:
            continue
        look["observed"].add(("X", t))
        look["cm30"][("X", t)] = float(np.exp(0.01 * t - (0.2 if t >= d1 else 0.0)))
        look["sigma_d"][("X", t)] = 0.25
    ev = pd.DataFrame({
        "event_id": ["X:old", "X:e1", "X:e2"], "security_id": "X",
        "day0_session": [s.dates[old], s.dates[d1], s.dates[d2]],
        "announce_date_used": [s.dates[old], s.dates[d1], s.dates[d2]],
        "exclusion_reason": ["outside_samples", None, None], "sample": ["none", "daily", "daily"]}).astype(object)
    eiv = pd.DataFrame({"event_id": ev["event_id"],
                        "pre_session": [None, s.dates[d1 - 1], s.dates[d2 - 2]],
                        "post_session": [None, s.dates[d1], s.dates[d2]],
                        "dsigma_d_mean_adj": [None, 0.05, None]}).astype(object)
    for c in window.IV_COPY:
        if c not in eiv:
            eiv[c] = None
    eps = pd.DataFrame(columns=["security_id", "fiscal_period_end", "event_id", "match_status"])
    w = dict(params.load()["windows"])
    pan = window.build_panel(ev, eps, look, s, w)
    m = window.measures(pan, eiv, s, w, data_end_index=d2 + 5)
    return {"s": s, "d1": d1, "d2": d2, "pan": pan, "m": m, "ev": ev, "eiv": eiv}


def test_window_rows_and_baselines(fixture):
    pan = fixture["pan"]
    # Two events get window rows (the excluded one does not), 71 columns each.
    assert pan.events["event_id"].tolist() == ["X:e1", "X:e2"] and pan.session.shape == (2, 71)
    # E1: [-60, -22] all clean (E2's zone [-21, +10] around d2 = d1 + 63 starts at +42): 39 sessions.
    # E2: [-60, -22] is E1's rel [3, 41]; E1's zone covers rel <= 10, i.e. E2's [-60, -53]: 8 out,
    # 31 clean sessions and 30 one-session changes.
    m = fixture["m"]
    assert m["n_sessions"].tolist() == [39, 31] and m["n_changes"].tolist() == [38, 30]
    assert pan.reason[1, abnormal.col(-60)] == "other_event_zone" and pan.reason[1, abnormal.col(-52)] is None
    assert pan.reason[0, abnormal.col(-5)] == "outside"
    assert not pan.usable[1, abnormal.col(-1)] and pan.observed[1, abnormal.col(-2)]


def test_beta_alive_crush_and_persistence_by_hand(fixture):
    m = fixture["m"]
    # beta = sum(0.01 * 0.02) / sum(0.02^2) = 0.5 over every clean change.
    assert m["beta"].tolist() == pytest.approx([0.5, 0.5]) and m["beta_n"][0] == 38 + 30
    v = m["values"]
    # E1 CRUSH: dx_0 = 0.01 - 0.2 = -0.19, dm_0 = 0.02 -> e_0 = -0.19 - 0.5 * 0.02 = -0.20.
    assert v["crush"][0] == pytest.approx(-0.20, abs=1e-12)
    # E1 RUNUP: the series is linear before day 0 and beta * dm = dx: ALIV_-1 = 0.
    # PERSIST_10: x_10 lost 0.2, the VIX term is still 0.5 * (m - mean m) = (x - mean x) + 0.2: -0.2.
    assert v["runup"][0] == pytest.approx(0.0, abs=1e-12) and v["persist_10"][0] == pytest.approx(-0.2, abs=1e-12)
    # DSIGMA_D: 0.05 - 0.5 * 0.02 = 0.04.
    assert v["dsigma_d"][0] == pytest.approx(0.04, abs=1e-12)
    assert m["eligible"]["crush"].tolist() == [True, False]


def test_eligibility_reasons_in_their_order(fixture):
    m = fixture["m"]
    # E2: day -1 unobserved -> crush and runup "missing_m1" (daily never falls back to day -2);
    # day +10 = d2 + 10 > the data end d2 + 5 -> persist_10 "beyond_data_end", before anything else.
    assert [m["reason"][k][1] for k in ("crush", "runup", "persist_10")] == ["missing_m1", "missing_m1",
                                                                             "beyond_data_end"]
    assert np.isnan(m["values"]["crush"][1])
    em = window.measures_table(fixture["ev"], fixture["eiv"], fixture["pan"], m, schema.EVENT_MEASURES.names)
    r = em.set_index("event_id")
    assert r.loc["X:e2", "ineligible_reason"] == "crush:missing_m1|persist_10:beyond_data_end|runup:missing_m1"
    assert r.loc["X:old", "ineligible_reason"] == "crush:event_excluded|persist_10:event_excluded|runup:event_excluded"
    assert r.loc["X:e1", "ineligible_reason"] == "" and r.loc["X:old", "baseline_n"] == 0
    store.validate(em, schema.EVENT_MEASURES)


def test_beta_pools_only_baselines_that_pass_the_minimum():
    # ADR 0004 §1: an event below the 20-session / 15-change minimum "gets no baseline and is
    # excluded from every measure that needs one". beta needs baselines, so its changes stay out.
    # One security, two events 150 sessions apart (no zone touches the other's baseline):
    #   A (day 0 = d1): every session observed, x_t = 0.01 t, m_t = 0.02 t: 39 clean sessions,
    #     38 one-session changes, each dX = 0.01, dM = 0.02.
    #   B (day 0 = d2 = d1 + 150): only rel -40 .. -31 observed: 10 clean sessions, 9 changes,
    #     fails the minimum; there x_t = 0.03 t, so each change has dX = 0.03, dM = 0.02.
    # beta over A only: 38 * 0.0002 / (38 * 0.0004) = 0.5, n = 38.
    # Pooling B's changes too: (38 * 0.0002 + 9 * 0.0006) / (47 * 0.0004) = 0.013 / 0.0188 = 0.691489, n = 47.
    eras = {"weekly_from": "2019-02-09", "mwf_from": "2020-01-06", "daily_from": "2024-09-11",
            "data_end": "2026-10-26"}
    tbl = calendar.build_session_table(date(2024, 1, 1), date(2026, 12, 31), eras)
    s = calendar.Sessions(tbl["session_date"].tolist())
    d1 = s.index[date(2025, 3, 3)]
    d2 = d1 + 150
    look = {"observed": set(), "cm30": {}, "sigma_d": {}, "event_var": {}, "ln_vix": {}}
    for t in range(d1 - 70, d2 + 20):
        look["ln_vix"][t] = 0.02 * t
        if t <= d1 + 10 or d2 - 40 <= t <= d2 - 31:
            look["observed"].add(("Y", t))
            look["cm30"][("Y", t)] = float(np.exp((0.01 if t <= d1 + 10 else 0.03) * t))
    ev = pd.DataFrame({"event_id": ["Y:a", "Y:b"], "security_id": "Y",
                       "day0_session": [s.dates[d1], s.dates[d2]], "announce_date_used": [s.dates[d1], s.dates[d2]],
                       "exclusion_reason": [None, None], "sample": ["daily", "daily"]}).astype(object)
    eiv = pd.DataFrame({"event_id": ev["event_id"], "pre_session": [s.dates[d1 - 1], None],
                        "post_session": [s.dates[d1], None], "dsigma_d_mean_adj": [None, None]}).astype(object)
    for c in window.IV_COPY:
        eiv[c] = None
    eps = pd.DataFrame(columns=["security_id", "fiscal_period_end", "event_id", "match_status"])
    w = dict(params.load()["windows"])
    pan = window.build_panel(ev, eps, look, s, w)
    m = window.measures(pan, eiv, s, w, data_end_index=d2 + 20)
    assert m["n_sessions"].tolist() == [39, 10] and m["n_changes"].tolist() == [38, 9]
    assert m["base_ok"].tolist() == [True, False]
    assert m["beta"].tolist() == pytest.approx([0.5, 0.5], abs=1e-12)
    assert m["beta_n"].tolist() == [38, 38]
    # A's crush uses that beta: dx_0 = 0.01, dm_0 = 0.02 -> e_0 = 0.01 - 0.5 * 0.02 = 0.
    assert m["values"]["crush"][0] == pytest.approx(0.0, abs=1e-12)


def test_coarse_changes_span_unobserved_sessions_only():
    # Baseline columns 0, 2, 3, 5 of one coarse event; 1 unobserved, 4 in another event's zone.
    # 0->2 spans one unobserved session: counts (span 2); 2->3: counts; 3->5 is a span of 2 too, but
    # across a zone, so it does not count: 2. With a 1-session limit only 2->3 counts: 1.
    pan = window.Panel(pd.DataFrame({"sample": ["coarse"]}), None, None, None,
                       np.array([[True, False, True, True, False, True]]),
                       np.array([[None, "not_observed", None, None, "other_event_zone", None]],
                                dtype=object), None, None, None, None, None)
    assert window.change_counts(pan, {"coarse": 2}).tolist() == [2]
    assert window.change_counts(pan, {"coarse": 1}).tolist() == [1]


def test_a_coarse_change_never_spans_a_session_with_a_snapshot_but_no_iv():
    # ADR 0004 §4: a span change crosses UNOBSERVED sessions only. A session that was observed
    # but has no cm30_iv (null_iv) is a data failure, not a Mon/Wed/Fri gap. Baseline columns
    # 0, 2, 4; column 1 null_iv, column 3 not_observed: 0->2 does not count, 2->4 does: 1.
    pan = window.Panel(pd.DataFrame({"sample": ["coarse"]}), None, None, None,
                       np.array([[True, False, True, False, True]]),
                       np.array([[None, "null_iv", None, "not_observed", None]], dtype=object),
                       None, None, None, None, None)
    assert window.change_counts(pan, {"coarse": 2}).tolist() == [1]


def test_coarse_persistence_tries_the_session_before_the_target_first():
    # ADR 0004 §4: coarse RUNUP/PERSIST use the nearest usable session within one of the target;
    # the header's order is +h, +h-1, +h+1. PERSIST_5 with +5 unusable and both +4 and +6
    # usable reads +4; only +6 usable: +6; neither: None. Daily never leaves +h.
    usable = np.zeros((1, abnormal.REL_DAYS.size), bool)
    usable[0, [abnormal.col(4), abnormal.col(6)]] = True
    pan = window.Panel(None, None, None, usable, None, None, None, None, None, None, None)
    assert window._target_col(pan, 0, 5, True) == abnormal.col(4)
    assert window._target_col(pan, 0, 5, False) is None
    usable[0, abnormal.col(4)] = False
    assert window._target_col(pan, 0, 5, True) == abnormal.col(6)
    usable[0, abnormal.col(6)] = False
    assert window._target_col(pan, 0, 5, True) is None


def test_daily_persistence_reads_exactly_its_target_session():
    # ADR 0004 §3/§5: in `daily` PERSIST_h is ALIV at exactly +h; only `coarse` may move one
    # session (§4). One daily event, every session observed except day +10, so +9 and +11
    # are usable: PERSIST_10 must be missing (reason missing_target), not read at +9.
    # x_t = 0.01 t, m_t = 0.02 t (beta 0.5, every abnormal change 0): PERSIST_5 = ALIV_+5 = 0.
    eras = {"weekly_from": "2019-02-09", "mwf_from": "2020-01-06", "daily_from": "2024-09-11",
            "data_end": "2026-10-26"}
    tbl = calendar.build_session_table(date(2024, 1, 1), date(2026, 12, 31), eras)
    s = calendar.Sessions(tbl["session_date"].tolist())
    d1 = s.index[date(2025, 6, 2)]
    look = {"observed": set(), "cm30": {}, "sigma_d": {}, "event_var": {}, "ln_vix": {}}
    for t in range(d1 - 70, d1 + 20):
        look["ln_vix"][t] = 0.02 * t
        if t != d1 + 10:
            look["observed"].add(("Z", t))
            look["cm30"][("Z", t)] = float(np.exp(0.01 * t))
    ev = pd.DataFrame({"event_id": ["Z:a"], "security_id": "Z", "day0_session": [s.dates[d1]],
                       "announce_date_used": [s.dates[d1]], "exclusion_reason": [None],
                       "sample": ["daily"]}).astype(object)
    eiv = pd.DataFrame({"event_id": ev["event_id"], "pre_session": [s.dates[d1 - 1]], "post_session": [s.dates[d1]],
                        "dsigma_d_mean_adj": [None]}).astype(object)
    for c in window.IV_COPY:
        eiv[c] = None
    eps = pd.DataFrame(columns=["security_id", "fiscal_period_end", "event_id", "match_status"])
    w = dict(params.load()["windows"])
    m = window.measures(window.build_panel(ev, eps, look, s, w), eiv, s, w, data_end_index=d1 + 19)
    assert m["reason"]["persist_10"] == ["missing_target"] and not m["eligible"]["persist_10"][0]
    assert np.isnan(m["values"]["persist_10"][0])
    assert m["values"]["persist_5"][0] == pytest.approx(0.0, abs=1e-12) and m["eligible"]["crush"][0]


# --- the committed tables -----------------------------------------------------------------------------
@pytest.fixture(scope="module")
def committed():
    names = ("events", "event_window_obs", "event_measures", "event_iv", "iv_daily", "eps", "session")
    return {n: store.read_table(DERIVED / f"{n}.parquet", store.committed_schema(schema.REGISTRY[n])) for n in names}


def test_committed_window_rows_hold_the_baseline_rules(committed):
    w = committed["event_window_obs"]
    ev = committed["events"]
    assert set(w["event_id"]) == set(ev.loc[ev["exclusion_reason"].isna(), "event_id"])
    assert (w.groupby("event_id").size() == 71).all()
    b = w[w["in_baseline"]]
    assert b["observed"].all() and b["cm30_iv"].notna().all() and b["rel_day"].between(-60, -22).all()
    assert w.loc[~w["rel_day"].between(-60, -22), "baseline_excluded_reason"].eq("outside").all()
    # ALIV0 = x - mean_B x, so it averages to 0 over B for every event with a baseline.
    means = b.dropna(subset=["aliv_mean_adj"]).groupby("event_id")["aliv_mean_adj"].mean()
    assert means.abs().max() < 1e-12


def test_the_primary_crush_sample_is_the_funnel_s_last_step(committed):
    em = committed["event_measures"].merge(committed["events"][["event_id", "sample"]], on="event_id")
    mine = set(em.loc[em["eligible_crush"] & (em["sample"] == "daily"), "event_id"])
    _, last = funnel.run_steps(committed["events"], committed["iv_daily"], committed["eps"], committed["session"],
                               params.load())
    assert mine == set(last["event_id"]) and len(mine) == 347
    # event_measures is 1:1 with events and carries event_iv's crush unchanged.
    assert len(em) == len(committed["events"]) == em["event_id"].nunique()
    j = committed["event_measures"].merge(committed["event_iv"], on="event_id", suffixes=("", "_iv"))
    assert np.allclose(j["crush_mean_adj"], j["crush_mean_adj_iv"], equal_nan=True)
