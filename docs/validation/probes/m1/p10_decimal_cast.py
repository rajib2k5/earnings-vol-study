"""p10: is decimal -> text -> float64 exact to float rounding, and is there other precision loss? (claim 9)

  uv run python docs/validation/probes/m1/p10_decimal_cast.py

1. Exhaustive over decimal(5,4) (all 100,000 values) and random samples of decimal(12,2),
   decimal(10,4), decimal(18,8), decimal(38,18): compare dolt.normalise() with float(Decimal(s)),
   which Python rounds correctly. Count the mismatches of the old direct cast too.
2. The cached small extracts (earnings_calendar, eps_history, eps_estimate) and the option-chain
   months: which normalise version wrote them (manifests / mtimes), and do their floats round-trip
   at the source scale (a direct-cast value like 0.26780000000000004 does not)?
   The source scales come from DESCRIBE on the project's MIRROR (never the shared clone).
3. timestamp -> date32: does the cast drop a time-of-day silently?
"""
import json
import random
from decimal import Decimal

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from earnings_vol import config, params as params_mod
from earnings_vol.ingest import dolt


def check(values, prec, scale):
    arr = pa.array([Decimal(v) for v in values], pa.decimal128(prec, scale))
    got = dolt.normalise(pa.table({"x": arr})).column("x").to_pylist()
    direct = pc.cast(arr, pa.float64()).to_pylist()
    want = [float(Decimal(v)) for v in values]
    bad = sum(g != w for g, w in zip(got, want))
    bad_direct = sum(g != w for g, w in zip(direct, want))
    print(f"decimal({prec},{scale}) n={len(values)}: normalise mismatches {bad}; direct-cast mismatches {bad_direct}")


def main():
    check([f"{i // 10000}.{i % 10000:04d}" for i in range(100000)], 5, 4)
    rnd = random.Random(20261029)
    for prec, scale in ((12, 2), (10, 4), (18, 8), (38, 18)):
        ip = prec - scale
        vals = [f"{'-' if rnd.random() < .3 else ''}{rnd.randrange(10 ** ip)}.{rnd.randrange(10 ** scale):0{scale}d}"
                for _ in range(100000)]
        check(vals, prec, scale)

    p = params_mod.load()
    base = config.cache_dir() / "dolt" / f"earnings@{p['dolt']['earnings_commit']}"
    mirror = config.cache_dir() / "dolt_mirror" / "earnings"
    for table, cols in (("eps_history", ("reported", "estimate")),
                        ("eps_estimate", ("consensus", "high", "low"))):
        desc = dolt.query(mirror, f"DESCRIBE `{table}`").to_pylist()
        types = {r["Field"]: r["Type"] for r in desc}
        t = pq.read_table(base / f"{table}.parquet")
        for c in cols:
            scale = int(types[c].split(",")[1].rstrip(")")) if "decimal" in types[c] else None
            vals = [v for v in t.column(c).to_pylist() if v is not None]
            off = [v for v in vals if scale is not None and float(f"{v:.{scale}f}") != v]
            print(f"{table}.{c} source type {types[c]}: {len(vals)} values, {len(off)} not the nearest float "
                  f"to a {scale}-dp decimal; e.g. {off[:3]}")
    import os
    import time
    for f in sorted(base.glob("*.parquet")):
        print("small extract", f.name, "mtime", time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(f))))
    cdir = config.cache_dir() / "dolt" / f"options@{p['dolt']['options_commit']}" / "option_chain"
    vers = {}
    for m in sorted(cdir.glob("*.manifest.json")):
        vers.setdefault(json.loads(m.read_text()).get("normalise"), []).append(m.name[:7])
    print("option_chain months by NORMALISE_VERSION:", {k: len(v) for k, v in vers.items()})
    oc = pq.read_table(sorted(cdir.glob("*.parquet"))[-1], columns=["strike", "bid", "ask"])
    for c in ("strike", "bid", "ask"):
        vals = oc.column(c).to_pylist()
        print(f"option_chain {c}: values not the nearest float to a 2-dp decimal: "
              f"{sum(float(f'{v:.2f}') != v for v in vals if v is not None)} of {len(vals)}")

    ts = pa.array([1792800000000000, 1792800000000000 + 3_600_000_000], pa.timestamp("us"))
    try:
        print("timestamp with 01:00 time-of-day -> date32 via normalise:",
              dolt.normalise(pa.table({"d": ts})).column("d").to_pylist())
    except Exception as e:
        print("timestamp with time-of-day -> date32 raises:", type(e).__name__, str(e)[:100])


if __name__ == "__main__":
    main()
