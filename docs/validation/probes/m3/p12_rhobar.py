"""p12: Pynnonen (2022) eq. 32 rho-bar for the H1 (CRUSH) event set (claim 12). Own code, aggregates only.
Run: uv run --frozen --no-sync python docs/validation/probes/m3/p12_rhobar.py
"""
import numpy as np
import pandas as pd

SD = "/home/rajib2k5/data/vol-projects/earnings-vol-study/cache/stage/94065662cd46610c/"
ewo = pd.read_parquet(SD + "event_window_obs.parquet")
em = pd.read_parquet(SD + "event_measures.parquet")
ev = pd.read_parquet(SD + "events.parquet")
res = pd.read_parquet(SD + "results.parquet")
x = em.merge(ev, on="event_id")
h1 = x[(x["sample"] == "daily") & x["eligible_crush"] & x["crush_cboe"].notna()]
w = ewo[ewo.event_id.isin(h1.event_id)].sort_values(["event_id", "rel_day"]).copy()
w["inb_prev"] = w.groupby("event_id")["in_baseline"].shift(1).fillna(False).astype(bool)
w = w[w.in_baseline.astype(bool) & w.inb_prev & w.e_abn_cboe.notna()]
w = w.merge(h1[["event_id", "security_id", "s_abn_cboe"]], on="event_id")
w["z"] = w.e_abn_cboe / w.s_abn_cboe


def rhobar(df):
    g = df.groupby("session_date")["z"]
    s, ss, n = g.sum(), g.apply(lambda v: (v ** 2).sum()), g.size()
    return float((s ** 2 - ss).sum() / (n * (n - 1)).sum())


dup = w.groupby(["session_date", "security_id"]).size()
print(f"12 events {h1.event_id.nunique()}, clean baseline changes {len(w)}, dates {w.session_date.nunique()}; "
      f"(date, security) cells holding >1 event: {(dup > 1).sum()}")
r = rhobar(w)
print(f"12 own rho-bar (uncentred z, eq. 32 form) = {r:.4f}")
wc = w.copy()
wc["z"] = wc.z - wc.groupby("event_id").z.transform("mean")
print(f"12 with z centred per event (the paper's U has mean 0) = {rhobar(wc):.4f}")
kpp = res[(res.hypothesis == "H1") & (res.statistic == "kpp_t") & (res.adjustment == "market")]
print(f"12 results H1 kpp_t rbar (= nubar * rho-bar) = {float(kpp.rbar.iloc[0]):.6f}")
d0 = h1.day0_session.astype(str).to_numpy()
same = (d0[:, None] == d0[None, :]).astype(float)
iu = np.triu_indices(len(d0), 1)
nubar = same[iu].mean()
print(f"12 own nubar (share of pairs on the same day 0) = {nubar:.6f}; nubar * rho-bar = {nubar * r:.6f}")
# is it a few dates? drop the 5% of dates with the largest |cross-sectional mean z|
cs = w.groupby("session_date").z.mean().abs()
keep = cs[cs <= cs.quantile(0.95)].index
print(f"12 rho-bar without the 5% of dates with the largest |mean z|: {rhobar(w[w.session_date.isin(keep)]):.4f}")
for yr, g in w.groupby(pd.to_datetime(w.session_date).dt.year):
    print(f"12 rho-bar in calendar year {yr}: {rhobar(g):.4f} ({g.session_date.nunique()} dates)")
