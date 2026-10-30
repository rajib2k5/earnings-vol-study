"""p02 (claim 2): size of H5/H6's two-way t and H7's two-way Wald under iid normal outcomes on the REAL
design, with an OWN vectorised CR1 (not stats/regression.py). The package is used only to build the real
design matrix and cluster labels (drivers.model_inputs, drivers.h7_inputs); no real outcome is read.

Run: uv run --frozen --no-sync python docs/validation/probes/m4/p02_size_iid.py [reps] [--falsify]
--falsify drops the G/(G-1) factor in every dimension (the rates must then move).
"""
import sys

import numpy as np
from scipy import stats

from earnings_vol import params
from earnings_vol.stats import drivers, run

R = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 8000
FALSIFY = "--falsify" in sys.argv
p = params.load()
f = run.load(p)


def codes(lab):
    _, gi = np.unique(np.asarray(lab).astype(str), return_inverse=True)
    return gi, gi.max() + 1


def meat_parts(W, U, gi, G, N, K):
    """For rows a, b of W (K x N influence matrix) and residual matrix U (N x R): sum over clusters of
    (sum_i W_a,i u_i)(sum_i W_b,i u_i), times c = G/(G-1) (N-1)/(N-K). Returns K x K x R."""
    c = (1.0 if FALSIFY else G / (G - 1)) * (N - 1) / (N - K)
    S = np.zeros((G, W.shape[0], U.shape[1]))
    for k in range(W.shape[0]):
        np.add.at(S[:, k, :], gi, W[k][:, None] * U)
    return c * np.einsum("gar,gbr->abr", S, S)


def twoway(X, Y, date, firm, rows_of_interest):
    N, K = X.shape
    W = np.linalg.solve(X.T @ X, X.T)          # K x N: b = W y
    B = W @ Y
    U = Y - X @ B
    Wr = W[rows_of_interest]
    gd, Gd = codes(date)
    gf, Gf = codes(firm)
    gp, Gp = codes([f"{a}|{b}" for a, b in zip(date, firm)])
    Vd = meat_parts(Wr, U, gd, Gd, N, K)
    Vf = meat_parts(Wr, U, gf, Gf, N, K)
    Vp = meat_parts(Wr, U, gp, Gp, N, K)
    return B[rows_of_interest], Vd + Vf - Vp, Vd, Vf, min(Gd, Gf) - 1, Gd - 1


rng = np.random.default_rng(20261101)
# H5 / H6
m = drivers.model_inputs(f, drivers.PRIMARY, tuple(p["drivers"]["surprise_winsor"]))
X, date, firm = m["X"], m["date"], m["firm"]
j5, j6 = m["names"].index("abs_surprise"), m["names"].index("ln_sigma_d")
print("H5/H6 design: N %d K %d G_date %d G_firm %d" % (X.shape[0], X.shape[1], len(set(date)), len(set(firm))))
rej = np.zeros((2, 2))
done = 0
while done < R:
    n = min(2000, R - done)
    Y = rng.standard_normal((X.shape[0], n))
    B, V, Vd, Vf, df2, df1 = twoway(X, Y, date, firm, [j5, j6])
    for i in range(2):
        v = V[i, i].copy()
        bad = v <= 0
        v[bad] = np.maximum(Vd[i, i][bad], Vf[i, i][bad])
        t2 = B[i] / np.sqrt(v)
        t1 = B[i] / np.sqrt(Vd[i, i])
        rej[i, 0] += (2 * stats.t.sf(np.abs(t2), df2) <= 0.05).sum()
        rej[i, 1] += (2 * stats.t.sf(np.abs(t1), df1) <= 0.05).sum()
    done += n
se = lambda r: 100 * np.sqrt(r * (1 - r) / R)
for i, h in enumerate(("H5", "H6")):
    r2, r1 = rej[i] / R
    print(f"{h}: two-way {100 * r2:.2f}% (se {se(r2):.2f}), one-way date {100 * r1:.2f}% over {R}")
# H7
h7 = drivers.h7_inputs(f, "evar_m1")
x = h7["x"]
X7 = np.column_stack([np.ones(x.size), x])
print("H7 design: n %d, min x %.3g, G_date %d G_firm %d" % (x.size, x.min(), len(set(h7["date"])), len(set(h7["firm"]))))
rej7 = np.zeros(2)
done = 0
while done < R:
    n = min(2000, R - done)
    r = np.sqrt(np.maximum(x, 0))[:, None] * rng.standard_normal((x.size, n))
    B, V, Vd, Vf, df2, df1 = twoway(X7, r ** 2, h7["date"], h7["firm"], [0, 1])
    d = B - np.array([0.0, 1.0])[:, None]
    for k, (VV, df) in enumerate(((V, df2), (Vd, df1))):
        det = VV[0, 0] * VV[1, 1] - VV[0, 1] ** 2
        quad = (VV[1, 1] * d[0] ** 2 - 2 * VV[0, 1] * d[0] * d[1] + VV[0, 0] * d[1] ** 2) / det
        F = quad / 2
        rej7[k] += (stats.f.sf(F, 2, df) <= 0.05).sum()
    done += n
print(f"H7 Wald: two-way {100 * rej7[0] / R:.2f}% (se {se(rej7[0] / R):.2f}), one-way date {100 * rej7[1] / R:.2f}% over {R}")
print("builder: H5 7.60, H6 6.50, H7 11.80 (2,000 / 2,000 / 4,000 reps); bar 6.30% at 2,000, "
      f"exact 99.5% bar at {R}: {100 * stats.binom.ppf(0.995, R, 0.05) / R:.2f}%")
