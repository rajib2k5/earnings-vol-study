"""How much does the size of the ramp primaries depend on the AR of levels phi? (second fix round, D2)

Gate G1's calibrated cm30 design (stats/run.py design_and_calibration, every other parameter as
calibrated) with only phi changed: the calibrated value (0.985), 0.99, 0.995 and 1 (random-walk
levels). REPS replications each, on the real H2 and H3 event sets, primaries only (robust rows off).
The seeds are recorded: replication r of phi number k uses g1_seed + 1_000_003 * (2000 + k) + r, a
block no other G1 run uses (the main run uses blocks 1 .. 33, the re-measure block 1000).

Each rate is compared with the upper edge of the exact binomial 99% band FOR ITS REPLICATIONS
(g1.binom_band: 6.30% at 2,000, 5.57% at 10,000), as ADR 0005 §5 sets it.
Aggregates only: no VIX value and no per-event VIX-adjusted value is printed.
Run from the repository root (needs the local stage cache):
  uv run --no-sync --frozen python research/prototypes/g1_phi.py 10000 > research/prototypes/g1_phi.out.txt
"""
import os
import sys

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import multiprocessing as mp  # noqa: E402

import numpy as np  # noqa: E402

from earnings_vol import params as params_mod  # noqa: E402
from earnings_vol.stats import g1, run  # noqa: E402

REPS = int(sys.argv[1]) if len(sys.argv) > 1 else 10000
S: dict = {}


def rep(args):
    phi, seed = args
    prm = dict(S["cal"], phi=phi)
    return g1.replicate((S["des"], prm, S["sets"], seed, S["alpha"], S["st"], False))


def main() -> None:
    p = params_mod.load()
    st = dict(p["stats"])
    f = run.load(p)
    des, cal, _, _ = run.design_and_calibration(f, st)
    S.update(des=des, cal=dict(cal["params"]), sets={h: des.sets[h] for h in ("H2", "H3")}, alpha=float(st["alpha"]),
             st=st)
    seed0 = int(st["g1_seed"])
    hi = g1.binom_band(REPS, S["alpha"])[1]
    print(f"G1 ramp primaries against phi: {REPS} replications per phi, params hash {p.params_hash[:16]}; "
          f"band upper edge at {REPS}: {100 * hi:.2f}%")
    phis = [round(float(cal["params"]["phi"]), 4), 0.99, 0.995, 1.0]
    with mp.get_context("fork").Pool(20) as pool:
        for k, phi in enumerate(phis):
            tasks = [(phi, seed0 + 1_000_003 * (2000 + k) + r) for r in range(REPS)]
            res = pool.map(rep, tasks, chunksize=max(1, REPS // 80))
            rates = g1.rates(res)
            line = []
            for h in ("H2", "H3"):
                pr = rates[h]["_primary"]
                x = rates[h][pr]
                se = np.sqrt(x * (1 - x) / REPS)
                line.append(f"{h} {pr} {100 * x:.2f}% (se {100 * se:.2f}, {'above' if x > hi else 'within'} the band)")
            print(f"phi {phi}: " + "; ".join(line), flush=True)


if __name__ == "__main__":
    main()
