"""p02b: does forward_from_pairs send a decimal tie in |C - P| to the lower strike? (claim 2a)

ADR 0003 §0 step 2 and forward.py's docstring: "ties go to the lower strike". Quotes are in cents, so
mids are multiples of 0.005 and |C - P| ties are exact in decimal. The code sorts the float |C - P|.
Run from the repository root: python docs/validation/probes/m2/p02b_tie.py
"""
import numpy as np

from earnings_vol.measures import forward

# Search small cent-quoted mids for a decimal tie whose float gaps order the higher strike first.
found = None
for c1 in range(5, 400, 5):            # mids in half-cents * 10: c1/1000 ... keep to 0.005 grid
    for p1 in range(5, 400, 5):
        g = abs(c1 - p1)
        if g == 0:
            continue
        for c2 in range(5, 400, 5):
            p2 = c2 + g if (c2 + g) < 400 else None
            if p2 is None:
                continue
            a, b = abs(c1 / 1000 - p1 / 1000), abs(c2 / 1000 - p2 / 1000)
            if a > b:                   # decimal tie, but the lower strike's float gap is larger
                found = (c1 / 1000, p1 / 1000, c2 / 1000, p2 / 1000, a, b)
                break
        if found:
            break
    if found:
        break
c1, p1, c2, p2, a, b = found
print(f"lower strike 100: C={c1} P={p1} |C-P| float={a!r}")
print(f"upper strike 105: C={c2} P={p2} |C-P| float={b!r}  (decimal: equal)")
# Five strikes so that the tie decides the 4th pick: three clear winners, then the tied pair.
strike = np.array([95.0, 97.5, 100.0, 102.5, 105.0])
c_mid = np.array([1.000, 0.500, c1, 0.200, c2])
p_mid = np.array([1.001, 0.501, p1, 0.201, p2])
F, n, disp = forward.forward_from_pairs(strike, c_mid, p_mid, 1.0)
gap = np.abs(c_mid - p_mid)
chosen = sorted(strike[np.argsort(gap, kind="mergesort")[:4]].tolist())
print(f"strikes chosen by the code: {chosen}; F = {F!r}")
want = sorted(strike[[0, 1, 3, 2]].tolist())
print(f"ADR rule (tie to the lower strike) would choose: {want}")
print("RESULT", "PASS (tie to the lower strike)" if chosen == want else "REFUTED (tie went to the higher strike)")
