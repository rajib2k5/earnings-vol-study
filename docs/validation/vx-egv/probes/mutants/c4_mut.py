import json, hashlib, pandas as pd, sys
R='/home/rajib2k5/data/vol-projects/earnings-vol-study/raw/cboe/'; fail=[]
log=json.load(open(R+'fetch_log.json'))
for s in ['VXAPL','VXAZN','VXGOG','VXGS','VXIBM']:
    b=open(R+s+'.csv','rb').read(); c=pd.read_csv(R+s+'.csv'); L=log[s]
    d=pd.to_datetime(c['DATE'],format='%m/%d/%Y')
    ok = ('SETTLE' in c.columns and len(c)==L['rows'] and hashlib.sha256(b).hexdigest()==L['sha256'] and L['final_url'].endswith(f'/daily_prices/{s}_History.csv')
          and d.is_monotonic_increasing and d.is_unique and (d.diff().dt.days.dropna().median()<=1) and c['CLOSE'].notna().all() and (c['CLOSE']>0).all())
    print(s,'cols',list(c.columns),'rows',len(c),'first',d.iloc[0].date(),'last',d.iloc[-1].date(),'median day gap',d.diff().dt.days.median(),'sha ok',hashlib.sha256(b).hexdigest()==L['sha256'],'hops',L['hops'],'final_url',L['final_url'],'->',ok)
    if not ok: fail.append(s)
print('FAIL' if fail else 'PASS',fail); sys.exit(1 if fail else 0)
