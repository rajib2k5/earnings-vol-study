"""Size and power of candidate primary statistics for H2 (RUNUP) and H3 (PERSIST_10), with CRUSH as a control.

Written for the milestone-0 methodology review (2026-10-28, docs/validation/m0-methodology-ledger.md, claim 7d and N7).
It is the early run of ADR 0005 §5 gate G1. It is a prototype, not the milestone-3 test.

Design (the real daily-sample design, not a toy):
- Event dates: the day-0 dates of the 30 large caps in data/derived/earnings_calendar_30_large_caps.json
  (ADR 0002 day-0 rule: AMC -> next session; BMO/NULL -> D if a session, else the next session), plus 20 synthetic firms.
  Each synthetic firm copies a random real firm's schedule and sector, with each day 0 jittered by U{-3..3} sessions.
  Events in the test: day 0 in [2024-12-05, 2026-10-12] (PERSIST_10 needs +10 <= 2026-10-26). Every other event of the
  same firm still removes its [-21, +10] zone from baselines (ADR 0004 §1). The design is fixed across replications.
- Baseline: [-60, -22] minus same-firm zones; s_i = sd (ddof=1) of the one-session changes with both ends in B_i.
- Measures (exact ramp representation, ADR 0005 §1): RUNUP = ALIV_-1, PERSIST_10 = ALIV_+10, CRUSH = e_0.
  The identity A_i = x_target - mean_B x = sum_t a_t e_t is asserted on the first replication.
- Simulated series are already market-adjusted (beta known), so e_it is the abnormal one-session change.
  latent l_it = phi l_i,t-1 + sig_i * (sqrt(rho_m) f_t + sqrt(rho_s) g_sector,t + sqrt(1-rho_m-rho_s) u_it)
  observed x_it = l_it + noise_ratio * sig_i * eps_it   (quote noise -> MA(1) in changes)
  event-induced variance: a jump N(0, (jump_k sig_i)^2) enters l at every event's day 0 (mean 0, decays with phi).
  hetero: a level step mu_i on [-21, +10] with mu_i = c (sig_i - mean over test events), so the equal-weighted mean
  of the true RUNUP and PERSIST_10 is exactly 0 while the 1/s_i-weighted mean is not (item 5 of the review).
  power: the same step with a common mu (P1-P3 on D4, P4 on D2). The step is added to x on [-21, +10], so it moves
  RUNUP and PERSIST_10 by mu and leaves CRUSH unchanged (CRUSH rows in P designs are size, not power).
- Statistics (two-sided 5%). Every input is estimated in each replication:
  bmp        BMP t, SA_i = A_i / (s_i sqrt(a_i' Rhat a_i)) with the revised Rhat (pooled, UNCENTRED, lags 1..10), t_{N-1}
  kp_ow      ADR 0005 §2d at milestone 0, with Rhat read as pooled and per-baseline DEMEANED (the milestone-0 text
             left the centring open; this is one reading of it), lags 1..10 (Bartlett if not PSD); rho_ij = Pearson over >= 20 shared baseline changes, else same-sector mean, else all-pairs mean;
             omega_ij = a_i'a_j / sqrt(a_i'Rhat a_i a_j'Rhat a_j); rbar = max(0, mean omega*rho); t_{N-1}
  kp_ow_raw  the same with Rhat uncentred (mean-zero model), the R-hat ADR 0005 §1 specifies after the review
  kpp        KPP (2018) average-overlap form as reported by Pynnonen (2022) §4: nu_ij = a_i'a_j / sqrt(a_i'a_i a_j'a_j)
             (= tau_ij / tau for uniform windows), nubar over pairs, rhobar from Pynnonen (2022) eq. 32 on the
             standardised baseline changes (calendar-day clustering), t_BMP * sqrt((1-nubar rhobar)/(1+(N-1) nubar rhobar))
  cs         cross-sectional t on raw A_i, t_{N-1}
  cl_date    CR1 clustered by day-0 date, t_{G-1}
  cl_week    CR1 clustered by ISO week of day 0, t_{G-1}
  cl_season  CR1 clustered by calendar quarter of day 0 (events.season), t_{G-1}
  wcb_season wild cluster restricted bootstrap by season, Webb 6-point weights, 999 draws
             (seasons with < 10 events are merged into the nearest neighbouring season, for both cl_season and wcb)
  sa_season  BMP's standardised SA_i (precision-weighted estimand), CR1 clustered by season, t_{G-1}
  cs_ow      raw-units overlap covariance: V = s_A^2/N + sum_{i!=j} rho_fg s_i s_j G_ij / (N(N-1)), G_ij = a_i'a_j on
             the calendar axis, rho_fg = uncentred correlation of standardised baseline changes pooled per FIRM PAIR
             over every shared clean baseline date (>= 30, else sector-class mean); same-firm pairs 0; normal crit.
  dk1, dk5   calendar-time Driscoll-Kraay: c_t = (1/N) sum_i a_it e_it, V = sum c_t^2 + 2 sum_k w_k sum c_t c_{t-k},
             uniform w=1 for K=1 (dk1), Bartlett K=5 (dk5); null imposed (uncentred); normal crit.
Run: uv run --no-sync --frozen python research/prototypes/h2h3_size_sim.py [reps] > research/prototypes/h2h3_size_sim.out.txt
"""
import os

for _v in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_v] = '1'  # one BLAS thread per worker; 20 workers otherwise oversubscribe the cores ~50x
import collections
import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
REPS = int(next((a for a in sys.argv[1:] if a.isdigit()), 2000))
HOL = ['2024-01-01', '2024-01-15', '2024-02-19', '2024-03-29', '2024-05-27', '2024-06-19', '2024-07-04', '2024-09-02',
       '2024-11-28', '2024-12-25', '2025-01-01', '2025-01-09', '2025-01-20', '2025-02-17', '2025-04-18', '2025-05-26',
       '2025-06-19', '2025-07-04', '2025-09-01', '2025-11-27', '2025-12-25', '2026-01-01', '2026-01-19', '2026-02-16',
       '2026-04-03', '2026-05-25', '2026-06-19', '2026-07-03', '2026-09-07', '2026-11-26', '2026-12-25']
CAL = np.busdaycalendar(holidays=HOL)
SECTOR = {'AAPL': 'IT', 'ADBE': 'IT', 'AMD': 'IT', 'CRM': 'IT', 'CSCO': 'IT', 'IBM': 'IT', 'INTC': 'IT', 'MSFT': 'IT',
          'NVDA': 'IT', 'ORCL': 'IT', 'AMZN': 'CD', 'HD': 'CD', 'TSLA': 'CD', 'BAC': 'FIN', 'GS': 'FIN', 'JPM': 'FIN',
          'COST': 'CS', 'KO': 'CS', 'PG': 'CS', 'WMT': 'CS', 'CVX': 'EN', 'XOM': 'EN', 'DIS': 'CM', 'GOOGL': 'CM',
          'META': 'CM', 'NFLX': 'CM', 'JNJ': 'HC', 'MRK': 'HC', 'PFE': 'HC', 'UNH': 'HC'}
T0 = np.datetime64('2024-01-02')
END = np.datetime64('2026-10-26')
SESS = np.array([d for d in np.arange(T0, END + np.timedelta64(1, 'D')) if np.is_busday(d, busdaycal=CAL)])
T = SESS.size
IDX = {d: i for i, d in enumerate(SESS)}
LO, HI = IDX[np.datetime64('2024-12-05')], IDX[np.datetime64('2026-10-12')]
WEBB = np.array([-np.sqrt(1.5), -1, -np.sqrt(0.5), np.sqrt(0.5), 1, np.sqrt(1.5)])


def build_design(seed=2026):
    rows = json.load(open(ROOT / 'data/derived/earnings_calendar_30_large_caps.json'))['rows']
    by = collections.defaultdict(list)
    for r in rows:
        d = np.datetime64(r['date'])
        # ADR 0002 §2: D a session -> AMC next(D), else D; D not a session -> the first session after D, any timing.
        # (The first version rolled a non-session D forward and then added 1 for AMC: one session too late. No row of
        # the extract has a non-session D, so the outputs did not change.)
        on = np.is_busday(d, busdaycal=CAL)
        d0 = np.busday_offset(d, 1 if (on and r['when'] == 'After market close') else 0, roll='forward', busdaycal=CAL)
        if d0 in IDX:
            by[r['act_symbol']].append(IDX[d0])
    rng = np.random.default_rng(seed)
    real = sorted(by)
    firms = [(s, SECTOR[s], sorted(by[s])) for s in real]
    for k in range(20):
        tmpl = real[rng.integers(len(real))]
        d0s = sorted({int(np.clip(d + rng.integers(-3, 4), 0, T - 1)) for d in by[tmpl]})
        firms.append((f'SYN{k:02d}<{tmpl}', SECTOR[tmpl], d0s))
    sectors = sorted({f[1] for f in firms})
    ev = []  # (firm index, d0, baseline idx array)
    for fi, (_, _, d0s) in enumerate(firms):
        for d in d0s:
            if not (LO <= d <= HI):
                continue
            bad = np.zeros(T, bool)
            for o in d0s:
                if o != d:
                    bad[max(o - 21, 0):o + 11] = True
            B = np.array([u for u in range(d - 60, d - 21) if u >= 0 and not bad[u]])
            if B.size < 20:
                continue
            ev.append((fi, d, B))
    N = len(ev)
    W = {m: np.zeros((N, T)) for m in ('runup', 'persist_10', 'crush')}
    Mb = np.zeros((N, T), bool)  # baseline one-session changes: t and t-1 in B
    for i, (fi, d, B) in enumerate(ev):
        inB = np.zeros(T, bool); inB[B] = True
        Mb[i, 1:] = inB[1:] & inB[:-1]
        n_before = np.cumsum(inB) - inB  # number of B sessions strictly before t
        for m, tgt in (('runup', d - 1), ('persist_10', d + 10)):
            t = np.arange(B.min() + 1, tgt + 1)
            W[m][i, t] = n_before[t] / B.size
        W['crush'][i, d] = 1.0
    firm = np.array([e[0] for e in ev])
    d0 = np.array([e[1] for e in ev])
    sec = np.array([sectors.index(firms[f][1]) for f in firm])
    season = np.array([f"{SESS[d].astype(object).year}Q{(SESS[d].astype(object).month - 1) // 3 + 1}" for d in d0])
    week = np.array(['%d-W%02d' % SESS[d].astype(object).isocalendar()[:2] for d in d0])  # true ISO weeks (review fix:
    # the first version used numpy 'datetime64[W]', which starts weeks on Thursday)
    # ADR 0005 cluster rule: a season with < 10 events joins the neighbouring season whose median day 0 is nearest
    cl = season.copy()
    while True:
        cnt = collections.Counter(cl); small = [k for k in sorted(cnt) if cnt[k] < 10]
        if not small or len(cnt) == 1:
            break
        k = small[0]; keys = sorted(cnt); j = keys.index(k)
        med = {q: np.median(d0[cl == q]) for q in keys}
        nb = [keys[x] for x in (j - 1, j + 1) if 0 <= x < len(keys)]
        cl[cl == k] = min(nb, key=lambda q: abs(med[q] - med[k]))
    return dict(firms=firms, nf=len(firms), ev=ev, N=N, W=W, Mb=Mb, firm=firm, d0=d0, sec=sec,
                firm_sec=np.array([sectors.index(f[1]) for f in firms]), season=cl, season_raw=season, week=week,
                tgt={'runup': d0 - 1, 'persist_10': d0 + 10, 'crush': d0})


DES = build_design()


def gen(rng, p):
    nf, ns = DES['nf'], DES['firm_sec'].max() + 1
    sig = 0.03 * np.exp(rng.normal(0, p['sig_disp'], nf))
    f = rng.standard_normal(T); g = rng.standard_normal((ns, T)); u = rng.standard_normal((nf, T))
    eta = sig[:, None] * (np.sqrt(p['rho_m']) * f[None] + np.sqrt(p['rho_s']) * g[DES['firm_sec']]
                          + np.sqrt(1 - p['rho_m'] - p['rho_s']) * u)
    for fi, (_, _, d0s) in enumerate(DES['firms']):
        eta[fi, d0s] += p['jump_k'] * sig[fi] * rng.standard_normal(len(d0s))
    if p['phi'] >= 1:
        lat = np.cumsum(eta, axis=1)
    else:
        lat = np.empty_like(eta); lat[:, 0] = eta[:, 0] / np.sqrt(1 - p['phi'] ** 2)
        for t in range(1, T):
            lat[:, t] = p['phi'] * lat[:, t - 1] + eta[:, t]
    x = lat + p['noise'] * sig[:, None] * rng.standard_normal((nf, T))
    mu = np.zeros(DES['N'])
    if p.get('hetero'):
        s_ev = sig[DES['firm']]; mu = p['hetero'] * (s_ev - s_ev.mean())
    if p.get('mu'):
        mu = mu + p['mu']
    if mu.any():
        for i, (fi, d, _) in enumerate(DES['ev']):
            x[fi, d - 21:d + 11] += mu[i]
    return x


def bartlett_if_needed(r):
    lam = np.linspace(0, np.pi, 512)
    if (1 + 2 * (r[:, None] * np.cos(np.outer(np.arange(1, r.size + 1), lam))).sum(0)).min() < 0:
        r = r * (1 - np.arange(1, r.size + 1) / (r.size + 1))
    return r


def quad(Wm, r):
    q = (Wm ** 2).sum(1)
    for k, rk in enumerate(r, 1):
        q = q + 2 * rk * (Wm[:, k:] * Wm[:, :-k]).sum(1)
    return q


def cr1(A, groups, null=True):
    N = A.size
    _, gi = np.unique(groups, return_inverse=True); G = gi.max() + 1
    S = np.bincount(gi, A - A.mean(), G)
    V = G / (G - 1) * (S ** 2).sum() / N ** 2
    return A.mean() / np.sqrt(V), G


def one_rep(args):
    seed, p, meas_list = args
    rng = np.random.default_rng(seed)
    x = gen(rng, p)
    e = np.full_like(x, np.nan); e[:, 1:] = np.diff(x, axis=1)
    firm, Mb, N = DES['firm'], DES['Mb'], DES['N']
    E = np.nan_to_num(e[firm])                                   # N x T, the event's firm series
    Eb = np.where(Mb, E, 0.0)
    nb = Mb.sum(1)
    s = np.sqrt(((Eb - (Eb.sum(1) / nb)[:, None] * Mb) ** 2).sum(1) / (nb - 1))
    Z = Eb / s[:, None]
    # Rhat: pooled lags 1..10, demeaned per baseline (ADR text) and uncentred
    Zc = np.where(Mb, Z - (Z.sum(1) / nb)[:, None], 0.0)
    rh = {}
    for name, ZZ in (('dm', Zc), ('raw', Z)):
        den = (ZZ ** 2).sum()
        rh[name] = bartlett_if_needed(np.array([(ZZ[:, k:] * ZZ[:, :-k]).sum() / den for k in range(1, 11)]))
    # per-event-pair Pearson rho over shared baseline changes (kp_ow)
    Mf = Mb.astype(float)
    n_sh = Mf @ Mf.T
    Sx = Z @ Mf.T; Sxx = (Z ** 2) @ Mf.T; Sxy = Z @ Z.T
    with np.errstate(invalid='ignore', divide='ignore'):
        cov = Sxy / n_sh - Sx * Sx.T / n_sh ** 2
        vx = Sxx / n_sh - (Sx / n_sh) ** 2
        rho_ev = cov / np.sqrt(vx * vx.T)
    ok = (n_sh >= 20) & ~np.eye(N, dtype=bool)
    iu = np.triu_indices(N, 1)
    same_sec = DES['sec'][:, None] == DES['sec'][None]
    m_all = rho_ev[ok].mean() if ok.any() else 0.0
    m_sec = rho_ev[ok & same_sec].mean() if (ok & same_sec).any() else m_all
    # Pynnonen (2022) eq. 32: calendar-day cluster estimator of the average correlation, standardised baseline changes
    Ut = Z.sum(0); nt = Mb.sum(0)
    rhobar_pyn = (Ut ** 2 - (Z ** 2).sum(0)).sum() / (nt * (nt - 1)).sum()
    # firm-pair correlation pooled over all shared clean baseline dates (cs_ow)
    nf = DES['nf']
    Zf = np.zeros((nf, T)); Mff = np.zeros((nf, T))
    np.add.at(Zf, firm, Z); np.add.at(Mff, firm, Mf)
    nfg = Mff @ Mff.T
    with np.errstate(invalid='ignore', divide='ignore'):
        rfg = (Zf @ Zf.T) / nfg
    fs = DES['firm_sec']; ssec = fs[:, None] == fs[None]; offd = ~np.eye(nf, dtype=bool)
    good = (nfg >= 30) & offd
    fill_s = rfg[good & ssec].mean() if (good & ssec).any() else 0.0
    fill_x = rfg[good & ~ssec].mean() if (good & ~ssec).any() else 0.0
    rfg = np.where(good, rfg, np.where(ssec, fill_s, fill_x)); np.fill_diagonal(rfg, 0.0)
    rho_pair = rfg[firm][:, firm]
    out = {}
    for m in meas_list:
        Wm = DES['W'][m]
        A = (Wm * E).sum(1)
        if seed % 100000 == 0 and m != 'crush':  # identity check, first replication of each design
            tg = DES['tgt'][m]
            direct = np.array([x[f, tg[i]] - x[f, DES['ev'][i][2]].mean() for i, f in enumerate(firm)])
            assert np.abs(direct - A).max() < 1e-10, np.abs(direct - A).max()
        G = Wm @ Wm.T
        res = {}
        # BMP and KP family
        q_dm = quad(Wm, rh['dm']); q_raw = quad(Wm, rh['raw'])
        SA = A / (s * np.sqrt(q_raw))                               # ADR 0005 §1 (revised): uncentred Rhat
        t_bmp = SA.mean() / (SA.std(ddof=1) / np.sqrt(N))
        res['bmp'] = abs(t_bmp) > stats.t.ppf(0.975, N - 1)
        for name, q in (('kp_ow', q_dm), ('kp_ow_raw', q_raw)):
            om = G / np.sqrt(np.outer(q, q))
            rr = np.where(ok, rho_ev, np.where(same_sec, m_sec, m_all))
            rbar = max(0.0, (om[iu] * rr[iu]).mean())
            SAq = A / (s * np.sqrt(q)); tq = SAq.mean() / (SAq.std(ddof=1) / np.sqrt(N))
            res[name] = abs(tq * np.sqrt((1 - rbar) / (1 + (N - 1) * rbar))) > stats.t.ppf(0.975, N - 1)
        dg = np.sqrt(np.diag(G))
        with np.errstate(invalid='ignore', divide='ignore'):
            nu = G / np.outer(dg, dg)
        nubar = np.nanmean(nu[iu])
        r = nubar * rhobar_pyn
        res['kpp'] = abs(t_bmp * np.sqrt((1 - r) / (1 + (N - 1) * r))) > 1.96 if 1 + (N - 1) * r > 0 else True
        # raw-units family
        t_cs = A.mean() / (A.std(ddof=1) / np.sqrt(N))
        res['cs'] = abs(t_cs) > stats.t.ppf(0.975, N - 1)
        for name, grp in (('cl_date', DES['d0']), ('cl_week', DES['week']), ('cl_season', DES['season'])):
            tc, Gc = cr1(A, grp)
            res[name] = abs(tc) > stats.t.ppf(0.975, Gc - 1)
        tsa, Gsa = cr1(SA, DES['season'])                          # BMP's estimand, season-clustered
        res['sa_season'] = abs(tsa) > stats.t.ppf(0.975, Gsa - 1)
        # wild cluster restricted bootstrap by season (Webb)
        _, gi = np.unique(DES['season'], return_inverse=True); Gs = gi.max() + 1
        Sg = np.bincount(gi, A, Gs); ng = np.bincount(gi, None, Gs)
        tc, _ = cr1(A, DES['season'])
        v = WEBB[rng.integers(0, 6, (999, Gs))]
        Ss = v * Sg[None]
        mstar = Ss.sum(1) / N
        Vs = Gs / (Gs - 1) * ((Ss - ng[None] * mstar[:, None]) ** 2).sum(1) / N ** 2
        res['wcb_season'] = (np.abs(mstar / np.sqrt(Vs)) >= abs(tc)).mean() < 0.05
        # cs_ow: additive overlap covariance in raw units, firm-pair rho
        C = rho_pair * np.outer(s, s) * G
        np.fill_diagonal(C, 0.0)
        V = A.var(ddof=1) / N + C.sum() / (N * (N - 1))
        res['cs_ow'] = abs(A.mean() / np.sqrt(V)) > 1.96
        # Driscoll-Kraay in calendar time, null imposed
        c = (Wm * E).sum(0) / N
        g0 = (c ** 2).sum()
        gk = [(c[k:] * c[:-k]).sum() for k in range(1, 6)]
        V1 = g0 + 2 * gk[0]
        V5 = g0 + 2 * sum((1 - k / 6) * gk[k - 1] for k in range(1, 6))
        res['dk1'] = abs(A.mean()) / np.sqrt(V1) > 1.96 if V1 > 0 else True
        res['dk5'] = abs(A.mean()) / np.sqrt(V5) > 1.96
        res['_rbar_ow'] = rbar; res['_nubar'] = nubar; res['_rhobar'] = rhobar_pyn
        out[m] = res
    return out


DESIGNS = {
    'D0 iid, no cross-corr':                      dict(phi=1, rho_m=0.0, rho_s=0.0, noise=0.0, sig_disp=0.0, jump_k=0.0),
    'D1 rho=0.10 same-date, iid changes':         dict(phi=1, rho_m=0.10, rho_s=0.0, noise=0.0, sig_disp=0.0, jump_k=0.0),
    'D2 D1 + quote noise (MA1, acf1 ~ -0.17)':    dict(phi=1, rho_m=0.10, rho_s=0.0, noise=0.5, sig_disp=0.0, jump_k=0.0),
    'D3 D1 + quote noise 0.8 (acf1 ~ -0.28)':     dict(phi=1, rho_m=0.10, rho_s=0.0, noise=0.8, sig_disp=0.0, jump_k=0.0),
    'D4 realistic: sector rho, AR(.98), noise, hetero sd, jumps x3':
        dict(phi=0.98, rho_m=0.05, rho_s=0.15, noise=0.5, sig_disp=0.4, jump_k=3.0),
    'D5 D4 + heterogeneous effects, EW mean 0':    dict(phi=0.98, rho_m=0.05, rho_s=0.15, noise=0.5, sig_disp=0.4, jump_k=3.0, hetero=3.0),
    'D6 rho=0.10, AR(.98) levels only':          dict(phi=0.98, rho_m=0.10, rho_s=0.0, noise=0.0, sig_disp=0.0, jump_k=0.0),
    'P1 power: D4 + common shift mu=0.03':         dict(phi=0.98, rho_m=0.05, rho_s=0.15, noise=0.5, sig_disp=0.4, jump_k=3.0, mu=0.03),
    'P2 power: D4 + common shift mu=0.05':         dict(phi=0.98, rho_m=0.05, rho_s=0.15, noise=0.5, sig_disp=0.4, jump_k=3.0, mu=0.05),
    'P3 power: D4 + common shift mu=0.08':         dict(phi=0.98, rho_m=0.05, rho_s=0.15, noise=0.5, sig_disp=0.4, jump_k=3.0, mu=0.08),
    'P4 power: D2 (random-walk) + mu=0.03':        dict(phi=1, rho_m=0.10, rho_s=0.0, noise=0.5, sig_disp=0.0, jump_k=0.0, mu=0.03),
}
STATS = ['bmp', 'kp_ow', 'kp_ow_raw', 'kpp', 'cs', 'cl_date', 'cl_week', 'cl_season', 'wcb_season', 'sa_season', 'cs_ow',
         'dk1', 'dk5']

if __name__ == '__main__':
    t0 = time.time()
    seasons = collections.Counter(DES['season_raw'])
    print(f"design: N={DES['N']} events, {DES['nf']} firms, {len(set(DES['d0']))} distinct day-0 dates, "
          f"{len(set(DES['week']))} ISO weeks, quarters {dict(sorted(seasons.items()))}, "
          f"season clusters after merging < 10: {dict(sorted(collections.Counter(DES['season']).items()))}")
    print(f"baseline sessions: min {min(e[2].size for e in DES['ev'])}, median {np.median([e[2].size for e in DES['ev']]):.0f}; "
          f"reps per design {REPS}; MC se at 5% = {100*np.sqrt(.05*.95/REPS):.2f} pp; 99% band "
          f"[{100*stats.binom.ppf(.005, REPS, .05)/REPS:.2f}, {100*stats.binom.ppf(.995, REPS, .05)/REPS:.2f}]%")
    with Pool(20) as pool:
        for di, (name, p) in enumerate(DESIGNS.items()):
            meas = ['runup', 'persist_10', 'crush']
            res = pool.map(one_rep, [((di + 1) * 100000 + r, p, meas) for r in range(REPS)], chunksize=10)
            print(f"\n[{name}]  {p}")
            print(f"  {'measure':11s} " + ' '.join(f'{s:>10s}' for s in STATS) + '   mean rbar_ow  nubar  rhobar_pyn')
            for m in meas:
                rates = [np.mean([r[m][s] for r in res]) for s in STATS]
                aux = [np.mean([r[m][k] for r in res]) for k in ('_rbar_ow', '_nubar', '_rhobar')]
                print(f"  {m:11s} " + ' '.join(f'{100*x:9.1f}%' for x in rates) + f"   {aux[0]:.4f}  {aux[1]:.3f}  {aux[2]:.4f}")
    print(f"\nelapsed {time.time()-t0:.0f}s")
