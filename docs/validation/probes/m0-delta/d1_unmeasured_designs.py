"""Delta probe 1d: is the H2/H3 primary correctly sized in the cases ADR 0005's own routing rules send it, but that
`h2h3_followup_sim.py` never simulated?

ADR 0005 §2b routing: two-way season x firm CR1 t (t_{min G - 1}) unless the largest season is more than 1.5x the
smallest; then `rad_season_p` (one-way, season sign flips, no firm dimension). Simulated by the repo: balanced seasons
(ratio 52/49 = 1.06) and one unbalanced design (3 of 7 seasons cut to 12, ratio 4.3). Not simulated:

  U1  D2, 3 of 7 seasons cut to 35 events: ratio 52/35 = 1.49 < 1.5, so the TWO-WAY t is the primary.
  U2  D2, 3 of 7 seasons cut to 12 (the repo's unbalanced design) + firm drift sd 0.0015: routed to `rad_season_p`.
  U3  D2, unbalanced (12) + random firm effects sd 0.03 (shifts PERSIST_10 per firm): routed to `rad_season_p`.
  U4  D2 balanced, two-way t with NORMAL critical values (1.96) instead of t_6 = 2.447. ADR 0005 §5 says G1 is
      "expected to" catch this mutation, "not yet measured".
  R0  reproduction control: the repo's 'D2, unbalanced seasons' row must come out at its kept 9.12 / 8.95 (two-way)
      and 5.22 / 5.65 (rad_enum) with the repo's seeds.

Uses the event design, generator and statistics of research/prototypes/h2h3_size_sim.py and h2h3_followup_sim.py
unchanged (imported, not copied). 4,000 replications per design; exact binomial 99% band [4.12, 5.90]%; the ADR's G1
bar at 2,000 replications is 6.30%.
Run: PYTHONDONTWRITEBYTECODE=1 uv run --no-sync --frozen python docs/validation/probes/m0-delta/d1_unmeasured_designs.py
"""
import os
import sys
from multiprocessing import Pool
from pathlib import Path

for _v in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_v] = '1'
import numpy as np  # noqa: E402
from scipy import stats  # noqa: E402

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'research' / 'prototypes'))
import h2h3_followup_sim as fu  # noqa: E402
import h2h3_size_sim as base  # noqa: E402

DES = base.DES
REPS = 4000


def keep_cut(n_keep, seed=99):
    rng = np.random.default_rng(seed)
    seasons = sorted(set(DES['season']))
    keep = np.ones(DES['N'], bool)
    for q in (seasons[1], seasons[3], seasons[5]):
        idx = np.flatnonzero(DES['season'] == q)
        keep[rng.choice(idx, idx.size - n_keep, replace=False)] = False
    return keep


KEEP35 = keep_cut(35)
assert (KEEP35 == keep_cut(35)).all()
assert (fu.KEEP_UNBAL == keep_cut(12)).all(), 'the repo unbalanced mask must be reproduced exactly'


def twoway_normal(A, season, firm):
    N = A.size; u = A - A.mean()
    _, gs = np.unique(season, return_inverse=True); G = gs.max() + 1
    _, gf = np.unique(firm, return_inverse=True); F = gf.max() + 1
    _, gi = np.unique(gs * 10000 + gf, return_inverse=True); I_ = gi.max() + 1
    VA, VB, VI = (k / (k - 1) * (np.bincount(g, u, k) ** 2).sum() / N ** 2 for g, k in ((gs, G), (gf, F), (gi, I_)))
    V = VA + VB - VI
    if V <= 0:
        V = max(VA, VB)  # ADR 0005 §2b fallback, as in the prototype
    return abs(A.mean() / np.sqrt(V)) > stats.norm.ppf(0.975)


def one_rep(args):
    seed, p, keep, df_cr2 = args
    rng = np.random.default_rng(seed)
    x = base.gen(rng, p)
    if p.get('drift'):
        d = rng.normal(0, p['drift'], x.shape[0])
        x = x + d[:, None] * np.arange(x.shape[1])[None]
    if p.get('firm_fx'):
        mu_ev = rng.normal(0, p['firm_fx'], x.shape[0])[DES['firm']]
        for i, (fi, d, _) in enumerate(DES['ev']):
            x[fi, d:d + 11] += mu_ev[i]
    e = np.zeros_like(x); e[:, 1:] = np.diff(x, axis=1)
    E = e[DES['firm']]
    res = {}
    for m in ('runup', 'persist_10'):
        A = (DES['W'][m] * E).sum(1)
        r = fu.cl_stats(A[keep], DES['season'][keep], DES['firm'][keep], rng, df_cr2)
        r['twoway_normal'] = twoway_normal(A[keep], DES['season'][keep], DES['firm'][keep])
        res[m] = r
    return res


DESIGNS = [
    # name, params, keep mask, seed offset (R0 uses the repo's own seed offset for its 4th design: di = 3)
    ('R0 repo control: D2, unbalanced 12 (repo seeds)', fu.D2, fu.KEEP_UNBAL, 3),
    ('U1 D2, 3 of 7 seasons cut to 35 (ratio 1.49)', fu.D2, KEEP35, 101),
    ('U2 D2, unbalanced 12 + firm drift sd 0.0015', dict(fu.D2, drift=0.0015), fu.KEEP_UNBAL, 102),
    ('U3 D2, unbalanced 12 + random firm effects sd 0.03', dict(fu.D2, firm_fx=0.03), fu.KEEP_UNBAL, 103),
    ('U4 D2 balanced (normal critical values for two-way)', fu.D2, np.ones(DES['N'], bool), 104),
    # U5: the repo's D2 row (PERSIST_10 two-way 6.05%) re-estimated with 4 x 4,000 fresh seeds = 16,000 replications
    ('U5a D2 balanced, fresh seeds', fu.D2, np.ones(DES['N'], bool), 201),
    ('U5b D2 balanced, fresh seeds', fu.D2, np.ones(DES['N'], bool), 202),
    ('U5c D2 balanced, fresh seeds', fu.D2, np.ones(DES['N'], bool), 203),
    ('U5d D2 balanced, fresh seeds', fu.D2, np.ones(DES['N'], bool), 204),
]

if __name__ == '__main__':
    lo, hi = (100 * stats.binom.ppf(q, REPS, .05) / REPS for q in (.005, .995))
    hi2000 = 100 * stats.binom.ppf(.995, 2000, .05) / 2000
    print(f"reps {REPS}; exact binomial 99% band [{lo:.2f}, {hi:.2f}]%; G1 bar at 2,000 reps {hi2000:.2f}%")
    with Pool(20) as pool:
        for name, p, keep, off in DESIGNS:
            sizes = np.bincount(np.unique(DES['season'][keep], return_inverse=True)[1])
            df_cr2 = fu.ik_df(DES['season'][keep])
            res = pool.map(one_rep, [((off + 1) * 1000003 + r, p, keep, df_cr2) for r in range(REPS)], chunksize=20)
            print(f"\n[{name}] N = {keep.sum()}, season sizes {sorted(sizes.tolist())}, "
                  f"max/min = {sizes.max() / sizes.min():.3f} -> routed to "
                  f"{'rad_season_p' if sizes.max() > 1.5 * sizes.min() else 'two-way t'}")
            for m in ('runup', 'persist_10'):
                row = {s: 100 * np.mean([r[m][s] for r in res]) for s in ('cr1_season', 'twoway', 'rad_enum', 'twoway_normal')}
                print(f"  {m:11s} " + '  '.join(f"{k} {v:5.2f}%" for k, v in row.items()))
