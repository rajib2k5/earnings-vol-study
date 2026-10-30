"""p03 (claim 3): Holm from the committed results.parquet; the binding family; the all-declared rows; the
G = 7 counterfactual; m = 7 vs m = 4. Own Holm (not multiple.holm). Reads data/derived only.
Run: uv run --frozen --no-sync python docs/validation/probes/m4/p03_holm.py [--falsify]
--falsify computes the binding Holm over H1-H7 (it must then disagree with the committed p_holm)."""
import sys

import numpy as np
import pandas as pd

r = pd.read_parquet("data/derived/results.parquet")


def holm(p):
    ks = sorted(p, key=lambda k: p[k])
    m, out, run = len(ks), {}, 0.0
    for i, k in enumerate(ks):
        run = max(run, min(1.0, (m - i) * p[k]))
        out[k] = run
    return out


prim = r[(r["role"] == "primary") & r["family"].isin(["event_test", "regression"])]
print("primary rows:", sorted(prim["hypothesis"]))
decl = {"H1": "twoway_date_t", "H2": "rad_season_p", "H3": "twoway_season_t", "H4": "twoway_date_t",
        "H5": "twoway_date_t", "H6": "twoway_date_t", "H7": "twoway_date_wald"}
p = {}
for h, s in decl.items():
    x = r[(r["hypothesis"] == h) & (r["statistic"] == s) & r["family"].isin(["event_test", "regression"])
          & (r["subgroup_key"] == "all") & (r["adjustment"] != "mean") & r["role"].isin(["primary", "exploratory"])]
    assert len(x) == 1, (h, len(x))
    p[h] = float(x["p_value"].iloc[0])
    print(f"{h} {s:16s} role={x['role'].iloc[0]:11s} p={p[h]:.6g} p_holm(committed)={x['p_holm'].iloc[0]}")
fam = ["H1", "H2", "H3", "H4", "H5", "H6", "H7"] if "--falsify" in sys.argv else ["H1", "H2", "H3", "H4"]
h4 = holm({h: p[h] for h in fam})
h7 = holm(p)
bad = 0
for h in ("H1", "H2", "H3", "H4"):
    c = float(prim[prim["hypothesis"] == h]["p_holm"].iloc[0])
    ok = abs(c - h4[h]) <= 1e-12 * max(1, h4[h])
    bad += not ok
    print(f"{h}: own Holm m={len(fam)} {h4[h]:.6g}  committed {c:.6g}  {'ok' if ok else 'DIFF'}")
dec = r[r["measure"] == "holm_all_declared"]
for _, x in dec.sort_values("hypothesis").iterrows():
    ok = abs(x["estimate"] - h7[x["hypothesis"]]) <= 1e-12
    bad += not ok
    print(f"all-declared {x['hypothesis']}: committed {x['estimate']:.6g} own m=7 {h7[x['hypothesis']]:.6g} "
          f"family={x['family']} role={x['role']} p_value={x['p_value']} p_holm={x['p_holm']} {'ok' if ok else 'DIFF'}")
cut = r[r["subgroup_key"] == "season_cut"]
for _, x in cut.iterrows():
    q = dict({h: p[h] for h in ("H1", "H2", "H3", "H4")}, H2=float(x["p_value"]))
    q7 = dict(p, H2=float(x["p_value"]))
    print(f"season cut {x['subgroup_value']}: p {x['p_value']:.6g} committed p_holm {x['p_holm']:.6g}; own m=4 "
          f"{holm(q)['H2']:.6g}; own m=7 with real H5-H7 {holm(q7)['H2']:.6g}; m=7 with H5-H7 at p=1 "
          f"{holm(dict(q, H5=1, H6=1, H7=1))['H2']:.6g}")
print("mismatches:", bad)
sys.exit(1 if bad else 0)
