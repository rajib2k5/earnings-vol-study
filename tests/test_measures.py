# Tests for the milestone-1 parts of the measures layer and for market.py:
# the parity forward, the session-snapshot mapping, the snapshot-close
# statistics and the rate conversion. Hand-worked numbers are in the comments.
#
# Mutations this module must catch (applied by hand, each seen to fail):
#   - parity_forward using all strikes instead of the 4 with the smallest |C-P|
#   - parity_forward ignoring DF (F_K = K + C - P)
#   - build_session_snapshot keeping the holiday copy instead of the session's own snapshot
#   - stale_repeat never set (the digest comparison removed)
#   - discount_to_continuous using 365 instead of 360 for the bill price
#   - build_market_daily carrying VIX forward over a missing day

import math
from datetime import date

import numpy as np
import pandas as pd
import pytest

from earnings_vol.events import calendar, market
from earnings_vol.measures import forward, snapshot_close, snapshots

# --- the parity forward (ADR 0003 §0 step 2) --------------------------------------
# DF = 0.98. Each strike's C - P is built as DF * (F_K - K) for a chosen F_K:
#   K   F_K     C - P = 0.98 * (F_K - K)   |C - P|
#   90  102.6   0.98 * 12.6  = 12.348      12.348
#   95  100.8   0.98 * 5.8   = 5.684        5.684
#   100 101.0   0.98 * 1.0   = 0.980        0.980
#   105 101.2   0.98 * -3.8  = -3.724       3.724
#   110 101.4   0.98 * -8.6  = -8.428       8.428
#   115 101.9   0.98 * -13.1 = -12.838     12.838
# The 4 smallest |C - P| are K = 100, 105, 95, 110, so F = median(101.0, 101.2,
# 100.8, 101.4) = (101.0 + 101.2) / 2 = 101.1. Over ALL strikes the median would
# be (101.2 + 101.4) / 2 = 101.3, so the test notices an all-strike forward.
# Dispersion = (101.4 - 100.8) / 101.1 = 0.6 / 101.1 = 0.0059347.
MIDS = {  # strike: (call mid, put mid), with C - P as in the table
    90: (12.848, 0.50), 95: (6.684, 1.00), 100: (3.48, 2.50),
    105: (1.80, 5.524), 110: (0.80, 9.228), 115: (0.30, 13.138),
}


def chain(mids, spread=0.02):
    rows = []
    for k, (c, p) in mids.items():
        rows.append({"strike": float(k), "call_put": "Call", "bid": c - spread, "ask": c + spread})
        rows.append({"strike": float(k), "call_put": "Put", "bid": p - spread, "ask": p + spread})
    return pd.DataFrame(rows)


def test_parity_forward_uses_the_four_strikes_nearest_the_money():
    f, n, disp = forward.parity_forward(chain(MIDS), 0.98)
    assert f == pytest.approx(101.1, abs=1e-9) and n == 4
    assert disp == pytest.approx(0.6 / 101.1, abs=1e-9)


def test_parity_forward_quote_filter_and_fallbacks():
    q = chain(MIDS)
    # A zero bid fails the filter: strike 100's call drops out, so 90 enters the four.
    q.loc[(q["strike"] == 100) & (q["call_put"] == "Call"), "bid"] = 0.0
    f, n, _ = forward.parity_forward(q, 0.98)
    # Four now: 105 (101.2), 95 (100.8), 110 (101.4), 90 (102.6) -> median (101.2 + 101.4)/2 = 101.3.
    assert (f, n) == (pytest.approx(101.3, abs=1e-9), 4)
    two = chain({100: MIDS[100], 105: MIDS[105]})
    assert forward.parity_forward(two, 0.98)[:2] == (pytest.approx(101.1, abs=1e-9), 2)  # fewer than 4: all
    assert forward.parity_forward(chain({100: (3.48, 0.01)}), 0.98) is None                 # put mid < 0.05


def test_discount_factor():
    # e^(-0.039 * 14/365) = e^(-0.0014959) = 0.9985052
    assert forward.discount_factor(0.039, 14) == pytest.approx(0.9985052279, abs=1e-10)


def test_parity_spot_reproduces_the_adr_example():
    # ADR 0002 Context item 2: AAPL 2025-10-31, F = 270.55, 14 days of carry at 3.9%,
    # a 0.26 dividend 11 days out. S = 270.55 * 0.9985052 + 0.26 * e^(-0.039 * 11/365)
    # = 270.14559 + 0.25969 = 270.40528 (the ADR says "about 270.41").
    df = forward.discount_factor(0.039, 14)
    assert snapshot_close.parity_spot(270.55, df, [(11, 0.26)], 0.039) == pytest.approx(270.40528, abs=1e-5)


def test_ols_slope_hand_worked():
    # x = 1, 2, 3; y = 1, 3, 2. Centred: x -1, 0, 1; y -1, 1, 0.
    # slope = (1 + 0 + 0) / 2 = 0.5; residuals -0.5, 1, -0.5; SSR = 1.5;
    # se = sqrt(1.5 / (3 - 2) / 2) = sqrt(0.75) = 0.8660254; corr = 1 / sqrt(2 * 2) = 0.5.
    out = snapshot_close.ols_slope(np.array([1.0, 2, 3]), np.array([1.0, 3, 2]))
    assert out == {"slope": 0.5, "se": pytest.approx(math.sqrt(0.75)), "corr": pytest.approx(0.5), "n": 3}


def test_bootstrap_is_seeded_and_centred_on_the_point_estimate():
    a, b = np.array([3.0, 4, 5, 6, 7]), np.array([1.0, 2, 3])
    one = snapshot_close.bootstrap_median_gap(a, b, reps=500)
    assert one == snapshot_close.bootstrap_median_gap(a, b, reps=500)     # same seed, same answer
    assert one["difference"] == 5.0 - 2.0                                 # medians 5 and 2
    assert one["ci_lo"] <= 3.0 <= one["ci_hi"]


# --- snapshots -> sessions (ADR 0002 §1) --------------------------------------------

@pytest.fixture(scope="module")
def sessions():
    t = calendar.build_session_table(date(2024, 8, 1), date(2024, 9, 30),
                                     {"weekly_from": "2019-02-09", "mwf_from": "2020-01-06",
                                      "daily_from": "2024-09-11", "data_end": "2026-10-26"})
    return calendar.Sessions(t["session_date"].tolist())


def snap(day, bid):
    return pd.DataFrame({"date": [day] * 2, "act_symbol": ["AAPL"] * 2, "expiration": [date(2024, 9, 20)] * 2,
                         "strike": [220.0, 225.0], "call_put": ["Call", "Put"], "bid": [bid, 3.0],
                         "ask": [bid + 0.1, 3.1]})


def test_quote_digest_ignores_row_order_and_sees_a_changed_bid():
    a = snap(date(2024, 8, 30), 5.0)
    d1 = snapshots.quote_digests(a)
    d2 = snapshots.quote_digests(a.iloc[::-1])
    d3 = snapshots.quote_digests(snap(date(2024, 8, 30), 5.01))
    assert d1["digest"].iloc[0] == d2["digest"].iloc[0] != d3["digest"].iloc[0]
    assert d1["rows"].iloc[0] == 2


def test_session_snapshot_copy_repeat_and_missing(sessions):
    # Fri 08-30 real; Mon 09-02 (Labor Day) a copy of it; Wed 09-04 a weekday
    # repeat of 08-30 (the vendor did not refresh); Fri 09-06 fresh quotes.
    chain_rows = pd.concat([snap(date(2024, 8, 30), 5.0), snap(date(2024, 9, 2), 5.0),
                            snap(date(2024, 9, 4), 5.0), snap(date(2024, 9, 6), 4.2)])
    dig = snapshots.quote_digests(chain_rows)
    table, counts = snapshots.build_session_snapshot(dig, lambda t, d: t, ["AAPL"], sessions,
                                                     date(2024, 8, 29), date(2024, 9, 6))
    got = dict(zip(table["session_date"], zip(table["snapshot_status"], table["snapshot_date"])))
    assert got == {
        date(2024, 8, 29): ("missing", None),
        date(2024, 8, 30): ("ok", date(2024, 8, 30)),       # the holiday copy maps here and is dropped
        date(2024, 9, 3): ("missing", None),
        date(2024, 9, 4): ("stale_repeat", date(2024, 9, 4)),
        date(2024, 9, 5): ("missing", None),
        date(2024, 9, 6): ("ok", date(2024, 9, 6)),
    }
    assert counts == {"snapshots": 4, "stale_copy_dropped": 1, "stale_repeat": 1, "missing": 3, "ok": 2}


# --- market_daily (data model §3.4) --------------------------------------------------

def test_discount_rate_to_continuous_hand_worked():
    # d = 4.05%: P = 1 - 0.0405 * 91/360 = 1 - 0.0102375 = 0.9897625
    # -ln P = 0.0102903; r = 0.0102903 * 365/91 = 0.0412741
    assert market.discount_to_continuous(4.05) == pytest.approx(0.04127413, abs=1e-8)
    assert market.discount_to_continuous(0.0) == 0.0


def test_market_daily_carries_the_rate_but_never_vix():
    s = [date(2025, 4, 17), date(2025, 4, 21)]                 # 04-18 is Good Friday
    dtb3 = pd.DataFrame({"date": [date(2025, 4, 17), date(2025, 4, 18), date(2025, 4, 21)],
                         "value": [4.20, np.nan, np.nan]})
    # A made-up VIX level (not the published close of that day: VIX is CBOE data, class R).
    vix = pd.DataFrame({"date": [date(2025, 4, 17), date(2025, 4, 21)], "value": [12.5, np.nan]})
    out = market.build_market_daily(s, dtb3, vix).set_index("session_date")
    assert out.loc[date(2025, 4, 21), "r_dtb3"] == 4.20      # last value on or before
    assert out.loc[date(2025, 4, 17), "ln_vix_cboe"] == pytest.approx(math.log(12.5))
    assert np.isnan(out.loc[date(2025, 4, 21), "vix_close_cboe"])   # missing stays missing
    with pytest.raises(ValueError, match="no DTB3"):
        market.build_market_daily([date(2025, 4, 16)], dtb3, vix)
