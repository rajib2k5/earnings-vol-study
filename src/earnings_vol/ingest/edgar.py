# =============================================================================
# edgar.py — SEC EDGAR 8-K Item 2.02 acceptance times (ADR 0002 §3, source 1).
#
# STATUS
#   The owner APPROVED EDGAR as the timing source on 2026-10-28. SEC's
#   fair-access policy requires a real contact in the User-Agent of every
#   request, and the owner will supply that string. Until then this client
#   REFUSES TO RUN: user_agent() raises unless SEC_EDGAR_USER_AGENT is set, and
#   there is no default or placeholder value, ever. At milestone 1 no request
#   was made to sec.gov or data.sec.gov; the tests use hand-written fixtures.
#
# WHAT IT READS (once the contact string is set)
#   One JSON file per company, data.sec.gov/submissions/CIK##########.json,
#   which lists each filing's form, items and acceptanceDateTime (UTC). At most
#   10 requests a second. The file is kept in raw_dir()/edgar/ and never
#   fetched twice.
#
# HOW A TIME IS READ (ADR 0002 §3)
#   Take the 8-K whose items include 2.02 and whose acceptance time, in New
#   York time, falls on D-1, D or D+1. Accepted before 09:30 on a session: BMO
#   on that session. At or after the close (16:00, 13:00 on a half day): AMC.
#   In between: during_session (hand-checked). On a non-session day: the
#   release was outside market hours. EDGAR is closed on two federal holidays
#   that are NYSE sessions (Columbus Day, Veterans Day): when D-1, D or D+1 is
#   one of them, the acceptance time is not read as timing.
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


def fetch_submissions(cik: str, raw_dir: Path, get=None, sleep=time.sleep) -> dict:
    """The submissions JSON of one company, from raw_dir()/edgar/ or (once) from EDGAR.

    The User-Agent is checked FIRST, before the cache or the network, so an
    unconfigured run fails the same way every time. `get` is requests.get by
    default; a test passes a recorder.
    """
    ua = user_agent()
    path = raw_dir / "edgar" / f"CIK{int(cik):010d}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    if get is None:
        import requests
        get = requests.get
    resp = get(submissions_url(cik), headers={"User-Agent": ua, "Accept-Encoding": "gzip, deflate"}, timeout=60)
    resp.raise_for_status()
    sleep(1.0 / MAX_PER_SECOND)
    doc = resp.json()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, sort_keys=True), encoding="utf-8")
    return doc


def item_202_filings(doc: dict) -> list[dict]:
    """The 8-K filings with Item 2.02 in the `recent` block: accession, accepted (UTC datetime)."""
    recent = doc["filings"]["recent"]
    out = []
    for form, items, acc, accepted in zip(recent["form"], recent["items"], recent["accessionNumber"],
                                          recent["acceptanceDateTime"]):
        if form != "8-K" or "2.02" not in [i.strip() for i in (items or "").split(",")]:
            continue
        when = datetime.strptime(accepted.replace("Z", ""), "%Y-%m-%dT%H:%M:%S.%f").replace(tzinfo=timezone.utc)
        out.append({"accession": acc, "accepted_utc": accepted, "accepted": when})
    return sorted(out, key=lambda f: f["accepted"])


def edgar_holidays(year: int) -> set[date]:
    """The two federal holidays on which NYSE trades but EDGAR is closed.

    Columbus Day: the second Monday of October. Veterans Day: 11 November,
    moved to the Friday before when it falls on a Saturday and to the Monday
    after on a Sunday.
    """
    oct1 = date(year, 10, 1)
    columbus = oct1 + timedelta(days=(7 - oct1.weekday()) % 7 + 7)
    vet = date(year, 11, 11)
    if vet.weekday() == 5:
        vet -= timedelta(days=1)
    elif vet.weekday() == 6:
        vet += timedelta(days=1)
    return {columbus, vet}


def read_acceptance(announce: date, filings: list[dict], sessions, close_time_et: dict) -> dict | None:
    """The EDGAR reading for a calendar event on `announce`, or None if no 8-K matches.

    Returns {accession, accepted_utc, ny_date, label} where label is BMO, AMC,
    during_session, outside_hours (a non-session day) or edgar_holiday (not
    read as timing; the press release decides).
    """
    window = {announce - timedelta(days=1), announce, announce + timedelta(days=1)}
    hits = [f for f in filings if f["accepted"].astimezone(NY).date() in window]
    if not hits:
        return None
    f = min(hits, key=lambda h: abs((h["accepted"].astimezone(NY).date() - announce).days))
    local = f["accepted"].astimezone(NY)
    d, hhmm = local.date(), local.strftime("%H:%M")
    if window & edgar_holidays(announce.year):
        label = "edgar_holiday"
    elif not sessions.is_session(d):
        label = "outside_hours"
    elif hhmm < "09:30":
        label = "BMO"
    elif hhmm >= close_time_et[d]:
        label = "AMC"
    else:
        label = "during_session"
    return {"accession": f["accession"], "accepted_utc": f["accepted_utc"], "ny_date": d, "label": label}
