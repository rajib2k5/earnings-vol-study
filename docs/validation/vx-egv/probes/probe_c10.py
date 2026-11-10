"""C10 probe: pooled bootstrap statistics resample the SAME dates for all names in each repetition.
usage: probe_c10.py <path-to-tools/vx_crosscheck.py>   exit 0 = claim survived.
Reference (from the claim): in repetition r the date multiset is one row of the count matrix; every name's observation dated d is
repeated count[r,d] times; pooled r/slope are computed on the stacked repeated observations."""
import sys, importlib.util, numpy as np, pandas as pd
sys.path.insert(0, '/home/rajib2k5/dev/earnings-vol-study/src')
from earnings_vol.stats import vx_crosscheck as vx
spec = importlib.util.spec_from_file_location('vxtool_under_test', sys.argv[1]); t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
rng = np.random.default_rng(5); n, w0, reps = 30, 100, 60
C = vx.block_counts(n, 5, reps, np.random.default_rng(11))
names = {}
for k, nm in enumerate(['A', 'B', 'C']):
    pos = np.sort(rng.choice(n, size=18 + 3 * k, replace=False)) + w0   # different dates per name; 'end' = w0 + position
    x = rng.normal(size=len(pos)); y = (0.5 + k) * x + rng.normal(scale=0.5 + k, size=len(pos))
    names[nm] = pd.DataFrame({'end': pos, 'd_ours': x, 'd_vx': y})
out = t.bar_i_ii(names, w0, n, {20: C})['pooled']['block20']
rs, sl = [], []
for r in range(reps):
    xs, ys = [], []
    for df in names.values():
        p = df['end'].to_numpy() - w0; rep = C[r][p]
        xs.append(np.repeat(df['d_ours'].to_numpy(), rep)); ys.append(np.repeat(df['d_vx'].to_numpy(), rep))
    X, Y = np.concatenate(xs), np.concatenate(ys)
    rs.append(np.corrcoef(X, Y)[0, 1]); sl.append(np.cov(X, Y, bias=True)[0, 1] / np.var(X))
def ci(v): lo, hi = np.percentile(v, (2.5, 97.5)); return round(float(lo), 4), round(float(hi), 4)
want_r, want_s = ci(rs), ci(sl)
got_r, got_s = (out['r']['lo'], out['r']['hi']), (out['slope']['lo'], out['slope']['hi'])
print('pooled r CI   got', got_r, 'want', want_r); print('pooled slope CI got', got_s, 'want', want_s)
ok = np.allclose(got_r, want_r, atol=1.5e-4) and np.allclose(got_s, want_s, atol=1.5e-4)
# discrimination: an independent-draw pooled reference must differ from the same-date reference (probe has power)
rs2 = []
for r in range(reps):
    xs, ys = [], []
    for k, df in enumerate(names.values()):
        p = df['end'].to_numpy() - w0; rep = C[(r + 7 * (k + 1)) % reps][p]
        xs.append(np.repeat(df['d_ours'].to_numpy(), rep)); ys.append(np.repeat(df['d_vx'].to_numpy(), rep))
    rs2.append(np.corrcoef(np.concatenate(xs), np.concatenate(ys))[0, 1])
print('independent-draw reference r CI (must differ from want):', ci(rs2))
power = ci(rs2) != want_r
print('PASS' if ok and power else 'FAIL', 'match=', ok, 'power=', power); sys.exit(0 if ok and power else 1)
