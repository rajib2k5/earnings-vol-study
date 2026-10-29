"""p01: beta per security, its sessions, look-ahead, and the twin consistency (claims 1a-1d).

Read-only on the stage cache. Prints only differences, counts and aggregates (no VIX value,
no per-event VIX-adjusted value). Own pandas code: no import of earnings_vol.panel.
Run: uv run --frozen --no-sync python docs/validation/probes/m3/p01_beta.py [--falsify]
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

w = ewo.merge(ev[["event_id", "security_id", "day0_session", "sample"]], on="event_id")
w = w.sort_values(["event_id", "rel_day"]).reset_index(drop=True)
w["t"] = [sidx[d] for d in w["session_date"]]
w["m"] = [lnvix.get(t, np.nan) for t in w["t"]]
g = w.groupby("event_id")
w["x_prev"] = g["ln_cm30"].shift(1)
w["m_prev"] = g["m"].shift(1)
w["inb_prev"] = g["in_baseline"].shift(1).fillna(False).astype(bool)
w["dX"] = w["ln_cm30"] - w["x_prev"]
w["dM"] = w["m"] - w["m_prev"]
if FALSIFY:   # mutant: every change with both ends usable, not only clean baseline changes
    sel = np.isfinite(w["dX"]) & np.isfinite(w["dM"])
else:
    sel = w["in_baseline"].astype(bool) & w["inb_prev"] & np.isfinite(w["dX"]) & np.isfinite(w["dM"])
c = w[sel].drop_duplicates(["security_id", "t"])
agg = c.groupby("security_id").apply(lambda d: pd.Series({"beta": (d.dX * d.dM).sum() / (d.dM ** 2).sum(),
                                                          "n": len(d)}), include_groups=False)
cmp_ = em.merge(ev[["event_id", "security_id"]], on="event_id").dropna(subset=["beta_vix_cboe"])
cmp_ = cmp_.merge(agg, left_on="security_id", right_index=True)
dbeta = (cmp_["beta_vix_cboe"] - cmp_["beta"]).abs().max()
dn = (cmp_["beta_n"] - cmp_["n"]).abs().max()
print(f"1a beta recomputed for {agg.shape[0]} securities; max |beta_pkg - beta_own| = {dbeta:.3e}; "
      f"max |beta_n diff| = {dn}")
if FALSIFY:
    sys.exit(1 if dbeta > 1e-9 else 0)

# 1a': which events feed beta: samples and failing baselines
used = c.merge(em[["event_id", "baseline_n", "baseline_n_changes"]], on="event_id")
short = used[(used.baseline_n < 20) | (used.baseline_n_changes < 15)]
print(f"1a' beta changes by sample of the contributing event: {used['sample'].value_counts().to_dict()}; "
      f"changes from events whose baseline fails 20/15: {len(short)} ({short.event_id.nunique()} events)")

# 1b: zones of every same-security event (all events except duplicate_row; no day 0 -> both candidates)
zones = {}
for r in ev.itertuples(index=False):
    if r.exclusion_reason == "duplicate_row":
        continue
    if r.day0_session is not None and r.day0_session == r.day0_session:
        cs = [sidx[r.day0_session]]
    else:
        a = r.announce_date_used
        nxt = next(i for i, d in enumerate(sess) if d > a)
        cs = [nxt] + ([sidx[a]] if a in sidx else [])
    zones.setdefault(r.security_id, []).extend([(r.event_id, cc - 21, cc + 10) for cc in cs])
bad = 0
for r in c.itertuples(index=False):
    for eid, lo, hi in zones.get(r.security_id, []):
        if eid != r.event_id and (lo <= r.t <= hi or lo <= r.t - 1 <= hi):
            bad += 1
print(f"1b beta changes with an end inside another same-security event's [-21,+10] zone: {bad} of {len(c)}")

# 1c: look-ahead. For each event with a beta, the share of its security's beta changes dated after its day 0 / +10
d0 = {r.event_id: sidx[r.day0_session] for r in ev.itertuples(index=False)
      if r.day0_session is not None and r.day0_session == r.day0_session}
ts_by_sec = {s: np.sort(d.t.to_numpy()) for s, d in c.groupby("security_id")}
after0, after10, n_ev = [], [], 0
for r in cmp_.itertuples(index=False):
    ts = ts_by_sec[r.security_id]
    after0.append((ts > d0[r.event_id]).mean())
    after10.append((ts > d0[r.event_id] + 10).mean())
    n_ev += 1
after0, after10 = np.array(after0), np.array(after10)
inwin = 0
for r in cmp_.itertuples(index=False):
    ts = ts_by_sec[r.security_id]
    inwin += int(((ts >= d0[r.event_id] - 21) & (ts <= d0[r.event_id] + 10)).sum())
print(f"1c events with a beta: {n_ev}; with >=1 beta change after day 0: {(after0 > 0).sum()}; "
      f"after +10: {(after10 > 0).sum()}; median share after day 0 {np.median(after0):.3f}; "
      f"beta changes inside the event's own [-21,+10]: {inwin}")

# 1d: twin consistency (differences only)
x = em.merge(ev[["event_id", "day0_session", "sample"]], on="event_id")
x = x[x["crush_cboe"].notna() & (x["sample"] == "daily")]
m0 = np.array([lnvix.get(sidx[d], np.nan) for d in x.day0_session])
m1 = np.array([lnvix.get(sidx[d] - 1, np.nan) for d in x.day0_session])
diff = (x["crush_cboe"].to_numpy() + x["beta_vix_cboe"].to_numpy() * (m0 - m1)) - x["crush_mean_adj"].to_numpy()
print(f"1d daily crush: max |crush_cboe + beta dm - crush_mean_adj| = {np.nanmax(np.abs(diff)):.3e} over {len(x)}")
wb = w.merge(em[["event_id", "beta_vix_cboe"]], on="event_id")
mu_m = wb[wb.in_baseline.astype(bool)].groupby("event_id")["m"].mean()
wb["mu_m"] = wb["event_id"].map(mu_m)
ok = wb["aliv_cboe"].notna() & wb["aliv_mean_adj"].notna() & np.isfinite(wb["m"])
dd = (wb.loc[ok, "aliv_cboe"] - wb.loc[ok, "aliv_mean_adj"]) + wb.loc[ok, "beta_vix_cboe"] * (wb.loc[ok, "m"] - wb.loc[ok, "mu_m"])
print(f"1d aliv: max |aliv_cboe - aliv_mean_adj + beta (m - mu_m)| = {dd.abs().max():.3e} over {ok.sum()} rows")
rel = em.merge(ewo[ewo.rel_day == -1][["event_id", "aliv_cboe"]], on="event_id")
rr = rel[rel.runup_cboe.notna()]
print(f"1d runup_cboe == aliv_cboe(-1) for daily+mixed? max |diff| = "
      f"{(rr.runup_cboe - rr.aliv_cboe).abs().max():.3e} (coarse may read -2)")
