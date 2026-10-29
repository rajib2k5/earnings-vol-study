"""p11c: the remaining milestone-2 numbers over the primary sample (claim 11), from data/derived.
Usage: python p11c_more_numbers.py <dir holding primary_ids.parquet from p10>
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ids = pd.read_parquet(Path(sys.argv[1]) / "primary_ids.parquet")
e = pd.read_parquet("data/derived/event_iv.parquet")
p = ids.merge(e, on="event_id")
a = e[e["event_id"] == "AAPL:2025-10-30"].iloc[0]
print(f"AAPL:2025-10-30 E={a.evar_m1:.8f} sqrtE={np.sqrt(a.evar_m1):.4%} crush30={a.crush_mean_adj:.4f} "
      f"front={a.crush_front_fixed:.4f} realised={a.realized_ret_0:.4%}")
ff, ds, rr = p["crush_front_fixed"].dropna(), p["dsigma_d_mean_adj"].dropna(), p["abs_ret_over_implied"].dropna()
print(f"front-fixed crush median {ff.median():.3f} (n={len(ff)}); dsigma median {ds.median():.4f} (n={len(ds)}); "
      f"|r0|/implied median {rr.median():.3f}, >1 {(rr > 1).mean():.1%} (n={len(rr)})")
x = p["implied_move_m1"].dropna()
print(f"sqrtE quantiles (n={len(x)}): " + ", ".join(f"p{int(q*100)} {x.quantile(q):.2%}" for q in (.1, .25, .5, .75, .9)))
c = p["crush_mean_adj"]
print(f"30-day crush (n={c.notna().sum()}): mean {c.mean():.4f} median {c.median():.4f} p10 {c.quantile(.1):.4f} p90 {c.quantile(.9):.4f}")
