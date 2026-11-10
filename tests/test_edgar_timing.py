# SEC EDGAR as timing source 1 (ADR 0002 §3): the extra submission pages, the
# time zone of acceptanceDateTime, EDGAR's closed days, and the wiring into the
# events layer. Every value is hand-written: made-up CIKs, accession numbers,
# times and contacts. No request is made and no real company's data is read.
#
# Mutations this module must catch (applied by hand, each seen to fail, then
# restored and the file's SHA-256 checked; docs/validation/edgar-ledger.md §6):
#   M1 pages_needed without the PAGE_MARGIN_DAYS margin
#   M2 merge_filings keeping the first copy of an accession without comparing
#   M3 item_202_filings reading `recent` only (pages ignored)
#   M4 read_cached returning no pages
#   M5 parse_acceptance reading the string as New York wall time
#   M6 parse_acceptance without its format check
#   M7 edgar_holidays without the New Year's Eve rule
#   M8 read_acceptance looking up the holidays of D's year only
#   M9 read_acceptance without the several_8k check
#   M10 resolve_edgar confirming a contradiction (the 8-K's label used as `corrected`)
#   M11 resolve_edgar without the other-date check
#   M12 cached_item_202 reading the first CIK only
#   M13 run.build consulting EDGAR for no event (empty scope)
#   M14 run.edgar_scope without the press-release events
#   M15 fetch_universe putting the User-Agent in its record

import json
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import pytest
import yaml

from earnings_vol import params as params_mod
from earnings_vol.events import calendar, run, timing
from earnings_vol.ingest import edgar

UA = "Research Project owner@realdomain.net"   # made up, as in test_ingest_sources.py


def block(rows):
    """Parallel arrays in EDGAR's format from (accession, filingDate, acceptanceDateTime, form, items)."""
    keys = ["accessionNumber", "filingDate", "acceptanceDateTime", "form", "items"]
    return {k: [r[i] for r in rows] for i, k in enumerate(keys)}


def doc_with(recent, files=()):
    return {"filings": {"recent": block(recent), "files": list(files)}}


@pytest.fixture(scope="module")
def sess():
    t = calendar.build_session_table(date(2021, 1, 1), date(2026, 12, 31),
                                     {"weekly_from": "2019-02-09", "mwf_from": "2020-01-06",
                                      "daily_from": "2024-09-11", "data_end": "2026-10-26"})
    return calendar.Sessions(t["session_date"].tolist()), dict(zip(t["session_date"], t["close_time_et"]))


# --- the extra pages ----------------------------------------------------------------

def page_meta(n, frm, to, count=1):
    return {"name": f"CIK0000000042-submissions-{n:03d}.json", "filingCount": count, "filingFrom": frm, "filingTo": to}


def test_pages_needed_reaches_back_to_since_with_a_margin():
    doc = doc_with([], [page_meta(1, "2021-01-05", "2021-06-30"), page_meta(2, "2019-06-01", "2019-12-28"),
                        page_meta(3, "2018-01-01", "2019-05-31")])
    # Page 2's filingTo is 4 days before `since`, inside the 7-day margin: a page's last
    # filing can fall a day after its listed filingTo (measured), so it is read.
    assert edgar.pages_needed(doc, date(2020, 1, 1)) == ["CIK0000000042-submissions-001.json",
                                                         "CIK0000000042-submissions-002.json"]
    with pytest.raises(ValueError, match="page name"):
        edgar.pages_needed(doc_with([], [{"name": "../evil.json", "filingTo": "2025-01-01"}]), date(2020, 1, 1))


def test_merge_filings_keeps_each_accession_once_and_refuses_two_readings():
    recent = [("0000000042-25-000002", "2025-01-30", "2025-01-30T21:30:00.000Z", "8-K", "2.02,9.01"),
              ("0000000042-24-000009", "2024-10-31", "2024-10-31T20:30:00.000Z", "8-K", "2.02,9.01")]
    page = block([("0000000042-24-000009", "2024-10-31", "2024-10-31T20:30:00.000Z", "8-K", "2.02,9.01"),
                  ("0000000042-24-000001", "2024-08-01", "2024-08-01T20:30:00.000Z", "10-Q", "")])
    m = edgar.merge_filings(doc_with(recent), [page])
    assert m["accessionNumber"] == ["0000000042-25-000002", "0000000042-24-000009", "0000000042-24-000001"]
    clash = block([("0000000042-24-000009", "2024-10-31", "2024-10-31T21:30:00.000Z", "8-K", "2.02,9.01")])
    with pytest.raises(ValueError, match="listed twice"):
        edgar.merge_filings(doc_with(recent), [clash])


def test_an_8k_only_in_an_extra_page_is_found(sess):
    s, close = sess
    recent = [("0000000042-25-000002", "2025-01-30", "2025-01-30T21:30:00.000Z", "8-K", "2.02,9.01")]
    page = block([("0000000042-21-000007", "2021-04-29", "2021-04-29T20:05:00.000Z", "8-K", "2.02,9.01"),
                  ("0000000042-21-000006", "2021-04-20", "2021-04-20T20:05:00.000Z", "8-K", "5.07")])
    f = edgar.item_202_filings(doc_with(recent), [page])
    assert [x["accession"] for x in f] == ["0000000042-21-000007", "0000000042-25-000002"]
    r = edgar.read_acceptance(date(2021, 4, 29), f, s, close)
    assert (r["accession"], r["label"]) == ("0000000042-21-000007", "AMC")


class Resp:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


def test_fetch_all_caches_the_pages_and_read_cached_needs_no_network(monkeypatch, tmp_path):
    monkeypatch.setenv(edgar.ENV, UA)
    page = block([("0000000042-21-000007", "2021-04-29", "2021-04-29T20:05:00.000Z", "8-K", "2.02,9.01")])
    doc = doc_with([("0000000042-25-000002", "2025-01-30", "2025-01-30T21:30:00.000Z", "8-K", "2.02,9.01")],
                   [page_meta(1, "2021-04-29", "2021-04-29"), page_meta(2, "2015-01-01", "2016-12-31")])
    calls = []

    def get(url, **kw):
        calls.append(url)
        return Resp(page if url.endswith("-001.json") else doc)

    d, pages = edgar.fetch_all("42", tmp_path, date(2020, 1, 1), get=get, sleep=lambda s: None)
    assert calls == ["https://data.sec.gov/submissions/CIK0000000042.json",
                     "https://data.sec.gov/submissions/CIK0000000042-submissions-001.json"]   # page 2 is too old
    assert pages == [page]
    # The cache holds the files, and never the User-Agent.
    for f in (tmp_path / "edgar").iterdir():
        assert "realdomain" not in f.read_text()
    # Offline and without a User-Agent, the same filings come back from the cache.
    monkeypatch.delenv(edgar.ENV)
    d2, pages2 = edgar.read_cached("42", tmp_path, date(2020, 1, 1))
    assert (d2, pages2) == (doc, [page])
    assert len(edgar.item_202_filings(d2, pages2)) == 2
    (tmp_path / "edgar" / "CIK0000000042-submissions-001.json").unlink()
    with pytest.raises(FileNotFoundError):
        edgar.read_cached("42", tmp_path, date(2020, 1, 1))


def test_the_fetch_record_never_holds_the_user_agent(monkeypatch, tmp_path):
    monkeypatch.setenv(edgar.ENV, UA)
    doc = doc_with([("0000000042-25-000002", "2025-01-30", "2025-01-30T21:30:00.000Z", "8-K", "2.02,9.01")])
    rec = edgar.fetch_universe([("XYZ", "42")], tmp_path, get=lambda url, **kw: Resp(doc), sleep=lambda s: None,
                               log=lambda *a: None)
    assert rec["XYZ"]["requests_this_run"] == 1 and rec["XYZ"]["first_filing_date"] == "2025-01-30"
    text = json.dumps(rec)
    assert "realdomain" not in text and "@" not in text and "Research Project" not in text


# --- the time zone ------------------------------------------------------------------

def test_acceptance_time_is_a_utc_instant_across_daylight_saving(sess):
    s, close = sess
    # One habitual 16:30 New York release, in summer (EDT, UTC-4) and in winter (EST, UTC-5).
    summer = edgar.parse_acceptance("2025-07-31T20:30:25.000Z")
    winter = edgar.parse_acceptance("2025-01-30T21:30:23.000Z")
    assert summer.tzinfo == timezone.utc
    assert (summer.astimezone(edgar.NY).strftime("%H:%M"), winter.astimezone(edgar.NY).strftime("%H:%M")) == \
        ("16:30", "16:30")
    # A morning filing: 10:46 UTC is 06:46 EDT, before the open (read as New York time it
    # would be 10:46, inside the session).
    f = [{"accession": a, "accepted_utc": t, "accepted": edgar.parse_acceptance(t)}
         for a, t in [("m", "2024-10-11T10:46:00.000Z"), ("w", "2025-01-30T21:30:23.000Z")]]
    assert edgar.read_acceptance(date(2024, 10, 11), f, s, close)["label"] == "BMO"
    assert edgar.read_acceptance(date(2025, 1, 30), f, s, close)["label"] == "AMC"


@pytest.mark.parametrize("value", ["2024-10-11T10:46:00Z", "2024-10-11T10:46:00.5Z", "2024-10-11T10:46:00.000000Z",
                                   "2024-10-11T10:46:00.000-04:00", "2024-10-11 10:46:00.000Z", None])
def test_parse_acceptance_refuses_any_other_format(value):
    with pytest.raises(ValueError, match="unexpected acceptanceDateTime"):
        edgar.parse_acceptance(value)


# --- EDGAR's closed days and the window ---------------------------------------------------

def test_edgar_holidays_include_new_years_eve_and_the_measured_closures():
    assert {date(2021, 6, 18), date(2021, 12, 31)} <= edgar.edgar_holidays(2021)   # 2022-01-01 is a Saturday
    assert date(2027, 12, 31) in edgar.edgar_holidays(2027)                          # 2028-01-01 is a Saturday
    assert date(2022, 12, 31) not in edgar.edgar_holidays(2022)                      # 2023-01-01 is a Sunday
    assert {date(2025, 12, 24), date(2025, 12, 26)} <= edgar.edgar_holidays(2025)
    assert edgar.edgar_holidays(2026) == {date(2026, 10, 12), date(2026, 11, 11)}


def test_the_holiday_window_crosses_the_year(sess):
    s, close = sess
    # D is Saturday 2022-01-01; D-1, Friday 2021-12-31, was an EDGAR holiday (a made-up filing on it).
    f = [{"accession": "h", "accepted_utc": "2021-12-31T15:00:00.000Z",
          "accepted": edgar.parse_acceptance("2021-12-31T15:00:00.000Z")}]
    assert edgar.read_acceptance(date(2022, 1, 1), f, s, close)["label"] == "edgar_holiday"


def test_two_8ks_in_the_window_that_read_differently_are_not_read(sess):
    s, close = sess
    mk = lambda a, t: {"accession": a, "accepted_utc": t, "accepted": edgar.parse_acceptance(t)}  # noqa: E731
    two = [mk("a", "2025-04-24T11:00:00.000Z"), mk("b", "2025-04-24T20:30:00.000Z")]   # 07:00 and 16:30 EDT
    r = edgar.read_acceptance(date(2025, 4, 24), two, s, close)
    assert (r["label"], r["n_in_window"]) == ("several_8k", 2)
    same = [mk("a", "2025-04-24T11:00:00.000Z"), mk("b", "2025-04-24T12:30:00.000Z")]  # 07:00 and 08:30 EDT
    r = edgar.read_acceptance(date(2025, 4, 24), same, s, close)
    assert (r["label"], r["n_in_window"], r["accession"]) == ("BMO", 2, "a")


# --- the EDGAR rule: resolve_edgar ----------------------------------------------------------

def reading(d, label, acc="0000000042-25-000001"):
    return {"accession": acc, "accepted_utc": "2025-04-24T20:30:00.000Z", "ny_date": d, "label": label,
            "n_in_window": 1}


THU, FRI, SAT = date(2025, 4, 24), date(2025, 4, 25), date(2025, 4, 26)


@pytest.mark.parametrize("announce, raw, rd, status, used, source, outcome", [
    (THU, "AMC", None, "not_checked", "AMC", "calendar", "no_8k"),
    (THU, "AMC", reading(THU, "AMC"), "confirmed", "AMC", "edgar", "confirmed"),
    (THU, None, reading(THU, "BMO"), "inferred", "BMO", "edgar", "inferred"),
    # The 8-K contradicts the label: the press release must agree before it is `corrected`.
    (THU, "BMO", reading(THU, "AMC"), "not_checked", "BMO", "calendar", "contradicts"),
    # A BMO 8-K on D+1 for an AMC event on D gives the same day 0, but the date differs.
    (THU, "AMC", reading(FRI, "BMO"), "not_checked", "AMC", "calendar", "other_date"),
    (THU, None, reading(FRI, "BMO"), "not_checked", None, None, "other_date"),
    (THU, "BMO", reading(THU, "during_session"), "not_checked", "BMO", "calendar", "during_session"),
    (THU, "BMO", reading(THU, "edgar_holiday"), "not_checked", "BMO", "calendar", "edgar_holiday"),
    (THU, "BMO", reading(THU, "several_8k"), "not_checked", "BMO", "calendar", "several_8k"),
    # A non-session D (a made-up Saturday filing): only the date is checked, the label is kept.
    (SAT, None, reading(SAT, "outside_hours"), "confirmed", None, "edgar", "confirmed"),
    (SAT, "BMO", reading(SAT, "outside_hours"), "confirmed", "BMO", "edgar", "confirmed"),
])
def test_resolve_edgar_status_table(sess, announce, raw, rd, status, used, source, outcome):
    s, _ = sess
    t = timing.resolve_edgar(announce, raw, rd, s)
    assert (t["timing_status"], t["timing_used"], t["timing_source"], t["edgar_outcome"]) == \
        (status, used, source, outcome)
    assert t["announce_date_used"] == announce and t["gap_check_changed"] is False
    # The matched 8-K is recorded whatever it decided.
    assert t["edgar_accession"] == (rd["accession"] if rd else None)


def test_predecessor_ciks_are_read_with_the_current_one(monkeypatch, tmp_path):
    pred = edgar.parse_predecessors("security_id,predecessor_cik,evidence\nXYZ,0000000041,made-up succession\n")
    assert pred == {"XYZ": ["0000000041"]}
    for bad in ("security_id,predecessor_cik,evidence\nXYZ,41,x\n", "security_id,predecessor_cik,evidence\nXYZ,0000000041,\n",
                "security_id,cik\nXYZ,0000000041\n"):
        with pytest.raises(ValueError):
            edgar.parse_predecessors(bad)
    base = tmp_path / "edgar"
    base.mkdir()
    old = doc_with([("0000000041-21-000003", "2021-04-29", "2021-04-29T20:05:00.000Z", "8-K", "2.02")])
    new = doc_with([("0000000042-26-000001", "2026-07-30", "2026-07-30T20:05:00.000Z", "8-K", "2.02")])
    (base / "CIK0000000041.json").write_text(json.dumps(old))
    (base / "CIK0000000042.json").write_text(json.dumps(new))
    f = edgar.cached_item_202(["0000000042", *pred["XYZ"]], tmp_path)
    assert [x["accession"] for x in f] == ["0000000041-21-000003", "0000000042-26-000001"]
    with pytest.raises(ValueError, match="two of the CIKs"):
        edgar.cached_item_202(["0000000041", "0000000041"], tmp_path)


# --- the wiring: run.build with params timing.edgar --------------------------------------------
# A made-up company with five releases in the look-up era and no prices (so no gap trigger).

CAL = pd.DataFrame({
    "act_symbol": ["XYZ"] * 5,
    "date": [date(2024, 10, 24), date(2025, 1, 23), date(2025, 4, 24), date(2025, 7, 24), date(2025, 10, 23)],
    "when": ["After market close", None, "Before market open", "After market close", "After market close"],
}, dtype=object)
HIST = pd.DataFrame({"act_symbol": ["XYZ"] * 5,
                     "period_end_date": [date(2024, 9, 30), date(2024, 12, 31), date(2025, 3, 31), date(2025, 6, 30),
                                         date(2025, 9, 30)],
                     "reported": [1.0, 1.1, 1.2, 1.3, 1.4], "estimate": [1.0, 1.0, 1.0, 1.0, 1.0]})
CHECK = ("XYZ,2024-10-24,true,2024-10-24,16:05,time_stamp,AMC,https://example.com/release,company,"
         "https://example.com/release,2026-11-09,false,0.5,made-up row\n")
# Made-up Item 2.02 8-Ks: 10-24 16:10 EDT (the press-release event), 01-23 07:00 EST (NULL label),
# 04-24 16:05 EDT (the calendar says BMO), none for 07-24, 10-23 16:02 EDT.
FILINGS = doc_with([("0000000042-24-000010", "2024-10-24", "2024-10-24T20:10:00.000Z", "8-K", "2.02,9.01"),
                    ("0000000042-25-000001", "2025-01-23", "2025-01-23T12:00:00.000Z", "8-K", "2.02,9.01"),
                    ("0000000042-25-000004", "2025-04-24", "2025-04-24T20:05:00.000Z", "8-K", "2.02,9.01"),
                    ("0000000042-25-000009", "2025-10-23", "2025-10-23T20:02:00.000Z", "8-K", "2.02,9.01")])


def inputs(checks=CHECK):
    selection = pd.DataFrame({"security_id": ["XYZ"], "name": ["Made-up Co"], "gics_sector": ["Financials"],
                              "gics_sub_industry": ["Made-up"], "cik": ["42"], "in_universe": [True],
                              "cboe_vx_index": [None]})
    return {"commits": {"earnings": "e" * 32, "options": "o" * 32}, "selection": selection, "calendar": CAL,
            "eps_history": HIST,
            "eps_estimate": pd.DataFrame(columns=["date", "act_symbol", "period", "period_end_date", "consensus",
                                                  "count", "high", "low"]),
            "dtb3": pd.DataFrame({"date": [date(2015, 12, 31)], "value": [1.0]}),
            "vix": pd.DataFrame({"date": pd.Series([], dtype=object), "value": pd.Series([], dtype="float64")}),
            "checks_text": ",".join(timing.CHECK_COLUMNS) + "\n" + checks}


def no_prices(_symbol):
    return pd.DataFrame({"date": [], "open": [], "close": [], "dividends": []})


def params_edgar(tmp_path, on: bool):
    raw = yaml.safe_load(params_mod.DEFAULT_PATH.read_text(encoding="utf-8"))
    raw["timing"]["edgar"] = on
    path = tmp_path / "params.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return params_mod.load(path)


def test_build_with_edgar_resolves_only_what_the_rule_allows(tmp_path):
    asked = []

    def loader(sid):
        asked.append(sid)
        return edgar.item_202_filings(FILINGS)

    out = run.build(params_edgar(tmp_path, True), inputs(), no_prices, edgar_loader=loader)
    ev = out["events"].set_index("event_id")
    cols = ["timing_status", "timing_source", "timing_used", "edgar_accession", "day0_session"]
    got = {e: tuple(ev.loc[e, cols]) for e in ev.index}
    assert got == {
        # The press release decides; the matched 8-K is recorded.
        "XYZ:2024-10-24": ("confirmed", "press_release", "AMC", "0000000042-24-000010", date(2024, 10, 25)),
        # A NULL label gets the 8-K's timing: 07:00 EST is before the open.
        "XYZ:2025-01-23": ("inferred", "edgar", "BMO", "0000000042-25-000001", date(2025, 1, 23)),
        # The 8-K contradicts BMO: left for a press release, with the calendar label.
        "XYZ:2025-04-24": ("not_checked", "calendar", "BMO", "0000000042-25-000004", date(2025, 4, 24)),
        # No 8-K: left for a press release.
        "XYZ:2025-07-24": ("not_checked", "calendar", "AMC", None, date(2025, 7, 25)),
        "XYZ:2025-10-23": ("confirmed", "edgar", "AMC", "0000000042-25-000009", date(2025, 10, 24)),
    }
    assert out["edgar_outcome"] == {"XYZ:2024-10-24": "press_release", "XYZ:2025-01-23": "inferred",
                                    "XYZ:2025-04-24": "contradicts", "XYZ:2025-07-24": "no_8k",
                                    "XYZ:2025-10-23": "confirmed"}
    assert sorted(v["event_id"] for v in out["lookup_violations"]) == ["XYZ:2025-04-24", "XYZ:2025-07-24"]
    assert asked == ["XYZ"]
    rep = run.report(out, params_edgar(tmp_path, True))["edgar"]
    assert rep["outcome"] == {"confirmed": 1, "contradicts": 1, "inferred": 1, "no_8k": 1, "press_release": 1}
    assert rep["resolved_by_label"] == {"AMC": 1, "BMO": 1}


def test_build_without_edgar_never_reads_it(tmp_path):
    def loader(sid):
        raise AssertionError("EDGAR was read with params timing.edgar false")

    out = run.build(params_edgar(tmp_path, False), inputs(), no_prices, edgar_loader=loader)
    ev = out["events"]
    assert set(ev["timing_source"].dropna()) == {"press_release", "calendar"}
    assert ev["edgar_accession"].isna().all() and set(out["edgar_outcome"].values()) == {None}
    assert len(out["lookup_violations"]) == 4
    with pytest.raises(ValueError, match="no EDGAR loader"):
        run.build(params_edgar(tmp_path, True), inputs(), no_prices)
