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
# and, for params timing.edgar_coarse (docs/validation/edgar-coarse-ledger.md):
#   MC1 run.coarse_scope returning no event
#   MC2 run.coarse_scope without its sample filter (a release before coarse is read)
#   MC3 a contradiction left off the press-release list (EDGAR_WAIT_FOR_RELEASE)
#   MC4 resolve_edgar taking the 8-K's label on a contradiction (day 0 moves)
#   MC5 run.build reading coarse_scope instead of, not as well as, the default rule's look-ups
#   MC6 run.build ignoring edgar_coarse: false
#   MC7 events.build_events letting EDGAR decide where a press release was read

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


def inputs(checks=CHECK, cal=CAL, hist=HIST):
    selection = pd.DataFrame({"security_id": ["XYZ"], "name": ["Made-up Co"], "gics_sector": ["Financials"],
                              "gics_sub_industry": ["Made-up"], "cik": ["42"], "in_universe": [True],
                              "cboe_vx_index": [None]})
    return {"commits": {"earnings": "e" * 32, "options": "o" * 32}, "selection": selection, "calendar": cal,
            "eps_history": hist,
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


# --- coarse: EDGAR labels the events the default rule leaves not_checked ------------------------
# Owner decision 2026-11-17 (ADR 0002, dated note; params timing.edgar_coarse): EDGAR is also read
# for every `coarse` event that the default rule leaves not_checked. resolve_edgar's rules do not
# change: only `confirmed` (and `inferred` for a NULL label) set a label. A contradiction or an 8-K
# on another date keeps the calendar label and day 0, and is listed for a press-release check.
#
# A made-up company: one release before the coarse sample starts (sample none), five coarse ones
# (the 2024-04-25 row has no label, so the default rule already requires it), one mixed and two
# daily. No prices, so no gap trigger: the four labelled coarse rows need no look-up by default.

COARSE_CAL = pd.DataFrame({
    "act_symbol": ["XYZ"] * 9,
    "date": [date(2020, 2, 13), date(2023, 4, 27), date(2023, 7, 27), date(2023, 10, 26), date(2024, 1, 25),
             date(2024, 4, 25), date(2024, 10, 24), date(2025, 4, 24), date(2025, 7, 24)],
    "when": ["After market close", "After market close", "Before market open", "After market close",
             "After market close", None, "After market close", "Before market open", "After market close"],
}, dtype=object)
COARSE_HIST = pd.DataFrame({
    "act_symbol": ["XYZ"] * 9,
    "period_end_date": [date(2019, 12, 31), date(2023, 3, 31), date(2023, 6, 30), date(2023, 9, 30),
                        date(2023, 12, 31), date(2024, 3, 31), date(2024, 9, 30), date(2025, 3, 31),
                        date(2025, 6, 30)],
    "reported": [1.0] * 9, "estimate": [1.0] * 9})
# Made-up Item 2.02 8-Ks. 2020-02-13 16:05 EST (not consulted: sample none); 2023-04-27 16:05 EDT
# (agrees with AMC); 2023-07-27 16:05 EDT (contradicts BMO); 2023-10-27 07:00 EDT (the day after
# the calendar's 10-26); none near 2024-01-25; 2024-04-25 16:05 EDT (NULL label); 2024-10-24
# 16:10 EDT (mixed); 2025-04-24 16:05 EDT (contradicts the daily BMO); none near 2025-07-24.
COARSE_FILINGS = doc_with([
    ("0000000042-20-000001", "2020-02-13", "2020-02-13T21:05:00.000Z", "8-K", "2.02,9.01"),
    ("0000000042-23-000002", "2023-04-27", "2023-04-27T20:05:00.000Z", "8-K", "2.02,9.01"),
    ("0000000042-23-000005", "2023-07-27", "2023-07-27T20:05:00.000Z", "8-K", "2.02,9.01"),
    ("0000000042-23-000008", "2023-10-27", "2023-10-27T11:00:00.000Z", "8-K", "2.02,9.01"),
    ("0000000042-24-000003", "2024-04-25", "2024-04-25T20:05:00.000Z", "8-K", "2.02,9.01"),
    ("0000000042-24-000010", "2024-10-24", "2024-10-24T20:10:00.000Z", "8-K", "2.02,9.01"),
    ("0000000042-25-000004", "2025-04-24", "2025-04-24T20:05:00.000Z", "8-K", "2.02,9.01")])

COLS = ["timing_status", "timing_source", "timing_used", "edgar_accession", "day0_session"]


def params_timing(tmp_path, **timing_keys):
    """params.yaml with the timing keys given; a value of None removes the key."""
    raw = yaml.safe_load(params_mod.DEFAULT_PATH.read_text(encoding="utf-8"))
    for k, v in timing_keys.items():
        if v is None:
            raw["timing"].pop(k, None)
        else:
            raw["timing"][k] = v
    path = tmp_path / f"params-{len(list(tmp_path.iterdir()))}.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return params_mod.load(path)


def build_coarse(tmp_path, coarse, checks=""):
    p = params_timing(tmp_path, edgar=True, edgar_coarse=coarse)
    out = run.build(p, inputs(checks, COARSE_CAL, COARSE_HIST), no_prices,
                    edgar_loader=lambda sid: edgar.item_202_filings(COARSE_FILINGS))
    return out, p


def rows(out):
    ev = out["events"].set_index("event_id")
    return {e: tuple(ev.loc[e, COLS]) for e in ev.index}


# The rows that the switch must not touch: the default rule's look-ups (2024-04-25 coarse,
# 2024-10-24 mixed, 2025-04-24 and 2025-07-24 daily) and the release before the coarse sample.
UNTOUCHED = {
    "XYZ:2020-02-13": ("not_checked", "calendar", "AMC", None, date(2020, 2, 14)),
    "XYZ:2024-04-25": ("inferred", "edgar", "AMC", "0000000042-24-000003", date(2024, 4, 26)),
    "XYZ:2024-10-24": ("confirmed", "edgar", "AMC", "0000000042-24-000010", date(2024, 10, 25)),
    "XYZ:2025-04-24": ("not_checked", "calendar", "BMO", "0000000042-25-000004", date(2025, 4, 24)),
    "XYZ:2025-07-24": ("not_checked", "calendar", "AMC", None, date(2025, 7, 25)),
}


def test_coarse_events_with_a_matching_8k_are_confirmed_by_edgar(tmp_path):
    out, p = build_coarse(tmp_path, True)
    got = rows(out)
    assert got["XYZ:2023-04-27"] == ("confirmed", "edgar", "AMC", "0000000042-23-000002", date(2023, 4, 28))
    # No 8-K near D: the calendar label stays, not_checked, which coarse still allows.
    assert got["XYZ:2024-01-25"] == ("not_checked", "calendar", "AMC", None, date(2024, 1, 26))
    assert {e: got[e] for e in UNTOUCHED} == UNTOUCHED
    # Consulted: the default rule's look-ups and the four labelled coarse rows; not the release
    # before the coarse sample, whose matching 8-K would otherwise confirm it.
    assert out["edgar_outcome"] == {
        "XYZ:2020-02-13": None, "XYZ:2023-04-27": "confirmed", "XYZ:2023-07-27": "contradicts",
        "XYZ:2023-10-26": "other_date", "XYZ:2024-01-25": "no_8k", "XYZ:2024-04-25": "inferred",
        "XYZ:2024-10-24": "confirmed", "XYZ:2025-04-24": "contradicts", "XYZ:2025-07-24": "no_8k"}
    # The build invariant is unchanged: coarse rows left not_checked are not violations.
    assert sorted(v["event_id"] for v in out["lookup_violations"]) == ["XYZ:2025-04-24", "XYZ:2025-07-24"]
    rep = run.report(out, p)["edgar"]
    assert rep["coarse"] is True and rep["consulted"] == 8
    assert rep["outcome"] == {"confirmed": 2, "contradicts": 2, "inferred": 1, "no_8k": 2, "other_date": 1}


def test_a_coarse_contradiction_keeps_the_calendar_label_and_waits_for_a_press_release(tmp_path):
    on, p = build_coarse(tmp_path, True)
    off, _ = build_coarse(tmp_path, False)
    got, before = rows(on), rows(off)
    for e, outcome in (("XYZ:2023-07-27", "contradicts"), ("XYZ:2023-10-26", "other_date")):
        assert on["edgar_outcome"][e] == outcome
        # The 8-K is recorded, but the label, its source and day 0 are the calendar's, as without EDGAR.
        assert got[e][:3] == before[e][:3] == (("not_checked", "calendar", "BMO") if outcome == "contradicts"
                                               else ("not_checked", "calendar", "AMC"))
        assert got[e][4] == before[e][4]
        assert got[e][3] is not None
    assert got["XYZ:2023-07-27"][4] == date(2023, 7, 27)
    # Listed for a press-release check, with the daily contradiction the default rule already requires.
    assert on["edgar_press_release_checks"] == ["XYZ:2023-07-27", "XYZ:2023-10-26", "XYZ:2025-04-24"]
    assert run.report(on, p)["edgar"]["press_release_checks"] == {
        "n": 3, "by_outcome": {"contradicts": {"coarse": 1, "daily": 1}, "other_date": {"coarse": 1}}}


def test_the_coarse_switch_leaves_daily_and_mixed_as_they_were(tmp_path):
    on, _ = build_coarse(tmp_path, True)
    off, _ = build_coarse(tmp_path, False)
    for s in ("daily", "mixed"):
        a = on["events"][on["events"]["sample"] == s].reset_index(drop=True)
        b = off["events"][off["events"]["sample"] == s].reset_index(drop=True)
        assert len(a) > 0
        pd.testing.assert_frame_equal(a, b)
        ids = a["event_id"].tolist()
        assert {e: on["edgar_outcome"][e] for e in ids} == {e: off["edgar_outcome"][e] for e in ids}
    pd.testing.assert_frame_equal(on["eps"], off["eps"])
    assert on["lookup_violations"] == off["lookup_violations"]
    assert on["edgar_pending_gap_checks"] == off["edgar_pending_gap_checks"]
    # And the switch does act, on coarse only (else the equalities above would prove nothing).
    changed = sorted(e for e in rows(on) if rows(on)[e] != rows(off)[e])
    assert changed == ["XYZ:2023-04-27", "XYZ:2023-07-27", "XYZ:2023-10-26"]


def test_the_coarse_switch_off_gives_the_old_output(tmp_path):
    off, p_off = build_coarse(tmp_path, False)
    absent, _ = build_coarse(tmp_path, None)
    for k in ("events", "eps", "timing_check"):
        pd.testing.assert_frame_equal(off[k], absent[k])
    for k in ("edgar_outcome", "lookup_violations", "edgar_pending_gap_checks", "edgar_press_release_checks"):
        assert off[k] == absent[k]
    # The output before the switch existed: EDGAR read only for the default rule's look-ups.
    got = rows(off)
    assert {e: got[e] for e in UNTOUCHED} == UNTOUCHED
    assert {e: got[e] for e in ("XYZ:2023-04-27", "XYZ:2023-07-27", "XYZ:2023-10-26", "XYZ:2024-01-25")} == {
        "XYZ:2023-04-27": ("not_checked", "calendar", "AMC", None, date(2023, 4, 28)),
        "XYZ:2023-07-27": ("not_checked", "calendar", "BMO", None, date(2023, 7, 27)),
        "XYZ:2023-10-26": ("not_checked", "calendar", "AMC", None, date(2023, 10, 27)),
        "XYZ:2024-01-25": ("not_checked", "calendar", "AMC", None, date(2024, 1, 26))}
    assert {e for e, o in off["edgar_outcome"].items() if o is not None} == {
        "XYZ:2024-04-25", "XYZ:2024-10-24", "XYZ:2025-04-24", "XYZ:2025-07-24"}
    assert off["edgar_press_release_checks"] == ["XYZ:2025-04-24"]
    assert run.report(off, p_off)["edgar"]["coarse"] is False


COARSE_CHECKS = (
    # The release says 07:00, before the open, although the calendar and the 8-K say AMC.
    "XYZ,2023-04-27,true,2023-04-27,07:00,time_stamp,BMO,https://example.com/q1,company,"
    "https://example.com/q1,2026-11-17,false,0.5,made-up row\n"
    # The release agrees with the 8-K against the calendar's BMO.
    "XYZ,2023-07-27,true,2023-07-27,16:05,time_stamp,AMC,https://example.com/q2,company,"
    "https://example.com/q2,2026-11-17,false,0.5,made-up row\n")


def test_a_press_release_still_decides_in_coarse(tmp_path):
    out, _ = build_coarse(tmp_path, True, COARSE_CHECKS)
    got = rows(out)
    assert got["XYZ:2023-04-27"] == ("corrected", "press_release", "BMO", "0000000042-23-000002", date(2023, 4, 27))
    assert got["XYZ:2023-07-27"] == ("corrected", "press_release", "AMC", "0000000042-23-000005", date(2023, 7, 28))
    assert out["edgar_outcome"]["XYZ:2023-04-27"] == out["edgar_outcome"]["XYZ:2023-07-27"] == "press_release"
    # A contradiction a release has settled is no longer listed.
    assert out["edgar_press_release_checks"] == ["XYZ:2023-10-26", "XYZ:2025-04-24"]
