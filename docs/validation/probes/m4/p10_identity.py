"""p10 (claim 10): every committed table vs 8c3221b (bytes); event_measures column by column (values, not bytes);
results: the H1-H4 rows (event tests, G1 validation rows, paths) vs 8c3221b's results, value by value.
Run: uv run --frozen --no-sync python docs/validation/probes/m4/p10_identity.py <scratch_dir>"""
import hashlib
import io
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

S = Path(sys.argv[1])
S.mkdir(parents=True, exist_ok=True)


def head(path):
    return subprocess.run(["git", "show", f"8c3221b:{path}"], capture_output=True, check=True).stdout


for pth in sorted(Path("data/derived").iterdir()):
    try:
        old = head(str(pth))
    except subprocess.CalledProcessError:
        print(f"{pth}: new file")
        continue
    same = hashlib.sha256(old).hexdigest() == hashlib.sha256(pth.read_bytes()).hexdigest()
    print(f"{pth}: {'byte-identical' if same else 'CHANGED'}")
old = pd.read_parquet(io.BytesIO(head("data/derived/event_measures.parquet")))
new = pd.read_parquet("data/derived/event_measures.parquet")
print("event_measures rows", len(old), len(new), "same ids/order:", old["event_id"].tolist() == new["event_id"].tolist())
print("columns added:", sorted(set(new) - set(old)), "removed:", sorted(set(old) - set(new)))
changed = []
for c in old.columns:
    a, b = old[c], new[c]
    if not a.equals(b):
        if a.isna().equals(b.isna()) and pd.api.types.is_float_dtype(a) and np.allclose(a.fillna(0), b.fillna(0), 0, 0):
            continue
        changed.append((c, int((a.astype(str) != b.astype(str)).sum()), int(a.notna().sum()), int(b.notna().sum())))
print("columns whose values changed (name, rows differing, non-null before, after):", changed)
print("class-R columns committed:", [c for c in new.columns if c.endswith("_yf") or c.endswith("_cboe")])
ro = pd.read_parquet(io.BytesIO(head("data/derived/results.parquet")))
rn = pd.read_parquet("data/derived/results.parquet")
print("results rows: 8c3221b", len(ro), "now", len(rn))
key = ["family", "hypothesis", "role", "measure", "statistic", "rel_day", "sample", "subgroup_key", "subgroup_value",
       "adjustment", "model_id", "term"]
vals = ["estimate", "se", "stat", "df", "p_value", "ci_lo", "ci_hi", "q_bh", "n", "n_clusters", "n_clusters_firm", "rbar"]
k = lambda d: d[key].apply(lambda c: c.map(lambda v: "" if v is None or (isinstance(v, float) and np.isnan(v)) else str(v))).agg("|".join, axis=1)
ro["k"], rn["k"] = k(ro), k(rn)
m = ro.merge(rn, on="k", how="left", suffixes=("_o", "_n"), indicator=True)
print("8c3221b rows missing now:", int((m["_merge"] != "both").sum()),
      m.loc[m["_merge"] != "both", "k"].str.slice(0, 90).tolist()[:12])
both = m[m["_merge"] == "both"]
diffs = {}
for v in vals + ["p_holm", "role"]:
    a, b = both[f"{v}_o"], both[f"{v}_n"]
    if v == "role":
        d = a.astype(str) != b.astype(str)
    else:
        a, b = pd.to_numeric(a, errors="coerce"), pd.to_numeric(b, errors="coerce")
        d = ~((a == b) | (a.isna() & b.isna()))
    if d.any():
        diffs[v] = both.loc[d, "k"].str.slice(0, 80).tolist()
for v, ks in diffs.items():
    print(f"value {v} differs in {len(ks)} rows, e.g. {ks[:6]}")
g1o = both[both["family_o"] == "validation"] if "family_o" in both else both[both["k"].str.startswith("validation")]
g = both[both["k"].str.startswith("validation|H1|") | both["k"].str.startswith("validation|H2|")
         | both["k"].str.startswith("validation|H3|") | both["k"].str.startswith("validation|H4|")]
eq = ((pd.to_numeric(g["estimate_o"]) == pd.to_numeric(g["estimate_n"])) | (g["estimate_o"].isna() & g["estimate_n"].isna()))
print(f"G1 validation rows of H1-H4: {len(g)}, estimate identical in {int(eq.sum())}")
cal = both[both["k"].str.contains("g1_calibration")]
eqc = (pd.to_numeric(cal["estimate_o"]) == pd.to_numeric(cal["estimate_n"])) | (cal["estimate_o"].isna() & cal["estimate_n"].isna())
print(f"G1 calibration rows (cm30, sigma_d): {len(cal)}, identical {int(eqc.sum())}")
