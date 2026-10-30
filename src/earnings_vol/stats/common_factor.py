# =============================================================================
# common_factor.py — Where the crush baselines' common movement sits (the
# milestone-3 open item: Pynnonen's rho-bar = 0.30 for the crush, above ADR
# 0005's warning line of about 0.2). Pure numpy: research/prototypes/
# rhobar_crush.py reads the real data and prints what these functions measure.
# Nothing here feeds a test statistic; H1's primary does not change.
#
# z is events x calendar dates: each event's standardised clean baseline
# changes (e / s_i, NaN elsewhere), as kpp_t uses them (stats/inputs.py).
#   date_contributions  per date t: n_t, sum z, sum z^2, and the cross-product
#       C_t = (sum z)^2 - sum z^2 = sum over pairs i != j of z_i z_j. Pynnonen's
#       rho-bar (eq. 32) is sum_t C_t / sum_t n_t (n_t - 1) (eventtests.pynnonen_rhobar).
#   loo_factor          per cell: the mean z of the OTHER firms on that date,
#       within the same group when groups are given (a sector factor), NaN when
#       no other firm is there. Leaving the event's own firm out keeps its own
#       noise out of its factor.
#   residualise         z minus a per-firm loading times the factor: the loading
#       is the through-the-origin slope over the firm's pooled cells, the
#       residuals rescaled to a mean square of 1 per event (eq. 32 assumes
#       standardised values).
# =============================================================================

import numpy as np


def date_contributions(z: np.ndarray) -> dict:
    """{"n", "sum", "sumsq", "cross", "pairs"} per date (arrays over the columns of z)."""
    ok = np.isfinite(z)
    zz = np.where(ok, z, 0.0)
    n = ok.sum(0)
    s, s2 = zz.sum(0), (zz ** 2).sum(0)
    return {"n": n, "sum": s, "sumsq": s2, "cross": s ** 2 - s2, "pairs": n * (n - 1)}


def rhobar(z: np.ndarray) -> float:
    """Pynnonen (2022) eq. 32: sum of cross-products over sum of pair counts."""
    c = date_contributions(z)
    return float(c["cross"].sum() / c["pairs"].sum()) if c["pairs"].sum() > 0 else 0.0


def loo_factor(z: np.ndarray, firm, groups=None) -> np.ndarray:
    """Per cell (i, t) with a value: the mean z at t of the rows of OTHER firms (in the same group
    when `groups` is given); NaN elsewhere or when there is none."""
    firm = np.asarray(firm, dtype=object)
    grp = np.zeros(firm.size, int) if groups is None else np.unique(np.asarray(groups, dtype=object).astype(str),
                                                                    return_inverse=True)[1]
    ok = np.isfinite(z)
    zz = np.where(ok, z, 0.0)
    out = np.full(z.shape, np.nan)
    for g in np.unique(grp):
        rows = np.flatnonzero(grp == g)
        s_g, n_g = zz[rows].sum(0), ok[rows].sum(0)
        for f in np.unique(firm[rows]):
            mine = rows[firm[rows] == f]
            s_f, n_f = zz[mine].sum(0), ok[mine].sum(0)
            others_n = n_g - n_f
            with np.errstate(invalid="ignore", divide="ignore"):
                m = np.where(others_n > 0, (s_g - s_f) / others_n, np.nan)
            out[mine] = np.where(ok[mine], m[None, :], np.nan)
    return out


def residualise(z: np.ndarray, factor: np.ndarray, firm) -> tuple[np.ndarray, dict]:
    """(residuals, {firm: loading}): z - b_f * factor with b_f the through-the-origin slope over the
    firm's cells where both exist; each event's residuals rescaled to mean square 1. Cells without a
    factor value are NaN."""
    firm = np.asarray(firm, dtype=object)
    both = np.isfinite(z) & np.isfinite(factor)
    res = np.full(z.shape, np.nan)
    load = {}
    for f in np.unique(firm):
        rows = firm == f
        zf, ff, ok = z[rows], factor[rows], both[rows]
        den = float((ff[ok] ** 2).sum())
        b = float((zf[ok] * ff[ok]).sum() / den) if den > 0 else 0.0
        load[f] = b
        res[rows] = np.where(ok, zf - b * ff, np.nan)
    cnt = np.isfinite(res).sum(1)
    ms = np.sqrt(np.where(cnt > 0, np.nansum(res ** 2, axis=1) / np.maximum(cnt, 1), np.nan))
    with np.errstate(invalid="ignore", divide="ignore"):
        res = res / np.where(ms > 0, ms, np.nan)[:, None]
    return res, load
