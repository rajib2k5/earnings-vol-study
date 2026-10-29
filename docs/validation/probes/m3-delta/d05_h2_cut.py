"""d05: H2's season-cut counterfactual (delta claim 7), recomputed without the package's stats code.

From the stage tables: the daily RUNUP set (eligible_runup, runup_cboe finite), the raw seasons, my own merge of
small seasons (< 10 events into the neighbour with the nearest median day 0), then the cut: the last merged season
into the one before. My own Rademacher enumeration of the one-sample t over season sums (all 2^G sign vectors,
p = share with |t*| >= |t|), and my own Holm over H1..H7 with H5-H7 at 1. Aggregates only: season sizes, signs
of the season means, p-values. Compared with the committed results rows.
Run: uv run --frozen --no-sync python docs/validation/probes/m3-delta/d05_h2_cut.py
"""
import itertools

import numpy as np
import pandas as pd

SD = "/home/rajib2k5/data/vol-projects/earnings-vol-study/cache/stage/94065662cd46610c/"
em = pd.read_parquet(SD + "event_measures.parquet")
ev = pd.read_parquet(SD + "events.parquet")
x = em.merge(ev, on="event_id")
x = x[(x["sample"] == "daily") & x.eligible_runup.astype(bool) & x.runup_cboe.notna()].copy()
x["d0"] = pd.to_datetime(x.day0_session).map(pd.Timestamp.toordinal)
cl = x.season.astype(str).to_numpy(object)
while True:
    keys = sorted(set(cl))
    cnt = {k: (cl == k).sum() for k in keys}
    small = [k for k in keys if cnt[k] < 10]
    if not small or len(keys) == 1:
        break
    k = small[0]
    j = keys.index(k)
    med = {q: np.median(x.d0.to_numpy()[cl == q]) for q in keys}
    nb = [keys[i] for i in (j - 1, j + 1) if 0 <= i < len(keys)]
    cl[cl == k] = min(nb, key=lambda q: (abs(med[q] - med[k]), q))
A = x.runup_cboe.to_numpy(float)


def rad_p(a, g):
    keys = sorted(set(g))
    gi = np.array([keys.index(v) for v in g])
    n, G = a.size, len(keys)
    best = None
    t_obs = None
    count = 0
    for signs in itertools.product((-1.0, 1.0), repeat=G):
        s = np.array(signs)[gi]
        b = s * a
        m = b.mean()
        u = np.bincount(gi, b - m, G)
        se = np.sqrt(G / (G - 1) * (u ** 2).sum()) / n
        t = m / se
        if all(v == 1.0 for v in signs):
            t_obs = t
        best = (best or []) + [t]
    tt = np.abs(np.array(best))
    return float((tt >= abs(t_obs) - 1e-12).mean()), G


for label, g in (("as built", cl), ("cut", None)):
    if g is None:
        keys = sorted(set(cl))
        g = cl.copy()
        g[g == keys[-1]] = keys[-2]
        print(f"cut: {keys[-1]} into {keys[-2]}")
    keys = sorted(set(g))
    sizes = [int((g == k).sum()) for k in keys]
    signs = ["+" if A[g == k].mean() > 0 else "-" for k in keys]
    p, G = rad_p(A, g)
    print(f"{label}: G {G}, sizes {sizes}, unbalanced {max(sizes) > 1.5 * min(sizes)}, season-mean signs {''.join(signs)}, "
          f"own rad p {p:.6f} (floor 2/2^G {2 / 2 ** G:.6f})")

R = pd.read_parquet("data/derived/results.parquet")
E = R[(R.family == "event_test") & (R.adjustment == "market")]
prim = E[E.role == "primary"].set_index("hypothesis")
cut = E[E.subgroup_key == "season_cut"].iloc[0]
pv = {h: (float(prim.loc[h, "p_value"]) if h in prim.index else 1.0) for h in ["H1", "H2", "H3", "H4", "H5", "H6", "H7"]}


def holm(pv):
    names = sorted(pv, key=lambda k: pv[k])
    out, run = {}, 0.0
    for r, k in enumerate(names):
        run = max(run, min(1.0, (len(names) - r) * pv[k]))
        out[k] = run
    return out


print(f"results: H2 primary p {prim.loc['H2', 'p_value']:.6f} p_holm {prim.loc['H2', 'p_holm']:.6f}; own Holm {holm(pv)['H2']:.6f}")
pv["H2"] = float(cut.p_value)
print(f"results: cut row {cut.subgroup_value} G {cut.n_clusters} p {cut.p_value:.6f} p_holm {cut.p_holm:.6f}; own Holm {holm(pv)['H2']:.6f}")
