# =============================================================================
# drivers.py — Milestone 4: what drives the crush, and implied against
# realised moves (ADR 0005 §3, §4). Pure: the stats Frame in, `results` rows
# out (family "regression"); stats/regression.py does the algebra.
#
# THE CRUSH REGRESSION (model crush_drivers, daily primary sample: the events
# of H1's set, eligible_crush, with every regressor present)
#   CRUSH_i = a + b1 z(|SURP|) + b2 z(ln sigma_d(-1)) + b3 z(SLOPE) + b4 z(SIZE)
#             + sector FE + season FE + e_i
#   |SURP| = abs_surprise_scaled_w, sigma_d(-1) = sigma_d_m1, SLOPE = ts_slope_m1,
#   SIZE = ln_mcap_yf; z over the model's rows. CRUSH is crush_cboe
#   (market-adjusted); its mean-adjusted twin uses crush_mean_adj.
#   H5: b1 = 0, H6: b2 = 0. Primary: the two-way day-0 date x firm t with
#   min(G) - 1 df (statistic twoway_date_t), role primary while the hypothesis
#   is in the binding Holm family (results.binding_family: H5-H7 stay in it
#   whatever G1's regression size check says; the export prints that size and
#   that a rejection would not be trusted; fix R1 after the milestone-4
#   review); robustness: the one-way date t
#   (cluster_date_t) and the mean-adjusted twin's two-way t. SLOPE and SIZE
#   are exploratory, with the primary statistic.
# IMPLIED VS REALISED (model implied_realised; ADR 0005 §3, ADR 0003 §c Units)
#   r0^2 = a + b (E + sigma_d^2/252) + u over the primary sample with a
#   realised move (realized_ret_0), E at day -1 (evar_m1, every sign) and
#   sigma_d_m1. H7: a = 0 and b = 1, a Wald F with q = 2 against F(2, min(G) - 1),
#   two-way date x firm (twoway_date_wald); robustness: one-way date
#   (cluster_date_wald). The coefficient rows test a = 0 and b = 1 one at a
#   time (stat = (b - 1)/se for b), exploratory. The share of events with
#   |r0| > implied_abs_move_total_m1 (E > 0) is compared with 0.425, the
#   benchmark for a normal move (not 0.5), as a two-way t of the share.
# EXPLORATORY MODELS (ADR 0005 §3 variants; BH within the sample's regression
#   rows): DSIGMA_D on the same regressors; ln cm30(-1) for the prior level
#   (mechanically linked); |SUE_hist|, the |dispersion-scaled surprise| and the
#   signed surprise; firm FE in place of sector FE; VIX-tercile dummies in
#   place of season FE with |SURP| x tercile slopes; the coarse sample; E at
#   day -2 for H7.
# Fixed-effect coefficients never become rows (data model §2.1). The model's
#   R^2 is a row of its own (statistic r2, no test).
# =============================================================================

from dataclasses import dataclass

import numpy as np
from scipy import stats

from earnings_vol.stats import clustering, inputs, regression
from earnings_vol.stats.g1_drivers import TWIN_KEY   # G1's key for the twin's size
from earnings_vol.stats.results import MEASURE_NAME, row, withhold

H7_BENCHMARK = 0.425          # P(|r| > sqrt(2/pi) sqrt(v)) for r ~ N(0, v): 2 (1 - Phi(0.798))
HYP_TERMS = {"H5": "abs_surprise", "H6": "ln_sigma_d"}
HYPOTHESES = ("H5", "H6", "H7")    # the hypotheses with rows here (results.require_verdicts)
LABEL = {"abs_surprise": "|surprise| / price (winsorised)", "ln_sigma_d": "ln sigma_d at day -1",
         "slope": "term-structure slope ln(sigma_T1 / sigma_T2) at day -1", "size": "ln market cap at day -1",
         "ln_cm30": "ln cm30 at day -1 (mechanically linked to the crush)", "abs_sue": "|SUE_hist|",
         "abs_disp": "|dispersion-scaled surprise| (winsorised)", "surprise": "signed surprise / price (winsorised)",
         "abs_surprise_x_mid": "|surprise| x mid-VIX tercile", "abs_surprise_x_high": "|surprise| x high-VIX tercile",
         "a": "intercept a (H0: a = 0)", "b": "slope b (H0: b = 1)", "exceed_share": "share |r0| > implied move"}
# Raw values of each regressor (before winsorising inside the model and z-scoring).
RAW = {"abs_surprise": lambda ev: ev["abs_surprise_scaled_w"].to_numpy(float),
       "ln_sigma_d": lambda ev: _log(ev["sigma_d_m1"].to_numpy(float)),
       "slope": lambda ev: ev["ts_slope_m1"].to_numpy(float),
       "size": lambda ev: ev["ln_mcap_yf"].to_numpy(float),
       "ln_cm30": lambda ev: _log(ev["cm30_m1"].to_numpy(float)),
       "abs_sue": lambda ev: np.abs(ev["sue_hist"].to_numpy(float)),
       "abs_disp": lambda ev: np.abs(ev["surprise_disp"].to_numpy(float)),
       "surprise": lambda ev: ev["surprise_scaled"].to_numpy(float)}
WINSOR_IN_MODEL = ("abs_disp", "surprise")    # |SURP| is already winsorised in event_measures
FE_COLUMN = {"sector": "gics_sector", "season": "season", "firm": "security_id", "vix_regime": "vix_regime"}
BASE_TERMS = ("abs_surprise", "ln_sigma_d", "slope", "size")
MIN_DF = 10        # a model needs at least this many events beyond its columns (else no rows: mixed)


def _log(v):
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.log(np.where(v > 0, v, np.nan))


@dataclass(frozen=True)
class Spec:
    """One regression: its id, outcome (crush or dsigma_d), adjustment, named terms, fixed
    effects, sample, and the VIX terciles whose |SURP| slope differs (crush_vix)."""

    model_id: str
    y: str
    adjustment: str
    terms: tuple
    fe: tuple
    sample: str = "daily"
    interact: tuple = ()


PRIMARY = Spec("crush_drivers", "crush", "market", BASE_TERMS, ("sector", "season"))
TWIN = Spec("crush_drivers", "crush", "mean", BASE_TERMS, ("sector", "season"))
EXPLORATORY = (
    Spec("dsigma_d_drivers", "dsigma_d", "market", BASE_TERMS, ("sector", "season")),
    Spec("crush_prior_cm30", "crush", "market", ("abs_surprise", "ln_cm30", "slope", "size"), ("sector", "season")),
    Spec("crush_sue", "crush", "market", ("abs_sue", "ln_sigma_d", "slope", "size"), ("sector", "season")),
    Spec("crush_disp", "crush", "market", ("abs_disp", "ln_sigma_d", "slope", "size"), ("sector", "season")),
    Spec("crush_signed", "crush", "market", ("abs_surprise", "surprise", "ln_sigma_d", "slope", "size"),
         ("sector", "season")),
    Spec("crush_firm_fe", "crush", "market", BASE_TERMS, ("firm", "season")),
    Spec("crush_vix", "crush", "market", BASE_TERMS, ("sector", "vix_regime"), interact=("mid", "high")),
    Spec("crush_drivers", "crush", "market", BASE_TERMS, ("sector", "season"), sample="coarse"),
)


def winsorise(v: np.ndarray, q: tuple) -> np.ndarray:
    """v clipped to its [q0, q1] quantiles (numpy's linear rule)."""
    lo, hi = np.quantile(v, q[0]), np.quantile(v, q[1])
    return np.clip(v, lo, hi)


def model_inputs(f: inputs.Frame, spec: Spec, winsor: tuple) -> dict:
    """{"rows", "y", "X", "names", "date", "firm"}: the complete cases of the model's event set
    (H1's set for the crush, H4's for DSIGMA_D, in spec.sample), the outcome, the design matrix
    [1, z-terms, |SURP| x tercile, FE dummies] and the cluster labels."""
    rows = inputs.event_set(f, spec.y, spec.sample)
    y = inputs.values(f, rows, spec.y, spec.adjustment)
    ev = f.ev.iloc[rows]
    raw = {t: RAW[t](ev) for t in spec.terms}
    keep = np.isfinite(y) & np.all([np.isfinite(v) for v in raw.values()], axis=0)
    for fe in spec.fe:
        keep &= ev[FE_COLUMN[fe]].notna().to_numpy()
    rows, y, ev = rows[keep], y[keep], ev[keep]
    if rows.size < len(spec.terms) + 3:
        return {"rows": rows, "y": y, "X": None, "names": [], "date": None, "firm": None}
    cols, names = [np.ones(rows.size)], ["const"]
    z = {}
    for t in spec.terms:
        v = raw[t][keep]
        z[t] = regression.zscore(winsorise(v, winsor) if t in WINSOR_IN_MODEL else v)
        cols.append(z[t])
        names.append(t)
    for lvl in spec.interact:
        cols.append(z[spec.terms[0]] * (ev["vix_regime"].to_numpy(object) == lvl))
        names.append(f"{spec.terms[0]}_x_{lvl}")
    for fe in spec.fe:
        d, n = regression.dummies(ev[FE_COLUMN[fe]].to_numpy(object), fe)
        cols += list(d.T)
        names += n
    return {"rows": rows, "y": y, "X": np.column_stack(cols), "names": names,
            "date": ev["day0_session"].astype(str).to_numpy(object), "firm": ev["security_id"].to_numpy(object)}


def h7_inputs(f: inputs.Frame, evar: str = "evar_m1", floor: float | None = None) -> dict:
    """{"rows", "y", "x", "X", "date", "firm", "n_floored"}: the primary sample's events with
    realized_ret_0, `evar` and sigma_d_m1; y = r0^2, x = E + sigma_d_m1^2/252 (ADR 0003 §c: the
    stored sigma_d is annualised; without /252 the second term is 252 times too big). `floor`,
    when given, raises x to at least floor (G1's simulated null only)."""
    rows = inputs.event_set(f, "crush", "daily")
    ev = f.ev.iloc[rows]
    r0, e, sd = (ev[c].to_numpy(float) for c in ("realized_ret_0", evar, "sigma_d_m1"))
    keep = np.isfinite(r0) & np.isfinite(e) & np.isfinite(sd)
    x = implied_variance(e[keep], sd[keep])
    n_floored = 0
    if floor is not None:
        n_floored = int((x < floor).sum())
        x = np.maximum(x, floor)
    ev = ev[keep]
    return {"rows": rows[keep], "y": r0[keep] ** 2, "x": x, "X": np.column_stack([np.ones(x.size), x]),
            "date": ev["day0_session"].astype(str).to_numpy(object), "firm": ev["security_id"].to_numpy(object),
            "n_floored": n_floored}


def implied_variance(evar: np.ndarray, sigma_d_ann: np.ndarray) -> np.ndarray:
    """E + sigma_d^2 per session = evar + sigma_d_ann^2 / 252 (both in squared-log-return units)."""
    return np.asarray(evar, float) + np.asarray(sigma_d_ann, float) ** 2 / 252.0


def fit_model(m: dict, two_way: bool = True) -> tuple[dict, dict]:
    """(fit, covariance): OLS and the two-way date x firm (or one-way date) covariance."""
    fit = regression.fit(m["y"], m["X"])
    return fit, regression.covariance(fit, m["X"], m["date"], m["firm"] if two_way else None)


def shift_null(res: dict, null: float) -> dict:
    """A coefficient row tested against `null` instead of 0: stat = (estimate - null)/se and its
    two-sided p on the same df (the CI does not move)."""
    t = (res["estimate"] - null) / res["se"]
    return dict(res, stat=float(t), p_value=float(2 * stats.t.sf(abs(t), res["df"])))


def _reg_row(base: dict, statistic: str, res: dict, **kw) -> dict:
    out = dict(base, statistic=statistic, estimand=None, **kw)
    for k in ("estimate", "se", "stat", "df", "df_num", "p_value", "ci_lo", "ci_hi"):
        if k in res and res[k] is not None and np.isfinite(res[k]):
            out[k] = float(res[k])
    out["n"] = int(res["n"])
    out["n_clusters"] = int(res["n_clusters"])
    out["n_clusters_firm"] = None if res.get("n_clusters_firm") is None else int(res["n_clusters_firm"])
    return row(**out)


def _r2_row(base: dict, fit: dict, cov: dict) -> dict:
    return row(**dict(base, statistic="r2", estimand=None, role="exploratory", term=None, n=int(fit["n"]),
                      n_clusters=int(cov["g_a"]), n_clusters_firm=None if cov["g_b"] is None else int(cov["g_b"]),
                      estimate=float(fit["r2"])))


def crush_rows(f: inputs.Frame, spec: Spec, winsor: tuple, in_family: dict, common: dict, primary: bool,
               mis_sized: dict) -> list[dict]:
    """The rows of one crush-type model. For the primary model: the two-way t of every term (H5's
    and H6's role primary when in_family[h], the binding Holm family, else exploratory; read
    strictly, a missing hypothesis is an error; the others exploratory), the
    one-way date t of H5's and H6's terms (robustness; withheld when G1 finds them mis-sized), and
    R^2. For the mean-adjusted twin (spec.adjustment mean): the two-way t of H5's and H6's terms
    (robustness; withheld when G1 finds the twin's statistic, key TWIN_KEY, mis-sized). For an
    exploratory model: the two-way t of every term, and R^2."""
    m = model_inputs(f, spec, winsor)
    if m["X"] is None or m["rows"].size < m["X"].shape[1] + MIN_DF:
        return []
    fit, cov2 = fit_model(m, True)
    base = dict(family="regression", model_id=spec.model_id, measure=MEASURE_NAME[spec.y], sample=spec.sample,
                adjustment=spec.adjustment, subgroup_key="all", subgroup_value="all", **common)
    hyp_of = {t: h for h, t in HYP_TERMS.items()}
    out = []
    twin = spec.adjustment == "mean"
    if not twin:
        out.append(_r2_row(dict(base, hypothesis=None), fit, cov2))
    cov1 = regression.covariance(fit, m["X"], m["date"]) if primary else None
    for j, t in enumerate(m["names"]):
        if t == "const" or ":" in t:
            continue
        h = hyp_of.get(t) if primary else None
        if twin and h is None:
            continue
        if h is not None:
            role = "robustness" if twin else ("primary" if in_family[h] else "exploratory")
        else:
            role = "exploratory"
        r2 = _reg_row(dict(base, hypothesis=h, role=role, term=t), "twoway_date_t", regression.coef_test(fit, cov2, j))
        out.append(withhold(r2) if twin and (h, TWIN_KEY) in mis_sized else r2)
        if h is not None and not twin:
            r1 = _reg_row(dict(base, hypothesis=h, role="robustness", term=t), "cluster_date_t",
                          regression.coef_test(fit, cov1, j))
            out.append(withhold(r1) if (h, "cluster_date_t") in mis_sized else r1)
    return out


def h7_rows(f: inputs.Frame, in_family: dict, common: dict, mis_sized: dict, evar: str = "evar_m1") -> list[dict]:
    """H7's rows (evar_m1): the two-way Wald of a = 0, b = 1 (primary when in_family["H7"]), the
    one-way date Wald (robustness, withheld when mis-sized), the coefficient rows a and b and
    R^2 (exploratory). With evar_m2: model implied_realised_m2, every row exploratory."""
    m = h7_inputs(f, evar)
    fit, cov2 = fit_model(m, True)
    main = evar == "evar_m1"
    mid = "implied_realised" if main else "implied_realised_m2"
    base = dict(family="regression", model_id=mid, measure="r0_squared", sample="daily", adjustment="none",
                subgroup_key="all", subgroup_value="all", **common)
    R, r = np.eye(2), np.array([0.0, 1.0])
    out = [_r2_row(dict(base, hypothesis=None), fit, cov2)]
    role = ("primary" if in_family["H7"] else "exploratory") if main else "exploratory"
    out.append(_reg_row(dict(base, hypothesis="H7" if main else None, role=role, term="a=0,b=1"), "twoway_date_wald",
                        regression.wald_test(fit, cov2, R, r)))
    if main:
        cov1 = regression.covariance(fit, m["X"], m["date"])
        w1 = _reg_row(dict(base, hypothesis="H7", role="robustness", term="a=0,b=1"), "cluster_date_wald",
                      regression.wald_test(fit, cov1, R, r))
        out.append(withhold(w1) if ("H7", "cluster_date_wald") in mis_sized else w1)
    for j, (t, null) in enumerate((("a", 0.0), ("b", 1.0))):
        out.append(_reg_row(dict(base, hypothesis=None, role="exploratory", term=t), "twoway_date_t",
                            shift_null(regression.coef_test(fit, cov2, j), null)))
    return out


def exceed_rows(f: inputs.Frame, common: dict) -> list[dict]:
    """The share of primary-sample events with |r0| > implied_abs_move_total_m1 (E > 0 there),
    against 0.425: estimate = the share, its two-way date x firm se, stat = (share - 0.425)/se."""
    rows = inputs.event_set(f, "crush", "daily")
    ev = f.ev.iloc[rows]
    r0, iam = ev["realized_ret_0"].to_numpy(float), ev["implied_abs_move_total_m1"].to_numpy(float)
    keep = np.isfinite(r0) & np.isfinite(iam) & (ev["evar_m1"].to_numpy(float) > 0)
    ind = (np.abs(r0[keep]) > iam[keep]).astype(float)
    tw = clustering.twoway(ind, ev["day0_session"].astype(str).to_numpy(object)[keep],
                           ev["security_id"].to_numpy(object)[keep])
    res = shift_null(dict(tw), H7_BENCHMARK)
    return [_reg_row(dict(family="regression", model_id="implied_realised", measure="abs_r0_over_implied",
                          sample="daily", adjustment="none", subgroup_key="all", subgroup_value="all",
                          hypothesis=None, role="exploratory", term="exceed_share", **common), "twoway_date_t", res)]


def driver_rows(f: inputs.Frame, drivers: dict, in_family: dict, common: dict,
                mis_sized: dict | None = None) -> list[dict]:
    """Every regression row (see the header). `in_family` maps each of H5-H7 to True when it is in
    the binding Holm family (results.binding_family); it is read strictly, so a missing hypothesis
    raises (fix R2 after the milestone-4 review: it used to count as True). `mis_sized` is
    results.oversized()'s set."""
    mis_sized = mis_sized or {}
    w = tuple(drivers["surprise_winsor"])
    out = crush_rows(f, PRIMARY, w, in_family, common, True, mis_sized)
    out += crush_rows(f, TWIN, w, in_family, common, True, mis_sized)
    for spec in EXPLORATORY:
        out += crush_rows(f, spec, w, in_family, common, False, mis_sized)
    out += h7_rows(f, in_family, common, mis_sized, "evar_m1")
    out += h7_rows(f, in_family, common, mis_sized, "evar_m2")
    out += exceed_rows(f, common)
    return out
