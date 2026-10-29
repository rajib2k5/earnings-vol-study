# =============================================================================
# suite.py — Which statistics each tested quantity gets (ADR 0005 §4), on
# one event set. The production run (stats/run.py) and gate G1 (stats/g1.py)
# both call these two functions, so G1 sizes exactly the code that makes the
# reported rows.
#
# ONE-SESSION MEASURES (CRUSH, DSIGMA_D; H1, H4)
#   primary     twoway_date_t      day-0 date x firm
#   robustness  cluster_date_t, kp_ow_t, kpp_t, bmp_t, patell_z (CRUSH only),
#               gen_sign_z, rank_t
# RAMPS (RUNUP, PERSIST_h; H2, H3)
#   primary     twoway_season_t    merged season x firm; rad_season_p instead
#               when the merged seasons are unbalanced (largest > 1.5 x
#               smallest), whatever G1 says (§2b, §5)
#   robustness  cluster_season_t, rad_season_p (or twoway_season_t when rad is
#               primary), sa_twoway_season_t
#   With fewer than 5 season clusters a ramp gets its estimate only (§2b).
# Each function returns {statistic: row}, a row being the dict of results
# columns it fills, plus "primary": the name of the primary statistic.
# =============================================================================

import numpy as np

from earnings_vol.stats import clustering, eventtests

ESTIMAND = {"twoway_date_t": "equal_weighted", "twoway_season_t": "equal_weighted",
            "cluster_date_t": "equal_weighted", "cluster_season_t": "equal_weighted",
            "rad_season_p": "equal_weighted", "sa_twoway_season_t": "precision_weighted",
            "bmp_t": "precision_weighted", "kp_ow_t": "precision_weighted", "kpp_t": "precision_weighted",
            "patell_z": "precision_weighted", "gen_sign_z": None, "rank_t": None, "mean": "equal_weighted"}


def one_session(A: np.ndarray, day0, firm, *, sa=None, z=None, a_cal=None, sector=None, n_changes=None,
                baseline=None, patell: bool = False, min_shared: int = 20, robust: bool = True) -> dict:
    """The rows of a one-session measure (see the header). Robustness rows need the
    standardised inputs: sa (SA_i), z (N x T standardised clean baseline changes on the
    calendar axis), a_cal (N x T weights on the calendar axis), sector, n_changes (L_i)
    and baseline (each event's baseline changes, for the sign and rank tests)."""
    out = {"twoway_date_t": clustering.twoway(A, day0, firm), "primary": "twoway_date_t"}
    if not robust:
        return out
    out["cluster_date_t"] = clustering.oneway(A, day0)
    if sa is not None:
        d0 = np.asarray(day0)
        nu = (d0[:, None] == d0[None, :]).astype(float)
        out["bmp_t"] = eventtests.bmp(sa)
        out["kp_ow_t"] = eventtests.kp_adjust(sa, eventtests.kp_ow_rbar(z, nu, sector, min_shared))
        out["kpp_t"] = eventtests.kpp(sa, a_cal, z)
        if patell:
            out["patell_z"] = eventtests.patell(sa, n_changes)
    if baseline is not None:
        out["gen_sign_z"] = eventtests.gen_sign(A, baseline)
        out["rank_t"] = eventtests.rank_test(A, baseline)
    return out


def ramp(A: np.ndarray, season, day0_ordinal, firm, *, sa=None, min_events: int = 10, ratio: float = 1.5,
         min_clusters: int = 5, robust: bool = True) -> dict:
    """The rows of a ramp measure (see the header); `merged` holds the merged seasons and
    `unbalanced` the rule's verdict. With fewer than min_clusters seasons only a `mean` row."""
    merged = clustering.merge_small_seasons(season, day0_ordinal, min_events)
    g = len(set(merged.tolist()))
    A = np.asarray(A, float)
    if g < min_clusters:
        return {"mean": {"estimate": float(A.mean()), "n": int(A.size), "n_clusters": g}, "primary": "mean",
                "merged": merged, "unbalanced": None}
    unb = clustering.unbalanced(merged, ratio)
    out = {"twoway_season_t": clustering.twoway(A, merged, firm),
           "primary": "rad_season_p" if unb else "twoway_season_t", "merged": merged, "unbalanced": unb}
    if unb or robust:
        out["rad_season_p"] = clustering.rademacher_p(A, merged)
    if robust:
        out["cluster_season_t"] = clustering.oneway(A, merged)
        if sa is not None:
            out["sa_twoway_season_t"] = clustering.twoway(sa, merged, firm)
    return out
