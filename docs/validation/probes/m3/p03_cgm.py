"""p03: the two-way CGM t (claims 3a, 3b).

3a: earnings_vol.stats.clustering.twoway against statsmodels OLS on a constant with two-column
    groups and use_t=True, on 200 random unbalanced data sets.
3b: H1 from the stage values with my own two-way code (no import of clustering), printed as the
    aggregate only. --falsify: add the intersection term instead of subtracting it.
Run: uv run --frozen --no-sync python docs/validation/probes/m3/p03_cgm.py [--falsify]
"""
import sys

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

from earnings_vol.stats import clustering

FALSIFY = "--falsify" in sys.argv
SIGN = +1.0 if FALSIFY else -1.0


def own_twoway(A, ga, gb):
    A = np.asarray(A, float)
    u = A - A.mean()
    N = A.size

    def v(groups):
        df = pd.DataFrame({"g": groups, "u": u})
        s = df.groupby("g")["u"].sum().to_numpy()
        G = s.size
        return G / (G - 1) * (s ** 2).sum() / N ** 2, G
    va, Ga = v(list(ga))
    vb, Gb = v(list(gb))
    vab, _ = v([f"{a}|{b}" for a, b in zip(ga, gb)])
    V = va + vb + SIGN * vab
    if V <= 0:
        V = max(va, vb)
    se = np.sqrt(V)
    t = A.mean() / se
    dfree = min(Ga, Gb) - 1
    return A.mean(), se, t, dfree, 2 * stats.t.sf(abs(t), dfree), Ga, Gb


rng = np.random.default_rng(3)
worst = {"t": 0.0, "p": 0.0, "df": 0}
for rep in range(200):
    n = int(rng.integers(30, 200))
    ga = rng.integers(0, int(rng.integers(5, 40)), n)
    gb = rng.integers(0, int(rng.integers(5, 30)), n)
    A = rng.standard_normal(n) + 0.3 * rng.standard_normal(ga.max() + 1)[ga] + 0.2
    pk = clustering.twoway(A, ga, gb)
    if pk["fallback"]:
        continue
    res = sm.OLS(A, np.ones(n)).fit(cov_type="cluster", cov_kwds={"groups": np.column_stack([ga, gb])}, use_t=True)
    worst["t"] = max(worst["t"], abs(res.tvalues[0] - pk["stat"]))
    worst["p"] = max(worst["p"], abs(res.pvalues[0] - pk["p_value"]))
    worst["df"] = max(worst["df"], abs(res.df_resid_inference - pk["df"]))
print(f"3a package twoway vs statsmodels (use_t=True), 200 random sets: max |dt| {worst['t']:.2e}, "
      f"max |dp| {worst['p']:.2e}, max |ddf| {worst['df']}")

SD = "/home/rajib2k5/data/vol-projects/earnings-vol-study/cache/stage/94065662cd46610c/"
em = pd.read_parquet(SD + "event_measures.parquet")
ev = pd.read_parquet(SD + "events.parquet")
x = em.merge(ev, on="event_id")
h1 = x[(x["sample"] == "daily") & x["eligible_crush"] & x["crush_cboe"].notna()]
est, se, t, dfree, p, Ga, Gb = own_twoway(h1["crush_cboe"], h1["day0_session"].astype(str), h1["security_id"])
print(f"3b H1 own two-way: n {len(h1)}, G_date {Ga}, G_firm {Gb}, estimate {est:.4f}, se {se:.4f}, t {t:.2f}, "
      f"df {dfree}, p {p:.3g}")
h4 = x[(x["sample"] == "daily") & x["eligible_crush"] & x["dsigma_d_cboe"].notna()]
est, se, t, dfree, p, Ga, Gb = own_twoway(h4["dsigma_d_cboe"], h4["day0_session"].astype(str), h4["security_id"])
print(f"3b H4 own two-way: n {len(h4)}, G_date {Ga}, G_firm {Gb}, estimate {est:.4f}, se {se:.4f}, t {t:.2f}, "
      f"df {dfree}, p {p:.3g}")
if FALSIFY:
    sys.exit(1)  # the falsifier's H1 line must differ from the claimed se 0.0113 / t -17.70 (checked by eye in out/)
