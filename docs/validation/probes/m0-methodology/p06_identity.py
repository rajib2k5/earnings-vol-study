"""Probe C6a/C6b: ADR 0005 §1 claims ALIV_t = sum_v a_v e_v exactly, a_v = n_v/|B| (n_v = # baseline sessions
strictly before v), e_v = dx_v - beta*dm_v the abnormal ONE-SESSION change.
Case A: random path, baseline [-60,-22] with an excluded hole (another event's zone) inside it; all sessions observed.
Case B: same, plus unobserved sessions (snapshot missing) inside (min B, t] -> one-session changes undefined there.
Falsifier: weights n_v/(|B|-1) must break case A.
Run: uv run --no-sync --frozen python docs/validation/probes/m0-methodology/p06_identity.py
"""
import numpy as np

rng = np.random.default_rng(6)
rel = np.arange(-60, 11)
x = np.cumsum(rng.normal(0, 0.03, rel.size)) + np.log(0.3)
m = np.cumsum(rng.normal(0, 0.05, rel.size)) + np.log(0.2)
beta = 0.6
pos = {r: i for i, r in enumerate(rel)}
B = [r for r in range(-60, -21) if not (-50 <= r <= -41)]  # hole: another event's zone [-50,-41]


def aliv(t, B=B):
    mu, mum = np.mean([x[pos[u]] for u in B]), np.mean([m[pos[u]] for u in B])
    return (x[pos[t]] - mu) - beta * (m[pos[t]] - mum)


def ramp_sum(t, observed, denom_shift=0, B=B):
    tot = 0.0; used = 0; skipped = []
    for v in range(min(B) + 1, t + 1):
        n_v = sum(1 for u in B if u < v)
        if observed[v] and observed[v - 1]:
            e_v = (x[pos[v]] - x[pos[v - 1]]) - beta * (m[pos[v]] - m[pos[v - 1]])
            tot += n_v / (len(B) - denom_shift) * e_v; used += 1
        else:
            skipped.append(v)
    return tot, used, skipped


obs_all = {r: True for r in rel}
for t in (-1, 0, 1, 5, 10):
    a = aliv(t); s, used, _ = ramp_sum(t, obs_all)
    sf, _, _ = ramp_sum(t, obs_all, denom_shift=1)
    print(f"A t={t:+d}: ALIV {a:+.12f} ramp {s:+.12f} |diff| {abs(a-s):.1e}  falsifier(|B|-1) |diff| {abs(a-sf):.1e}")

obs_miss = dict(obs_all); obs_miss[-45] = False; obs_miss[-30] = False; obs_miss[-8] = False
# x at a missing session is unknown to the pipeline; ADR 0004 §1 drops unobserved sessions from B
B2 = [u for u in B if obs_miss[u]]
for t in (-1, 5):
    a = aliv(t, B2); s, used, skipped = ramp_sum(t, obs_miss, B=B2)
    print(f"B t={t:+d}: ALIV {a:+.12f} ramp(one-session only) {s:+.12f} |diff| {abs(a-s):.2e}; "
          f"one-session changes undefined at v={skipped}")
    # rescue: replace the two undefined changes around a missing session by one 2-session change
    tot = 0.0; v = min(B2) + 1
    while v <= t:  # walk sessions from min B to t
        n_v = sum(1 for u in B2 if u < v)
        if obs_miss[v] and obs_miss[v - 1]:
            tot += n_v / len(B2) * ((x[pos[v]] - x[pos[v-1]]) - beta * (m[pos[v]] - m[pos[v-1]])); v += 1
        else:  # v-1 or v missing: bridge from last observed to next observed with the (constant) weight
            a0 = v - 1 if obs_miss[v - 1] else v - 2
            b0 = v if obs_miss[v] else v + 1
            assert sum(1 for u in B2 if a0 < u < b0) == 0
            tot += sum(1 for u in B2 if u < b0) / len(B2) * ((x[pos[b0]] - x[pos[a0]]) - beta * (m[pos[b0]] - m[pos[a0]]))
            v = b0 + 1
    print(f"   with multi-session bridging changes: |diff| {abs(a-tot):.1e}")
print("weights at hole sessions v in [-49,-41] (an excluded zone) are nonzero:",
      [round(sum(1 for u in B if u < v) / len(B), 3) for v in (-49, -45, -41)])
