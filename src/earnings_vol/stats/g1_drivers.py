# =============================================================================
# g1_drivers.py — Gate G1 for the driver hypotheses H5-H7 (ADR 0005 §5): the
# size of their primary statistics at the REAL design, before any H5-H7
# result is computed, and the size of their robustness rows (ADR 0005 §4).
#
# H5, H6 (the crush regression, stats/drivers.py PRIMARY). Each replication
#   simulates ln cm30 for every firm with g1.generate on the cm30 G1 design
#   (the real day-0 dates, baselines, holes and usable sessions), re-estimates
#   beta, s_i and the abnormal changes with g1.estimate (the package's code),
#   and takes the simulated market-adjusted CRUSH of H5's events. It is then
#   regressed on the REAL regressors of the primary model (z-scored |SURP|,
#   ln sigma_d(-1), SLOPE, SIZE, sector and season FE: the same design matrix
#   as production). The simulated CRUSH does not depend on them, so every
#   coefficient is 0 and a 5% test should reject 5% of the time. OLS residuals
#   do not move when Y gains X gamma, so the size of b1's test does not depend
#   on the other coefficients' true values.
#   The calibrated design is g1's cm30 calibration with each firm's scale
#   pinned to its real one (sig_firm: the firm's mean ln s_i minus the mean over
#   firms, g1.generate), so heteroskedasticity follows the real firms, as the
#   regressor ln sigma_d(-1) does. calibrated_random_scale is the same with
#   g1's random scales; the stress designs D0, D2, D4, D4+firm_fx0.03 and
#   D2+common_ar0.5 are g1.STRESS's.
#   The mean-adjusted twin (robustness) is sized too: the same regression of
#   the simulated ln cm30(0) - ln cm30(-1), key TWIN_KEY.
#   Power: adding beta z_j to Y moves b_j by exactly beta and leaves the
#   residuals, so the power at beta (log points of crush per sd of the
#   regressor) is read from the null replications: reject when the two-sided
#   p of (b_j + beta)/se_j <= alpha.
# H7 (implied vs realised). r_i = sqrt(v_i) w_i with v_i = x_i m_f(i), x_i the
#   real E_i + sigma_d,i^2/252 (floored at h7_floor; none of the primary
#   events needs it), m_f = exp(tau g_f - tau^2/2) a firm multiplier with mean
#   1, and w_i = sqrt(rho) c_date(i) + sqrt(1 - rho) eps_i, c and eps standard
#   Student t with nu degrees of freedom scaled to variance 1 (normal when nu
#   is inf). So E[r_i^2 | x] = x_i: a = 0, b = 1 hold exactly. Each
#   replication regresses r^2 on [1, x] and runs the two-way and the one-way
#   date Wald test of (a, b) = (0, 1). Power at b: r^2 scaled by b.
#   calibrate_h7() estimates (nu, rho, tau) from the real standardised moves
#   z_i = r0_i / sqrt(x_i), rescaled to mean square 1 first, so the level of
#   r0^2 against x (the tested quantity) does not enter (as g1.calibrate keeps
#   H1's mean out of the day-0 jump):
#     rho  = sum over dates of sum_{i != j} z_i z_j / sum n_t (n_t - 1),
#            times exp(tau^2 / 4) (E sqrt(m_i m_j) = exp(-tau^2 / 4))
#     tau  = sqrt(ln(1 + var_m)), var_m = var across firms of mean z^2 minus
#            the mean within-firm sampling variance (method of moments, >= 0)
#     nu   from the kurtosis K = mean z^4: E w^4 = K exp(-tau^2) =
#            (rho^2 + (1 - rho)^2) k + 6 rho (1 - rho), k = 3 + 6 / (nu - 4);
#            normal when k <= 3, nu at least NU_MIN.
# =============================================================================

from dataclasses import dataclass

import numpy as np
from scipy import stats

from earnings_vol.panel import abnormal
from earnings_vol.stats import g1, regression

PRIMARY = {"H5": "twoway_date_t", "H6": "twoway_date_t", "H7": "twoway_date_wald"}
ROBUST = {"H5": "cluster_date_t", "H6": "cluster_date_t", "H7": "cluster_date_wald"}
# The mean-adjusted twin of H5/H6 (drivers.TWIN): the same two-way t on ln cm30(0) - ln cm30(-1) of
# the simulated series. Its G1 key differs from the primary's statistic name, and drivers.crush_rows
# withholds a twin row by this key.
TWIN_KEY = "twoway_date_t:mean_adj"
NU_MIN = 4.05
CM30_STRESS = ("D0", "D2", "D4", "D4+firm_fx0.03", "D2+common_ar0.5")


@dataclass
class DriverDesign:
    """The fixed inputs of the H5-H7 simulation (built once from the real tables)."""

    rows: np.ndarray        # H5/H6 events: indices into the cm30 G1 design's events
    X: np.ndarray           # the primary crush model's design matrix (real regressors)
    j: dict                 # {"H5": column of |SURP|, "H6": column of ln sigma_d}
    date: np.ndarray        # cluster labels of those events
    firm: np.ndarray
    sig_firm: np.ndarray    # per cm30-design firm: real mean ln s_i minus the mean over firms
    x7: np.ndarray          # H7: E + sigma_d^2/252 per event (floored)
    date7: np.ndarray
    firm7: np.ndarray
    n_floored: int


def std_t(rng: np.random.Generator, nu: float, size) -> np.ndarray:
    """Student t draws with nu degrees of freedom, scaled to variance 1 (normal when nu is inf)."""
    if not np.isfinite(nu):
        return rng.standard_normal(size)
    return rng.standard_t(nu, size) * np.sqrt((nu - 2.0) / nu)


def _codes(labels) -> tuple[np.ndarray, int]:
    _, gi = np.unique(np.asarray(labels).astype(str), return_inverse=True)
    return gi, int(gi.max()) + 1


def h7_generate(rng: np.random.Generator, dd: DriverDesign, p: dict) -> np.ndarray:
    """Simulated r0 of H7's events under the null (see the header)."""
    di, nd = _codes(dd.date7)
    fi, nf = _codes(dd.firm7)
    nu, rho, tau = float(p["nu"]), float(p["rho_d"]), float(p["firm_sd"])
    c = std_t(rng, nu, nd)
    eps = std_t(rng, nu, dd.x7.size)
    w = np.sqrt(rho) * c[di] + np.sqrt(1.0 - rho) * eps
    m = np.exp(tau * rng.standard_normal(nf) - tau ** 2 / 2.0)
    return np.sqrt(dd.x7 * m[fi]) * w


def calibrate_h7(r: np.ndarray, x: np.ndarray, date, firm) -> dict:
    """{"params": {nu, rho_d, firm_sd}, "measured": {...}}: (nu, rho, tau) from the real moves
    (see the header). Events with x <= 0 are left out."""
    ok = np.isfinite(r) & np.isfinite(x) & (x > 0)
    z = r[ok] / np.sqrt(x[ok])
    z = z / np.sqrt(np.mean(z ** 2))
    date, firm = np.asarray(date, dtype=object)[ok], np.asarray(firm, dtype=object)[ok]
    di, nd = _codes(date)
    s = np.bincount(di, z, nd)
    s2 = np.bincount(di, z ** 2, nd)
    nt = np.bincount(di, None, nd)
    pairs = float((nt * (nt - 1)).sum())
    rho_raw = float((s ** 2 - s2).sum() / pairs) if pairs > 0 else 0.0
    fi, nf = _codes(firm)
    z2 = z ** 2
    means = np.array([z2[fi == k].mean() for k in range(nf)])
    samp = np.array([z2[fi == k].var(ddof=1) / (fi == k).sum() for k in range(nf) if (fi == k).sum() >= 2])
    var_m = max(0.0, float(means.var(ddof=1) - samp.mean()))
    tau = float(np.sqrt(np.log1p(var_m)))
    rho = float(min(0.9, max(0.0, rho_raw * np.exp(tau ** 2 / 4.0))))
    kurt = float(np.mean(z ** 4))
    ew4 = kurt * np.exp(-tau ** 2)
    k = (ew4 - 6.0 * rho * (1.0 - rho)) / (rho ** 2 + (1.0 - rho) ** 2)
    nu = float("inf") if k <= 3.0 else max(NU_MIN, 4.0 + 6.0 / (k - 3.0))
    return {"params": {"nu": nu, "rho_d": rho, "firm_sd": tau},
            "measured": {"n": int(z.size), "n_dates": int(nd), "n_firms": int(nf), "kurtosis": kurt,
                         "rho_d_raw": rho_raw, "firm_var_ms": var_m, "kurtosis_innovation": float(k)}}


def evaluate_h56(dd: DriverDesign, d: g1.Design, x: np.ndarray, est: dict, alpha: float,
                 betas) -> tuple[dict, dict]:
    """({"H5": {statistic: reject?, "_primary"}, "H6": ...}, {"H5": {beta: reject?}, ...}) for one
    simulated data set (x: ln cm30 per firm and session; est: g1.estimate's inputs): the crush
    regression on the real regressors, and its mean-adjusted twin (see the header)."""
    A = est["e"][dd.rows, abnormal.col(0)]
    fit = regression.fit(A, dd.X)
    cov2 = regression.covariance(fit, dd.X, dd.date, dd.firm)
    cov1 = regression.covariance(fit, dd.X, dd.date)
    raw = x[d.firm[dd.rows], d.sess[dd.rows, abnormal.col(0)]] - x[d.firm[dd.rows], d.sess[dd.rows, abnormal.col(-1)]]
    fit_m = regression.fit(raw, dd.X)
    cov_m = regression.covariance(fit_m, dd.X, dd.date, dd.firm)
    out, pw = {}, {}
    for h, j in dd.j.items():
        t2, t1 = regression.coef_test(fit, cov2, j), regression.coef_test(fit, cov1, j)
        out[h] = {"_primary": PRIMARY[h], PRIMARY[h]: bool(t2["p_value"] <= alpha),
                  ROBUST[h]: bool(t1["p_value"] <= alpha),
                  TWIN_KEY: bool(regression.coef_test(fit_m, cov_m, j)["p_value"] <= alpha)}
        pw[h] = {float(b): bool(2 * stats.t.sf(abs((t2["estimate"] + b) / t2["se"]), t2["df"]) <= alpha)
                 for b in betas}
    return out, pw


def evaluate_h7(dd: DriverDesign, r: np.ndarray, alpha: float, bs) -> tuple[dict, dict]:
    """({"H7": {statistic: reject?, "_primary"}}, {"H7": {b: reject?}}) for one simulated r."""
    X = np.column_stack([np.ones(dd.x7.size), dd.x7])
    R, q = np.eye(2), np.array([0.0, 1.0])

    def tests(y):
        fit = regression.fit(y, X)
        return (regression.wald_test(fit, regression.covariance(fit, X, dd.date7, dd.firm7), R, q),
                regression.wald_test(fit, regression.covariance(fit, X, dd.date7), R, q))

    w2, w1 = tests(r ** 2)
    out = {"H7": {"_primary": PRIMARY["H7"], PRIMARY["H7"]: bool(w2["p_value"] <= alpha),
                  ROBUST["H7"]: bool(w1["p_value"] <= alpha)}}
    pw = {"H7": {float(b): bool(tests(b * r ** 2)[0]["p_value"] <= alpha) for b in bs}}
    return out, pw


def replicate(args) -> dict:
    """One replication: (cm30 design, driver design, cm30 params or None, H7 params or None, seed,
    alpha, betas, bs). The cm30 series uses g1's stream from `seed`; H7 its own, (seed, 7)."""
    d, dd, p_cm30, p_h7, seed, alpha, betas, bs = args
    out, pw = {}, {}
    if p_cm30 is not None:
        rng = np.random.default_rng(seed)
        x, m = g1.generate(rng, d, p_cm30)
        o, w = evaluate_h56(dd, d, x, g1.estimate(d, x, m), alpha, betas)
        out.update(o)
        pw.update(w)
    if p_h7 is not None:
        o, w = evaluate_h7(dd, h7_generate(np.random.default_rng([seed, 7]), dd, p_h7), alpha, bs)
        out.update(o)
        pw.update(w)
    out["_power"] = pw
    return out


def rates(results: list[dict]) -> tuple[dict, dict]:
    """({test: {statistic: rate, "_primary"}}, {test: {shift: power}}) over replications."""
    sizes = g1.rates([{h: v for h, v in r.items() if h != "_power"} for r in results])
    power = {}
    for h, by in results[0]["_power"].items():
        power[h] = {b: float(np.mean([r["_power"][h][b] for r in results])) for b in by}
    return sizes, power


def sig_firm(firms: list, firm_of_event, log_s) -> np.ndarray:
    """Per firm of `firms`: the mean of its events' ln s_i minus the mean of those firm means
    (firms without an event: 0)."""
    firm_of_event, log_s = np.asarray(firm_of_event, dtype=object), np.asarray(log_s, float)
    means = {f: float(log_s[firm_of_event == f].mean()) for f in sorted(set(firm_of_event.tolist()))}
    grand = float(np.mean(list(means.values())))
    return np.array([means[f] - grand if f in means else 0.0 for f in firms])


def h7_stress(cal7: dict) -> dict:
    """The H7 stress designs (reported, not pass/fail): normal moves with no dependence; t(4.5)
    tails, a same-date correlation of 0.3 and a firm sd of 0.5, each with the other parameters
    calibrated."""
    p = dict(cal7["params"])
    return {"h7:normal": {"nu": float("inf"), "rho_d": 0.0, "firm_sd": 0.0},
            "h7:t4.5": dict(p, nu=4.5), "h7:date0.3": dict(p, rho_d=0.3), "h7:firm0.5": dict(p, firm_sd=0.5)}


def designs(cal: dict, cal7: dict, sigf: np.ndarray) -> dict:
    """{name: {"cm30": params or None, "h7": params or None}}: the calibrated design (binding for
    H5-H7), H5/H6's calibrated_random_scale and stress designs, and H7's stress designs. Pure."""
    out = {"calibrated": {"cm30": dict(cal["params"], sig_firm=np.asarray(sigf, float)),
                          "h7": dict(cal7["params"])},
           "calibrated_random_scale": {"cm30": dict(cal["params"]), "h7": None}}
    for k in CM30_STRESS:
        out[k] = {"cm30": {kk: vv for kk, vv in g1.STRESS[k].items() if not kk.startswith("_")}, "h7": None}
    for k, v in h7_stress(cal7).items():
        out[k] = {"cm30": None, "h7": v}
    return out


def merge(report: dict, drv: dict) -> dict:
    """The H1-H4 G1 report with the H5-H7 run merged in (pure): their rates under each design
    name (H5/H6's stress designs share g1.STRESS's names: the same DGP, its own replications),
    the power designs power_beta:<beta> (H5, H6) and power_b:<b> (H7) with the primary's
    rejection rate, the gate and primaries, the power summaries, the re-measured rates, the H7
    calibration and the event counts."""
    out = dict(report)
    rates_ = {k: {h: dict(r) for h, r in v.items()} for k, v in report["rates"].items()}
    for name, by in drv["rates"].items():
        rates_.setdefault(name, {}).update({h: dict(r) for h, r in by.items()})
    for h, by in drv["power"].items():
        kind = "power_b" if h == "H7" else "power_beta"
        for shift, pw in by.items():
            rates_.setdefault(f"{kind}:{shift}", {})[h] = {"_primary": PRIMARY[h], PRIMARY[h]: pw}
    out["rates"] = rates_
    out["gate"] = dict(report["gate"], **drv["gate"])
    out["primary"] = dict(report["primary"], **{h: PRIMARY[h] for h in drv["gate"]})
    out["power"] = dict(report["power"], **drv["power_summary"])
    rem = report.get("remeasured")
    if drv.get("remeasured"):
        base = rem or {"reps": drv["remeasured"]["reps"], "rates": {}}
        if int(base["reps"]) != int(drv["remeasured"]["reps"]):
            raise ValueError("the H1-H4 and H5-H7 re-measures must use the same number of replications")
        rem = dict(base, rates=dict(base["rates"], **drv["remeasured"]["rates"]),
                   seed_block_drivers=drv["remeasured"]["seed_block"])
    out["remeasured"] = rem
    out["calibration_h7"] = drv["calibration_h7"]
    out["n_events_drivers"] = drv["n_events"]
    out["drivers_seconds"] = drv.get("seconds")
    return out
