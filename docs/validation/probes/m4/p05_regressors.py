"""p05 (claim 5): own recomputation of the regressor columns from the stage tables (pandas merges, not the
package's dict code), look-ahead checks, and the model's z-scores / fixed effects. Prints counts and
differences only (no VIX value, no per-event value). Reads the stage cache and raw/yfinance (local).
Run: uv run --frozen --no-sync python docs/validation/probes/m4/p05_regressors.py [--falsify]
--falsify: own SUE_hist includes the current quarter in its history (must then disagree)."""
import sys

import numpy as np
import pandas as pd

from earnings_vol import config, params
from earnings_vol.events import calendar
from earnings_vol.events.run import stage_dir
from earnings_vol.ingest import prices, universe
from earnings_vol.stats import drivers, run

FALS = "--falsify" in sys.argv
p = params.load()
sd = stage_dir(p)
T = {n: pd.read_parquet(sd / f"{n}.parquet") for n in ("events", "event_iv", "eps", "event_measures", "chain_expiry",
                                                         "iv_daily", "session")}
ev, eiv, eps, em = T["events"], T["event_iv"], T["eps"], T["event_measures"].set_index("event_id")
bad = 0


def cmp(name, own: pd.Series, col: str, tol=1e-12):
    global bad
    got = em[col].reindex(own.index)
    both = own.notna() & got.notna()
    only_own, only_got = int((own.notna() & got.isna()).sum()), int((own.isna() & got.notna()).sum())
    diff = float((own[both].astype(float) - got[both].astype(float)).abs().max()) if both.any() else 0.0
    nn_got = int(em[col].notna().sum())
    ok = only_own == 0 and only_got == 0 and diff <= tol and int(own.notna().sum()) == nn_got
    bad += not ok
    print(f"{name:24s} own n {int(own.notna().sum()):5d} committed n {nn_got:5d} only-own {only_own} only-committed "
          f"{only_got} max|diff| {diff:.2e} {'ok' if ok else 'DIFF'}")


# price_ref: forward x df of iv_daily.front_expiry at event_iv.pre_session
x = eiv[["event_id", "pre_session"]].merge(ev[["event_id", "security_id"]], on="event_id")
x = x.merge(T["iv_daily"][["security_id", "session_date", "front_expiry"]],
            left_on=["security_id", "pre_session"], right_on=["security_id", "session_date"], how="left")
ce = T["chain_expiry"]
ce = ce[(ce["status"] == "ok") & ce["forward"].notna()]
x = x.merge(ce[["security_id", "session_date", "expiration", "forward", "df"]],
            left_on=["security_id", "pre_session", "front_expiry"], right_on=["security_id", "session_date", "expiration"],
            how="left", suffixes=("", "_ce"))
pr = (x["forward"] * x["df"]).where(lambda s: s > 0)
pr.index = x["event_id"]
cmp("price_ref", pr, "price_ref")
# surprise_scaled
lk = eps[eps["event_id"].notna()].set_index("event_id")["surprise"]
ss = (lk / pr.reindex(lk.index)).dropna()
cmp("surprise_scaled", ss, "surprise_scaled")
# winsorised |SURP| within events.sample
smp = ev.set_index("event_id")["sample"]
a = ss.abs()
w = a.copy()
for g, idx in a.groupby(smp.reindex(a.index)).groups.items():
    v = a[idx].to_numpy()
    w[idx] = np.clip(v, np.quantile(v, 0.01), np.quantile(v, 0.99))
cmp("abs_surprise_scaled_w", w, "abs_surprise_scaled_w")
# sue_hist: previous 8 with a surprise, by effective day 0; look-ahead check
sess = calendar.Sessions(T["session"]["session_date"].tolist())
ev["eff0"] = [calendar.effective_day0(a_, d_, sess) for a_, d_ in zip(ev["announce_date_used"], ev["day0_session"])]
s = ev[ev["event_id"].isin(ss.index)][["event_id", "security_id", "eff0"]].sort_values(["security_id", "eff0", "event_id"])
sue, sue_n, look = {}, {}, 0
ties = 0
for sid, g in s.groupby("security_id"):
    ids, days = g["event_id"].tolist(), g["eff0"].tolist()
    ties += len(days) - len(set(days))
    for i, e in enumerate(ids):
        prev = [ss[ids[k]] for k in range(max(0, i - 8), i)]
        if FALS:
            prev = prev[1:] + [ss[e]] if len(prev) >= 8 else prev + [ss[e]]
        look += sum(days[k] >= days[i] for k in range(max(0, i - 8), i))
        if len(prev) >= 4 and np.std(prev, ddof=1) > 0:
            sue[e] = (ss[e] - np.mean(prev)) / np.std(prev, ddof=1)
            sue_n[e] = len(prev)
cmp("sue_hist", pd.Series(sue, dtype=float), "sue_hist")
cmp("sue_hist_n", pd.Series(sue_n, dtype=float), "sue_hist_n", 0)
print(f"sue_hist: previous quarters dated on/after the event's own effective day 0: {look}; same-day ties within a "
      f"security: {ties}")
# ln_mcap_yf: own, from raw Yahoo closes and the rank-date cap file
raw = config.raw_dir()
caps = pd.read_csv(raw / "yfinance" / f"market_cap_{p['universe']['rank_date']}.csv").set_index("symbol")["market_cap_yf"]
own_mc, after_rank = {}, 0
for sid, g in ev.groupby("security_id"):
    sym = universe.yahoo_symbol(sid)
    path = raw / "yfinance" / f"{sym}.parquet"
    if not path.exists() or sid not in caps.index or pd.isna(caps[sid]):
        continue
    px = prices.load(sym, raw).set_index("date")["close"]
    last = px.sort_index().iloc[-1]
    for e, d in zip(g["event_id"], g["day_m1_session"]):
        if d is not None and d in px.index and px[d] > 0:
            own_mc[e] = np.log(caps[sid]) + np.log(px[d] / last)
            after_rank += d > pd.Timestamp(p["universe"]["rank_date"]).date()
cmp("ln_mcap_yf", pd.Series(own_mc, dtype=float), "ln_mcap_yf", 1e-9)
print("ln_mcap_yf: day -1 sessions after the rank date:", after_rank)
# Look-ahead of the inputs dated per event: pre/post sessions vs day -1 / day 0 by timing (daily, eligible)
z = ev.merge(eiv[["event_id", "pre_session", "post_session"]], on="event_id").merge(
    T["event_measures"][["event_id", "eligible_crush"]], on="event_id")
d = z[(z["sample"] == "daily") & z["eligible_crush"].astype(bool)]
for tm, g in d.groupby("timing_used"):
    print(f"daily eligible {tm}: n {len(g)}; pre == day -1: {int((g['pre_session'] == g['day_m1_session']).sum())}; "
          f"post == day 0: {int((g['post_session'] == g['day0_session']).sum())}; pre >= day 0: "
          f"{int((g['pre_session'] >= g['day0_session']).sum())}; announce date == day 0: "
          f"{int((g['announce_date_used'] == g['day0_session']).sum())}; announce date == day -1: "
          f"{int((g['announce_date_used'] == g['day_m1_session']).sum())}")
allp = z[z["pre_session"].notna() & z["day0_session"].notna()]
print("every event with a pre session and day 0: pre >= day 0 in", int((allp["pre_session"] >= allp["day0_session"]).sum()),
      "of", len(allp))
# The primary model: z-scores over its rows, fixed effects
f = run.load(p)
m = drivers.model_inputs(f, drivers.PRIMARY, tuple(p["drivers"]["surprise_winsor"]))
X, names = m["X"], m["names"]
zc = [names.index(t) for t in drivers.BASE_TERMS]
print("model: N", X.shape[0], "K", X.shape[1], "z means max", f"{np.abs(X[:, zc].mean(0)).max():.1e}", "z sd (ddof 1)",
      np.round(X[:, zc].std(0, ddof=1), 12).tolist())
sect = [n for n in names if n.startswith("sector:")]
seas = [n for n in names if n.startswith("season:")]
evm = f.ev.iloc[m["rows"]]
print("sector dummies", len(sect), "of", evm["gics_sector"].nunique(), "sectors; season dummies", len(seas), "of",
      evm["season"].nunique(), "seasons; dropped levels:", sorted(set(evm["gics_sector"]) - {n[7:] for n in sect}),
      sorted(set(evm["season"]) - {n[7:] for n in seas}))
raw_size = evm["ln_mcap_yf"].to_numpy(float)
print("size column == zscore(ln_mcap_yf):", np.allclose(X[:, names.index("size")],
                                                        (raw_size - raw_size.mean()) / raw_size.std(ddof=1)))
print("primary model rows == H1 set with every regressor:", m["rows"].size)
print("mismatching columns:", bad)
sys.exit(1 if bad else 0)
