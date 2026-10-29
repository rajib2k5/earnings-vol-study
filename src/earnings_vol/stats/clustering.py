# =============================================================================
# clustering.py — Cluster-robust inference for an equal-weighted mean
# (ADR 0005 §2b, §2f). Pure numpy/scipy, no statsmodels: every formula is
# the one on the whiteboard. tests/test_clustering.py checks it against a
# hand-worked 4-event case and against statsmodels with use_t=True.
#
# ONE-WAY CR1, for a clustering g with G groups (u_i = A_i - mean A):
#   V_g = G/(G-1) * (1/N^2) * sum_c (sum_{i in c} u_i)^2
# TWO-WAY (Cameron, Gelbach & Miller 2011), dimensions A and B:
#   V = V_A + V_B - V_{A and B};  if V <= 0, use max(V_A, V_B)
#   t = mean / sqrt(V), compared with t_{min(G_A, G_B) - 1}.
#   V_{A and B} clusters by the (A, B) pairs, with its own G/(G-1).
# THE CI is mean +- t_{df, 0.975} * se, on the same reference as the p-value.
#
# SEASONS (§2b). events.season is the calendar quarter of day 0. A season
# with fewer than 10 events of the test's event set joins the neighbouring
# season whose median day 0 is nearest (ties: the earlier one), repeated
# until none is left, the earliest small season first (merging one moves its
# neighbour's median, so the order can matter). If the largest merged season is more than 1.5 times the
# smallest, the seasons are unbalanced and the ramp p-value comes from
# rad_season_p.
#
# RAD_SEASON_P (§2f). The wild cluster restricted bootstrap by season with
# ALL 2^G Rademacher sign vectors: under H0 the residuals are A_i itself, so
# the season sums S_g get every sign pattern; each gives a one-way CR1 t*.
#   p = share of the 2^G vectors with |t*| >= |t| (a tolerance of 1e-12)
# Its smallest value is 2/2^G (the observed signs and their mirror).
# =============================================================================

import itertools

import numpy as np
from scipy import stats


def _codes(groups) -> tuple[np.ndarray, int]:
    _, gi = np.unique(np.asarray(groups), return_inverse=True)
    return gi, int(gi.max()) + 1 if gi.size else 0


def cr1_variance(A: np.ndarray, groups) -> tuple[float, int]:
    """(V_g, G): the one-way CR1 variance of the mean of A (see the header)."""
    A = np.asarray(A, float)
    n = A.size
    gi, g = _codes(groups)
    s = np.bincount(gi, A - A.mean(), g)
    return float(g / (g - 1) * (s ** 2).sum() / n ** 2), g


def _row(est: float, var: float, df: float, n: int, g: int, gf: int | None) -> dict:
    se = float(np.sqrt(var))
    t = est / se if se > 0 else np.nan
    q = stats.t.ppf(0.975, df)
    return {"estimate": est, "se": se, "stat": t, "df": float(df),
            "p_value": float(2 * stats.t.sf(abs(t), df)) if se > 0 else np.nan,
            "ci_lo": est - q * se, "ci_hi": est + q * se, "n": n, "n_clusters": g, "n_clusters_firm": gf}


def oneway(A: np.ndarray, groups) -> dict:
    """One-way CR1 t of the mean of A: estimate, se, stat, df = G - 1, p, CI, n, n_clusters."""
    A = np.asarray(A, float)
    v, g = cr1_variance(A, groups)
    return _row(float(A.mean()), v, g - 1, A.size, g, None)


def twoway(A: np.ndarray, groups_a, groups_b) -> dict:
    """Two-way CGM t of the mean of A, time dimension a and firm dimension b.

    df = min(G_a, G_b) - 1; `fallback` is True when V <= 0 and max(V_a, V_b) was used."""
    A = np.asarray(A, float)
    va, ga = cr1_variance(A, groups_a)
    vb, gb = cr1_variance(A, groups_b)
    vab, _ = cr1_variance(A, [f"{x}\x1f{y}" for x, y in zip(groups_a, groups_b)])
    v = va + vb - vab
    fallback = v <= 0
    if fallback:
        v = max(va, vb)
    out = _row(float(A.mean()), v, min(ga, gb) - 1, A.size, ga, gb)
    out.update(fallback=bool(fallback), v_a=va, v_b=vb, v_ab=vab)
    return out


def merge_small_seasons(season, day0_ordinal, min_events: int = 10) -> np.ndarray:
    """The merged season of each event (see the header). `day0_ordinal` orders day 0."""
    cl = np.asarray(season, dtype=object).copy()
    d0 = np.asarray(day0_ordinal, float)
    while True:
        keys = sorted(set(cl.tolist()))
        cnt = {k: int((cl == k).sum()) for k in keys}
        small = [k for k in keys if cnt[k] < min_events]
        if not small or len(keys) == 1:
            return cl
        k = small[0]
        j = keys.index(k)
        med = {q: float(np.median(d0[cl == q])) for q in keys}
        nb = [keys[x] for x in (j - 1, j + 1) if 0 <= x < len(keys)]
        cl[cl == k] = min(nb, key=lambda q: (abs(med[q] - med[k]), q))


def unbalanced(clusters, ratio: float = 1.5) -> bool:
    """True when the largest cluster has more than `ratio` times the events of the smallest."""
    _, c = np.unique(np.asarray(clusters, dtype=object).astype(str), return_counts=True)
    return bool(c.max() > ratio * c.min())


def sign_vectors(g: int) -> np.ndarray:
    """All 2^g Rademacher sign vectors, one per row."""
    return np.array(list(itertools.product((-1.0, 1.0), repeat=g)))


def rademacher_p(A: np.ndarray, season) -> dict:
    """rad_season_p: the full-enumeration restricted wild cluster p-value by season (header).

    Returns estimate (the mean), stat (the one-way CR1 t), p_value, n, n_clusters and
    n_vectors (always 2^G)."""
    A = np.asarray(A, float)
    n = A.size
    gi, g = _codes(season)
    t = oneway(A, season)["stat"]
    s0 = np.bincount(gi, A, g)
    ng = np.bincount(gi, None, g)
    v = sign_vectors(g)
    ss = v * s0[None, :]
    m = ss.sum(1) / n
    var = g / (g - 1) * ((ss - ng[None, :] * m[:, None]) ** 2).sum(1) / n ** 2
    with np.errstate(invalid="ignore", divide="ignore"):
        tstar = np.abs(m / np.sqrt(var))
    p = float((tstar >= abs(t) - 1e-12).mean())
    return {"estimate": float(A.mean()), "stat": float(t), "p_value": p, "n": n, "n_clusters": g,
            "n_vectors": int(v.shape[0])}
