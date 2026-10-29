"""d06: withheld rows vs G1's calibrated rates (delta claim 5). Stage g1_report.json + committed files; aggregates.
Run: uv run --frozen --no-sync python docs/validation/probes/m3-delta/d06_withhold.py
"""
import json, pandas as pd
rep=json.load(open('/home/rajib2k5/data/vol-projects/earnings-vol-study/cache/stage/94065662cd46610c/g1_report.json'))
hi=rep['band'][1]
cal=rep['rates']['calibrated']
over=set()
for h,r in cal.items():
    for k,v in r.items():
        if k.startswith('_'): continue
        tag = 'PRIMARY' if k==r['_primary'] else ''
        if v>hi and k!=r['_primary'] and k!='date_cluster_t': over.add((h,k))
        print(f"g1 {h} {k:22s} {100*v:6.2f}% {tag}{' OVER' if v>hi else ''}")
R=pd.read_parquet('data/derived/results.parquet')
E=R[R.family=='event_test']
nullp=E[E.p_value.isna()]
print('event_test rows', len(E), '; with null p', len(nullp))
for r in nullp.itertuples():
    print(f"  null p: {r.hypothesis} {r.role} {r.statistic} {r.adjustment} {r.sample} {r.subgroup_value} est_notna={pd.notna(r.estimate)} se_notna={pd.notna(r.se)} stat_notna={pd.notna(r.stat)} ci_null={pd.isna(r.ci_lo) and pd.isna(r.ci_hi)}")
withheld={(r.hypothesis,r.statistic) for r in nullp.itertuples() if r.role=='robustness'}
print('withheld == oversized set:', withheld==over, 'sizes', len(withheld), len(over))
print('primary rows with null p:', int(E[(E.role=='primary')].p_value.isna().sum()), 'of', int((E.role=='primary').sum()))
for h,k in sorted(over):
    other=E[(E.statistic==k)&(E.p_value.notna())]
    if len(other): print('  statistic', k, 'keeps a p in', len(other), 'other rows:', sorted(set(zip(other.hypothesis.fillna('-'),other['sample'],other.adjustment,other.subgroup_value))))
T=json.load(open('app/public/data/tests.json'))['data']['rows']
g1s={(r['hypothesis'],r['statistic']):r['g1_size'] for r in T if r['g1_size'] is not None}
print('tests.json g1_size rows', len(g1s), 'match G1 rates:', all(abs(v-cal[h][k])<5e-5 for (h,k),v in g1s.items()), 'keys equal:', set(g1s)==over)
