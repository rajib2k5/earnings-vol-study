"""d04: the beta pool after F2 (delta claim 4). Reads the stage cache and the committed results; aggregates only.

Own beta per security = OLS through the origin over the one-session clean baseline changes of events whose
baseline passes 20/15 (event_measures baseline_n / baseline_n_changes, i.e. the panel's own counts), each
(security, session) once. Compared with the package's beta_vix_cboe (stage event_measures). Also: how many
changes the pool holds, how many come from failing events, the median, the H1 primary from results.
Falsifier (--falsify): pool every clean change (the pre-fix rule): must disagree.
Run: uv run --frozen --no-sync python docs/validation/probes/m3-delta/d04_beta.py [--falsify]
"""
import sys

import numpy as np
import pandas as pd

SD = "/home/rajib2k5/data/vol-projects/earnings-vol-study/cache/stage/94065662cd46610c/"
FALSIFY = "--falsify" in sys.argv
ewo = pd.read_parquet(SD + "event_window_obs.parquet")
em = pd.read_parquet(SD + "event_measures.parquet")
ev = pd.read_parquet(SD + "events.parquet")
md = pd.read_parquet(SD + "market_daily.parquet")
sess = pd.read_parquet(SD + "session.parquet")["session_date"].tolist()
sidx = {d: i for i, d in enumerate(sess)}
lnvix = {sidx[d]: v for d, v in zip(md["session_date"], md["ln_vix_cboe"]) if np.isfinite(v)}
w = ewo.merge(ev[["event_id", "security_id", "sample", "exclusion_reason"]], on="event_id").merge(
    em[["event_id", "baseline_n", "baseline_n_changes", "beta_vix_cboe"]], on="event_id").sort_values(["event_id", "rel_day"])
w["t"] = [sidx[d] for d in w.session_date]
w["m"] = [lnvix.get(t, np.nan) for t in w.t]
g = w.groupby("event_id")
w["dX"] = w.ln_cm30 - g.ln_cm30.shift(1)
w["dM"] = w.m - g.m.shift(1)
w["clean"] = w.in_baseline.astype(bool) & g.in_baseline.shift(1).fillna(False).astype(bool) & np.isfinite(w.dX) & np.isfinite(w.dM)
ok = (w.baseline_n >= 20) & (w.baseline_n_changes >= 15)
mask = w.clean if FALSIFY else (w.clean & ok)
c = w[mask].drop_duplicates(["security_id", "t"])
own = c.groupby("security_id").apply(lambda d: (d.dX * d.dM).sum() / (d.dM ** 2).sum(), include_groups=False)
n_own = c.groupby("security_id").size()
pkg = em.merge(ev[["event_id", "security_id"]], on="event_id").dropna(subset=["beta_vix_cboe"]).groupby("security_id").beta_vix_cboe
assert (pkg.nunique() == 1).all(), "one beta per security"
pkg = pkg.first()
d = (own.reindex(pkg.index) - pkg).abs()
all_clean = w[w.clean].drop_duplicates(["security_id", "t"])
fail_only = w[w.clean & ~ok].drop_duplicates(["security_id", "t"])
both = fail_only.merge(w[w.clean & ok][["security_id", "t"]].drop_duplicates(), on=["security_id", "t"])
print(f"{'FALSIFY (every clean change)' if FALSIFY else 'passing baselines only'}: securities {pkg.size}, "
      f"max |own - package beta| {d.max():.2e}; median own {own.median():.4f} package {pkg.median():.4f}; "
      f"min/max package {pkg.min():.3f}/{pkg.max():.3f}; changes per company {n_own.min()}-{n_own.max()}")
print(f"pool: {len(c)} changes in the pool; {len(all_clean)} clean changes overall; {len(fail_only)} from failing "
      f"events, of which {len(both)} also lie in a passing event's baseline (kept)")
R = pd.read_parquet("data/derived/results.parquet")
r = R[(R.family == "event_test") & (R.hypothesis == "H1") & (R.role == "primary")].iloc[0]
bm = R[(R.measure == "g1_calibration:measured") & (R.statistic == "beta_median")].estimate.iloc[0]
print(f"results: H1 {r.estimate:+.4f} t {r.stat:.2f}; g1 beta_median row {bm:.4f}")
if FALSIFY:
    sys.exit(0 if d.max() < 1e-9 else 1)
