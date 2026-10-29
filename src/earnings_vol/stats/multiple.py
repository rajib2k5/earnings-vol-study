# =============================================================================
# multiple.py — Multiple testing (ADR 0005 §4).
#
# HOLM (1979), step-down, for m hypotheses with p-values p_(1) <= ... <= p_(m):
#   adjusted p_(k) = max over j <= k of min(1, (m - j + 1) p_(j))
#   H_(k) is rejected at alpha exactly when its adjusted p <= alpha.
#   A hypothesis of the declared family that has no p-value yet (H5-H7 wait
#   for milestone 4) enters as p = 1. The adjusted p is non-decreasing in
#   every other p-value, so this is the largest the adjusted p of H1-H4 can
#   be: a rejection now stays a rejection whatever H5-H7 turn out to be.
#
# BENJAMINI-HOCHBERG (1995) q-values within one exploratory family:
#   q_(k) = min over j >= k of min(1, m p_(j) / j)
#   For p-values in [0, 1] the cap never binds: at the top rank m p_(m)/m = p_(m) <= 1, and the
#   running minimum only falls from there. Both functions refuse anything else (NaN, < 0, > 1).
# =============================================================================

import numpy as np


def _probabilities(pv: np.ndarray) -> np.ndarray:
    """pv itself, after checking every entry is a number from 0 to 1 (NaN is refused). The
    caps at 1 in holm() and bh() rest on it."""
    if np.isnan(pv).any() or (pv < 0).any() or (pv > 1).any():
        raise ValueError(f"p-values must be numbers from 0 to 1, got {pv.tolist()}")
    return pv


def holm(p: dict) -> dict:
    """{name: Holm-adjusted p} for {name: p or None}; None (not tested yet) counts as 1."""
    names = list(p)
    pv = _probabilities(np.array([1.0 if p[k] is None else float(p[k]) for k in names]))
    m = pv.size
    order = np.argsort(pv, kind="mergesort")
    adj = np.empty(m)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pv[i]))
        adj[i] = running
    return {k: float(a) for k, a in zip(names, adj)}


def bh(p: list[float]) -> list[float]:
    """Benjamini-Hochberg q-values, in the order given."""
    pv = _probabilities(np.asarray(p, float))
    m = pv.size
    if m == 0:
        return []
    order = np.argsort(pv, kind="mergesort")
    q = np.empty(m)
    running = 1.0
    for rank in range(m - 1, -1, -1):
        i = order[rank]
        running = min(running, m * pv[i] / (rank + 1))
        q[i] = running
    return [float(x) for x in q]
