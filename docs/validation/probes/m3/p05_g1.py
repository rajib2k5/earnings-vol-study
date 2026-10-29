"""p05: gate G1 (claims 5a-5d). Read-only on the stage cache; writes only to argv[2] (scratch).

  a   re-run the calibrated design, 2,000 reps, the builder's seeds -> compare with g1_report.json
  b   simulate the calibrated DGP and re-run calibrate() on the simulated panel (moments)
  c   the AR estimator's reading at several true phi (same pipeline as b)
  d   H1-H4 primary rates under alternative calibrations (phi, kappa), robust rows off
Run: uv run --frozen --no-sync python docs/validation/probes/m3/p05_g1.py <a|b|c|d> <outfile> [reps]
"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
import json  # noqa: E402
import multiprocessing as mp  # noqa: E402
import sys  # noqa: E402

import numpy as np  # noqa: E402

from earnings_vol import params as params_mod  # noqa: E402
from earnings_vol.panel import abnormal  # noqa: E402
from earnings_vol.stats import g1, run  # noqa: E402

REPORT = "/home/rajib2k5/data/vol-projects/earnings-vol-study/cache/stage/94065662cd46610c/g1_report.json"
S = {}


def setup():
    p = params_mod.load()
    st = p["stats"]
    f = run.load(p)
    des, cal = run.design_and_calibration(f, st)
    S.update(p=p, st=dict(st), des=des, cal=cal)


def _rep(args):
    params, seed, robust = args
    return g1.replicate((S["des"], params, S["des"].sets, seed, 0.05, S["st"], robust))


def rates_for(params, seeds, robust, workers=10):
    with mp.get_context("fork").Pool(workers) as pool:
        res = pool.map(_rep, [(params, s, robust) for s in seeds], chunksize=20)
    return g1.rates(res)


def sim_moments(params, seed):
    """Simulate one panel from the DGP and compute calibrate() exactly as run.design_and_calibration
    does on the real data, using the H1 rows."""
    d = S["des"]
    rng = np.random.default_rng(seed)
    x, m = g1.generate(rng, d, params)
    X = np.where(d.usable, x[d.firm[:, None], d.sess], np.nan)
    M = m[d.sess]
    clean_all = abnormal.clean_changes(d.in_baseline)
    dX, dM = abnormal.one_session_changes(X), abnormal.one_session_changes(M)
    betas = abnormal.beta_by_security(d.firm, d.sess, dX, dM, clean_all)
    beta = np.array([betas[q][0] for q in d.firm], float)
    al, _ = abnormal.aliv(X, M, d.in_baseline, beta)
    e_all = abnormal.abnormal_changes(X, M, beta)
    s_all = abnormal.baseline_sd(e_all, clean_all)
    rows = d.sets["H1"]
    clean = clean_all[rows]
    e = np.where(clean & np.isfinite(e_all[rows]), e_all[rows], np.nan)
    s = s_all[rows]
    rho, _ = abnormal.rhat(e_all[rows], s, clean, 10, 512)
    sec_of = d.firm[rows]
    cal_firms = sorted(set(sec_of.tolist()))
    z_firm = np.full((len(cal_firms), d.T), np.nan)
    for i in range(rows.size):
        k = cal_firms.index(sec_of[i])
        ok = np.isfinite(e[i]) & ~np.isfinite(z_firm[k, d.sess[rows[i]]])
        z_firm[k, d.sess[rows[i]][ok]] = e[i, ok] / s[i]
    cal_sector = np.array([d.firm_sector[c] for c in cal_firms])
    lo, hi = abnormal.col(-60), abnormal.col(-22)
    levels = [np.where(d.in_baseline[r, lo:hi + 1], al[r, lo:hi + 1], np.nan) for r in rows]
    crush = e_all[rows, abnormal.col(0)]
    by = {c: np.flatnonzero(sec_of == c) for c in cal_firms}
    return g1.calibrate(z_firm, cal_sector, float(rho[0]), levels, [e[ix][np.isfinite(e[ix])] for ix in by.values()],
                        [crush[ix] for ix in by.values()], [crush[ix] / s[ix] for ix in by.values()],
                        [np.log(s[ix]) for ix in by.values()], 20, level_s=s)["measured"]


def _mom(args):
    params, seed = args
    return sim_moments(params, seed)


KEYS = ("rho1", "corr_same_date_across_sectors", "corr_same_date_within_sector", "corr_lag1_cross_firm",
        "ar_levels_raw", "ar_levels", "drift_sd", "firm_crush_sd", "day0_variance_ratio", "sd_log_s")


def moments(params, n, seed0, workers=10):
    with mp.get_context("fork").Pool(workers) as pool:
        out = pool.map(_mom, [(params, seed0 + k) for k in range(n)])
    res = {}
    for k in KEYS:
        v = np.array([o[k] for o in out], float)
        res[k] = {"mean": float(v.mean()), "sd": float(v.std(ddof=1))}
    v = np.array([o["cs_mean_acf"][0] for o in out])
    res["cs_mean_acf1"] = {"mean": float(v.mean()), "sd": float(v.std(ddof=1))}
    return res


def main():
    mode, outfile = sys.argv[1], sys.argv[2]
    reps = int(sys.argv[3]) if len(sys.argv) > 3 else 2000
    setup()
    cal = S["cal"]["params"]
    out = {"mode": mode, "reps": reps}
    if mode == "a":
        seed0 = int(S["p"]["stats"]["g1_seed"])
        seeds = [seed0 + 1_000_003 * 1 + r for r in range(reps)]
        mine = rates_for(dict(cal), seeds, True, workers=12)
        theirs = json.load(open(REPORT))["rates"]["calibrated"]
        out["mine"] = mine
        out["max_abs_diff_vs_report"] = max(abs(mine[h][k] - theirs[h][k]) for h in mine for k in mine[h]
                                           if not k.startswith("_"))
        out["calibration_params_equal_report"] = all(
            abs(cal[k] - json.load(open(REPORT))["calibration"]["params"][k]) < 1e-12 for k in cal)
    elif mode == "b":
        real = S["cal"]["measured"]
        sim = moments(dict(cal), reps, 777)
        out["real"] = {k: real[k] for k in KEYS} | {"cs_mean_acf1": real["cs_mean_acf"][0]}
        out["sim"] = sim
        out["z"] = {k: (out["real"][k] - sim[k]["mean"]) / sim[k]["sd"] if sim[k]["sd"] > 0 else None for k in sim}
    elif mode == "c":
        out["reading"] = {}
        for phi in (1.0, 0.995, 0.99, 0.982, 0.97, 0.95):
            mm = moments(dict(cal, phi=phi), reps, 900)
            out["reading"][str(phi)] = {"ar_levels": mm["ar_levels"], "ar_levels_raw": mm["ar_levels_raw"]}
    elif mode == "d":
        meas = S["cal"]["measured"]
        n2 = cal["noise"] ** 2
        infl = 1 + 2 * n2
        alt = {
            "calibrated": dict(cal),
            "phi=1.0": dict(cal, phi=1.0),
            "phi=0.995": dict(cal, phi=0.995),
            "phi=0.99": dict(cal, phi=0.99),
            "kappa=0 (rho_m refit)": dict(cal, noise_common=0.0,
                                          rho_m=meas["corr_same_date_across_sectors"] * infl),
            "kappa=0, phi=1.0": dict(cal, noise_common=0.0, phi=1.0,
                                     rho_m=meas["corr_same_date_across_sectors"] * infl),
            "drift=0.0005": dict(cal, drift=0.0005),
        }
        lo, hi = g1.binom_band(reps, 0.05)
        out["band"] = [lo, hi]
        out["rates"] = {}
        for k, prm in alt.items():
            rr = rates_for(prm, [5_000_000 + r for r in range(reps)], False, workers=12)
            out["rates"][k] = {h: {"primary": v["_primary"], "rate": v[v["_primary"]]} for h, v in rr.items()}
            print(k, {h: round(100 * v["rate"], 2) for h, v in out["rates"][k].items()}, flush=True)
    with open(outfile, "w") as fh:
        json.dump(out, fh, indent=1, default=float)
    print(json.dumps(out, indent=1, default=float)[:4000])


if __name__ == "__main__":
    main()
