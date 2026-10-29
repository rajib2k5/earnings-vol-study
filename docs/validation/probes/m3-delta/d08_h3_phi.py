"""d08: H3 (and H2) under random-walk levels (delta claim 3). Stage cache only; stdout only.
  1. the fixer's four phi = 1 blocks (seeds 888_000_000 + 10_000 k + r, k = 0..3, from its phi_dep.py): reproduce;
  2. 10,000 FRESH seeds at phi = 1, at phi = 0.995, and at phi = 1 with sig0 = 0.03 (the pre-fix scale), paired;
  3. the exact binomial 99% band for 10,000 replications (what 5.86% over 10,000 should be compared with).
Run: uv run --frozen --no-sync python docs/validation/probes/m3-delta/d08_h3_phi.py
"""
import os
for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(v, "1")
import multiprocessing as mp  # noqa: E402
import numpy as np  # noqa: E402
from earnings_vol import params as P  # noqa: E402
from earnings_vol.stats import g1, run  # noqa: E402

p = P.load(); st = dict(p["stats"]); f = run.load(p)
des, cal, des_sd, cal_sd = run.design_and_calibration(f, st)
RAMP = {h: des.sets[h] for h in ("H2", "H3")}


def rep(args):
    prm, seed = args
    return g1.replicate((des, prm, RAMP, seed, 0.05, st, False))


def flags(res, h):
    k = res[0][h]["_primary"]
    return np.array([r[h][k] for r in res], float)


if __name__ == "__main__":
    with mp.get_context("fork").Pool(20) as pool:
        tot = []
        for k in range(4):
            res = pool.map(rep, [(dict(cal["params"], phi=1.0), 888_000_000 + 10_000 * k + r) for r in range(2000)], chunksize=25)
            tot.append(flags(res, "H3").mean())
            print(f"1) fixer block k={k}: H2 {100 * flags(res, 'H2').mean():.2f}%  H3 {100 * tot[-1]:.2f}%", flush=True)
        out = {}
        for lab, prm in (("phi=1", dict(cal["params"], phi=1.0)), ("phi=0.995", dict(cal["params"], phi=0.995)),
                         ("phi=1,sig0=0.03", dict(cal["params"], phi=1.0, sig0=0.03))):
            res = pool.map(rep, [(prm, 555_000_000 + r) for r in range(10_000)], chunksize=50)
            out[lab] = res
            h3 = flags(res, "H3")
            blocks = [100 * h3[i:i + 2000].mean() for i in range(0, 10_000, 2000)]
            print(f"2) {lab}, 10,000 fresh: H2 {100 * flags(res, 'H2').mean():.2f}%  H3 {100 * h3.mean():.2f}% "
                  f"(binomial se {100 * np.sqrt(h3.mean() * (1 - h3.mean()) / h3.size):.2f}); 2,000-blocks "
                  + " ".join(f"{b:.2f}" for b in blocks), flush=True)
        d = flags(out["phi=1"], "H3") - flags(out["phi=1,sig0=0.03"], "H3")
        print(f"2) phi=1: calibrated sig0 minus sig0=0.03, paired: {100 * d.mean():+.3f} pp (se {100 * d.std(ddof=1) / np.sqrt(d.size):.3f})")
    print(f"3) exact binomial 99% band at 10,000: {g1.binom_band(10_000)}; at 2,000: {g1.binom_band(2000)}")
