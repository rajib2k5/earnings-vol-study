"""Probe C7a-d (ADR 0005 §2): Patell variance, BMP robustness to s_hat, KP factor algebra.
Run: uv run --no-sync --frozen python docs/validation/probes/m0-methodology/p07_tests_algebra.py
"""
import numpy as np
from scipy import stats

rng = np.random.default_rng(7)

# ---- C7a: SA = e0 / s, s = sample sd ddof=1 over L iid N(0,1) changes, mean-zero model
print("C7a  L   MC var(SA)        d/(d-2), d=L-1   L/(L-2)    (L-2)/(L-4)")
for L in (8, 31):
    acc = []; n = 0
    for _ in range(20):
        e = rng.standard_normal((500_000, L + 1))
        sa = e[:, L] / e[:, :L].std(axis=1, ddof=1)
        acc.append((sa**2).sum()); n += sa.size
    v = sum(acc) / n
    print(f"     {L:2d}  {v:.4f}            {(L-1)/(L-3):.4f}           {L/(L-2):.4f}     {(L-2)/(L-4):.4f}")
# detectability of the ADR's mutation "L instead of L-1" by the §5 Monte Carlo (2,000 reps, band [3.74, 6.26])
N, L = 350, 31
sd_ratio = np.sqrt(((L - 1) / (L - 3)) / (L / (L - 2)))
print(f"     mutation L vs L-1 at L=31, N=350: Z_P sd ratio {sd_ratio:.5f} -> size {2*stats.norm.sf(1.96/sd_ratio):.4%} (band 3.74-6.26%)")


def bmp(sa):
    return sa.mean() / (sa.std(ddof=1) / np.sqrt(sa.size))


def cs(a):
    return a.mean() / (a.std(ddof=1) / np.sqrt(a.size))


# ---- C7b/C7c: BMP size under different s_hat
N, L, R = 350, 31, 4000
crit = stats.t.ppf(0.975, N - 1)
designs = {}
for name in ("sharp: s_hat = baseline sd", "sharp: s_hat x U(0.3,3) noise", "sharp: s_hat = 1 (equal weights)",
             "hetero mu_i = c*(sigma_i - mean), s_hat = baseline sd", "hetero, s_hat = 1"):
    rej_b = rej_c = 0
    for _ in range(R):
        sig = np.exp(rng.normal(np.log(0.05), 0.5, N))      # per-event sd of log-IV changes
        base = rng.standard_normal((N, L)) * sig[:, None]
        mu = np.zeros(N)
        if name.startswith("hetero"):
            mu = 1.0 * (sig - sig.mean())                    # equal-weighted mean of mu is exactly 0
        a = mu + rng.standard_normal(N) * sig * 3            # event-induced variance x9
        s_hat = base.std(axis=1, ddof=1)
        if "noise" in name:
            s_hat = s_hat * rng.uniform(0.3, 3, N)
        if "= 1" in name:
            s_hat = np.ones(N)
        rej_b += abs(bmp(a / s_hat)) > crit; rej_c += abs(cs(a)) > crit
    designs[name] = (rej_b / R, rej_c / R)
    print(f"C7b/c {name:55s} BMP {rej_b/R:6.3f}  CS-t {rej_c/R:6.3f}")

# ---- C7d: KP factor algebra, exact (no simulation)
Nn = 50
for label, common in (("common variance", True), ("unequal variances (event-induced, lognormal sd 0.6)", False)):
    A = rng.uniform(0, 1, (Nn, Nn)); C = 0.05 + 0.1 * (A + A.T) / 2; np.fill_diagonal(C, 1.0)
    w, V = np.linalg.eigh(C); C = V @ np.diag(np.clip(w, 1e-6, None)) @ V.T
    d = np.sqrt(np.diag(C)); C = C / np.outer(d, d)
    sd = np.ones(Nn) if common else np.exp(rng.normal(0, 0.6, Nn))
    Sig = C * np.outer(sd, sd)
    rbar = (C.sum() - Nn) / (Nn * (Nn - 1))
    var_mean = Sig.sum() / Nn**2
    E_s2 = (np.trace(Sig) - Sig.sum() / Nn) / (Nn - 1)
    s2bar = np.mean(sd**2)
    infl_true = var_mean / (E_s2 / Nn)
    infl_kp = (1 + (Nn - 1) * rbar) / (1 - rbar)
    print(f"C7d [{label}] rbar={rbar:.4f}: Var(mean)/[s2bar(1+(N-1)rbar)/N]={var_mean/(s2bar*(1+(Nn-1)*rbar)/Nn):.4f}; "
          f"E[s^2]/[s2bar(1-rbar)]={E_s2/(s2bar*(1-rbar)):.4f}; true t^2 inflation {infl_true:.3f} vs KP {infl_kp:.3f}")
