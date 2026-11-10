"""E2: older filings are listed in filings.files, each page with the same arrays.  Exit 0 = survives.
Raw checks on every page file in the cache; completeness check; and an outcome check through the code: calendar events
dated before a company's `recent` block begins must still find their Item 2.02 8-K (they exist only in the pages)."""
import sys, os, glob, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _lib import *
import pandas as pd

fails = []
mains = sorted(p for p in glob.glob(str(EDG / "CIK*.json")) if re.fullmatch(r"CIK\d{10}\.json", os.path.basename(p)))
pages_on_disk = sorted(os.path.basename(p) for p in glob.glob(str(EDG / "CIK*-submissions-*.json")))
listed_all, listed_with_content = 0, 0
overlap = []
for p in mains:
    d = json.load(open(p))
    rec = d["filings"]["recent"]
    rmin = min(rec["filingDate"])
    for f in d["filings"].get("files", []):
        listed_all += 1
        fp = EDG / f["name"]
        if fp.exists():
            listed_with_content += 1
            pg = json.load(open(fp))
            if set(pg) != set(rec):
                fails.append((f["name"], "page key set != recent key set", sorted(set(pg) ^ set(rec))))
            n = {len(pg[k]) for k in pg}
            if len(n) != 1 or n != {f["filingCount"]}:
                fails.append((f["name"], "ragged or count != listed filingCount", sorted(n), f["filingCount"]))
            if min(pg["filingDate"]) != f["filingFrom"]:
                fails.append((f["name"], "filingFrom mismatch"))
            overlap.append((max(pg["filingDate"]) - 0 if False else (date.fromisoformat(max(pg["filingDate"])) - date.fromisoformat(rmin)).days))
        else:
            # not cached: must be a page the code deliberately skipped (older than SINCE - margin)
            if date.fromisoformat(f["filingTo"]) >= edgar.SINCE - timedelta(days=edgar.PAGE_MARGIN_DAYS):
                fails.append((f["name"], "needed page missing from cache", f["filingTo"]))
extra = set(pages_on_disk) - {f["name"] for p in mains for f in json.load(open(p))["filings"].get("files", [])}
if extra: fails.append(("pages on disk not listed by any main file", sorted(extra)[:3]))
print(f"pages listed {listed_all}; cached {listed_with_content}; on disk {len(pages_on_disk)}")
print(f"newest filing of each cached page minus its CIK's oldest `recent` filing (days): min {min(overlap)} max {max(overlap)} (<=0 means page is entirely older)")
# outcome check through the code
ev = pd.read_parquet(REPO / "data/derived/events.parquet")
firsts = {}
for sid, v in SECS.items():
    if " (" in sid: continue
    firsts[sid] = v["recent_first_filing_date"]
n = hit = 0
nopage_hit = 0
for _, e in ev.iterrows():
    sid = e["security_id"]
    if sid not in firsts or not firsts[sid] or SECS[sid]["pages_used"] == 0: continue
    ad = pd.Timestamp(e["announce_date"]).date()
    if ad >= date.fromisoformat(firsts[sid]): continue
    n += 1
    fs = edgar.cached_item_202(ciks_for(sid), RAW)
    hit += any(abs((f["accepted"].astimezone(NY).date() - ad).days) <= 1 for f in fs)
print(f"events dated before their `recent` block starts: {n}; with an Item 2.02 8-K within +-1 day via the code: {hit}")
if n < 50 or hit / max(n, 1) < 0.9: fails.append(("events older than `recent` not found", n, hit))
for f in fails: print("FAIL", f)
print("RESULT:", "SURVIVES" if not fails else "REFUTED")
sys.exit(0 if not fails else 1)
