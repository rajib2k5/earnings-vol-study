"""p04 (claim 4): stats/regression.py vs statsmodels OLS cov_type cluster, use_t=True, on random unbalanced
designs: one-way and two-way CR1 se, t, p, CI, df, and the Wald F of (a, b) = (0, 1)-style restrictions with
F df_denom. Also production-shaped designs (a firm at most once per date) and the real H5/H7 designs.
Run: uv run --frozen --no-sync python docs/validation/probes/m4/p04_regression_vs_sm.py [--falsify]
--falsify: the package's intersection term is ADDED instead of subtracted (must then disagree)."""
import sys
import warnings

import numpy as np
import statsmodels.api as sm

from earnings_vol.stats import regression

warnings.simplefilter("ignore")
if "--falsify" in sys.argv:
    _orig = regression.covariance

    def bad(f, X, a, b=None):
        c = _orig(f, X, a, b)
        if b is not None:
            vab = c["V_a"] + c["V_b"] - c["V"]
            c = dict(c, V=c["V_a"] + c["V_b"] + vab)
        return c
    regression.covariance = bad

rng = np.random.default_rng(4)
worst = {k: 0.0 for k in ("se1", "t1", "p1", "se2", "t2", "p2", "ci2", "F2", "pF2", "F1", "pF1")}
dfbad = 0
n_designs = 0
for it in range(300):
    n = int(rng.integers(40, 260))
    k = int(rng.integers(2, 6))
    gd, gf = int(rng.integers(8, 40)), int(rng.integers(6, 25))
    once = it % 2 == 0      # production shape: a firm at most once per date
    firm = rng.integers(0, gf, n)
    date = rng.integers(0, gd, n)
    if once:
        seen = set()
        for i in range(n):
            while (firm[i], date[i]) in seen:
                date[i] = rng.integers(0, gd + 40)
            seen.add((firm[i], date[i]))
    X = np.column_stack([np.ones(n)] + [rng.standard_normal(n) * rng.uniform(0.2, 3) + (rng.exponential(1, n) if j == 0 else 0)
                                        for j in range(k - 1)])
    y = X @ rng.standard_normal(k) + rng.standard_normal(n) * (1 + firm % 3) + rng.standard_normal(gd + 40)[date]
    if np.unique(date).size < 3 or np.unique(firm).size < 3:
        continue
    n_designs += 1
    f = regression.fit(y, X)
    c1 = regression.covariance(f, X, date)
    c2 = regression.covariance(f, X, date, firm)
    s1 = sm.OLS(y, X).fit(cov_type="cluster", cov_kwds={"groups": date}, use_t=True)
    s2 = sm.OLS(y, X).fit(cov_type="cluster", cov_kwds={"groups": np.column_stack([date, firm])}, use_t=True)
    if s2.df_resid_inference != c2["df"] or s1.df_resid_inference != c1["df"]:
        dfbad += 1
    for j in range(k):
        a, b = regression.coef_test(f, c1, j), regression.coef_test(f, c2, j)
        if b["fallback"]:
            continue
        worst["se1"] = max(worst["se1"], abs(a["se"] - s1.bse[j]) / s1.bse[j])
        worst["t1"] = max(worst["t1"], abs(a["stat"] - s1.tvalues[j]))
        worst["p1"] = max(worst["p1"], abs(a["p_value"] - s1.pvalues[j]))
        worst["se2"] = max(worst["se2"], abs(b["se"] - s2.bse[j]) / s2.bse[j])
        worst["t2"] = max(worst["t2"], abs(b["stat"] - s2.tvalues[j]))
        worst["p2"] = max(worst["p2"], abs(b["p_value"] - s2.pvalues[j]))
        worst["ci2"] = max(worst["ci2"], abs(b["ci_hi"] - s2.conf_int()[j, 1]))
    R = np.zeros((2, k)); R[0, 0] = 1; R[1, 1] = 1
    r = np.array([0.0, 1.0])
    w2 = regression.wald_test(f, c2, R, r)
    w1 = regression.wald_test(f, c1, R, r)
    if not w2["fallback"]:
        t2 = s2.wald_test((R, r), use_f=True, scalar=True)
        worst["F2"] = max(worst["F2"], abs(w2["stat"] - t2.statistic) / max(1, t2.statistic))
        worst["pF2"] = max(worst["pF2"], abs(w2["p_value"] - t2.pvalue))
        if t2.df_denom != w2["df"] or t2.df_num != 2:
            dfbad += 1
    t1 = s1.wald_test((R, r), use_f=True, scalar=True)
    worst["F1"] = max(worst["F1"], abs(w1["stat"] - t1.statistic) / max(1, t1.statistic))
    worst["pF1"] = max(worst["pF1"], abs(w1["p_value"] - t1.pvalue))
print(f"designs {n_designs}; df mismatches (t df_resid_inference, F df_denom/df_num) {dfbad}")
print("max abs diff:", {k: f"{v:.2e}" for k, v in worst.items()})
ok = dfbad == 0 and max(worst.values()) <= 1e-10
print("PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
