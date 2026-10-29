"""p01c: how much the beta pool matters (follow-up to Channel A's A1; NOT pre-registered).

beta as built (all non-excluded events, every sample) vs beta from events whose baseline passes 20/15 only,
vs daily events only. Prints the H1 and H2 equal-weighted means under each (aggregates only).
Run: uv run --frozen --no-sync python docs/validation/probes/m3/p01c_beta_pool.py
"""
import numpy as np
import pandas as pd

SD = "/home/rajib2k5/data/vol-projects/earnings-vol-study/cache/stage/94065662cd46610c/"
ewo = pd.read_parquet(SD + "event_window_obs.parquet")
em = pd.read_parquet(SD + "event_measures.parquet")
ev = pd.read_parquet(SD + "events.parquet")
md = pd.read_parquet(SD + "market_daily.parquet")
sess = pd.read_parquet(SD + "session.parquet")["session_date"].tolist()
sidx = {d: i for i, d in enumerate(sess)}
lnvix = {sidx[d]: v for d, v in zip(md["session_date"], md["ln_vix_cboe"]) if np.isfinite(v)}
w = ewo.merge(ev[["event_id", "security_id", "sample"]], on="event_id").merge(
    em[["event_id", "baseline_n", "baseline_n_changes"]], on="event_id").sort_values(["event_id", "rel_day"])
w["t"] = [sidx[d] for d in w.session_date]
w["m"] = [lnvix.get(t, np.nan) for t in w.t]
g = w.groupby("event_id")
w["dX"] = w.ln_cm30 - g.ln_cm30.shift(1)
w["dM"] = w.m - g.m.shift(1)
w["clean"] = w.in_baseline.astype(bool) & g.in_baseline.shift(1).fillna(False).astype(bool) & np.isfinite(w.dX) & np.isfinite(w.dM)
ok_base = (w.baseline_n >= 20) & (w.baseline_n_changes >= 15)


def betas(mask):
    c = w[w.clean & mask].drop_duplicates(["security_id", "t"])
    return c.groupby("security_id").apply(lambda d: (d.dX * d.dM).sum() / (d.dM ** 2).sum(), include_groups=False)


x = em.merge(ev, on="event_id")
h1 = x[(x["sample"] == "daily") & x.eligible_crush & x.crush_cboe.notna()]
dm0 = np.array([lnvix[sidx[d]] - lnvix[sidx[d] - 1] for d in h1.day0_session])
mu = {e: d[d.in_baseline.astype(bool)].m.mean() for e, d in w[w.event_id.isin(h1.event_id)].groupby("event_id")}
for label, mask in (("as built (all non-excluded)", pd.Series(True, index=w.index)), ("baseline passes 20/15 only", ok_base),
                    ("daily events only", w["sample"] == "daily")):
    b = betas(mask)
    bb = h1.security_id.map(b).to_numpy()
    crush = h1.crush_mean_adj.to_numpy() - bb * dm0
    print(f"{label:30s}: median beta {np.median(b):.3f}; H1 mean crush {crush.mean():+.4f}; "
          f"max |beta - beta_built| {np.max(np.abs(b - betas(pd.Series(True, index=w.index)))):.3f}")
