# =============================================================================
# regression.py — OLS with cluster-robust inference (ADR 0005 §3), pure numpy
# and scipy like clustering.py: every formula is the one on the whiteboard.
# tests/test_regression.py checks it against a hand-worked 4-event case and
# against statsmodels' OLS with cov_type "cluster" and use_t=True.
#
# THE FIT. y = X b + u, b = (X'X)^-1 X'y, u the residuals, N rows, K columns.
# ONE-WAY CR1 for a clustering g with G groups (statsmodels' cov_cluster with
# its default small-sample correction):
#   V_g = c_g (X'X)^-1 [ sum_c (X_c' u_c)(X_c' u_c)' ] (X'X)^-1,
#   c_g = G/(G-1) * (N-1)/(N-K)
#   For an intercept-only model (K = 1) this is clustering.cr1_variance.
# TWO-WAY (Cameron, Gelbach & Miller 2011): V = V_A + V_B - V_{A and B}, each
#   with its own c_g; the intersection clusters by the (A, B) pairs. When a
#   firm has one event per date that term is the event-level HC1.
#   If a coefficient's variance comes out <= 0, that coefficient uses
#   max(V_A, V_B) (clustering.twoway's rule); a Wald block that is not
#   positive definite uses the one-way block with the larger trace. Both are
#   flagged (`fallback`).
# REFERENCE DISTRIBUTION (ADR 0005 §3 and §5): t with df = min(G_A, G_B) - 1
#   (two-way) or G - 1 (one-way), never the normal; the CI is
#   b +- t_{df,0.975} se; the Wald test of R b = r with q rows is
#   F = (R b - r)' (R V R')^-1 (R b - r) / q against F(q, df).
# Z-SCORES. Regressors are z-scored over the regression's own rows (ddof 1),
# so a coefficient reads "one sd more of the regressor -> b log points".
# FIXED EFFECTS are dummy columns, one level dropped (the first in sorted
# order); their coefficients are never reported (data model §2.1).
# =============================================================================

import numpy as np
from scipy import stats


def zscore(v: np.ndarray) -> np.ndarray:
    """(v - mean) / sd, sd with ddof 1."""
    v = np.asarray(v, float)
    return (v - v.mean()) / v.std(ddof=1)


def dummies(labels, prefix: str) -> tuple[np.ndarray, list[str]]:
    """(N x (L-1) 0/1 matrix, column names) for the L levels of `labels`, the first level in
    sorted order dropped (it is absorbed by the intercept)."""
    lab = np.asarray(labels, dtype=object).astype(str)
    levels = sorted(set(lab.tolist()))
    cols = levels[1:]
    return (np.column_stack([(lab == c).astype(float) for c in cols]) if cols else np.zeros((lab.size, 0)),
            [f"{prefix}:{c}" for c in cols])


def _codes(groups) -> tuple[np.ndarray, int]:
    _, gi = np.unique(np.asarray(groups).astype(str), return_inverse=True)
    return gi, int(gi.max()) + 1


def fit(y: np.ndarray, X: np.ndarray) -> dict:
    """OLS: b, residuals, (X'X)^-1, N, K, R^2. Refuses a rank-deficient X."""
    y, X = np.asarray(y, float), np.asarray(X, float)
    n, k = X.shape
    if np.linalg.matrix_rank(X) < k:
        raise ValueError(f"the design matrix has rank {np.linalg.matrix_rank(X)} < {k} columns")
    xtx_inv = np.linalg.inv(X.T @ X)
    b = xtx_inv @ (X.T @ y)
    u = y - X @ b
    tss = float(((y - y.mean()) ** 2).sum())
    return {"b": b, "u": u, "xtx_inv": xtx_inv, "n": n, "k": k, "r2": 1.0 - float(u @ u) / tss if tss > 0 else np.nan}


def cluster_cov(f: dict, X: np.ndarray, groups) -> tuple[np.ndarray, int]:
    """(V_g, G): the one-way CR1 covariance of the coefficients (see the header)."""
    gi, g = _codes(groups)
    xu = np.asarray(X, float) * f["u"][:, None]
    s = np.zeros((g, xu.shape[1]))
    np.add.at(s, gi, xu)
    meat = s.T @ s
    c = g / (g - 1) * (f["n"] - 1) / (f["n"] - f["k"])
    return c * f["xtx_inv"] @ meat @ f["xtx_inv"], g


def covariance(f: dict, X: np.ndarray, groups_a, groups_b=None) -> dict:
    """{"V", "V_a", "V_b", "g_a", "g_b", "df"}: one-way CR1 by groups_a when groups_b is None,
    else the two-way CGM covariance (V_b, g_b None for one-way)."""
    va, ga = cluster_cov(f, X, groups_a)
    if groups_b is None:
        return {"V": va, "V_a": va, "V_b": None, "g_a": ga, "g_b": None, "df": float(ga - 1)}
    vb, gb = cluster_cov(f, X, groups_b)
    vab, _ = cluster_cov(f, X, [f"{a}\x1f{b}" for a, b in zip(np.asarray(groups_a).astype(str),
                                                               np.asarray(groups_b).astype(str))])
    return {"V": va + vb - vab, "V_a": va, "V_b": vb, "g_a": ga, "g_b": gb, "df": float(min(ga, gb) - 1)}


def coef_test(f: dict, cov: dict, j: int) -> dict:
    """The t row of coefficient j: estimate, se, stat, df, p_value, ci_lo, ci_hi, n, n_clusters,
    n_clusters_firm, fallback (header)."""
    v = float(cov["V"][j, j])
    fallback = v <= 0
    if fallback:
        v = max(float(cov["V_a"][j, j]), float(cov["V_b"][j, j]) if cov["V_b"] is not None else 0.0)
    est, se, df = float(f["b"][j]), float(np.sqrt(v)), cov["df"]
    t = est / se if se > 0 else np.nan
    q = stats.t.ppf(0.975, df)
    return {"estimate": est, "se": se, "stat": t, "df": df,
            "p_value": float(2 * stats.t.sf(abs(t), df)) if se > 0 else np.nan,
            "ci_lo": est - q * se, "ci_hi": est + q * se, "n": f["n"], "n_clusters": cov["g_a"],
            "n_clusters_firm": cov["g_b"], "fallback": bool(fallback)}


def wald_test(f: dict, cov: dict, R: np.ndarray, r: np.ndarray) -> dict:
    """The Wald F row of R b = r: stat (F), df (denominator), df_num (q), p_value, n,
    n_clusters, n_clusters_firm, fallback (header)."""
    R, r = np.atleast_2d(np.asarray(R, float)), np.asarray(r, float)
    q = R.shape[0]
    block = R @ cov["V"] @ R.T
    fallback = bool(np.linalg.eigvalsh(block).min() <= 0)
    if fallback:
        cands = [cov["V_a"]] + ([cov["V_b"]] if cov["V_b"] is not None else [])
        block = max((R @ c @ R.T for c in cands), key=lambda m: float(np.trace(m)))
    d = R @ f["b"] - r
    F = float(d @ np.linalg.solve(block, d)) / q
    df = cov["df"]
    return {"stat": F, "df": df, "df_num": float(q), "p_value": float(stats.f.sf(F, q, df)), "n": f["n"],
            "n_clusters": cov["g_a"], "n_clusters_firm": cov["g_b"], "fallback": fallback}
