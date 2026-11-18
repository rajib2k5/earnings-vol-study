# =============================================================================
# snapshot_timing.py — When in the day was each option snapshot taken? Pure
# statistics for the 2026 snapshot-timing check.
#
# The plan is docs/validation/snapshot-timing/preregistration.md (owner
# decision 2026-11-18, report §9 Q9, option 3). tools/snapshot_timing_map.py
# reads the files and writes docs/validation/snapshot-timing/timing_map.json;
# everything here is pure.
#
# THE QUANTITY, per company and snapshot session t
#   gap = ln(S_parity,t / Close_t), S_parity from the put-call-parity forward of
#   the nearest expiry with at least 5 sessions to go (measures/snapshot_close),
#   and r = ln(Close_t / Close_{t-1}), t-1 the NYSE session before t.
#   - snapshot at the close:        gap ~ 0 (a few bp of quote noise)
#   - snapshot during day t:        gap = -(the move from the snapshot to the
#                                   close), so gap leans on -r with a slope of
#                                   about the share of the day still to come
#   - snapshot = the close of t-1:  gap = -r exactly, slope 1 ("late")
#
# THE DAY'S CLASS (pre-registration §3), from the companies with a value
#   n           companies with both gap and r
#   gap_bp      median |gap| in bp
#   ret_bp      median |r| in bp
#   ratio       gap_bp / ret_bp (scale-free: a volatile day at the close has a
#               larger gap_bp, but not a larger ratio)
#   slope       OLS slope of gap on -r across the companies
#   unknown  n < MIN_FIRMS
#   off      gap_bp > GAP_BP and ratio > RATIO
#   late     off and slope >= LATE_SLOPE
#   close    otherwise
#
# WORKED (made-up numbers, tests/test_snapshot_timing.py)
#   r = +1%, -2%, +3% and gap = -0.5%, +1%, -1.5%: gap = -0.5 r, slope 0.5,
#   gap_bp 100, ret_bp 200, ratio 0.5 -> off (with n >= MIN_FIRMS).
# =============================================================================

import numpy as np
import pandas as pd
from scipy import stats as sps

from earnings_vol.stats import regression

MIN_FIRMS = 20
GAP_BP = 20.0
RATIO = 0.2
LATE_SLOPE = 0.8


def day_stats(gap, neg_r) -> dict:
    """n, gap_bp, ret_bp, ratio and slope (gap on -r) for one session (see the header)."""
    g, x = np.asarray(gap, float), np.asarray(neg_r, float)
    keep = np.isfinite(g) & np.isfinite(x)
    g, x = g[keep], x[keep]
    n = int(g.size)
    if n < 3:
        return {"n": n, "gap_bp": np.nan, "ret_bp": np.nan, "ratio": np.nan, "slope": np.nan}
    gap_bp = float(np.median(np.abs(g)) * 1e4)
    ret_bp = float(np.median(np.abs(x)) * 1e4)
    xc = x - x.mean()
    sxx = float(xc @ xc)
    slope = float(xc @ (g - g.mean()) / sxx) if sxx > 0 else np.nan
    return {"n": n, "gap_bp": gap_bp, "ret_bp": ret_bp,
            "ratio": gap_bp / ret_bp if ret_bp > 0 else np.nan, "slope": slope}


def classify(s: dict) -> str:
    """close, off, late or unknown for one session's day_stats (see the header)."""
    if s["n"] < MIN_FIRMS:
        return "unknown"
    off = s["gap_bp"] > GAP_BP and s["ratio"] > RATIO
    if not off:
        return "close"
    return "late" if s["slope"] >= LATE_SLOPE else "off"


# =============================================================================
# THE CHECK (pre-registration §5-§10). X is a ln level (ln CM30 per company, or
# ln sigma_d per event) on `ok` snapshots; M is ln VIX (Cboe close, untouched by
# the snapshot timing); cls maps a session to its class (a session the map does
# not list is close). Every function below takes values and returns values.
#
# BLOCKS (§7), each a frame with columns y, dm, firm, week and its regressors:
#   O  ordinary company-sessions t: h = (D_t - D_{t+1}) / 2, t-1 and t+1 close,
#      t close or off, t outside [-2, +2] of the company's day 0s; dm = the same
#      h of M; weekday of t, off
#   P  events: D_{+1} = X(+1) - X(0), day +1 close, day 0 close or off; off0
#   A  events: D_{-1} = X(-1) - X(-2), day -2 close, day -1 close or off; offm1
#   C  events: X(0) - X(-1), both close or off; off0, offm1
#   P, A, C: dm = the change of M over the same two sessions; company, season
#   and weekday-of-the-end-session dummies.
#   week = ISO week of the row's end session (O: t, P: +1, A: -1, C: 0).
# A late or unknown session never enters a block (§5, §5a).
#
# INFERENCE (§7, §8, §10): one-way CR1 by ISO week; Webb six-point weights.
#   Verdicts and the identity check: the RESTRICTED wild cluster bootstrap by
#   ISO week (the null imposed). For H0: w'b = c, the restricted fit b~ and its
#   residuals u~; y* = X b~ + v_g u~; t* = (w'b* - c) / se*, and the observed
#   t = (w'b - c) / se. p_up = P*(t* >= t) tests H0 w'b <= c; p_dn = P*(t* <= t)
#   tests H0 w'b >= c. The identity's Wald statistic is drawn the same way with
#   R b = 0 imposed.
#   Descriptive intervals: the unrestricted bootstrap-t, [w'b - q_hi se,
#   w'b - q_lo se], q the quantiles of t* = w'(b* - b) / se*, y* = X b + v_g u.
# Either way y* = X b0 + v_g e for a centre b0 and residuals e, so
# b* - b0 = sum_g v_g S_g (S_g = A X_g' e_g, A = (X'X)^-1), and the cluster sums
# of z_i u*_i are v_g C_g - M_g (b* - b0) (z = X A w, C_g = sum z_i e_i,
# M_g = sum z_i x_i'): each draw costs O(G K), no refit.
# =============================================================================

USABLE = ("close", "off")
WEBB = np.array([-np.sqrt(1.5), -1.0, -np.sqrt(0.5), np.sqrt(0.5), 1.0, np.sqrt(1.5)])
OFFS = {"O": ["off"], "P": ["off0"], "A": ["offm1"], "C": ["off0", "offm1"]}


def iso_week(d) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def _finite(*v) -> bool:
    return all(x is not None for x in v) and bool(np.isfinite(v).all())


def block_ordinary(lv: dict, m: dict, firms, sessions: list, cls, near_event: set, first) -> pd.DataFrame:
    """Block O. lv[(firm, session)] = X, m[session] = M; near_event holds (firm, session) within [-2, +2] of a
    day 0; t - 1 must be on or after `first` (the daily era's first session)."""
    rows = []
    for i in range(1, len(sessions) - 1):
        a, t, c = sessions[i - 1], sessions[i], sessions[i + 1]
        if a < first or cls(a) != "close" or cls(c) != "close" or cls(t) not in USABLE:
            continue
        ma, mt, mc = m.get(a), m.get(t), m.get(c)
        if not _finite(ma, mt, mc):
            continue
        dm = ((mt - ma) - (mc - mt)) / 2.0
        for f in firms:
            if (f, t) in near_event:
                continue
            xa, xt, xc = lv.get((f, a)), lv.get((f, t)), lv.get((f, c))
            if not _finite(xa, xt, xc):
                continue
            rows.append({"y": ((xt - xa) - (xc - xt)) / 2.0, "dm": dm, "firm": f, "week": iso_week(t),
                         "weekday": t.weekday(), "off": float(cls(t) == "off")})
    return pd.DataFrame(rows, columns=["y", "dm", "firm", "week", "weekday", "off"])


def block_event(ev: pd.DataFrame, lv: dict, m: dict, cls, kind: str, key: str = "firm") -> pd.DataFrame:
    """Block P, A or C for the events in ev (columns event_id, firm, season, s_m2, s_m1, s_0, s_p1).
    The level is lv[(r.<key>, session)]: key "firm" for ln CM30 (one series per company), "event_id" for ln sigma_d
    (one series per event: the forward variance between that event's expiry pair, held fixed as H4 holds it)."""
    if key not in ("firm", "event_id"):
        raise ValueError(key)
    rows = []
    for r in ev.itertuples(index=False):
        k = r.event_id if key == "event_id" else r.firm
        if kind == "P":
            lo, hi, need_close, need_usable = r.s_0, r.s_p1, [r.s_p1], [r.s_0]
        elif kind == "A":
            lo, hi, need_close, need_usable = r.s_m2, r.s_m1, [r.s_m2], [r.s_m1]
        elif kind == "C":
            lo, hi, need_close, need_usable = r.s_m1, r.s_0, [], [r.s_m1, r.s_0]
        else:
            raise ValueError(kind)
        if any(cls(s) != "close" for s in need_close) or any(cls(s) not in USABLE for s in need_usable):
            continue
        x0, x1, m0, m1 = lv.get((k, lo)), lv.get((k, hi)), m.get(lo), m.get(hi)
        if not _finite(x0, x1, m0, m1):
            continue
        rows.append({"y": x1 - x0, "dm": m1 - m0, "firm": r.firm, "season": r.season, "week": iso_week(hi),
                     "weekday": hi.weekday(), "event_id": r.event_id,
                     "off0": float(cls(r.s_0) == "off"), "offm1": float(cls(r.s_m1) == "off")})
    return pd.DataFrame(rows, columns=["y", "dm", "firm", "season", "week", "weekday", "event_id", "off0", "offm1"])


def design(block: pd.DataFrame, kind: str) -> tuple[np.ndarray, list[str]]:
    """The block's own columns: an intercept, its dummies, dm, then its off indicator(s) (§7's table)."""
    n = len(block)
    parts, names = [np.ones((n, 1))], ["const"]
    labels = ("weekday",) if kind == "O" else ("firm", "season", "weekday")
    for lab in labels:
        d, c = regression.dummies(block[lab], lab)
        parts.append(d)
        names += c
    parts.append(block[["dm"] + OFFS[kind]].to_numpy(float))
    names += ["dm"] + OFFS[kind]
    X = np.column_stack(parts)
    # A weekday dummy that other columns already span carries nothing (BRK.B reports on Saturdays, so its day -1
    # is a Friday, and in block A no other event's is): drop such weekday columns, last first. Any other
    # dependence is an error (regression.fit refuses it).
    k = np.linalg.matrix_rank(X)
    for j in [j for j in range(len(names) - 1, -1, -1) if names[j].startswith("weekday:")]:
        if k == X.shape[1]:
            break
        Xd = np.delete(X, j, axis=1)
        if np.linalg.matrix_rank(Xd) == k:
            X, names = Xd, names[:j] + names[j + 1:]
    return X, names


def stacked_fit(blocks: dict) -> dict:
    """One OLS over block-diagonal designs: blocks[name] = (frame, kind). The coefficients are those of the
    separate fits; the one-way CR1 covariance by ISO week is joint across blocks (§7).
    Returns f, cov, X, weeks, index {"<name>:<column>": j}, n_rows."""
    Xs, ys, weeks, index, k0 = [], [], [], {}, 0
    for name, (frame, kind) in blocks.items():
        X, cols = design(frame, kind)
        Xs.append(X)
        ys.append(frame["y"].to_numpy(float))
        weeks += frame["week"].tolist()
        index.update({f"{name}:{c}": k0 + j for j, c in enumerate(cols)})
        k0 += X.shape[1]
    n = sum(x.shape[0] for x in Xs)
    X = np.zeros((n, k0))
    r = c = 0
    for x in Xs:
        X[r:r + x.shape[0], c:c + x.shape[1]] = x
        r, c = r + x.shape[0], c + x.shape[1]
    f = regression.fit(np.concatenate(ys), X)
    weeks = np.asarray(weeks)
    cov = regression.covariance(f, X, weeks)
    return {"f": f, "cov": cov, "X": X, "weeks": weeks, "index": index,
            "n_rows": {k: int(len(v[0])) for k, v in blocks.items()}}


def vector(fit: dict, weights: dict) -> np.ndarray:
    """w with w[index[key]] = weight: a linear combination of the stacked coefficients."""
    w = np.zeros(len(fit["f"]["b"]))
    for k, v in weights.items():
        w[fit["index"][k]] += v
    return w


def shift_weights(series: str, measure: str, k: dict, n: int) -> dict:
    """The weights of §9 on the stacked coefficients. k holds k0, km1 (CRUSH, dSIGMA_D), km1 (RUNUP), k10
    (PERSIST_10) and s_sum (the sum over events of the share of off baseline sessions)."""
    P, A, O = f"{series}.P:off0", f"{series}.A:offm1", f"{series}.O:off"
    if measure in ("crush", "dsigma_d"):
        return {P: -k["k0"] / n, A: -k["km1"] / n}
    if measure == "runup":
        return {A: k["km1"] / n, O: -k["s_sum"] / n}
    if measure == "persist_10":
        return {O: (k["k10"] - k["s_sum"]) / n}
    raise ValueError(measure)


def identity_rows(fit: dict, series: str) -> np.ndarray:
    """§8 for one series: the rows of beta_C0 + beta_P = 0 and beta_C1 + beta_A = 0."""
    return np.array([vector(fit, {f"{series}.C:off0": 1.0, f"{series}.P:off0": 1.0}),
                     vector(fit, {f"{series}.C:offm1": 1.0, f"{series}.A:offm1": 1.0})])


def _cluster_sums(gi: np.ndarray, G: int, v: np.ndarray) -> np.ndarray:
    s = np.zeros((G,) + v.shape[1:])
    np.add.at(s, gi, v)
    return s


def bootstrap_base(fit: dict) -> dict:
    """What every bootstrap of one fit shares: the cluster index, X A and the CR1 factor."""
    X, f = fit["X"], fit["f"]
    _, gi = np.unique(fit["weeks"].astype(str), return_inverse=True)
    G = int(gi.max()) + 1
    n, k = X.shape
    return {"gi": gi, "G": G, "XA": X @ f["xtx_inv"], "c": G / (G - 1) * (n - 1) / (n - k)}


def bootstrap_prep(fit: dict, L: np.ndarray, e: np.ndarray | None = None, base: dict | None = None) -> dict:
    """The per-cluster pieces of the wild bootstrap for the rows of L (m x K), see the header. e: the residuals the
    draws scale (default the fit's own, the unrestricted bootstrap; restricted residuals impose a null)."""
    X, f = fit["X"], fit["f"]
    base = base or bootstrap_base(fit)
    gi, G = base["gi"], base["G"]
    e = f["u"] if e is None else e
    Z = base["XA"] @ L.T
    S = _cluster_sums(gi, G, base["XA"] * e[:, None])
    C = _cluster_sums(gi, G, Z * e[:, None])
    M = np.stack([Z[gi == g].T @ X[gi == g] for g in range(G)])
    return {"L": L, "S": S, "C": C, "M": M, "G": G, "c": base["c"], "est": L @ f["b"]}


def restricted(fit: dict, R: np.ndarray, r) -> tuple[np.ndarray, np.ndarray]:
    """The least-squares fit under R b = r, and its residuals: b~ = b - A R'(R A R')^-1 (R b - r)."""
    f, X = fit["f"], fit["X"]
    R, r = np.atleast_2d(R), np.atleast_1d(np.asarray(r, float))
    A, b = f["xtx_inv"], f["b"]
    bt = b - A @ R.T @ np.linalg.solve(R @ A @ R.T, R @ b - r)
    return bt, f["u"] + X @ (b - bt)


def bootstrap_draws(prep: dict, v: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """For draws v (R x G): (D, U) with D = L (b* - b) (R x m) and U the cluster sums of z u* (R x G x m)."""
    delta = v @ prep["S"]
    D = delta @ prep["L"].T
    U = v[:, :, None] * prep["C"][None] - np.einsum("gmk,rk->rgm", prep["M"], delta)
    return D, U


def _draws(rng, reps: int, G: int, chunk: int):
    done = 0
    while done < reps:
        r = min(chunk, reps - done)
        yield done, r, WEBB[rng.integers(0, 6, size=(r, G))]
        done += r


def wild_bootstrap(fit: dict, combos: dict, reps: int, seed: int, chunk: int = 500) -> dict:
    """Descriptive (§7): combos {name: w (K)} -> estimate, se (CR1 by week) and the 90% and 95% unrestricted
    bootstrap-t intervals."""
    names = list(combos)
    L = np.vstack([np.atleast_2d(combos[k]) for k in names])
    prep = bootstrap_prep(fit, L)
    c, est = prep["c"], prep["est"]
    se = np.sqrt(c * np.sum(prep["C"] ** 2, axis=0))
    tstar = np.empty((reps, len(names)))
    for done, r, v in _draws(np.random.default_rng(seed), reps, prep["G"], chunk):
        D, U = bootstrap_draws(prep, v)
        tstar[done:done + r] = D / np.sqrt(c * np.sum(U ** 2, axis=1))
    out = {"combos": {}, "reps": reps, "seed": seed, "clusters": prep["G"]}
    for i, k in enumerate(names):
        row = {"estimate": float(est[i]), "se": float(se[i])}
        for lvl in (0.90, 0.95):
            lo_q, hi_q = np.quantile(tstar[:, i], [(1 - lvl) / 2, 1 - (1 - lvl) / 2])
            row[f"ci{int(lvl * 100)}"] = [float(est[i] - hi_q * se[i]), float(est[i] - lo_q * se[i])]
        out["combos"][k] = row
    return out


def wcr_bootstrap(fit: dict, tests: dict, walds: dict, reps: int, seed: int, chunk: int = 500) -> dict:
    """The restricted wild cluster bootstrap by ISO week (§8, §10), every null on the same draws.
    tests {name: (w (K), c)}: t = (w'b - c) / se, p_up = P*(t* >= t), p_dn = P*(t* <= t), under w'b = c imposed.
    walds {name: R (q x K)}: the Wald statistic of R b = 0 / q (CR1 by week), its p under R b = 0 imposed, and the
    analytic F(q, G - 1) p."""
    base = bootstrap_base(fit)
    G, c = base["G"], base["c"]
    b = fit["f"]["b"]
    jobs = {}
    for k, (w, c0) in tests.items():
        w = np.atleast_2d(w)
        un = bootstrap_prep(fit, w, base=base)
        se = float(np.sqrt(c * np.sum(un["C"] ** 2)))
        _, e = restricted(fit, w, c0)
        jobs[("t", k)] = (bootstrap_prep(fit, w, e, base), float((w @ b)[0] - c0) / se, se, float(c0))
    for k, R in walds.items():
        R = np.atleast_2d(R)
        un = bootstrap_prep(fit, R, base=base)
        V = c * un["C"].T @ un["C"]
        d = R @ b
        _, e = restricted(fit, R, np.zeros(len(R)))
        jobs[("w", k)] = (bootstrap_prep(fit, R, e, base), float(d @ np.linalg.solve(V, d)) / len(R), None, None)
    stars = {j: np.empty(reps) for j in jobs}
    for done, r, v in _draws(np.random.default_rng(seed), reps, G, chunk):
        for j, (prep, _, _, _) in jobs.items():
            D, U = bootstrap_draws(prep, v)  # D = L (b* - b~): the restriction holds at b~
            Vs = c * np.einsum("rgm,rgn->rmn", U, U)
            if j[0] == "t":
                stars[j][done:done + r] = D[:, 0] / np.sqrt(Vs[:, 0, 0])
            else:
                stars[j][done:done + r] = np.einsum("rq,rq->r", D, np.linalg.solve(Vs, D[:, :, None])[:, :, 0]) \
                    / D.shape[1]
    out = {"tests": {}, "walds": {}, "reps": reps, "seed": seed, "clusters": G}
    for (kind, k), (prep, stat, se, c0) in jobs.items():
        s = stars[(kind, k)]
        if kind == "t":
            out["tests"][k] = {"estimate": float(prep["est"][0]), "se": se, "c": c0, "t": stat,
                               "p_up": float(np.mean(s >= stat)), "p_dn": float(np.mean(s <= stat))}
        else:
            q = prep["L"].shape[0]
            out["walds"][k] = {"stat": stat, "q": int(q), "p_boot": float(np.mean(s >= stat)),
                               "p_F": float(sps.f.sf(stat, q, G - 1))}
    return out


def line_tests(w: np.ndarray, line: float) -> dict:
    """§10's two nulls for one shift: w'b = -line and w'b = +line."""
    return {"lo": (w, -line), "hi": (w, line)}


def tost_verdict(lo: dict, hi: dict, alpha: float = 0.05) -> str:
    """§10, from the restricted-bootstrap tests at -line (lo) and +line (hi): SMALL when both -line < shift and
    shift < +line are shown at alpha (two one-sided tests); LARGE when shift < -line or shift > +line is shown at
    alpha; else UNCLEAR."""
    if lo["p_up"] < alpha and hi["p_dn"] < alpha:
        return "SMALL"
    if lo["p_dn"] < alpha or hi["p_up"] < alpha:
        return "LARGE"
    return "UNCLEAR"


def gated(verdicts: dict, series_of: dict, rejected: dict) -> dict:
    """§10: a measure whose series fails the identity check of §8 cannot be SMALL (it becomes UNCLEAR)."""
    return {h: ("UNCLEAR" if v == "SMALL" and rejected[series_of[h]] else v) for h, v in verdicts.items()}


# --- §6, the ordering description ---------------------------------------------

def ordering_slope(y, g, clusters) -> dict:
    """OLS slope of y on g with an intercept, one-way CR1 by clusters, 95% interval on t(G - 1)."""
    y, g = np.asarray(y, float), np.asarray(g, float)
    X = np.column_stack([np.ones_like(g), g])
    f = regression.fit(y, X)
    cov = regression.covariance(f, X, np.asarray(clusters))
    return regression.coef_test(f, cov, 1)
