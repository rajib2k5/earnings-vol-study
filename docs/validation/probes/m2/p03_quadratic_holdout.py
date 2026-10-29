"""p03: is the quadratic fallback sound? A hold-out test on real smiles, and where its rows are used.

Claim 3b. Take bracket_linear expiries (where the bracket answer is known), hide strikes so the code
must fall back, run the code's own expiry_atom, and compare its quadratic ATM IV with the bracket one:
  one_sided  hide every valid strike with k <= 0 (the no_bracket case: pure extrapolation)
  wide       hide the bracket's lower strike only (often a wide bracket: interpolation across a hole)
Also: (a) the decimal-tie forward rows (p02) re-solved with the exact tie rule, as an IV impact;
(b) which downstream measures read a quadratic row.
Run from the repository root:
  python docs/validation/probes/m2/p03_quadratic_holdout.py <stage dir> <option_chain dir> <p02 out dir>
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from earnings_vol import store, schema
from earnings_vol.events import calendar
from earnings_vol.measures import chain, forward, run

stage, chain_dir, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
ce = pd.read_parquet(stage / "chain_expiry.parquet")
snap = pd.read_parquet(stage / "session_snapshot.parquet")
aliases = pd.read_parquet(stage / "ticker_alias.parquet")
kept = snap[snap["snapshot_status"] == "ok"]
keep = {(s, sd): d for s, d, sd in zip(kept["security_id"], kept["session_date"], kept["snapshot_date"])}
rng = np.random.default_rng(20261029)
br = ce[(ce["atm_method"].astype(str) == "bracket_linear") & (ce["tau_sessions"] >= 5)]
months = sorted({f"{d.year:04d}-{d.month:02d}" for d in br["snapshot_date"]})
pick = set(rng.choice(months, size=8, replace=False))
ties = pd.read_parquet(out / "tie_keys.parquet")
tie_months = {f"{d.year:04d}-{d.month:02d}" for d in ce.merge(ties)["snapshot_date"]}
P = chain.AtomParams()


def subset(q, keepmask):
    return chain.ExpiryQuotes(*(np.asarray(getattr(q, n))[keepmask] for n in
                                ("strike", "call_bid", "call_ask", "put_bid", "put_ask", "call_vol", "put_vol")))


res, tie_res = [], []
tie_set = {(r.security_id, r.session_date, r.expiration): r.fwd_exact for r in ties.itertuples(index=False)}
for m in sorted(pick | tie_months):
    path = chain_dir / f"{m}.parquet"
    quotes = run.snapshot_quotes(path, keep, aliases)
    sub = ce[ce["snapshot_date"].map(lambda d: f"{d.year:04d}-{d.month:02d}") == m]
    for r in sub.itertuples(index=False):
        q = quotes.get((r.security_id, r.session_date), {}).get(r.expiration)
        if q is None:
            continue
        key = (r.security_id, r.session_date, r.expiration)
        if key in tie_set:
            # same atom, but the forward forced to the exact-tie value
            orig = forward.forward_from_pairs
            forward.forward_from_pairs = lambda *a, **k: (tie_set[key],) + orig(*a, **k)[1:]
            try:
                alt = chain.expiry_atom(q, r.df, r.tau_sessions, P)
            finally:
                forward.forward_from_pairs = orig
            tie_res.append({"iv": r.iv_atm, "iv_alt": alt["iv_atm"]})
        if m not in pick or r.atm_method != "bracket_linear" or r.tau_sessions < 5 or rng.random() > 0.15:
            continue
        k = np.log(np.asarray(q.strike, float) / r.forward)
        for mode in ("one_sided", "wide"):
            mask = (k > 0) if mode == "one_sided" else (np.asarray(q.strike) != r.strike_lo)
            a = chain.expiry_atom(subset(q, mask), r.df, r.tau_sessions, P)
            res.append({"mode": mode, "method": a["atm_method"], "iv_true": r.iv_atm, "iv": a["iv_atm"],
                        "tau": r.tau_sessions})

d = pd.DataFrame(res)
print(f"hold-out expiries: {len(d) // 2} bracket_linear rows from months {sorted(pick)}")
for mode, g in d.groupby("mode"):
    print(f"  {mode}: methods {g['method'].value_counts().to_dict()}")
    for meth, h in g[g["iv"].notna()].groupby("method"):
        e = (h["iv"] - h["iv_true"]) * 100
        print(f"    {meth:15s} n={len(h):5d} error vs bracket IV (vol pts): median {e.median():+.3f}, "
              f"median |.| {e.abs().median():.3f}, p95 |.| {e.abs().quantile(.95):.3f}, max |.| {e.abs().max():.2f}, "
              f">1pt {(e.abs() > 1).mean():.1%}")
t = pd.DataFrame(tie_res)
if len(t):
    e = (t["iv_alt"] - t["iv"]) * 100
    print(f"decimal-tie rows re-solved with the exact tie forward: n={len(t)}, IV change (vol pts) median |.| "
          f"{e.abs().median():.4f}, max |.| {e.abs().max():.4f}")

# where are the 293 quadratic rows read downstream?
iv = pd.read_parquet(stage / "iv_daily.parquet")
qd = ce[ce["atm_method"].astype(str) == "quadratic"][["security_id", "session_date", "expiration"]]
qset = set(map(tuple, qd.to_numpy()))
cols = {"front": "front_expiry", "cm30_lo": "cm30_exp_lo", "cm30_hi": "cm30_exp_hi", "ev1": "ev_exp1", "ev2": "ev_exp2"}
for name, c in cols.items():
    n = sum((s, d, e) in qset for s, d, e in zip(iv["security_id"], iv["session_date"], iv[c]))
    print(f"iv_daily rows whose {name} expiry is a quadratic atom: {n}")
