"""d12: committed per-event values against the stage's VIX-adjusted columns (delta claim 9). Counts and max diffs only.
The exact 4-dp scan at the end is NOT diagnostic (collisions; see the control line).
Run: uv run --frozen --no-sync python docs/validation/probes/m3-delta/d12_per_event.py
"""
import json, numpy as np, pandas as pd
SD="/home/rajib2k5/data/vol-projects/earnings-vol-study/cache/stage/94065662cd46610c/"
ewo=pd.read_parquet(SD+"event_window_obs.parquet")
d=json.load(open('app/public/data/event_paths.json'))['data']
w=ewo[ewo.rel_day.between(-10,10)].set_index(['event_id','rel_day'])
dm=dc=0; n=0
for e in d['per_event']:
    for rd,v in zip(d['rel_days'], e['values']):
        if v is None: continue
        r=w.loc[(e['event_id'],rd)]
        n+=1
        dm=max(dm,abs(v-r['aliv_mean_adj'])); dc=max(dc,abs(v-r['aliv_cboe']) if np.isfinite(r['aliv_cboe']) else 0)
print(f"event_paths per-event values {n}: max |v - aliv_mean_adj| {dm:.2e}; max |v - aliv_cboe| {dc:.3f} (large = not the VIX-adjusted value)")
for fn in ("event_window_obs","event_measures","results"):
    cols=pd.read_parquet(f"data/derived/{fn}.parquet").columns
    print(fn, "cboe/beta/vix columns:", [c for c in cols if 'cboe' in c or 'beta' in c or 'vix' in c])
vals=set()
em=pd.read_parquet(SD+"event_measures.parquet")
for c in [c for c in em.columns if c.endswith('_cboe')]:
    vals |= set(np.round(em[c].dropna().to_numpy(float),4).tolist())
ctl=set(np.round(em['crush_mean_adj'].dropna().to_numpy(float),4).tolist())
def nums(o,out):
    if isinstance(o,dict): [nums(v,out) for v in o.values()]
    elif isinstance(o,list): [nums(v,out) for v in o]
    elif isinstance(o,float): out.append(round(o,4))
for fn in ("tests","event_paths","terrain","heatmap"):
    out=[]; nums(json.load(open(f"app/public/data/{fn}.json"))['data'],out)
    s=set(out)
    print(f"{fn}.json: {len(s)} distinct 4-dp numbers; equal to some per-event *_cboe/beta value: {len(s&vals)}; control (equal to some crush_mean_adj): {len(s&ctl)}")
