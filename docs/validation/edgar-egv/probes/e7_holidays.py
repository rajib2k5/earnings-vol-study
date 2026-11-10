"""E7: EDGAR accepts nothing on Columbus Day and Veterans Day although NYSE is open.  Exit 0 = survives.
Dates are derived here from the federal calendar rule (second Monday of October; 11 Nov, Fri if Sat, Mon if Sun), not from
the code.  For each, NYSE must have a session (data/derived/session.parquet) and EDGAR must have zero acceptances (all
forms, all cached CIKs, NY date and UTC date) while ordinary sessions are busy.  Finally edgar_holidays() must contain
each date.  Days after the last cached acceptance are reported as not testable."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _lib import *

closes = sessions()
ny_dates, utc_dates, fil_dates = collections.Counter(), collections.Counter(), collections.Counter()
import glob, re
files = sorted(p for p in glob.glob(str(EDG / "CIK*.json")) if "submissions" not in os.path.basename(p) or True)
for p in files:
    if os.path.basename(p) == "fetch_log.json": continue
    d = json.load(open(p))
    blk = d["filings"]["recent"] if "filings" in d else d
    for at, fd in zip(blk["acceptanceDateTime"], blk["filingDate"]):
        inst = datetime.strptime(at, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)
        ny_dates[inst.astimezone(NY).date()] += 1
        utc_dates[inst.date()] += 1
        fil_dates[fd] += 1
last = max(ny_dates)
first_full = date(2020, 1, 2)
print("cached acceptances span", min(ny_dates), "..", last, "; total", sum(ny_dates.values()))
targets = []
for y in range(2020, 2027):
    o = date(y, 10, 1)
    col = o + timedelta(days=(7 - o.weekday()) % 7 + 7)
    vet = date(y, 11, 11)
    vet = vet - timedelta(days=1) if vet.weekday() == 5 else vet + timedelta(days=1) if vet.weekday() == 6 else vet
    targets += [("Columbus", col), ("Veterans", vet)]
fails = []
tested = 0
for name, d in targets:
    if d > last:
        print(f"{name} {d}: after the last cached acceptance, not testable"); continue
    nyse = d in closes
    c = (ny_dates[d], utc_dates[d], fil_dates[d.isoformat()])
    in_code = d in edgar.edgar_holidays(d.year)
    print(f"{name:9s} {d} {d:%a} NYSE session={nyse} acceptances(NY date, UTC date, filingDate)={c} in edgar_holidays={in_code}")
    tested += 1
    # UTC date is reported only: a UTC date of 11 Nov holds the evening of 10 Nov in New York, which is not an acceptance on the 11th
    if not nyse or c[0] or c[2] or not in_code: fails.append((name, str(d)))
# control: ordinary sessions in the same window are busy
ords = [ny_dates[d] for d in closes if first_full <= d <= last and d not in {t for _, t in targets}]
zero_other = [d for d in closes if first_full <= d <= last and ny_dates[d] == 0 and d not in {t for _, t in targets}]
print(f"control: {len(ords)} other sessions, min acceptances {min(ords)}, median {sorted(ords)[len(ords)//2]}; sessions with zero acceptances (other than targets): {zero_other}")
if tested < 10 or min(ords) < 0: fails.append("too few testable days")
print("RESULT:", "SURVIVES" if not fails else "REFUTED: " + "; ".join(map(str, fails)))
sys.exit(0 if not fails else 1)
