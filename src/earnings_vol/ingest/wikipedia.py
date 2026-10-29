# =============================================================================
# wikipedia.py — The S&P 500 constituents list: ticker, name, GICS sector,
# sub-industry and SEC CIK, read from one pinned Wikipedia revision.
#
# Wikipedia text is CC BY-SA 4.0, the same licence as data/derived/, so the
# columns we take from it may be committed (data model §1.3).
#
# fetch_revision() is the only function here that uses the network. It asks
# the MediaWiki API for one revision id, so a re-run reads the same table, and
# it keeps the raw answer in raw_dir()/wikipedia/. parse_constituents() is a
# pure function of that text, tested on a hand-written fixture.
# =============================================================================

import json
import re
from pathlib import Path

import pandas as pd
import requests

API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "earnings-vol-study/0.1 (research pipeline; python-requests)"

# The ticker cell is a template: {{NyseSymbol|MMM}}, {{NasdaqSymbol|ADBE}} or
# {{BZX link|CBOE}} (seen in revision 1382178819).
_SYMBOL = re.compile(r"\{\{\s*(?:NyseSymbol|NasdaqSymbol|BZX link)\s*\|\s*([A-Za-z0-9.\-]+)\s*\}\}", re.IGNORECASE)
_LINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")


def fetch_revision(revid: int, raw_dir: Path) -> dict:
    """Download one revision's wikitext (or reuse the saved copy) and return the API JSON."""
    path = raw_dir / "wikipedia" / f"sp500_{revid}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    resp = requests.get(API, params={
        "action": "query", "prop": "revisions", "revids": str(revid),
        "rvprop": "ids|timestamp|content", "rvslots": "main", "format": "json", "formatversion": "2",
    }, headers={"User-Agent": USER_AGENT}, timeout=60)
    resp.raise_for_status()
    doc = resp.json()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, sort_keys=True), encoding="utf-8")
    return doc


def wikitext(doc: dict) -> str:
    rev = doc["query"]["pages"][0]["revisions"][0]
    return rev["slots"]["main"]["content"]


def _plain(cell: str) -> str:
    """Wiki markup to plain text: [[a|b]] -> b, [[a]] -> a, extra spaces removed."""
    text = _LINK.sub(lambda m: m.group(2) or m.group(1), cell)
    return re.sub(r"\s+", " ", text).strip()


def parse_constituents(text: str) -> pd.DataFrame:
    """The table with id="constituents" as rows of
    symbol, name, gics_sector, gics_sub_industry, cik.

    A row's cells are separated by "||", either on one line or at the start of
    each line, so both layouts are read the same way.
    """
    start = text.find('id="constituents"')
    if start < 0:
        raise ValueError('no table with id="constituents"')
    end = text.find("\n|}", start)
    rows = []
    for raw in text[start:end].split("\n|-")[1:]:
        flat = re.sub(r"\n\|\|?", "||", raw.strip("\n"))
        if not flat.startswith("||"):
            continue                       # the header row starts with "!"
        cells = [c.strip() for c in flat.split("||")[1:]]
        if len(cells) < 7:
            raise ValueError(f"row with {len(cells)} cells: {raw[:120]!r}")
        m = _SYMBOL.search(cells[0])
        if not m:
            raise ValueError(f"no ticker template in {cells[0]!r}")
        cik = re.sub(r"\D", "", cells[6])
        rows.append({
            "symbol": m.group(1).upper(),
            "name": _plain(cells[1]),
            "gics_sector": _plain(cells[2]),
            "gics_sub_industry": _plain(cells[3]),
            "cik": cik.zfill(10) if cik else None,
        })
    df = pd.DataFrame(rows, columns=["symbol", "name", "gics_sector", "gics_sub_industry", "cik"])
    if df["symbol"].duplicated().any():
        raise ValueError(f"duplicate symbols: {df[df['symbol'].duplicated()]['symbol'].tolist()}")
    return df
