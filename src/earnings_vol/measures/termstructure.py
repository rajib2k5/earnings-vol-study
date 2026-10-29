# =============================================================================
# termstructure.py — From one session's expiries (rows of chain_expiry) to the
# daily measures of `iv_daily` (data model §3.6, ADR 0003 §a-§c).
#
# THE INPUT
#   The `ok` expiries of one (security, session) with tau >= 5 sessions (the
#   usable ones, ADR 0003 §0 step 5), each with its ATM total variance w and
#   whether it SPANS the security's next event: expiration >= that event's
#   day 0, because an expiry that settles at day 0's close already holds the
#   news, and for an AMC release also an expiry on the announcement day
#   itself (tables.spans). All others are CLEAN.
#
# THE MEASURES
#   front     the shortest usable expiry: front_atm_iv. It rolls, so it is for
#             display and vendor comparison only.
#   cm30      the 21-session IV, event-aware (ADR 0003 §b). If the horizon holds
#             the next event's day 0 (sessions to it <= 21), only spanning
#             expiries are used, otherwise only clean ones:
#               2+ expiries  linear in tau between the two that bracket 21
#                            (interp_*); without a bracket, extrapolate from the
#                            two nearest, at most 10 sessions beyond the nearer
#                            (extrap_*);
#               1 spanning   two_component: sigma_d^2 = w_C / tau_C from the
#                            longest clean expiry C, E = w_S - sigma_d^2 tau_S,
#                            w* = sigma_d^2 * 21 + E;
#               1 clean      flat_sigma: w* = w_C * 21 / tau_C, if |21 - tau_C| <= 10.
#             cm30_iv = sqrt(252 w* / 21). cm30_blind_iv interpolates ALL usable
#             expiries the same way: the gap between the two measures the leak.
#   E         event variance from the two shortest usable spanning expiries (a
#             spanning expiry without an ATM w is not in `usable`, so the next
#             one takes its place; ADR 0003 §c):
#               w_j = sigma_d^2 tau_j + E  =>  sigma_d^2 = (w2 - w1) / (tau2 - tau1),
#                                              E = (w1 tau2 - w2 tau1) / (tau2 - tau1).
#             E is stored SIGNED. implied_move = sqrt(E) only when E > 0.
#   sigma_d   sigma_d_iv = sqrt(252 sigma_d^2), an annualised volatility, from the
#             pair that gave E, else from the two shortest clean expiries.
#
# WORKED (the AAPL example, 2025-10-30, both expiries spanning the event):
#   w1 = 0.003486251 (tau 11), w2 = 0.005616313 (tau 20)
#   sigma_d^2 = (0.005616313 - 0.003486251) / 9 = 2.3667e-4 per session
#   E = (0.003486251 * 20 - 0.005616313 * 11) / 9 = 0.00088284
#   implied_move = sqrt(E) = 2.9713%;  sigma_d_iv = sqrt(252 * 2.3667e-4) = 0.2442.
# =============================================================================

import math
from dataclasses import dataclass, fields
from datetime import date
from typing import Mapping

SQRT_2_OVER_PI = math.sqrt(2.0 / math.pi)

# The measure columns day_measures() fills, in the registry's order (schema.IV_DAILY).
DAY_FIELDS = ("front_expiry", "front_tau", "front_atm_iv", "cm30_iv", "cm30_method", "cm30_exp_lo", "cm30_exp_hi",
              "cm30_blind_iv", "sigma_d_iv", "event_var", "ev_exp1", "ev_exp2", "ev_tau1", "ev_tau2", "ev_w1", "ev_w2",
              "implied_move", "implied_abs_move", "implied_abs_move_total", "implied_move_status", "ts_slope")


@dataclass(frozen=True)
class TermParams:
    """ADR 0003 §b choices, from params.yaml `iv`."""

    cm30_horizon_sessions: int = 21
    tau_min_sessions: int = 5
    cm30_max_extrap_sessions: int = 10

    @classmethod
    def from_params(cls, iv: Mapping) -> "TermParams":
        return cls(**{f.name: f.type(iv[f.name]) for f in fields(cls)})


@dataclass(frozen=True)
class Expiry:
    """One usable expiry of one session: its date, sessions to go, ATM w and IV, and its class."""

    expiration: date
    tau: int
    w: float
    iv: float
    spans: bool


def interpolate(xs: list[Expiry], target: int, max_extrap: int) -> tuple[float, Expiry, Expiry, bool] | None:
    """(w at tau = target, lower expiry, upper expiry, extrapolated?) from 2+ expiries, or None.

    Linear in tau between the expiries that bracket the target (the longest
    with tau <= target and the shortest with tau > target). Without a bracket,
    the line through the two expiries nearest the target, if the nearer one is
    at most `max_extrap` sessions away. One entry per tau (the first listed).
    """
    by_tau: dict[int, Expiry] = {}
    for e in sorted(xs, key=lambda e: (e.tau, e.expiration)):
        by_tau.setdefault(e.tau, e)
    ex = list(by_tau.values())
    if len(ex) < 2:
        return None
    below = [e for e in ex if e.tau <= target]
    above = [e for e in ex if e.tau > target]
    if below and above:
        a, b, extrap = below[-1], above[0], False
    elif above:
        a, b, extrap = above[0], above[1], True
        if a.tau - target > max_extrap:
            return None
    else:
        a, b, extrap = below[-2], below[-1], True
        if target - b.tau > max_extrap:
            return None
    w = a.w + (target - a.tau) / (b.tau - a.tau) * (b.w - a.w)
    return w, a, b, extrap


def _cm30(usable: list[Expiry], contains_event: bool, p: TermParams) -> tuple[float | None, str, Expiry | None,
                                                                               Expiry | None]:
    """(w*, method, lo, hi) of the event-aware 21-session variance (ADR 0003 §b)."""
    h = p.cm30_horizon_sessions
    cls = [e for e in usable if e.spans == contains_event]
    kind = "spanning" if contains_event else "clean"
    if len(cls) >= 2:
        r = interpolate(cls, h, p.cm30_max_extrap_sessions)
        if r is None:
            return None, "none", None, None
        w, a, b, extrap = r
        return w, ("extrap_" if extrap else "interp_") + kind, a, b
    if len(cls) == 1:
        e = cls[0]
        if contains_event:
            clean = [c for c in usable if not c.spans]
            if not clean:
                return None, "none", None, None
            c = max(clean, key=lambda x: (x.tau, x.expiration))
            s2 = c.w / c.tau
            event = e.w - s2 * e.tau
            return s2 * h + event, "two_component", c, e
        if abs(h - e.tau) <= p.cm30_max_extrap_sessions:
            return e.w * h / e.tau, "flat_sigma", e, e
    return None, "none", None, None


def _blind(usable: list[Expiry], p: TermParams) -> float | None:
    """cm30_blind: every usable expiry, whatever its class (as CBOE interpolates)."""
    h = p.cm30_horizon_sessions
    r = interpolate(usable, h, p.cm30_max_extrap_sessions)
    if r is not None:
        return r[0]
    if len(usable) == 1 and abs(h - usable[0].tau) <= p.cm30_max_extrap_sessions:
        return usable[0].w * h / usable[0].tau
    return None


def event_variance(w1: float, tau1: int, w2: float, tau2: int) -> tuple[float, float]:
    """(E, sigma_d^2 per session) from two spanning expiries tau1 < tau2 (ADR 0003 §c)."""
    s2 = (w2 - w1) / (tau2 - tau1)
    return (w1 * tau2 - w2 * tau1) / (tau2 - tau1), s2


def implied_moves(event_var: float | None, sigma_d2: float | None) -> dict:
    """implied_move = sqrt(E), implied_abs_move = sqrt(2/pi) sqrt(E) and
    implied_abs_move_total = sqrt(2/pi) sqrt(E + sigma_d^2), with sigma_d^2 per
    session; all null unless E > 0 (the last also needs sigma_d^2)."""
    if event_var is None:
        return {"implied_move": None, "implied_abs_move": None, "implied_abs_move_total": None,
                "implied_move_status": "not_identified"}
    if event_var <= 0:
        return {"implied_move": None, "implied_abs_move": None, "implied_abs_move_total": None,
                "implied_move_status": "nonpositive_event_variance"}
    total = None if sigma_d2 is None or sigma_d2 < 0 else SQRT_2_OVER_PI * math.sqrt(event_var + sigma_d2)
    return {"implied_move": math.sqrt(event_var), "implied_abs_move": SQRT_2_OVER_PI * math.sqrt(event_var),
            "implied_abs_move_total": total, "implied_move_status": "ok"}


def day_measures(usable: list[Expiry], sessions_to_event: int | None, p: TermParams = TermParams()) -> tuple[dict,
                                                                                                             set]:
    """The iv_daily measure columns (DAY_FIELDS) of one session, and its flags.

    `usable` holds the session's ok expiries with tau >= 5. `sessions_to_event`
    counts sessions from this session to the next event's day 0 (None if
    there is no next event).
    """
    out = {f: None for f in DAY_FIELDS}
    flags: set[str] = set()
    ex = sorted(usable, key=lambda e: (e.tau, e.expiration))
    if any(e.tau < p.tau_min_sessions for e in ex):
        raise ValueError("day_measures takes usable expiries only (tau >= tau_min_sessions)")
    out["cm30_method"] = "none"
    out.update(implied_moves(None, None))
    if not ex:
        return out, flags

    front = ex[0]
    out.update(front_expiry=front.expiration, front_tau=front.tau, front_atm_iv=front.iv)
    if len(ex) >= 2:
        out["ts_slope"] = math.log(ex[0].iv / ex[1].iv)

    contains = sessions_to_event is not None and sessions_to_event <= p.cm30_horizon_sessions
    w, method, lo, hi = _cm30(ex, contains, p)
    if w is not None and w > 0:
        out.update(cm30_iv=math.sqrt(252.0 * w / p.cm30_horizon_sessions), cm30_method=method,
                   cm30_exp_lo=lo.expiration, cm30_exp_hi=hi.expiration)
    wb = _blind(ex, p)
    if wb is not None and wb > 0:
        out["cm30_blind_iv"] = math.sqrt(252.0 * wb / p.cm30_horizon_sessions)

    spanning = [e for e in ex if e.spans]
    clean = [e for e in ex if not e.spans]
    sigma_d2 = None
    if len(spanning) >= 2:
        t1, t2 = spanning[0], spanning[1]
        event, sigma_d2 = event_variance(t1.w, t1.tau, t2.w, t2.tau)
        out.update(event_var=event, ev_exp1=t1.expiration, ev_exp2=t2.expiration, ev_tau1=t1.tau, ev_tau2=t2.tau,
                   ev_w1=t1.w, ev_w2=t2.w)
        out.update(implied_moves(event, sigma_d2))
    elif len(clean) >= 2:
        sigma_d2 = (clean[1].w - clean[0].w) / (clean[1].tau - clean[0].tau)
    if sigma_d2 is not None:
        if sigma_d2 >= 0:
            out["sigma_d_iv"] = math.sqrt(252.0 * sigma_d2)
        else:
            flags.add("negative_forward_variance")
    return out, flags
