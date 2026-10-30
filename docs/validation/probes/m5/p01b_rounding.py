"""p01b: is any printed value within 1e-9 (relative) of a rounding half-boundary at its printed precision?

    uv run --frozen --offline --no-sync python docs/validation/probes/m5/p01b_rounding.py

Reads p01's output (key, printed string) and the raw floats behind the main families of keys from results.parquet /
JSON; for fixed-decimal prints, measures |x*10^nd - (floor(x*10^nd) + 0.5)|. Prints only the near-boundary cases.
"""
import json, math, re
import pandas as pd
r = pd.read_parquet("data/derived/results.parquet")
vals = []
for c in ("estimate", "se", "ci_lo", "ci_hi", "stat"):
    vals += [(f"results.{c}", float(x)) for x in r[c].dropna()]
for k in ("tests", "drivers", "implied_vs_realised", "event_paths", "iv_measures"):
    def walk(o, p=k):
        if isinstance(o, dict):
            for a, b in o.items(): walk(b, f"{p}.{a}")
        elif isinstance(o, list):
            for b in o[:400]: walk(b, p)
        elif isinstance(o, float):
            vals.append((p, o))
    walk(json.load(open(f"app/public/data/{k}.json"))["data"])
near = []
for name, x in vals:
    for nd in (2, 3, 4):
        y = abs(x) * 10 ** nd
        d = abs(y - (math.floor(y) + 0.5))
        if d < 1e-9 * max(1.0, y):
            near.append((name, nd))
    for scale in (100,):  # percentages at 1 and 2 decimals
        for nd in (1, 2):
            y = abs(x) * scale * 10 ** nd
            d = abs(y - (math.floor(y) + 0.5))
            if d < 1e-9 * max(1.0, y):
                near.append((name + " (as %)", nd))
print(f"values scanned: {len(vals):,}; at a half-boundary (exact ties) at 2-4 dp or as a % at 1-2 dp: {len(near)}")
from collections import Counter
print(Counter(near).most_common(20))
