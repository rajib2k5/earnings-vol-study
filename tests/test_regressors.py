# Tests for panel/regressors.py: the regressor columns of event_measures (data model §3.11,
# ADR 0005 §3), filled at milestone 4. Hand-worked fixtures with made-up numbers, then invariants
# of the committed table.
#
# Mutations this module must catch (each applied to a scratch copy, the test seen to fail, the file
# restored and its SHA-256 checked; milestone page appendix):
#   - price_ref = forward only (the discount factor dropped)
#   - price_ref read from any ok expiry of the pre session, not the front one
#   - surprise_scaled = surprise * price_ref
#   - winsorise over all events instead of within each sample
#   - regressor_table winsorising |SURP| over all samples together (the call, not the helper; the
#     milestone-4 review's surviving mutant M25)
#   - sue_hist's sd with ddof 0
#   - sue_hist using the previous n_prev + 1 values (the window off by one)
#   - sue_hist in input order instead of day-0 order
#   - sue_hist computed with fewer than sue_min_prev previous values (>= changed to >)
#   - vix_regime putting a value on a cut point in the upper bin
#   - vix_regime cut over every sample together
#   - the Yahoo return without the dividend added back
#   - ln_mcap against the first close of the file instead of the last

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from earnings_vol import params, schema, store
from earnings_vol.events import calendar
from earnings_vol.panel import regressors

DERIVED = Path(__file__).resolve().parents[1] / "data" / "derived"
D = date


def test_price_ref_is_forward_times_df_of_the_front_expiry_at_the_pre_session():
    # E1: A at pre 2025-01-02, front expiry 2025-01-17: 100 x 0.998 = 99.8 (not the 2025-01-31
    #     expiry's 101 x 0.99). E2: no pre session. E3: no front expiry. E4: the front expiry has
    #     no forward (status no_forward). Only E1 gets a price.
    events = pd.DataFrame({"event_id": ["E1", "E2", "E3", "E4"], "security_id": ["A", "A", "B", "B"]})
    eiv = pd.DataFrame({"event_id": ["E1", "E2", "E3", "E4"],
                        "pre_session": [D(2025, 1, 2), None, D(2025, 1, 3), D(2025, 1, 6)]})
    iv = pd.DataFrame({"security_id": ["A", "B", "B"], "session_date": [D(2025, 1, 2), D(2025, 1, 3), D(2025, 1, 6)],
                       "front_expiry": [D(2025, 1, 17), None, D(2025, 1, 17)]})
    ce = pd.DataFrame({"security_id": ["A", "A", "B"], "session_date": [D(2025, 1, 2), D(2025, 1, 2), D(2025, 1, 6)],
                       "expiration": [D(2025, 1, 31), D(2025, 1, 17), D(2025, 1, 17)],
                       "forward": [101.0, 100.0, np.nan], "df": [0.99, 0.998, 0.998],
                       "status": ["ok", "ok", "no_forward"]})
    got = regressors.price_ref(eiv, events, iv, ce)
    assert got == {"E1": pytest.approx(99.8, abs=1e-12)}


def test_surprise_scaled_divides_by_the_as_of_price():
    # 0.25 / 99.8 = 0.00250501; an unlinked eps row and an event without a price are left out.
    eps = pd.DataFrame({"event_id": ["E1", None, "E3"], "surprise": [0.25, 0.4, 0.1]})
    got = regressors.surprise_scaled(eps, {"E1": 99.8})
    assert got == {"E1": pytest.approx(0.25 / 99.8, abs=1e-15)}


def test_winsorise_within_each_group():
    # Group g: 1, 2, ..., 100. numpy's linear quantiles: q 0.01 at position 0.99 -> 1.99, q 0.99 at
    # 98.01 -> 99.01. Group h: 5 and 7 -> 5.02 and 6.98. Pooled together, g's cut points would be
    # 1.06 and 99.0 (102 values), so the per-group cut is visible.
    vals = {f"g{k}": float(k) for k in range(1, 101)}
    vals.update({"h1": 5.0, "h2": 7.0})
    grp = {k: k[0] for k in vals}
    got = regressors.winsorise(vals, grp, (0.01, 0.99))
    assert got["g1"] == pytest.approx(1.99) and got["g100"] == pytest.approx(99.01) and got["g50"] == 50.0
    assert got["h1"] == pytest.approx(5.02) and got["h2"] == pytest.approx(6.98)


def test_sue_hist_hand_worked():
    # Security A in day-0 order: values 1, 2, 3, 4, 10, 5 (given shuffled); B has its own history.
    #   5th (10): previous 1, 2, 3, 4: mean 2.5, sd sqrt((2.25 + 0.25 + 0.25 + 2.25)/3) = 1.290994
    #             -> (10 - 2.5)/1.290994 = 5.809475, n 4
    #   6th (5):  previous 1, 2, 3, 4, 10: mean 4, sd sqrt((9 + 4 + 1 + 0 + 36)/4) = 3.535534
    #             -> (5 - 4)/3.535534 = 0.282843, n 5
    #   the first four have fewer than 4 previous values; X (no value) is neither scored nor history.
    order = [("A", D(2025, 1, k), f"A{k}") for k in (6, 2, 4, 1, 5, 3)] + [("A", D(2025, 1, 7), "X")]
    order += [("B", D(2024, 1, k), f"B{k}") for k in range(1, 6)]
    vals = {"A1": 1.0, "A2": 2.0, "A3": 3.0, "A4": 4.0, "A5": 10.0, "A6": 5.0,
            "B1": 0.0, "B2": 0.0, "B3": 1.0, "B4": 1.0, "B5": 3.0}
    got = regressors.sue_hist(order, vals, 8, 4)
    assert set(got) == {"A5", "A6", "B5"}
    assert got["A5"][0] == pytest.approx(5.809475, abs=1e-6) and got["A5"][1] == 4
    assert got["A6"][0] == pytest.approx(0.282843, abs=1e-6) and got["A6"][1] == 5
    # B5 (3): previous 0, 0, 1, 1: mean 0.5, sd sqrt(1/3) = 0.577350 -> 4.330127
    assert got["B5"][0] == pytest.approx(4.330127, abs=1e-6)
    # A window of 3, at least 3: A4 (4) vs 1, 2, 3 -> (4 - 2)/1 = 2; A5 (10) vs 2, 3, 4 -> 7; A6 (5) vs 3, 4, 10:
    # mean 5.666667, sd 3.785939 -> -0.176090.
    w3 = regressors.sue_hist(order, vals, 3, 3)
    assert w3["A4"] == (pytest.approx(2.0), 3) and w3["A5"] == (pytest.approx(7.0), 3)
    assert w3["A6"][0] == pytest.approx(-0.176090, abs=1e-6)
    # An sd of 0 gives no value: C has 0, 0, 0, 0 before its fifth.
    flat = regressors.sue_hist([("C", k, f"C{k}") for k in range(5)], {f"C{k}": 0.0 for k in range(5)}, 8, 4)
    assert flat == {}


def test_vix_regime_terciles_within_each_sample():
    # daily 10, 12, 14, 16, 18, 20: cut points at positions 5/3 and 10/3 -> 13.333, 16.667:
    # 10, 12 low; 14, 16 mid; 18, 20 high. coarse 1, 2, 3, 4: cuts 2.0 and 3.0 exactly, and a value on
    # a cut goes to the lower bin: 1, 2 low; 3 mid; 4 high. `none` gets no regime.
    vix = {f"d{v}": float(v) for v in (10, 12, 14, 16, 18, 20)}
    vix.update({f"c{v}": float(v) for v in (1, 2, 3, 4)})
    vix["n1"] = 50.0
    smp = {k: {"d": "daily", "c": "coarse", "n": "none"}[k[0]] for k in vix}
    got = regressors.vix_regime(vix, smp)
    assert [got[f"d{v}"] for v in (10, 12, 14, 16, 18, 20)] == ["low", "low", "mid", "mid", "high", "high"]
    assert [got[f"c{v}"] for v in (1, 2, 3, 4)] == ["low", "low", "mid", "high"]
    assert "n1" not in got


def test_yahoo_return_adds_back_the_dividend_and_ln_mcap_scales_the_rank_date_cap():
    # ln((99 + 1.5)/100) = ln(1.005) = 0.00498754; a missing day gives None.
    px = pd.DataFrame({"date": [D(2025, 1, 2), D(2025, 1, 3), D(2025, 1, 6)], "close": [100.0, 99.0, 200.0],
                       "dividends": [0.0, 1.5, 0.0]})
    assert regressors.yahoo_return(px, D(2025, 1, 2), D(2025, 1, 3)) == pytest.approx(np.log(1.005), abs=1e-15)
    assert regressors.yahoo_return(px, D(2025, 1, 2), D(2025, 1, 7)) is None
    # cap 2e12 on the rank date, close 100 on the day against the file's last close 200:
    # ln(2e12) + ln(100/200) = 28.324168 - 0.693147 = 27.631021
    assert regressors.ln_mcap(px, 2e12, D(2025, 1, 2)) == pytest.approx(np.log(2e12) + np.log(0.5), abs=1e-12)
    assert regressors.ln_mcap(px, None, D(2025, 1, 2)) is None
    assert regressors.ln_mcap(px, 2e12, D(2025, 1, 9)) is None


def test_regressor_table_assembles_every_column():
    # Two events of one security, both daily; E2's VIX and eps are missing. Values as above.
    sessions = calendar.Sessions([D(2025, 1, 2), D(2025, 1, 3), D(2025, 1, 6), D(2025, 1, 7)])
    events = pd.DataFrame({"event_id": ["E1", "E2"], "security_id": ["A", "A"], "sample": ["daily", "daily"],
                           "announce_date_used": [D(2025, 1, 3), D(2025, 1, 7)],
                           "day0_session": [D(2025, 1, 3), D(2025, 1, 7)],
                           "day_m1_session": [D(2025, 1, 2), D(2025, 1, 6)]})
    eiv = pd.DataFrame({"event_id": ["E1", "E2"], "pre_session": [D(2025, 1, 2), D(2025, 1, 6)],
                        "post_session": [D(2025, 1, 3), D(2025, 1, 7)]})
    iv = pd.DataFrame({"security_id": ["A"], "session_date": [D(2025, 1, 2)], "front_expiry": [D(2025, 1, 17)]})
    ce = pd.DataFrame({"security_id": ["A"], "session_date": [D(2025, 1, 2)], "expiration": [D(2025, 1, 17)],
                       "forward": [100.0], "df": [0.998], "status": ["ok"]})
    md = pd.DataFrame({"session_date": [D(2025, 1, 2)], "vix_close_cboe": [15.0]})
    eps = pd.DataFrame({"event_id": ["E1"], "surprise": [0.25]})
    px = pd.DataFrame({"date": [D(2025, 1, 2), D(2025, 1, 3)], "close": [100.0, 99.0], "dividends": [0.0, 1.5]})
    dr = {"surprise_winsor": [0.01, 0.99], "sue_prev": 8, "sue_min_prev": 4}
    t = regressors.regressor_table(events, eps, eiv, iv, ce, md, sessions, {"A": px}, {"A": 1e12}, dr)
    assert list(t.columns) == ["event_id", *regressors.COLUMNS]
    e1, e2 = t.iloc[0].to_dict(), t.iloc[1].to_dict()
    assert e1["price_ref"] == pytest.approx(99.8) and e1["surprise_scaled"] == pytest.approx(0.25 / 99.8)
    assert e1["abs_surprise_scaled_w"] == pytest.approx(0.25 / 99.8) and e1["vix_regime"] == "low"
    assert e1["realized_ret_0_yf"] == pytest.approx(np.log(1.005))
    assert e1["ln_mcap_yf"] == pytest.approx(np.log(1e12) + np.log(100 / 99))
    assert pd.isna(e2["price_ref"]) and pd.isna(e2["vix_regime"]) and pd.isna(e2["realized_ret_0_yf"])


def test_regressor_table_winsorises_abs_surprise_within_each_sample():
    # Fix R3 (milestone-4 review, mutant M25): the CALL must group by events.sample. Eight made-up
    # companies, one event each on the same sessions, price_ref 100 for all; |surprise| 1, 2, 3, 4 in
    # the daily sample and 10, 20, 30, 40 in the coarse one, winsorised at [0.25, 0.75]. Within each
    # sample (numpy linear quantiles): daily [1.75, 3.25], coarse [17.5, 32.5], over 100. Over all
    # eight together the cut would be [2.75, 22.5], which moves every one of them differently.
    sessions = calendar.Sessions([D(2025, 1, 2), D(2025, 1, 3)])
    ids, secs = [f"E{i}" for i in range(8)], [f"S{i}" for i in range(8)]
    events = pd.DataFrame({"event_id": ids, "security_id": secs, "sample": ["daily"] * 4 + ["coarse"] * 4,
                           "announce_date_used": [D(2025, 1, 3)] * 8, "day0_session": [D(2025, 1, 3)] * 8,
                           "day_m1_session": [D(2025, 1, 2)] * 8})
    eiv = pd.DataFrame({"event_id": ids, "pre_session": [D(2025, 1, 2)] * 8, "post_session": [D(2025, 1, 3)] * 8})
    iv = pd.DataFrame({"security_id": secs, "session_date": [D(2025, 1, 2)] * 8, "front_expiry": [D(2025, 1, 17)] * 8})
    ce = pd.DataFrame({"security_id": secs, "session_date": [D(2025, 1, 2)] * 8, "expiration": [D(2025, 1, 17)] * 8,
                       "forward": [100.0] * 8, "df": [1.0] * 8, "status": ["ok"] * 8})
    md = pd.DataFrame({"session_date": [D(2025, 1, 2)], "vix_close_cboe": [15.0]})
    eps = pd.DataFrame({"event_id": ids, "surprise": [1.0, -2.0, 3.0, -4.0, 10.0, -20.0, 30.0, -40.0]})
    dr = {"surprise_winsor": [0.25, 0.75], "sue_prev": 8, "sue_min_prev": 4}
    t = regressors.regressor_table(events, eps, eiv, iv, ce, md, sessions, {}, {}, dr)
    got = dict(zip(t["event_id"], t["abs_surprise_scaled_w"]))
    want = [1.75, 2.0, 3.0, 3.25, 17.5, 20.0, 30.0, 32.5]
    assert [got[e] for e in ids] == pytest.approx([w / 100 for w in want])
    assert list(t["surprise_scaled"]) == pytest.approx([v / 100 for v in eps["surprise"]])     # signed, unclipped


# --- the committed table -------------------------------------------------------------------------


@pytest.fixture(scope="module")
def committed():
    em = store.read_table(DERIVED / "event_measures.parquet", store.committed_schema(schema.EVENT_MEASURES))
    ev = store.read_table(DERIVED / "events.parquet", store.committed_schema(schema.EVENTS))
    return em.merge(ev[["event_id", "sample", "security_id"]], on="event_id")


def test_committed_regressors_hold_their_rules(committed):
    p = params.load()["drivers"]
    em = committed
    assert not [c for c in em.columns if c.endswith(("_yf", "_cboe"))]          # class R stays local
    has = em["surprise_scaled"].notna()
    assert (em.loc[has, "price_ref"] > 0).all() and em.loc[~em["price_ref"].notna(), "surprise_scaled"].isna().all()
    # |SURP|_w is |surprise_scaled| clipped to its sample's quantiles: equal inside, the cut outside.
    for smp, g in em[has].groupby("sample"):
        a = g["surprise_scaled"].abs()
        lo, hi = np.quantile(a, p["surprise_winsor"][0]), np.quantile(a, p["surprise_winsor"][1])
        assert np.allclose(g["abs_surprise_scaled_w"], a.clip(lo, hi), atol=1e-15), smp
    s = em["sue_hist"].notna()
    assert (em.loc[s, "sue_hist_n"].astype(int).between(p["sue_min_prev"], p["sue_prev"])).all()
    assert em.loc[~s, "sue_hist_n"].isna().all()
    assert set(em["vix_regime"].dropna()) == {"low", "mid", "high"}
    assert em.loc[em["sample"] == "none", "vix_regime"].isna().all()
    prim = em[(em["sample"] == "daily") & em["eligible_crush"]]
    assert len(prim) == 347 and prim["abs_surprise_scaled_w"].notna().all() and prim["vix_regime"].notna().all()
