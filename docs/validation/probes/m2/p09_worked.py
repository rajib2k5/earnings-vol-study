"""p09: the AAPL worked example from worked.py's quotes, with nothing from the code under test or worked.py's code.

Claim 9. Reads only worked.py's literal quotes and r (ast, not run). Sessions from exchange_calendars.
Pricer: Black-76 with scipy.stats.norm; inversion by bisection. Forward: exact cents |C - P|, ties to the
lower strike, median of 4. OTM side, mid, bracket linear in k. E = (w1 t2 - w2 t1)/(t2 - t1).
Run from the repository root:  python docs/validation/probes/m2/p09_worked.py [--mutant-allstrikes]
"""
import ast
import math
import sys
from datetime import date
from pathlib import Path

import exchange_calendars as xcals
from scipy.stats import norm

lit = {}
for node in ast.parse(Path("research/prototypes/worked.py").read_text()).body:
    if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id in ("chain", "chain0", "r"):
        lit[node.targets[0].id] = ast.literal_eval(node.value)
ALL = "--mutant-allstrikes" in sys.argv
S = [t.date() for t in xcals.get_calendar("XNYS", start="2025-01-02", end="2026-12-31").sessions]


def px(F, K, w, DF, call):
    s = math.sqrt(w); d1 = (math.log(F / K) + w / 2) / s; d2 = d1 - s
    return DF * (F * norm.cdf(d1) - K * norm.cdf(d2)) if call else DF * (K * norm.cdf(-d2) - F * norm.cdf(-d1))


def inv(mid, F, K, DF, call):
    lo, hi = math.log(1e-8), math.log(4.0)
    for _ in range(80):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if px(F, K, math.exp(m), DF, call) < mid else (lo, m)
    return math.exp((lo + hi) / 2)


def ok(b, a):
    m = (b + a) / 2
    return 0 < b < a and m >= 0.05 and (a - b) / m <= 0.5


def atom(day, exp, ch):
    cal = (exp - day).days
    tau = sum(1 for s in S if day < s <= exp)
    DF = math.exp(-lit["r"] * cal / 365)
    rows = sorted(ch.items())
    pairs = [(abs(round((cb + ca) * 100) - round((pb + pa) * 100)), K, K + ((cb + ca) / 2 - (pb + pa) / 2) / DF)
             for K, (cb, ca, pb, pa) in rows if ok(cb, ca) and ok(pb, pa)]
    use = sorted(pairs)[: (len(pairs) if ALL else 4)]
    fk = sorted(x[2] for x in use)
    F = (fk[(len(fk) - 1) // 2] + fk[len(fk) // 2]) / 2
    pts = []
    for K, (cb, ca, pb, pa) in rows:
        call = K >= F
        b, a = (cb, ca) if call else (pb, pa)
        mid = (b + a) / 2
        if ok(b, a) and abs(math.log(K / F)) <= 0.5:
            pts.append((math.log(K / F), inv(mid, F, K, DF, call), K))
    lo = max((p for p in pts if p[0] <= 0), key=lambda p: p[0])
    hi = min((p for p in pts if p[0] > 0), key=lambda p: p[0])
    w = lo[1] + (0 - lo[0]) / (hi[0] - lo[0]) * (hi[1] - lo[1])
    return F, (lo[2], hi[2]), w, tau, math.sqrt(252 * w / tau)


out = {}
for day, ch in ((date(2025, 10, 30), lit["chain"]), (date(2025, 10, 31), lit["chain0"])):
    for e, v in ch.items():
        F, br, w, tau, iv = atom(day, date.fromisoformat(e), v)
        out[(day, e)] = (w, tau, iv, F)
        print(f"{day} {e}: F={F:.4f} bracket={br} w={w:.9f} tau={tau} iv={iv:.4f}")
(w1, t1, s1, F1), (w2, t2, s2, _) = out[(date(2025, 10, 30), "2025-11-14")], out[(date(2025, 10, 30), "2025-11-28")]
E = (w1 * t2 - w2 * t1) / (t2 - t1)
sd2 = (w2 - w1) / (t2 - t1)
print(f"E = {E:.8f}  sqrt(E) = {math.sqrt(E):.4%}  sigma_d,ann = {math.sqrt(252 * sd2):.4f}  "
      f"abs_move_total = {math.sqrt(2 / math.pi) * math.sqrt(E + sd2):.4%}")
F0 = out[(date(2025, 10, 31), "2025-11-14")][3]
print(f"realised = {math.log(F0 / F1) + lit['r'] / 365:.4%}; front crush = "
      f"{math.log(out[(date(2025, 10, 31), '2025-11-14')][2] / s1):.4f}")
ok_ = abs(E - 0.00088284) < 5e-9 and f"{math.sqrt(E):.4%}" == "2.9713%"
print("RESULT", "PASS" if ok_ else "FAIL", "[MUTANT all strikes]" if ALL else "")
sys.exit(0 if ok_ else 1)
