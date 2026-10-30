# =============================================================================
# invariants.py — The `results` invariant on the reference distribution
# (data model §3.13; ADR 0005 §5, gate G1's reference-distribution check).
#
# The schema registry attaches it to the `results` table, and store.validate
# runs it on every write and every read, so no row with a wrong reference
# distribution can be stored: milestone-3 rows now, regressions (H5-H7) later.
#
# THE RULES, per row (tolerance 1e-10 on p-values, 1e-9 on the CI multiplier)
#   1. A cluster-robust t (twoway_*, cluster_*, sa_twoway_season_t, a
#      clustered ols_coef): df = min(n_clusters, n_clusters_firm) - 1 for a
#      two-way row, n_clusters - 1 for a one-way row.
#   2. A t row (those, and bmp_t, kp_ow_t, kpp_t, a `mean` row with a df):
#      p_value = 2 * P(T_df > |stat|).
#   3. A normal row (patell_z, gen_sign_z, rank_t): p_value = 2 * P(Z > |z|),
#      and no df.
#   4. A Wald row (wald, and since milestone 4 twoway_date_wald and
#      cluster_date_wald, whose df rule 1 checks like a t row's): its numerator
#      df is stored (df_num), its denominator df too, and p_value =
#      P(F(df_num, df) > stat).
#   5. A row with a CI, an se > 0 and a df: (ci_hi - estimate) / se and
#      (estimate - ci_lo) / se both equal t_{df, 0.975}. That is the CI
#      half-width on the same reference as the p-value (statsmodels' default
#      fit would use 1.960).
#   6. rad_season_p: p_value >= 2 / 2^G, the smallest p a full enumeration of
#      the 2^G sign vectors can give (G = n_clusters).
# Validation rows (family = validation) are G1's own sizes and calibration
# numbers, not tests, and are skipped.
#
# A fit left at statsmodels' default use_t=False breaks rule 2 or 4: its
# p-values are normal (chi-square for a Wald test).
# =============================================================================

import math

from scipy import stats

TWO_WAY_T = ("twoway_date_t", "twoway_season_t", "sa_twoway_season_t")
ONE_WAY_T = ("cluster_date_t", "cluster_season_t")
TWO_WAY_WALD = ("twoway_date_wald",)            # milestone 4: H7 (ADR 0005 §3)
ONE_WAY_WALD = ("cluster_date_wald",)
WALD = ("wald",) + TWO_WAY_WALD + ONE_WAY_WALD
OTHER_T = ("bmp_t", "kp_ow_t", "kpp_t")
NORMAL = ("patell_z", "gen_sign_z", "rank_t")
P_TOL, CI_TOL = 1e-10, 1e-9


def _null(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v))


def row_problems(r: dict) -> list[str]:
    """The rules this row breaks (see the header); [] if none."""
    if r.get("family") == "validation":
        return []
    st, df, p = r.get("statistic"), r.get("df"), r.get("p_value")
    out = []
    is_wald = st in WALD
    clustered = (st in TWO_WAY_T + ONE_WAY_T + TWO_WAY_WALD + ONE_WAY_WALD
                 or (st in ("ols_coef", "wald") and not _null(r.get("n_clusters"))))
    if clustered:
        g, gf = r.get("n_clusters"), r.get("n_clusters_firm")
        two = st in TWO_WAY_T + TWO_WAY_WALD or not _null(gf)
        if _null(g) or (two and _null(gf)):
            out.append(f"a clustered row without its cluster counts (n_clusters {g}, n_clusters_firm {gf})")
            return out
        want = (min(g, gf) - 1) if two else (g - 1)
        if _null(df) or df != want:
            out.append(f"df {df} != {'min(n_clusters, n_clusters_firm)' if two else 'n_clusters'} - 1 = {want}")
    is_t = (clustered and not is_wald) or st in OTHER_T or (st == "mean" and not _null(df))
    if is_t and not _null(p) and not _null(r.get("stat")) and not _null(df):
        want_p = 2.0 * stats.t.sf(abs(r["stat"]), df)
        if abs(p - want_p) > P_TOL:
            out.append(f"p_value {p} is not the two-sided t_{df} tail of {r['stat']} ({want_p})")
    if st in NORMAL and not _null(p):
        if not _null(df):
            out.append(f"{st} is a normal statistic but has df {df}")
        want_p = 2.0 * stats.norm.sf(abs(r["stat"]))
        if abs(p - want_p) > P_TOL:
            out.append(f"p_value {p} is not the two-sided normal tail of {r['stat']} ({want_p})")
    if is_wald:
        dn = r.get("df_num")
        if _null(dn):
            out.append("a Wald row without its numerator df (df_num)")
        elif _null(df):
            out.append("a Wald row without its denominator df")
        elif not _null(p) and abs(p - stats.f.sf(r["stat"], dn, df)) > P_TOL:
            out.append(f"p_value {p} is not the F({dn}, {df}) tail of {r['stat']}")
    se, est, lo, hi = r.get("se"), r.get("estimate"), r.get("ci_lo"), r.get("ci_hi")
    if not any(_null(v) for v in (se, est, lo, hi, df)) and se > 0:
        q = stats.t.ppf(0.975, df)
        for name, mult in (("ci_hi", (hi - est) / se), ("ci_lo", (est - lo) / se)):
            if abs(mult - q) > CI_TOL * max(1.0, q):
                out.append(f"{name} is {mult} se from the estimate, not t_{df},0.975 = {q}")
    if st == "rad_season_p" and not _null(p):
        g = r.get("n_clusters")
        if _null(g) or p < 2.0 / 2 ** g - 1e-12:
            out.append(f"rad_season_p {p} is below the enumeration floor 2/2^G (G = {g})")
    return out


def results_reference(df) -> list[str]:
    """Every rule broken by any row of a results DataFrame, with its result_id."""
    out = []
    for r in df.to_dict("records"):
        out += [f"{r.get('result_id')} ({r.get('measure')}, {r.get('statistic')}): {msg}" for msg in row_problems(r)]
    return out
