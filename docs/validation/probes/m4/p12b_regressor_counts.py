"""p12b (claim 12, §6.7 and decision 4): regressor counts, the Yahoo cross-check aggregates, the vix_regime split
(label counts only). Run: uv run --frozen --no-sync python docs/validation/probes/m4/p12b_regressor_counts.py"""
import numpy as np
import pandas as pd

from earnings_vol import params
from earnings_vol.events.run import stage_dir

sd = stage_dir(params.load())
ev = pd.read_parquet(sd / "events.parquet").merge(pd.read_parquet(sd / "event_measures.parquet"), on="event_id")
for c in ("price_ref", "surprise_scaled", "abs_surprise_scaled_w", "sue_hist", "vix_regime", "ln_mcap_yf", "realized_ret_0_yf"):
    print(c, int(ev[c].notna().sum()))
p = ev[(ev["sample"] == "daily") & ev["eligible_crush"].astype(bool) & ev["crush_cboe"].notna()]
print("primary", len(p), "sue_hist", int(p["sue_hist"].notna().sum()))
k = p[p["realized_ret_0"].notna() & p["realized_ret_0_yf"].notna()]
d = (k["realized_ret_0_yf"] - k["realized_ret_0"]).abs() * 1e4
print(f"Yahoo vs forward return on {len(k)} primary events: median |diff| {d.median():.1f} bp, p95 "
      f"{np.percentile(d, 95):.1f} bp, corr {np.corrcoef(k['realized_ret_0_yf'], k['realized_ret_0'])[0, 1]:.4f}")
print("daily vix_regime split:", ev[ev["sample"] == "daily"]["vix_regime"].value_counts().to_dict())
