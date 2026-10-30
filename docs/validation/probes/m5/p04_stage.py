"""p04: facts the report states that only the local stage cache can check. Prints counts, signs and dates only:
no per-event VIX-adjusted value and no VIX value.

    uv run --frozen --offline --no-sync python docs/validation/probes/m5/p04_stage.py [--falsify]

(a) "The market-adjusted change is negative in 99.1% of the 347 events" (gen_sign_z's estimate): count of
    crush_cboe < 0 over the eligible daily crush events; compare with eventtests.gen_sign's definition (A_i < 0).
(b) the realised day-0 range of the 347 primary events (the docs print 2024-12-05 to 2026-10-26).
(c) "every season mean is positive" (H2, milestone 3 §6.2): the sign of each season's mean RUNUP over the eligible
    daily run-up events, seasons as the stage labels them, the October 2026 tail merged as the package merges it.
(d) the share of mean-adjusted crush < 0 (committed column) for comparison.
--falsify: (a) counts crush_cboe <= -0.05 instead of < 0: the share must change.
"""
import sys

import pandas as pd

ST = "/home/rajib2k5/data/vol-projects/earnings-vol-study/cache/stage/74bed6f4b1281810/"
falsify = "--falsify" in sys.argv
em = pd.read_parquet(ST + "event_measures.parquet")
ev = pd.read_parquet(ST + "events.parquet")
j = em.merge(ev[["event_id", "sample", "day0_session", "season", "timing_used"]], on="event_id")
c = j[(j["sample"] == "daily") & j["eligible_crush"] & j["crush_cboe"].notna()]
thr = -0.05 if falsify else 0.0
neg = int((c["crush_cboe"] < thr).sum()) if not falsify else int((c["crush_cboe"] <= thr).sum())
print(f"(a) eligible daily crush events with crush_cboe: {len(c)}; below {'-0.05' if falsify else '0'}: {neg}; "
      f"share {neg / len(c):.4f}")
print(f"(b) day0_session range of those events: {c['day0_session'].min()} to {c['day0_session'].max()}")
r = j[(j["sample"] == "daily") & j["eligible_runup"] & j["runup_cboe"].notna()]
seasons = r.groupby("season")["runup_cboe"].agg(["size", "mean"])
print(f"(c) eligible daily run-up events: {len(r)}; seasons: {len(seasons)}; "
      f"sizes {dict(seasons['size'])}; seasons with a positive mean: {(seasons['mean'] > 0).sum()} of {len(seasons)}")
m = c["crush_mean_adj"]
print(f"(d) mean-adjusted crush below 0: {(m < 0).sum()} of {m.notna().sum()}")
