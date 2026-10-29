# Data notice: the option quotes in `chain` and `chain0` below (bid and ask, a few strikes of
# two expiries on two days) come from the DoltHub database post-no-preference/options, licensed
# under Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0):
# https://www.dolthub.com/repositories/post-no-preference/options
# Attribution: DoltHub, post-no-preference. We selected the rows we copied here. The quotes stay
# under CC BY-SA 4.0, not the repository's MIT licence; see data/derived/README.md.
"""ADR 0003's hand-worked AAPL example (AMC 2025-10-30: day -1 = 2025-10-30, day 0 = 2025-10-31).

Follows ADR 0003 §0 step by step, including the forward rule: F = the median of F_K over the (up to) 4 strikes with
the smallest |C_mid - P_mid| (ties: lower strike first). Revised after the milestone-0 review (ledger N1): the first
version took the median over ALL strikes, which is not the ADR's rule; on the 10-30 / 11-14 expiry (7 strikes) that
moved E by +27%. The old rule is printed once at the end, for the record only.

The identity check can fail: it compares the w-form of E with the textbook form applied to the IVs the pipeline
REPORTS (sqrt(252 w / tau)), with time in years (tau / 252). It is run a second time with a planted bug (time in
sessions, i.e. the 252 dropped) and must fail there, which shows the check has teeth.
Run: uv run --no-sync --frozen python research/prototypes/worked.py > research/prototypes/worked.out.txt
"""
import numpy as np
from scipy.optimize import brentq
from scipy.stats import norm


def black(F, K, w, DF, cp):
    s = np.sqrt(w); d1 = (np.log(F / K) + 0.5 * w) / s; d2 = d1 - s
    return DF * (F * norm.cdf(d1) - K * norm.cdf(d2)) if cp == 'C' else DF * (K * norm.cdf(-d2) - F * norm.cdf(-d1))


W_LO, W_HI = 1e-8, 4.0
r = 0.039
# AAPL snapshot 2025-10-30 (day -1). expiry -> {strike: (call_bid, call_ask, put_bid, put_ask)}
chain = {
 '2025-11-14': {262.5:(10.85,13.35,2.88,2.95),265.0:(10.10,12.20,3.65,4.50),267.5:(8.60,9.25,3.75,5.00),
                272.5:(5.60,6.25,6.05,8.10),275.0:(4.50,5.05,7.85,8.70),277.5:(3.00,4.10,9.05,10.35),280.0:(3.00,3.15,11.10,11.65)},
 '2025-11-28': {265.0:(11.75,12.15,4.00,5.05),270.0:(8.05,9.50,6.80,7.75),275.0:(6.35,6.65,8.60,10.25),280.0:(4.50,4.70,10.65,14.40)},
}
# AAPL snapshot 2025-10-31 (day 0)
chain0 = {
 '2025-11-14': {267.5:(6.70,6.80,3.65,3.75),270.0:(5.30,5.40,4.75,4.85),272.5:(4.15,4.20,6.05,6.20),275.0:(3.15,3.25,7.60,7.70)},
 '2025-11-28': {265.0:(10.35,10.45,4.35,4.45),270.0:(7.40,7.55,6.45,6.55),275.0:(5.10,5.20,9.15,9.30),280.0:(3.40,3.50,12.45,12.60)},
}
cal_days = {('2025-10-30','2025-11-14'):15,('2025-10-30','2025-11-28'):29,('2025-10-31','2025-11-14'):14,('2025-10-31','2025-11-28'):28}
# NYSE sessions in (snapshot, expiry] (Thanksgiving 11-27 closed; the 11-28 half day counts as 1)
td = {('2025-10-30','2025-11-14'):11,('2025-10-30','2025-11-28'):20,('2025-10-31','2025-11-14'):10,('2025-10-31','2025-11-28'):19}


def leg_ok(bid, ask):
    """ADR 0003 §0 step 1, first part: 0 < bid < ask, mid >= 0.05, (ask - bid)/mid <= 0.5."""
    mid = (bid + ask) / 2
    return 0 < bid < ask and mid >= 0.05 and (ask - bid) / mid <= 0.5


def atm_w(snap, exp, ch, rule='adr4'):
    DF = np.exp(-r * cal_days[(snap, exp)] / 365)
    q = ch[exp]
    # step 2: parity forward from strikes quoted on both sides
    both = [(K, (cb + ca) / 2 - (pb + pa) / 2) for K, (cb, ca, pb, pa) in sorted(q.items())
            if leg_ok(cb, ca) and leg_ok(pb, pa)]
    used = sorted(both, key=lambda kd: (abs(kd[1]), kd[0]))[:4] if rule == 'adr4' else both
    FK = {K: K + d / DF for K, d in used}
    F = float(np.median(list(FK.values())))
    disp = (max(FK.values()) - min(FK.values())) / F
    # steps 1 (second part) and 3: OTM side, moneyness, no-arbitrage bounds, Brent with a root guaranteed
    valid = {}
    for K, (cb, ca, pb, pa) in q.items():
        cp, bid, ask = ('P', pb, pa) if K < F else ('C', cb, ca)
        mid = (bid + ask) / 2
        if not leg_ok(bid, ask) or abs(np.log(K / F)) > 0.5:
            continue
        lo_b = max(DF * (F - K), 0) if cp == 'C' else max(DF * (K - F), 0)
        hi_b = DF * F if cp == 'C' else DF * K
        if not lo_b <= mid <= hi_b:
            continue
        if not black(F, K, W_LO, DF, cp) < mid < black(F, K, W_HI, DF, cp):
            continue  # ADR 0003 §0 step 3: no root on [1e-8, 4] -> strike invalid (`iv_no_root`), never extrapolated
        valid[K] = brentq(lambda w: black(F, K, w, DF, cp) - mid, W_LO, W_HI)
    Ks = sorted(valid)
    lo = max(k for k in Ks if np.log(k / F) <= 0); hi = min(k for k in Ks if np.log(k / F) > 0)
    kl, kh = np.log(lo / F), np.log(hi / F)
    w0 = valid[lo] + (0 - kl) / (kh - kl) * (valid[hi] - valid[lo])
    assert kh - kl <= 1.5 * np.sqrt(w0), 'bracket wider than 1.5 sd: ADR 0003 §0 step 4 would use the quadratic'
    return dict(F=F, FK=FK, disp=disp, lo=lo, hi=hi, w=w0, DF=DF)


def E_wform(w1, w2, t1, t2):
    return (w1 * t2 - w2 * t1) / (t2 - t1)


def iv_reported(w, tau):
    return np.sqrt(252 * w / tau)            # ADR 0003 §0 step 6, what `chain_expiry.iv_atm` stores


def E_textbook(s1, s2, T1, T2):
    return T1 * T2 * (s1 ** 2 - s2 ** 2) / (T2 - T1)   # the brief's formula; T must be in years


def check(name, a, b, rel=1e-12):
    ok = abs(a - b) <= rel * max(abs(a), abs(b))
    print(f"  {name}: {a:.12e} vs {b:.12e} -> {'PASS' if ok else 'FAIL'}")
    return ok


res = {}
for snap, ch in (('2025-10-30', chain), ('2025-10-31', chain0)):
    for exp in ch:
        a = atm_w(snap, exp, ch)
        res[(snap, exp)] = a
        print(f"{snap} exp {exp}: F_K used {', '.join(f'{K:g}:{v:.2f}' for K, v in sorted(a['FK'].items()))} -> "
              f"F={a['F']:.2f} (dispersion {a['disp']:.2%}) bracket=({a['lo']:g},{a['hi']:g}) w={a['w']:.6f} "
              f"tau={td[(snap, exp)]}/{cal_days[(snap, exp)]} IV_252={iv_reported(a['w'], td[(snap, exp)]):.4f} "
              f"IV_365={np.sqrt(365 * a['w'] / cal_days[(snap, exp)]):.4f}")

w1, w2 = res[('2025-10-30', '2025-11-14')]['w'], res[('2025-10-30', '2025-11-28')]['w']
E = E_wform(w1, w2, 11, 20); sd2 = (w2 - w1) / 9
Ec = E_wform(w1, w2, 15, 29)
print(f"\nsession clock: sigma_d^2 = {sd2:.4e} per session ({np.sqrt(252 * sd2):.4f} annualised); E = {E:.8f}")
print(f"  implied_move sqrt(E) = {np.sqrt(E):.4%}; implied_abs_move = {np.sqrt(2 / np.pi * E):.4%}; "
      f"implied_abs_move_total = {np.sqrt(2 / np.pi * (E + sd2)):.4%}")
print(f"  straddle 'implied move' over T1's life = 0.798 sqrt(w1) = {np.sqrt(2 / np.pi * w1):.4%}; "
      f"event share of w1 = {E / w1:.1%}")
print(f"calendar clock: E = {Ec:.8f}, sqrt(E) = {np.sqrt(Ec):.4%}; E ratio calendar/session = {Ec / E:.3f}, "
      f"sqrt ratio = {np.sqrt(Ec / E):.3f}")
print(f"textbook IV form from the 4-dp IVs in ADR 0003's table: "
      f"{E_textbook(round(iv_reported(w1, 11), 4), round(iv_reported(w2, 20), 4), 11 / 252, 20 / 252):.8f}")

print("\nidentity check (must PASS), w-form vs textbook form on the REPORTED IVs, time in years:")
s1, s2 = iv_reported(w1, 11), iv_reported(w2, 20)
assert check('E', E_wform(w1, w2, 11, 20), E_textbook(s1, s2, 11 / 252, 20 / 252))
print("falsifier (must FAIL): the same with time in sessions, i.e. the factor 252 dropped:")
assert not check('E', E_wform(w1, w2, 11, 20), E_textbook(s1, s2, 11, 20))
print(f"  ratio {E_textbook(s1, s2, 11, 20) / E:.4f} (= 252)")

w01, w02 = res[('2025-10-31', '2025-11-14')]['w'], res[('2025-10-31', '2025-11-28')]['w']
sdA_m1, sdA_0 = 252 * sd2, 252 * (w02 - w01) / 9
dsig = 0.5 * np.log(sdA_0 / sdA_m1); ev = -0.5 * np.log(1 + 252 * E / (21 * sdA_m1))
print(f"\nADR 0004 §3 crush split (model, two front expiries): dsigma term {dsig:.4f} + event term {ev:.4f} = {dsig + ev:.4f}")
iv_m1, iv_0 = iv_reported(w1, 11), iv_reported(w01, 10)
print(f"front fixed-expiry (11-14) IV: day -1 {iv_m1:.4f}, day 0 {iv_0:.4f}: {100 * (iv_0 - iv_m1):.2f} vol points, "
      f"log {np.log(iv_0 / iv_m1):.4f}")
F_m1, F_0 = res[('2025-10-30', '2025-11-14')]['F'], res[('2025-10-31', '2025-11-14')]['F']
print(f"realised move from the 11-14 forwards (ADR 0003 §e): ln({F_0:.2f}/{F_m1:.2f}) + r*1/365 = "
      f"{np.log(F_0 / F_m1) + r / 365:.4%}")

old = atm_w('2025-10-30', '2025-11-14', chain, rule='all')
print(f"\nfor the record, the first prototype's rule (median over all 7 strikes): F={old['F']:.2f} w={old['w']:.6f} "
      f"E={E_wform(old['w'], w2, 11, 20):.8f} (ADR rule E / old E = {E / E_wform(old['w'], w2, 11, 20):.3f})")
