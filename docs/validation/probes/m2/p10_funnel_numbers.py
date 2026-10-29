"""p10/p11: the funnel, the terciles, the 285 missing moves, P4, P5, P6 and the leak, recomputed.

Claims 10 and 11. Reads the committed tables in data/derived (and, for P6 only, the local
chain_expiry). Nothing from earnings_vol is imported: the steps, the baseline rule of ADR 0004 §1,
the orphan zones, the terciles and every statistic are written here.
Run from the repository root:
  python docs/validation/probes/m2/p10_funnel_numbers.py <stage dir> [--mutant-snapshot-baseline]
--mutant-snapshot-baseline counts baseline sessions by snapshot only (the milestone-1 rule): it must
not give 348 (falsifier for the baseline change).
"""
import json
import math
import sys
from bisect import bisect_left, bisect_right
from pathlib import Path

import numpy as np
import pandas as pd

stage = Path(sys.argv[1])
D = Path("data/derived")
ev = pd.read_parquet(D / "events.parquet")
iv = pd.read_parquet(D / "iv_daily.parquet")
eiv = pd.read_parquet(D / "event_iv.parquet")
eps = pd.read_parquet(D / "eps.parquet")
tc = pd.read_parquet(D / "timing_check.parquet")
S = list(pd.read_parquet(D / "session.parquet")["session_date"])
IDX = {d: i for i, d in enumerate(S)}
MUT = "--mutant-snapshot-baseline" in sys.argv
fund = json.load(open("app/public/data/sample_funnel.json"))["data"]
ivm = json.load(open("app/public/data/iv_measures.json"))["data"]

ok_snap = {(s, d) for s, d, st in zip(iv["security_id"], iv["session_date"], iv["snapshot_status"]) if st == "ok"}
usable = {(s, d) for s, d, st, c in zip(iv["security_id"], iv["session_date"], iv["snapshot_status"], iv["cm30_iv"])
          if st == "ok" and not pd.isna(c)}
base_ok = ok_snap if MUT else usable

s1 = ev
s2 = s1[~s1["exclusion_reason"].isin(["duplicate_row", "timing_ambiguous", "timing_not_checked"])]
s3 = s2[s2["sample"] == "daily"]
s4 = s3[[(s, m) in ok_snap and (s, z) in ok_snap for s, m, z in zip(s3["security_id"], s3["day_m1_session"], s3["day0_session"])]]
s5 = s4[[(s, m) in usable and (s, z) in usable for s, m, z in zip(s4["security_id"], s4["day_m1_session"], s4["day0_session"])]]

# ADR 0004 §1 baseline, own implementation
zones: dict = {}
for r in ev.itertuples(index=False):
    if r.exclusion_reason == "duplicate_row":
        continue
    if r.day0_session is not None:
        cs = [IDX[r.day0_session]]
    else:
        a = r.announce_date_used
        nxt = S[bisect_right(S, a)]
        cs = [IDX[nxt]] + ([IDX[a]] if a in IDX else [])
    zones.setdefault(r.security_id, []).extend((r.event_id, c - 21, c + 10) for c in cs)
for r in eps[eps["match_status"].isin(["orphan", "pre_calendar"])].itertuples(index=False):
    i = bisect_left(S, r.fiscal_period_end)
    if i < len(S):
        zones.setdefault(r.security_id, []).append(("orphan", i + 10, i + 60))


def baseline(r):
    c = IDX[r.day0_session]
    blocked = [(a, b) for eid, a, b in zones.get(r.security_id, []) if eid != r.event_id]
    clean = {t for t in range(c - 60, c - 21) if 0 <= t < len(S) and (r.security_id, S[t]) in base_ok
             and not any(a <= t <= b for a, b in blocked)}
    return len(clean), sum(1 for t in clean if t - 1 in clean)


s6 = s5[[(lambda n: n[0] >= 20 and n[1] >= 15)(baseline(r)) for r in s5.itertuples(index=False)]]
mine = [len(s1), len(s2), len(s3), len(s4), len(s5), len(s6)]
if len(sys.argv) > 2 and not sys.argv[2].startswith("--"):
    s6[["event_id"]].to_parquet(Path(sys.argv[2]) / "primary_ids.parquet")   # for p11c
theirs = [x["n_events"] for x in fund["steps"]]
print(f"[10] funnel recomputed {mine}; sample_funnel.json {theirs}; claimed [1353, 1320, 366, 356, 354, 348]")
gone5 = s4[~s4["event_id"].isin(s5["event_id"])]
print(f"[10] dropped at iv_usable: {list(gone5['event_id'])}")
gone6 = s5[~s5["event_id"].isin(s6["event_id"])]
print(f"[10] dropped at baseline: {[(e, baseline(r)) for e, r in zip(gone6['event_id'], gone6.itertuples(index=False))]}")
if MUT:
    print("RESULT", "FAIL (mutant gives the claimed 348)" if mine[-1] == 348 else f"falsifier distinguishes ({mine[-1]})")
    sys.exit(0 if mine[-1] != 348 else 1)

# terciles
j = ev.merge(eiv[["event_id", "abs_move_cand_max", "crush_mean_adj"]], on="event_id").merge(tc, on="event_id", how="left")
j = j[(j["exclusion_reason"] != "duplicate_row") & j["abs_move_cand_max"].notna()]
bad = 0
for row in fund["by_move_tercile"]:
    g = j[j["sample"] == row["sample"]].sort_values(["abs_move_cand_max", "event_id"])
    n = len(g)
    t = np.array([1 + (3 * r) // n for r in range(n)])
    c = g[t == row["tercile"]]
    v = c["gap_verdict_yf"].dropna()
    got = (len(c), round(c["abs_move_cand_max"].mean(), 5), round(c["crush_mean_adj"].dropna().mean(), 4),
           int(c["crush_mean_adj"].notna().sum()), round(float((v == "contradicts").mean()), 4) if len(v) else None)
    want = (row["n_events"], row["mean_abs_move"], row["mean_crush_mean_adj"], row["n_crush"], row["share_gap_contradicts"])
    if got != want:
        bad += 1
        print("  tercile mismatch", row["sample"], row["tercile"], got, want)
sizes = {s: [r["n_events"] for r in fund["by_move_tercile"] if r["sample"] == s] for s in ("daily", "mixed", "coarse")}
print(f"[10] tercile rows mismatching: {bad}; sizes {sizes}")
# ties at the tercile cut points
for s in ("daily", "mixed", "coarse"):
    g = j[j["sample"] == s]["abs_move_cand_max"]
    print(f"   {s}: duplicated abs_move_cand_max values {int(g.duplicated().sum())}")

# the 285 events without abs_move_cand_max
mm = ev.merge(eiv[["event_id", "abs_move_cand_max"]], on="event_id")
miss = mm[mm["abs_move_cand_max"].isna()]
print(f"[10] events without abs_move_cand_max: {len(miss)} by sample {miss['sample'].value_counts().to_dict()}; "
      f"of which duplicate_row {int((miss['exclusion_reason'] == 'duplicate_row').sum())}")
last = max(d for (s, d) in ok_snap)
late = miss[miss["announce_date_used"] > last]
print(f"   dated after the last ok snapshot ({last}): {len(late)} (sample none: {int((late['sample'] == 'none').sum())})")
okd = {(s, d) for (s, d) in ok_snap}


def leg_reason(sid, d):
    """Why the label-free move is missing: 'no_snapshot' if an end has no ok snapshot within one session,
    else 'no_common_forward' (both ends observed, no expiry with a forward on both)."""
    if d not in IDX:
        legs = [(S[bisect_left(S, d) - 1], S[bisect_right(S, d)])]
    else:
        legs = [(S[IDX[d] - 1], d), (d, S[IDX[d] + 1])]
    for lo, hi in legs:
        a = lo if (sid, lo) in okd else (S[IDX[lo] - 1] if (sid, S[IDX[lo] - 1]) in okd else None)
        b = hi if (sid, hi) in okd else (S[IDX[hi] + 1] if IDX[hi] + 1 < len(S) and (sid, S[IDX[hi] + 1]) in okd else None)
        if a is None or b is None:
            return "no_snapshot"
    return "no_common_forward_or_tau"


reasons = pd.Series([leg_reason(s, d) if d <= S[-2] else "beyond_table" for s, d in
                     zip(miss["security_id"], miss["announce_date_used"])], index=miss.index)
print("   reasons by sample:", miss.assign(r=reasons).groupby(["sample", "r"]).size().to_dict())

# P5 and the E <= 0 field
pe = s6.merge(eiv, on="event_id")
print(f"[11] P5: primary {len(pe)}, with E {int(pe['evar_m1'].notna().sum())}, E<=0 {int((pe['evar_m1'] <= 0).sum())}, "
      f"json {fund['evar_nonpositive']}")
# P4
mv = pe.set_index("event_id")["implied_move_m1"]
for t in ("AAPL", "MSFT"):
    x = pe[pe["security_id"] == t]["implied_move_m1"].dropna()
    print(f"[11] P4 {t}: n={len(x)} values {sorted(np.round(x * 100, 2))} median {x.median():.2%}")
pos = pe[pe["evar_m1"] > 0]["implied_move_m1"]
print(f"[11] P4 whole sample: median of sqrt(E) over E>0 ({len(pos)}) {pos.median():.2%}; "
      f"median over all {len(pe)} with E<=0 as 0: {np.median(np.where(pe['evar_m1'] > 0, np.sqrt(pe['evar_m1'].clip(lower=0)), 0)):.2%}; "
      f"sqrt(mean E) signed {math.sqrt(pe['evar_m1'].mean()):.2%}; json {ivm['implied_move']['quantiles']} "
      f"sqrt_mean_evar {ivm['implied_move']['sqrt_mean_evar']}")
cr = pe["crush_mean_adj"].dropna()
print(f"[11] crush: n={len(cr)} mean {cr.mean():.4f} median {cr.median():.4f}; json mean {ivm['crush']['mean']} q {ivm['crush']['quantiles']}")
hist = np.histogram(pos, bins=ivm["implied_move"]["bin_edges"])[0].tolist()
print(f"[11] implied-move histogram equal to json: {hist == ivm['implied_move']['counts']}")

# the leak
w = iv[(iv["snapshot_status"] == "ok") & iv["cm30_iv"].notna() & iv["cm30_blind_iv"].notna()]
far = w[w["sessions_to_next_event"].between(22, 60)]
d = (far["cm30_blind_iv"] - far["cm30_iv"]) * 100
print(f"[11] leak, sessions 22-60 before the next event: n={len(d)} mean {d.mean():+.3f} p95 {d.quantile(.95):.2f} "
      f"equal {(d.abs() < 1e-12).mean():.1%}")
near = w[w["sessions_to_next_event"].between(1, 21)]
print(f"[11] leak, sessions 1-21 before: n={len(near)} mean {((near['cm30_blind_iv'] - near['cm30_iv']) * 100).mean():+.3f}")
# the leak on the ADR 0004 baseline proper: [-60,-22] of each primary/all event, minus other zones, usable
rows = []
ivk = w.set_index(["security_id", "session_date"])
for r in ev[ev["day0_session"].notna() & (ev["exclusion_reason"] != "duplicate_row")].itertuples(index=False):
    c = IDX[r.day0_session]
    blocked = [(a, b) for eid, a, b in zones.get(r.security_id, []) if eid != r.event_id]
    for t in range(c - 60, c - 21):
        if 0 <= t < len(S) and not any(a <= t <= b for a, b in blocked) and (r.security_id, S[t]) in ivk.index:
            x = ivk.loc[(r.security_id, S[t])]
            rows.append((x["cm30_blind_iv"] - x["cm30_iv"]) * 100)
b = pd.Series(rows)
print(f"[11] leak on clean ADR 0004 baselines of all events: n={len(b)} mean {b.mean():+.3f} equal {(b.abs() < 1e-12).mean():.1%}")
