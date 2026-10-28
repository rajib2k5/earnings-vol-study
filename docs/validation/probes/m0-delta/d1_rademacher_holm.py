"""Delta probe 1c: the Rademacher enumeration p-value floor at G = 7, and where that floor passes Holm.

ADR 0005 §2f: `rad_season_p` enumerates all 2^G Rademacher sign vectors (128 at G = 7); "its smallest attainable
two-sided p is 2/2^G = 0.0156. So it can never pass Holm's first step at 0.05/7, and can pass only from the fourth step
on (0.05/4 = 0.0125 < 0.0156 <= 0.05/3)". ADR 0005 §4 repeats "only from the fourth step on".

Channel B:
  (a) the statistic of `research/prototypes/h2h3_followup_sim.py` (restricted wild bootstrap of the one-way CR1 t by
      season, intercept-only, p = share of |t*| >= |t|): over 20,000 random data sets with 7 seasons, the smallest p
      seen, and the exact identities t*(1) = t and |t*(-v)| = |t*(v)|;
  (b) an extreme data set built to make |t| as large as possible: p must still be >= 2/128;
  (c) falsifier: draw 128 sign vectors at random instead of enumerating -> p < 2/128 must occur;
  (d) Holm (step-down, m = 7, alpha = 0.05): the k-th smallest p is compared with alpha/(m-k+1). Print each step's
      threshold and the first step at which p = 2/128 can be rejected; cross-check with statsmodels' 'holm'.
Exit 0 only if (a)-(c) behave as stated; (d) is printed, the verdict on the ADR's "fourth step" is in the ledger.
Run: uv run --no-sync --frozen python docs/validation/probes/m0-delta/d1_rademacher_holm.py
"""
import itertools
import sys

import numpy as np
from statsmodels.stats.multitest import multipletests

G = 7
SIGNS = np.array(list(itertools.product((-1.0, 1.0), repeat=G)))


def p_enum(A, gs, signs=SIGNS):
    N = A.size
    ng = np.bincount(gs, minlength=G)
    S0 = np.bincount(gs, A, G)
    u = A - A.mean()
    V1 = G / (G - 1) * (np.bincount(gs, u, G) ** 2).sum() / N ** 2
    t1 = A.mean() / np.sqrt(V1)
    Ss = signs * S0[None]
    m = Ss.sum(1) / N
    Vs = G / (G - 1) * ((Ss - ng[None] * m[:, None]) ** 2).sum(1) / N ** 2
    ts = m / np.sqrt(Vs)
    return (np.abs(ts) >= abs(t1) - 1e-12).mean(), t1, ts


ok = True
rng = np.random.default_rng(7)
gs = np.repeat(np.arange(G), [52, 50, 50, 50, 49, 49, 52])
pmin, ident = 1.0, 0.0
for _ in range(20000):
    A = rng.normal(rng.normal(0, 0.5), 1, gs.size) + rng.normal(0, 1, G)[gs] * rng.uniform(0, 2)
    p, t1, ts = p_enum(A, gs)
    pmin = min(pmin, p)
    ident = max(ident, abs(ts[-1] - t1), np.abs(ts + ts[::-1]).max())  # SIGNS[-1] = all +1; SIGNS[::-1] = -SIGNS
print(f"(a) 20,000 random data sets: smallest p = {pmin:.6f} (2/128 = {2/128:.6f}); "
      f"max |t*(+1) - t| and max |t*(v) + t*(-v)| = {ident:.2e}")
ok &= pmin >= 2 / 128 - 1e-15 and ident < 1e-9
# (b) large |t|: the prototype compares |t*| >= |t| - 1e-12 (an ABSOLUTE tolerance) and computes t* by a different
# floating-point route than t, so t*(all +1) can fall below |t| by more than 1e-12 when |t| is large.
broke = None
for sd in np.geomspace(1.0, 1e-4, 41):
    for _ in range(50):
        A = 1.0 + sd * rng.normal(size=gs.size)
        p, t1, _ = p_enum(A, gs)
        if p < 2 / 128:
            broke = (abs(t1), p) if broke is None or abs(t1) < broke[0] else broke
    if broke:
        break
print(f"(b) large |t|: smallest |t| seen with p below the floor = {broke[0]:.0f} (p = {broke[1]:.6f})" if broke else
      "(b) large |t|: p never fell below the floor")
B_BROKE = broke is not None
p_s = min(p_enum(A, gs, rng.choice([-1.0, 1.0], (128, G)))[0] for _ in range(200))
print(f"(c) falsifier, 128 sampled sign vectors, same data, 200 tries: smallest p = {p_s:.6f} "
      f"-> {'below the floor (good: enumeration matters)' if p_s < 2 / 128 else 'never below (falsifier failed)'}")
ok &= p_s < 2 / 128

m, alpha, pfloor = 7, 0.05, 2 / 128
print(f"(d) Holm, m = {m}, alpha = {alpha}: step k compares the k-th smallest p with alpha/(m-k+1)")
first = None
for k in range(1, m + 1):
    thr = alpha / (m - k + 1)
    passes = pfloor <= thr
    print(f"    step {k}: threshold alpha/{m - k + 1} = {thr:.5f}  p = 2/128 {'passes' if passes else 'fails'}")
    if passes and first is None:
        first = k
print(f"    first step at which p = 2/128 can be rejected: step {first} (threshold 0.05/{m - first + 1})")
# statsmodels cross-check: H2 at the floor plus k-1 smaller p-values from other hypotheses
for k in range(1, m + 1):
    pv = np.array([1e-6] * (k - 1) + [pfloor] + [0.5] * (m - k))
    rej = multipletests(pv, alpha=alpha, method="holm")[0]
    print(f"    statsmodels holm: {k - 1} smaller p-values before it -> floor p rejected: {bool(rej[k - 1])}")
print("RESULT (a, c):", "PASS" if ok else "FAIL", "| (b) floor violated numerically at large |t|:", B_BROKE)
sys.exit(0 if ok else 1)
