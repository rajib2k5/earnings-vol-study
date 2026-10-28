"""Delta probe 4c: does ADR 0002's DEFAULT timing rule (no EDGAR) still select on move size, and by how much?

The world is that of docs/validation/probes/m0-methodology/p02_gap_selection.py (same gap model, same thresholds,
3% wrong labels, 1.1% NULL labels, true crush -0.12 log points on the true day 0, ~0 on a wrong day), but simulated at
the real scale: R replications of n = 365 events, because the default's audit (50 events, 17/17/16 across the |r0|
terciles) only makes sense per sample.

The default (ADR 0002 status note and §3 "The fallback"):
  - a labelled event is hand-checked (press release decides) iff the gap contradicts its label
    (z_other >= 4 and >= 3 z_label) or the nearby-session flag fires (z >= 6 and >= 3 max(z_B, z_A) in [D-3, D+4]);
  - a stratified audit hand-checks 17/17/16 of the UNtriggered labelled events across the |r0| terciles;
  - every other labelled event keeps the calendar label (`unverified`);
  - NULL labels: the ADR does not say when a NULL-label event gets a press-release check under the default. Two
    readings are simulated: R1 every NULL-label event is looked up; R2 only when a gap signal fires (the nearby flag,
    or one candidate with z >= 4 and >= 3x the other), else `ambiguous` = excluded.
  - assumption favourable to the ADR: every hand check finds a press release, and it is right.
Controls: C0 "no check at all" (calendar label everywhere); C1 "hand-check every event" (the ADR's rejected
alternative, the gold standard).
Terciles are reported two ways: by the TRUE announcement move |J|, and by the MEASURED move |r0| on the day 0 actually
used, which is what the sample funnel can compute.
Run: uv run --no-sync --frozen python docs/validation/probes/m0-delta/d4_default_gap_selection.py [--nu=3|5|1e9]
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
zL = np.where(lab == 1, zA, zB)
zO = np.where(lab == 1, zB, zA)
nearby = (others >= 6) & (others >= 3 * mx)
contra = (lab >= 0) & (zO >= 4) & (zO >= 3 * zL)
null_signal = nearby | ((mx >= 4) & (mx >= 3 * mn))
rep = np.repeat(np.arange(R), n)


def r0_of(used_amc):
    used_idx = np.where(used_amc == 1, 4, 3)
    return np.abs(g[np.arange(N), used_idx])


def terc_within_rep(x):
    """|r0| tercile computed inside each replication of n events (what one study can compute)."""
    xs = x.reshape(R, n)
    ranks = xs.argsort(1).argsort(1)
    return (ranks * 3 // n).ravel()


def run(rule, null_reading="R1"):
    checked = np.zeros(N, bool)
    if rule == "default":
        checked |= (lab >= 0) & (contra | nearby)
        checked |= is_null & (True if null_reading == "R1" else null_signal)
    elif rule == "all":
        checked[:] = True
    # provisional day 0 (before the audit): checked -> truth; unchecked labelled -> label; unchecked NULL -> none
    used = np.where(checked, true_amc.astype(int), lab)
    excluded = (~checked) & is_null
    audited = np.zeros(N, bool)
    if rule == "default":
        tr = terc_within_rep(np.where(excluded, 0.0, r0_of(np.where(used < 0, 0, used))))
        pool = (~checked) & (lab >= 0)
        key = rng.random(N)
        for t_, quota in ((0, 17), (1, 17), (2, 16)):
            cand = np.where(pool & (tr == t_), key, np.inf).reshape(R, n)
            pick = np.argsort(cand, axis=1)[:, :quota]
            ok = np.take_along_axis(cand, pick, 1) < np.inf
            idx = (pick + np.arange(R)[:, None] * n)[ok]
            audited[idx] = True
        audit_terc = tr
    else:
        audit_terc = None
    used = np.where(audited, true_amc.astype(int), used)
    wrong = (~excluded) & (used != true_amc.astype(int))
    measured = np.where(wrong, 0.0, TRUE_CRUSH) + rng.normal(0, NOISE, N)
    return dict(checked=checked | audited, audited=audited, excluded=excluded, wrong=wrong, measured=measured,
                used=used, audit_terc=audit_terc)


terc_true = terc_within_rep(np.abs(J))
mislab = (lab >= 0) & (lab != true_amc.astype(int))
print(f"default rule vs controls: R = {R} samples of n = {n}; P_ERR {P_ERR}, P_NULL {P_NULL}, gaps t(nu = {NU:g})")
for name, rule, nr in (("C0 no check", "none", None), ("DEFAULT, NULL reading R1", "default", "R1"),
                       ("DEFAULT, NULL reading R2", "default", "R2"), ("C1 check every event", "all", None)):
    o = run(rule, nr)
    kept = ~o["excluded"]
    terc_r0 = terc_within_rep(np.where(o["excluded"], 0.0, r0_of(np.where(o["used"] < 0, 0, o["used"]))))
    print(f"\n[{name}]  hand checks per sample: {o['checked'].sum() / R:.1f} (of which audit {o['audited'].sum() / R:.1f}); "
          f"excluded per sample {o['excluded'].sum() / R:.2f}")
    print(f"  {'tercile':>16} {'excluded':>9} {'wrong day0 (kept)':>18} {'mislabels fixed':>16} "
          f"{'unverified':>11} {'mean crush (kept)':>18}")
    for lbl, T in (("true |J|", terc_true), ("measured |r0|", terc_r0)):
        for t_ in range(3):
            m = T == t_
            mm = m & mislab
            unver = m & kept & ~o["checked"] & (lab >= 0)
            print(f"  {lbl + ' ' + ['low', 'mid', 'high'][t_]:>16} {o['excluded'][m].mean():9.4f} "
                  f"{o['wrong'][m & kept].mean():18.4f} {((o['used'] == true_amc)[mm]).mean():16.3f} "
                  f"{unver[m].mean():11.3f} {o['measured'][m & kept].mean():18.4f}")
    lo, hi = (terc_true == 0) & kept, (terc_true == 2) & kept
    d = o["wrong"][lo].mean() - o["wrong"][hi].mean()
    print(f"  wrong day 0, low minus high TRUE-|J| tercile = {d:+.4f}; "
          f"crush attenuation in the low tercile = {o['measured'][lo].mean() - TRUE_CRUSH:+.4f} log pts "
          f"({(o['measured'][lo].mean() - TRUE_CRUSH) / -TRUE_CRUSH:+.1%} of the true crush)")
    if rule == "default":
        # what the 17/17/16 audit can see: per sample, the share of audited events in each |r0| tercile whose
        # calendar label was wrong, against the true residual rate among unchecked events in that tercile
        a = o["audited"]
        T = o["audit_terc"]
        print("  audit (per sample): tercile, true residual wrong rate among unaudited unverified events, "
              "mean audit estimate, P(audit finds 0 errors), audit 95% upper bound when it finds 0")
        for t_ in range(3):
            res = (T == t_) & (lab >= 0) & ~o["checked"]
            true_rate = (mislab & res).sum() / max(res.sum(), 1)
            aa = (a & (T == t_)).reshape(R, n)
            ee = (a & (T == t_) & mislab).reshape(R, n)
            k_a, k_e = aa.sum(1), ee.sum(1)
            est = k_e / np.maximum(k_a, 1)
            print(f"    {['low', 'mid', 'high'][t_]:>4}: true {true_rate:.4f}; audit mean {est.mean():.4f} "
                  f"(sd {est.std():.4f}, n audited {k_a.mean():.1f}); P(0 found) {np.mean(k_e == 0):.3f}; "
                  f"upper bound at 0 found {1 - 0.05 ** (1 / max(k_a.mean(), 1)):.3f}")
        lo_e = (a & (T == 0) & mislab).reshape(R, n).sum(1)
        hi_e = (a & (T == 2) & mislab).reshape(R, n).sum(1)
        print(f"  P(audit finds MORE errors in the low |r0| tercile than in the high one) = {np.mean(lo_e > hi_e):.3f}; "
              f"P(it finds >= 2 more) = {np.mean(lo_e - hi_e >= 2):.3f}")
