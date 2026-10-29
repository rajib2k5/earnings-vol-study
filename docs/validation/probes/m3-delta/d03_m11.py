"""d03: is M11 (BH's running minimum starting at +inf instead of 1) an equivalent mutant? (delta claim 6)

The mutant is built from the package's own source text (inspect.getsource, one string replaced), so the
comparison is the shipped bh() against the shipped bh() with only that change.
  1. 100,000 random p-vectors (m 1..300) from mixed generators, adversarial ones included:
     values within a few ulps of 1, exact 1s, ties, exact 0s, subnormals, m up to 300.
  2. exhaustive float check near 1: every p in the 2,000 doubles just below 1.0, every m in 1..400:
     fl(fl(m p) / m) <= 1 (the top-rank value; monotone rounding says it cannot exceed fl(m)/m = 1).
  3. inputs the guard refuses (NaN, < 0, > 1): both versions must raise; and with the guard removed,
     a p > 1 makes the two versions differ (so equivalence rests on the guard).
Run: uv run --frozen --no-sync python docs/validation/probes/m3-delta/d03_m11.py
"""
import inspect

import numpy as np

from earnings_vol.stats import multiple

src = inspect.getsource(multiple.bh)
assert src.count("running = 1.0") == 1
ns = dict(vars(multiple))
exec(src.replace("running = 1.0", "running = np.inf"), ns)
bh_mut = ns["bh"]
rng = np.random.default_rng(20261029)
one = np.nextafter(1.0, 0.0)
diff = 0
gens = 0
for k in range(100_000):
    m = int(rng.integers(1, 301))
    kind = k % 6
    if kind == 0:
        p = rng.random(m)
    elif kind == 1:
        p = rng.beta(0.3, 1.0, m)
    elif kind == 2:                                  # exact 1s and ties
        p = rng.choice([0.0, 0.01, 0.5, 1.0], m)
    elif kind == 3:                                  # a few ulps below 1
        p = 1.0 - rng.integers(0, 50, m) * np.finfo(float).eps / 2
    elif kind == 4:                                  # subnormals and zeros
        p = rng.choice([0.0, 5e-324, 1e-300, 1.0, one], m)
    else:                                            # mixture
        p = np.where(rng.random(m) < 0.5, rng.random(m), 1.0 - rng.random(m) * 1e-15)
    p = np.clip(p, 0.0, 1.0)
    a, b = multiple.bh(list(p)), bh_mut(list(p))
    gens += 1
    if a != b:
        diff += 1
print(f"1) random vectors {gens}: shipped vs M11 differ in {diff}")

worst = 0.0
x = 1.0
bad = 0
for _ in range(2000):
    x = np.nextafter(x, 0.0)
    for m in range(1, 401):
        v = (m * x) / m
        bad += v > 1.0
        worst = max(worst, v)
print(f"2) 2,000 doubles below 1 x m 1..400: top-rank value > 1 in {bad} cases; max {worst!r}")

for bad_in in ([0.2, float("nan")], [0.2, -0.1], [0.2, 1.5]):
    r = []
    for fn in (multiple.bh, bh_mut):
        try:
            fn(bad_in)
            r.append("returned")
        except ValueError:
            r.append("raised")
    print(f"3) input {bad_in}: shipped {r[0]}, M11 {r[1]}")
ns2 = dict(vars(multiple), _probabilities=lambda v: v)
exec(src, ns2)
exec(src.replace("running = 1.0", "running = np.inf"), ns3 := dict(vars(multiple), _probabilities=lambda v: v))
print(f"3) guard removed, input [0.2, 1.5]: shipped {ns2['bh']([0.2, 1.5])}  M11 {ns3['bh']([0.2, 1.5])}")
