# =============================================================================
# abnormal.py — Abnormal IV in logs, market-adjusted with VIX (ADR 0004 §2),
# and the one representation of every tested quantity as a weighted sum of
# abnormal changes (ADR 0005 §1). Pure functions on numpy arrays.
#
# THE WINDOW MATRIX
#   N events in rows, the 71 sessions rel_day -60 .. +10 in columns (column
#   j = rel_day + 60, so consecutive columns are consecutive sessions):
#     X     ln cm30_iv, NaN where the session is not usable (no ok snapshot,
#           or no cm30_iv)
#     M     ln VIX on the same sessions
#     inB   the clean baseline B_i (ADR 0004 §1)
#   The production run (panel/run.py) and gate G1 (stats/g1.py) both pass
#   their matrices through these same functions.
#
# THE FORMULAS (ADR 0004 §2), for event i of security s
#   mu_i   = mean of X over B_i          mu^m_i = mean of M over B_i
#   beta_s = sum dX dM / sum dM^2, no intercept, over the clean one-session
#            baseline changes (both ends in B) of ALL of s's events whose
#            baseline passes the 20/15 minimum (window.measures passes that
#            mask), each calendar date once
#   e_t    = dX_t - beta_s dM_t            (abnormal one-session change)
#   ALIV_t = (X_t - mu_i) - beta_s (M_t - mu^m_i)   (abnormal log IV)
#   ALIV0_t = X_t - mu_i                            (mean-adjusted twin)
#   s_i    = sd (ddof 1) of e over the clean baseline one-session changes
#
# SPAN CHANGES (ADR 0005 §1, "Exactness, and gaps")
#   Walk the usable sessions o_0 = min B < o_1 < ... < o_K = t of [min B, t].
#   Change k is x(o_k) - x(o_{k-1}) (minus beta times the same for VIX), with
#   weight n(o_k)/|B|, n(o) = the number of baseline sessions before o. Then
#     ALIV_t = sum_k n(o_k)/|B| * span change k        exactly,
#   because x_t - x_u telescopes over the changes after u, and B holds usable
#   sessions only. On the one-session grid a span change puts its weight on
#   every session it spans, so one weight vector a_i serves the value and its
#   variance s_i^2 a' R a.
#   Worked: B = {0, 1, 3}, usable {0, 1, 3, 4, 6}, t = 6 (sessions 2 and 5
#   unobserved). Changes 0->1 (n = 1), 1->3 (n = 2), 3->4 (n = 3),
#   4->6 (n = 3), each over |B| = 3: weights 1/3, 2/3, 1, 1. With x = 0, 1,
#   ., 4, 2, ., 5: 1/3*1 + 2/3*3 + 1*(-2) + 1*3 = 10/3 = x_6 - mean(0, 1, 4)
#   = 5 - 5/3.
#
# R-HAT (ADR 0005 §1, "R-hat, exactly")
#   z = e / s_i on the clean baseline one-session changes of each event;
#   rho_k = sum_i sum_t z_t z_{t-k} / sum_i sum_t z_t^2, k = 1 .. 10, over
#   pairs of clean changes of the same event; uncentred (no drift in the
#   model). If 1 + 2 sum rho_k cos(k lam) < 0 anywhere on 512 points of
#   [0, pi], taper by (1 - k/11) and check again; still negative: R = I and
#   the flag rhat_identity.
# =============================================================================

import math

import numpy as np

REL_LO, REL_HI = -60, 10
REL_DAYS = np.arange(REL_LO, REL_HI + 1)


def col(rel_day: int) -> int:
    """The column of a rel_day in the window matrix (-60 -> 0, -1 -> 59, 0 -> 60)."""
    return rel_day - REL_LO


def one_session_changes(X: np.ndarray) -> np.ndarray:
    """dX[:, j] = X[:, j] - X[:, j-1]; NaN in column 0 and wherever an end is NaN."""
    d = np.full_like(X, np.nan, dtype=float)
    d[:, 1:] = X[:, 1:] - X[:, :-1]
    return d


def clean_changes(in_baseline: np.ndarray) -> np.ndarray:
    """C[:, j]: the one-session change into column j has both ends in the baseline."""
    c = np.zeros_like(in_baseline, dtype=bool)
    c[:, 1:] = in_baseline[:, 1:] & in_baseline[:, :-1]
    return c


def beta_by_security(security: np.ndarray, session: np.ndarray, dX: np.ndarray, dM: np.ndarray,
                     clean: np.ndarray) -> dict:
    """{security: (beta, n)}: the OLS slope through the origin of dX on dM over the clean
    one-session baseline changes of all of a security's events, each (security, session) once.

    `security` has one entry per row (event); `session` is the N x W matrix of session
    indices; dX, dM and clean are N x W. A security with no usable change gets (None, 0).
    """
    rows, cols = np.nonzero(clean & np.isfinite(dX) & np.isfinite(dM))
    seen: dict = {}
    for r, c in zip(rows, cols):
        seen.setdefault((security[r], int(session[r, c])), (dX[r, c], dM[r, c]))
    sxy: dict = {}
    for (sec, _), (x, m) in seen.items():
        a = sxy.setdefault(sec, [0.0, 0.0, 0])
        a[0] += x * m
        a[1] += m * m
        a[2] += 1
    out = {}
    for sec in dict.fromkeys(security.tolist()):
        a = sxy.get(sec)
        out[sec] = (a[0] / a[1], a[2]) if a and a[1] > 0 else (None, a[2] if a else 0)
    return out


def baseline_mean(V: np.ndarray, in_baseline: np.ndarray) -> np.ndarray:
    """Row means of V over the baseline (NaN for an empty baseline)."""
    n = in_baseline.sum(1)
    s = np.where(in_baseline, V, 0.0).sum(1)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(n > 0, s / np.maximum(n, 1), np.nan)


def aliv(X: np.ndarray, M: np.ndarray, in_baseline: np.ndarray, beta: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(ALIV, ALIV0): market- and mean-adjusted abnormal log IV, N x W (ADR 0004 §2)."""
    mu = baseline_mean(X, in_baseline)[:, None]
    mu_m = baseline_mean(M, in_baseline)[:, None]
    a0 = X - mu
    return a0 - beta[:, None] * (M - mu_m), a0


def abnormal_changes(X: np.ndarray, M: np.ndarray, beta: np.ndarray) -> np.ndarray:
    """e = dX - beta dM on the one-session grid (NaN where either change is undefined)."""
    return one_session_changes(X) - beta[:, None] * one_session_changes(M)


def baseline_sd(e: np.ndarray, clean: np.ndarray) -> np.ndarray:
    """s_i: sd (ddof = 1) of e over the clean one-session baseline changes (NaN below 2)."""
    ok = clean & np.isfinite(e)
    n = ok.sum(1)
    v = np.where(ok, e, 0.0)
    m = v.sum(1) / np.maximum(n, 1)
    ss = np.where(ok, (e - m[:, None]) ** 2, 0.0).sum(1)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(n >= 2, np.sqrt(ss / np.maximum(n - 1, 1)), np.nan)


def span_changes(in_baseline: np.ndarray, usable: np.ndarray, target: int) -> list[tuple[int, int, float]]:
    """[(start column, end column, weight)] of the span-change walk from min B to `target`
    (see the header). One event's rows of in_baseline and usable; `target` a usable column
    after the baseline. Empty when the baseline is empty."""
    b = np.flatnonzero(in_baseline)
    if b.size == 0:
        return []
    if not usable[target]:
        raise ValueError(f"target column {target} is not usable")
    walk = [c for c in range(int(b[0]), target + 1) if usable[c]]
    n_before = np.cumsum(in_baseline) - in_baseline       # baseline sessions strictly before each column
    return [(walk[k - 1], walk[k], n_before[walk[k]] / b.size) for k in range(1, len(walk))]


def grid_weights(changes: list[tuple[int, int, float]], width: int) -> np.ndarray:
    """The weights a on the one-session grid: a span change (s, e] puts its weight on
    every column s+1 .. e."""
    a = np.zeros(width)
    for s, e, w in changes:
        a[s + 1:e + 1] = w
    return a


def span_value(changes: list[tuple[int, int, float]], x: np.ndarray, m: np.ndarray, beta: float) -> float:
    """sum_k w_k ((x_e - x_s) - beta (m_e - m_s)) over the span changes of one event."""
    return float(sum(w * ((x[e] - x[s]) - beta * (m[e] - m[s])) for s, e, w in changes))


def lag_products(a: np.ndarray, max_lag: int) -> np.ndarray:
    """Q[:, k] = sum_t a_t a_{t-k} for k = 0 .. max_lag (a is N x W)."""
    q = np.zeros((a.shape[0], max_lag + 1))
    q[:, 0] = (a * a).sum(1)
    for k in range(1, max_lag + 1):
        q[:, k] = (a[:, k:] * a[:, :-k]).sum(1)
    return q


def quad_form(q: np.ndarray, rho: np.ndarray) -> np.ndarray:
    """a' R a = Q_0 + 2 sum_k rho_k Q_k (R Toeplitz with R_tu = rho_|t-u|, rho_k = 0 past the list)."""
    return q[:, 0] + 2.0 * (q[:, 1:len(rho) + 1] * rho[None, :]).sum(1)


def rhat_raw(z: np.ndarray, ok: np.ndarray, max_lag: int) -> np.ndarray:
    """Pooled uncentred autocorrelations rho_1 .. rho_max_lag of z over the entries `ok`."""
    zz = np.where(ok, z, 0.0)
    den = (zz * zz).sum()
    if den <= 0:
        return np.zeros(max_lag)
    return np.array([(zz[:, k:] * zz[:, :-k]).sum() / den for k in range(1, max_lag + 1)])


def spectral_min(rho: np.ndarray, grid: int) -> float:
    """min over lam in [0, pi] (grid points) of 1 + 2 sum_k rho_k cos(k lam)."""
    lam = np.linspace(0.0, math.pi, grid)
    k = np.arange(1, rho.size + 1)
    return float((1.0 + 2.0 * (rho[:, None] * np.cos(np.outer(k, lam))).sum(0)).min())


def rhat_psd(rho: np.ndarray, grid: int = 512) -> tuple[np.ndarray, str]:
    """(rho to use, flag): rho itself, the Bartlett taper (1 - k/(L+1)), or zeros and
    'rhat_identity' when both fail the spectral check."""
    if spectral_min(rho, grid) >= 0:
        return rho, ""
    taper = rho * (1.0 - np.arange(1, rho.size + 1) / (rho.size + 1))
    if spectral_min(taper, grid) >= 0:
        return taper, "rhat_bartlett"
    return np.zeros_like(rho), "rhat_identity"


def rhat(e: np.ndarray, s: np.ndarray, clean: np.ndarray, max_lag: int = 10,
         grid: int = 512) -> tuple[np.ndarray, str]:
    """R-hat of ADR 0005 §1 from the abnormal changes e (N x W), the scales s and the clean
    one-session baseline changes. Rows with a NaN scale are left out."""
    ok = clean & np.isfinite(e) & np.isfinite(s)[:, None]
    with np.errstate(invalid="ignore", divide="ignore"):
        z = e / s[:, None]
    return rhat_psd(rhat_raw(z, ok, max_lag), grid)
