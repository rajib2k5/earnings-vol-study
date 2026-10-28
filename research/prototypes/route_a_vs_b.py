"""Scratch extension of docs/validation/probes/m0-delta/d4_default_gap_selection.py (same world, same seed layout).

Question 1 (route choice): under "hand-check every event's press release" (route a), how much move dependence comes
back once the hand check is imperfect?
  f = share of events whose press release is NOT found (independent of the move; the event keeps the calendar label,
      status no_document; a NULL label with no document is ambiguous = excluded);
  m = misread rate of a found press release (the reader records the wrong side of the close; independent of the move);
  reread = a gap contradiction against a press-release label triggers one re-read, which is right.
Question 2 (tercile measure): is wrong day 0 flat across terciles of a day-0-INDEPENDENT move measure,
  max(|g_B|, |g_A|), when errors are uniform (control C0)?  The probe's |r0| on the used day 0 is not (N7).
"""
import sys

import numpy as np

NU = float(next((a.split("=")[1] for a in sys.argv if a.startswith("--nu=")), 3.0))
R, n = 2000, 365
P_ERR, P_NULL = 0.03, 0.011
TRUE_CRUSH, NOISE = -0.12, 0.04
rng = np.random.default_rng(20261028)
N = R * n
t_scale = 1 / np.sqrt(NU / (NU - 2)) if NU < 1e6 else 1.0


def tdraw(*shape):
    return rng.standard_normal(shape) if NU >= 1e6 else rng.standard_t(NU, size=shape) * t_scale


# --- identical world to d4 (same draw order) ---
true_amc = rng.random(N) < 0.5
k = np.exp(rng.normal(np.log(2.5), 0.8, N))
J = rng.normal(0, 1, N) * k
scale = np.median(np.abs(tdraw(N, 39)), axis=1)
g = tdraw(N, 8)
true_idx = np.where(true_amc, 4, 3)
g[np.arange(N), true_idx] += J
z = np.abs(g) / scale[:, None]
zB, zA = z[:, 3], z[:, 4]
mx, mn = np.maximum(zB, zA), np.minimum(zB, zA)
others = np.delete(z, [3, 4], axis=1).max(axis=1)
lab = np.where(rng.random(N) < P_ERR, ~true_amc, true_amc).astype(int)
is_null = rng.random(N) < P_NULL
lab = np.where(is_null, -1, lab)
nearby = (others >= 6) & (others >= 3 * mx)
truth = true_amc.astype(int)
# --- extra draws for route (a), made after the d4 world so the world is unchanged ---
u_found = rng.random(N)
u_misread = rng.random(N)
u_noise = rng.normal(0, NOISE, N)


def terc_within_rep(x):
    xs = x.reshape(R, n)
    ranks = xs.argsort(1).argsort(1)
    return (ranks * 3 // n).ravel()


def contra_of(label):
    zL = np.where(label == 1, zA, zB)
    zO = np.where(label == 1, zB, zA)
    return (label >= 0) & (zO >= 4) & (zO >= 3 * zL)


terc_true = terc_within_rep(np.abs(J))
mxg = np.maximum(np.abs(g[:, 3]), np.abs(g[:, 4]))          # day-0-independent move measure
terc_mxg = terc_within_rep(mxg)


def report(name, used, excluded, lookups, status_nodoc=None):
    kept = ~excluded
    wrong = kept & (used != truth)
    used_idx = np.where(used == 1, 4, 3)
    r0 = np.abs(g[np.arange(N), used_idx])
    terc_r0 = terc_within_rep(np.where(excluded, 0.0, r0))
    meas = np.where(wrong, 0.0, TRUE_CRUSH) + u_noise
    print(f"\n[{name}] look-ups per sample {lookups / R:.1f}; excluded per sample {excluded.sum() / R:.2f}")
    for lbl, T in (("true |J|", terc_true), ("max(|gB|,|gA|)", terc_mxg), ("used-day0 |r0|", terc_r0)):
        cells = []
        for t_ in range(3):
            m_ = (T == t_) & kept
            cells.append(f"{100 * wrong[m_].mean():5.2f}%")
        extra = ""
        if status_nodoc is not None and lbl == "max(|gB|,|gA|)":
            extra = "  no_document share " + " / ".join(f"{100 * status_nodoc[(T == t_)].mean():4.1f}%" for t_ in range(3))
        crush = " / ".join(f"{meas[(T == t_) & kept].mean():+.4f}" for t_ in range(3))
        print(f"  wrong day 0 by {lbl:>15} tercile (low/mid/high): {' / '.join(cells)}   mean crush {crush}{extra}")


print(f"R = {R} x n = {n}; P_ERR {P_ERR}; P_NULL {P_NULL}; gaps t(nu = {NU:g})")

# C0: calendar label everywhere; NULL excluded
report("C0 no check", np.where(lab < 0, 0, lab), is_null, 0)

# DEFAULT (R1) without the audit, to show the tercile-measure effect only (the audit changes little: d4)
checked = ((lab >= 0) & (contra_of(lab) | nearby)) | is_null
report("DEFAULT R1 (gap-triggered + every NULL; audit omitted)", np.where(checked, truth, lab), np.zeros(N, bool),
       checked.sum())

# ROUTE (a): every event's press release is looked up
for f in (0.0, 0.05):
    for m in (0.0, 0.01):
        for reread in (False, True):
            found = u_found >= f
            misread = found & (u_misread < m)
            pr_label = np.where(misread, 1 - truth, truth)
            used = np.where(found, pr_label, lab)                 # not found -> calendar label (no_document)
            excluded = (~found) & is_null                         # NULL and no document -> ambiguous
            lookups = N
            if reread:
                trig = found & (contra_of(used) | nearby)
                used = np.where(trig, truth, used)                # the re-read is right
                lookups += trig.sum()
            nodoc = (~found).astype(float)
            report(f"ROUTE (a): not found {f:.0%}, misread {m:.0%}, gap-triggered re-read {'on' if reread else 'off'}",
                   np.where(used < 0, 0, used), excluded, lookups, nodoc)
