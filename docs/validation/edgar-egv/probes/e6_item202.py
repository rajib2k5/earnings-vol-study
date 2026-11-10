"""E6 (empirical half): Item 2.02 is the item under which companies furnish earnings releases.  Exit 0 = survives.
(i) all 20 press-release ground-truth releases: an 8-K accepted on the release date has 2.02 in its items (raw census);
(ii) over all calendar events, an Item 2.02 8-K (via the code) lies within +-1 day of the announce date far more often
than at a placebo date 45 days later.  The wording of the item's title cannot be probed from the cache."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _lib import *
import pandas as pd

fails = []
rows = [r for r in all_8k_rows() if r[2] == "8-K"]
chk = pd.read_csv(REPO / "data/manual/press_release_checks.csv")
ok = 0
for _, c in chk.iterrows():
    rd = date.fromisoformat(c["release_date"])
    ciks = set(ciks_for(c["security_id"]))
    day = [r for r in rows if r[0] in {k for k in SECS if k == c["security_id"] or k.startswith(c["security_id"] + " (")}
           and edgar.parse_acceptance(r[4]).astimezone(NY).date() == rd]
    has = any("2.02" in r[3].split(",") for r in day)
    ok += has
    print(f"{c['security_id']:5s} {c['release_date']} 8-Ks that day: {[r[3] for r in day]}  has 2.02: {has}")
print(f"ground-truth releases with a 2.02 8-K on the release date: {ok}/{len(chk)}")
if ok != len(chk): fails.append("a ground-truth release has no 2.02 8-K that day")
ev = pd.read_parquet(REPO / "data/derived/events.parquet")
cache, real, plc, n = {}, 0, 0, 0
for _, e in ev.iterrows():
    sid = e["security_id"]
    if sid not in cache:
        cache[sid] = [f["accepted"].astimezone(NY).date() for f in edgar.cached_item_202(ciks_for(sid), RAW)]
    ad = pd.Timestamp(e["announce_date"]).date()
    n += 1
    real += any(abs((d - ad).days) <= 1 for d in cache[sid])
    pd45 = ad + timedelta(days=45)
    plc += any(abs((d - pd45).days) <= 1 for d in cache[sid])
print(f"events {n}: Item 2.02 8-K within +-1 day of announce_date {real} ({real/n:.4f}); at announce_date+45d (placebo) {plc} ({plc/n:.4f})")
if not (real / n >= 0.95 and plc / n <= 0.20): fails.append("event vs placebo contrast")
print("RESULT:", "SURVIVES" if not fails else "REFUTED: " + "; ".join(fails))
sys.exit(0 if not fails else 1)
