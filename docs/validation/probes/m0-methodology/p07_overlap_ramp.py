"""Probe C7e (ADR 0005 §2d): overlap weight omega_ij, and the FIRST size check of the overlap-weighted KP on the
RUNUP ramp (ALIV_-1), which the ADR says was never simulated.
Part 1 (exact algebra): e_it = sqrt(rho) f_t + sqrt(1-rho) u_it, f iid across dates, u_i MA(1) (quote noise).
  Cov(A_i,A_j) = rho a_i'a_j ; Var(A_i) = a_i'(rho I + (1-rho) R_u) a_i. Compare with the ADR omega formula.
Part 2 (Monte Carlo, design 3 of ADR 0005 §5 applied to RUNUP): N events, day 0 uniform on 15 consecutive
  sessions, baseline [-60,-22] (39 sessions, no holes), A_i = ALIV_-1 computed from LEVELS, s_i = sd of baseline
  changes, SA_i = A_i/(s_i sqrt(a'R_hat a)), rho_hat_ij over shared baseline changes (>= 20), omega_ij per ADR on the
  calendar axis, rbar = mean over all pairs of omega*rho_hat clamped at 0; two-sided 5% with 1.96 like the prototype.
  R_hat: pooled lag 1..10 autocorrelation of standardised baseline changes (Bartlett if not PSD).
Run: uv run --no-sync --frozen python docs/validation/probes/m0-methodology/p07_overlap_ramp.py [reps] [--rhat=demeaned|raw|true ...]
"""
import sys

import numpy as np

rng = np.random.default_rng(75)
REPS = int(next((a for a in sys.argv[1:] if a.isdigit()), 1000))

# ---------------- part 1: algebra
T = 120; rho = 0.2; th = -0.4  # MA(1) coefficient of the idiosyncratic part
Ru = np.eye(T) + (th / (1 + th**2)) * (np.eye(T, k=1) + np.eye(T, k=-1))
Rown = rho * np.eye(T) + (1 - rho) * Ru


def ramp(d0, nb=39, t_end=-1):
    a = np.zeros(T)
    B = list(range(d0 - 60, d0 - 21))
    for v in range(min(B) + 1, d0 + t_end + 1):
        a[v] = sum(1 for u in B if u < v) / len(B)
    return a


ai, aj = ramp(70), ramp(78)
cov = rho * ai @ aj  # same-date only
corr_true = cov / np.sqrt((ai @ Rown @ ai) * (aj @ Rown @ aj))
omega = (ai @ aj) / np.sqrt((ai @ Rown @ ai) * (aj @ Rown @ aj))
omega_Rnum = (ai @ Rown @ aj) / np.sqrt((ai @ Rown @ ai) * (aj @ Rown @ aj))
print(f"part1: true Corr(A_i,A_j) {corr_true:.5f} | ADR rho*omega {rho*omega:.5f} | rejected-draft rho*omega(R numerator) {rho*omega_Rnum:.5f}")
print(f"       omega = {omega:.3f} (> 1 is possible: a'a / a'Ra with negative autocorrelation: own {ai@ai/(ai@Rown@ai):.3f})")
c0 = np.zeros(T); c0[70] = 1; c1 = np.zeros(T); c1[70] = 1; c2 = np.zeros(T); c2[71] = 1
print(f"       CRUSH: same date omega {(c0@c1)/np.sqrt((c0@Rown@c0)*(c1@Rown@c1)):.3f}, adjacent dates omega {(c0@c2)/np.sqrt((c0@Rown@c0)*(c2@Rown@c2)):.3f}")


# ---------------- part 2: Monte Carlo
def one_rep(N, rho, th, ndates, rmode="demeaned"):
    Tt = 60 + ndates + 2
    f = rng.standard_normal(Tt)
    z = rng.standard_normal((N, Tt + 1))
    u = (z[:, 1:] + th * z[:, :-1]) / np.sqrt(1 + th**2)
    e = np.sqrt(rho) * f[None, :] + np.sqrt(1 - rho) * u          # abnormal one-session changes
    x = np.cumsum(e, axis=1)                                       # log-IV level (abnormal part)
    d0 = 61 + rng.integers(0, ndates, N)
    A = np.empty(N); s = np.empty(N); a_cal = np.zeros((N, Tt))
    base_lo = d0 - 60; base_hi = d0 - 22                           # B = [lo, hi]
    for i in range(N):
        B = np.arange(base_lo[i], base_hi[i] + 1)
        A[i] = x[i, d0[i] - 1] - x[i, B].mean()
        s[i] = e[i, B[1:]].std(ddof=1)                             # changes with both ends in B
        n_before = np.arange(1, B.size + 1)                        # weights for v = B[1..], then 1
        a_cal[i, B[1:]] = n_before[:-1] / B.size
        a_cal[i, base_hi[i] + 1:d0[i]] = 1.0
    # pooled autocorrelation of standardised baseline changes
    zs = [e[i, base_lo[i] + 1:base_hi[i] + 1] / s[i] for i in range(N)]
    rk = []
    for k in range(1, 11):
        c = (lambda zz: zz.mean()) if rmode == "demeaned" else (lambda zz: 0.0)
        num = sum((zz[k:] - c(zz)) @ (zz[:-k] - c(zz)) for zz in zs)
        den = sum(((zz - c(zz)) ** 2).sum() for zz in zs)
        rk.append(num / den)
    if rmode == "true":  # oracle: the true own autocorrelation (rho*I + (1-rho)*MA(1))
        rk = [(1 - rho) * th / (1 + th**2)] + [0.0] * 9
    Rh = np.eye(Tt)
    for k, r_ in enumerate(rk, 1):
        Rh += r_ * (np.eye(Tt, k=k) + np.eye(Tt, k=-k))
    if np.linalg.eigvalsh(Rh).min() < 0:
        Rh = np.eye(Tt)
        for k, r_ in enumerate(rk, 1):
            Rh += (1 - k / 11) * r_ * (np.eye(Tt, k=k) + np.eye(Tt, k=-k))
    q = np.einsum("it,ts,is->i", a_cal, Rh, a_cal)
    SA = A / (s * np.sqrt(q))
    # pairwise rho_hat over shared baseline changes
    es = np.where(np.isnan(e), 0, e)
    Rho = np.zeros((N, N)); ok = np.zeros((N, N), bool)
    for i in range(N):
        for j in range(i + 1, N):
            lo = max(base_lo[i], base_lo[j]) + 1; hi = min(base_hi[i], base_hi[j]) + 1
            if hi - lo >= 20:
                Rho[i, j] = np.corrcoef(es[i, lo:hi], es[j, lo:hi])[0, 1]; ok[i, j] = True
    G = a_cal @ a_cal.T
    Om = G / np.sqrt(np.outer(q, q))
    iu = np.triu_indices(N, 1)
    rbar_ow = max(0.0, (Om[iu] * Rho[iu]).sum() / len(iu[0]))
    rbar_pub = max(0.0, Rho[ok].mean())
    t = SA.mean() / (SA.std(ddof=1) / np.sqrt(N))
    adj = lambda r: np.sqrt((1 - r) / (1 + (N - 1) * r))
    return abs(t) > 1.96, abs(t * adj(rbar_ow)) > 1.96, abs(t * adj(rbar_pub)) > 1.96, rbar_ow, Om[iu].mean()


MODES = [a.split("=")[1] for a in sys.argv if a.startswith("--rhat=")] or ["demeaned"]
for rmode in MODES:
  for rho_, th_ in ((0.0, 0.0), (0.1, 0.0), (0.1, -0.4)):
    res = np.array([one_rep(50, rho_, th_, 15, rmode) for _ in range(REPS)])
    se = np.sqrt(0.05 * 0.95 / REPS)
    print(f"[R_hat={rmode}] part2 RUNUP N=50, 15 dates, rho={rho_}, MA(1) theta={th_}, {REPS} reps (MC se {100*se:.2f} pp): "
          f"BMP {res[:,0].mean():.3f}  KP_ow(clamped) {res[:,1].mean():.3f}  KP_published {res[:,2].mean():.3f}  "
          f"mean rbar_ow {res[:,3].mean():.4f}  mean omega {res[:,4].mean():.3f}")
