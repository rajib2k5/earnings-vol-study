"""Shared helpers for the Channel B probes. Reads only the local cache; no network.
Run as:  python -B -I <probe>.py   (the probe inserts this directory and src/ in sys.path)."""
import json, sys, collections
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path("/home/rajib2k5/dev/earnings-vol-study")
RAW = Path("/home/rajib2k5/data/vol-projects/earnings-vol-study/raw")
EDG = RAW / "edgar"
sys.path.insert(0, str(REPO / "src"))
from earnings_vol.ingest import edgar  # code under test  # noqa: E402

NY = ZoneInfo("America/New_York")
UTC = timezone.utc
SECS = json.loads((EDG / "fetch_log.json").read_text())["securities"]


def ciks_for(sid):
    return [v["cik"] for k, v in SECS.items() if k == sid or k.startswith(sid + " (")]


def sessions():
    import pandas as pd
    s = pd.read_parquet(REPO / "data/derived/session.parquet")
    return {d: c for d, c in zip(s["session_date"], s["close_time_et"])}


def label_indep(local, closes):
    """Independent session label: BMO < 09:30, AMC >= close, else during; non-session -> outside."""
    d, hhmm = local.date(), local.strftime("%H:%M")
    if d not in closes:
        return "outside_hours"
    if hhmm < "09:30":
        return "BMO"
    return "AMC" if hhmm >= closes[d] else "during_session"


def wall_as_ny(raw):
    """The mutant reading, computed independently of the code: EDGAR's wall clock taken as New York time."""
    return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=NY)


def all_8k_rows():
    """(sid, accession, form, items, acceptanceDateTime string, filingDate) for every 8-K row of every CIK,
    via the code's own read_cached + merge_filings (so a read-only-recent mutant shows)."""
    out, seen = [], set()
    for sid, v in SECS.items():
        doc, pages = edgar.read_cached(v["cik"], RAW, edgar.SINCE)
        m = edgar.merge_filings(doc, pages)
        for form, items, acc, at, fd in zip(m["form"], m["items"], m["accessionNumber"],
                                            m["acceptanceDateTime"], m["filingDate"]):
            if acc in seen:
                continue
            seen.add(acc)
            out.append((sid, acc, form, items, at, fd))
    return out


def filingdate_consistency(local_of):
    """Weekday 8-Ks: accepted before 17:30 NY -> filingDate == that NY date; at/after 17:30 -> filingDate later.
    local_of(raw_string) -> aware NY datetime under the reading being tested."""
    c = collections.Counter()
    bad = []
    for sid, acc, form, items, at, fd in all_8k_rows():
        if form != "8-K":
            continue
        l = local_of(at)
        if l.weekday() >= 5:
            c["weekend_skipped"] += 1
            continue
        fdd = date.fromisoformat(fd)
        after = l.time() >= time(17, 30)
        ok = (fdd > l.date()) if after else (fdd == l.date())
        c[("after" if after else "before", ok)] += 1
        if not ok:
            bad.append((sid, at, fd, l.strftime("%F %T")))
    nb = c[("before", True)] + c[("before", False)]
    na = c[("after", True)] + c[("after", False)]
    return {"before_n": nb, "before_ok": c[("before", True)], "after_n": na, "after_ok": c[("after", True)],
            "weekend_skipped": c["weekend_skipped"],
            "before_rate": c[("before", True)] / nb if nb else 0.0, "after_rate": c[("after", True)] / na if na else 0.0,
            "violations": bad}
