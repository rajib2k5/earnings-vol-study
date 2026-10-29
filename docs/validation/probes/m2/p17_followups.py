"""p17: follow-ups from Channel A's hypotheses and from p02/p03 (claims 2a, 3b, 7, 8a).

(a) chain rows whose expiration is an AMC announcement date (classed clean): which iv_daily measures read them;
(b) iv_daily E pairs that skip a shorter spanning expiry with tau >= 5 that is not `ok`;
(c) forwards above 1,253 (where ADR 0003's "the lower root end always holds" stops being true);
(d) do the decimal-tie rows (p02) or the quadratic rows reach an E or a cm30 at day -1 / day 0 of the 348?
Usage: python p17_followups.py <stage dir> <p02 out dir>
"""
import sys
from pathlib import Path

import pandas as pd

st, out = Path(sys.argv[1]), Path(sys.argv[2])
ce = pd.read_parquet(st / "chain_expiry.parquet")
iv = pd.read_parquet(st / "iv_daily.parquet")
ev = pd.read_parquet(st / "events.parquet")
amc = ev[(ev["timing_used"] == "AMC") & ev["day0_session"].notna()][["security_id", "announce_date_used", "event_id"]]
rows = ce.merge(amc, left_on=["security_id", "expiration", "next_event_id"],
                right_on=["security_id", "announce_date_used", "event_id"])
rows = rows[(rows["status"] == "ok") & (rows["tau_sessions"] >= 5)]
keys = set(zip(rows["security_id"], rows["session_date"], rows["expiration"]))
print(f"(a) usable rows expiring on their next event's AMC announcement date: {len(rows)} "
      f"(spans_next_event values {rows['spans_next_event'].value_counts(dropna=False).to_dict()})")
for c in ("front_expiry", "cm30_exp_lo", "cm30_exp_hi", "ev_exp1", "ev_exp2"):
    hit = iv[[(s, d, e) in keys for s, d, e in zip(iv["security_id"], iv["session_date"], iv[c])]]
    print(f"    iv_daily rows reading one as {c}: {len(hit)} methods {hit['cm30_method'].value_counts().to_dict() if len(hit) else {}}")
sig = iv[iv["event_var"].isna() & iv["sigma_d_iv"].notna()]
print("    (sigma_d fallback rows cannot be attributed from stored columns; the cm30 reads above bound the exposure)")

okk = ce[(ce["tau_sessions"] >= 5)]
skipped = 0
by = {k: g for k, g in okk.groupby(["security_id", "session_date"])}
for r in iv[iv["ev_exp1"].notna()].itertuples(index=False):
    g = by[(r.security_id, r.session_date)]
    sp = g[(g["spans_next_event"] == True) & (g["expiration"] < r.ev_exp2)]
    if (sp["status"] != "ok").any():
        skipped += 1
print(f"(b) iv_daily E pairs that skip a non-ok spanning expiry shorter than T2: {skipped} of {iv['ev_exp1'].notna().sum()}")

hi = ce[ce["forward"] > 1253]
print(f"(c) rows with forward > 1253: {len(hi)}, securities {sorted(hi['security_id'].unique())}; "
      f"iv_no_root flags among all rows: {int(ce['flags'].str.contains('iv_no_root').sum())}")

import json
fund = json.load(open("app/public/data/sample_funnel.json"))["data"]
D = Path("data/derived")
eiv = pd.read_parquet(D / "event_iv.parquet")
evd = pd.read_parquet(D / "events.parquet")
ties = pd.read_parquet(out / "tie_keys.parquet")
quad = pd.read_parquet(out / "quad_keys.parquet")
tie_k = set(map(tuple, ties[["security_id", "session_date", "expiration"]].to_numpy()))
quad_k = set(map(tuple, quad.to_numpy()))
daily = evd[(evd["sample"] == "daily") & evd["day0_session"].notna()]
hits = {"tie": 0, "quad": 0}
for r in daily.itertuples(index=False):
    for d in (r.day_m1_session, r.day0_session):
        x = iv[(iv["security_id"] == r.security_id) & (iv["session_date"] == d)]
        if x.empty:
            continue
        x = x.iloc[0]
        used = {(r.security_id, d, e) for e in (x.ev_exp1, x.ev_exp2, x.cm30_exp_lo, x.cm30_exp_hi) if not pd.isna(e)}
        hits["tie"] += bool(used & tie_k)
        hits["quad"] += bool(used & quad_k)
print(f"(d) daily-sample events whose day -1 or day 0 E/cm30 reads a decimal-tie forward row: {hits['tie']}, "
      f"a quadratic row: {hits['quad']} (of {len(daily)} daily events)")
