# p03 — What was fetched, its structure, and how far back each company is covered.
#
# Per security: files, extra pages used / listed, bytes on disk, the first and
# last filing date of the merged filings, and the first Item 2.02 8-K from
# 2020. Checks the structure the code relies on: each extra page has the
# arrays of `recent` (FILING_KEYS) with filingCount entries, its first
# filingDate is the listed filingFrom, and its last is near filingTo; and the
# format of `items` and `acceptanceDateTime`. Reads raw/edgar/ only.
#
# Run: .venv/bin/python docs/validation/probes/edgar/p03_coverage.py

import collections
import json
import re
from datetime import date

import pandas as pd

from earnings_vol import config
from earnings_vol.ingest import edgar

raw = config.raw_dir()
log = json.loads((raw / "edgar" / "fetch_log.json").read_text(encoding="utf-8"))
first_run = log.get("earlier_runs", [log])[0]
print(f"fetch runs: first {first_run['started_utc']} .. {first_run['finished_utc']}, "
      f"{first_run['requests']} requests, {first_run['files']} files; last run {log['requests']} requests")
print(f"files on disk: {log['files']}, {log['bytes']:,} bytes; since {log['since']}")
sel = pd.read_parquet(config.cache_dir() / "universe.parquet")
sel = sel[sel["in_universe"]].sort_values("security_id")
pred = edgar.parse_predecessors(edgar.PREDECESSORS_PATH.read_text(encoding="utf-8"))
pairs = list(zip(sel["security_id"], sel["cik"])) + [(f"{s}*", c) for s, cs in pred.items() for c in cs]
rows, problems, to_diff = [], [], []
items_fmt, acc_fmt = collections.Counter(), collections.Counter()
for sid, cik in pairs:
    doc, pages = edgar.read_cached(cik, raw, edgar.SINCE)
    listed = {f["name"]: f for f in doc["filings"].get("files", [])}
    for n, pg in zip(edgar.pages_needed(doc, edgar.SINCE), pages):
        if not set(edgar.FILING_KEYS) <= set(pg):
            problems.append(f"{n}: missing {set(edgar.FILING_KEYS) - set(pg)}")
        if len(pg["accessionNumber"]) != listed[n]["filingCount"]:
            problems.append(f"{n}: {len(pg['accessionNumber'])} filings, listed {listed[n]['filingCount']}")
        if min(pg["filingDate"]) != listed[n]["filingFrom"]:
            problems.append(f"{n}: first filingDate {min(pg['filingDate'])} != filingFrom {listed[n]['filingFrom']}")
        to_diff.append((date.fromisoformat(max(pg["filingDate"])) - date.fromisoformat(listed[n]["filingTo"])).days)
    m = edgar.merge_filings(doc, pages)
    for form, items, acc in zip(m["form"], m["items"], m["acceptanceDateTime"]):
        acc_fmt["ok" if re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z", acc) else acc] += 1
        if form == "8-K" and m is not None:
            items_fmt["n.nn[,n.nn...]" if re.fullmatch(r"\d\.\d\d(,\d\.\d\d)*", items or "") else repr(items)] += 1
    f202 = [f for f in edgar.item_202_filings(doc, pages) if f["accepted"].year >= 2020]
    cov = edgar.coverage(doc, pages)
    names = [f"CIK{int(cik):010d}.json", *edgar.pages_needed(doc, edgar.SINCE)]
    rows.append({"security": sid, "cik": f"{int(cik):010d}", "pages used/listed": f"{len(pages)}/{len(listed)}",
                 "bytes": sum((raw / 'edgar' / n).stat().st_size for n in names),
                 "first filing": cov["first_filing_date"], "last filing": cov["last_filing_date"],
                 "Item 2.02 8-Ks 2020+": len(f202),
                 "first 2.02 from 2020": f202[0]["accepted"].astimezone(edgar.NY).date() if f202 else None})
T = pd.DataFrame(rows)
print(T.to_string(index=False))
print("\nstructure problems:", problems or "none")
print("extra pages read:", len(to_diff), "; last filingDate minus listed filingTo, days: min", min(to_diff),
      "max", max(to_diff))
print("8-K `items` formats:", dict(items_fmt))
print("acceptanceDateTime formats:", dict(acc_fmt))
late = T[T["first filing"] > "2020-01-01"]
print("securities whose merged filings start after 2020-01-01:", late["security"].tolist())
