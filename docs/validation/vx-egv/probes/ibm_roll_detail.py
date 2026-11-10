import sys; sys.path.insert(0,'/home/rajib2k5/dev/earnings-vol-study/docs/validation/vx-egv/probes')
from common import *; import datetime as dt
D=load(); d=D['IBM']; ses=d['ses']; pos={x:i for i,x in enumerate(ses)}
sub=d['sub']; pi=np.array([pos[x] for x in sub.index])
def tf(y,m):
    d1=dt.date(y,m,1); f=d1+dt.timedelta(days=(4-d1.weekday())%7); return f+dt.timedelta(days=14)
T={tf(y,m) for y in range(2020,2027) for m in range(1,13)}
lv=np.log(d['vx']); dv=np.r_[np.nan,np.diff(lv)]
lb=np.log(d['blind']); db=np.r_[np.nan,np.diff(lb)]
sp=sub['sessions_since_prev_event'].values; sn=sub['sessions_to_next_event'].values
rows=[]
for i,p in enumerate(pi):
    if i>0 and ses[p-1] in T and not(sp[i]<=3 or sn[i]<=3): rows.append((str(ses[p]),dv[p],db[p],sp[i],sn[i]))
rows.sort(key=lambda r:-abs(r[1]))
# aggregates only: no per-day Cboe value is printed (they are licensed data and stay out of the repository)
a=np.array([abs(r[1]) for r in rows]); print('median|dVX| roll',np.nanmedian(a),'n',len(a))
print('roll days with |dVX| > 0.1:',int((a>0.1).sum()),'of',len(a))
allp=np.array([abs(dv[p]) for i,p in enumerate(pi) if not(sp[i]<=3 or sn[i]<=3)]); print('median|dVX| clean all',np.nanmedian(allp))
