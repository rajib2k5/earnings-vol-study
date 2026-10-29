"""Does gate G1's calibrated DGP reproduce the real moments it was calibrated on? (milestone-3 review, F5)

For each calibrated series, the cm30 one behind H1-H3 and the sigma_d one behind H4 (stats/run.py
design_and_calibration), simulate K panels on the real event design from the calibrated parameters,
re-estimate the inputs with the package's own code (g1.estimate), run the same calibration
(g1.calibrate_from) on the simulated rows of the test's event set, and compare each measured moment
with the real one: mean and sd over the K panels, and z = (real - mean) / sd.

Aggregates only: no VIX value and no per-event VIX-adjusted value is printed.
Run from the repository root (needs the local stage cache):
  uv run --no-sync --frozen python research/prototypes/g1_moments.py 20 > research/prototypes/g1_moments.out.txt
"""
import sys

import numpy as np

from earnings_vol import params as params_mod
from earnings_vol.panel import abnormal
from earnings_vol.stats import g1, run

K = int(sys.argv[1]) if len(sys.argv) > 1 else 20
MOMENTS = ("rho1", "corr_same_date_across_sectors", "corr_same_date_within_sector", "corr_lag1_cross_firm",
           "cs_mean_acf", "ar_levels_raw", "ar_levels", "firm_crush_sd", "day0_variance_ratio", "sd_log_s")


def simulated(d: g1.Design, params: dict, rows: np.ndarray, seed: int, st: dict, first=None) -> dict:
    """One simulated panel's calibration moments. `first` = (cm30 design, cm30 params): the panel is
    then H4's second series of a replication, as gate G1 simulates it (g1.second_series: the first
    series' ln VIX path and its beta; second fix round)."""
    if first is None:
        x, m = g1.generate(np.random.default_rng(seed), d, params)
        est = g1.estimate(d, x, m)
    else:
        d1, p1 = first
        x1, m1 = g1.generate(np.random.default_rng(seed), d1, p1)
        _, _, est = g1.second_series(seed, d1, g1.estimate(d1, x1, m1), d, params, m1)
    vals = est["e"][rows, abnormal.col(0)]
    ok = np.isfinite(vals) & np.isfinite(est["s"][rows])
    r = rows[ok]
    e = np.where(est["clean"][r] & np.isfinite(est["e"][r]), est["e"][r], np.nan)
    cal = g1.calibrate_from(e, est["s"][r], est["aliv"][r], d.in_baseline[r], d.sess[r], d.firm[r], d.sector[r],
                            vals[ok], int(st["rhat_max_lag"]), int(st["psd_grid"]), int(st["kp_min_shared"]))
    return cal["measured"]


def main() -> None:
    p = params_mod.load()
    st = dict(p["stats"])
    f = run.load(p)
    des, cal, des_sd, cal_sd = run.design_and_calibration(f, st)
    print(f"G1 moment check: {K} simulated panels per series, params hash {p.params_hash[:16]}")
    for label, d, c, h, first in (("cm30 (H1-H3; calibrated on the CRUSH set)", des, cal, "H1", None),
                                  ("sigma_d (H4; calibrated on the DSIGMA_D set; the second series of a replication)",
                                   des_sd, cal_sd, "H4", (des, cal["params"]))):
        sims = [simulated(d, c["params"], d.sets[h], 1000 + k, st, first) for k in range(K)]
        print(f"\n{label}: {d.sets[h].size} events")
        print(f"  {'moment':32s} {'real':>9s} {'sim mean':>9s} {'sim sd':>8s} {'z':>6s}")
        for mo in MOMENTS:
            pick = (lambda v: v[0]) if mo == "cs_mean_acf" else (lambda v: v)
            real = float(pick(c["measured"][mo]))
            s = np.array([float(pick(x[mo])) for x in sims])
            z = (real - s.mean()) / s.std(ddof=1) if s.std(ddof=1) > 0 else float("nan")
            print(f"  {mo + (' (lag 1)' if mo == 'cs_mean_acf' else ''):32s} {real:9.4f} {s.mean():9.4f} "
                  f"{s.std(ddof=1):8.4f} {z:6.1f}")


if __name__ == "__main__":
    main()
