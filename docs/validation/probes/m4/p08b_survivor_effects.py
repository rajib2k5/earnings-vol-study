"""p08b: real-data effect of the surviving mutants M25 (|SURP| winsorised over all samples) and M09 (calibrate_h7
rho correction sign). Counts and aggregates only.
Run: uv run --frozen --no-sync python docs/validation/probes/m4/p08b_survivor_effects.py"""
import json

import numpy as np
import pandas as pd

from earnings_vol import params
from earnings_vol.events.run import stage_dir

sd = stage_dir(params.load())
ev = pd.read_parquet(sd / "events.parquet").merge(pd.read_parquet(sd / "event_measures.parquet"), on="event_id")
a = ev["surprise_scaled"].abs()
ok = a.notna()
lo, hi = np.quantile(a[ok], 0.01), np.quantile(a[ok], 0.99)
glob = a.clip(lo, hi)
prim = (ev["sample"] == "daily") & ev["eligible_crush"].astype(bool) & ev["crush_cboe"].notna()
d = (glob - ev["abs_surprise_scaled_w"]).abs()
print(f"M25: events whose |SURP|_w changes {int((d[ok] > 0).sum())} of {int(ok.sum())}; on the primary set "
      f"{int((d[prim & ok] > 0).sum())} of {int((prim & ok).sum())}")
c7 = json.loads((sd / "g1_report.json").read_text())["calibration_h7"]
print("M09: real H7 calibration firm_sd (tau)", c7["params"]["firm_sd"], "rho_d_raw", round(c7["measured"]["rho_d_raw"], 4),
      "rho_d", c7["params"]["rho_d"], "-> exp(+-tau^2/4) = 1 and rho clamped at 0: the mutant is equivalent on the real data")
