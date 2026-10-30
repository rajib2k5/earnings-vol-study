"""p01 (claim 1): re-run gate G1 for H5-H7 with the package's code, compare with the stage report.

Run: uv run --frozen --no-sync python docs/validation/probes/m4/p01_g1_drivers.py <scratch_out.json> [--falsify]
Reads the stage cache only; writes the re-run report to <scratch_out.json>. --falsify shifts the seed
block by one (the rates must then differ from the report: the comparison can fail).
"""
import json
import sys

from earnings_vol import params as params_mod
from earnings_vol.events.run import stage_dir
from earnings_vol.stats import run

out_path = sys.argv[1]
falsify = "--falsify" in sys.argv
p = params_mod.load()
st = p["stats"]
f = run.load(p)
des, cal, des_sd, cal_sd = run.design_and_calibration(f, st)
if falsify:
    _orig = run.driver_tasks
    run.driver_tasks = lambda names, reps, seed0, block0: _orig(names, reps, seed0, block0 + 1)
drv = run.run_g1_drivers(p, f, des, cal, 20)
json.dump(drv, open(out_path, "w"), indent=1, sort_keys=True, default=float)
rep = json.loads((stage_dir(p) / "g1_report.json").read_text())
bad = 0
n = 0
for name, by in drv["rates"].items():
    for h, rates in by.items():
        for k, v in rates.items():
            if k.startswith("_"):
                continue
            n += 1
            w = rep["rates"][name][h][k]
            if abs(float(v) - float(w)) > 0:
                bad += 1
                print(f"DIFF {name} {h} {k}: rerun {v} report {w}")
print(f"compared {n} H5-H7 rates; differ {bad}")
print("gate rerun", drv["gate"], "report", {h: rep["gate"][h] for h in ("H5", "H6", "H7")})
print("calibrated primaries:", {h: drv["rates"]["calibrated"][h][drv["rates"]["calibrated"][h]["_primary"]]
                               for h in ("H5", "H6", "H7")})
print("calibration_h7 equal:", drv["calibration_h7"] == rep["calibration_h7"])
print("n_events", drv["n_events"], "report", rep.get("n_events_drivers"))
for h in ("H5", "H6", "H7"):
    print("power", h, drv["power_summary"][h], "report", rep["power"][h])
sys.exit(1 if bad else 0)
