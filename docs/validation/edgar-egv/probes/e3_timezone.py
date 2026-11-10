"""E3: acceptanceDateTime is a UTC instant (trailing Z).  Exit 0 = claim survives, 1 = refuted.
Hypotheses compared against ground truth that does not come from EDGAR's timestamp:
 (a) press-release times / labels / dates (data/manual/press_release_checks.csv, 20 rows),
 (b) EDGAR's own filingDate (accepted before 17:30 NY on a weekday carries that day's filingDate),
 (c) the calendar's BMO/AMC labels over events.parquet.
The code's reading is edgar.item_202_filings()[...]['accepted'] (an aware instant) converted to New York;
the rival reading (wall clock = New York) is computed independently in _lib.wall_as_ny."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _lib import *
import pandas as pd

closes = sessions()
chk = pd.read_csv(REPO / "data/manual/press_release_checks.csv")
fails = []
print("== (a) press-release ground truth: code reading (UTC instant -> NY) vs rival (wall clock = NY)")
nA = okA_code = okA_rival = nT = okT_code = okT_rival = 0
for _, r in chk.iterrows():
    if not r["found"]:
        continue
    rd = date.fromisoformat(r["release_date"])
    fs = edgar.cached_item_202(ciks_for(r["security_id"]), RAW)
    cand = []
    for f in fs:
        code_l = f["accepted"].astimezone(NY)
        riv_l = wall_as_ny(f["accepted_utc"])
        cand.append((f, code_l, riv_l))
    # pick, for each reading separately, the filing whose local date is the release date (nearest otherwise)
    def pick(idx):
        best = min(cand, key=lambda t: abs((t[idx].date() - rd).days) * 1e6 + abs(
            (t[idx].replace(tzinfo=None) - datetime.combine(rd, time(12))).total_seconds()))
        return best
    pc, pr = pick(1), pick(2)
    row = {}
    for tag, l in (("code", pc[1]), ("rival", pr[2])):
        lab = label_indep(l, closes)
        row[tag] = (l, lab, l.date() == rd and lab == r["label"])
    nA += 1
    okA_code += row["code"][2]
    okA_rival += row["rival"][2]
    line = f"{r['security_id']:5s} release {r['release_date']} {str(r['release_time_et']):5s} {r['label']} | raw {pc[0]['accepted_utc']} | code {row['code'][0]:%m-%d %H:%M} {row['code'][1]:14s} ok={row['code'][2]} | rival {row['rival'][0]:%m-%d %H:%M} {row['rival'][1]:14s} ok={row['rival'][2]}"
    if isinstance(r["release_time_et"], str):
        hh, mm = map(int, r["release_time_et"].split(":"))
        rel = datetime.combine(rd, time(hh, mm), tzinfo=NY)
        dc = (row["code"][0] - rel).total_seconds() / 60
        dr = (row["rival"][0] - rel).total_seconds() / 60
        nT += 1
        okT_code += abs(dc) <= 60
        okT_rival += abs(dr) <= 60
        line += f" | delta_min code {dc:+.0f} rival {dr:+.0f}"
    print(line)
print(f"label+date agreement: code {okA_code}/{nA}, rival {okA_rival}/{nA}")
print(f"time-stamped rows within +-60 min of the release stamp: code {okT_code}/{nT}, rival {okT_rival}/{nT}")
if okA_code != nA: fails.append("(a) code reading disagrees with a press-release label/date")
if okT_code != nT: fails.append("(a) code reading is >60 min from a release stamp")

print("== (b) EDGAR filingDate consistency (8-K, weekday, 17:30 NY cut-off)")
rc = filingdate_consistency(lambda s: edgar.parse_acceptance(s).astimezone(NY))
rv = filingdate_consistency(wall_as_ny)
for tag, x in (("code ", rc), ("rival", rv)):
    print(f"{tag}: before-17:30 same-day {x['before_ok']}/{x['before_n']} ({x['before_rate']:.4f}); "
          f"at/after-17:30 later-day {x['after_ok']}/{x['after_n']} ({x['after_rate']:.4f}); violations {len(x['violations'])}")
if rc["before_rate"] < 0.995 or rc["after_rate"] < 0.85: fails.append("(b) filingDate cut-off consistency below 0.995/0.85")

print("== (c) calendar labels: events with timing_raw in BMO/AMC and exactly one Item 2.02 8-K on announce_date")
ev = pd.read_parquet(REPO / "data/derived/events.parquet")
ev = ev[ev["timing_raw"].isin(["BMO", "AMC"])]
cache = {}
n = a_code = a_riv = 0
for _, e in ev.iterrows():
    sid = e["security_id"]
    if sid not in cache:
        try:
            cache[sid] = edgar.cached_item_202(ciks_for(sid), RAW)
        except FileNotFoundError:
            cache[sid] = []
    ad = e["announce_date"]
    ad = ad if isinstance(ad, date) and not isinstance(ad, datetime) else pd.Timestamp(ad).date()
    hc = [f for f in cache[sid] if f["accepted"].astimezone(NY).date() == ad]
    hr = [f for f in cache[sid] if wall_as_ny(f["accepted_utc"]).date() == ad]
    if len(hc) != 1 or len(hr) != 1:
        continue
    n += 1
    a_code += label_indep(hc[0]["accepted"].astimezone(NY), closes) == e["timing_raw"]
    a_riv += label_indep(wall_as_ny(hr[0]["accepted_utc"]), closes) == e["timing_raw"]
print(f"events compared {n}; label agreement code {a_code}/{n} ({a_code/n:.4f}); rival {a_riv}/{n} ({a_riv/n:.4f})")
if not (n > 500 and a_code / n >= 0.9 and a_code > a_riv): fails.append("(c) calendar-label agreement")

print("RESULT:", "SURVIVES" if not fails else "REFUTED: " + "; ".join(fails))
sys.exit(0 if not fails else 1)
