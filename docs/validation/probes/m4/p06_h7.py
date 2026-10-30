"""p06 (claim 6): H7 by own numpy (no stats/regression.py, no stats/clustering.py): r0^2 on [1, E + sigma_d^2/252]
over H1's set, two-way date x firm CR1, Wald (0, 1); b, its CI; the exceed share against 0.425; E at day -2;
the worked example; the implied-move definition the benchmark assumes. Prints aggregates only.
Reads the stage cache and data/derived/results.parquet.
Run: uv run --frozen --no-sync python docs/validation/probes/m4/p06_h7.py [--falsify]   (--falsify: no /252)"""
import sys

import numpy as np
import pandas as pd
from scipy import stats

from earnings_vol import params
from earnings_vol.events.run import stage_dir

FALS = "--falsify" in sys.argv
p = params.load()
sd = stage_dir(p)
ev = pd.read_parquet(sd / "events.parquet").merge(pd.read_parquet(sd / "event_measures.parquet"), on="event_id")
res = pd.read_parquet("data/derived/results.parquet")
DIV = 1.0 if FALS else 252.0
print("worked example 0.00088284 + 0.2442^2/252 =", f"{0.00088284 + 0.2442 ** 2 / 252:.7f}")
print("benchmark 2(1 - Phi(sqrt(2/pi))) =", f"{2 * stats.norm.sf(np.sqrt(2 / np.pi)):.5f}")
h1 = ev[(ev["sample"] == "daily") & ev["eligible_crush"].astype(bool) & ev["crush_cboe"].notna()]
print("H1 set:", len(h1))


def cr1(X, u, g):
    _, gi = np.unique(np.asarray(g).astype(str), return_inverse=True)
    G = gi.max() + 1
    S = np.zeros((G, X.shape[1]))
    np.add.at(S, gi, X * u[:, None])
    n, k = X.shape
    return G / (G - 1) * (n - 1) / (n - k) * S.T @ S, G


def ols2(y, X, date, firm):
    xi = np.linalg.inv(X.T @ X)
    b = xi @ X.T @ y
    u = y - X @ b
    md, gd = cr1(X, u, date)
    mf, gf = cr1(X, u, firm)
    mp, _ = cr1(X, u, [f"{a}|{c}" for a, c in zip(date, firm)])
    V2 = xi @ (md + mf - mp) @ xi
    V1 = xi @ md @ xi
    return b, V2, V1, min(gd, gf) - 1, gd - 1, gd, gf, 1 - (u @ u) / ((y - y.mean()) @ (y - y.mean()))


def wald(b, V, df):
    d = b - np.array([0.0, 1.0])
    F = d @ np.linalg.solve(V, d) / 2
    return F, stats.f.sf(F, 2, df), np.linalg.eigvalsh(V).min() > 0


for evar, mid in (("evar_m1", "implied_realised"), ("evar_m2", "implied_realised_m2")):
    k = h1[h1["realized_ret_0"].notna() & h1[evar].notna() & h1["sigma_d_m1"].notna()]
    x = k[evar].to_numpy() + k["sigma_d_m1"].to_numpy() ** 2 / DIV
    y = k["realized_ret_0"].to_numpy() ** 2
    X = np.column_stack([np.ones(len(k)), x])
    date, firm = k["day0_session"].astype(str).to_numpy(), k["security_id"].to_numpy()
    b, V2, V1, df2, df1, gd, gf, r2 = ols2(y, X, date, firm)
    F2, p2, pd2 = wald(b, V2, df2)
    F1, p1, _ = wald(b, V1, df1)
    se = np.sqrt(np.diag(V2))
    q = stats.t.ppf(0.975, df2)
    print(f"{mid}: n {len(k)} G {gd}/{gf} E<=0 {int((k[evar] <= 0).sum())} R2 {r2:.4f} | a {b[0]:.6f} se {se[0]:.6f} "
          f"t {b[0] / se[0]:.3f} | b {b[1]:.4f} se {se[1]:.4f} t(b-1) {(b[1] - 1) / se[1]:.3f} p "
          f"{2 * stats.t.sf(abs((b[1] - 1) / se[1]), df2):.4f} CI [{b[1] - q * se[1]:.4f}, {b[1] + q * se[1]:.4f}] | "
          f"Wald2 F({2},{df2}) {F2:.4f} p {p2:.4f} (V PD {pd2}) | Wald1 F(2,{df1}) {F1:.4f} p {p1:.4f}")
    rr = res[(res["model_id"] == mid) & (res["family"] == "regression")]
    for _, r in rr.iterrows():
        print(f"   committed {str(r['term']):10s} {str(r['statistic']):18s} est {r['estimate']} se {r['se']} stat {r['stat']} "
              f"df {r['df']} df_num {r['df_num']} p {r['p_value']} ci [{r['ci_lo']}, {r['ci_hi']}] role {r['role']}")
# exceed share
k = h1[h1["realized_ret_0"].notna() & h1["implied_abs_move_total_m1"].notna() & (h1["evar_m1"] > 0)]
ind = (k["realized_ret_0"].abs() > k["implied_abs_move_total_m1"]).astype(float).to_numpy()
Xc = np.ones((len(k), 1))
b, V2, V1, df2, *_ = ols2(ind, Xc, k["day0_session"].astype(str).to_numpy(), k["security_id"].to_numpy())
se = np.sqrt(V2[0, 0])
t = (b[0] - 0.425) / se
print(f"exceed share: n {len(k)} share {b[0]:.4f} se {se:.4f} t {t:.3f} p {2 * stats.t.sf(abs(t), df2):.4f}")
ratio = k["implied_abs_move_total_m1"] / np.sqrt(np.sqrt(2 / np.pi) ** 2 * (k["evar_m1"] + k["sigma_d_m1"] ** 2 / 252))
print("implied_abs_move_total_m1 / (sqrt(2/pi) sqrt(E + sd^2/252)): min %.6f max %.6f" % (ratio.min(), ratio.max()))
rr = res[(res["term"] == "exceed_share")]
print("   committed:", rr[["estimate", "se", "stat", "p_value", "n"]].to_dict("records"))
med = (k["realized_ret_0"].abs() / k["implied_abs_move_total_m1"]).median()
print(f"median |r0| / implied |move| over E > 0: {med:.4f}")
