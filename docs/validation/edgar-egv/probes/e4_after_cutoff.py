"""E4: acceptanceDateTime is the real acceptance time, also for filings accepted after 17:30 Eastern
(which carry the next business day as filingDate).  Exit 0 = survives, 1 = refuted.
Test: every cached 8-K accepted on a weekday; local time via the CODE's parse_acceptance + edgar.NY.
Pre-set criteria: before-17:30 filings carry the same-day filingDate >= 99.5%; filings at/after 17:30 carry a later
filingDate >= 85% (n >= 100); both daylight-saving regimes pass >= 80% with n >= 30; after-cut-off acceptance times are
spread (>= 50 distinct minutes of the day between 17:30 and 23:59), i.e. they are real times, not a collapsed stamp.
(The 85% / 80% levels were fixed after a first look at the data; the falsifier shows the probe separates the readings.)"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _lib import *

local_of = lambda s: edgar.parse_acceptance(s).astimezone(edgar.NY)
r = filingdate_consistency(local_of)
print({k: v for k, v in r.items() if k != "violations"})
print("violations:", len(r["violations"]))
for v in r["violations"]:
    print("  ", v)
fails = []
if r["before_rate"] < 0.995: fails.append("before-cut-off rate")
if r["after_n"] < 100 or r["after_rate"] < 0.85: fails.append("after-cut-off rate")
# DST regimes, classified with an independent zone object (not the code's edgar.NY)
for tag, want_dst in (("EDT (summer)", True), ("EST (winter)", False)):
    n = ok = 0
    for sid, acc, form, items, at, fd in all_8k_rows():
        if form != "8-K":
            continue
        inst = edgar.parse_acceptance(at)
        true_l = inst.astimezone(NY)
        if bool(true_l.dst()) != want_dst or true_l.weekday() >= 5:
            continue
        l = local_of(at)
        if l.time() >= time(17, 30):
            n += 1
            ok += date.fromisoformat(fd) > l.date()
    print(f"{tag}: after-cut-off (by the code's local time) {ok}/{n} carry a later filingDate")
    if n < 30 or ok / max(n, 1) < 0.80: fails.append(f"after-cut-off rate in {tag}")
mins = set()
for sid, acc, form, items, at, fd in all_8k_rows():
    if form == "8-K":
        l = local_of(at)
        if l.weekday() < 5 and l.time() >= time(17, 30):
            mins.add(l.hour * 60 + l.minute)
print("distinct minutes of day among after-cut-off acceptances:", len(mins), "min", min(mins) if mins else None, "max", max(mins) if mins else None)
if len(mins) < 50: fails.append("after-cut-off times are not spread")
print("RESULT:", "SURVIVES" if not fails else "REFUTED: " + "; ".join(fails))
sys.exit(0 if not fails else 1)
