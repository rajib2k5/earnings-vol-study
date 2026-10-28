"""Delta probe 5: is ADR 0005 §1's span-change rule (ADR 0004 §4) EXACT for ALIV_t with unobserved sessions?

Definition (ADR 0005 §1): ALIV_t = (1/|B|) sum_{u in B} (y_t - y_u), y = x - beta * m (log IV minus beta * log VIX),
B = the observed, non-excluded baseline sessions (ADR 0004 §1).
Rule under test: walk the OBSERVED sessions o_0 = min B < o_1 < ... < o_K = t of [min B, t]; span change
e_k = y(o_k) - y(o_{k-1}); weight a_k = n(o_k)/|B|, n(s) = number of B sessions strictly before s. Then
ALIV_t = sum_k a_k e_k exactly (claim), whatever sessions are unobserved.

Cases (2,000 random paths each, random B, random holes):
  A  every session observed, an excluded hole inside B
  B  3 unobserved sessions inside (min B, t]
  C  Mon/Wed/Fri sample (only Mon/Wed/Fri sessions observed), plus a hole
  D  unobserved session at t-1
  E  unobserved session at min B + 1
  F  an unobserved session inside an excluded zone inside B
Falsifiers (each must give a difference >= 1e-6 in at least one case where it is meant to bite):
  F1 weight n/(|B|-1);  F2 walk starts at the first observed session AFTER min B;  F3 weight n(o_{k-1}) (span start);
  F4 one-session changes only (spans that cross an unobserved session dropped).
Exit 0 only if the rule matches to 1e-12 in every case and every falsifier bites somewhere.
Run: uv run --no-sync --frozen python docs/validation/probes/m0-delta/d5_aliv_span.py
"""
import sys

import numpy as np

rng = np.random.default_rng(5)
T = 140  # sessions; target t in [-1, +10] relative to day 0 = 100
WEEKDAY = (np.arange(T) + 2) % 5  # 0 = Monday


def one(case):
    x = np.cumsum(rng.normal(0, 0.02, T)) + rng.normal(0, 0.01, T)
    m = np.cumsum(rng.normal(0, 0.03, T))
    beta = rng.uniform(0.3, 1.2)
    y = x - beta * m
    d0 = 100
    t = d0 + int(rng.choice([-1, 0, 5, 10]))
    observed = np.ones(T, bool)
    if case == "C":
        observed = np.isin(WEEKDAY, [0, 2, 4])
        while not observed[t]:
            t += 1
    base = np.arange(d0 - 60, d0 - 21)
    excluded = np.zeros(T, bool)
    h0 = int(rng.integers(d0 - 55, d0 - 35))
    excluded[h0:h0 + int(rng.integers(3, 10))] = True  # a hole inside B
    if case == "B":
        observed[rng.choice(np.arange(d0 - 58, t), 3, replace=False)] = False
    if case == "F":
        observed[h0 + 1] = False
    B = np.array([u for u in base if observed[u] and not excluded[u]])
    if case == "D":
        observed[t - 1] = False
        B = B[B != t - 1]
    if case == "E":
        observed[B.min() + 1] = False
        B = B[B != B.min() + 1]
    assert observed[t] and observed[B].all()
    inB = np.zeros(T, bool); inB[B] = True
    n_before = np.cumsum(inB) - inB
    aliv = y[t] - y[B].mean()
    obs = np.array([s for s in range(B.min(), t + 1) if observed[s]])

    def span_sum(start, wfun, one_session_only=False):
        o = obs[obs >= start]
        tot = 0.0
        for a, b in zip(o[:-1], o[1:]):
            if one_session_only and b - a > 1:
                continue
            tot += wfun(a, b) * (y[b] - y[a])
        return tot

    L = B.size
    rule = span_sum(B.min(), lambda a, b: n_before[b] / L)
    f1 = span_sum(B.min(), lambda a, b: n_before[b] / (L - 1))
    f2 = span_sum(obs[obs > B.min()].min(), lambda a, b: n_before[b] / L)
    f3 = span_sum(B.min(), lambda a, b: n_before[a] / L)
    f4 = span_sum(B.min(), lambda a, b: n_before[b] / L, one_session_only=True)
    return aliv, rule, f1, f2, f3, f4


ok = True
bites = {f: 0.0 for f in ("F1", "F2", "F3", "F4")}
for case in "ABCDEF":
    d = np.array([one(case) for _ in range(2000)])
    err = np.abs(d[:, 1] - d[:, 0]).max()
    fd = {f: np.abs(d[:, i] - d[:, 0]).max() for i, f in zip(range(2, 6), ("F1", "F2", "F3", "F4"))}
    for f, v in fd.items():
        bites[f] = max(bites[f], v)
    print(f"case {case}: max |rule - ALIV| = {err:.2e}   falsifiers max |diff|: "
          + "  ".join(f"{f} {v:.1e}" for f, v in fd.items()))
    ok &= err < 1e-12
print("falsifiers bite (>= 1e-6 somewhere):", {f: v >= 1e-6 for f, v in bites.items()})
ok &= all(v >= 1e-6 for v in bites.values())
print("RESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
