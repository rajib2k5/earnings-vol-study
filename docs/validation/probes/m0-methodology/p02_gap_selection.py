"""Probe C2b/C2c: does ADR 0002 §3's overnight-gap timing check select or mis-measure events by move size?

Monte Carlo of the rule exactly as tabled in ADR 0002 §3 (thresholds 4 / 3x / 6; date_suspect checked first,
because it applies to "any label"). Synthetic world:
  - market-adjusted overnight gaps on ordinary days ~ scaled Student-t(nu) (heavy tails), unit scale;
  - the announcement adds a jump J ~ N(0, k_i^2) on the TRUE reaction day; k_i ~ lognormal (quiet to big movers);
  - calendar label wrong with probability P_ERR (BMO <-> AMC), NULL with probability P_NULL;
  - reference scale = median |g| over 39 ordinary days ([-60,-22]).
Outputs, by tercile of |J| (the true announcement move):
  - share excluded from the primary sample (ambiguous + date_suspect)                  -> C2b
  - share of mislabelled events that get corrected                                    -> C2c
  - share of primary-sample events whose day 0 is wrong, and the resulting bias in the measured crush
    (true crush -0.12 log pts on the true day 0; a wrong day 0 measures an ordinary day, ~0)
Control (--control): replace the rule by "exclude 5% at random, never correct" -> exclusion must be flat
across terciles; this shows the tercile comparison can report 'no dependence'.
Run: uv run --no-sync --frozen python docs/validation/probes/m0-methodology/p02_gap_selection.py [--control] [--nu=3|5|1e9 (normal)]
"""
import sys

import numpy as np

CONTROL = "--control" in sys.argv
rng = np.random.default_rng(20261028)
N = 400_000
NU = float(next((a.split("=")[1] for a in sys.argv if a.startswith("--nu=")), 3.0))
P_ERR, P_NULL = 0.03, 0.011
t_scale = 1 / np.sqrt(NU / (NU - 2)) if NU < 1e6 else 1.0  # unit-variance t


def tdraw(*shape):
    if NU >= 1e6:
        return rng.standard_normal(shape)
    return rng.standard_t(NU, size=shape) * t_scale


true_amc = rng.random(N) < 0.5
k = np.exp(rng.normal(np.log(2.5), 0.8, N))  # jump sd in units of ordinary gap sd
J = rng.normal(0, 1, N) * k
ref = np.abs(tdraw(N, 39))
scale = np.median(ref, axis=1)
# 8 sessions D-3 .. D+4 ; index 3 = D (BMO candidate), 4 = next(D) (AMC candidate)
g = tdraw(N, 8)
g[np.arange(N), np.where(true_amc, 4, 3)] += J
z = np.abs(g) / scale[:, None]
zB, zA = z[:, 3], z[:, 4]
others = np.delete(z, [3, 4], axis=1).max(axis=1)

lab = np.where(rng.random(N) < P_ERR, ~true_amc, true_amc).astype(int)  # 1 = AMC
is_null = rng.random(N) < P_NULL
lab = np.where(is_null, -1, lab)

status = np.empty(N, dtype=object)
used_amc = np.full(N, -1)
if CONTROL:
    excl = rng.random(N) < 0.05
    status[:] = "not_contradicted"
    status[excl] = "excluded_random"
    used_amc = np.where(is_null, true_amc.astype(int), lab)
else:
    mx = np.maximum(zB, zA)
    date_suspect = (others >= 6) & (others >= 3 * mx)
    zL = np.where(lab == 1, zA, zB)
    zO = np.where(lab == 1, zB, zA)
    corrected = (lab >= 0) & (zO >= 4) & (zO >= 3 * zL)
    confirmed = (lab >= 0) & (zL >= 4) & (zL >= 3 * zO)
    inferred = (lab < 0) & (mx >= 4) & (mx >= 3 * np.minimum(zB, zA))
    status[:] = "not_contradicted"
    status[confirmed] = "confirmed"
    status[corrected] = "corrected"
    status[(lab < 0) & inferred] = "inferred"
    status[(lab < 0) & ~inferred] = "ambiguous"
    status[date_suspect] = "date_suspect"
    used_amc = np.where(corrected, 1 - lab, lab)
    used_amc = np.where(inferred, (zA > zB).astype(int), used_amc)

excluded = np.isin(status, ["ambiguous", "date_suspect", "excluded_random"])
wrong_day0 = (~excluded) & (used_amc != true_amc.astype(int))
true_crush, noise_sd = -0.12, 0.04
measured = np.where(wrong_day0, 0.0, true_crush) + rng.normal(0, noise_sd, N)

terc = np.digitize(np.abs(J), np.quantile(np.abs(J), [1 / 3, 2 / 3]))
mislab = (lab >= 0) & (lab != true_amc.astype(int))
print(f"{'control' if CONTROL else 'ADR 0002 rule'}: N={N}, P_ERR={P_ERR}, P_NULL={P_NULL}, t(nu={NU}) gaps")
print("status counts:", {s: int((status == s).sum()) for s in np.unique(status)})
print(f"{'tercile |J|':>12} {'excluded':>9} {'date_susp':>9} {'mislab corrected':>16} {'wrong day0 in primary':>22} {'mean measured crush':>20}")
for t_ in range(3):
    m = terc == t_
    mm = m & mislab
    p = m & ~excluded
    print(f"{['low','mid','high'][t_]:>12} {excluded[m].mean():9.4f} {(status[m]=='date_suspect').mean():9.4f} "
          f"{(status[mm]=='corrected').mean() if mm.any() else float('nan'):16.3f} {wrong_day0[p].mean():22.4f} "
          f"{measured[p].mean():20.4f}")
lo, hi = terc == 0, terc == 2
d = excluded[lo].mean() - excluded[hi].mean()
se = np.sqrt(excluded[lo].mean() * (1 - excluded[lo].mean()) / lo.sum() + excluded[hi].mean() * (1 - excluded[hi].mean()) / hi.sum())
print(f"exclusion low-minus-high tercile = {d:.4f} (z = {d/se:.1f})")
# spurious driver slope: regress measured crush on |r0| proxy (|g| on the day used as day 0) in the primary sample
p = ~excluded
r0 = np.abs(np.where(used_amc == 1, g[:, 4], g[:, 3]))[p]
b = np.polyfit(r0, measured[p], 1)[0]
print(f"slope of measured crush on |r0| (true slope 0): {b:.5f} per unit |gap|")
okl = (lab >= 0) & ~mislab
print("false corrections of CORRECT labels by tercile:", [round(float((status[(terc==t_) & okl]=="corrected").mean()),4) for t_ in range(3)])
sys.exit(0 if (CONTROL and abs(d / se) < 3) or (not CONTROL) else 1)
