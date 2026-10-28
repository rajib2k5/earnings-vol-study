"""Delta probe 1b: is ADR 0005 §2b's two-way CR1 the Cameron-Gelbach-Miller (2011) estimator, and does statsmodels'
two-column `groups` compute the same number?

ADR 0005 §2b (intercept-only model, u_i = A_i - mean A):
    V_g = G/(G-1) * (1/N^2) * sum_c (sum_{i in c} u_i)^2      (one-way CR1)
    V   = V_A + V_B - V_{A cap B}                            (two-way), t = mean / sqrt(V) vs t_{min(G_A, G_B) - 1}
    if V <= 0: max(V_A, V_B)

Channel B compares it with statsmodels 0.15.0
    OLS(A, ones).fit(cov_type="cluster", cov_kwds={"groups": np.column_stack([gA, gB])}, use_t=True)
on (i) a hand-worked 4-event example, (ii) 200 random designs shaped like the study (N = 352, 7 seasons, 50 firms,
at most one event per firm and season, so A cap B cells are singletons as ADR 0005:627 says), and (iii) designs where
firm x season cells hold several events (so the intersection term is not HC1).
It also prints the df statsmodels uses for its t p-value, with and without use_t.

Falsifiers (each must make the comparison FAIL):
  F1  intersection term added instead of subtracted;  F2  G/(G-1) dropped;  F3  intersection term dropped.
Exit code 0 only if the ADR formula matches statsmodels everywhere AND every falsifier mismatches.
Run: uv run --no-sync --frozen python docs/validation/probes/m0-delta/d1_twoway_cgm.py
"""
import sys

import numpy as np
import statsmodels
import statsmodels.api as sm
from scipy import stats


def cr1(u, g):
    _, gi = np.unique(g, return_inverse=True, axis=0)
    gi = gi.ravel()
    G = gi.max() + 1
    S = np.bincount(gi, u, G)
    return G / (G - 1) * (S ** 2).sum() / u.size ** 2, G


def adr_twoway(A, gA, gB, variant="adr"):
    u = A - A.mean()
    VA, GA = cr1(u, gA)
    VB, GB = cr1(u, gB)
    VI, _ = cr1(u, np.column_stack([gA, gB]))
    if variant == "F1":
        V = VA + VB + VI
    elif variant == "F2":
        N = A.size
        V = sum((np.bincount(np.unique(g, return_inverse=True, axis=0)[1].ravel(), u) ** 2).sum() / N ** 2 * s
                for g, s in ((gA, 1), (gB, 1), (np.column_stack([gA, gB]), -1)))
    elif variant == "F3":
        V = VA + VB
    else:
        V = VA + VB - VI
    if V <= 0:
        V = max(VA, VB)
    return V, min(GA, GB) - 1


def sm_twoway(A, gA, gB, use_t=True):
    X = np.ones((A.size, 1))
    r = sm.OLS(A, X).fit(cov_type="cluster", cov_kwds={"groups": np.column_stack([gA, gB])}, use_t=use_t)
    return float(r.cov_params()[0, 0]), r.df_resid_inference if hasattr(r, "df_resid_inference") else None, \
        float(r.pvalues[0]), r


ok = True
print(f"statsmodels {statsmodels.__version__}, numpy {np.__version__}")

# (i) hand-worked 4-event example: seasons (A) and firms (B), values chosen by hand
A = np.array([0.10, -0.02, 0.05, 0.03])
season = np.array([1, 1, 2, 2])
firm = np.array([1, 2, 1, 2])
# by hand: mean 0.04; u = (0.06, -0.06, 0.01, -0.01)
#   seasons: S = (0.00, 0.00)            -> V_A = 2/1 * 0 / 16 = 0
#   firms:   S = (0.07, -0.07)           -> V_B = 2/1 * 0.0098 / 16 = 0.001225
#   cells:   singletons, sum u^2 = 0.0074 -> V_I = 4/3 * 0.0074 / 16 = 0.000616667
#   V = 0 + 0.001225 - 0.000616667 = 0.000608333
hand = 0.001225 - 4 / 3 * 0.0074 / 16
V, df = adr_twoway(A, season, firm)
Vsm, dfsm, p_sm, _ = sm_twoway(A, season, firm)
print(f"[hand 4-event] hand {hand:.12g}  adr {V:.12g}  statsmodels {Vsm:.12g}  df adr {df}  df sm {dfsm}")
ok &= abs(V - hand) < 1e-15 and abs(Vsm - hand) < 1e-15

# (ii) study-shaped random designs; (iii) designs with repeated firm x season cells
rng = np.random.default_rng(20261028)
worst = {"adr": 0.0}
fals = {"F1": np.inf, "F2": np.inf, "F3": np.inf}
dfs = set()
pdiff = 0.0
for rep in range(400):
    if rep < 200:
        N, Gs, F = 352, 7, 50
        season = np.repeat(np.arange(Gs), [52, 50, 50, 50, 49, 49, 52])
        firm = np.concatenate([rng.choice(F, n, replace=n > F) for n in [52, 50, 50, 50, 49, 49, 52]])
    else:
        N, Gs, F = 240, 6, 12  # several events per firm x season cell
        season = rng.integers(0, Gs, N)
        firm = rng.integers(0, F, N)
    # dependence in both dimensions so that both terms matter
    A = rng.normal(0, 1, Gs)[season] * 0.3 + rng.normal(0, 1, F)[firm] * 0.3 + rng.normal(0, 1, N)
    V, df = adr_twoway(A, season, firm)
    Vsm, dfsm, psm, _ = sm_twoway(A, season, firm)
    dfs.add((df, dfsm))
    worst["adr"] = max(worst["adr"], abs(V - Vsm) / Vsm)
    t = A.mean() / np.sqrt(V)
    pdiff = max(pdiff, abs(2 * stats.t.sf(abs(t), df) - psm))
    for f in fals:
        Vf, _ = adr_twoway(A, season, firm, f)
        fals[f] = min(fals[f], abs(Vf - Vsm) / Vsm)
print(f"[random x400] max rel |V_adr - V_sm| = {worst['adr']:.2e}; max |p_adr - p_sm(use_t)| = {pdiff:.2e}; "
      f"(df_adr, df_sm) pairs seen: {sorted(dfs)}")
ok &= worst["adr"] < 1e-10 and pdiff < 1e-10 and all(a == b for a, b in dfs)
for f, v in fals.items():
    print(f"  falsifier {f}: min rel diff over 400 designs = {v:.3e} -> {'MISMATCH (good)' if v > 1e-6 else 'MATCH (falsifier failed)'}")
    ok &= v > 1e-6

# what statsmodels does by default (use_t not passed)
_, _, p_default, r_def = sm_twoway(A, season, firm, use_t=False)
_, _, p_t, r_t = sm_twoway(A, season, firm, use_t=True)
print(f"[defaults] use_t not set -> use_t={r_def.use_t}, p={p_default:.6f} (normal); use_t=True -> p={p_t:.6f} "
      f"(t with df {r_t.df_resid_inference})")
# non-PSD case: what statsmodels returns when V_A + V_B - V_I <= 0 (ADR substitutes max(V_A, V_B))
A = np.array([1.1, -0.9, -0.9, 1.1]); season = np.array([1, 1, 2, 2]); firm = np.array([1, 2, 1, 2])  # both one-way sums 0
u = A - A.mean(); VA, _ = cr1(u, season); VB, _ = cr1(u, firm); VI, _ = cr1(u, np.column_stack([season, firm]))
Vsm, _, _, _ = sm_twoway(A, season, firm)
print(f"[non-PSD] V_A {VA:.4f} V_B {VB:.4f} V_I {VI:.4f}: raw two-way {VA + VB - VI:.4f}; statsmodels returns {Vsm:.4f}; "
      f"ADR uses {adr_twoway(A, season, firm)[0]:.4f}")
print("RESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
