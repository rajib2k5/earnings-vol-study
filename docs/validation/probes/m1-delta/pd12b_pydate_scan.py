# pd12b (claim 9): pd12 plus Python date(Y, M, D) literals, added after the hand check found one.
# pd12 (claim 9): what tools/licensing/scan_real_rows.py cannot see.
# Its rule 3 needs >= 2 decimals and an ISO/US date. This probe looks for numbers
# with >= 1 decimal (and percentages) within 2 lines of a date in ISO, US or
# month-name form ("September 9, 2024", "9 Sep 2024", "Sep. 9, 2024"), and
# compares them with the raw Yahoo OHLC, close-to-close % change, VIX and DTB3
# of that date (raw rounded to the number's own decimals). Prints file:line,
# the number and what it matched, for review by hand. Local only.
#
# Run: uv run --frozen python docs/validation/probes/m1-delta/pd12_one_decimal_scan.py
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[4]
RAW = Path.home() / "data/vol-projects/earnings-vol-study/raw"
MONTHS = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct",
                                          "nov", "dec"])}
ISO = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
PYD = re.compile(r"date\((\d{4}),\s*(\d{1,2}),\s*(\d{1,2})\)")
US = re.compile(r"(?<!\d)(\d{1,2})/(\d{1,2})/(\d{4})(?!\d)")
MDY = re.compile(r"\b([A-Z][a-z]{2,8})\.? (\d{1,2}),? (\d{4})\b")
DMY = re.compile(r"\b(\d{1,2}) ([A-Z][a-z]{2,8})\.? (\d{4})\b")
NUM = re.compile(r"(?<![\w.])(-?\d{1,5}\.\d{1,4})(%?)(?![\w.])")

by_date: dict[date, list[tuple[str, float]]] = {}
for f in sorted((RAW / "yfinance").glob("*.parquet")):
    df = pd.read_parquet(f).sort_values("date")
    df["pct"] = df["close"].pct_change() * 100
    sym = f.stem
    for r in df.itertuples(index=False):
        d = r.date if isinstance(r.date, date) else pd.Timestamp(r.date).date()
        lst = by_date.setdefault(d, [])
        for k in ("open", "high", "low", "close"):
            lst.append((f"{sym}.{k}", float(getattr(r, k))))
        if pd.notna(r.pct):
            lst.append((f"{sym}.pct%", float(r.pct)))
for name in ("VIXCLS", "DTB3"):
    s = pd.read_csv(RAW / "fred" / f"{name}.csv")
    s.columns = ["date", "v"]
    s = s[pd.to_numeric(s["v"], errors="coerce").notna()]
    s["v"] = s["v"].astype(float)
    s["pct"] = s["v"].pct_change() * 100
    for d, v, pc in zip(s["date"], s["v"], s["pct"]):
        dd = date.fromisoformat(d)
        by_date.setdefault(dd, []).append((name, v))
        if pd.notna(pc):
            by_date[dd].append((f"{name}.pct%", float(pc)))


def dates_in(line):
    out = []
    for m in ISO.finditer(line):
        try:
            out.append(date(*map(int, m.groups())))
        except ValueError:
            pass
    for m in PYD.finditer(line):
        try:
            out.append(date(*map(int, m.groups())))
        except ValueError:
            pass
    for m in US.finditer(line):
        mo, dy, yr = map(int, m.groups())
        try:
            out.append(date(yr, mo, dy))
        except ValueError:
            pass
    for rx, order in ((MDY, "mdy"), (DMY, "dmy")):
        for m in rx.finditer(line):
            a, b, yr = m.groups()
            mon, day = (a, b) if order == "mdy" else (b, a)
            mi = MONTHS.get(mon[:3].lower())
            if mi:
                try:
                    out.append(date(int(yr), mi, int(day)))
                except ValueError:
                    pass
    return out


files = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=REPO, capture_output=True,
                       text=True, check=True).stdout.split("\n")
files = [f for f in files if f and not f.startswith("docs/validation/") and not f.endswith(
    (".parquet", ".png", ".ttf", ".svg", ".drawio", ".lock", ".xml")) and not f.startswith("tools/diagrams/")]
hits = 0
for f in files:
    p = REPO / f
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
        continue
    ds = [dates_in(line) for line in lines]
    for i, line in enumerate(lines):
        near = {d for j in range(max(0, i - 2), min(len(lines), i + 3)) for d in ds[j]}
        if not near:
            continue
        for m in NUM.finditer(line):
            txt, pct = m.group(1), m.group(2)
            dec = len(txt.split(".")[1])
            val = float(txt)
            if len(txt.replace("-", "").replace(".", "").lstrip("0")) < 2:
                continue
            for d in near:
                for name, raw in by_date.get(d, []):
                    if pct and not name.endswith("pct%"):
                        continue
                    if not pct and name.endswith("pct%"):
                        continue
                    if round(raw, dec) == val:
                        hits += 1
                        print(f"{f}:{i + 1}: {txt}{pct} == {name} on {d}  | {line.strip()[:110]}")
print(f"\nhits: {hits} in {len(files)} files")
