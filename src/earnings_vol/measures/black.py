# =============================================================================
# black.py — Black-76 on the parity forward, and its inversion for the total
# implied variance w (ADR 0003 §0 step 3, §c straddle cross-check).
#
# BLACK-76
#   With the forward F, the strike K, the discount factor DF and the TOTAL
#   variance w = sigma^2 * T (so sqrt(w) = sigma * sqrt(T)):
#       d1 = (ln(F/K) + w/2) / sqrt(w),   d2 = d1 - sqrt(w)
#       call = DF * (F N(d1) - K N(d2))
#       put  = DF * (K N(-d2) - F N(-d1))
#   sigma and T enter only through w. So a price pins down w, and no day count
#   enters the variance here: the clock (sessions) is applied later, when w is
#   turned into an annualised IV, sqrt(252 w / tau).
#
# THE INVERSION
#   Each price is increasing in w, so mid = Black76(w) has a root on
#   [W_MIN, W_MAX] exactly when Black76(W_MIN) < mid < Black76(W_MAX). Brent's
#   method finds it. Outside that range the strike is invalid (`iv_no_root`):
#   never solved on a wider interval, never clipped to W_MAX.
#
# THE ATM-FORWARD STRADDLE (K = F)
#   d1 = sqrt(w)/2 and d2 = -sqrt(w)/2, so call = put = DF F (2 N(sqrt(w)/2) - 1)
#   and the straddle is Pi = call + put = 2 DF F (2 N(sqrt(w)/2) - 1). Inverting:
#       sqrt(w) = 2 N^-1( (Pi / (2 DF F) + 1) / 2 ).
#   Worked: w = 0.0036, DF = 1, F = 100: sqrt(w)/2 = 0.03, N(0.03) = 0.5119665,
#   Pi = 200 * (2 * 0.5119665 - 1) = 4.78660; back: (4.78660/200 + 1)/2 =
#   0.5119665, N^-1 = 0.03, sqrt(w) = 0.06, w = 0.0036.
# =============================================================================

from statistics import NormalDist

import numpy as np
from scipy.optimize import brentq
from scipy.special import ndtr

W_MIN = 1e-8
W_MAX = 4.0


def black76(f, k, w, df, call):
    """The Black-76 price of a European call (call=True) or put on the forward f.

    Works on floats or on numpy arrays (k, w and call may be arrays of one shape).
    """
    s = np.sqrt(w)
    d1 = (np.log(f / k) + 0.5 * w) / s
    d2 = d1 - s
    c = df * (f * ndtr(d1) - k * ndtr(d2))
    p = df * (k * ndtr(-d2) - f * ndtr(-d1))
    return np.where(call, c, p)


def has_root(mid, f, k, df, call, w_min: float = W_MIN, w_max: float = W_MAX):
    """True where the price lies strictly between the prices at w_min and w_max (arrays allowed)."""
    return (black76(f, k, w_min, df, call) < mid) & (mid < black76(f, k, w_max, df, call))


def implied_w(mid: float, f: float, k: float, df: float, call: bool, w_min: float = W_MIN,
              w_max: float = W_MAX) -> float | None:
    """The total variance w with Black76(w) = mid, or None when no root lies in [w_min, w_max]."""
    if not has_root(mid, f, k, df, call, w_min, w_max):
        return None
    return float(brentq(lambda w: float(black76(f, k, w, df, call)) - mid, w_min, w_max, xtol=1e-15,
                        rtol=1e-14, maxiter=200))


def straddle_w(pi: float, f: float, df: float) -> float | None:
    """The total variance implied by the ATM-forward straddle price pi (K = F), or None.

    Needs 0 < pi / (DF F) < 2: a straddle at K = F is worth between 0 and 2 DF F.
    """
    x = pi / (2.0 * df * f)
    if not 0.0 < x < 1.0:
        return None
    return (2.0 * NormalDist().inv_cdf((x + 1.0) / 2.0)) ** 2
