# The hand-worked oracle of ADR 0003 §c, through the pipeline's own code path:
# tables.chain_rows (tau, DF, the atom) -> tables.iv_daily_row (E, cm30) ->
# event_iv.event_row (the crushes, the realised move).
#
# THE INPUTS are those of research/prototypes/worked.py, read from that file
# with `ast` (its literal assignments only; the script is not run): the AAPL
# quotes of 2025-10-30 and 2025-10-31 (DoltHub post-no-preference/options,
# CC BY-SA 4.0, attribution in that file), r = 3.9% continuous, and its
# session and calendar-day counts, which this test also recounts on the NYSE
# calendar. No quote is copied into this file.
#
# THE ORACLE (ADR 0003 §c, worked.out.txt):
#   10-30 / 11-14: F = 271.42 (4 strikes: 267.5, 272.5, 275, 277.5), bracket 267.5 / 272.5,
#                  w = 0.003486, tau 11 / 15 days, IV 0.2826
#   10-30 / 11-28: F = 272.06, bracket 270 / 275, w = 0.005616, tau 20 / 29, IV 0.2660
#   10-31 / 11-14: F = 270.55, bracket 270 / 272.5, w = 0.002217, tau 10 / 14, IV 0.2364
#   10-31 / 11-28: F = 270.95, bracket 270 / 275, w = 0.004179, tau 19 / 28, IV 0.2354
#   E = 0.00088284, sqrt(E) = 2.9713%, sigma_d,ann = 0.2442, implied_abs_move 2.3707%,
#   implied_abs_move_total 2.6697%; front crush ln(0.2364/0.2826) = -0.1787;
#   realised ln(270.55/271.42) + 0.039/365 = -0.3112%; dsigma term -0.0410.
#
# Mutations this module must catch (applied by hand, each seen to fail):
#   - the forward over all strikes (F = 271.69 on 10-30/11-14, E = 0.00069327)
#   - tau counted on calendar days (E = 0.00120404)
#   - the identity check's own falsifier: time in sessions in the textbook form (x 252)
#   - realised move without the carry term
#   - event_row reading E at post (day 0) instead of pre

import ast
import math
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from earnings_vol.events import calendar
from earnings_vol.measures import chain, event_iv, tables, termstructure

ROOT = Path(__file__).resolve().parents[1]
WORKED = ROOT / "research" / "prototypes" / "worked.py"
M1, D0 = date(2025, 10, 30), date(2025, 10, 31)
EXP1, EXP2 = date(2025, 11, 14), date(2025, 11, 28)


def worked_literals() -> dict:
    """The literal assignments chain, chain0, cal_days, td and r of worked.py (parsed, not run)."""
    out = {}
    for node in ast.parse(WORKED.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in ("chain", "chain0", "cal_days", "td", "r"):
                out[name] = ast.literal_eval(node.value)
    assert set(out) == {"chain", "chain0", "cal_days", "td", "r"}
    return out


def expiry_quotes(by_strike: dict) -> chain.ExpiryQuotes:
    ks = sorted(by_strike)
    col = lambda j: np.array([by_strike[k][j] for k in ks], float)
    nan = np.full(len(ks), np.nan)                       # worked.py has no vendor vols
    return chain.ExpiryQuotes(np.array(ks, float), col(0), col(1), col(2), col(3), nan, nan)


@pytest.fixture(scope="module")
def run():
    lit = worked_literals()
    t = calendar.build_session_table(date(2025, 1, 1), date(2026, 12, 31),
                                     {"weekly_from": "2019-02-09", "mwf_from": "2020-01-06",
                                      "daily_from": "2024-09-11", "data_end": "2026-10-26"})
    sessions = calendar.Sessions(t["session_date"].tolist())
    # AMC on Thu 10-30 and on Thu 2026-01-29: spans_from is the announcement day (tables.py header).
    anchors = [tables.Anchor(D0, "AAPL:2025-10-30", M1),
               tables.Anchor(date(2026, 1, 30), "AAPL:2026-01-29", date(2026, 1, 29))]
    ap, tp = chain.AtomParams(), termstructure.TermParams()
    chains, daily = {}, {}
    for day, ch in ((M1, lit["chain"]), (D0, lit["chain0"])):
        q = {date.fromisoformat(e): expiry_quotes(v) for e, v in ch.items()}
        nxt, _ = tables.neighbours(anchors, day)
        chains[("AAPL", day)] = tables.chain_rows("AAPL", day, day, False, q, lit["r"], sessions, nxt, ap)
        daily[("AAPL", day)] = tables.iv_daily_row("AAPL", day, day, "ok", chains[("AAPL", day)], anchors, sessions,
                                                   tp)
    inp = event_iv.EventInputs(daily, chains, {M1: lit["r"], D0: lit["r"]}, sessions, tp, {"AAPL": anchors})
    ev = SimpleNamespace(event_id="AAPL:2025-10-30", security_id="AAPL", announce_date_used=M1, day0_session=D0,
                         day_m1_session=M1, exclusion_reason=None)
    row, flags = event_iv.event_row(ev, inp)
    return SimpleNamespace(lit=lit, chains=chains, daily=daily, row=row, flags=flags)


def row_of(run, day, exp):
    return next(r for r in run.chains[("AAPL", day)] if r["expiration"] == exp)


def test_the_clock_matches_worked_py_and_the_nyse_calendar(run):
    # Recounted by hand in tests/test_iv_atom.py: (10-30, 11-14] = 11 and (10-30, 11-28] = 20 sessions;
    # from 10-31 one fewer each. Calendar days: 15, 29, 14, 28.
    for day, exp, tau, cal in ((M1, EXP1, 11, 15), (M1, EXP2, 20, 29), (D0, EXP1, 10, 14), (D0, EXP2, 19, 28)):
        r = row_of(run, day, exp)
        key = (day.isoformat(), exp.isoformat())
        assert (r["tau_sessions"], r["tau_cal_days"]) == (tau, cal) == (run.lit["td"][key], run.lit["cal_days"][key])
        # DF = exp(-0.039 * cal / 365): 15 days -> exp(-0.0016027) = 0.9983986.
    assert row_of(run, M1, EXP1)["df"] == pytest.approx(math.exp(-0.039 * 15 / 365), abs=1e-15)


@pytest.mark.parametrize("day, exp, f, lo, hi, w, iv", [
    (M1, EXP1, 271.42, 267.5, 272.5, 0.003486, 0.2826),
    (M1, EXP2, 272.06, 270.0, 275.0, 0.005616, 0.2660),
    (D0, EXP1, 270.55, 270.0, 272.5, 0.002217, 0.2364),
    (D0, EXP2, 270.95, 270.0, 275.0, 0.004179, 0.2354),
])
def test_each_expiry_reproduces_the_adr_table(run, day, exp, f, lo, hi, w, iv):
    r = row_of(run, day, exp)
    assert r["status"] == "ok" and r["atm_method"] == "bracket_linear"
    assert round(r["forward"], 2) == f            # the 4-strike forward; all strikes would give 271.69 on row 1
    assert (r["strike_lo"], r["strike_hi"]) == (lo, hi)
    assert round(r["w_atm"], 6) == w
    assert round(r["iv_atm"], 4) == iv


def test_event_variance_is_the_oracle(run):
    d = run.daily[("AAPL", M1)]
    # E = (w1 * 20 - w2 * 11) / 9 = 0.00088284; sigma_d^2 = (w2 - w1)/9 = 2.3667e-4, sigma_d,ann = 0.2442.
    assert d["event_var"] == pytest.approx(0.00088284, abs=5e-9)
    assert (d["ev_exp1"], d["ev_exp2"], d["ev_tau1"], d["ev_tau2"]) == (EXP1, EXP2, 11, 20)
    assert round(d["implied_move"], 6) == 0.029713
    assert round(d["sigma_d_iv"], 4) == 0.2442
    assert round(d["implied_abs_move"], 6) == 0.023707
    assert round(d["implied_abs_move_total"], 6) == 0.026697


def test_identity_check_and_its_planted_bug(run):
    # ADR 0003 §c, "The unit test, and why it can fail": the w-form fed the stored w, against the textbook
    # form E = T1 T2 (s1^2 - s2^2)/(T2 - T1) fed the REPORTED IVs (iv_atm) with T in years (tau/252).
    w1, w2 = row_of(run, M1, EXP1)["w_atm"], row_of(run, M1, EXP2)["w_atm"]
    s1, s2 = row_of(run, M1, EXP1)["iv_atm"], row_of(run, M1, EXP2)["iv_atm"]
    e_w, _ = termstructure.event_variance(w1, 11, w2, 20)

    def textbook(s1, s2, t1, t2):
        return t1 * t2 * (s1 ** 2 - s2 ** 2) / (t2 - t1)

    assert e_w == pytest.approx(textbook(s1, s2, 11 / 252, 20 / 252), rel=1e-12)
    # The planted bug, time in sessions: off by exactly 252 (0.2225 against 0.000883).
    wrong = textbook(s1, s2, 11, 20)
    assert wrong / e_w == pytest.approx(252.0, rel=1e-12)
    # The calendar clock (15 and 29 days) would give 0.00120404: the clock alone moves E by +36%.
    assert termstructure.event_variance(w1, 15, w2, 29)[0] == pytest.approx(0.00120404, abs=5e-9)


def test_the_event_row_reproduces_the_crushes_and_the_realised_move(run):
    r = run.row
    assert (r["pre_session"], r["post_session"], r["crush_span_sessions"]) == (M1, D0, 1) and run.flags == set()
    assert r["evar_m1"] == pytest.approx(0.00088284, abs=5e-9) and r["implied_move_status"] == "ok"
    # Front fixed T1* = 11-14 (10 sessions after day 0, >= 5): IV 0.2826 -> 0.2364, ln ratio -0.1787.
    assert r["front_fixed_expiry"] == EXP1 and not r["front_fixed_interpolated"]
    assert round(r["crush_front_fixed"], 4) == -0.1787
    # Realised: ln(270.55/271.42) + 0.039 * 1/365 = -0.0032118 + 0.0001068 = -0.3112%.
    assert round(r["realized_ret_0"], 6) == -0.003112
    # Same two expiries both days: 1/2 ln(((0.004179 - 0.002217)/9) / ((0.005616 - 0.003486)/9)) = -0.0410.
    assert round(r["dsigma_d_mean_adj"], 4) == -0.0410
    # cm30: day -1 spanning 11 and 20 only, extrapolated 1 session: 0.005616 + (1/9)(0.005616 - 0.003486)
    # = 0.005853, sqrt(252 * 0.005853/21) = 0.26502; day 0 clean 10 and 19, 2 sessions beyond:
    # 0.004179 + (2/9)(0.004179 - 0.002217) = 0.004616, sqrt(252 * 0.004616/21) = 0.23534;
    # crush ln(0.23534/0.26502) = -0.1188.
    assert run.daily[("AAPL", M1)]["cm30_method"] == "extrap_spanning"
    assert run.daily[("AAPL", D0)]["cm30_method"] == "extrap_clean"
    assert (round(r["cm30_m1"], 5), round(r["cm30_0"], 5), round(r["crush_mean_adj"], 4)) == (0.26502, 0.23534, -0.1188)
    # |r0| / implied_abs_move_total = 0.003112 / 0.026697 = 0.1166.
    assert round(r["abs_ret_over_implied"], 4) == 0.1166
