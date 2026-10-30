"""Where does the crush baselines' rho-bar of 0.30 come from? (milestone-3 page §8; milestone 4)

ADR 0005 ("How we'll know it's wrong") flags Pynnonen's rho-bar above about 0.2 for the crush:
"far more correlation than market adjustment should leave". Milestone 3 measured 0.301 and left
three questions open: is it a few dates where every company moves together, a stale snapshot shared
on a date, or a common factor that VIX does not capture (does a sector-IV factor remove it?).

This script measures, on H1's event set (the 347 daily primary events) and its standardised clean
baseline changes z = e / s_i (the input of kpp_t, stats/inputs.robust_inputs):
  1. rho-bar itself (stats/common_factor.rhobar = eventtests.pynnonen_rhobar), and how it splits
     over dates: the share of the cross-product from the top dates, the share of dates with a
     positive cross-product, the cross-sectional mean z of the top dates;
  2. the snapshots behind the top dates: the share of the date's firms whose iv_daily snapshot is
     not from that session, or is a stale repeat, and the share with an exactly zero ln cm30 change;
  3. rho-bar after removing a common IV factor from z with a per-firm loading
     (common_factor.residualise): the leave-one-firm-out mean of all firms (an equal-weighted
     single-stock IV factor), the leave-one-firm-out mean of the same sector (a sector-IV factor),
     and the sector factor after the market one;
  4. how much VIX explains: the correlation of the date's mean e with the change of ln VIX, and
     rho-bar with beta = 1 in place of the estimated beta (median 0.31).
H1's primary statistic is not changed by any of this.

Aggregates and dates only: no VIX value and no per-event VIX-adjusted value is printed.
Run from the repository root (needs the local stage cache):
  uv run --no-sync --frozen python research/prototypes/rhobar_crush.py > research/prototypes/rhobar_crush.out.txt
"""
import numpy as np

from earnings_vol import params as params_mod, schema, store
from earnings_vol.events.run import stage_dir
from earnings_vol.panel import abnormal
from earnings_vol.stats import common_factor, eventtests, inputs, run

p = params_mod.load()
f = run.load(p)
rows = run.primary_sets(f)[0]["H1"]
ri = inputs.robust_inputs(f, rows, "crush")
z = ri["z"]
firm = f.ev["security_id"].to_numpy(object)[rows]
sector = f.ev["gics_sector"].to_numpy(object)[rows]
t0 = int(f.sess[rows].min())
dates = [f.sessions.dates[t0 + k] for k in range(z.shape[1])]

print(f"H1 events {rows.size}, firms {len(set(firm))}, sectors {len(set(sector))}, calendar dates {z.shape[1]}")
rb = common_factor.rhobar(z)
print(f"1. rho-bar {rb:.4f} (eventtests.pynnonen_rhobar {eventtests.pynnonen_rhobar(z):.4f})")
c = common_factor.date_contributions(z)
use = c["pairs"] > 0
cross, pairs = c["cross"][use], c["pairs"][use]
print(f"   dates with >= 2 events: {use.sum()}; mean events per such date {c['n'][use].mean():.1f}")
print(f"   share of dates with a positive cross-product: {(cross > 0).mean():.3f}")
order = np.argsort(-cross)
tot = cross.sum()
for k in (1, 5, 10, 25, 50):
    print(f"   top {k:>2} dates: {cross[order[:k]].sum() / tot:.3f} of the cross-product, "
          f"{pairs[order[:k]].sum() / pairs.sum():.3f} of the pairs")
print(f"   rho-bar without the top 10 dates: {(tot - cross[order[:10]].sum()) / (pairs.sum() - pairs[order[:10]].sum()):.4f}")
mean_pair = cross / pairs
print(f"   per-date mean pair product: median {np.median(mean_pair):.3f}, quartiles "
      f"{np.percentile(mean_pair, 25):.3f} / {np.percentile(mean_pair, 75):.3f}")

# 2. The snapshots behind the top dates.
sd = stage_dir(p)
iv = store.read_table(sd / "iv_daily.parquet", schema.IV_DAILY)
snap = {(s, d): (sd_, st) for s, d, sd_, st in zip(iv["security_id"], iv["session_date"], iv["snapshot_date"],
                                                    iv["snapshot_status"])}
idx = np.flatnonzero(use)
print("2. top 10 dates by cross-product (date, events, mean z, mean pair product, "
      "share snapshot not that session or stale, share zero ln cm30 change):")
ewo = store.read_table(sd / "event_window_obs.parquet", schema.EVENT_WINDOW_OBS)
zero = {}
for e, d, v in zip(ewo["event_id"], ewo["session_date"], ewo["d_ln_cm30"]):
    zero.setdefault(d, []).append(v == 0.0 if v is not None and np.isfinite(v) else None)
for k in order[:10]:
    j = idx[k]
    d = dates[j]
    members = np.flatnonzero(np.isfinite(z[:, j]))
    off = [snap.get((firm[i], d), (None, "missing")) for i in members]
    bad = np.mean([(sd_ != d) or (st != "ok") for sd_, st in off])
    zr = [x for x in zero.get(d, []) if x is not None]
    print(f"   {d}  n {c['n'][j]:>3}  mean z {c['sum'][j] / c['n'][j]:+.2f}  pair {mean_pair[k]:+.2f}  "
          f"not-that-session/stale {bad:.2f}  zero change {np.mean(zr) if zr else float('nan'):.2f}")

# 3. A common single-stock IV factor, and a sector one.
market = common_factor.loo_factor(z, firm)
sect = common_factor.loo_factor(z, firm, sector)
r_m, load_m = common_factor.residualise(z, market, firm)
r_s, _ = common_factor.residualise(z, sect, firm)
r_ms, _ = common_factor.residualise(r_m, common_factor.loo_factor(r_m, firm, sector), firm)
lm = np.array(list(load_m.values()))
print("3. rho-bar after removing a factor (per-firm loading, residuals rescaled):")
print(f"   all-firm leave-one-out factor: {common_factor.rhobar(r_m):.4f} "
      f"(loadings median {np.median(lm):.2f}, range {lm.min():.2f} to {lm.max():.2f})")
print(f"   sector leave-one-out factor:   {common_factor.rhobar(r_s):.4f}")
print(f"   sector factor after the all-firm one: {common_factor.rhobar(r_ms):.4f}")
print("   for scale: G1's calibration measured the same-date correlation 0.294 across sectors and 0.360 within")

# 4. How much VIX explains.
win = abnormal.clean_changes(f.in_baseline[rows])
dM = abnormal.one_session_changes(f.M[rows])
beta = f.ev["beta_vix_cboe"].to_numpy(float)[rows]
e_win = np.where(win & np.isfinite(f.e[rows]), f.e[rows], np.nan)
dx_win = e_win + beta[:, None] * dM
z_b1 = inputs.calendar_axis(f, rows, (dx_win - dM) / np.sqrt(np.nanvar(dx_win - dM, axis=1, ddof=1))[:, None])
z_raw = inputs.calendar_axis(f, rows, dx_win / np.sqrt(np.nanvar(dx_win, axis=1, ddof=1))[:, None])
print("4. VIX:")
print(f"   rho-bar of the raw changes (no market adjustment): {common_factor.rhobar(z_raw):.4f}")
print(f"   rho-bar with beta = 1 for every firm:              {common_factor.rhobar(z_b1):.4f}")
cs = np.nanmean(np.where(np.isfinite(z), z, np.nan), axis=0)
dm_cal = inputs.calendar_axis(f, rows, np.where(win, dM, np.nan))
dm_d = np.nanmean(dm_cal, axis=0)
ok = np.isfinite(cs) & np.isfinite(dm_d) & (c["n"] >= 10)
print(f"   corr(date mean z, change of ln VIX) over {ok.sum()} dates with >= 10 events: "
      f"{np.corrcoef(cs[ok], dm_d[ok])[0, 1]:+.3f}")
csr = np.nanmean(np.where(np.isfinite(z_raw), z_raw, np.nan), axis=0)
ok2 = np.isfinite(csr) & np.isfinite(dm_d) & (c["n"] >= 10)
print(f"   corr(date mean raw z, change of ln VIX): {np.corrcoef(csr[ok2], dm_d[ok2])[0, 1]:+.3f}")
