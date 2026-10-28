"""Probe C11b/C11c: is iv_persistence_mc.py's 0.675 (levels) vs 0.022 (changes) an artefact of phi = 0.98 and
sd_e = 0.005? Vectorised re-implementation of the same test statistics, parameter sweep, plus the closed-form size
of the 'summed changes' statistic under AR(1)+noise (explains the 0.022).
Run: uv run --no-sync --frozen python docs/validation/probes/m0-methodology/p11_persistence_sweep.py
"""
import numpy as np
from scipy import stats

rng = np.random.default_rng(11)
L1, L2, burn, reps = 120, 11, 300, 20000


def sim(phi, sd_x, sd_e):
    T = burn + L1 + L2
    x = np.empty((reps, T))
    x[:, 0] = rng.normal(0, sd_x / np.sqrt(1 - phi**2) if phi < 1 else sd_x, reps)
    eps = rng.normal(0, sd_x, (reps, T))
    for t in range(1, T):
        x[:, t] = phi * x[:, t - 1] + eps[:, t]
    iv = 0.40 + x + rng.normal(0, sd_e, (reps, T))
    est, evt = iv[:, burn:burn + L1], iv[:, burn + L1:]
    zA = (evt - est.mean(1, keepdims=True)).sum(1) / np.sqrt(L2 * est.var(1, ddof=1))
    d = np.diff(iv[:, burn - 1:], axis=1)
    de, dv = d[:, :L1], d[:, L1:]
    zB = (dv - de.mean(1, keepdims=True)).sum(1) / np.sqrt(L2 * de.var(1, ddof=1))
    return (np.abs(zA) > 1.96).mean(), (np.abs(zB) > 1.96).mean()


def analytic_changes(phi, sd_x, sd_e):
    vx = sd_x**2 / (1 - phi**2)
    var_sum = 2 * vx * (1 - phi**L2) + 2 * sd_e**2        # Var(iv_{t+11} - iv_t)
    var_one = 2 * vx * (1 - phi) + 2 * sd_e**2            # Var(one change)
    ratio = var_sum / (L2 * var_one)
    rho1 = (-(1 - phi) * vx * (1 - phi) - sd_e**2) / var_one
    return 2 * stats.norm.sf(1.96 / np.sqrt(ratio)), ratio, rho1


print(f"{'phi':>5} {'sd_x':>6} {'sd_e':>6} | {'levels':>7} {'changes':>8} | analytic changes size, var ratio, lag-1 acf")
for phi in (0.0, 0.5, 0.9, 0.98, 0.995):
    for sd_e in (0.0, 0.005, 0.01):
        a, b = sim(phi, 0.01, sd_e)
        sz, ratio, r1 = analytic_changes(phi, 0.01, sd_e)
        print(f"{phi:5.3f} {0.01:6.3f} {sd_e:6.3f} | {a:7.3f} {b:8.3f} | {sz:.3f}  {ratio:.3f}  {r1:+.3f}")
