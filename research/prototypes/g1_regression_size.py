"""Why do the driver statistics fail gate G1? (milestone 4, docs/milestones/04-drivers.md §6.1)

Gate G1 (stats/g1_drivers.py) rejected H5's and H6's two-way t 9.55% and 8.10% of the time, and H7's two-way Wald
16.15%, at 5% under its calibrated null: all three above the 6.30% bar. Is that the statistic at this design, or the
simulation? This script uses the simplest possible nulls on the REAL design matrices and cluster labels:
  H5/H6: y iid N(0, 1), regressed on the primary crush model's X (z-scored |SURP|, ln sigma_d(-1), SLOPE, SIZE,
         sector and season dummies), then with no dummies, then with season dummies only;
  H7:    r = sqrt(x) z with z iid N(0, 1) and x = E + sigma_d^2/252 of the real events, r^2 regressed on [1, x];
and records the rejection rate at 5% of the two-way (date x firm), one-way date, one-way firm and HC1 (event
clusters, N - K df) tests. No real outcome (crush or r0) is read. 2,000 replications for H5/H6, 4,000 for H7; seed 1.
Run from the repository root (needs the local stage cache):
  uv run --no-sync --frozen python research/prototypes/g1_regression_size.py > research/prototypes/g1_regression_size.out.txt
"""
import numpy as np
from scipy import stats

from earnings_vol import params
from earnings_vol.stats import drivers, regression, run

p = params.load()
f = run.load(p)
m = drivers.model_inputs(f, drivers.PRIMARY, tuple(p["drivers"]["surprise_winsor"]))
X, date, firm = m["X"], m["date"], m["firm"]
print("N, K", X.shape, "G_date", len(set(date)), "G_firm", len(set(firm)))
sect = f.ev.iloc[m["rows"]]["gics_sector"].to_numpy(object)
print("firms per sector", sorted(len(set(firm[sect == s])) for s in set(sect)))
print("skewness of the z-scored regressors: |SURP| %.2f, ln sigma_d %.2f" % (stats.skew(X[:, 1]), stats.skew(X[:, 2])))
rng = np.random.default_rng(1)


def rates(Xm, n=2000):
    rej = {k: np.zeros(2) for k in ("two-way", "date", "firm", "HC1")}
    for _ in range(n):
        fit = regression.fit(rng.standard_normal(Xm.shape[0]), Xm)
        covs = {"two-way": regression.covariance(fit, Xm, date, firm), "date": regression.covariance(fit, Xm, date),
                "firm": regression.covariance(fit, Xm, firm),
                "HC1": dict(regression.covariance(fit, Xm, np.arange(Xm.shape[0]).astype(str)),
                            df=float(Xm.shape[0] - Xm.shape[1]))}
        for k, cov in covs.items():
            for i, j in enumerate((1, 2)):
                rej[k][i] += regression.coef_test(fit, cov, j)["p_value"] <= 0.05
    return "; ".join(f"{k} {100 * v[0] / n:.2f} / {100 * v[1] / n:.2f}" for k, v in rej.items())


print("H5 / H6 rejection % at 5%, y iid normal (|SURP| / ln sigma_d):")
print("  primary X (sector + season FE):", rates(X))
print("  no fixed effects:              ", rates(X[:, :5]))
seas = [j for j, nm in enumerate(m["names"]) if nm.startswith("season:")]
print("  season FE only:                ", rates(np.column_stack([X[:, :5]] + [X[:, j] for j in seas])))
h7 = drivers.h7_inputs(f, "evar_m1", float(p["drivers"]["h7_floor"]))
x, X7 = h7["x"], h7["X"]
rej, n = np.zeros(4), 4000
for _ in range(n):
    r = np.sqrt(x) * rng.standard_normal(x.size)
    fit = regression.fit(r ** 2, X7)
    covs = (regression.covariance(fit, X7, h7["date"], h7["firm"]), regression.covariance(fit, X7, h7["date"]),
            regression.covariance(fit, X7, h7["firm"]),
            dict(regression.covariance(fit, X7, np.arange(x.size).astype(str)), df=float(x.size - 2)))
    for i, cov in enumerate(covs):
        rej[i] += regression.wald_test(fit, cov, np.eye(2), np.array([0.0, 1.0]))["p_value"] <= 0.05
print("H7 Wald (a, b) = (0, 1) rejection %% at 5%%, normal moves with variance exactly x: two-way %.2f, date %.2f, "
      "firm %.2f, HC1 %.2f" % tuple(100 * rej / n))
print("x: n %d, skewness %.2f, max / median %.2f" % (x.size, stats.skew(x), x.max() / np.median(x)))
