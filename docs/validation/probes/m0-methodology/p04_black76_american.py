"""Probe C4a-d: Black-76 inversion bracket, day-count dependence, American early-exercise bias (ADR 0003 §d table)
and its propagation into E through the ADR's own pipeline (parity forward from the 4 strikes with the smallest
|C-P|, OTM side, linear-in-k ATM interpolation, session clock).
Run: uv run --no-sync --frozen python docs/validation/probes/m0-methodology/p04_black76_american.py
"""
import numpy as np
from scipy.optimize import brentq
from scipy.stats import norm


def black(F, K, w, DF, cp):
    s = np.sqrt(w); d1 = (np.log(F / K) + 0.5 * w) / s; d2 = d1 - s
    return DF * (F * norm.cdf(d1) - K * norm.cdf(d2)) if cp == "C" else DF * (K * norm.cdf(-d2) - F * norm.cdf(-d1))


# ---- C4a: is there always a root in [1e-8, 4] for prices allowed by the §0 filter?
F, DF = 271.4, 0.998
worst = min(black(F, F * np.exp(k), 4.0, DF, "C") / (DF * F) for k in np.linspace(0, 0.5, 51))
print(f"C4a: min over k in [0,0.5] of Black76(w=4)/(DF*F) for OTM calls = {worst:.3f}; "
      f"the filter allows C up to DF*F, so a mid in ({worst:.3f}, 1]*DF*F passes the filter and has no root")
try:
    brentq(lambda w: black(F, F * np.exp(0.5), w, DF, "C") - 0.8 * DF * F, 1e-8, 4.0)
    print("   brentq found a root (unexpected)")
except ValueError as e:
    print("   brentq on such a quote raises:", e)
lo_edge = black(F, F, 1e-8, DF, "C")
print(f"   Black76 at w=1e-8, K=F: {lo_edge:.4f} (< the 0.05 minimum mid, so the lower end always brackets)")

# ---- C4b: price -> w uses only w and DF; DF uses a calendar day count
w_true = 0.003401
for name, DFx in (("cal/365 (15d)", np.exp(-0.039 * 15 / 365)), ("sessions/252 (11)", np.exp(-0.039 * 11 / 252))):
    p = black(F, 275.0, w_true, np.exp(-0.039 * 15 / 365), "C")
    w = brentq(lambda w: black(F, 275.0, w, DFx, "C") - p, 1e-8, 4)
    print(f"C4b: invert with DF {name}: w = {w:.7f} (true {w_true})")


# ---- C4c: CRR binomial, 2000 steps
def crr(S, K, T, sig, r, american, cp, n=2000):
    dt = T / n; u = np.exp(sig * np.sqrt(dt)); d = 1 / u; disc = np.exp(-r * dt)
    p = (np.exp(r * dt) - d) / (u - d)
    j = np.arange(n + 1); ST = S * u ** (n - j) * d ** j
    V = np.maximum(K - ST, 0) if cp == "P" else np.maximum(ST - K, 0)
    for i in range(n - 1, -1, -1):
        V = disc * (p * V[:-1] + (1 - p) * V[1:])
        if american:
            ST = ST[:-1] / u
            V = np.maximum(V, (K - ST) if cp == "P" else (ST - K))
    return V[0]


S, sig, r = 271.4, 0.27, 0.039
print("\nC4c: put        premium   IV bias(vol pts)  fwd bias(bp)   [ADR: 0.016/0.08/0.6, 0.026/0.12/1.0, 0.079/0.20/2.9, 0.103/0.26/3.8]")
for days in (15, 50):
    T = days / 365
    for lab, K in (("1.5% OTM", S * 0.985), ("ATM", S)):
        am, eu = crr(S, K, T, sig, r, True, "P"), crr(S, K, T, sig, r, False, "P")
        Fw, DFw = S * np.exp(r * T), np.exp(-r * T)
        iv = np.sqrt(brentq(lambda w: black(Fw, K, w, DFw, "P") - am, 1e-8, 4) / T)
        iv_eu = np.sqrt(brentq(lambda w: black(Fw, K, w, DFw, "P") - eu, 1e-8, 4) / T)
        print(f"   {lab:9s} {days}d  ${am-eu:.3f}   {100*(iv-iv_eu):.3f}             {1e4*(am-eu)/DFw/Fw:.2f}")


# ---- C4d: propagate into E through the ADR pipeline (AAPL-like grid, w1/w2 from the worked example)
def pipeline(prices, Ks, T_cal):
    DFx = np.exp(-r * T_cal)
    diffs = sorted(((K, prices[K][0] - prices[K][1]) for K in Ks), key=lambda kv: abs(kv[1]))[:4]
    Fx = float(np.median([K + dd / DFx for K, dd in diffs]))
    lo = max(k for k in Ks if k <= Fx); hi = min(k for k in Ks if k > Fx)

    def wK(K):
        cp, p = ("P", prices[K][1]) if K < Fx else ("C", prices[K][0])
        return brentq(lambda w: black(Fx, K, w, DFx, cp) - p, 1e-8, 4)
    kl, kh = np.log(lo / Fx), np.log(hi / Fx)
    return wK(lo) + (0 - kl) / (kh - kl) * (wK(hi) - wK(lo)), Fx


Ks = [262.5, 265.0, 267.5, 270.0, 272.5, 275.0, 277.5, 280.0]
res = {}
for S0 in (271.4, 270.2, 272.6):
    for lab, (Tc, w_t) in {"T1": (15 / 365, 0.003401), "T2": (29 / 365, 0.005616)}.items():
        sg = np.sqrt(w_t / Tc)
        for ex in (False, True):
            pr = {K: (crr(S0, K, Tc, sg, r, ex, "C"), crr(S0, K, Tc, sg, r, ex, "P")) for K in Ks}
            res[(S0, lab, ex)] = pipeline(pr, Ks, Tc)
    for ex in (False, True):
        w1, w2 = res[(S0, "T1", ex)][0], res[(S0, "T2", ex)][0]
        E = (w1 * 20 - w2 * 11) / 9
        E_true = (0.003401 * 20 - 0.005616 * 11) / 9
        print(f"C4d S={S0} {'American' if ex else 'European'}: w1 {w1:.6f} w2 {w2:.6f} E {E:.7f} "
              f"vs true {E_true:.7f} -> {100*(E/E_true-1):+.2f}%  (F1 {res[(S0,'T1',ex)][1]:.3f})")
