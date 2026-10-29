"""d01: the calibrated scale sig0 (delta claim 1) and H4's own series (claim 2).

Reads the stage cache only (run.load); writes nothing but stdout. Aggregates only.
  a) sig0 from the package (design_and_calibration) against the committed results rows, and an
     independent recomputation: exp(mean over firms of mean ln s_i) / sqrt(2/(1+phi) + 2 n^2).
  b) outcome independence: calibrate_on with the tested values replaced (permuted / sign-flipped /
     shifted by +1): sig0 must not move; firm_fx / jump_k must (proves the substitution took).
  c) the calibrated design with the production seeds (harness check: must give 4.45/0.40/0.50/4.75),
     and the same seeds with sig0 = 0.03 on both series (the pre-fix scale), every statistic.
  d) the same two settings on 10,000 FRESH seeds (paired), primaries and H4 robustness rows.
  e) H4's simulated event count vs the real 262 (sigma_d usable at day -1 and 0).
Run: uv run --frozen --no-sync python docs/validation/probes/m3-delta/d01_sig0.py [reps_fresh]
"""
import os
import sys

for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(v, "1")
import multiprocessing as mp  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from earnings_vol import params as P  # noqa: E402
from earnings_vol.panel import abnormal  # noqa: E402
from earnings_vol.stats import g1, inputs, run  # noqa: E402

REPS_FRESH = int(sys.argv[1]) if len(sys.argv) > 1 else 10000
p = P.load()
st = dict(p["stats"])
f = run.load(p)
des, cal, des_sd, cal_sd = run.design_and_calibration(f, st)

# a) provenance
R = pd.read_parquet("data/derived/results.parquet")
for lab, c in (("g1_calibration", cal), ("g1_calibration_sigma_d", cal_sd)):
    row = R[(R.measure == f"{lab}:params") & (R.statistic == "sig0")]
    print(f"a) {lab}: package sig0 {c['params']['sig0']:.6f}  committed {float(row.estimate.iloc[0]):.6f}  "
          f"diff {abs(c['params']['sig0'] - float(row.estimate.iloc[0])):.2e}")
sets = {h: inputs.event_set(f, m, "daily") for h, m in g1.TESTS.items()}
h1 = sets["H1"][np.isfinite(inputs.values(f, sets["H1"], "crush", "market"))]
for lab, rows, c, series in (("cm30", h1, cal, "cm30"), ("sigma_d", sets["H4"], cal_sd, "sigma_d")):
    e = inputs.clean_e(f, rows, series)
    s = f.ev["s_abn_cboe"].to_numpy(float)[rows] if series == "cm30" else np.sqrt(np.nanvar(e, axis=1, ddof=1))
    firm = f.ev["security_id"].to_numpy(object)[rows]
    fm = pd.Series(np.log(s)).groupby(firm).mean()
    # own rho1: pooled lag-1 autocorrelation of standardised clean changes (independent of abnormal.rhat)
    z = e / s[:, None]
    a, b = z[:, 1:], z[:, :-1]
    ok = np.isfinite(a) & np.isfinite(b)
    rho1_own = float((a[ok] * b[ok]).sum() / np.sqrt((a[ok] ** 2).sum() * (b[ok] ** 2).sum()))
    rho1 = c["measured"]["rho1"]
    n2 = -rho1 / (1 + 2 * rho1)
    phi = c["params"]["phi"]
    own = float(np.exp(fm.mean()) / np.sqrt(2 / (1 + phi) + 2 * n2))
    print(f"a) {lab}: own sig0 {own:.6f} (package {c['params']['sig0']:.6f}); geo-mean s {np.exp(fm.mean()):.4f}; "
          f"rho1 package {rho1:.4f} own-uncentred {rho1_own:.4f}; phi {phi:.4f}; n {np.sqrt(n2):.4f}; firms {fm.size}")

# b) outcome independence
orig_values = inputs.values
for lab, fn in (("permuted", lambda v: np.random.default_rng(1).permutation(v)), ("negated", lambda v: -v),
                ("shift+1", lambda v: v + 1.0), ("x3", lambda v: 3 * v)):
    inputs.values = lambda f_, r_, m_, a_, fn=fn: fn(orig_values(f_, r_, m_, a_))
    try:
        for meas, rows, c in (("crush", h1, cal), ("dsigma_d", sets["H4"], cal_sd)):
            c2 = run.calibrate_on(f, rows, meas, st)
            dp = {k: c2["params"][k] - c["params"][k] for k in ("sig0", "phi", "noise", "firm_fx", "jump_k")}
            print(f"b) {meas} vals {lab}: " + " ".join(f"d{k} {v:+.2e}" for k, v in dp.items()))
    finally:
        inputs.values = orig_values

# c/d) rates
STATE = {}


def rep(args):
    name, seed, robust, key = args
    dsg, dsd = STATE["designs"][name]
    sets_ = STATE["sets"][key]
    main = {h: r for h, r in sets_.items() if h != "H4"}
    second = (des_sd, dsd, {"H4": sets_["H4"]}) if "H4" in sets_ else None
    return g1.replicate((des, dsg, main, seed, 0.05, st, robust, second))


def show(label, r):
    parts = []
    for h in ("H1", "H2", "H3", "H4"):
        if h in r:
            parts.append(f"{h} {100 * r[h][r[h]['_primary']]:.2f}%")
    print(f"{label}: " + "; ".join(parts), flush=True)


if __name__ == "__main__":
    STATE["designs"] = {
        "cal": (dict(cal["params"]), dict(cal_sd["params"])),
        "cal_sig003": (dict(cal["params"], sig0=0.03), dict(cal_sd["params"], sig0=0.03)),
    }
    STATE["sets"] = {"all": des.sets}
    seed0 = int(st["g1_seed"])
    _, hi = g1.binom_band(2000)
    out = {}
    with mp.get_context("fork").Pool(20) as pool:
        for name in ("cal", "cal_sig003"):
            res = pool.map(rep, [(name, seed0 + 1_000_003 * 1 + r, True, "all") for r in range(2000)], chunksize=25)
            out[name] = g1.rates(res)
            show(f"c) production seeds, {name}", out[name])
        for h in ("H1", "H4"):
            for k in sorted(out["cal"][h]):
                if k.startswith("_"):
                    continue
                a_, b_ = out["cal"][h][k], out["cal_sig003"][h][k]
                print(f"c)   {h} {k:22s} cal {100 * a_:6.2f}%  sig0=0.03 {100 * b_:6.2f}%  "
                      f"{'OVER' if a_ > hi else '    '}/{'OVER' if b_ > hi else '    '}")
        fresh = 777_000_000
        paired = {}
        for name in ("cal", "cal_sig003"):
            res = pool.map(rep, [(name, fresh + r, True, "all") for r in range(REPS_FRESH)], chunksize=50)
            paired[name] = res
            show(f"d) {REPS_FRESH} fresh seeds, {name}", g1.rates(res))
        for h in ("H1", "H2", "H3", "H4"):
            k = paired["cal"][0][h]["_primary"]
            a_ = np.array([r[h][k] for r in paired["cal"]], float)
            b_ = np.array([r[h][k] for r in paired["cal_sig003"]], float)
            d = a_ - b_
            print(f"d)   {h} {k}: cal - sig0=0.03 = {100 * d.mean():+.3f} pp (paired se {100 * d.std(ddof=1) / np.sqrt(d.size):.3f}); "
                  f"flips cal-only {int((d > 0).sum())}, 0.03-only {int((d < 0).sum())}")
        for k in sorted(paired["cal"][0]["H4"]):
            if k.startswith("_"):
                continue
            a_ = np.mean([r["H4"][k] for r in paired["cal"]])
            b_ = np.mean([r["H4"][k] for r in paired["cal_sig003"]])
            print(f"d)   H4 {k:22s} cal {100 * a_:6.2f}%  sig0=0.03 {100 * b_:6.2f}%")

    # e) H4 simulated n vs real
    t = des_sd.target["dsigma_d"][des_sd.sets["H4"]]
    rows = des_sd.sets["H4"]
    both = des_sd.usable[rows, t] & des_sd.usable[rows, t - 1]
    print(f"e) H4 real set {rows.size}; sigma_d usable at day -1 and 0 in the G1 mask: {int(both.sum())}")
