"""Probe C3a-e, C3g: ADR 0003 event-variance algebra, units, blind-interpolation leak, and the AAPL worked example
re-computed under the ADR's OWN forward rule (median F_K over the 4 strikes with the smallest |C_mid - P_mid|,
ADR 0003 §0 step 2), which research/prototypes/worked.py does not implement (it takes the median over all strikes).
Run: uv run --no-sync --frozen python docs/validation/probes/m0-methodology/p03_algebra.py
"""
import contextlib
import io
from pathlib import Path

import numpy as np
from scipy.optimize import brentq
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[4]
rng = np.random.default_rng(3)

# ---- C3a / C3b: w-form vs model vs IV-form, random inputs
worst_a = worst_b = 0.0
for _ in range(10000):
    sd2 = rng.uniform(1e-5, 1e-3); E = rng.uniform(-1e-3, 5e-3)
    t1 = int(rng.integers(5, 30)); t2 = t1 + int(rng.integers(1, 40))
    w1, w2 = sd2 * t1 + E, sd2 * t2 + E
    Ew = (w1 * t2 - w2 * t1) / (t2 - t1)
    s1, s2 = np.sqrt(252 * w1 / t1 + 0j).real, np.sqrt(252 * w2 / t2 + 0j).real
    if w1 <= 0 or w2 <= 0:
        continue
    Eiv = t1 * t2 * (s1**2 - s2**2) / (252 * (t2 - t1))
    worst_a = max(worst_a, abs(Ew - E)); worst_b = max(worst_b, abs(Eiv - Ew) / max(abs(Ew), 1e-12))
print(f"C3a max|E_wform - E_true| = {worst_a:.2e};  C3b max rel|E_ivform - E_wform| = {worst_b:.2e}")
# falsifier: IV-form without 252
print("C3b falsifier: IV-form without /252 over w-form ratio =",
      (t1 * t2 * (s1**2 - s2**2) / (t2 - t1)) / Ew)

# ---- C3c / C3d: blind interpolation leak
def blind(sd2, E, ta, tb, ts):
    wa, wb = sd2 * ta, sd2 * tb + E
    return wa + (ts - ta) / (tb - ta) * (wb - wa)
sd2 = 0.25**2 / 252
for E in (0.0007, 0.003):
    wb = blind(sd2, E, 19, 32, 21)
    formula = sd2 * 21 + E * (21 - 19) / (32 - 19)
    leak_vol = np.sqrt(252 * wb / 21) - 0.25
    print(f"C3c E={E}: interp {wb:.10f} formula {formula:.10f} | C3d leak = {100*leak_vol:.3f} vol pts")
# leak range over the vendor grid described in ADR 0003 (second expiry 17-21, third 27-42 sessions)
fr = [(21 - ta) / (tb - ta) for ta in range(17, 22) for tb in range(27, 43)]
print(f"   leak fraction (tau*-tau_a)/(tau_b-tau_a) over tau_a 17..21, tau_b 27..42: min {min(fr):.3f} median {np.median(fr):.3f} max {max(fr):.3f}")
for E in (0.0007, 0.003):
    lk = [np.sqrt(0.25**2 + 252 * E * f / 21) - 0.25 for f in (np.median(fr), max(fr))]
    print(f"   E={E}: leak at median fraction {100*lk[0]:.2f}, at max fraction {100*lk[1]:.2f} vol pts")

# ---- C3e: worked example, worked.py's rule vs the ADR's 4-strike rule
ns = {}
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile((ROOT / "research/prototypes/worked.py").read_text(), "worked.py", "exec"), ns)
chain, chain0, cal_days, td, r = ns["chain"], ns["chain0"], ns["cal_days"], ns["td"], ns["r"]


def black(F, K, w, DF, cp):
    s = np.sqrt(w); d1 = (np.log(F / K) + 0.5 * w) / s; d2 = d1 - s
    return DF * (F * norm.cdf(d1) - K * norm.cdf(d2)) if cp == "C" else DF * (K * norm.cdf(-d2) - F * norm.cdf(-d1))


def atm(snap, exp, ch, rule):
    DF = np.exp(-r * cal_days[(snap, exp)] / 365); q = ch[exp]
    items = [(K, (cb + ca) / 2 - (pb + pa) / 2) for K, (cb, ca, pb, pa) in q.items()]
    if rule == "adr4":
        items = sorted(items, key=lambda kv: abs(kv[1]))[:4]
    F = float(np.median([K + d / DF for K, d in items]))
    Ks = sorted(q); lo = max(k for k in Ks if k <= F); hi = min(k for k in Ks if k > F)

    def wK(K):
        cb, ca, pb, pa = q[K]
        cp, p = ("P", (pb + pa) / 2) if K < F else ("C", (cb + ca) / 2)
        return brentq(lambda w: black(F, K, w, DF, cp) - p, 1e-8, 4.0)
    kl, kh = np.log(lo / F), np.log(hi / F)
    return F, lo, hi, wK(lo) + (0 - kl) / (kh - kl) * (wK(hi) - wK(lo))


for rule in ("worked.py (median of all strikes)", "adr4"):
    key = "adr4" if rule == "adr4" else "all"
    res = {(s, e): atm(s, e, ch, key) for s, ch in (("2025-10-30", chain), ("2025-10-31", chain0)) for e in ch}
    w1, w2 = res[("2025-10-30", "2025-11-14")][3], res[("2025-10-30", "2025-11-28")][3]
    E = (w1 * 20 - w2 * 11) / 9; sd2 = (w2 - w1) / 9
    Ec = (w1 * 29 - w2 * 15) / 14
    print(f"\n[{rule}]")
    for kk, (F, lo, hi, w) in res.items():
        print(f"  {kk}: F={F:.3f} bracket=({lo},{hi}) w={w:.6f} IV252={np.sqrt(252*w/td[kk]):.4f} IV365={np.sqrt(365*w/cal_days[kk]):.4f}")
    print(f"  E={E:.8f} sd2={sd2:.4e} (ann {np.sqrt(252*sd2):.4f}) sqrtE={np.sqrt(E):.4%} abs={np.sqrt(2/np.pi*E):.4%} "
          f"total={np.sqrt(2/np.pi*(E+sd2)):.4%} straddle_T1={np.sqrt(2/np.pi*w1):.4%} | calendar E={Ec:.6f} sqrt={np.sqrt(Ec):.4%}")
    if key == "all":
        s1, s2 = np.sqrt(252 * w1 / 11), np.sqrt(252 * w2 / 20)
        print(f"  IV-form minus w-form on unrounded w: {11*20*(s1**2-s2**2)/(252*9) - E:.2e}")
        # C3g: CRUSH split from the same w's
        w01, w02 = res[("2025-10-31", "2025-11-14")][3], res[("2025-10-31", "2025-11-28")][3]
        sdA_m1, sdA_0 = 252 * sd2, 252 * (w02 - w01) / 9
        dsig = 0.5 * np.log(sdA_0 / sdA_m1); ev = -0.5 * np.log(1 + 252 * E / (21 * sdA_m1))
        print(f"  C3g: dsigma term {dsig:.4f}, event term {ev:.4f}, CRUSH {dsig+ev:.4f}")
