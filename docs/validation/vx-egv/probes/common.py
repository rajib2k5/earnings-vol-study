import os, sys, numpy as np, pandas as pd
from datetime import date
RAW = '/home/rajib2k5/data/vol-projects/earnings-vol-study/raw/cboe/'
VX = {"AAPL": "VXAPL", "AMZN": "VXAZN", "GOOGL": "VXGOG", "GS": "VXGS", "IBM": "VXIBM"}
R = '/home/rajib2k5/dev/earnings-vol-study/'
def sessions():
    s = pd.read_parquet(R + 'data/derived/session.parquet')
    return [d for d in s['session_date']]
def load(mode='normal'):
    """mode: dmy (mis-read dates) | normal | nodiv (CLOSE not /100) | shift (Cboe dates moved one session later)."""
    ses = sessions(); pos = {d: i for i, d in enumerate(ses)}
    iv = pd.read_parquet(R + 'data/derived/iv_daily.parquet')
    out = {}
    for nm, sym in VX.items():
        c = pd.read_csv(RAW + sym + '.csv')
        c['d'] = (pd.to_datetime(c['DATE'], format='%d/%m/%Y', errors='coerce') if mode == 'dmy' else pd.to_datetime(c['DATE'], format='%m/%d/%Y')).dt.date
        v = c['CLOSE'].astype(float) / (1.0 if mode == 'nodiv' else 100.0)
        g = np.full(len(ses), np.nan)
        for d, x in zip(c['d'], v):
            if d in pos:
                i = pos[d] + (1 if mode == 'shift' else 0)
                if i < len(ses): g[i] = x
        sub = iv[iv.security_id == nm].set_index('session_date')
        a = np.full(len(ses), np.nan); f = np.full(len(ses), np.nan)
        for d, x, y in zip(sub.index, sub['cm30_blind_iv'], sub['front_atm_iv']):
            a[pos[d]] = x; f[pos[d]] = y
        out[nm] = dict(vx=g, blind=a, front=f, sub=sub, ses=ses)
    return out
def chg_corr(x, y, lag=0):
    """corr of daily ln changes of x and of y shifted by lag (y[i+lag]); only consecutive-session pairs."""
    n = len(x); yy = np.full(n, np.nan)
    if lag == 0: yy[:] = y
    elif lag > 0: yy[:-lag] = y[lag:]
    else: yy[-lag:] = y[:lag]
    ok = np.isfinite(x) & np.isfinite(yy) & (x > 0) & (yy > 0)
    ok2 = ok[1:] & ok[:-1]
    dx = np.diff(np.log(np.where(ok, x, 1)))[ok2]; dy = np.diff(np.log(np.where(ok, yy, 1)))[ok2]
    return np.corrcoef(dx, dy)[0, 1], int(ok2.sum()), dx, dy
