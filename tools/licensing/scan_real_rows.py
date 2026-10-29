"""Look for licensed raw data (Yahoo, FRED/Cboe VIX) copied into the repository. Local only.

    uv run python tools/licensing/scan_real_rows.py              # the working tree
    uv run python tools/licensing/scan_real_rows.py --rev 3636e98  # a commit, read with git show

Adapted from implied-vol-forecasting's scanner of the same name. It reads every raw file under
``$VOL_DATA_DIR/earnings-vol-study/raw/`` (yfinance Parquet, FRED CSVs, the market-cap CSV) and
every text file git would commit (or, with ``--rev``, every file in that commit). A line is
flagged when:

1. it is at least 12 characters long (after stripping) and appears verbatim in a raw CSV;
2. it contains a whole raw CSV data row (a line that starts with a date);
3. it holds a number with 2 or more decimals and 3 or more significant digits (or an integer of 6
   or more digits) that equals, rounded to the number's own decimals, a raw value of a date named
   within ``NEAR_CHARS`` characters on the same line or up to ``NEAR_LINES`` lines away. A date is
   ISO, US ``MM/DD/YYYY``, or a Python ``date(Y, M, D)`` / ``datetime(...)`` / ``Timestamp(...)``
   literal (the milestone-1 delta review found a Cboe VIX close beside ``date(2025, 4, 17)``);
4. it holds an integer of 6 or more digits (separators ``,``, ``_`` or space allowed) equal to an
   undated raw integer (a market cap) or to a raw file's size.

DoltHub-derived rows are not raw here: they may be committed under CC BY-SA 4.0 with attribution.
Rule 3 can flag a coincidence; the fix is the same: pick another made-up number.

It prints only ``file:line`` and a count, never the matched text. Exit 0 clean, 1 something
flagged, 2 no raw data. It is not a test, because CI has no raw data; run it before every push.
"""

from __future__ import annotations

import argparse
import math
import re
import subprocess
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

import pandas as pd

from earnings_vol import config

MIN_LINE = 12
NEAR_CHARS = 120
NEAR_LINES = 3
_ISO_DATE = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
_US_DATE = re.compile(r"(?<!\d)(\d{2})/(\d{2})/(\d{4})(?!\d)")
_PY_DATE = re.compile(r"(?<![\w.])(?:date|datetime|Timestamp)\(\s*(\d{4})\s*,\s*(\d{1,2})\s*,\s*(\d{1,2})")
_NUMBER = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])")
_BIG_INT = re.compile(r"(?<![\w.,])\d{1,3}(?:[,_ ]\d{3})+(?![\w.,]?\d)|(?<![\w.,])\d{6,}(?![\w.])")
REPO = Path(__file__).resolve().parents[2]


def _dates_in(text: str) -> list[tuple[int, int, date]]:
    found = []
    for pattern, order in ((_ISO_DATE, (0, 1, 2)), (_US_DATE, (2, 0, 1)), (_PY_DATE, (0, 1, 2))):
        for m in pattern.finditer(text):
            p = [int(g) for g in m.groups()]
            try:
                found.append((m.start(), m.end(), date(p[order[0]], p[order[1]], p[order[2]])))
            except ValueError:
                continue
    return found


def _sig(token: str) -> int:
    return len(token.lstrip("-").replace(".", "").lstrip("0"))


class RawIndex:
    def __init__(self, raw: Path):
        self.files = sorted(p for p in raw.rglob("*") if p.is_file())
        self.values_by_date: dict[date, set[float]] = defaultdict(set)
        self.ints: set[int] = {p.stat().st_size for p in self.files}
        self.rows_by_prefix: dict[str, list[str]] = defaultdict(list)
        texts = []
        for path in self.files:
            if path.suffix == ".parquet":
                frame = pd.read_parquet(path)
                for row in frame.itertuples(index=False):
                    day = date.fromisoformat(str(row.date)[:10])
                    for value in row[1:]:
                        if isinstance(value, float) and math.isfinite(value) and value != 0:
                            self.values_by_date[day].add(value)
            elif path.suffix == ".csv":
                text = path.read_text(errors="replace")
                texts.append(text)
                for line in text.splitlines():
                    line = line.strip()
                    dates = _dates_in(line)
                    tokens = line.split(",")
                    if dates and dates[0][0] == 0:
                        if len(line) >= MIN_LINE:
                            self.rows_by_prefix[line[: dates[0][1]]].append(line)
                        targets = (self.values_by_date[dates[0][2]],)
                        tokens = line[dates[0][1] :].split(",")
                    else:
                        targets = ()
                    for token in tokens:
                        try:
                            value = float(token)
                        except ValueError:
                            continue
                        if not math.isfinite(value):
                            continue
                        for t in targets:
                            t.add(value)
                        if not targets and value.is_integer() and abs(value) >= 100_000:
                            self.ints.add(int(value))
        self.joined = "\n".join(texts)

    def dated_value(self, line: str, nearby: list[date]) -> bool:
        dates = _dates_in(line)
        for m in _NUMBER.finditer(line):
            token = m.group()
            decimals = len(token.split(".")[1]) if "." in token else 0
            if any(s <= m.start() < e for s, e, _ in dates):
                continue
            if not ((decimals >= 2 and _sig(token) >= 3) or (decimals == 0 and len(token.lstrip("-")) >= 6)):
                continue
            days = [d for s, e, d in dates if min(abs(m.start() - e), abs(s - m.end())) <= NEAR_CHARS] + nearby
            number = float(token)
            if any(round(v, decimals) == number for d in days for v in self.values_by_date.get(d, ())):
                return True
        return False

    def hits(self, line: str) -> bool:
        stripped = line.strip()
        if len(stripped) >= MIN_LINE and stripped in self.joined:
            return True
        for start, end, _ in _dates_in(line):
            if any(line.startswith(row, start) for row in self.rows_by_prefix.get(line[start:end], ())):
                return True
        return any(int(re.sub(r"[,_ ]", "", m.group())) in self.ints for m in _BIG_INT.finditer(line))


def _files(rev: str | None) -> list[tuple[str, bytes]]:
    if rev:
        names = subprocess.run(["git", "ls-tree", "-r", "-z", "--name-only", rev], cwd=REPO,
                               capture_output=True, check=True).stdout.split(b"\0")
        return [(n.decode(), subprocess.run(["git", "show", f"{rev}:{n.decode()}"], cwd=REPO,
                                            capture_output=True, check=True).stdout) for n in names if n]
    names = subprocess.run(["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=REPO,
                           capture_output=True, check=True).stdout.split(b"\0")
    return [(n.decode(), (REPO / n.decode()).read_bytes()) for n in names if n and (REPO / n.decode()).is_file()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--rev", help="scan this commit instead of the working tree")
    args = parser.parse_args(argv)
    index = RawIndex(config.raw_dir())
    if not index.files:
        print("error: no raw files to compare with", file=sys.stderr)
        return 2
    flagged = scanned = 0
    for name, blob in _files(args.rev):
        if b"\0" in blob[:8192]:
            continue
        try:
            text = blob.decode("utf-8")
        except UnicodeDecodeError:
            continue
        scanned += 1
        lines = text.splitlines()
        line_dates = [[d for _, _, d in _dates_in(x)] if len(x) <= 300 else [] for x in lines]
        for i, line in enumerate(lines):
            nearby = [d for j in range(max(0, i - NEAR_LINES), min(len(lines), i + NEAR_LINES + 1)) if j != i
                      for d in line_dates[j]]
            if index.hits(line) or index.dated_value(line, nearby):
                flagged += 1
                print(f"{name}:{i + 1}")
    where = args.rev or "working tree"
    if flagged:
        print(f"{flagged} line(s) flagged in {scanned} text file(s) of {where} against {len(index.files)} raw file(s)")
        return 1
    print(f"clean: 0 lines flagged in {scanned} text file(s) of {where} against {len(index.files)} raw file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
