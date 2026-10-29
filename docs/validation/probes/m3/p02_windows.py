"""p02: day 0, the tested quantities, the baseline counts and eligibility (claims 2a, 2b, 2d).

Read-only on the stage cache; own pandas code, no import of earnings_vol.panel. Prints only
differences and counts. Run: uv run --frozen --no-sync python docs/validation/probes/m3/p02_windows.py [--falsify]
--falsify: count spans across ANY excluded session (zone, null_iv) -> must mismatch.
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

# 2a day 0
bad = 0
n = 0
for r in ev.itertuples(index=False):
    if r.day0_session is None or r.day0_session != r.day0_session or r.timing_used not in ("BMO", "AMC"):
        continue
    a = r.announce_date_used
    nxt = next(d for d in sess if d > a)
    want = (a if a in sidx else nxt) if r.timing_used == "BMO" else nxt
    n += 1
    bad += int(want != r.day0_session) + int(sess[sidx[r.day0_session] - 1] != r.day_m1_session)
print(f"2a day 0 / day -1 checked on {n} events with BMO/AMC: violations {bad}")

# 2b quantities from the window rows (own)
W = ewo.merge(ev[["event_id", "sample", "security_id"]], on="event_id").merge(
    em[["event_id", "beta_vix_cboe", "baseline_n", "baseline_n_changes"]], on="event_id")
W["t"] = [sidx[d] for d in W["session_date"]]
W["m"] = [lnvix.get(t, np.nan) for t in W["t"]]
piv = {c: W.pivot(index="event_id", columns="rel_day", values=c) for c in ("ln_cm30", "aliv_cboe", "m")}
emi = em.set_index("event_id")
smp = ev.set_index("event_id")["sample"]
daily = [e for e in piv["ln_cm30"].index if smp[e] == "daily"]
x, m = piv["ln_cm30"].loc[daily], piv["m"].loc[daily]
beta = emi.loc[daily, "beta_vix_cboe"]
crush_own = (x[0] - x[-1]) - beta * (m[0] - m[-1])
d = (crush_own - emi.loc[daily, "crush_cboe"]).abs()
print(f"2b daily CRUSH own vs package: max |diff| {d.max():.3e}; both null {int((crush_own.isna() & emi.loc[daily,'crush_cboe'].isna()).sum())}; "
      f"null mismatch {int((crush_own.isna() != emi.loc[daily,'crush_cboe'].isna()).sum())}")
shift = (x[1] - x[0]) - beta * (m[1] - m[0])
print(f"2b falsifier (crush read one day late): max |diff| {(shift - emi.loc[daily,'crush_cboe']).abs().max():.3e}")
base_ok = (emi.loc[daily, "baseline_n"] >= 20) & (emi.loc[daily, "baseline_n_changes"] >= 15)
for name, rel in (("runup", -1), ("persist_1", 1), ("persist_5", 5), ("persist_10", 10)):
    own = piv["aliv_cboe"].loc[daily, rel].where(base_ok)
    pk = emi.loc[daily, f"{name}_cboe"]
    both = own.notna() & pk.notna()
    print(f"2b daily {name}: max |own - pkg| {(own[both] - pk[both]).abs().max():.3e}; "
          f"own-only {int((own.notna() & pk.isna()).sum())}, pkg-only {int((own.isna() & pk.notna()).sum())}")

# 2d baseline change counts, own
cnt_bad, checked = 0, 0
for eid, g in W.groupby("event_id"):
    g = g.sort_values("rel_day")
    b = g.loc[g.in_baseline.astype(bool), "rel_day"].to_numpy()
    k = 1 if smp[eid] == "daily" else 2
    reason = dict(zip(g.rel_day, g.baseline_excluded_reason))
    c = 0
    for a, z in zip(b[:-1], b[1:]):
        if z - a <= k and (FALSIFY or all(reason[j] == "not_observed" for j in range(a + 1, z))):
            c += 1
    checked += 1
    cnt_bad += int(c != emi.loc[eid, "baseline_n_changes"]) + int(len(b) != emi.loc[eid, "baseline_n"])
print(f"2d baseline_n / baseline_n_changes recomputed on {checked} events: mismatches {cnt_bad}")
# how many coarse/mixed changes are 2-session spans, and what lies inside them
spans = W[W.baseline_excluded_reason.notna()].groupby(["baseline_excluded_reason"]).size().to_dict()
print(f"2d excluded baseline-range sessions by reason (all samples): {spans}")
# eligibility (daily): crush needs -1 and 0 usable, a beta, the baseline
ok_cr = x[-1].notna() & x[0].notna() & beta.notna() & base_ok
el = emi.loc[daily, "eligible_crush"].astype(bool)
print(f"2d daily eligible_crush own vs package mismatches: {int((ok_cr != el).sum())} (own {int(ok_cr.sum())}, pkg {int(el.sum())})")
fails = (~base_ok).sum()
print(f"2d daily events failing the 20/15 baseline minimum: {int(fails)} of {len(daily)}")
sys.exit(1 if (FALSIFY and cnt_bad > 0) else 0)
