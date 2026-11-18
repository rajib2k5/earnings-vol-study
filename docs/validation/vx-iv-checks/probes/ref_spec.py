# =============================================================================
# ref_spec.py - A second implementation of ADR 0003 §0 (the atom) and §b (the
# 30-day interpolation), written from the ADR text and params.yaml, for rule
# (a) of the vx-iv-checks pre-registration: "the code does not do what ADR
# 0003 or params.yaml says".
#
# INDEPENDENCE, STATED HONESTLY
#   The author read src/earnings_vol/measures/*.py before writing this file,
#   so it is not a blind re-implementation. It shares no code with the
#   package: plain Python loops, its own Black-76 (math.erfc), its own root
#   finder (bisection, not Brent), its own weighted least squares (normal
#   equations, not lstsq), and it reads params.yaml itself.
#
# WHERE THE ADR IS SILENT
#   Each point has a default choice (the one below, which is also the
#   package's) and one or two alternatives, selected by `choices`. A mismatch
#   with the package is "unspecified", not a bug, ONLY when the code shows it:
#   ivchecks.differential reruns this file with each alternative, and tags the
#   mismatch with the S-point whose alternative makes it go away, or with
#   "boundary" when an input sits within 1e-9 (relative) of a threshold
#   (`margin` below). A mismatch with no tag is a bug candidate (rule (a)).
#   S1  A strike listed twice in one expiry: not handled (the input has one row
#       per strike); tagged when the input has a duplicate strike.
#   S2  The median of an even count: the mean of the two middle values
#       (alternatives: the lower, the upper middle value).
#   S3  The quadratic's weight: weight 1/rel multiplies the squared residual
#       (alternatives: 1/rel^2, no weight).
#   S4  The quadratic's "each side of k = 0": k <= 0 and k > 0, as the bracket
#       (alternative: k < 0 and k >= 0).
#   S5  Two usable expiries with the same tau: the earlier expiration is kept
#       (alternative: the later one).
#   S6  The blind series with one usable expiry: flat sigma within 10 sessions
#       (the ADR only says "all expiries interpolated"; alternative: no value).
#   S7  w* <= 0 after interpolation: no IV (null); tagged when it happens.
#   `matters` (in every result) lists the S-points whose choice changes THIS
#   result. ivchecks.differential accepts an alternative only when it is
#   consistent: no matching atom (or day) where the point matters, and every
#   mismatching one where it matters is removed by the same alternative. A
#   package that used the alternative throughout passes; a bug that the
#   alternative removes only here and there does not.
#
# THE 30-DAY PART READS ITS OWN ATOMS
#   ref_cm30 takes (tau, w, expiration, spans) from this file's ref_atom, tau
#   from the exchange_calendars list, and spans from the events table (first
#   session on or after the announcement date), not from the package.
# =============================================================================

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml

SQRT2 = math.sqrt(2.0)


@dataclass(frozen=True)
class RefParams:
    min_mid: float
    max_rel_spread: float
    max_abs_log_moneyness: float
    forward_strikes: int
    w_min: float
    w_max: float
    bracket_max_sd: float
    quadratic_max_sd: float
    quadratic_min_strikes: int
    horizon: int
    tau_min: int
    max_extrap: int


DEFAULT = {"S2": "mean", "S3": "w", "S4": "le", "S5": "earlier", "S6": "flat"}
ALTERNATIVES = {"S2": ("lower", "upper"), "S3": ("w2", "none"), "S4": ("lt",), "S5": ("later",), "S6": ("none",)}


def load_params(path: Path) -> RefParams:
    iv = yaml.safe_load(Path(path).read_text())["iv"]
    return RefParams(float(iv["min_mid"]), float(iv["max_rel_spread"]), float(iv["max_abs_log_moneyness"]),
                     int(iv["forward_strikes"]), float(iv["w_min"]), float(iv["w_max"]), float(iv["bracket_max_sd"]),
                     float(iv["quadratic_max_sd"]), int(iv["quadratic_min_strikes"]), int(iv["cm30_horizon_sessions"]),
                     int(iv["tau_min_sessions"]), int(iv["cm30_max_extrap_sessions"]))


def _n(x: float) -> float:
    return 0.5 * math.erfc(-x / SQRT2)


def b76(f: float, k: float, w: float, df: float, call: bool) -> float:
    s = math.sqrt(w)
    d1 = (math.log(f / k) + w / 2.0) / s
    d2 = d1 - s
    return df * (f * _n(d1) - k * _n(d2)) if call else df * (k * _n(-d2) - f * _n(-d1))


def _solve_w(mid: float, f: float, k: float, df: float, call: bool, lo: float, hi: float) -> float:
    """Bisection on the increasing function b76(w) - mid, to the last bit of a double."""
    for _ in range(300):
        m = 0.5 * (lo + hi)
        if m <= lo or m >= hi:
            break
        if b76(f, k, m, df, call) < mid:
            lo = m
        else:
            hi = m
    return 0.5 * (lo + hi)


def _fin(x) -> bool:
    return x is not None and math.isfinite(x)


def _leg_ok(b: float, a: float, p: RefParams) -> bool:
    # ADR §0 step 1, first part: 0 < bid < ask, mid >= 0.05, (ask - bid)/mid <= 0.5.
    if not (_fin(b) and _fin(a)) or not (0.0 < b < a):
        return False
    m = (b + a) / 2.0
    return m >= p.min_mid and (a - b) / m <= p.max_rel_spread


def _rel(x: float, edge: float) -> float:
    return abs(x - edge) / max(abs(edge), 1e-300)


def ref_atom(strike, cb, ca, pb, pa, df: float, tau: int, p: RefParams, choices=None) -> dict:
    """status, forward, forward_n_strikes, n_strikes_valid, strike_lo, strike_hi, atm_method, w_atm, iv_atm,
    and `margin`: the smallest relative distance of an input to a threshold that decided the outcome."""
    ch = {**DEFAULT, **(choices or {})}
    margin = [math.inf]

    def near(x, edge):
        margin[0] = min(margin[0], _rel(x, edge))

    def leg_ok(b, a):
        ok = _leg_ok(b, a, p)
        if _fin(b) and _fin(a) and 0.0 < b < a:
            m = (b + a) / 2.0
            near(m, p.min_mid)
            near((a - b) / m, p.max_rel_spread)
        return ok
    n = len(strike)
    K = [float(x) for x in strike]
    cok = [leg_ok(cb[i], ca[i]) for i in range(n)]
    pok = [leg_ok(pb[i], pa[i]) for i in range(n)]
    out = {"status": "no_forward", "forward": None, "forward_n_strikes": 0, "n_strikes_valid": 0,
           "strike_lo": None, "strike_hi": None, "atm_method": "none", "w_atm": None, "iv_atm": None,
           "margin": math.inf, "duplicate_strike": len(set(K)) != len(K), "matters": set()}
    # Step 2: the parity forward from the 4 strikes with the smallest |C - P| (as whole cents of 2|C - P|),
    # ties to the lower strike; with fewer, all of them.
    pairs = [i for i in range(n) if cok[i] and pok[i]]
    if not pairs:
        out["margin"] = margin[0]
        return out
    gap = {i: round(abs((cb[i] + ca[i]) - (pb[i] + pa[i])) * 100.0) for i in pairs}
    chosen = sorted(pairs, key=lambda i: (gap[i], K[i]))[:p.forward_strikes]
    fk = sorted(K[i] + ((cb[i] + ca[i]) / 2.0 - (pb[i] + pa[i]) / 2.0) / df for i in chosen)
    m = len(fk)
    if m % 2 == 0 and fk[m // 2 - 1] != fk[m // 2]:
        out["matters"].add("S2")         # the S2 choice changes the forward of this atom
    if m % 2:
        f = fk[m // 2]
    else:
        f = {"mean": 0.5 * (fk[m // 2 - 1] + fk[m // 2]), "lower": fk[m // 2 - 1], "upper": fk[m // 2]}[ch["S2"]]
    out.update(status="no_atm", forward=f, forward_n_strikes=m)
    # Step 1, second part, and step 3: the OTM leg (puts below F, calls at or above), |ln K/F| <= 0.5,
    # inside the no-arbitrage bounds, and a root strictly inside (w_min, w_max).
    valid = []          # (k, w, rel spread, strike)
    for i in range(n):
        call = K[i] >= f
        b, a, ok = (cb[i], ca[i], cok[i]) if call else (pb[i], pa[i], pok[i])
        if not ok:
            continue
        mid = (b + a) / 2.0
        k = math.log(K[i] / f)
        near(abs(k), p.max_abs_log_moneyness)
        if abs(k) > p.max_abs_log_moneyness:
            continue
        lower = max(df * (f - K[i]), 0.0) if call else max(df * (K[i] - f), 0.0)
        upper = df * f if call else df * K[i]
        if lower > 0:
            near(mid, lower)
        near(mid, upper)
        if not (lower <= mid <= upper):
            continue
        lo_p, hi_p = b76(f, K[i], p.w_min, df, call), b76(f, K[i], p.w_max, df, call)
        if lo_p > 0:
            near(mid, lo_p)
        near(mid, hi_p)
        if not (lo_p < mid < hi_p):
            continue
        valid.append((k, _solve_w(mid, f, K[i], df, call, p.w_min, p.w_max), (a - b) / mid, K[i]))
    out["n_strikes_valid"] = len(valid)
    for v in valid:
        margin[0] = min(margin[0], abs(v[0]))   # a strike at F: k = 0 decides its side (S4), in log units
    below = [v for v in valid if v[0] <= 0.0]
    above = [v for v in valid if v[0] > 0.0]
    if not below or not above:
        out["margin"] = margin[0]
        return out
    lo = max(below, key=lambda v: v[0])
    hi = min(above, key=lambda v: v[0])
    w_lin = lo[1] + (0.0 - lo[0]) / (hi[0] - lo[0]) * (hi[1] - lo[1])
    out.update(strike_lo=lo[3], strike_hi=hi[3])
    # Step 4: linear in k when the bracket is at most 1.5 sqrt(w) wide (w = the bracket's linear w).
    if w_lin > 0:
        near(hi[0] - lo[0], p.bracket_max_sd * math.sqrt(w_lin))
    if hi[0] - lo[0] <= p.bracket_max_sd * math.sqrt(max(w_lin, 0.0)):
        out.update(status="ok", atm_method="bracket_linear", w_atm=w_lin, iv_atm=math.sqrt(252.0 * w_lin / tau),
                   margin=margin[0])
        return out
    # Otherwise a quadratic in k, weighted by 1/(relative spread), through the valid strikes with
    # |k| <= 2 sqrt(w_lin); at least 4, at least one on each side of k = 0, intercept > 0.
    half = p.quadratic_max_sd * math.sqrt(max(w_lin, 0.0))
    for v in valid:
        if half > 0:
            near(abs(v[0]), half)
    win = [v for v in valid if abs(v[0]) <= half]
    if any(v[0] == 0.0 for v in win):
        out["matters"].add("S4")         # a strike exactly at F: the side rule decides
    left = (lambda k: k <= 0) if ch["S4"] == "le" else (lambda k: k < 0)
    if len(win) >= p.quadratic_min_strikes and any(left(v[0]) for v in win) and any(not left(v[0]) for v in win):
        x = np.array([[1.0, v[0], v[0] * v[0]] for v in win])
        y = np.array([v[1] for v in win])
        wt = np.array([{"w": 1.0 / v[2], "w2": 1.0 / (v[2] * v[2]), "none": 1.0}[ch["S3"]] for v in win])
        if len({v[2] for v in win}) > 1:
            out["matters"].add("S3")     # unequal spreads: the weight choice changes the fit
        a0 = float(np.linalg.solve(x.T @ (x * wt[:, None]), x.T @ (wt * y))[0])
        if w_lin > 0:
            near(a0 + w_lin, w_lin)          # a0 near 0, relative to the bracket's w
        if a0 > 0:
            out.update(status="ok", atm_method="quadratic", w_atm=a0, iv_atm=math.sqrt(252.0 * a0 / tau))
    out["margin"] = margin[0]
    return out


# --- ADR 0003 §b ---------------------------------------------------------------------------

def _interp(xs: list, target: int, max_ex: int, s5: str = "earlier"):
    """xs: [(tau, w, expiration)]. Linear in tau between the expiries that bracket the target, else
    through the two nearest, if the nearer is at most max_ex sessions away. (w, lo, hi, extrap) or None."""
    by_tau = {}
    for x in sorted(xs, key=lambda x: (x[0], x[2])):
        if x[0] not in by_tau or s5 == "later":         # S5
            by_tau[x[0]] = x
    ys = [by_tau[t] for t in sorted(by_tau)]
    if len(ys) < 2:
        return None
    lo = [x for x in ys if x[0] <= target]
    hi = [x for x in ys if x[0] > target]
    if lo and hi:
        a, b, ex = lo[-1], hi[0], False
    else:
        a, b, ex = (hi[0], hi[1], True) if hi else (lo[-2], lo[-1], True)
        nearest = a if hi else b
        if abs(nearest[0] - target) > max_ex:
            return None
    return a[1] + (target - a[0]) / (b[0] - a[0]) * (b[1] - a[1]), a, b, ex


def ref_cm30(usable: list, sessions_to_event, p: RefParams, choices=None) -> dict:
    """usable: [(tau, w, expiration, spans)] of ok expiries with tau >= tau_min. ADR 0003 §b and §c:
    cm30_iv, cm30_method, cm30_exp_lo, cm30_exp_hi, cm30_blind_iv, event_var, sigma_d_iv; and s7 (a w*
    <= 0 was met)."""
    ch = {**DEFAULT, **(choices or {})}
    h = p.horizon
    out = {"cm30_iv": None, "cm30_method": "none", "cm30_exp_lo": None, "cm30_exp_hi": None,
           "cm30_blind_iv": None, "event_var": None, "sigma_d_iv": None, "s7": False, "matters": set()}
    usable = sorted(usable, key=lambda x: (x[0], x[2]))
    if len({x[0] for x in usable}) < len(usable):
        out["matters"].add("S5")         # two usable expiries share a tau
    contains = sessions_to_event is not None and sessions_to_event <= h
    kind = "spanning" if contains else "clean"
    cls = [(t, w, e) for t, w, e, s in usable if s == contains]
    wstar, method, lo, hi = None, "none", None, None
    if len(cls) >= 2:
        r = _interp(cls, h, p.max_extrap, ch["S5"])
        if r is not None:
            wstar, a, b, ex = r
            method, lo, hi = ("extrap_" if ex else "interp_") + kind, a[2], b[2]
    elif len(cls) == 1:
        t1, w1, e1 = cls[0]
        if contains:
            clean = [(t, w, e) for t, w, e, s in usable if not s]
            if clean:
                tc, wc, ec = max(clean, key=lambda x: (x[0], x[2]))
                s2 = wc / tc
                wstar, method, lo, hi = s2 * h + (w1 - s2 * t1), "two_component", ec, e1
        elif abs(h - t1) <= p.max_extrap:
            wstar, method, lo, hi = w1 * h / t1, "flat_sigma", e1, e1
    if wstar is not None and wstar <= 0:
        out["s7"] = True                                                  # S7
    if wstar is not None and wstar > 0:
        out.update(cm30_iv=math.sqrt(252.0 * wstar / h), cm30_method=method, cm30_exp_lo=lo, cm30_exp_hi=hi)
    allx = [(t, w, e) for t, w, e, s in usable]
    r = _interp(allx, h, p.max_extrap, ch["S5"])
    wb = None if r is None else r[0]
    if r is None and len(allx) == 1 and abs(h - allx[0][0]) <= p.max_extrap:
        out["matters"].add("S6")
        if ch["S6"] == "flat":                                                                       # S6
            wb = allx[0][1] * h / allx[0][0]
    if wb is not None and wb <= 0:
        out["s7"] = True
    if wb is not None and wb > 0:
        out["cm30_blind_iv"] = math.sqrt(252.0 * wb / h)
    # §c: E and sigma_d from the first two spanning expiries, else sigma_d from the first two clean ones.
    span = [(t, w) for t, w, e, s in usable if s]
    clean = [(t, w) for t, w, e, s in usable if not s]
    s2 = None
    if len(span) >= 2 and span[1][0] != span[0][0]:
        (t1, w1), (t2, w2) = span[0], span[1]
        out["event_var"] = (w1 * t2 - w2 * t1) / (t2 - t1)
        s2 = (w2 - w1) / (t2 - t1)
    elif len(span) < 2 and len(clean) >= 2 and clean[1][0] != clean[0][0]:
        s2 = (clean[1][1] - clean[0][1]) / (clean[1][0] - clean[0][0])
    if s2 is not None and s2 >= 0:
        out["sigma_d_iv"] = math.sqrt(252.0 * s2)
    return out
