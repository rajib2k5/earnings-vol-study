"""Delta-2 probe e4 (claim 4): the Rademacher floor and Holm's fifth step, m = 7, G = 7 (ADR 0005 :428-437, :714-717).

Part A. Full enumeration of all 2^G Rademacher sign vectors for a wild cluster RESTRICTED bootstrap of an
intercept-only mean (H0: mean = 0, so the restricted residuals are y itself), CR1 cluster t. Over many random data
sets the smallest attainable two-sided p must be 2 / 2^G (the identity and its negation tie with |t|).
Part B. statsmodels multipletests(method="holm") with the floor and k = 0..5 smaller p-values that each pass their
own step. ADR: rejected only with k >= 4; adjusted p 0.0469 at k = 4, 0.0625 at k = 3.
Falsifier: the old "fourth step" text predicts rejection at k = 3; the run must contradict it.
Part C (context, not part of the claim): the floor at G = 6 and G = 8.

Run from the repository root: .venv/bin/python docs/validation/probes/m0-delta2/e4_holm.py
"""
import itertools

import numpy as np
from statsmodels.stats.multitest import multipletests


def cr1_t(y, cl, G):
    n = len(y)
    m = y.mean()
    u = y - m
    s = np.array([u[cl == g].sum() for g in range(G)])
    v = (G / (G - 1)) * ((n - 1) / (n - 1)) * (s ** 2).sum() / n ** 2
    return m / np.sqrt(v)


def wcr_min_p(G, reps=200, seed=1):
    rng = np.random.default_rng(seed)
    signs = np.array(list(itertools.product([-1, 1], repeat=G)))
    mins = []
    for _ in range(reps):
        sizes = rng.integers(8, 15, G)
        cl = np.repeat(np.arange(G), sizes)
        y = rng.standard_t(4, cl.size) + rng.normal(0, 0.5, G)[cl] + rng.normal(0.8, 0.2)
        t0 = abs(cr1_t(y, cl, G))
        tb = np.array([abs(cr1_t(y * w[cl], cl, G)) for w in signs])
        mins.append((tb >= t0 - 1e-12).mean())
    return min(mins), 2 / 2 ** G


p_min, floor = wcr_min_p(7)
print(f"A  G=7: smallest p over 200 strong-signal data sets = {p_min:.6f}; 2/128 = {floor:.6f}; equal: "
      f"{np.isclose(p_min, floor)}")

floor = 2 / 128
others_ok = [0.001, 0.002, 0.003, 0.004, 0.005]
print("B  thresholds 0.05/(8-k):", [round(0.05 / (8 - k), 4) for k in range(1, 8)])
res = {}
for k in range(0, 6):
    p = others_ok[:k] + [floor] + [0.5] * (6 - k)
    rej, padj, _, _ = multipletests(p, alpha=0.05, method="holm")
    i = k  # position of the floor
    res[k] = (bool(rej[i]), float(padj[i]))
    print(f"   k={k} smaller p-values: floor rejected={rej[i]}, Holm-adjusted p={padj[i]:.4f}")
ok = (not res[3][0]) and res[4][0] and np.isclose(res[4][1], 0.046875) and np.isclose(res[3][1], 0.0625) \
    and all(not res[k][0] for k in range(4))
print("   falsifier ('fourth step' => rejected at k=3):", "contradicted" if not res[3][0] else "NOT contradicted")
for G in (6, 8):
    f = 2 / 2 ** G
    first = next((k for k in range(1, 8) if f <= 0.05 / (8 - k)), None)
    print(f"C  G={G}: floor {f:.5f}, first Holm step it can pass: {first}")
print("RESULT:", "PASS" if ok and np.isclose(p_min, 2 / 128) else "FAIL")
raise SystemExit(0 if ok else 1)
