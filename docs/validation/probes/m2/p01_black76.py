"""p01: Black-76 pricing and inversion (claims 1a-1d).

Run from the repository root:  python docs/validation/probes/m2/p01_black76.py [--mutant]
--mutant plants d1 = (ln(F/K) + w)/sqrt(w) in a copy of black76 (falsifier for 1a/1b).
The oracle is the textbook formula written here with scipy.stats.norm; it is the
reference, not the code under test.
"""
import math
import sys

import numpy as np
from scipy.stats import norm

from earnings_vol.measures import black, chain

MUTANT = "--mutant" in sys.argv
if MUTANT:
    from scipy.special import ndtr

    def _mut(f, k, w, df, call):
        s = np.sqrt(w)
        d1 = (np.log(f / k) + w) / s
        d2 = d1 - s
        c = df * (f * ndtr(d1) - k * ndtr(d2))
        p = df * (k * ndtr(-d2) - f * ndtr(-d1))
        return np.where(call, c, p)

    black.black76 = _mut


def textbook(f, k, w, df, call):
    s = math.sqrt(w)
    d1 = (math.log(f / k) + 0.5 * w) / s
    d2 = d1 - s
    if call:
        return df * (f * norm.cdf(d1) - k * norm.cdf(d2))
    return df * (k * norm.cdf(-d2) - f * norm.cdf(-d1))


fails = 0
F, DF = 271.42, math.exp(-0.039 * 15 / 365)
# 1a: price against the textbook formula, and parity
worst_price, worst_parity = 0.0, 0.0
for k in np.linspace(-3, 3, 61):
    K = F * math.exp(k)
    for w in (1e-8, 1e-6, 1e-4, 3.486e-3, 0.05, 0.5, 4.0):
        for call in (True, False):
            got = float(black.black76(F, K, w, DF, call))
            worst_price = max(worst_price, abs(got - textbook(F, K, w, DF, call)) / F)
        c, p = float(black.black76(F, K, w, DF, True)), float(black.black76(F, K, w, DF, False))
        worst_parity = max(worst_parity, abs((c - p) - DF * (F - K)) / F)
print(f"1a max |black76 - textbook|/F = {worst_price:.3e}; max parity residual/F = {worst_parity:.3e}")
if worst_price > 1e-12 or worst_parity > 1e-12:
    fails += 1
    print("1a FAIL")

# 1b: round trip on the OTM side, deep OTM and near-zero time value included
worst_rel, n_solved, n_noroot, worst_case = 0.0, 0, 0, None
for k in np.linspace(-0.5, 0.5, 41):
    K = F * math.exp(k)
    call = K >= F
    for w in (1e-7, 1e-6, 1e-5, 1e-4, 1e-3, 3.486e-3, 0.02, 0.2, 1.0, 3.9):
        mid = textbook(F, K, w, DF, call)
        got = black.implied_w(mid, F, K, DF, call)
        if got is None:
            n_noroot += 1
            continue
        n_solved += 1
        rel = abs(got - w) / w
        if rel > worst_rel:
            worst_rel, worst_case = rel, (round(k, 3), w, mid)
print(f"1b solved {n_solved}, no-root {n_noroot}; worst rel err {worst_rel:.3e} at (k, w, mid) = {worst_case}")
if worst_rel > 1e-6:
    fails += 1
    print("1b FAIL")

# 1b': the ATM forward straddle inversion
for w in (1e-4, 3.486e-3, 0.3):
    pi = 2 * textbook(F, F, w, DF, True)
    ws = black.straddle_w(pi, F, DF)
    print(f"1b' straddle w={w}: back {ws:.15g} rel {abs(ws - w) / w:.2e}")

# 1c: no root -> None, never clipped or widened
for call, K in ((True, F * 1.2), (False, F * 0.8)):
    hi = float(black.black76(F, K, 4.0, DF, call))
    lo = float(black.black76(F, K, 1e-8, DF, call))
    res = [black.implied_w(hi, F, K, DF, call), black.implied_w(hi * 1.01, F, K, DF, call),
           black.implied_w(lo, F, K, DF, call), black.implied_w(max(lo * 0.5, 0.0), F, K, DF, call)]
    print(f"1c call={call} at/above w=4 and at/below w=1e-8 -> {res}")
    if any(r is not None for r in res):
        fails += 1
        print("1c FAIL")

# 1d: corrupt one OTM strike; the atom must equal the chain without it
def chain_from_surface(strikes, w_of_k, f=100.0, df=1.0, half_spread=0.02):
    cb, ca, pb, pa = [], [], [], []
    for K in strikes:
        w = w_of_k(math.log(K / f))
        c, p = textbook(f, K, w, df, True), textbook(f, K, w, df, False)
        cb.append(c - half_spread); ca.append(c + half_spread)
        pb.append(p - half_spread); pa.append(p + half_spread)
    arr = lambda x: np.array(x, float)
    nan = np.full(len(strikes), np.nan)
    return chain.ExpiryQuotes(arr(strikes), arr(cb), arr(ca), arr(pb), arr(pa), nan, nan)


smile = lambda k: 0.004 + 0.002 * k + 0.03 * k * k
strikes = [80, 85, 90, 95, 97.5, 100, 102.5, 105, 110, 115, 120]
base = chain_from_surface(strikes, smile, f=101.0)  # F off-strike so the upper bracket strike carries weight
ref = chain.expiry_atom(base, 1.0, 10)
print(f"1d reference: w_atm={ref['w_atm']:.10f} bracket {ref['strike_lo']}/{ref['strike_hi']} status {ref['status']}")
# corrupt the OTM side of strike 102.5 (a call, the upper bracket strike) in four ways
i = strikes.index(102.5)
for label, bid, ask in (("bid=0", 0.0, None), ("crossed", None, "below_bid"), ("locked", None, "equal"),
                        ("nan", np.nan, np.nan)):
    cb, ca = base.call_bid.copy(), base.call_ask.copy()
    if label == "bid=0":
        cb[i] = 0.0
    elif label == "crossed":
        ca[i] = cb[i] - 0.01
    elif label == "locked":
        ca[i] = cb[i]
    else:
        cb[i], ca[i] = np.nan, np.nan
    q = chain.ExpiryQuotes(base.strike, cb, ca, base.put_bid, base.put_ask, base.call_vol, base.put_vol)
    got = chain.expiry_atom(q, 1.0, 10)
    keep = [j for j in range(len(strikes)) if j != i]
    sub = chain.ExpiryQuotes(*(np.asarray(getattr(base, n))[keep] for n in
                               ("strike", "call_bid", "call_ask", "put_bid", "put_ask", "call_vol", "put_vol")))
    want = chain.expiry_atom(sub, 1.0, 10)
    same = got["w_atm"] == want["w_atm"] and got["strike_hi"] == want["strike_hi"]
    print(f"1d {label:8s}: w_atm={got['w_atm']:.10f} hi={got['strike_hi']} | without strike: {want['w_atm']:.10f} "
          f"hi={want['strike_hi']} -> {'same' if same else 'DIFFERENT'}")
    if not same:
        fails += 1

print("RESULT", "FAIL" if fails else "PASS", f"({fails} failing checks){' [MUTANT]' if MUTANT else ''}")
sys.exit(1 if fails else 0)
