"""p02/p03: recompute every chain_expiry atom from the raw option_chain quotes, independently.

Claims 2a, 2b, 3a, 3b. Nothing from earnings_vol.measures is imported: the filter, the forward,
the OTM side, the bounds, the Black-76 inversion (vectorised bisection on log w), the bracket,
the 1.5-sd rule and the quadratic are written here from ADR 0003 §0. Two forward variants:
  float  ties broken as the code does (stable sort on the float |C - P|)
  exact  |C - P| in integer half-cents, ties to the lower strike (ADR 0003 §0 step 2 read literally)
Run from the repository root:
  python docs/validation/probes/m2/p02_atom_recompute.py <stage dir> <option_chain dir> <out dir>
Writes <out dir>/p02_rows.parquet (per-row comparison) and prints the summary.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from scipy.special import ndtr

stage, chain_dir, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
ce = pd.read_parquet(stage / "chain_expiry.parquet")
alias = pd.read_parquet(stage / "ticker_alias.parquet")
intervals: dict = {}
for t, a, b, s in alias[["ticker", "valid_from", "valid_to"]].assign(sid=alias["security_id"]).itertuples(index=False):
    intervals.setdefault(t, []).append((s, a, None if pd.isna(b) else b))


def black(f, k, w, df, call):
    s = np.sqrt(w)
    d1 = (np.log(f / k) + 0.5 * w) / s
    d2 = d1 - s
    return np.where(call, df * (f * ndtr(d1) - k * ndtr(d2)), df * (k * ndtr(-d2) - f * ndtr(-d1)))


def inv_w(mid, f, k, df, call, iters=70):
    lo, hi = np.full(mid.shape, np.log(1e-8)), np.full(mid.shape, np.log(4.0))
    for _ in range(iters):
        m = 0.5 * (lo + hi)
        up = black(f, k, np.exp(m), df, call) < mid
        lo, hi = np.where(up, m, lo), np.where(up, hi, m)
    return np.exp(0.5 * (lo + hi))


def ok(b, a):
    with np.errstate(invalid="ignore", divide="ignore"):
        m = (b + a) / 2
        return (b > 0) & (b < a) & (m >= 0.05) & ((a - b) / m <= 0.5)


def wls_a(k, w, wt):
    x = np.column_stack([np.ones_like(k), k, k * k]) * np.sqrt(wt)[:, None]
    return float(np.linalg.lstsq(x, w * np.sqrt(wt), rcond=None)[0][0])


def atom(g, df):
    K = g["strike"].to_numpy(float)
    cb, ca, pb, pa = (g[c].to_numpy(float) for c in ("bid_c", "ask_c", "bid_p", "ask_p"))
    cok, pok = ok(cb, ca), ok(pb, pa)
    cm, pm = (cb + ca) / 2, (pb + pa) / 2
    both = cok & pok
    res = {}
    if not both.any():
        return {"status": "no_forward"}
    Kb, gap_f = K[both], np.abs(cm[both] - pm[both])
    gap_i = np.abs(np.round((cb[both] + ca[both]) * 100).astype(int) - np.round((pb[both] + pa[both]) * 100).astype(int))
    fk = Kb + (cm[both] - pm[both]) / df
    sel_f = np.argsort(gap_f, kind="mergesort")[:4]
    sel_e = np.array(sorted(range(len(Kb)), key=lambda i: (gap_i[i], Kb[i]))[:4])
    res["fwd_float"], res["fwd_exact"] = float(np.median(fk[sel_f])), float(np.median(fk[sel_e]))
    res["tie_differs"] = set(sel_f.tolist()) != set(sel_e.tolist())
    f = res["fwd_float"]
    call = K >= f
    mid = np.where(call, cm, pm)
    bid, ask = np.where(call, cb, pb), np.where(call, ca, pa)
    k = np.log(K / f)
    lower = np.where(call, np.maximum(df * (f - K), 0), np.maximum(df * (K - f), 0))
    upper = np.where(call, df * f, df * K)
    with np.errstate(invalid="ignore"):
        passes = np.where(call, cok, pok) & (np.abs(k) <= 0.5) & (lower <= mid) & (mid <= upper)
        root = (black(f, K, 1e-8, df, call) < mid) & (mid < black(f, K, 4.0, df, call))
    valid = passes & root
    idx = np.flatnonzero(valid)
    res["n_valid"] = int(idx.size)
    if idx.size == 0:
        res["status"] = "no_atm"
        return res
    w = np.full(K.shape, np.nan)
    w[idx] = inv_w(mid[idx], f, K[idx], df, call[idx])
    with np.errstate(invalid="ignore", divide="ignore"):
        rel = (ask - bid) / mid
        spr = ask - bid
    below, above = idx[k[idx] <= 0], idx[k[idx] > 0]
    wref = None
    res["one_sided"] = not (below.size and above.size)
    if below.size and above.size:
        lo, hi = below[-1], above[0]
        w0 = w[lo] + (0 - k[lo]) / (k[hi] - k[lo]) * (w[hi] - w[lo])
        res.update(strike_lo=K[lo], strike_hi=K[hi])
        if k[hi] - k[lo] <= 1.5 * np.sqrt(w0):
            res.update(w_atm=w0, method="bracket_linear", status="ok")
            return res
        wref = w0
    if wref is None:
        wref = w[idx[np.argmin(np.abs(k[idx]))]]
    sel = idx[np.abs(k[idx]) <= 2 * np.sqrt(wref)]
    res["quad_n"] = int(sel.size)
    res["quad_sides"] = int((k[sel] <= 0).any()) + int((k[sel] > 0).any())
    res["quad_kmin_abs"] = float(np.min(np.abs(k[sel]))) if sel.size else np.nan
    if sel.size >= 4:
        a = wls_a(k[sel], w[sel], 1 / rel[sel])
        res["quad_a_absspread"] = wls_a(k[sel], w[sel], 1 / spr[sel])
        res["quad_a_unweighted"] = wls_a(k[sel], w[sel], np.ones(sel.size))
        # the nearest valid strike's own w, a model-free sanity anchor
        res["w_nearest"] = float(w[idx[np.argmin(np.abs(k[idx]))]])
        if a > 0:
            res.update(w_atm=a, method="quadratic", status="ok")
            return res
    res["status"] = "no_atm"
    return res


rows = []
live = ce[ce["status"] != "stale"]
need = set(zip(live["security_id"], live["snapshot_date"]))
for path in sorted(chain_dir.glob("*.parquet")):
    q = pq.read_table(path).to_pandas(date_as_object=True)
    # ticker -> security on the date (independent of securities.resolve_on)
    amap = {}
    for t, d in q[["act_symbol", "date"]].drop_duplicates().itertuples(index=False):
        hits = [s for s, a, b in intervals.get(t, []) if a <= d and (b is None or b >= d)]
        amap[(t, d)] = hits[0] if hits else None
    q["security_id"] = [amap[(t, d)] for t, d in zip(q["act_symbol"], q["date"])]
    q = q[[(s, d) in need for s, d in zip(q["security_id"], q["date"])]]
    if q.empty:
        continue
    key = ["security_id", "date", "expiration", "strike"]
    c = q[q["call_put"] == "Call"][key + ["bid", "ask"]]
    p = q[q["call_put"] == "Put"][key + ["bid", "ask"]]
    wide = c.merge(p, on=key, how="outer", suffixes=("_c", "_p")).sort_values(key)
    sub = live[live["snapshot_date"].isin(set(q["date"]))]
    lookup = {(r.security_id, r.snapshot_date, r.expiration): r for r in sub.itertuples(index=False)}
    for (s, d, e), g in wide.groupby(["security_id", "date", "expiration"], sort=True):
        r = lookup.get((s, d, e))
        if r is None:
            continue
        a = atom(g, r.df)
        a.update(security_id=s, session_date=r.session_date, expiration=e)
        rows.append(a)

got = pd.DataFrame(rows)
m = live.merge(got, on=["security_id", "session_date", "expiration"], how="left", suffixes=("", "_ind"))
m.to_parquet(out / "p02_rows.parquet")
print("rows: stored non-stale", len(live), "recomputed", int(m["status_ind"].notna().sum()))
print("status agreement:", int((m["status"].astype(str) == m["status_ind"]).sum()), "of", len(m))
print(pd.crosstab(m["status"].astype(str), m["status_ind"].fillna("missing")).to_string())
hasf = m["forward"].notna() & m["fwd_float"].notna()
d = (m.loc[hasf, "forward"] - m.loc[hasf, "fwd_float"]).abs()
print(f"forward vs independent (code tie rule): n={hasf.sum()} max|diff|={d.max():.3e}")
de = (m.loc[hasf, "forward"] - m.loc[hasf, "fwd_exact"]).abs()
print(f"forward vs independent (exact decimal ties to lower strike): rows differing >1e-9: {(de > 1e-9).sum()}, "
      f"tie selections differing: {int(m['tie_differs'].fillna(False).astype(bool).sum())}, max|diff| {de.max():.4f}, "
      f"max rel {(de / m.loc[hasf, 'forward']).max():.2e}")
okb = (m["atm_method"].astype(str) == "bracket_linear") & (m["method"] == "bracket_linear")
rw = ((m.loc[okb, "w_atm"] - m.loc[okb, "w_atm_ind"]) / m.loc[okb, "w_atm_ind"]).abs()
print(f"bracket_linear w_atm: n={okb.sum()} max rel diff {rw.max():.3e}; strike_lo/hi equal: "
      f"{int(((m.loc[okb,'strike_lo']==m.loc[okb,'strike_lo_ind'])&(m.loc[okb,'strike_hi']==m.loc[okb,'strike_hi_ind'])).sum())}")
print("atm_method stored x independent:")
print(pd.crosstab(m["atm_method"].astype(str), m["method"].fillna("none")).to_string())
qd = m[m["atm_method"].astype(str) == "quadratic"]
rq = ((qd["w_atm"] - qd["w_atm_ind"]) / qd["w_atm_ind"]).abs()
print(f"quadratic rows {len(qd)}: max rel diff to independent {rq.max():.3e}")
print("  flags:", qd["flags"].str.contains("no_bracket").sum(), "no_bracket,", qd["flags"].str.contains("wide_bracket").sum(),
      "wide_bracket; strikes in the fit on one side of k=0 only:", int((qd["quad_sides"] == 1).sum()))
print("  n strikes in fit: ", qd["quad_n"].value_counts().sort_index().to_dict())
iv_q = np.sqrt(252 * qd["w_atm"] / qd["tau_sessions"])
iv_near = np.sqrt(252 * qd["w_nearest"] / qd["tau_sessions"])
iv_abs = np.sqrt(252 * qd["quad_a_absspread"].clip(lower=0) / qd["tau_sessions"])
iv_unw = np.sqrt(252 * qd["quad_a_unweighted"].clip(lower=0) / qd["tau_sessions"])
for name, other in (("nearest strike", iv_near), ("1/abs spread", iv_abs), ("unweighted", iv_unw)):
    dd = (iv_q - other) * 100
    print(f"  quadratic IV minus {name} IV (vol pts): median {dd.median():+.2f}, p5 {dd.quantile(.05):+.2f}, "
          f"p95 {dd.quantile(.95):+.2f}, |.|>2: {(dd.abs() > 2).sum()}, |.|>5: {(dd.abs() > 5).sum()}")
os_ = qd[qd["quad_sides"] == 1]
dd = (np.sqrt(252 * os_["w_atm"] / os_["tau_sessions"]) - np.sqrt(252 * os_["w_nearest"] / os_["tau_sessions"])) * 100
print(f"  one-sided quadratic rows: {len(os_)}; extrapolated IV minus nearest-strike IV: median {dd.median():+.2f}, "
      f"max |.| {dd.abs().max():.2f}, min |k| of the fit's strikes median {os_['quad_kmin_abs'].median():.4f}")
