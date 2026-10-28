import json, numpy as np, collections
from pathlib import Path
CAL = Path(__file__).resolve().parents[2] / 'data' / 'derived' / 'earnings_calendar_30_large_caps.json'
rows = json.load(open(CAL))['rows']
hol = ['2024-01-01','2024-01-15','2024-02-19','2024-03-29','2024-05-27','2024-06-19','2024-07-04','2024-09-02','2024-11-28','2024-12-25',
 '2025-01-01','2025-01-09','2025-01-20','2025-02-17','2025-04-18','2025-05-26','2025-06-19','2025-07-04','2025-09-01','2025-11-27','2025-12-25',
 '2026-01-01','2026-01-19','2026-02-16','2026-04-03','2026-05-25','2026-06-19','2026-07-03','2026-09-07','2026-11-26','2026-12-25']
cal = np.busdaycalendar(holidays=hol)
def day0(d, when):
    d = np.datetime64(d)
    # ADR 0002 §2. A non-session D maps to the first session after it, whatever the label (fixed after the review: the
    # first version added one more session for AMC; no row of the extract has a non-session D, so output is unchanged).
    if when == 'After market close' and np.is_busday(d, busdaycal=cal): return np.busday_offset(d, 1, busdaycal=cal)
    return np.busday_offset(d, 0, roll='forward', busdaycal=cal)
by = collections.defaultdict(list)
for r in rows: by[r['act_symbol']].append(day0(r['date'], r['when']))
gaps = []
for s, ds in by.items():
    ds = sorted(ds)
    for a, b in zip(ds, ds[1:]): gaps.append(int(np.busday_count(a, b, busdaycal=cal)))
g = np.array(gaps)
print("n gaps", len(g), "min", g.min(), "p5", np.percentile(g,5), "p25", np.percentile(g,25), "median", np.median(g), "p75", np.percentile(g,75), "max", g.max())
# A fixed [-60,-20] baseline sits at [g-60, g-20] relative to the previous report's day 0 (g = gap in sessions).
# Revised after the milestone-0 review (ledger claim 5): the second share is the OVERLAP with the previous [0,+10]
# window, not "day -60 inside it" (that share is P(60 <= g <= 70) = 0.833).
print("share gap<=60 (fixed [-60,-20] baseline contains prev day 0):", np.mean(g<=60).round(3))
print("share gap<=70 (fixed [-60,-20] baseline overlaps prev [0,+10]):", np.mean(g<=70).round(3))
print("share 60<=gap<=70 (day -60 itself inside prev [0,+10]):", np.mean((g>=60)&(g<=70)).round(3))
# clean baseline sessions in [-60,-22] after excluding prev event's [-21,+10] (and anything before prev day0 within its window)
def clean(gap, lo=-60, hi=-22, ex_lo=-21, ex_hi=10):
    days = np.arange(lo, hi+1)
    prev_rel = days + gap            # position relative to previous event's day0
    bad = (prev_rel >= ex_lo) & (prev_rel <= ex_hi)
    return (~bad).sum()
c = np.array([clean(x) for x in g])
print("clean baseline sessions: min", c.min(), "p5", np.percentile(c,5), "median", np.median(c), "share >=20:", np.mean(c>=20).round(3))
c5 = np.array([clean(x, ex_hi=5) for x in g]); print("if exclude only to +5: median", np.median(c5), "share>=20", np.mean(c5>=20).round(3))
print("small gaps:", sorted(g)[:8])
