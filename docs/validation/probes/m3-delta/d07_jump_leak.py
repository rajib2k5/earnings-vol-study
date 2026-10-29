"""d07: does the calibration read the tested MEAN? (unasked finding next to claim 1)
jump_k = sqrt((ratio - 1) infl), ratio = var of (A_i / s_i) around company means. A common shift of A does not
cancel inside A_i / s_i when s_i varies within a company, so the real mean crush (the H1 estimate) enters jump_k.
Compares the calibration on the real values with the calibration on values demeaned by their grand mean (the null
the gate simulates), then runs the calibrated design (production seeds, 2,000 reps) with each jump_k.
Run: uv run --frozen --no-sync python docs/validation/probes/m3-delta/d07_jump_leak.py
"""
import os
for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(v, "1")
import multiprocessing as mp  # noqa: E402
import numpy as np  # noqa: E402
from earnings_vol import params as P  # noqa: E402
from earnings_vol.stats import g1, inputs, run  # noqa: E402

p = P.load(); st = dict(p["stats"]); f = run.load(p)
des, cal, des_sd, cal_sd = run.design_and_calibration(f, st)
sets = {h: inputs.event_set(f, m, "daily") for h, m in g1.TESTS.items()}
h1 = sets["H1"][np.isfinite(inputs.values(f, sets["H1"], "crush", "market"))]
orig = inputs.values
inputs.values = lambda f_, r_, m_, a_: (lambda v: v - np.nanmean(v))(orig(f_, r_, m_, a_))
c0 = run.calibrate_on(f, h1, "crush", st)
s0 = run.calibrate_on(f, sets["H4"], "dsigma_d", st)
inputs.values = orig
for lab, a, b in (("cm30/CRUSH", cal, c0), ("sigma_d/DSIGMA_D", cal_sd, s0)):
    print(f"{lab}: jump_k real {a['params']['jump_k']:.3f} demeaned {b['params']['jump_k']:.3f}; day-0 ratio "
          f"{a['measured']['day0_variance_ratio']:.2f} vs {b['measured']['day0_variance_ratio']:.2f}; firm_fx "
          f"{a['params']['firm_fx']:.4f} vs {b['params']['firm_fx']:.4f}")
D = {}


def rep(args):
    name, seed = args
    dsg, dsd = D[name]
    return g1.replicate((des, dsg, {"H1": des.sets["H1"]}, seed, 0.05, st, True, (des_sd, dsd, {"H4": des.sets["H4"]})))


if __name__ == "__main__":
    D["real"] = (dict(cal["params"]), dict(cal_sd["params"]))
    D["demeaned"] = (dict(cal["params"], jump_k=c0["params"]["jump_k"]), dict(cal_sd["params"], jump_k=s0["params"]["jump_k"]))
    seed0 = int(st["g1_seed"])
    with mp.get_context("fork").Pool(20) as pool:
        for name in D:
            r = g1.rates(pool.map(rep, [(name, seed0 + 1_000_003 + k) for k in range(2000)], chunksize=25))
            print(name + ": " + "; ".join(f"{h} {k} {100 * v:.2f}%" for h in ("H1", "H4") for k, v in sorted(r[h].items())
                                           if not k.startswith("_")), flush=True)
