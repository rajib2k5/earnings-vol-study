"""Delta-2 probe e5 (claim 5): does G1's reference-distribution check catch statsmodels' use_t=False default for
regressions as well as intercept-only tests? statsmodels 0.15.0.

G1 (ADR 0005 :781-790; data model :703-711) reads each results row and requires
  df == min(G_A, G_B) - 1 (two-way) or G - 1 (one-way), and
  p_value == two-sided t_df tail of stat (t rows), or the F tail with df as denominator df (Wald rows), to 1e-10.
The probe fits intercept-only and 2-regressor OLS with two-way and one-way clusters, default use_t and use_t=True,
writes rows the way a straightforward results writer would (stat = tvalues, p = pvalues, df = df_resid_inference,
ci = conf_int()), and applies the check. It also reports what the default does to ci_lo / ci_hi, which G1 does not
read. Falsifier: use_t=True rows must pass; default rows must fail.

Run from the repository root: .venv/bin/python docs/validation/probes/m0-delta2/e5_use_t.py
"""
import warnings

import numpy as np
import statsmodels
import statsmodels.api as sm
from scipy import stats

warnings.simplefilter("ignore")
print("statsmodels", statsmodels.__version__)
rng = np.random.default_rng(5)
n = 350
gA = rng.integers(0, 7, n)          # 7 date/season clusters
gB = rng.integers(0, 50, n)         # 50 firms
x = rng.normal(size=(n, 2))
y = 0.1 + 0.2 * x[:, 0] + rng.normal(0, 1, n) + rng.normal(0, 0.5, 7)[gA]


def g1_check(stat, p, df, wald_q=None):
    if wald_q is None:
        ref = 2 * stats.t.sf(abs(stat), df)
    else:
        ref = stats.f.sf(stat, wald_q, df)
    return abs(p - ref) <= 1e-10, ref


rows = []
for model_name, X in (("intercept-only", np.ones((n, 1))), ("regression", sm.add_constant(x))):
    for cl_name, groups, Gexp in (("two-way", np.column_stack([gA, gB]), 6), ("one-way", gA, 6)):
        for ut in (None, True):
            kw = {} if ut is None else {"use_t": True}
            res = sm.OLS(y, X).fit(cov_type="cluster", cov_kwds={"groups": groups}, **kw)
            j = X.shape[1] - 1 if model_name == "regression" else 0
            j = 1 if model_name == "regression" else 0
            stat, p, df = res.tvalues[j], res.pvalues[j], getattr(res, "df_resid_inference", None)
            ok, ref = g1_check(stat, p, df)
            ci = res.conf_int()[j]
            se = res.bse[j]
            crit = (ci[1] - res.params[j]) / se
            rows.append((model_name, cl_name, "default" if ut is None else "use_t=True", res.use_t, df, ok, crit))
            print(f"{model_name:15s} {cl_name:8s} {'default' if ut is None else 'use_t=True':10s} use_t={res.use_t!s:5s} "
                  f"df_inf={df} p={p:.6f} t_df-ref={ref:.6f} G1 {'PASS' if ok else 'FAIL'}  CI half-width/se={crit:.3f}")
            if model_name == "regression" and cl_name == "two-way":
                w = res.wald_test("const = 0, x1 = 0", scalar=True)
                stat_w = float(np.squeeze(w.statistic))
                pw = float(np.squeeze(w.pvalue))
                okw, refw = g1_check(stat_w, pw, df, wald_q=2)
                print(f"{'':15s} {'':8s} {'':10s} Wald: {'F' if w.distribution == 'F' else w.distribution} "
                      f"stat={stat_w:.4f} p={pw:.6f} F(2,{df})-ref={refw:.6f} G1 {'PASS' if okw else 'FAIL'}")
                rows.append((model_name, cl_name + " wald", "default" if ut is None else "use_t=True", res.use_t, df,
                             okw, None))
print(f"t_6 0.975 quantile {stats.t.ppf(0.975, 6):.3f}; normal {stats.norm.ppf(0.975):.3f}")
caught = all(not r[5] for r in rows if r[2] == "default")
clean = all(r[5] for r in rows if r[2] == "use_t=True")
print("RESULT: G1 fails every default row:", caught, "| passes every use_t=True row (falsifier):", clean)
raise SystemExit(0 if caught and clean else 1)
