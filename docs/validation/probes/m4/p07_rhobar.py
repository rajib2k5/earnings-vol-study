"""p07 (claim 7): own rho-bar, top-10 removal, positive share and LOO-factor residual rho-bar from the same z
(inputs.robust_inputs), own code; then the mechanics: the same LOO residualisation applied to z with NO
cross-sectional dependence (iid N(0,1) in the real missingness pattern) and to a pure common factor plus noise.
Aggregates only. Run: uv run --frozen --no-sync python docs/validation/probes/m4/p07_rhobar.py"""
import numpy as np

from earnings_vol import params
from earnings_vol.stats import inputs, run

p = params.load()
f = run.load(p)
rows = run.primary_sets(f)[0]["H1"]
z = inputs.robust_inputs(f, rows, "crush")["z"]
firm = f.ev["security_id"].to_numpy(object)[rows]
sector = f.ev["gics_sector"].to_numpy(object)[rows]


def rb(z):
    ok = np.isfinite(z)
    s = np.where(ok, z, 0).sum(0)
    s2 = (np.where(ok, z, 0) ** 2).sum(0)
    n = ok.sum(0)
    return ((s ** 2 - s2).sum() / (n * (n - 1)).sum()), s ** 2 - s2, n * (n - 1)


def loo_resid(z, groups=None):
    ok = np.isfinite(z)
    zz = np.where(ok, z, 0)
    grp = np.zeros(len(firm), int) if groups is None else np.unique(groups.astype(str), return_inverse=True)[1]
    fac = np.full(z.shape, np.nan)
    for i in range(z.shape[0]):
        others = (firm != firm[i]) & (grp == grp[i])
        n = ok[others].sum(0)
        with np.errstate(invalid="ignore", divide="ignore"):
            fac[i] = np.where(ok[i] & (n > 0), zz[others].sum(0) / n, np.nan)
    res = np.full(z.shape, np.nan)
    for fm in set(firm):
        r = firm == fm
        both = np.isfinite(z[r]) & np.isfinite(fac[r])
        b = (z[r][both] * fac[r][both]).sum() / (fac[r][both] ** 2).sum()
        res[r] = np.where(both, z[r] - b * fac[r], np.nan)
    ms = np.sqrt(np.nanmean(res ** 2, axis=1))
    return res / ms[:, None]


r0, cross, pairs = rb(z)
use = pairs > 0
print(f"own rho-bar {r0:.4f}; dates with >= 2 events {use.sum()}; positive share {(cross[use] > 0).mean():.3f}")
o = np.argsort(-cross)
print(f"top 10 share of cross-product {cross[o[:10]].sum() / cross.sum():.3f}; without top 10 "
      f"{(cross.sum() - cross[o[:10]].sum()) / (pairs.sum() - pairs[o[:10]].sum()):.4f}")
print(f"own LOO all-firm residual rho-bar {rb(loo_resid(z))[0]:.4f}; sector LOO {rb(loo_resid(z, sector))[0]:.4f}")
rng = np.random.default_rng(7)
mask = np.isfinite(z)
iid = [rb(loo_resid(np.where(mask, rng.standard_normal(z.shape), np.nan)))[0] for _ in range(5)]
print("mechanics: iid z (no dependence), real missingness: raw rho-bar ~0; after the all-firm LOO residualisation: "
      + ", ".join(f"{v:.4f}" for v in iid))
iid_s = [rb(loo_resid(np.where(mask, rng.standard_normal(z.shape), np.nan), sector))[0] for _ in range(3)]
print("mechanics: iid z after the SECTOR LOO residualisation: " + ", ".join(f"{v:.4f}" for v in iid_s))
cf = []
for _ in range(3):
    c = rng.standard_normal(z.shape[1])
    zz = np.sqrt(0.3) * c[None, :] + np.sqrt(0.7) * rng.standard_normal(z.shape)
    zz = np.where(mask, zz, np.nan)
    cf.append((rb(zz)[0], rb(loo_resid(zz))[0], rb(loo_resid(zz, sector))[0]))
print("mechanics: pure common factor (rho 0.3) + noise: raw / after all-firm LOO / after sector LOO: "
      + "; ".join(f"{a:.3f} / {b:.4f} / {c:.4f}" for a, b, c in cf))
