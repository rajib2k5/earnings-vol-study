"""d11: is the simulated H4 statistic (one-session change of the daily ln sigma_d series at day 0) the real DSIGMA_D
(event_iv: the same expiry pair on both days)? Mean-adjusted values only; aggregates. Stage cache only.
Run: uv run --frozen --no-sync python docs/validation/probes/m3-delta/d11_dsigma_series.py
"""
import numpy as np
from earnings_vol import params as P
from earnings_vol.stats import run, inputs
from earnings_vol.panel import abnormal
p=P.load(); f=run.load(p)
rows=inputs.event_set(f,"dsigma_d","daily")
real=f.ev["dsigma_d_mean_adj"].to_numpy(float)[rows]
sd=f.sigma_d[rows]
ser=np.log(sd[:,abnormal.col(0)])-np.log(sd[:,abnormal.col(-1)])
ok=np.isfinite(real)&np.isfinite(ser)
d=np.abs(real[ok]-ser[ok])
print(f"H4 events {rows.size}; both finite {ok.sum()}; |DSIGMA_D - series change|: equal (<1e-9) {(d<1e-9).sum()}, median {np.median(d):.4f}, 90th pct {np.quantile(d,0.9):.4f}, corr {np.corrcoef(real[ok],ser[ok])[0,1]:.3f}; sd real {real[ok].std():.4f} sd series {ser[ok].std():.4f}")
