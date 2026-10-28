"""Follow-up to h2h3_size_sim.py, after the adversarial review of the ADR 0005 revision (2026-10-28).

The review reported that the season-clustered CR1 t (cluster_season_t, G = 7) over-rejects
(a) when firms' abnormal log IV drifts (ADR 0004 fits no intercept, so a firm-specific trend enters every event of
    that firm with the same sign, which makes seasons dependent through firms), and
(b) when seasons are unbalanced (3 of 7 seasons cut to 12 events),
and that the declared fallback (Webb wild cluster restricted bootstrap) is more liberal than CR1.
This script re-measures those designs and the candidate fixes, on the same event design as h2h3_size_sim.py.

Statistics (RUNUP / PERSIST_10, two-sided 5%, equal-weighted mean of raw A_i):
  cr1_season   CR1 by merged season, t_{G-1}                        (the revised ADR's primary)
  cr2_season   CR2 (Bell-McCaffrey), Imbens-Kolesar degrees of freedom. For an intercept-only model CR2 has the
               closed form V = sum_g S_g^2 / (1 - n_g/N) / N^2; with balanced clusters it equals CR1.
  twoway       Cameron-Gelbach-Miller two-way season x firm: V = V_season + V_firm - V_season&firm (each CR1),
               t_{min(G)-1}; if V <= 0, max(V_season, V_firm)
  rad_enum     wild cluster restricted bootstrap by season with ALL 2^G Rademacher sign vectors (exact
               randomisation p-value when seasons are independent and symmetric). With G = 7 the smallest attainable
               two-sided p is 2/128 = 0.0156, so it can never pass a Holm step below that.
  webb_wcr     Webb six-point restricted bootstrap, 999 draws (the revised ADR's G1 fallback)
CRUSH (one-session): cr1_date (CR1 by day-0 date, t_{G-1}) and twoway_df (two-way day-0 date x firm, t_{min G - 1}).
  The firm-effect designs add a firm-specific level step on [0, +10] (CRUSH_i gets mu_f), with mu_f ~ N(0, sd) drawn
  per firm in every replication and NOT centred: the expected mean is 0, but the events of one firm share mu_f
  (superpopulation inference over firms, as for the drift designs). They also shift PERSIST_10 by mu_f.
  (A first version centred mu exactly within each replication; that removes the firm component from the mean's
  variance and made every estimator conservative, so it tested nothing.)
Designs: base D2 of h2h3_size_sim.py (random-walk levels, same-date rho 0.10, quote noise 0.5), plus
  drift sd 0.0005 / 0.0015 per session (firm-specific linear trend in abnormal log IV, mean 0 across firms),
  unbalanced (3 of 7 seasons subsampled to 12 events, fixed), D4 (mean reversion), D4 + drift 0.0005, the firm-effect
  designs below, and power designs P1, P2, P4 (as in h2h3_size_sim.py; CRUSH rows there are size).
Run: uv run --no-sync --frozen python research/prototypes/h2h3_followup_sim.py [reps] > research/prototypes/h2h3_followup_sim.out.txt
"""
import itertools
import os

for _v in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_v] = '1'
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
import h2h3_size_sim as base  # noqa: E402  (same event design and generator)

REPS = int(next((a for a in sys.argv[1:] if a.isdigit()), 4000))
DES = base.DES
WEBB = base.WEBB

# fixed unbalanced subset: in 3 of the 7 season clusters keep 12 events
_rng = np.random.default_rng(99)
_seasons = sorted(set(DES['season']))
_cut = [_seasons[1], _seasons[3], _seasons[5]]
KEEP_UNBAL = np.ones(DES['N'], bool)
for q in _cut:
    idx = np.flatnonzero(DES['season'] == q)
    drop = _rng.choice(idx, idx.size - 12, replace=False)
    KEEP_UNBAL[drop] = False


def ik_df(groups):
    """Imbens-Kolesar (2016) / Bell-McCaffrey degrees of freedom for CR2, intercept-only model."""
    N = groups.size
    _, gi = np.unique(groups, return_inverse=True); G = gi.max() + 1
    ng = np.bincount(gi, minlength=G)
    # V = u' Q u with Q = sum_g c_g 1_g 1_g' / N^2, c_g = 1/(1 - n_g/N); working model u ~ N(0, M), M = I - 11'/N
    Q = np.zeros((N, N))
    for g in range(G):
        m = gi == g
        Q[np.ix_(m, m)] = 1.0 / (1 - ng[g] / N) / N ** 2
    M = np.eye(N) - np.ones((N, N)) / N
    lam = np.linalg.eigvalsh(M @ Q @ M)
    return lam.sum() ** 2 / (lam ** 2).sum()


def cl_stats(A, season, firm, rng, df_cr2):
    N = A.size
    out = {}
    u = A - A.mean()
    _, gs = np.unique(season, return_inverse=True); G = gs.max() + 1
    Sg = np.bincount(gs, u, G); ng = np.bincount(gs, None, G)
    V1 = G / (G - 1) * (Sg ** 2).sum() / N ** 2
    t1 = A.mean() / np.sqrt(V1)
    out['cr1_season'] = abs(t1) > stats.t.ppf(0.975, G - 1)
    V2 = ((Sg ** 2) / (1 - ng / N)).sum() / N ** 2
    out['cr2_season'] = abs(A.mean() / np.sqrt(V2)) > stats.t.ppf(0.975, df_cr2)
    _, gf = np.unique(firm, return_inverse=True); F = gf.max() + 1
    Sf = np.bincount(gf, u, F)
    Vf = F / (F - 1) * (Sf ** 2).sum() / N ** 2
    inter = gs * 10000 + gf
    _, gi = np.unique(inter, return_inverse=True); I_ = gi.max() + 1
    Si = np.bincount(gi, u, I_)
    Vi = I_ / (I_ - 1) * (Si ** 2).sum() / N ** 2
    Vtw = V1 + Vf - Vi
    if Vtw <= 0:
        Vtw = max(V1, Vf)
    out['twoway'] = abs(A.mean() / np.sqrt(Vtw)) > stats.t.ppf(0.975, min(G, F) - 1)
    # restricted wild bootstraps: residuals under H0 are A_i themselves
    S0 = np.bincount(gs, A, G)

    def tstar(v):
        Ss = v * S0[None]
        m = Ss.sum(1) / N
        Vs = G / (G - 1) * ((Ss - ng[None] * m[:, None]) ** 2).sum(1) / N ** 2
        return np.abs(m / np.sqrt(Vs))
    signs = np.array(list(itertools.product((-1.0, 1.0), repeat=G)))
    out['rad_enum'] = (tstar(signs) >= abs(t1) - 1e-12).mean() <= 0.05
    out['webb_wcr'] = (tstar(WEBB[rng.integers(0, 6, (999, G))]) >= abs(t1)).mean() < 0.05
    return out


def crush_stats(A, d0, firm):
    N = A.size; u = A - A.mean(); out = {}
    _, gd = np.unique(d0, return_inverse=True); G = gd.max() + 1
    Vd = G / (G - 1) * (np.bincount(gd, u, G) ** 2).sum() / N ** 2
    out['cr1_date'] = abs(A.mean() / np.sqrt(Vd)) > stats.t.ppf(0.975, G - 1)
    _, gf = np.unique(firm, return_inverse=True); F = gf.max() + 1
    Vf = F / (F - 1) * (np.bincount(gf, u, F) ** 2).sum() / N ** 2
    _, gi = np.unique(d0 * 1000 + gf, return_inverse=True); I_ = gi.max() + 1
    Vi = I_ / (I_ - 1) * (np.bincount(gi, u, I_) ** 2).sum() / N ** 2
    V = Vd + Vf - Vi
    if V <= 0:
        V = max(Vd, Vf)
    out['twoway_df'] = abs(A.mean() / np.sqrt(V)) > stats.t.ppf(0.975, min(G, F) - 1)
    return out


def one_rep(args):
    seed, p, keep, df_cr2 = args
    rng = np.random.default_rng(seed)
    x = base.gen(rng, p)
    if p.get('drift'):
        d = rng.normal(0, p['drift'], x.shape[0])
        x = x + d[:, None] * np.arange(x.shape[1])[None]
    if p.get('firm_fx'):  # firm-specific level step from day 0 to +10: CRUSH_i += mu_f, random firm effects, E = 0
        mu_f = rng.normal(0, p['firm_fx'], x.shape[0])
        mu_ev = mu_f[DES['firm']]
        for i, (fi, d, _) in enumerate(DES['ev']):
            x[fi, d:d + 11] += mu_ev[i]
    e = np.zeros_like(x); e[:, 1:] = np.diff(x, axis=1)
    E = e[DES['firm']]
    res = {}
    for m in ('runup', 'persist_10'):
        A = (DES['W'][m] * E).sum(1)
        res[m] = cl_stats(A[keep], DES['season'][keep], DES['firm'][keep], rng, df_cr2)
    A = (DES['W']['crush'] * E).sum(1)
    res['crush'] = crush_stats(A[keep], DES['d0'][keep], DES['firm'][keep])
    return res


D2 = dict(phi=1, rho_m=0.10, rho_s=0.0, noise=0.5, sig_disp=0.0, jump_k=0.0)
D4 = dict(phi=0.98, rho_m=0.05, rho_s=0.15, noise=0.5, sig_disp=0.4, jump_k=3.0)
DESIGNS = [
    ('D2 base (random walk, rho 0.10, noise 0.5)', D2, 'all'),
    ('D2 + firm drift sd 0.0005/session', dict(D2, drift=0.0005), 'all'),
    ('D2 + firm drift sd 0.0015/session', dict(D2, drift=0.0015), 'all'),
    ('D2, unbalanced seasons (3 of 7 cut to 12 events)', D2, 'unbal'),
    ('D4 (mean reversion)', D4, 'all'),
    ('D4 + firm drift sd 0.0005/session', dict(D4, drift=0.0005), 'all'),
    ('D2 + random firm effects on CRUSH, sd 0.01', dict(D2, firm_fx=0.01), 'all'),
    ('D2 + random firm effects on CRUSH, sd 0.03', dict(D2, firm_fx=0.03), 'all'),
    ('D4 + random firm effects on CRUSH, sd 0.03', dict(D4, firm_fx=0.03), 'all'),
    ('P1 power: D4 + shift mu=0.03 on RUNUP/PERSIST_10', dict(D4, mu=0.03), 'all'),
    ('P2 power: D4 + shift mu=0.05', dict(D4, mu=0.05), 'all'),
    ('P4 power: D2 + shift mu=0.03', dict(D2, mu=0.03), 'all'),
]
STATS = ['cr1_season', 'cr2_season', 'twoway', 'rad_enum', 'webb_wcr']

if __name__ == '__main__':
    t0 = time.time()
    keep_all = np.ones(DES['N'], bool)
    dfs = {'all': ik_df(DES['season']), 'unbal': ik_df(DES['season'][KEEP_UNBAL])}
    print(f"reps {REPS}; MC se at 5% {100*np.sqrt(.05*.95/REPS):.2f} pp; exact binomial 99% band "
          f"[{100*stats.binom.ppf(.005, REPS, .05)/REPS:.2f}, {100*stats.binom.ppf(.995, REPS, .05)/REPS:.2f}]%")
    print(f"CR2 Imbens-Kolesar df: balanced design {dfs['all']:.2f} (G-1 = {len(set(DES['season']))-1}); "
          f"unbalanced design {dfs['unbal']:.2f}, N = {KEEP_UNBAL.sum()}")
    with Pool(20) as pool:
        for di, (name, p, which) in enumerate(DESIGNS):
            keep = keep_all if which == 'all' else KEEP_UNBAL
            res = pool.map(one_rep, [((di + 1) * 1000003 + r, p, keep, dfs[which]) for r in range(REPS)], chunksize=20)
            print(f"\n[{name}]")
            print('  ' + ' ' * 11 + ''.join(f'{s:>12s}' for s in STATS))
            for m in ('runup', 'persist_10'):
                print(f"  {m:11s}" + ''.join(f"{100*np.mean([r[m][s] for r in res]):11.2f}%" for s in STATS))
            print(f"  {'crush':11s}" + ''.join(f"{k:>12s}{100*np.mean([r['crush'][k] for r in res]):6.2f}%" for k in ('cr1_date', 'twoway_df')))
    print(f"\nelapsed {time.time()-t0:.0f}s")
