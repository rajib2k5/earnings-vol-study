"""Delta-2 probe e2 (claim 2): is abs_move_cand_max flat under uniform errors, for DATE errors as well as label flips?

ADR 0002 :453-455 and data model :638 define abs_move_cand_max = max(|r(prev(D)->D)|, |r(D->next(D))|) around "D",
and say it "does not depend on the label". route_a_vs_b.py checks flatness only for BMO/AMC label flips, whose
measure max(|g_B|, |g_A|) is label-free by construction, so that check cannot fail for any label-free measure.

Here the same world (route_a_vs_b.py draw order, nu = 3) gets one more error type, drawn uniformly and independently
of the move: with probability Q_DATE the calendar's D is wrong by more than the candidate window, so the jump is in
neither candidate session of the calendar D. The tercile measure is then computed
  (M1) around the calendar D (what "D" means in data model :477, events.announce_date), and
  (M2) around the true / document date (falsifier control: must be flat).
Pass condition for claim 2: the wrong-date share is flat across M1 terciles. Falsifier: M2 flat; label flips flat.

Run from the repository root: .venv/bin/python docs/validation/probes/m0-delta2/e2_cand_max.py
"""
import numpy as np

NU, R, n, P_ERR, Q_DATE = 3.0, 2000, 365, 0.03, 0.01
rng = np.random.default_rng(20261028)
N = R * n
t_scale = 1 / np.sqrt(NU / (NU - 2))


def tdraw(*shape):
    return rng.standard_t(NU, size=shape) * t_scale


true_amc = rng.random(N) < 0.5
k = np.exp(rng.normal(np.log(2.5), 0.8, N))
J = rng.normal(0, 1, N) * k
_ = np.median(np.abs(tdraw(N, 39)), axis=1)
g = tdraw(N, 8)
lab_flip = rng.random(N) < P_ERR
date_err = np.random.default_rng(99).random(N) < Q_DATE   # independent of everything above
# true event at session 3/4 relative to the TRUE date. For a calendar-date error the calendar's candidate sessions
# (3, 4) hold only ordinary noise; the jump sits at the true date's candidates, modelled as two extra sessions.
g_true = g.copy()
g_true[np.arange(N), np.where(true_amc, 4, 3)] += J
g_cal = np.where(date_err[:, None], g, g_true)

m1 = np.maximum(np.abs(g_cal[:, 3]), np.abs(g_cal[:, 4]))      # around the calendar D
m2 = np.maximum(np.abs(g_true[:, 3]), np.abs(g_true[:, 4]))    # around the true date


def terc(x):
    xs = x.reshape(R, n)
    return ((xs.argsort(1).argsort(1)) * 3 // n).ravel()


def share(flag, T):
    return " / ".join(f"{100 * flag[T == t].mean():5.2f}%" for t in range(3))


T1, T2 = terc(m1), terc(m2)
print(f"R = {R} x n = {n}, t({NU:g}) gaps, label flips {P_ERR:.0%}, calendar date errors {Q_DATE:.0%} (uniform)")
print("label-flip share   by M1 (calendar D) terciles:", share(lab_flip, T1))
print("date-error share   by M1 (calendar D) terciles:", share(date_err, T1))
print("date-error share   by M2 (true date)  terciles:", share(date_err, T2))
lo, hi = date_err[T1 == 0].mean(), date_err[T1 == 2].mean()
flat_m1 = abs(lo - hi) < 0.002
flat_m2 = abs(date_err[T2 == 0].mean() - date_err[T2 == 2].mean()) < 0.002
print("RESULT: M1 flat for date errors:", flat_m1, "| falsifier M2 flat:", flat_m2)
raise SystemExit(0 if flat_m1 else 1)
