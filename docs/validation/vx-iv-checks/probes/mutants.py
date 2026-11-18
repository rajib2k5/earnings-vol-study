# =============================================================================
# mutants.py - Planted code faults for the falsifier probes. Each is a context
# manager that swaps ONE function of the package for a wrong version while it
# is active, then puts the original back. The package files are not edited.
#
#   fwd_reversed        forward.forward_from_pairs takes the 4 strikes with the
#                       LARGEST |C - P| (a sign slip in the ranking): deep
#                       in-the-money pairs with wide spreads, so F is noisy.
#   fwd_reversed_one    the same slip with one strike instead of 4 (no median).
#   tau_plus_one        chain.tau_sessions counts the snapshot session too.
#   interp_wrong_pair   termstructure.interpolate takes the SHORTEST expiry at
#                       or below 21 sessions instead of the longest.
#   interp_two_shortest termstructure.interpolate always draws its line
#                       through the two shortest expiries, with no limit on
#                       how far it extrapolates.
#   spans_from_day0     tables.spans classes an expiry as spanning only from
#                       day 0 on, the rule before ADR 0003 amendment 3: an
#                       expiry on the day of an after-close (AMC)
#                       announcement becomes clean.
#   fwd_common          forward.forward_from_pairs multiplies F by exp(c_t),
#                       one c_t ~ N(0, sd^2) per session, the SAME for every
#                       expiry of the session: an error sigma_f cannot see,
#                       because the cross-expiry difference cancels it
#                       (after the reviewer's expD, 2026-11-17).
# Parameter drift (the code reading other values than params.yaml) is planted
# by passing other AtomParams/TermParams; see run_probes.py.
# =============================================================================

from contextlib import contextmanager

import numpy as np

import math

from earnings_vol.measures import chain, forward, tables, termstructure


@contextmanager
def _swap(module, name, new):
    old = getattr(module, name)
    setattr(module, name, new)
    try:
        yield
    finally:
        setattr(module, name, old)


def _fwd_reversed(strike, c_mid, p_mid, df, n_strikes=forward.N_STRIKES):
    if len(strike) == 0:
        return None
    gap = np.rint(200.0 * np.abs(c_mid - p_mid)).astype(np.int64)
    chosen = np.argsort(-gap, kind="mergesort")[:n_strikes]
    fk = strike[chosen] + (c_mid[chosen] - p_mid[chosen]) / df
    f = float(np.median(fk))
    return f, int(len(chosen)), float((fk.max() - fk.min()) / f)


def fwd_reversed():
    return _swap(forward, "forward_from_pairs", _fwd_reversed)


def fwd_reversed_one():
    return _swap(forward, "forward_from_pairs", lambda s, c, p_, df, n_strikes=1: _fwd_reversed(s, c, p_, df, 1))


def tau_plus_one():
    orig = chain.tau_sessions
    return _swap(chain, "tau_sessions", lambda s, e, sess: orig(s, e, sess) + 1)


def _interp_wrong_pair(xs, target, max_extrap):
    by_tau = {}
    for e in sorted(xs, key=lambda e: (e.tau, e.expiration)):
        by_tau.setdefault(e.tau, e)
    ex = list(by_tau.values())
    if len(ex) < 2:
        return None
    below = [e for e in ex if e.tau <= target]
    above = [e for e in ex if e.tau > target]
    if below and above:
        a, b, extrap = below[0], above[0], False          # the mutation: below[0], not below[-1]
    elif above:
        a, b, extrap = above[0], above[1], True
        if a.tau - target > max_extrap:
            return None
    else:
        a, b, extrap = below[-2], below[-1], True
        if target - b.tau > max_extrap:
            return None
    return a.w + (target - a.tau) / (b.tau - a.tau) * (b.w - a.w), a, b, extrap


def interp_wrong_pair():
    return _swap(termstructure, "interpolate", _interp_wrong_pair)


def _interp_two_shortest(xs, target, max_extrap):
    by_tau = {}
    for e in sorted(xs, key=lambda e: (e.tau, e.expiration)):
        by_tau.setdefault(e.tau, e)
    ex = list(by_tau.values())
    if len(ex) < 2:
        return None
    a, b = ex[0], ex[1]
    return a.w + (target - a.tau) / (b.tau - a.tau) * (b.w - a.w), a, b, not (a.tau <= target < b.tau)


def interp_two_shortest():
    return _swap(termstructure, "interpolate", _interp_two_shortest)


def spans_from_day0():
    return _swap(tables, "spans", lambda expiration, anchor, sessions: sessions.as_of(expiration) >= anchor[0])


@contextmanager
def fwd_common(sd: float, seed: int):
    """See the header. The session comes from tables.chain_rows, the caller of the atom on this path."""
    cur = {}
    orig_rows, orig_ffp = tables.chain_rows, forward.forward_from_pairs

    def rows(security_id, session, *a, **k):
        cur["c"] = float(np.random.default_rng([99, seed, session.toordinal()]).normal(0.0, sd))
        try:
            return orig_rows(security_id, session, *a, **k)
        finally:
            cur.pop("c", None)

    def ffp(*a, **k):
        r = orig_ffp(*a, **k)
        if r is None or "c" not in cur:
            return r
        f, n, disp = r
        return f * math.exp(cur["c"]), n, disp
    tables.chain_rows, forward.forward_from_pairs = rows, ffp
    try:
        yield
    finally:
        tables.chain_rows, forward.forward_from_pairs = orig_rows, orig_ffp
