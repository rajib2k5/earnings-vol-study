"""d09: are §6.5's named company firm-term values (RUNUP: TSLA, NFLX, CSCO) VIX-adjusted per-company aggregates?
Prints only |doc - computed| for the market- and the mean-adjusted computation (no value itself). Stage cache only.
Run: uv run --frozen --no-sync python docs/validation/probes/m3-delta/d09_firm_term.py
"""
import numpy as np, pandas as pd
from earnings_vol import params as P
from earnings_vol.stats import run, inputs
p=P.load(); f=run.load(p)
doc={"TSLA":-1.46,"NFLX":1.38,"CSCO":1.24}
rows=inputs.event_set(f,"runup","daily")
for adj in ("market","mean"):
    A=inputs.values(f,rows,"runup",adj); ok=np.isfinite(A); r=rows[ok]; A=A[ok]
    firm=f.ev["security_id"].to_numpy(object)[r]
    sym=f.ev["ticker"].to_numpy(object)[r] if "ticker" in f.ev else firm
    u=pd.Series(A-A.mean()).groupby(sym).sum()
    share=float((u**2)[list(doc)].sum()/(u**2).sum())
    print(adj, {k: round(abs(doc[k]-float(u.get(k,np.nan))),3) for k in doc}, "share of firm term", round(share,3))
