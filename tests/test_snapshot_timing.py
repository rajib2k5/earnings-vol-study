"""The snapshot-timing classes (earnings_vol.stats.snapshot_timing; plan: docs/validation/snapshot-timing/
preregistration.md §3).

The expected values come from the rule in the plan, worked by hand, not from the code: a snapshot at the close has
gap ~ 0; one during the day has gap = -(the rest of the day's move); one carrying the previous close has gap = -r.

Hand mutants, each seen to fail a test here before it was restored (2026-11-18):
  T1  classify: ``and`` -> ``or`` between the gap and the ratio conditions (a volatile close day becomes off)
  T2  classify: late when slope >= LATE_SLOPE dropped (a late day reads as off)
  T3  classify: unknown when n < MIN_FIRMS dropped
  T4  day_stats: slope of gap on -r replaced by the slope on +r (sign flip)
  T5  day_stats: ratio = ret_bp / gap_bp (inverted)
The check's estimators (plan §5-§10): docs/validation/snapshot-timing/mutants_check.py applies T1-T5 and C1-C19 one
at a time and needs each to fail a test here; its output is in the plan's ledger.
  C1  block P admits an off day +1          C11 block_event reads the company's level for an event-keyed series
  C2  block O: h's sign of the t+1 change   C12 dm's sign in blocks P, A and C
  C3  crush shift: sign of the b(-1) term   C13 the restricted bootstrap scales the unrestricted residuals
  C4  runup shift: baseline term dropped    C14 p_up counts the wrong tail
  C5  TOST: p = alpha counts as shown       C15 the two lines swapped
  C6  the identity gate ignored             C16 the descriptive interval's sign
  C7  the restricted fit's sign             C17 the sign of M_g delta in the bootstrap cluster sums
  C8  identity: beta_C - beta_P, not +      C18 a weekday dropped whether or not it is the dependent one
  C9  block O admits an off t-1             C19 LARGE needs both sides instead of either
  C10 persist shift: sign flipped
"""

import numpy as np
import pytest

from earnings_vol.stats import snapshot_timing as stm


def day(neg_r, gap):
    return stm.day_stats(np.asarray(gap, float), np.asarray(neg_r, float))


def test_worked_example_in_the_header():
    s = day([-0.01, 0.02, -0.03], [-0.005, 0.01, -0.015])  # gap = 0.5 * (-r)
    assert s["n"] == 3
    assert s["gap_bp"] == pytest.approx(100.0)
    assert s["ret_bp"] == pytest.approx(200.0)
    assert s["ratio"] == pytest.approx(0.5)
    assert s["slope"] == pytest.approx(0.5)


def _firms(n, seed):
    rng = np.random.default_rng(seed)
    return rng.normal(0, 0.015, n)  # -r across companies, 1.5% a day


def test_a_close_day_is_close_even_when_the_market_moves_a_lot():
    neg_r = _firms(40, 1) * 4  # a 6%-a-day market
    gap = np.random.default_rng(2).normal(0, 0.004, 40)  # quote noise only: 40 bp, no lean on r
    s = day(neg_r, gap)
    assert s["gap_bp"] > stm.GAP_BP  # large in bp ...
    assert s["ratio"] < stm.RATIO  # ... but small against the day's moves
    assert stm.classify(s) == "close"


def test_an_intraday_day_is_off():
    neg_r = _firms(40, 3)
    gap = 0.4 * neg_r  # 40% of the day's move still to come at the snapshot
    s = day(neg_r, gap)
    assert s["slope"] == pytest.approx(0.4)
    assert stm.classify(s) == "off"


def test_a_previous_close_day_is_late():
    neg_r = _firms(40, 4)
    s = day(neg_r, neg_r.copy())  # gap = -r: the snapshot carries yesterday's close
    assert s["slope"] == pytest.approx(1.0)
    assert stm.classify(s) == "late"


def test_too_few_companies_is_unknown():
    neg_r = _firms(stm.MIN_FIRMS - 1, 5)
    assert stm.classify(day(neg_r, neg_r.copy())) == "unknown"
    neg_r = _firms(stm.MIN_FIRMS, 5)
    assert stm.classify(day(neg_r, neg_r.copy())) == "late"


def test_the_thresholds_are_strict():
    base = {"n": 50, "slope": 0.3}
    assert stm.classify({**base, "gap_bp": stm.GAP_BP, "ratio": 0.9}) == "close"
    assert stm.classify({**base, "gap_bp": 60.0, "ratio": stm.RATIO}) == "close"
    assert stm.classify({**base, "gap_bp": 60.0, "ratio": 0.3}) == "off"
    assert stm.classify({**base, "gap_bp": 60.0, "ratio": 0.3, "slope": stm.LATE_SLOPE}) == "late"


def test_missing_values_are_dropped_before_counting():
    s = day([0.01, np.nan, -0.02, 0.03], [0.0, 0.01, np.nan, 0.0])
    assert s["n"] == 2


# --- the check (plan §5-§10) on a synthetic world -------------------------------------------------------
# The true ln level is flat except a run-up of +0.05 at day -1 and a step of -0.2 from day 0 on, the same around
# every event. Snapshot levels add the planted errors: b0 on an off day 0, bm1 on an off day -1, bord on any other
# off session, and +5 on a late session (which must never enter a block). Expected values come from these
# constants and the definitions in the plan, not from the code.

from datetime import date, timedelta

import pandas as pd

B0, BM1, BORD, LATE_ERR = 0.04, -0.03, 0.01, 5.0


def _world(seed=7, n_firms=25, noise=0.0, repaid=True):
    rng = np.random.default_rng(seed)
    sessions, d = [], date(2025, 1, 2)
    while len(sessions) < 200:
        if d.weekday() < 5:
            sessions.append(d)
        d += timedelta(days=1)
    off = {s for s in sessions if rng.random() < 0.3}
    events, firms = [], [f"F{i:02d}" for i in range(n_firms)]
    for i, f in enumerate(firms):
        for m in range(4):
            p0 = 40 + (i % 10) + 45 * m + (i * m) % 4  # not 9 weeks apart, so the weekday varies within firm
            if p0 + 12 < len(sessions):
                events.append({"event_id": f"{f}:{m}", "firm": f, "season": f"S{m}", "p0": p0})
    ev = pd.DataFrame(events)
    event_pos = {(r.firm, r.p0 + k) for r in ev.itertuples() for k in range(-2, 3)}
    # late sessions only where no event or baseline can see them: positions 0-9 of the calendar
    late = {sessions[i] for i in (3, 6)}
    off -= late
    cls = lambda s: "late" if s in late else ("off" if s in off else "close")  # noqa: E731
    # ln VIX: a random walk that every company loads on with 0.5 (the dm column must take it out exactly)
    mkt = dict(zip(sessions, np.cumsum(rng.normal(0, 0.05, len(sessions)))))
    lv = {}
    for f in firms:
        p0s = sorted(ev.loc[ev["firm"] == f, "p0"])
        for i, s in enumerate(sessions):
            x = -0.2 * sum(i >= p for p in p0s) + 0.05 * sum(i == p - 1 for p in p0s) + 0.5 * mkt[s]
            x += noise * rng.standard_normal()
            if s in late:
                x += LATE_ERR
            elif s in off:
                if any(i == p for p in p0s):
                    x += B0
                elif any(i == p - 1 for p in p0s):
                    x += BM1
                else:
                    x += BORD
            if not repaid and any(i == p + 1 for p in p0s) and sessions[i - 1] in off:
                x += B0  # the day-0 error is not repaid at the next close (plan §8's violation)
            lv[(f, s)] = x
    for k, col in ((-2, "s_m2"), (-1, "s_m1"), (0, "s_0"), (1, "s_p1"), (10, "s_p10")):
        ev[col] = [sessions[p + k] for p in ev["p0"]]
    near = {(f, sessions[p]) for f, p in event_pos}
    return {"sessions": sessions, "cls": cls, "lv": lv, "m": mkt, "ev": ev, "firms": firms, "near": near,
            "off": off}


def _fit(w):
    ev = w["ev"]
    blocks = {"cm30.O": (stm.block_ordinary(w["lv"], w["m"], w["firms"], w["sessions"], w["cls"], w["near"],
                                            w["sessions"][0]), "O")}
    for kind in ("P", "A", "C"):
        blocks[f"cm30.{kind}"] = (stm.block_event(ev, w["lv"], w["m"], w["cls"], kind), kind)
    return stm.stacked_fit(blocks)


def test_planted_level_errors_are_recovered_exactly():
    w = _world()
    f = _fit(w)
    b = lambda k: float(f["f"]["b"][f["index"][k]])  # noqa: E731
    assert b("cm30.O:off") == pytest.approx(BORD, abs=1e-10)
    assert b("cm30.P:off0") == pytest.approx(-B0, abs=1e-10)
    assert b("cm30.A:offm1") == pytest.approx(BM1, abs=1e-10)
    assert b("cm30.C:off0") == pytest.approx(B0, abs=1e-10)
    assert b("cm30.C:offm1") == pytest.approx(-BM1, abs=1e-10)
    for blk in ("O", "P", "A", "C"):
        assert b(f"cm30.{blk}:dm") == pytest.approx(0.5, abs=1e-10)  # the market loading, taken out


def test_the_world_has_the_cases_the_rules_must_drop():
    w = _world()
    ev, off = w["ev"], w["off"]
    assert (ev["s_0"].isin(off) & ev["s_p1"].isin(off)).sum() > 0  # day 0 off with day +1 off: not in block P
    assert (ev["s_m1"].isin(off) & ev["s_m2"].isin(off)).sum() > 0  # day -1 off with day -2 off: not in block A
    assert (ev["s_0"].isin(off) & ev["s_m1"].isin(off)).sum() > 0  # both off: block C adds the two errors


def _shift(f, series, measure, k, n):
    return float(stm.vector(f, stm.shift_weights(series, measure, k, n)) @ f["f"]["b"])


def test_the_crush_shift_is_the_mean_planted_error_over_all_events():
    w = _world()
    f = _fit(w)
    ev, off = w["ev"], w["off"]
    off0, offm1 = ev["s_0"].isin(off), ev["s_m1"].isin(off)
    expected = float((B0 * off0 - BM1 * offm1).mean())  # plan §5: CRUSH moves by b(0) - b(-1)
    k = {"k0": int(off0.sum()), "km1": int(offm1.sum())}
    assert _shift(f, "cm30", "crush", k, len(ev)) == pytest.approx(expected, abs=1e-10)


def test_the_runup_and_persist_shifts_follow_the_baseline_share():
    w = _world()
    f = _fit(w)
    ev, off, sessions = w["ev"], w["off"], w["sessions"]
    base = [[sessions[p + k] for k in range(-35, -15)] for p in ev["p0"]]  # a 20-session baseline
    share = np.array([np.mean([s in off for s in b]) for b in base])
    offm1, off10 = ev["s_m1"].isin(off).to_numpy(), ev["s_p10"].isin(off).to_numpy()
    runup = float((BM1 * offm1 - BORD * share).mean())  # plan §5: b(-1) - mean baseline b
    persist = float((BORD * off10 - BORD * share).mean())  # b(+10) - mean baseline b
    k = {"km1": int(offm1.sum()), "k10": int(off10.sum()), "s_sum": float(share.sum())}
    assert _shift(f, "cm30", "runup", k, len(ev)) == pytest.approx(runup, abs=1e-10)
    assert _shift(f, "cm30", "persist_10", k, len(ev)) == pytest.approx(persist, abs=1e-10)


def test_the_identity_check_rejects_an_error_that_is_not_repaid():
    def p_boot(world):
        f = _fit(world)
        return stm.wcr_bootstrap(f, {}, {"cm30": stm.identity_rows(f, "cm30")}, 999, 11)["walds"]["cm30"]["p_boot"]
    assert p_boot(_world(noise=0.01)) > 0.05
    assert p_boot(_world(noise=0.01, repaid=False)) < 0.01


def test_the_bootstrap_algebra_equals_a_refit_per_draw():
    # the cheap draw of the header against the slow route: refit y* = X b + v_g u and recompute the CR1 sums
    from earnings_vol.stats import regression
    f = _fit(_world(n_firms=6, noise=0.01))
    X, b, u = f["X"], f["f"]["b"], f["f"]["u"]
    L = np.vstack([stm.vector(f, {"cm30.P:off0": -0.3, "cm30.A:offm1": -0.2}), stm.identity_rows(f, "cm30")])
    prep = stm.bootstrap_prep(f, L)
    _, gi = np.unique(f["weeks"].astype(str), return_inverse=True)
    v = stm.WEBB[np.random.default_rng(5).integers(0, 6, size=(3, prep["G"]))]
    D, U = stm.bootstrap_draws(prep, v)
    for r in range(3):
        fs = regression.fit(X @ b + v[r][gi] * u, X)
        Z = X @ (fs["xtx_inv"] @ L.T)
        sums = np.zeros((prep["G"], L.shape[0]))
        np.add.at(sums, gi, Z * fs["u"][:, None])
        assert D[r] == pytest.approx(L @ (fs["b"] - b), abs=1e-10)
        assert U[r] == pytest.approx(sums, abs=1e-10)


def test_the_bootstrap_interval_is_the_percentile_t_of_refits():
    from earnings_vol.stats import regression
    f = _fit(_world(n_firms=6, noise=0.01))
    X, b, u = f["X"], f["f"]["b"], f["f"]["u"]
    w = stm.vector(f, {"cm30.P:off0": -0.3, "cm30.A:offm1": -0.2})
    reps, seed = 300, 4
    got = stm.wild_bootstrap(f, {"s": w}, reps, seed, chunk=reps)["combos"]["s"]
    _, gi = np.unique(f["weeks"].astype(str), return_inverse=True)
    G = int(gi.max()) + 1
    se = float(np.sqrt(w @ regression.cluster_cov(f["f"], X, f["weeks"])[0] @ w))
    assert got["se"] == pytest.approx(se, rel=1e-10)
    v = stm.WEBB[np.random.default_rng(seed).integers(0, 6, size=(reps, G))]
    t = []
    for r in range(reps):
        fs = regression.fit(X @ b + v[r][gi] * u, X)
        t.append(float(w @ (fs["b"] - b)) / float(np.sqrt(w @ regression.cluster_cov(fs, X, f["weeks"])[0] @ w)))
    lo, hi = np.quantile(t, [0.05, 0.95])
    est = float(w @ b)
    assert got["ci90"] == pytest.approx([est - hi * se, est - lo * se], abs=1e-10)


def test_the_restricted_fit_is_least_squares_under_the_null():
    f = _fit(_world(n_firms=6, noise=0.01))
    X, y = f["X"], f["X"] @ f["f"]["b"] + f["f"]["u"]
    R = np.vstack([stm.vector(f, {"cm30.P:off0": -0.3, "cm30.A:offm1": -0.2}), stm.identity_rows(f, "cm30")])
    r = np.array([0.01, 0.0, 0.0])
    bt, e = stm.restricted(f, R, r)
    # the slow route: the KKT system of min |y - X b|^2 subject to R b = r
    K, q = X.shape[1], R.shape[0]
    kkt = np.block([[X.T @ X, R.T], [R, np.zeros((q, q))]])
    want = np.linalg.solve(kkt, np.concatenate([X.T @ y, r]))[:K]
    assert R @ bt == pytest.approx(r, abs=1e-10)
    assert bt == pytest.approx(want, abs=1e-8)
    assert e == pytest.approx(y - X @ bt, abs=1e-10)


def test_the_restricted_bootstrap_equals_a_refit_per_draw():
    # y* = X b~ + v_g u~ refitted per draw, against the cheap algebra of the header
    from earnings_vol.stats import regression
    f = _fit(_world(n_firms=6, noise=0.01))
    X, weeks = f["X"], f["weeks"]
    w = stm.vector(f, {"cm30.P:off0": -0.3, "cm30.A:offm1": -0.2})
    R = stm.identity_rows(f, "cm30")
    c0, reps, seed = 0.004, 200, 9
    got = stm.wcr_bootstrap(f, {"s": (w, c0)}, {"id": R}, reps, seed, chunk=reps)
    _, gi = np.unique(weeks.astype(str), return_inverse=True)
    G = int(gi.max()) + 1
    v = stm.WEBB[np.random.default_rng(seed).integers(0, 6, size=(reps, G))]
    bt, e = stm.restricted(f, w, c0)
    bw, ew = stm.restricted(f, R, np.zeros(2))
    se = float(np.sqrt(w @ regression.cluster_cov(f["f"], X, weeks)[0] @ w))
    t0 = (float(w @ f["f"]["b"]) - c0) / se
    V0 = R @ regression.cluster_cov(f["f"], X, weeks)[0] @ R.T
    W0 = float(R @ f["f"]["b"] @ np.linalg.solve(V0, R @ f["f"]["b"])) / 2
    ts, ws = [], []
    for k in range(reps):
        fs = regression.fit(X @ bt + v[k][gi] * e, X)
        ts.append((float(w @ fs["b"]) - c0) / float(np.sqrt(w @ regression.cluster_cov(fs, X, weeks)[0] @ w)))
        fw = regression.fit(X @ bw + v[k][gi] * ew, X)
        d = R @ fw["b"]
        ws.append(float(d @ np.linalg.solve(R @ regression.cluster_cov(fw, X, weeks)[0] @ R.T, d)) / 2)
    ts, ws = np.array(ts), np.array(ws)
    s = got["tests"]["s"]
    assert s["t"] == pytest.approx(t0, rel=1e-9)
    assert s["p_up"] == pytest.approx(np.mean(ts >= t0), abs=1e-12)
    assert s["p_dn"] == pytest.approx(np.mean(ts <= t0), abs=1e-12)
    assert 0 < s["p_up"] < 1  # the null sits inside the draws, so the comparison means something
    assert got["walds"]["id"]["stat"] == pytest.approx(W0, rel=1e-9)
    assert got["walds"]["id"]["p_boot"] == pytest.approx(np.mean(ws >= W0), abs=1e-12)


def test_the_tost_verdict_needs_both_one_sided_tests():
    p = lambda up, dn: {"p_up": up, "p_dn": dn}  # noqa: E731
    assert stm.tost_verdict(p(0.01, 0.99), p(0.99, 0.01)) == "SMALL"
    assert stm.tost_verdict(p(0.01, 0.99), p(0.90, 0.10)) == "UNCLEAR"  # above -line shown, below +line not
    assert stm.tost_verdict(p(0.05, 0.95), p(0.99, 0.01)) == "UNCLEAR"  # p = alpha is not below it
    assert stm.tost_verdict(p(0.99, 0.01), p(1.00, 0.00)) == "LARGE"  # below -line shown
    assert stm.tost_verdict(p(0.00, 1.00), p(0.02, 0.98)) == "LARGE"  # above +line shown
    assert stm.tost_verdict(p(0.95, 0.05), p(0.99, 0.01)) == "UNCLEAR"


def test_the_verdict_follows_the_planted_shift():
    w = _world(noise=0.005)
    f = _fit(w)
    ev, off = w["ev"], w["off"]
    off0, offm1 = ev["s_0"].isin(off), ev["s_m1"].isin(off)
    true = float((B0 * off0 - BM1 * offm1).mean())
    k = {"k0": int(off0.sum()), "km1": int(offm1.sum())}
    sw = stm.vector(f, stm.shift_weights("cm30", "crush", k, len(ev)))

    def verdict(line):
        t = stm.wcr_bootstrap(f, stm.line_tests(sw, line), {}, 999, 3)["tests"]
        return stm.tost_verdict(t["lo"], t["hi"])
    assert true > 0.005
    assert verdict(2 * true) == "SMALL"
    assert verdict(true / 2) == "LARGE"
    assert verdict(true) == "UNCLEAR"  # the shift sits on the line


def test_a_failed_identity_check_stops_its_own_series_being_small():
    v = {"H1": "SMALL", "H2": "SMALL", "H3": "LARGE", "H4": "SMALL"}
    series = {"H1": "cm30", "H2": "cm30", "H3": "cm30", "H4": "sigma"}
    assert stm.gated(v, series, {"cm30": False, "sigma": False}) == v
    assert stm.gated(v, series, {"cm30": True, "sigma": False}) == {"H1": "UNCLEAR", "H2": "UNCLEAR",
                                                                     "H3": "LARGE", "H4": "SMALL"}
    assert stm.gated(v, series, {"cm30": False, "sigma": True})["H4"] == "UNCLEAR"


def test_the_ordering_slope_recovers_a_planted_share_of_the_gap():
    rng = np.random.default_rng(3)
    g = rng.normal(0, 0.06, 150)  # the overnight gap that holds the news
    y = 0.9 * g + rng.normal(0, 0.008, 150)  # a day -1 snapshot after the news carries 90% of it
    s = stm.ordering_slope(y, g, [f"d{i // 2}" for i in range(150)])
    assert s["ci_lo"] < 0.9 < s["ci_hi"]
    assert s["ci_hi"] - s["ci_lo"] < 0.1


def test_an_event_keyed_series_reads_its_own_levels():
    # one company, two events whose days overlap: the sigma_d level of each is its own pair's, so the same session
    # holds two different levels and the block must read each event's own
    d = [date(2025, 3, 3) + timedelta(days=i) for i in range(4)]  # Mon..Thu
    ev = pd.DataFrame({"event_id": ["e1", "e2"], "firm": ["F", "F"], "season": ["S1", "S1"],
                       "s_m2": [d[0], d[0]], "s_m1": [d[1], d[1]], "s_0": [d[2], d[2]], "s_p1": [d[3], d[3]]})
    lv = {("e1", d[1]): 0.0, ("e1", d[2]): -0.3, ("e2", d[1]): 1.0, ("e2", d[2]): 0.9,
          ("F", d[1]): 5.0, ("F", d[2]): 5.0}
    m = {s: 0.0 for s in d}
    cls = lambda s: "close"  # noqa: E731
    by_event = stm.block_event(ev, lv, m, cls, "C", key="event_id")
    assert by_event["y"].tolist() == pytest.approx([-0.3, -0.1])
    assert by_event["firm"].tolist() == ["F", "F"]  # clustering and dummies stay by company
    assert stm.block_event(ev, lv, m, cls, "C")["y"].tolist() == pytest.approx([0.0, 0.0])


def test_a_weekday_that_one_company_owns_is_dropped_and_nothing_else():
    # company Z's day -1 is always a Friday and no other company's is: the Friday dummy equals Z's dummy
    rng = np.random.default_rng(2)
    n = 40
    firm = ["Z"] * 8 + [f"F{i % 4}" for i in range(n - 8)]
    wd = [4] * 8 + [int(x) for x in rng.integers(0, 4, n - 8)]
    blk = pd.DataFrame({"y": rng.normal(size=n), "dm": rng.normal(size=n), "firm": firm,
                        "season": [f"S{i % 3}" for i in range(n)], "week": ["w"] * n, "weekday": wd,
                        "event_id": [str(i) for i in range(n)], "offm1": (rng.random(n) < 0.3).astype(float)})
    X, names = stm.design(blk, "A")
    assert np.linalg.matrix_rank(X) == X.shape[1]
    assert "weekday:4" not in names and "firm:Z" in names and "offm1" in names and "dm" in names
    blk["weekday"] = [int(x) for x in rng.integers(0, 5, n)]  # no such dependence: every weekday stays
    assert {"weekday:1", "weekday:2", "weekday:3", "weekday:4"} <= set(stm.design(blk, "A")[1])
    # Z owns Wednesday instead: Wednesday goes, and Friday (the last weekday, independent here) stays
    blk["weekday"] = [2] * 8 + [int(x) for x in rng.choice([0, 1, 3, 4], n - 8)]
    X, names = stm.design(blk, "A")
    assert np.linalg.matrix_rank(X) == X.shape[1]
    assert "weekday:2" not in names and {"weekday:1", "weekday:3", "weekday:4"} <= set(names)
