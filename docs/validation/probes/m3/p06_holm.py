"""p06: Holm over H1-H7 with untested at p = 1 is an upper bound and equals statsmodels (claim 6).
--falsify: the package's holm with (m - rank) replaced by (m - rank - 1) via a local copy -> mismatches.
Run: uv run --frozen --no-sync python docs/validation/probes/m3/p06_holm.py [--falsify]
"""
import sys

import numpy as np
from statsmodels.stats.multitest import multipletests

from earnings_vol.stats.multiple import holm

FALSIFY = "--falsify" in sys.argv


def holm_bad(p):
    names = list(p)
    pv = np.array([1.0 if p[k] is None else p[k] for k in names])
    order = np.argsort(pv, kind="mergesort")
    adj = np.empty(pv.size)
    run = 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (pv.size - rank - 1 or 1) * pv[i]))
        adj[i] = run
    return dict(zip(names, adj))


H = holm_bad if FALSIFY else holm
rng = np.random.default_rng(6)
viol_bound, viol_sm, n = 0, 0, 0
for _ in range(2000):
    p14 = rng.uniform(0, 0.05, 4) ** rng.uniform(1, 4)
    base = H({f"H{i+1}": float(p14[i]) for i in range(4)} | {"H5": None, "H6": None, "H7": None})
    p57 = rng.uniform(0, 1, 3) ** rng.uniform(0.2, 5)
    full = H({f"H{i+1}": float(p14[i]) for i in range(4)} | {f"H{i+5}": float(p57[i]) for i in range(3)})
    viol_bound += sum(full[f"H{i+1}"] > base[f"H{i+1}"] + 1e-15 for i in range(4))
    sm = multipletests(list(p14) + list(p57), method="holm")[1]
    viol_sm += int(np.max(np.abs(np.array([full[f"H{i+1}"] for i in range(7)]) - sm)) > 1e-12)
    n += 1
print(f"6 {n} draws: adjusted p(H1-H4) with real H5-H7 above the p=1 value: {viol_bound}; "
      f"draws differing from statsmodels holm: {viol_sm}")
rep = H({"H1": 6.35e-23, "H2": 2 / 256, "H3": 0.696, "H4": 0.764, "H5": None, "H6": None, "H7": None})
print("6 reported family:", {k: round(v, 4) for k, v in rep.items()})
sys.exit(1 if (viol_sm or viol_bound) else 0)
