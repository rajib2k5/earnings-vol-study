# =============================================================================
# eventtests.py — The standardised and nonparametric robustness statistics of
# ADR 0005 §2c-§2e and §2h. They test the PRECISION-weighted mean (BMP's
# estimand) or a sign share / mean rank, not the equal-weighted mean of
# H1-H4, and are labelled so in `results.estimand`.
#
#   BMP     t = mean(SA) / (sd(SA) / sqrt N), t_{N-1}
#   KP_OW   t_BMP * sqrt((1 - r) / (1 + (N-1) r)),
#           r = max(0, mean over pairs i<j of nu_ij * rho_ij)          (§2e)
#           nu_ij = 1[same day 0] for a one-session measure; rho_ij the
#           Pearson correlation of z_i and z_j over their shared clean
#           baseline dates (at least 20; else the mean rho of same-sector
#           pairs that have 20, else of all such pairs)
#   KPP     t_BMP * sqrt((1 - v) / (1 + (N-1) v)), v = nubar * rhobar, no clamp
#           nubar = mean over pairs of a_i'a_j / sqrt(a_i'a_i a_j'a_j) on the
#           calendar axis; rhobar = Pynnonen (2022) eq. 32:
#           sum_t sum_{i != j} z_it z_jt / sum_t n_t (n_t - 1) over clean dates
#   Both KP rows use t_{N-1}, as BMP; their se is BMP's divided by the same
#   factor, so the CI sits on the reference of the p-value.
#   PATELL  sum SA_i / sqrt(sum d_i/(d_i - 2)), d_i = L_i - 1, normal (§2c)
#   SIGN    (w - N p) / sqrt(N p (1-p)), p = pooled share of baseline changes
#           below 0, w = events with A_i < 0, normal (Cowan 1992)
#   RANK    sum U_i / sqrt(sum L_i / (12 (L_i + 2))), U_i = K_i/(L_i + 2) - 1/2,
#           K_i the rank of A_i among its L_i baseline changes and itself
#           (average ranks for ties), normal (Corrado 1989; Corrado & Zivney)
#
# z (N x T) holds each event's standardised clean baseline changes on the
# calendar axis (NaN elsewhere); it is the input of both correlation terms.
# =============================================================================

import numpy as np
from scipy import stats


def _t_row(est: float, se: float, t: float, df: float, n: int) -> dict:
    q = stats.t.ppf(0.975, df)
    return {"estimate": est, "se": se, "stat": t, "df": float(df), "p_value": float(2 * stats.t.sf(abs(t), df)),
            "ci_lo": est - q * se, "ci_hi": est + q * se, "n": n}


def bmp(sa: np.ndarray) -> dict:
    """BMP t of the mean of the standardised values SA_i."""
    sa = np.asarray(sa, float)
    n = sa.size
    se = float(sa.std(ddof=1) / np.sqrt(n))
    return _t_row(float(sa.mean()), se, float(sa.mean() / se), n - 1, n)


def kp_adjust(sa: np.ndarray, r: float) -> dict:
    """BMP t multiplied by sqrt((1 - r)/(1 + (N - 1) r)); `rbar` holds r."""
    b = bmp(sa)
    n = b["n"]
    f = np.sqrt((1 - r) / (1 + (n - 1) * r))
    out = _t_row(b["estimate"], b["se"] / f, b["stat"] * f, n - 1, n)
    out["rbar"] = float(r)
    return out


def pair_correlations(z: np.ndarray, min_shared: int) -> tuple[np.ndarray, np.ndarray]:
    """(rho, ok): Pearson correlations of the rows of z over their shared non-NaN columns,
    and whether at least `min_shared` columns are shared (diagonal False)."""
    m = np.isfinite(z).astype(float)
    zz = np.nan_to_num(z)
    n_sh = m @ m.T
    sx = zz @ m.T
    sxx = (zz ** 2) @ m.T
    sxy = zz @ zz.T
    with np.errstate(invalid="ignore", divide="ignore"):
        cov = sxy / n_sh - sx * sx.T / n_sh ** 2
        vx = sxx / n_sh - (sx / n_sh) ** 2
        rho = cov / np.sqrt(vx * vx.T)
    ok = (n_sh >= min_shared) & np.isfinite(rho) & ~np.eye(z.shape[0], dtype=bool)
    return rho, ok


def kp_ow_rbar(z: np.ndarray, nu: np.ndarray, sector: np.ndarray, min_shared: int) -> float:
    """r of kp_ow_t: max(0, mean over pairs i<j of nu_ij rho_ij), with the fallbacks of §2e."""
    n = z.shape[0]
    rho, ok = pair_correlations(z, min_shared)
    same = np.asarray(sector)[:, None] == np.asarray(sector)[None, :]
    m_all = float(rho[ok].mean()) if ok.any() else 0.0
    m_sec = float(rho[ok & same].mean()) if (ok & same).any() else m_all
    filled = np.where(ok, rho, np.where(same, m_sec, m_all))
    iu = np.triu_indices(n, 1)
    return max(0.0, float((nu[iu] * filled[iu]).mean()))


def overlap_nu(a: np.ndarray) -> np.ndarray:
    """nu_ij = a_i'a_j / sqrt(a_i'a_i a_j'a_j) for weight rows on the calendar axis."""
    g = a @ a.T
    d = np.sqrt(np.diag(g))
    with np.errstate(invalid="ignore", divide="ignore"):
        return g / np.outer(d, d)


def pynnonen_rhobar(z: np.ndarray) -> float:
    """Pynnonen (2022) eq. 32 on the standardised baseline changes, clustered by calendar date."""
    zz = np.nan_to_num(z)
    nt = np.isfinite(z).sum(0)
    den = (nt * (nt - 1)).sum()
    return float(((zz.sum(0) ** 2 - (zz ** 2).sum(0)).sum()) / den) if den > 0 else 0.0


def kpp(sa: np.ndarray, a: np.ndarray, z: np.ndarray) -> dict:
    """kpp_t (see the header). `rbar` holds nubar * rhobar."""
    n = sa.size
    nu = overlap_nu(a)
    iu = np.triu_indices(n, 1)
    return kp_adjust(sa, float(np.nanmean(nu[iu])) * pynnonen_rhobar(z))


def patell(sa: np.ndarray, n_changes: np.ndarray) -> dict:
    """Patell Z (normal) of the standardised one-session values; d_i = L_i - 1."""
    d = np.asarray(n_changes, float) - 1.0
    z = float(np.sum(sa) / np.sqrt(np.sum(d / (d - 2.0))))
    return {"estimate": float(np.mean(sa)), "stat": z, "p_value": float(2 * stats.norm.sf(abs(z))), "n": int(sa.size)}


def gen_sign(A: np.ndarray, baseline: list[np.ndarray]) -> dict:
    """Generalised sign Z (normal); `estimate` is the share of events with A_i < 0."""
    pooled = np.concatenate(baseline)
    p = float((pooled < 0).mean())
    n = A.size
    w = float((np.asarray(A) < 0).sum())
    z = (w - n * p) / np.sqrt(n * p * (1 - p))
    return {"estimate": w / n, "stat": float(z), "p_value": float(2 * stats.norm.sf(abs(z))), "n": n}


def rank_test(A: np.ndarray, baseline: list[np.ndarray]) -> dict:
    """Corrado-Zivney rank T (normal); `estimate` is the mean U_i."""
    u, var = [], []
    for a, b in zip(A, baseline):
        allv = np.concatenate([b, [a]])
        k = stats.rankdata(allv)[-1]
        L = b.size
        u.append(k / (L + 2) - 0.5)
        var.append(L / (12.0 * (L + 2)))
    t = float(np.sum(u) / np.sqrt(np.sum(var)))
    return {"estimate": float(np.mean(u)), "stat": t, "p_value": float(2 * stats.norm.sf(abs(t))), "n": len(u)}
