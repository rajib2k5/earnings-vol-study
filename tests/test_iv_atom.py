# Tests for measures/black.py and measures/chain.py: Black-76, its inversion,
# and the ATM atom of ADR 0003 §0 (one expiry -> one chain_expiry row). Every
# expected number is worked in the comments. All quotes are made up.
#
# The chain tests need option prices for a KNOWN total variance w per strike.
# They come from `price76` below, a forward model written here with
# scipy.stats.norm (black.py uses scipy.special.ndtr). It is checked against
# hand-worked numbers first (test_the_test_pricer_matches_hand_numbers), and
# the assertions land on what the code under test RECOVERS from those prices,
# never on price76 itself: a bug in black.py's inversion changes the
# recovered w and fails the test.
#
# Mutations this module must catch (applied by hand, each seen to fail):
#   - black76 with d1 = (ln(F/K) + w) / sqrt(w) (the +w/2 lost)
#   - implied_w solving on a wider interval when there is no root (no None)
#   - straddle_w without the factor 2 inside N^-1
#   - tau_sessions counting the snapshot session as well (tau + 1)
#   - tau_sessions on calendar days
#   - expiry_atom using the in-the-money side (calls below F, puts above)
#   - expiry_atom using the bid instead of the mid
#   - expiry_atom taking the lower bracket strike's w instead of interpolating
#   - expiry_atom skipping the 1.5-sd bracket rule (no quadratic fallback)
#   - the quadratic fit unweighted
#   - the |ln(K/F)| <= 0.5 filter dropped
#   - the no-arbitrage upper bound dropped
#   - annualised_iv with 365 instead of 252
# Milestone-2 review (claim 3b; the review's C4, R5 and R7 survived the tests above):
#   - the quadratic fitted with no bracket (one side of the money only): an extrapolated ATM w
#   - the quadratic fitted on a window that holds one side of k = 0 only (the two-sided check removed)
#   - the quadratic's weights at the call site set to ones (unweighted)
#   - the quadratic's weights at the call site set to rel instead of 1/rel
#   - the quadratic window at 3 sd instead of quadratic_max_sd = 2
#   - the window drawn with the w of the valid strike nearest k = 0 instead of the bracket's w0

import math
from datetime import date

import numpy as np
import pytest
from scipy.stats import norm

from earnings_vol import params
from earnings_vol.events import calendar
from earnings_vol.measures import black, chain


def price76(f, k, w, df, call):
    """Black-76 for the test's made-up quotes (an independent forward model, see the header)."""
    s = math.sqrt(w)
    d1 = (math.log(f / k) + w / 2) / s
    d2 = d1 - s
    if call:
        return df * (f * norm.cdf(d1) - k * norm.cdf(d2))
    return df * (k * norm.cdf(-d2) - f * norm.cdf(-d1))


def test_the_test_pricer_matches_hand_numbers():
    # F = K = 100, w = 0.04 (sqrt w = 0.2), DF = 1: d1 = 0.1, d2 = -0.1,
    # call = 100 (N(0.1) - N(-0.1)) = 100 (2 * 0.5398278 - 1) = 7.965567.
    assert price76(100, 100, 0.04, 1.0, True) == pytest.approx(7.965567, abs=1e-6)
    # F = 100, K = 110, w = 0.04, DF = 0.99: d1 = (ln(100/110) + 0.02)/0.2 = (-0.0953102 + 0.02)/0.2 = -0.3765509,
    # d2 = -0.5765509, N(d1) = 0.3532537, N(d2) = 0.2821214,
    # call = 0.99 (100 * 0.3532537 - 110 * 0.2821214) = 0.99 * 4.2919099 = 4.249091.
    assert price76(100, 110, 0.04, 0.99, True) == pytest.approx(4.249091, abs=1e-6)


# --- black.py -------------------------------------------------------------------------

def test_black76_hand_worked():
    # The two hand-worked prices above, now through the code under test.
    assert float(black.black76(100, 100, 0.04, 1.0, True)) == pytest.approx(7.965567, abs=1e-6)
    assert float(black.black76(100, 110, 0.04, 0.99, True)) == pytest.approx(4.249091, abs=1e-6)
    # Parity, C - P = DF (F - K) = 0.99 * (100 - 110) = -9.9: put = 4.249091 + 9.9 = 14.149091.
    assert float(black.black76(100, 110, 0.04, 0.99, False)) == pytest.approx(14.149091, abs=1e-6)
    # With d1 = (ln(F/K) + w)/sqrt(w) (a lost 1/2) the call would be 4.211204: the 1e-6 above sees it.
    # Arrays work too: one call and one put.
    got = black.black76(100.0, np.array([100.0, 110.0]), 0.04, 0.99, np.array([True, False]))
    assert got == pytest.approx([0.99 * 7.965567, 14.149091], abs=1e-6)


def test_implied_w_inverts_and_refuses_a_price_with_no_root():
    mid = price76(100, 110, 0.0123, 0.99, True)
    assert black.implied_w(mid, 100, 110, 0.99, True) == pytest.approx(0.0123, abs=1e-12)
    # At K = F and w = 4 a call is worth 100 (2 N(1) - 1) = 100 * 0.6826895 = 68.26895 (DF = 1).
    assert black.implied_w(68.0, 100, 100, 1.0, True) is not None        # below: a root
    assert black.implied_w(70.0, 100, 100, 1.0, True) is None            # above (still <= DF F = 100): none
    assert not black.has_root(70.0, 100, 100, 1.0, True)
    # A price at or below Black76(1e-8) (about intrinsic) has no root either.
    assert black.implied_w(0.0, 100, 110, 0.99, True) is None


def test_straddle_w_hand_worked():
    # w = 0.0036, DF = 1, F = 100: sqrt(w)/2 = 0.03, N(0.03) = 0.5119665,
    # Pi = 2 * 100 * (2 * 0.5119665 - 1) = 4.786589; back: (4.786589/200 + 1)/2 = 0.5119665,
    # N^-1 = 0.03, sqrt(w) = 2 * 0.03 = 0.06, w = 0.0036.
    assert black.straddle_w(4.786589365645044, 100, 1.0) == pytest.approx(0.0036, abs=1e-12)
    assert black.straddle_w(200.0, 100, 1.0) is None                     # Pi >= 2 DF F: no w
    assert black.straddle_w(0.0, 100, 1.0) is None


# --- chain.py: the clock -----------------------------------------------------------------

@pytest.fixture(scope="module")
def sessions():
    t = calendar.build_session_table(date(2025, 1, 1), date(2025, 12, 31),
                                     {"weekly_from": "2019-02-09", "mwf_from": "2020-01-06",
                                      "daily_from": "2024-09-11", "data_end": "2026-10-26"})
    return calendar.Sessions(t["session_date"].tolist())


def test_tau_sessions_counted_by_hand_on_the_nyse_calendar(sessions):
    # (Thu 2025-10-30, Fri 2025-11-14]: Oct 31; Nov 3-7 (5); Nov 10-14 (5) = 11 sessions
    # (15 calendar days). The snapshot session itself does not count.
    assert chain.tau_sessions(date(2025, 10, 30), date(2025, 11, 14), sessions) == 11
    # (2025-10-30, 2025-11-28]: the 11 above, Nov 17-21 (5), Nov 24-26 (3), Thanksgiving Nov 27 closed,
    # the half day Nov 28 counts as 1: 11 + 5 + 3 + 1 = 20 (29 calendar days).
    assert chain.tau_sessions(date(2025, 10, 30), date(2025, 11, 28), sessions) == 20
    # An expiry on Good Friday 2025-04-18 (closed) settles on Thursday 04-17:
    # (Mon 04-14, Thu 04-17] = 04-15, 04-16, 04-17 = 3.
    assert chain.tau_sessions(date(2025, 4, 14), date(2025, 4, 18), sessions) == 3


def test_annualised_iv_is_on_252_sessions():
    # sqrt(252 * 0.003486 / 11) = sqrt(0.0798611) = 0.2825971.
    assert chain.annualised_iv(0.003486, 11) == pytest.approx(0.2825971, abs=1e-7)


# --- chain.py: the atom ------------------------------------------------------------------

F, DF, TAU = 100.0, 0.99, 11
SPREAD = 0.02


def quotes(w_by_strike: dict, f=F, df=DF, itm_premium: dict | None = None, vols: dict | None = None,
           half_spread=SPREAD) -> chain.ExpiryQuotes:
    """Made-up quotes: the out-of-the-money leg priced at the strike's w, the other leg by
    parity (plus an optional premium, like early exercise), each mid +- half_spread."""
    ks = sorted(w_by_strike)
    cb, ca, pb, pa, cv, pv = ([] for _ in range(6))
    for k in ks:
        w = w_by_strike[k]
        if k >= f:
            c = price76(f, k, w, df, True)
            p = c - df * (f - k) + (itm_premium or {}).get(k, 0.0)
        else:
            p = price76(f, k, w, df, False)
            c = p + df * (f - k) + (itm_premium or {}).get(k, 0.0)
        cb.append(c - half_spread); ca.append(c + half_spread); pb.append(p - half_spread); pa.append(p + half_spread)
        v = (vols or {}).get(k, (math.nan, math.nan))
        cv.append(v[0]); pv.append(v[1])
    a = lambda x: np.array(x, float)
    return chain.ExpiryQuotes(a(ks), a(cb), a(ca), a(pb), a(pa), a(cv), a(pv))


# A smile: w per strike. The bracket around F = 100 is 98 (put side) and 103 (call side).
SMILE = {90.0: 0.0060, 95.0: 0.0050, 98.0: 0.0046, 103.0: 0.0042, 110.0: 0.0040}


def test_atom_hand_worked_bracket():
    # The 103 put (in the money) carries a made-up early-exercise premium of 0.10, so its own w is
    # higher than the 103 call's. The forward: |C - P| = DF |F - K| (+ 0.10 at 103), the 4 smallest are
    # 98 (1.98), 103 (3.07), 95 (4.95) and 90 (9.90, tied with 110 and taken as the lower strike).
    # F_K = F at 98, 95, 90; at 103, F - 0.10/0.99 = 99.89899. Median of 4 = mean of the middle two = 100.
    # ATM: k_lo = ln(0.98) = -0.0202027, k_hi = ln(1.03) = 0.0295588, width 0.0497615,
    # frac = 0.0202027 / 0.0497615 = 0.4059906,
    # w_atm = 0.0046 + 0.4059906 * (0.0042 - 0.0046) = 0.0046 - 0.0001624 = 0.0044376037.
    # Bracket rule: 0.0497615 <= 1.5 sqrt(0.0044376) = 0.0999230, so bracket_linear.
    # iv_atm = sqrt(252 * 0.0044376037 / 11) = sqrt(0.1016615) = 0.3188440.
    # The vendor's vols (call, put): OTM legs 0.30 (98 put) and 0.26 (103 call); the ITM legs differ.
    # vendor_iv_atm = 0.30 + 0.4059906 * (0.26 - 0.30) = 0.2837604.
    q = quotes(SMILE, itm_premium={103.0: 0.10}, vols={98.0: (0.31, 0.30), 103.0: (0.26, 0.25)})
    out = chain.expiry_atom(q, DF, TAU)
    assert out["status"] == "ok" and out["atm_method"] == "bracket_linear"
    assert out["forward"] == pytest.approx(100.0, abs=1e-9) and out["forward_n_strikes"] == 4
    assert (out["strike_lo"], out["strike_hi"]) == (98.0, 103.0)
    assert out["k_lo"] == pytest.approx(-0.0202027, abs=1e-7) and out["k_hi"] == pytest.approx(0.0295588, abs=1e-7)
    assert out["w_atm"] == pytest.approx(0.0044376037, abs=1e-9)
    assert out["iv_atm"] == pytest.approx(0.3188440, abs=1e-6)
    assert out["vendor_iv_atm"] == pytest.approx(0.2837604, abs=1e-7)
    assert out["n_strikes_valid"] == 5
    # Relative spread of the OTM quotes at the bracket: 0.04 / mid.
    assert out["rel_spread_lo"] == pytest.approx(0.04 / price76(F, 98.0, 0.0046, DF, False), rel=1e-9)
    # Dispersion of the four F_K: (100 - 99.89899) / 100 = 0.00101, under the 0.5% flag.
    assert out["forward_dispersion"] == pytest.approx(0.10 / 0.99 / 100, abs=1e-9)
    assert "fwd_dispersion" not in out["flags"]


def test_atom_straddle_at_the_bracket():
    # C + P at 98 and 103 (mids), interpolated in k with frac = 0.4059906. Without a premium, by parity
    # C + P = 2 * OTM + DF |F - K|: at 98, 2 P98 + 1.98; at 103, 2 C103 + 2.97.
    q = quotes(SMILE)
    out = chain.expiry_atom(q, DF, TAU)
    s98 = 2 * price76(F, 98.0, 0.0046, DF, False) + 0.99 * 2
    s103 = 2 * price76(F, 103.0, 0.0042, DF, True) + 0.99 * 3
    assert out["straddle_atm"] == pytest.approx(s98 + 0.4059906441 * (s103 - s98), abs=1e-8)
    # Interpolating C + P linearly across the kink at K = F overstates the ATM straddle, so the straddle IV
    # sits above iv_atm (here by more than the 0.5-point flag).
    assert out["iv_straddle"] > out["iv_atm"]
    assert ("straddle_gap" in out["flags"]) == (abs(out["iv_straddle"] - out["iv_atm"]) > 0.005)


def test_atom_uses_the_mid_not_the_bid():
    # A wider spread around the same mids leaves w_atm unchanged; a bid-based solve would move it.
    wide = chain.expiry_atom(quotes(SMILE, half_spread=0.20), DF, TAU)
    assert wide["w_atm"] == pytest.approx(0.0044376037, abs=1e-9)


def test_atom_quadratic_when_the_bracket_is_too_wide():
    # Strikes 70, 85, 120, 140, 160 around F = 100 with w(k) = 0.04 + 0.01 k + 0.05 k^2 (a smile).
    # k: 70 -> -0.3566749, 85 -> -0.1625189, 120 -> 0.1823216, 140 -> 0.3364722, 160 -> 0.4700036;
    # w85 = 0.0396954, w120 = 0.0434853.
    # The bracket 85 / 120 is 0.3448405 wide. Its linear w0 = 0.0396954 + (0.1625189/0.3448405) *
    # (0.0434853 - 0.0396954) = 0.0396954 + 0.4712873 * 0.0037898 = 0.0414815, and the limit is
    # 1.5 sqrt(0.0414815) = 0.3055052 < 0.3448405: too wide (flag wide_bracket). The quadratic uses the
    # strikes with |k| <= 2 sqrt(w0) = 0.4073403: 70, 85, 120, 140 (160 is out), four, enough. Through 4
    # points of an exact quadratic the fit returns a = 0.04 whatever the weights; the linear bracket
    # would have given 0.0414815.
    def wq(k):
        x = math.log(k / 100.0)
        return 0.04 + 0.01 * x + 0.05 * x * x
    q = quotes({k: wq(k) for k in (70.0, 85.0, 120.0, 140.0, 160.0)})
    out = chain.expiry_atom(q, DF, TAU)
    assert out["atm_method"] == "quadratic" and out["status"] == "ok"
    assert out["w_atm"] == pytest.approx(0.04, abs=1e-9)
    assert "wide_bracket" in out["flags"]
    assert out["vendor_iv_atm"] is None and out["straddle_atm"] is None


def quotes_rel(w_rel: dict, f=F, df=DF) -> chain.ExpiryQuotes:
    """Made-up quotes like quotes(), but each strike's OUT-of-the-money quote has the given relative spread
    (ask - bid)/mid ({strike: (w, rel)}); the in-the-money leg keeps the half-spread SPREAD."""
    ks = sorted(w_rel)
    cb, ca, pb, pa = ([] for _ in range(4))
    for k in ks:
        w, rel = w_rel[k]
        otm = price76(f, k, w, df, k >= f)
        itm = otm - df * (f - k) if k >= f else otm + df * (f - k)
        c, p = (otm, itm) if k >= f else (itm, otm)
        hc, hp = (rel * c / 2, SPREAD) if k >= f else (SPREAD, rel * p / 2)
        cb.append(c - hc); ca.append(c + hc); pb.append(p - hp); pa.append(p + hp)
    a = lambda x: np.array(x, float)
    nan = np.full(len(ks), np.nan)
    return chain.ExpiryQuotes(a(ks), a(cb), a(ca), a(pb), a(pa), nan, nan)


# F = 100, DF = 0.99. Strike: (w of the OTM quote, its relative spread). k = ln(K/100):
#   86 -0.1508229   90 -0.1053605   95 -0.0512933 | 106 0.0582689   112 0.1133287   115 0.1397619
WIDE = {86.0: (0.0060, 0.10), 90.0: (0.0050, 0.10), 95.0: (0.0055, 0.05), 106.0: (0.0030, 0.05),
        112.0: (0.0045, 0.40), 115.0: (0.0080, 0.10)}


def test_atom_quadratic_window_weights_and_reference_w():
    # The forward: |C - P| = 0.99 |100 - K|, smallest at 95, 106, 90, 112, each F_K = 100, so F = 100.
    # Bracket 95 / 106: width 0.1095622; frac = 0.0512933 / 0.1095622 = 0.4681660;
    # w0 = 0.0055 + 0.4681660 * (0.0030 - 0.0055) = 0.0043296. 1.5 sqrt(w0) = 0.0986994 < 0.1095622: too wide.
    # The window, drawn with w_ref = w0: |k| <= 2 sqrt(0.0043296) = 0.1315992 holds 90, 95, 106, 112 (two on each
    # side); 115 (0.1397619) and 86 (0.1508229) are out. Weights 1/rel = 10, 20, 20, 2.5.
    # a, computed with numpy.polyfit(k, w, 2, w=sqrt(weights)) outside the code under test: 0.0043709131.
    # What each mutant would give instead (same tool):
    #   unweighted 0.0040954861; weights = rel 0.0040542828;
    #   window at 3 sd (|k| <= 0.1973987: 86 and 115 join) 0.0038445175;
    #   window from the nearest strike's w, w95 = 0.0055 (|k| <= 0.1483240: 115 joins) 0.0034327478;
    #   the linear bracket itself 0.0043296.
    out = chain.expiry_atom(quotes_rel(WIDE), DF, TAU)
    assert out["forward"] == pytest.approx(100.0, abs=1e-9)
    assert out["atm_method"] == "quadratic" and out["status"] == "ok" and "wide_bracket" in out["flags"]
    assert (out["strike_lo"], out["strike_hi"]) == (95.0, 106.0)
    assert out["rel_spread_lo"] == pytest.approx(0.05, abs=1e-12) and out["rel_spread_hi"] == pytest.approx(0.05, abs=1e-12)
    assert out["w_atm"] == pytest.approx(0.0043709131, abs=1e-9)
    assert out["iv_atm"] == pytest.approx(math.sqrt(252 * 0.0043709131 / TAU), abs=1e-7)


def test_atom_never_extrapolates_from_one_side_of_the_money():
    # No bracket: every call is filtered (bid 0.01 -> relative spread > 0.5), so only the puts 88, 90, 95, 98 are
    # valid, all with k < 0. The forward still exists (those four strikes pair up, F = 100). Before the review this
    # fitted a quadratic on the four puts and extrapolated it to k = 0; now there is no ATM.
    q = quotes({88.0: 0.0052, 90.0: 0.0050, 95.0: 0.0048, 98.0: 0.0046, 103.0: 0.0042, 110.0: 0.0040})
    cb = np.where(q.strike >= 100, 0.01, q.call_bid)
    out = chain.expiry_atom(chain.ExpiryQuotes(q.strike, cb, q.call_ask, q.put_bid, q.put_ask, q.call_vol,
                                               q.put_vol), DF, TAU)
    assert out["forward"] == pytest.approx(100.0, abs=1e-9) and out["n_strikes_valid"] == 4
    assert (out["status"], out["atm_method"], out["w_atm"]) == ("no_atm", "none", None)
    assert out["flags"] == "no_bracket" and out["strike_lo"] is None
    # A bracket that is too wide, whose window holds one side only: the same puts, the calls at 103 and 110
    # filtered, and a valid call at 130 (k = 0.2623643, w 0.03). Bracket 98 / 130: frac = 0.0202027 / 0.2825670
    # = 0.0714970, w0 = 0.0046 + 0.0714970 * (0.03 - 0.0046) = 0.0064160; 1.5 sqrt(w0) = 0.1201498 < 0.2825670,
    # too wide. The window |k| <= 2 sqrt(w0) = 0.1601997 holds 88 (-0.1278334), 90, 95, 98 and not 130: four
    # strikes, all below k = 0, so no quadratic.
    q = quotes({88.0: 0.0052, 90.0: 0.0050, 95.0: 0.0048, 98.0: 0.0046, 103.0: 0.0042, 110.0: 0.0040, 130.0: 0.03})
    cb = np.where((q.strike >= 100) & (q.strike < 130), 0.01, q.call_bid)
    out = chain.expiry_atom(chain.ExpiryQuotes(q.strike, cb, q.call_ask, q.put_bid, q.put_ask, q.call_vol,
                                               q.put_vol), DF, TAU)
    assert out["n_strikes_valid"] == 5 and (out["strike_lo"], out["strike_hi"]) == (98.0, 130.0)
    assert (out["status"], out["atm_method"], out["w_atm"]) == ("no_atm", "none", None)
    assert out["flags"] == "wide_bracket"


def test_quadratic_fit_is_weighted_by_inverse_spread():
    # Five points, one off the curve: k = -0.2, -0.1, 0.1, 0.2, 0.3 with
    # w = 0.04 + 0.05 k^2 except w(0.3) = 0.050 (the curve says 0.0445).
    # Weights 1/spread = 1, 1, 1, 1, 100 pull the fit through the last point.
    # Computed with numpy.polyfit(k, w, 2, w=sqrt(weights)) outside the code under test (polyfit
    # weights the unsquared residuals): weighted a = 0.0385386221, unweighted a = 0.03875.
    k = np.array([-0.2, -0.1, 0.1, 0.2, 0.3])
    w = 0.04 + 0.05 * k * k
    w[-1] = 0.050
    weight = np.array([1.0, 1.0, 1.0, 1.0, 100.0])
    assert chain._wls_quadratic_intercept(k, w, weight) == pytest.approx(0.0385386221, abs=1e-10)
    assert chain._wls_quadratic_intercept(k, w, np.ones(5)) == pytest.approx(0.03875, abs=1e-10)


def test_atom_filters_moneyness_bounds_and_roots():
    base = dict(SMILE)
    # |ln(K/F)| > 0.5: a 170 strike (ln 1.7 = 0.5306) is dropped even though its quote passes the filter
    # (w = 0.25 prices the call at 0.99 (100 N(-0.8113) - 170 N(-1.3113)) = 4.68, mid well above 0.05).
    assert price76(F, 170.0, 0.25, DF, True) == pytest.approx(4.68, abs=0.01)
    out = chain.expiry_atom(quotes({**base, 170.0: 0.25}), DF, TAU)
    assert out["n_strikes_valid"] == 5
    # A call above the no-arbitrage bound DF F = 99 (mid 99.5) is dropped; one between Black76(w = 4)
    # and DF F has no root: dropped and flagged iv_no_root.
    q = quotes(base)
    k = list(q.strike).index(110.0)
    cb, ca = q.call_bid.copy(), q.call_ask.copy()
    cb[k], ca[k] = 99.4, 99.6                     # mid 99.5 > DF F = 99: outside the bound
    out = chain.expiry_atom(chain.ExpiryQuotes(q.strike, cb, ca, q.put_bid, q.put_ask, q.call_vol, q.put_vol), DF, TAU)
    assert out["n_strikes_valid"] == 4 and "iv_no_root" not in out["flags"]
    # Black76(F=100, K=110, w=4, DF=0.99): d1 = (ln(100/110) + 2)/2 = 0.9523449, d2 = -1.0476551,
    # 0.99 (100 N(0.9523449) - 110 N(-1.0476551)) = 66.0726. A mid of 80 is inside the bound (<= 99)
    # but above it: no root.
    cb[k], ca[k] = 79.9, 80.1
    out = chain.expiry_atom(chain.ExpiryQuotes(q.strike, cb, ca, q.put_bid, q.put_ask, q.call_vol, q.put_vol), DF, TAU)
    assert out["n_strikes_valid"] == 4 and "iv_no_root" in out["flags"]
    assert out["w_atm"] == pytest.approx(0.0044376037, abs=1e-9)    # 110 was not in the bracket anyway


def test_atom_statuses():
    # No strike with both legs passing the quote filter: no forward.
    q = quotes(SMILE)
    nan = np.full(len(q.strike), np.nan)
    out = chain.expiry_atom(chain.ExpiryQuotes(q.strike, q.call_bid, q.call_ask, nan, nan, nan, nan), DF, TAU)
    assert out["status"] == "no_forward" and out["forward"] is None and out["atm_method"] == "none"
    # Only puts out of the money valid (every call leg filtered: spread too wide): no bracket, and the
    # 3 put strikes are fewer than the 4 the quadratic needs.
    wide_c = quotes({90.0: 0.006, 95.0: 0.005, 98.0: 0.0046, 103.0: 0.0042})
    cb = np.where(wide_c.strike >= 100, 0.01, wide_c.call_bid)
    out = chain.expiry_atom(chain.ExpiryQuotes(wide_c.strike, cb, wide_c.call_ask, wide_c.put_bid, wide_c.put_ask,
                                               nan[:4], nan[:4]), DF, TAU)
    assert out["status"] == "no_atm" and out["w_atm"] is None and "no_bracket" in out["flags"]
    assert out["forward"] is not None                      # the forward exists (98, 95, 90 pair up)
    assert chain.stale_atom()["status"] == "stale"


def test_atom_params_come_from_params_yaml():
    p = chain.AtomParams.from_params(params.load()["iv"])
    assert p == chain.AtomParams()                        # the defaults are the ADR's values
    assert (p.min_mid, p.max_rel_spread, p.forward_strikes, p.bracket_max_sd) == (0.05, 0.5, 4, 1.5)
