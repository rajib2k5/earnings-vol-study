# =============================================================================
# chain.py — The atom of every IV measure: the ATM total implied variance of
# one (security, session, expiry), ADR 0003 §0 steps 1 to 6. One call of
# expiry_atom() gives one row of `chain_expiry` (data model §3.5).
#
# THE STEPS
#   1. Quote filter: 0 < bid < ask, mid >= 0.05, (ask - bid)/mid <= 0.5.
#   2. Forward from put-call parity (forward.py): the median F_K of the 4
#      strikes with the smallest |C - P| among strikes whose call AND put pass.
#   1b. With F known, the OUT-OF-THE-MONEY side of each strike (puts for
#      K < F, calls for K >= F) must also have |ln(K/F)| <= 0.5 and lie inside
#      the no-arbitrage bounds
#          call: max(DF (F - K), 0) <= C <= DF F
#          put:  max(DF (K - F), 0) <= P <= DF K.
#   3. Solve mid = Black76(F, K, w, DF) for w (black.py). No root in
#      [1e-8, 4]: the strike is invalid (flag iv_no_root).
#   4. ATM: with k = ln(K/F), take the nearest valid strikes with
#      k_lo <= 0 < k_hi and interpolate w linearly in k to k = 0:
#          w_atm = w_lo + (0 - k_lo) / (k_hi - k_lo) * (w_hi - w_lo).
#      The bracket must be at most 1.5 sqrt(w_atm) wide (1.5 standard
#      deviations). Otherwise fit w(k) = a + b k + c k^2 by least squares,
#      weighted by 1/(relative spread) of the OTM quote, through the valid
#      strikes with |k| <= 2 sqrt(w_ref), w_ref = the too-wide bracket's linear
#      w_atm. The fit needs at least 4 strikes, at least one on each side of
#      k = 0, and a > 0; then w_atm = a (atm_method quadratic). Else no ATM:
#      with no valid strike on one side of the money (flag no_bracket), or a
#      window on one side only, the ATM w would be extrapolated, and it is not
#      (milestone-2 review, claim 3b: a one-sided fit missed the known ATM IV by
#      more than 1.5 vol points in 1 case in 20, ADR 0003 §0 step 4).
#   5. tau = NYSE sessions in (session, expiry]: the expiry session counts, the
#      snapshot session does not (tau_sessions below).
#   6. The reported IV is session-annualised: iv_atm = sqrt(252 w_atm / tau).
#
# WORKED (the AAPL example of ADR 0003, 2025-10-30, expiry 2025-11-14): the
# forward is 271.42, the bracket 267.5 (put, k = -0.01458) and 272.5 (call,
# k = +0.00397); w_atm = 0.003486, tau = 11, iv_atm = sqrt(252 * 0.003486 / 11)
# = 0.2826. tests/test_iv_worked_example.py reproduces every digit.
#
# ALSO STORED, for validation only
#   vendor_iv_atm  the vendor's `vol` of the OTM quotes at the two bracket
#                  strikes, interpolated in k the same way (bracket_linear only)
#   straddle_atm   C + P mid at the two bracket strikes, interpolated in k to 0,
#   iv_straddle    and the IV it implies at K = F (black.straddle_w). A gap
#                  above 0.5 vol points to iv_atm is flagged straddle_gap.
# =============================================================================

import math
from dataclasses import dataclass, fields
from typing import Mapping

import numpy as np

from earnings_vol.measures import black, forward

# The value columns expiry_atom() fills, in the registry's order (schema.CHAIN_EXPIRY).
ATOM_FIELDS = ("forward", "forward_n_strikes", "forward_dispersion", "n_strikes_valid", "strike_lo", "strike_hi",
               "k_lo", "k_hi", "rel_spread_lo", "rel_spread_hi", "w_atm", "iv_atm", "atm_method", "vendor_iv_atm",
               "straddle_atm", "iv_straddle", "status", "flags")


@dataclass(frozen=True)
class AtomParams:
    """The ADR 0003 §0 choices, from params.yaml `iv`."""

    min_mid: float = 0.05
    max_rel_spread: float = 0.5
    max_abs_log_moneyness: float = 0.5
    forward_strikes: int = 4
    forward_dispersion_flag: float = 0.005
    w_min: float = black.W_MIN
    w_max: float = black.W_MAX
    bracket_max_sd: float = 1.5
    quadratic_max_sd: float = 2.0
    quadratic_min_strikes: int = 4
    straddle_flag: float = 0.005

    @classmethod
    def from_params(cls, iv: Mapping) -> "AtomParams":
        return cls(**{f.name: f.type(iv[f.name]) for f in fields(cls)})


@dataclass(frozen=True)
class ExpiryQuotes:
    """One expiry of one snapshot, one entry per strike (ascending, unique). NaN = side not quoted."""

    strike: np.ndarray
    call_bid: np.ndarray
    call_ask: np.ndarray
    put_bid: np.ndarray
    put_ask: np.ndarray
    call_vol: np.ndarray
    put_vol: np.ndarray


def tau_sessions(session_date, expiration, sessions) -> int:
    """NYSE sessions in (session_date, expiration] (ADR 0003 §0 step 5).

    An expiration on a non-session day (an exchange holiday) settles on the
    session before it, so it counts up to as_of(expiration).
    """
    return sessions.between(session_date, sessions.as_of(expiration))


def annualised_iv(w: float, tau: int) -> float:
    """ADR 0003 §0 step 6: sqrt(252 w / tau), the session-annualised IV."""
    return math.sqrt(252.0 * w / tau)


def _empty(status: str, flags=()) -> dict:
    out = {f: None for f in ATOM_FIELDS}
    out.update(forward_n_strikes=0, n_strikes_valid=0, atm_method="none", status=status, flags="|".join(sorted(flags)))
    return out


def stale_atom() -> dict:
    """The value columns of an expiry whose snapshot is a stale repeat: kept for audit, never measured."""
    return _empty("stale")


def _wls_quadratic_intercept(k: np.ndarray, w: np.ndarray, weight: np.ndarray) -> float:
    """a of w(k) = a + b k + c k^2, minimising sum weight * residual^2."""
    x = np.column_stack([np.ones_like(k), k, k * k])
    root = np.sqrt(weight)
    beta = np.linalg.lstsq(x * root[:, None], w * root, rcond=None)[0]
    return float(beta[0])


def expiry_atom(q: ExpiryQuotes, df: float, tau: int, p: AtomParams = AtomParams()) -> dict:
    """The chain_expiry value columns of one expiry (ATOM_FIELDS), with its status and flags."""
    k_strike = np.asarray(q.strike, float)
    c_ok = forward.quote_ok(q.call_bid, q.call_ask, p.min_mid, p.max_rel_spread)
    p_ok = forward.quote_ok(q.put_bid, q.put_ask, p.min_mid, p.max_rel_spread)
    c_mid = (q.call_bid + q.call_ask) / 2.0
    p_mid = (q.put_bid + q.put_ask) / 2.0

    # Step 2: the parity forward.
    both = c_ok & p_ok
    fw = forward.forward_from_pairs(k_strike[both], c_mid[both], p_mid[both], df, p.forward_strikes)
    if fw is None:
        return _empty("no_forward")
    f, n_fw, disp = fw
    flags = set()
    if disp > p.forward_dispersion_flag:
        flags.add("fwd_dispersion")
    if n_fw < p.forward_strikes:
        flags.add("few_strikes")

    # Step 1, second part: the OTM side, moneyness, no-arbitrage bounds.
    is_call = k_strike >= f
    mid = np.where(is_call, c_mid, p_mid)
    bid = np.where(is_call, q.call_bid, q.put_bid)
    ask = np.where(is_call, q.call_ask, q.put_ask)
    vol = np.where(is_call, q.call_vol, q.put_vol)
    k = np.log(k_strike / f)
    lower = np.where(is_call, np.maximum(df * (f - k_strike), 0.0), np.maximum(df * (k_strike - f), 0.0))
    upper = np.where(is_call, df * f, df * k_strike)
    passes = np.where(is_call, c_ok, p_ok) & (np.abs(k) <= p.max_abs_log_moneyness) & (lower <= mid) & (mid <= upper)

    # Step 3: a root must exist in [w_min, w_max].
    with np.errstate(invalid="ignore"):
        root = black.has_root(mid, f, k_strike, df, is_call, p.w_min, p.w_max)
    valid = passes & root
    if (passes & ~root).any():
        flags.add("iv_no_root")
    idx = np.flatnonzero(valid)
    out = _empty("no_atm", flags)
    out.update(forward=f, forward_n_strikes=n_fw, forward_dispersion=disp, n_strikes_valid=int(idx.size))
    if idx.size == 0:
        return out

    w_cache: dict[int, float] = {}

    def w_at(i: int) -> float:
        if i not in w_cache:
            w_cache[i] = black.implied_w(float(mid[i]), f, float(k_strike[i]), df, bool(is_call[i]), p.w_min,
                                         p.w_max)
        return w_cache[i]

    with np.errstate(divide="ignore", invalid="ignore"):
        rel = (ask - bid) / mid            # NaN where the OTM side is not quoted (never used there)
    below, above = idx[k[idx] <= 0], idx[k[idx] > 0]
    if not (below.size and above.size):
        flags.add("no_bracket")            # nothing on one side of the money: no ATM, never extrapolated
        out["flags"] = "|".join(sorted(flags))
        return out
    lo, hi = int(below[-1]), int(above[0])
    frac = float((0.0 - k[lo]) / (k[hi] - k[lo]))
    w0 = float(w_at(lo) + frac * (w_at(hi) - w_at(lo)))     # > 0: a mix of two w in [w_min, w_max]
    out.update(strike_lo=float(k_strike[lo]), strike_hi=float(k_strike[hi]), k_lo=float(k[lo]),
               k_hi=float(k[hi]), rel_spread_lo=float(rel[lo]), rel_spread_hi=float(rel[hi]))
    if k[hi] - k[lo] <= p.bracket_max_sd * math.sqrt(w0):
        out.update(w_atm=w0, iv_atm=annualised_iv(w0, tau), atm_method="bracket_linear", status="ok")
        v = vol[lo] + frac * (vol[hi] - vol[lo])
        out["vendor_iv_atm"] = None if math.isnan(v) else float(v)
        if c_ok[lo] and p_ok[lo] and c_ok[hi] and p_ok[hi]:
            s_lo, s_hi = c_mid[lo] + p_mid[lo], c_mid[hi] + p_mid[hi]
            pi = float(s_lo + frac * (s_hi - s_lo))
            ws = black.straddle_w(pi, f, df)
            out["straddle_atm"] = pi
            if ws is not None:
                out["iv_straddle"] = annualised_iv(ws, tau)
                if abs(out["iv_straddle"] - out["iv_atm"]) > p.straddle_flag:
                    flags.add("straddle_gap")
        out["flags"] = "|".join(sorted(flags))
        return out
    flags.add("wide_bracket")
    sel = idx[np.abs(k[idx]) <= p.quadratic_max_sd * math.sqrt(w0)]     # the window, drawn with w_ref = w0
    two_sided = bool((k[sel] <= 0).any() and (k[sel] > 0).any())
    if sel.size >= p.quadratic_min_strikes and two_sided:
        a = _wls_quadratic_intercept(k[sel], np.array([w_at(int(i)) for i in sel]), 1.0 / rel[sel])
        if a > 0:
            out.update(w_atm=a, iv_atm=annualised_iv(a, tau), atm_method="quadratic", status="ok")
    out["flags"] = "|".join(sorted(flags))
    return out
