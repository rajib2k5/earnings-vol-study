# =============================================================================
# edgar.py — SEC EDGAR 8-K Item 2.02 acceptance times (ADR 0002 §3, source 1).
#
# STATUS
#   The owner APPROVED EDGAR as the timing source on 2026-10-28 and supplied
#   the contact string on 2026-11-09. SEC's fair-access policy requires a real
#   contact in the User-Agent of every request. This client REFUSES TO FETCH
#   unless SEC_EDGAR_USER_AGENT holds one: there is no default or placeholder
#   value, ever, and the string is never written to a file or a log. The
#   events layer reads only the local cache (read_cached), which makes no
#   request and needs no User-Agent. The first fetch ran on 2026-11-09
#   (docs/validation/edgar-ledger.md), and the same day the owner switched it
#   on in the pipeline (params timing.edgar: true): of the 473 required
#   look-ups, 20 rest on press releases, 411 on an 8-K time, and 42 stay open
#   (no 8-K 26, EDGAR holiday 11, 8-K on another date 4, 8-K against the
#   calendar 1). The ADR's 50-event audit of the EDGAR labels has not run, so
#   timing.lookups_complete stays false.
#
# WHAT IT READS
#   One JSON file per company, data.sec.gov/submissions/CIK##########.json,
#   which lists each filing's form, items and acceptanceDateTime, plus the
#   extra pages its `filings.files` lists for filings older than the `recent`
#   block (a bank's 2020-2023 8-Ks are only there). At most 10 requests a
#   second. Every file is kept in raw_dir()/edgar/ and never fetched twice.
#
# THE TIME ZONE (verified 2026-11-09, edgar-ledger.md §2)
#   acceptanceDateTime ("2024-10-29T20:01:46.000Z") is a UTC instant, as its
#   "Z" says, not New York wall time: read as UTC, 16 of the 20 press-release
#   look-ups agree on date and label (the other 4 are EDGAR-holiday windows,
#   whose times also agree), each company's release time keeps its New York
#   clock time across daylight-saving changes, and an 8-K accepted after
#   17:30 New York time gets the next filing date. Read as New York time,
#   every BMO release of the 20 lands inside the session. parse_acceptance()
#   refuses any other format.
#
# HOW A TIME IS READ (ADR 0002 §3)
#   Take the 8-K whose items include 2.02 and whose acceptance time, in New
#   York time, falls on D-1, D or D+1. Accepted before 09:30 on a session: BMO
#   on that session. At or after the close (16:00, 13:00 on a half day): AMC.
#   In between: during_session (hand-checked). On a non-session day: the
#   release was outside market hours. EDGAR is closed on some days that are
#   NYSE sessions (Columbus Day, Veterans Day, and others measured in the
#   data, edgar_holidays): when D-1, D or D+1 is one of them, the acceptance
#   time is not read as timing. Two Item 2.02 8-Ks in the window that read
#   differently are not read either (several_8k).
# =============================================================================

import json
import os
import re
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ENV = "SEC_EDGAR_USER_AGENT"
NY = ZoneInfo("America/New_York")
MAX_PER_SECOND = 10
# A contact email: local part, "@", and a domain of two or more dot-separated
# labels. "@" alone, "a@b" or "x@localhost" do not match.
_EMAIL = re.compile(r"(?<![\w.%+-])([A-Za-z0-9._%+-]+)@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)(?![\w.-])")
# Names reserved so that they never belong to anyone, including every
# subdomain: x@mail.example.com, x@foo.example and x@foo.test are placeholders,
# not contacts. The design-time placeholder admin@example.org is one of them.
#   RFC 2606 / 6761: test, example, invalid, localhost, example.com/.org/.net
#   RFC 6762: local (mDNS)        RFC 8375: home.arpa (home networks)
#   RFC 7686: onion (Tor)         RFC 9476: alt (non-DNS namespaces)
#   internal: reserved by ICANN in 2024 for private use
_RESERVED_TLDS = {"test", "example", "invalid", "localhost", "local", "onion", "alt", "internal"}
_RESERVED_DOMAINS = {"example.com", "example.org", "example.net", "home.arpa"}


class EdgarNotConfigured(RuntimeError):
    """SEC_EDGAR_USER_AGENT is not set to a real contact: no request may be made."""


def is_real_contact(ua: str) -> bool:
    """Does `ua` hold at least one well-formed email, and no reserved or malformed one?

    Well-formed (RFC 5321/5322 dot-atom, ASCII): a local part that does not
    start or end with a dot and has no "..", and a domain of at most 253
    characters whose labels have 1-63 letters, digits or hyphens, with no
    hyphen at either end, under a top-level domain of letters only.

    It FAILS CLOSED on some real addresses (delta review, claim 6b): they are
    refused, and the owner writes the contact another way.
      - a trailing full stop: "contact first.last@gmail.com." (the dot reads
        as part of the domain; drop it)
      - a punycode top-level domain such as .xn--p1ai (letters only)
      - a Unicode local part or domain such as josé@uni.edu (ASCII only)
    """
    found = [(local, domain.lower()) for local, domain in _EMAIL.findall(ua)]
    if not found or ua.count("@") != len(found):
        return False   # no email, or an "@" that is not part of a well-formed one
    for local, d in found:
        if local.startswith(".") or local.endswith(".") or ".." in local:
            return False
        labels = d.split(".")
        if len(d) > 253 or any(len(lb) > 63 for lb in labels):
            return False
        if labels[-1] in _RESERVED_TLDS or any(d == r or d.endswith("." + r) for r in _RESERVED_DOMAINS):
            return False
        if not re.fullmatch(r"[a-z]{2,63}", labels[-1]):
            return False   # a top-level domain is letters only
        if any(lb.startswith("-") or lb.endswith("-") for lb in labels):
            return False
    return True


def user_agent() -> str:
    """The owner's User-Agent string, or EdgarNotConfigured. Never a default."""
    ua = os.environ.get(ENV, "").strip()
    if not ua:
        raise EdgarNotConfigured(f"{ENV} is not set: EDGAR runs only with the owner's contact string")
    if not is_real_contact(ua):
        raise EdgarNotConfigured(f"{ENV} must hold a real contact email, not a placeholder")
    return ua


def submissions_url(cik: str) -> str:
    if not re.fullmatch(r"\d{1,10}", cik or ""):
        raise ValueError(f"not a CIK: {cik!r}")
    return f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json"


def _fetch_json(url: str, path: Path, get, sleep) -> dict:
    """One file, from the cache or (once) from EDGAR. The User-Agent is checked
    FIRST, before the cache or the network, so an unconfigured run fails the
    same way every time. Only sec.gov hosts are ever asked."""
    ua = user_agent()
    if not url.startswith("https://data.sec.gov/submissions/"):
        raise ValueError(f"not an EDGAR submissions URL: {url!r}")
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    if get is None:
        import requests
        get = requests.get
    resp = get(url, headers={"User-Agent": ua, "Accept-Encoding": "gzip, deflate"}, timeout=60)
    resp.raise_for_status()
    sleep(1.0 / MAX_PER_SECOND)
    doc = resp.json()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, sort_keys=True), encoding="utf-8")
    return doc


def fetch_submissions(cik: str, raw_dir: Path, get=None, sleep=time.sleep) -> dict:
    """The submissions JSON of one company, from raw_dir()/edgar/ or (once) from EDGAR.

    The User-Agent is checked FIRST, before the cache or the network, so an
    unconfigured run fails the same way every time. `get` is requests.get by
    default; a test passes a recorder.
    """
    url = submissions_url(cik)
    return _fetch_json(url, raw_dir / "edgar" / f"CIK{int(cik):010d}.json", get, sleep)


# --- the extra pages: filings older than the `recent` block ---------------------
#
# `filings.recent` holds only a company's most recent filings (about 1,000, or
# a year, whichever is more). Older ones are listed in `filings.files`, one
# entry per extra page {name, filingCount, filingFrom, filingTo}, each page
# served at data.sec.gov/submissions/<name> with the same parallel arrays as
# `recent`, at its top level. A bank that files thousands of prospectuses a
# year has its 2020-2023 8-Ks only in those pages.

PAGE_NAME = re.compile(r"CIK\d{10}-submissions-\d{3}\.json")
# The arrays a filing is read from; every block must have them, of one length.
FILING_KEYS = ("accessionNumber", "filingDate", "acceptanceDateTime", "form", "items")
# A page's listed filingTo is not always its last filingDate: over the 135
# pages fetched on 2026-11-09 the last filingDate was 6 days before to 1 day
# AFTER filingTo (filingFrom was always exact). A page is therefore used when
# its filingTo is within this margin before `since`.
PAGE_MARGIN_DAYS = 7
# How far back the pages are read: the calendar starts 2020-01-22, so D-1 >= 2020-01-21.
SINCE = date(2020, 1, 1)


def pages_needed(doc: dict, since: date) -> list[str]:
    """The extra pages listed in `filings.files` that may hold a filing dated on or after `since`."""
    out = []
    for f in doc["filings"].get("files", []):
        if not PAGE_NAME.fullmatch(f.get("name", "")):
            raise ValueError(f"unexpected page name in filings.files: {f.get('name')!r}")
        if date.fromisoformat(f["filingTo"]) >= since - timedelta(days=PAGE_MARGIN_DAYS):
            out.append(f["name"])
    return out


def fetch_page(name: str, raw_dir: Path, get=None, sleep=time.sleep) -> dict:
    """One extra page, from raw_dir()/edgar/ or (once) from EDGAR."""
    if not PAGE_NAME.fullmatch(name):
        raise ValueError(f"not a submissions page name: {name!r}")
    return _fetch_json(f"https://data.sec.gov/submissions/{name}", raw_dir / "edgar" / name, get, sleep)


def fetch_all(cik: str, raw_dir: Path, since: date, get=None, sleep=time.sleep) -> tuple[dict, list[dict]]:
    """The submissions file and every extra page that reaches back to `since`."""
    doc = fetch_submissions(cik, raw_dir, get=get, sleep=sleep)
    return doc, [fetch_page(n, raw_dir, get=get, sleep=sleep) for n in pages_needed(doc, since)]


def read_cached(cik: str, raw_dir: Path, since: date) -> tuple[dict, list[dict]]:
    """The same files as fetch_all(), from the cache ONLY.

    It never makes a request, so it needs no User-Agent: the events layer
    reads EDGAR through it and stays offline. A missing file raises
    FileNotFoundError (fetch it first with `python -m earnings_vol.ingest.edgar`).
    """
    base = raw_dir / "edgar"
    doc = json.loads((base / f"CIK{int(cik):010d}.json").read_text(encoding="utf-8"))
    pages = [json.loads((base / n).read_text(encoding="utf-8")) for n in pages_needed(doc, since)]
    return doc, pages


def merge_filings(doc: dict, pages: list[dict]) -> dict[str, list]:
    """`recent` and the extra pages as one set of parallel arrays (FILING_KEYS).

    An accession listed twice must carry the same fields both times, and is
    kept once; two different readings of one accession stop the build.
    """
    blocks = [doc["filings"]["recent"], *pages]
    seen: dict[str, tuple] = {}
    out: dict[str, list] = {k: [] for k in FILING_KEYS}
    for b in blocks:
        n = {len(b[k]) for k in FILING_KEYS}
        if len(n) != 1:
            raise ValueError(f"a filings block has arrays of different lengths: {sorted(n)}")
        for row in zip(*(b[k] for k in FILING_KEYS)):
            acc = row[0]
            if acc in seen:
                if seen[acc] != row:
                    raise ValueError(f"accession {acc} is listed twice with different fields")
                continue
            seen[acc] = row
            for k, v in zip(FILING_KEYS, row):
                out[k].append(v)
    return out


def coverage(doc: dict, pages: list[dict]) -> dict:
    """How far back the merged filings reach: {n_filings, first_filing_date, last_filing_date}."""
    m = merge_filings(doc, pages)
    dates = sorted(m["filingDate"])
    return {"n_filings": len(dates), "first_filing_date": dates[0] if dates else None,
            "last_filing_date": dates[-1] if dates else None}


# acceptanceDateTime as EDGAR writes it: milliseconds, then "Z".
_ACCEPTANCE = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z")


def parse_acceptance(value: str) -> datetime:
    """An acceptanceDateTime string -> an aware UTC datetime.

    The value is a UTC instant (verified 2026-11-09 against the 20
    press-release look-ups, the calendar labels, the price gaps, EDGAR's
    filing-date cut-off and daylight saving; edgar-ledger.md §2). Any other
    format is refused, so a change in EDGAR's output cannot silently move a
    time by hours.
    """
    if not isinstance(value, str) or not _ACCEPTANCE.fullmatch(value):
        raise ValueError(f"unexpected acceptanceDateTime {value!r}")
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)


def item_202_filings(doc: dict, pages: list[dict] = ()) -> list[dict]:
    """The 8-K filings with Item 2.02, from `recent` AND the extra pages:
    accession, accepted_utc (EDGAR's string) and accepted (aware UTC datetime).

    `items` is one comma-separated string of item numbers ("2.02,9.01"). An
    amendment (8-K/A) is not read: it is filed after the release it amends.
    """
    m = merge_filings(doc, pages)
    out = []
    for form, items, acc, accepted in zip(m["form"], m["items"], m["accessionNumber"], m["acceptanceDateTime"]):
        if form != "8-K" or "2.02" not in [i.strip() for i in (items or "").split(",")]:
            continue
        out.append({"accession": acc, "accepted_utc": accepted, "accepted": parse_acceptance(accepted)})
    return sorted(out, key=lambda f: f["accepted"])


# NYSE sessions on which EDGAR accepted nothing, measured on 2026-11-09: no
# filing of the 51 CIKs read (390,105 filings, 2020-01-02 .. 2026-11-06) was
# accepted on these days, while every other session had at least one. Each is
# a federal closure on a trading day: Christmas Eve by executive order (2020,
# 2024, 2025), the day after Christmas 2025, and Juneteenth's first observance
# (Friday 2021-06-18, before NYSE closed for it). The recurring ones are the
# rules in edgar_holidays(); later one-off closures are not known in advance.
EDGAR_CLOSED_MEASURED = frozenset({date(2020, 12, 24), date(2021, 6, 18), date(2024, 12, 24),
                                   date(2025, 12, 24), date(2025, 12, 26)})


def edgar_holidays(year: int) -> set[date]:
    """Days of `year` on which EDGAR is closed although NYSE may trade.

    Columbus Day: the second Monday of October. Veterans Day: 11 November,
    moved to the Friday before when it falls on a Saturday and to the Monday
    after on a Sunday. New Year's Day observed on Friday 31 December when the
    next 1 January is a Saturday (NYSE does not close for it; 2021-12-31 had no
    acceptance, measured). Plus the measured one-off closures above.
    """
    oct1 = date(year, 10, 1)
    columbus = oct1 + timedelta(days=(7 - oct1.weekday()) % 7 + 7)
    vet = date(year, 11, 11)
    if vet.weekday() == 5:
        vet -= timedelta(days=1)
    elif vet.weekday() == 6:
        vet += timedelta(days=1)
    out = {columbus, vet} | {d for d in EDGAR_CLOSED_MEASURED if d.year == year}
    if date(year + 1, 1, 1).weekday() == 5:
        out.add(date(year, 12, 31))
    return out


def _label(local: datetime, sessions, close_time_et: dict) -> str:
    d, hhmm = local.date(), local.strftime("%H:%M")
    if not sessions.is_session(d):
        return "outside_hours"
    if hhmm < "09:30":
        return "BMO"
    return "AMC" if hhmm >= close_time_et[d] else "during_session"


def read_acceptance(announce: date, filings: list[dict], sessions, close_time_et: dict) -> dict | None:
    """The EDGAR reading for a calendar event on `announce`, or None if no 8-K matches.

    Returns {accession, accepted_utc, ny_date, label, n_in_window} where label is
    BMO, AMC, during_session, outside_hours (a non-session day), edgar_holiday
    (D-1, D or D+1 is an EDGAR holiday: not read as timing; the press release
    decides) or several_8k (two Item 2.02 8-Ks in the window that read
    differently: not read as timing either). The filing reported is the one
    nearest to D (the earliest of equals).
    """
    window = {announce - timedelta(days=1), announce, announce + timedelta(days=1)}
    hits = [f for f in filings if f["accepted"].astimezone(NY).date() in window]
    if not hits:
        return None
    f = min(hits, key=lambda h: abs((h["accepted"].astimezone(NY).date() - announce).days))
    local = f["accepted"].astimezone(NY)
    readings = {(h["accepted"].astimezone(NY).date(), _label(h["accepted"].astimezone(NY), sessions, close_time_et))
                for h in hits}
    holidays = set().union(*(edgar_holidays(y) for y in {d.year for d in window}))
    if window & holidays:
        label = "edgar_holiday"
    elif len(readings) > 1:
        label = "several_8k"
    else:
        label = _label(local, sessions, close_time_et)
    return {"accession": f["accession"], "accepted_utc": f["accepted_utc"], "ny_date": local.date(), "label": label,
            "n_in_window": len(hits)}


# --- predecessor CIKs ---------------------------------------------------------------
#
# A company that moved its listing to a new holding company files under a new
# CIK from that day, and its earlier 8-Ks stay under the old one (XOM: a new
# CIK from 2026-07-01). data/manual/edgar_predecessor_ciks.csv names, per
# security, the older CIKs to read as well, each with its evidence from EDGAR.

PREDECESSOR_COLUMNS = ["security_id", "predecessor_cik", "evidence"]
PREDECESSORS_PATH = Path(__file__).resolve().parents[3] / "data" / "manual" / "edgar_predecessor_ciks.csv"


def parse_predecessors(text: str) -> dict[str, list[str]]:
    """{security_id: [predecessor CIK, 10 digits]} from edgar_predecessor_ciks.csv."""
    import csv
    reader = csv.DictReader(text.splitlines(keepends=True))
    if reader.fieldnames != PREDECESSOR_COLUMNS:
        raise ValueError(f"edgar_predecessor_ciks.csv columns {reader.fieldnames} != {PREDECESSOR_COLUMNS}")
    out: dict[str, list[str]] = {}
    for n, r in enumerate(reader, start=2):
        if not re.fullmatch(r"\d{10}", r["predecessor_cik"] or "") or not (r["evidence"] or "").strip():
            raise ValueError(f"edgar_predecessor_ciks.csv line {n}: a 10-digit CIK and its evidence are required")
        out.setdefault(r["security_id"], []).append(r["predecessor_cik"])
    return out


def cached_item_202(ciks: list[str], raw_dir: Path, since: date = SINCE) -> list[dict]:
    """The Item 2.02 8-Ks of one security under all its CIKs, from the cache only (no request)."""
    out = []
    for cik in ciks:
        doc, pages = read_cached(cik, raw_dir, since)
        out += item_202_filings(doc, pages)
    accs = [f["accession"] for f in out]
    if len(accs) != len(set(accs)):
        raise ValueError(f"an accession is listed under two of the CIKs {ciks}")
    return sorted(out, key=lambda f: f["accepted"])


# --- the fetch run: python -m earnings_vol.ingest.edgar ---------------------------
#
# Fetches the submissions file and the extra pages back to SINCE for every
# security in the universe (cache/universe.parquet), at most 10 requests a
# second, and writes raw/edgar/fetch_log.json: what was fetched, its size on
# disk and the filing dates it covers. The log never holds the User-Agent.
# Set SEC_EDGAR_USER_AGENT inline in the command that runs it; nothing else
# in the project reads it.



def fetch_universe(securities: list[tuple[str, str]], raw_dir: Path, since: date = SINCE, get=None,
                   sleep=time.sleep, log=print) -> dict:
    """{security_id: fetch record} for (security_id, cik) pairs. Cached files are not fetched again."""
    if get is None:
        import requests
        get = requests.get
    out = {}
    for sid, cik in securities:
        calls = []

        def counted(url, **kw):
            calls.append(url)
            return get(url, **kw)

        t0 = time.perf_counter()
        doc, pages = fetch_all(cik, raw_dir, since, get=counted, sleep=sleep)
        names = [f"CIK{int(cik):010d}.json", *pages_needed(doc, since)]
        cov = coverage(doc, pages)
        listed = doc["filings"].get("files", [])
        out[sid] = {
            "cik": f"{int(cik):010d}", "requests_this_run": len(calls),
            "seconds_this_run": round(time.perf_counter() - t0, 2),
            "files": names, "bytes": sum((raw_dir / "edgar" / n).stat().st_size for n in names),
            "pages_listed": len(listed), "pages_used": len(names) - 1,
            "recent_first_filing_date": min(doc["filings"]["recent"]["filingDate"], default=None),
            **cov,
        }
        log(f"{sid}: {out[sid]['requests_this_run']} requests, {len(names)} files, "
            f"filings {cov['first_filing_date']} .. {cov['last_filing_date']}")
    return out


def main(argv: list[str] | None = None) -> int:
    import pandas as pd

    from earnings_vol import config

    raw = config.raw_dir()
    user_agent()   # refuse before reading anything else
    sel = pd.read_parquet(config.cache_dir() / "universe.parquet")
    sel = sel[sel["in_universe"]].sort_values("security_id")
    pred = parse_predecessors(PREDECESSORS_PATH.read_text(encoding="utf-8"))
    pairs = list(zip(sel["security_id"], sel["cik"]))
    pairs += [(f"{sid} (predecessor CIK)", c) for sid, cs in sorted(pred.items()) for c in cs]
    t0 = datetime.now(timezone.utc)
    rec = fetch_universe(pairs, raw)
    log = {"started_utc": t0.strftime("%Y-%m-%dT%H:%M:%SZ"),
           "finished_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "since": SINCE.isoformat(), "max_per_second": MAX_PER_SECOND,
           "requests": sum(r["requests_this_run"] for r in rec.values()),
           "files": sum(len(r["files"]) for r in rec.values()),
           "bytes": sum(r["bytes"] for r in rec.values()), "securities": rec}
    path = raw / "edgar" / "fetch_log.json"
    if path.exists():   # keep the record of an earlier run's requests
        old = json.loads(path.read_text(encoding="utf-8"))
        log["earlier_runs"] = old.get("earlier_runs", []) + [{k: old[k] for k in
                                                             ("started_utc", "finished_utc", "requests", "files")}]
    path.write_text(json.dumps(log, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{log['requests']} requests, {log['files']} files, {log['bytes']} bytes; log at {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
