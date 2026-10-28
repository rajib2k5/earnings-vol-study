import numpy as np
rng = np.random.default_rng(7)
def sim(N=50, L=36, rho=0.1, nsim=20000, evvar=1.0):
    rej = {'bmp':0,'kp':0,'cs':0}
    for _ in range(nsim):
        # common factor across firms on every day (estimation + event day): equicorrelation rho
        f = rng.standard_normal(L+1)
        e = np.sqrt(rho)*f[None,:] + np.sqrt(1-rho)*rng.standard_normal((N,L+1))
        est, ev = e[:,:L], e[:,L]*np.sqrt(evvar)   # event-induced variance multiplier
        s = est.std(axis=1, ddof=1)
        sar = ev/s
        t_bmp = sar.mean()/(sar.std(ddof=1)/np.sqrt(N))
        # r-bar from estimation-period residuals
        C = np.corrcoef(est); rbar = (C.sum()-N)/(N*(N-1))
        t_kp = t_bmp*np.sqrt((1-rbar)/(1+(N-1)*rbar))
        t_cs = ev.mean()/(ev.std(ddof=1)/np.sqrt(N))
        rej['bmp'] += abs(t_bmp)>1.96; rej['kp'] += abs(t_kp)>1.96; rej['cs'] += abs(t_cs)>1.96
    return {k:v/nsim for k,v in rej.items()}
for rho in (0.0, 0.05, 0.15):
    print("rho",rho, sim(rho=rho, nsim=4000), "| with 3x event variance:", sim(rho=rho, nsim=4000, evvar=3.0))
