import numpy as np
rng = np.random.default_rng(11)
def sim(N=50, L=36, ndates=15, rho=0.1, nsim=3000, crit=1.96):
    rej = dict(bmp=0, kp_all=0, kp_samedate=0, clus=0, kp_all_clamp=0, kp_ow_clamp=0, neg_all=0, neg_ow=0)
    for _ in range(nsim):
        T = L+ndates+1
        f = rng.standard_normal(T)
        d0 = L + rng.integers(0, ndates, N)
        u = rng.standard_normal((N,T))
        e = np.sqrt(rho)*f[None,:] + np.sqrt(1-rho)*u
        est = np.stack([e[i, d0[i]-L:d0[i]] for i in range(N)])
        ev = e[np.arange(N), d0]
        s = est.std(axis=1, ddof=1); sar = ev/s
        t_bmp = sar.mean()/(sar.std(ddof=1)/np.sqrt(N))
        # pairwise correlation over overlapping calendar days of the baselines
        R = np.zeros((N,N)); W = np.zeros((N,N))
        for i in range(N):
            for j in range(i+1,N):
                lo, hi = max(d0[i],d0[j])-L, min(d0[i],d0[j])
                if hi-lo >= 20:
                    a = e[i,lo:hi]; b = e[j,lo:hi]
                    R[i,j] = np.corrcoef(a,b)[0,1]; W[i,j] = 1.0
        same = (d0[:,None]==d0[None,:]) & np.triu(np.ones((N,N),bool),1)
        rbar_all = R[W>0].mean()
        # effective rbar: average over ALL pairs of rho_ij * 1[same event date]
        rbar_eff = (R*same).sum()/(N*(N-1)/2)
        adj = lambda r: np.sqrt((1-r)/(1+(N-1)*r))
        rej['bmp'] += abs(t_bmp)>crit
        rej['kp_all'] += abs(t_bmp*adj(rbar_all))>crit
        rej['kp_samedate'] += abs(t_bmp*adj(rbar_eff))>crit
        # date-clustered SE for the mean of SAR (CR1)
        m = sar.mean(); g = {}
        for i in range(N): g.setdefault(d0[i], 0.0); g[d0[i]] += sar[i]-m
        G = len(g); v = (G/(G-1))*sum(x*x for x in g.values())/N**2
        rej['clus'] += abs(m/np.sqrt(v))>crit
        rej['kp_all_clamp'] += abs(t_bmp*adj(max(rbar_all,0.0)))>crit
        rej['kp_ow_clamp'] += abs(t_bmp*adj(max(rbar_eff,0.0)))>crit
        rej['neg_all'] += rbar_all<0; rej['neg_ow'] += rbar_eff<0
    return {k: round(v/nsim,3) for k,v in rej.items()}
for nd in (15, 40):
    for rho in (0.0, 0.1, 0.2):
        print(f"dates={nd} rho={rho}", sim(ndates=nd, rho=rho))
