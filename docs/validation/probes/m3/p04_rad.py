"""p04: rad_season_p for H2, the season merge, and whether H2's Holm pass depends on the cut (4a-4c).

Own enumeration and merge (no import of clustering). Prints aggregates only.
--falsify: 200 sampled sign vectors instead of the full enumeration.
Run: uv run --frozen --no-sync python docs/validation/probes/m3/p04_rad.py [--falsify]
"""
import itertools
import sys

import numpy as np
import pandas as pd
from statsmodels.stats.multitest import multipletests

FALSIFY = "--falsify" in sys.argv
SD = "/home/rajib2k5/data/vol-projects/earnings-vol-study/cache/stage/94065662cd46610c/"
em = pd.read_parquet(SD + "event_measures.parquet")
ev = pd.read_parquet(SD + "events.parquet")
sess = pd.read_parquet(SD + "session.parquet")["session_date"].tolist()
sidx = {d: i for i, d in enumerate(sess)}
x = em.merge(ev, on="event_id")


def merge(season, d0, k=10):
    cl = np.array(season, dtype=object)
    while True:
        keys = sorted(set(cl))
        cnt = {q: (cl == q).sum() for q in keys}
        small = [q for q in keys if cnt[q] < k]
        if not small or len(keys) == 1:
            return cl
        q = small[0]
        j = keys.index(q)
        med = {z: np.median(d0[cl == z]) for z in keys}
        nb = [keys[i] for i in (j - 1, j + 1) if 0 <= i < len(keys)]
        cl[cl == q] = min(nb, key=lambda z: (abs(med[z] - med[q]), z))


def cr1_t(A, g):
    A = np.asarray(A, float)
    u = A - A.mean()
    keys = sorted(set(g))
    s = np.array([u[g == q].sum() for q in keys])
    G = len(keys)
    return A.mean() / np.sqrt(G / (G - 1) * (s ** 2).sum() / A.size ** 2)


def rad_p(A, g, sample=None, rng=None):
    keys = sorted(set(g))
    G = len(keys)
    t0 = cr1_t(A, g)
    vecs = list(itertools.product((-1, 1), repeat=G)) if sample is None else \
        [tuple(rng.choice((-1, 1), G)) for _ in range(sample)]
    hits = 0
    for v in vecs:
        sign = dict(zip(keys, v))
        As = A * np.array([sign[q] for q in g])
        hits += abs(cr1_t(As, g)) >= abs(t0) - 1e-12
    return hits / len(vecs), len(vecs), G


h2 = x[(x["sample"] == "daily") & x["eligible_runup"]].copy()
A = h2["runup_cboe"].to_numpy(float)
d0 = np.array([sidx[d] for d in h2["day0_session"]], float)
raw = h2["season"].to_numpy(object)
cl = merge(raw, d0)
sizes = pd.Series(cl).value_counts().sort_index()
print(f"4b RUNUP set n {len(h2)}; raw seasons {pd.Series(raw).value_counts().sort_index().to_dict()}")
print(f"4b merged seasons ({sizes.size}): {sizes.to_dict()}; max/min = {sizes.max()}/{sizes.min()} = "
      f"{sizes.max() / sizes.min():.2f} -> unbalanced {sizes.max() > 1.5 * sizes.min()}")
rng = np.random.default_rng(0)
p, nv, G = rad_p(A, cl, sample=200 if FALSIFY else None, rng=rng)
print(f"4a own rad_season_p: G {G}, vectors {nv}, p {p:.6f} (floor 2/2^G = {2 / 2 ** G:.6f}); "
      f"one-way t {cr1_t(A, cl):.2f}; all 8 season means > 0: {all(A[cl == q].mean() > 0 for q in set(cl))}")
if FALSIFY:
    sys.exit(1 if nv != 2 ** G else 0)

# 4c: the Oct-2026 tail merged into its neighbour (what ADR 0005 §2b at HEAD expected)
last = sizes.index[-1]
cl7 = cl.copy()
prev = sizes.index[-2]
cl7[cl7 == last] = prev
s7 = pd.Series(cl7).value_counts().sort_index()
p7, nv7, G7 = rad_p(A, cl7)
unb7 = s7.max() > 1.5 * s7.min()
print(f"4c tail '{last}' merged into '{prev}': G {G7}, sizes {s7.to_dict()}, unbalanced {unb7}, rad p {p7:.6f}")
# the H1, H3, H4 primary p-values as reported, H5-H7 at 1
others = {"H1": 6.35e-23, "H3": 0.696, "H4": 0.764, "H5": 1.0, "H6": 1.0, "H7": 1.0}
for label, ph2 in (("G=8 (as built)", p), ("G=7 (tail merged)", p7)):
    pv = [others["H1"], ph2, others["H3"], others["H4"], 1, 1, 1]
    rej, adj, _, _ = multipletests(pv, alpha=0.05, method="holm")
    print(f"4c Holm with H2 p from {label}: H2 adjusted {adj[1]:.4f}, rejected {bool(rej[1])}")
# 4c': drop the tail entirely (an RUNUP set ending where PERSIST_10's does)
keep = cl != last
pk, _, Gk = rad_p(A[keep], merge(raw[keep], d0[keep]))
sk = pd.Series(merge(raw[keep], d0[keep])).value_counts()
print(f"4c without the tail: G {Gk}, unbalanced {sk.max() > 1.5 * sk.min()}, rad p {pk:.6f}")
