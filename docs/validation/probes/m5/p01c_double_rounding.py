"""p01c: printed numbers sourced from 4-dp JSON and printed at 3 dp: does the full-precision value round the same way?

    uv run --frozen --offline --no-sync python docs/validation/probes/m5/p01c_double_rounding.py

The mean path (event_paths.json, 4 dp) against results.parquet's aliv_path rows (full precision), market/all and
AMC/BMO at the printed days; prints mismatches of the 3-dp string.
"""
import json
from decimal import ROUND_HALF_EVEN, Decimal
import pandas as pd

def q3(x):
    return str(Decimal(x).quantize(Decimal("0.001"), rounding=ROUND_HALF_EVEN))
r = pd.read_parquet("data/derived/results.parquet")
p = r[r.measure == "aliv_path"]
print("aliv_path rows:", len(p), p.groupby(["adjustment", "subgroup_value", "statistic"]).size().to_dict())
ep = json.load(open("app/public/data/event_paths.json"))["data"]
bad = n = 0
for s in ep["series"]:
    if s["adjustment"] != "market":
        continue
    for day in (-10, -1, 0, 1, 5, 10):
        i = ep["rel_days"].index(day)
        row = p[(p.adjustment == "market") & (p.subgroup_value == s["subgroup_value"]) & (p.rel_day == day)]
        for col, js in (("estimate", s["mean"][i]), ("ci_lo", s["ci_lo"][i]), ("ci_hi", s["ci_hi"][i])):
            if len(row) != 1 or pd.isna(row.iloc[0][col]):
                continue
            n += 1
            full = float(row.iloc[0][col])
            if q3(js) != q3(full):
                bad += 1
                print(f"MISMATCH {s['subgroup_value']} day {day} {col}: json->3dp {q3(js)} full->3dp {q3(full)}")
print(f"compared {n}; 3-dp strings that differ between the 4-dp JSON and full precision: {bad}")
