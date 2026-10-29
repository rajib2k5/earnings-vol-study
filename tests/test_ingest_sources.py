# Tests for the small ingest modules, all on hand-written fixtures and with no
# network: wikipedia.py (the constituents parser), universe.py (the selection
# rule and the ticker aliases), fred.py (the CSV parser), prices.py (undoing
# later splits) and edgar.py (refuses to run without the owner's contact; the
# acceptance-time reading).
#
# Mutations this module must catch (applied by hand, each seen to fail):
#   - parse_constituents reading only the one-cell-per-line layout
#   - select_universe ranking smallest first
#   - select_universe letting a force_include name in when it is not eligible
#   - build_security keeping the Yahoo market-cap rank (universe_rank)
#   - split_factor_after including the row's own split
#   - user_agent() returning a default when the variable is unset
#   - is_real_contact matching reserved domains only at the top level (x@mail.example.com)
#   - is_real_contact without the two-label domain rule (a@b)
#   - is_real_contact without home.arpa, .onion, .alt or .internal (delta review, claim 6a)
#   - is_real_contact without the local-part dot rule, the 63-character label
#     limit or the 253-character domain limit (each removed alone)
#   - read_acceptance ignoring the EDGAR holiday rule

from datetime import date, datetime, timezone

import pandas as pd
import pytest

from earnings_vol import schema, store
from earnings_vol.events import calendar, securities
from earnings_vol.ingest import edgar, fred, prices, universe, wikipedia

WIKITEXT = """intro text
{| class="wikitable sortable" id="constituents"
|-
![[Ticker symbol|Symbol]]
! Security !! GICS Sector !! GICS Sub-Industry !! Headquarters Location !! Date added !! CIK !! Founded
|-
|| {{NyseSymbol|MMM}}
|| [[3M]]
|| Industrials
|| Industrial Conglomerates
|| [[Saint Paul, Minnesota]]
|| 1957-03-04
|| 0000066740
|| 1902
|-
|| {{NasdaqSymbol|AMD}}
|| [[AMD|Advanced Micro Devices]]
|| Information Technology
|| Semiconductors
|| [[Santa Clara, California]]
|| 2017-03-20
|| 0000002488
|| 1969
|-
|| {{NyseSymbol|EME}}
||  [[Emcor]]|| Industrials
|| Construction & Engineering
|| [[Norwalk, Connecticut]]
|| 2025-09-22
|| 105634
|| 1994
|-
|| {{BZX link|CBOE}}
|| [[Cboe Global Markets]]
|| Financials
|| Financial Exchanges & Data
|| [[Chicago]], Illinois
|| 2017-03-01
|| 0001374310
|1973
|}
after the table
"""


def test_parse_constituents_reads_both_layouts():
    df = wikipedia.parse_constituents(WIKITEXT)
    assert df["symbol"].tolist() == ["MMM", "AMD", "EME", "CBOE"]
    assert df.loc[1, "name"] == "Advanced Micro Devices"          # [[AMD|Advanced Micro Devices]] -> the label
    assert df.loc[2, ["name", "gics_sector"]].tolist() == ["Emcor", "Industrials"]   # cells on one line
    assert df.loc[2, "cik"] == "0000105634"                         # padded to 10 digits
    assert df.loc[3, "gics_sub_industry"] == "Financial Exchanges & Data"


def test_parse_constituents_refuses_a_missing_table_and_duplicates():
    with pytest.raises(ValueError, match="constituents"):
        wikipedia.parse_constituents("no table here")
    dup = WIKITEXT.replace("{{NasdaqSymbol|AMD}}", "{{NyseSymbol|MMM}}")
    with pytest.raises(ValueError, match="duplicate"):
        wikipedia.parse_constituents(dup)


CONSTITUENTS = pd.DataFrame({
    "symbol": ["AAPL", "GOOGL", "GOOG", "XOM", "GS", "TINY", "NOOPT"],
    "name": list("abcdefg"), "gics_sector": ["Information Technology"] * 7,
    "gics_sub_industry": ["x"] * 7, "cik": [None] * 7,
})
CAPS = pd.DataFrame({"symbol": ["AAPL", "GOOGL", "GOOG", "XOM", "GS", "TINY", "NOOPT"],
                     "market_cap_yf": [500.0, 400.0, 390.0, 300.0, 100.0, 50.0, 999.0]})
ELIGIBLE = {"AAPL", "GOOGL", "GOOG", "XOM", "GS", "TINY"}               # NOOPT has no options


def test_select_universe_ranks_eligible_companies_and_adds_forced_names():
    sel = universe.select_universe(CONSTITUENTS, CAPS, ELIGIBLE, n_largest=2, force_include=["GS"],
                                   drop_share_classes=["GOOG"]).set_index("security_id")
    # GOOG is dropped before ranking; NOOPT is not eligible (no rank, although the largest).
    assert "GOOG" not in sel.index and sel.loc["NOOPT", "universe_rank"] is None
    # Ranks by cap among the eligible: AAPL 500 (1), GOOGL 400 (2), XOM 300 (3), GS 100 (4), TINY 50 (5).
    assert [sel.loc[s, "universe_rank"] for s in ("AAPL", "GOOGL", "XOM", "GS", "TINY")] == [1, 2, 3, 4, 5]
    # n_largest = 2 keeps AAPL and GOOGL; GS is forced in; XOM (rank 3) is out.
    assert sorted(sel.index[sel["in_universe"]]) == ["AAPL", "GOOGL", "GS"]
    assert sel.loc["GOOGL", "cboe_vx_index"] == "VXGOG" and pd.isna(sel.loc["XOM", "cboe_vx_index"])


def test_select_universe_refuses_a_forced_name_that_is_not_eligible():
    with pytest.raises(ValueError, match="not eligible"):
        universe.select_universe(CONSTITUENTS, CAPS, ELIGIBLE, n_largest=2, force_include=["NOOPT"],
                                 drop_share_classes=[])


def test_the_committed_security_table_carries_no_yahoo_rank():
    # The selection ranks by Yahoo market cap. That rank is a per-row Yahoo-derived number for
    # ~500 firms, so the `security` table (committed) keeps only the in/out label
    # (milestone-1 review, claim 10); the rank stays in the local selection.
    sel = universe.select_universe(CONSTITUENTS, CAPS, ELIGIBLE, n_largest=2, force_include=["GS"],
                                   drop_share_classes=["GOOG"])
    assert "universe_rank" in sel.columns
    sec = securities.build_security(sel)
    assert list(sec.columns) == list(schema.SECURITY.names)
    assert "universe_rank" not in sec.columns
    store.validate(sec, schema.SECURITY)
    assert sorted(sec.loc[sec["in_universe"], "security_id"]) == ["AAPL", "GOOGL", "GS"]


def test_alias_rows_and_source_tickers():
    rows = universe.alias_rows(["META", "AAPL"])
    assert rows == [
        {"ticker": "AAPL", "valid_from": date(2016, 1, 1), "valid_to": None, "security_id": "AAPL"},
        {"ticker": "FB", "valid_from": date(2012, 5, 18), "valid_to": date(2022, 6, 8), "security_id": "META"},
        {"ticker": "META", "valid_from": date(2022, 6, 9), "valid_to": None, "security_id": "META"},
    ]
    assert universe.source_tickers(["RTX", "META"]) == ["FB", "META", "RTX", "UTX"]
    assert universe.yahoo_symbol("BRK.B") == "BRK-B"


def test_fred_parser_keeps_missing_days_missing():
    # Made-up values in FRED's layout (not the real VIX closes of those dates).
    text = "observation_date,VIXCLS\n2025-04-17,12.34\n2025-04-18,\n2025-04-21,23.45\n"
    df = fred.parse_series(text, "VIXCLS")
    assert df["date"].tolist() == [date(2025, 4, 17), date(2025, 4, 18), date(2025, 4, 21)]
    assert df["value"].iloc[0] == 12.34 and pd.isna(df["value"].iloc[1]) and df["value"].iloc[2] == 23.45
    with pytest.raises(ValueError, match="unexpected FRED columns"):
        fred.parse_series(text, "DTB3")


def test_split_factor_after_undoes_only_later_splits():
    # A 10-for-1 split on day 3 (Yahoo writes 10.0 in `splits` on that day).
    # Yahoo divided every earlier price by 10, so rows 1 and 2 get factor 10 and
    # rows 3 and 4 get 1.
    df = pd.DataFrame({"date": [date(2025, 11, d) for d in (13, 14, 17, 18)],
                       "close": [110.0, 111.0, 112.0, 113.0], "splits": [0.0, 0.0, 10.0, 0.0]})
    assert prices.split_factor_after(df).tolist() == [10.0, 10.0, 1.0, 1.0]
    assert prices.asof_close(df).tolist() == [1100.0, 1110.0, 112.0, 113.0]
    # Two splits multiply: 2-for-1 then 3-for-1 -> 6, 3, 1.
    df2 = df.assign(splits=[0.0, 2.0, 0.0, 3.0])
    assert prices.split_factor_after(df2).tolist() == [6.0, 3.0, 3.0, 1.0]


# --- EDGAR: refuses without the owner's contact, and no request is ever made ------

class Recorder:
    def __init__(self):
        self.calls = []

    def __call__(self, url, **kw):
        self.calls.append((url, kw))
        raise AssertionError("a request was attempted")


@pytest.mark.parametrize("value", [
    None, "", "   ", "earnings-vol-study admin@example.org", "someone@example.com", "no email here",
    # Reserved subdomains and top-level domains, and malformed contacts (milestone-1 review, claim 4):
    "x@mail.example.com", "x@foo.example", "x@foo.test", "x@test", "x@localhost", "x@host.invalid",
    "x@printer.local", "Study x@EXAMPLE.NET", "@", "a@b", "x@corp", "a@", "@b.com", "x@-bad.com", "x@foo.c0m",
    "Study owner@realdomain.net and admin@example.org",   # one real, one placeholder
    "Study owner@realdomain.net @",                       # a stray "@"
    # Special-use names (RFC 8375, 7686, 9476; .internal, ICANN 2024) and malformed addresses
    # (delta review, claim 6a):
    "x@router.home.arpa", "x@abcdefghijklmnop.onion", "x@foo.alt", "x@corp.internal",
    ".x@realdomain.net", "x.@realdomain.net", "x..y@realdomain.net",
    "x@" + "a" * 64 + ".com",                                             # a label of 64 characters
    "x@" + "a" * 63 + "." + "b" * 63 + "." + "c" * 63 + "." + "d" * 58 + ".com",   # a domain of 254
    # Real addresses refused on purpose (documented in is_real_contact: it fails closed):
    "Study, contact first.last@gmail.com.", "x@example-shop.xn--p1ai", "jos\u00e9@uni.edu",
])
def test_edgar_refuses_without_a_real_contact_and_makes_no_request(monkeypatch, tmp_path, value):
    if value is None:
        monkeypatch.delenv(edgar.ENV, raising=False)
    else:
        monkeypatch.setenv(edgar.ENV, value)
    rec = Recorder()
    with pytest.raises(edgar.EdgarNotConfigured):
        edgar.fetch_submissions("1234567", tmp_path, get=rec, sleep=lambda s: None)
    assert rec.calls == []
    assert not (tmp_path / "edgar").exists()


@pytest.mark.parametrize("value", ["Research Project owner@realdomain.net", "Name <first.last+sec@uni.ac.uk>",
                                   "lab contact@sub.realdomain.org", "x.y@arpa-research.net",
                                   "x@" + "a" * 63 + ".com",                                   # a 63-character label
                                   "x@" + "a" * 63 + "." + "b" * 63 + "." + "c" * 63 + "." + "d" * 57 + ".com"])
def test_edgar_accepts_a_well_formed_contact(value):
    assert edgar.is_real_contact(value)


def test_edgar_sends_the_owners_user_agent_once_and_caches(monkeypatch, tmp_path):
    monkeypatch.setenv(edgar.ENV, "Research Project owner@realdomain.net")

    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return FIXTURE

    calls = []
    doc = edgar.fetch_submissions("1234567", tmp_path, get=lambda url, **kw: calls.append((url, kw)) or Resp(),
                                  sleep=lambda s: None)
    assert doc == FIXTURE and len(calls) == 1
    assert calls[0][0] == "https://data.sec.gov/submissions/CIK0001234567.json"
    assert calls[0][1]["headers"]["User-Agent"] == "Research Project owner@realdomain.net"
    edgar.fetch_submissions("1234567", tmp_path, get=lambda *a, **k: 1 / 0, sleep=lambda s: None)  # cached


# A hand-written submissions file in EDGAR's format, with made-up accession
# numbers. The first filing's time mirrors the GOOGL time quoted in ADR 0002 §3
# (20:01:46 UTC = 16:01:46 EDT).
FIXTURE = {"filings": {"recent": {
    "form": ["8-K", "10-Q", "8-K", "8-K", "8-K"],
    "items": ["2.02,9.01", "", "5.02", "2.02,9.01", "2.02"],
    "accessionNumber": ["9999999999-24-999999", "q", "x", "y", "z"],
    "acceptanceDateTime": ["2024-10-29T20:01:46.000Z", "2024-10-30T10:00:00.000Z", "2024-11-01T12:00:00.000Z",
                           "2025-10-14T11:15:00.000Z", "2025-04-24T14:00:00.000Z"],
}}}


@pytest.fixture(scope="module")
def sess():
    t = calendar.build_session_table(date(2024, 1, 1), date(2025, 12, 31),
                                     {"weekly_from": "2019-02-09", "mwf_from": "2020-01-06",
                                      "daily_from": "2024-09-11", "data_end": "2026-10-26"})
    return calendar.Sessions(t["session_date"].tolist()), dict(zip(t["session_date"], t["close_time_et"]))


def test_edgar_item_202_filter():
    f = edgar.item_202_filings(FIXTURE)
    assert [x["accession"] for x in f] == ["9999999999-24-999999", "z", "y"]   # 10-Q and 5.02 dropped, sorted
    assert f[0]["accepted"] == datetime(2024, 10, 29, 20, 1, 46, tzinfo=timezone.utc)


def test_edgar_reading_of_acceptance_times(sess):
    s, close = sess
    f = edgar.item_202_filings(FIXTURE)
    # GOOGL 2024-10-29: 20:01:46 UTC is 16:01 EDT (UTC-4) on a full session -> AMC.
    r = edgar.read_acceptance(date(2024, 10, 29), f, s, close)
    assert (r["label"], r["ny_date"], r["accession"]) == ("AMC", date(2024, 10, 29), "9999999999-24-999999")
    # 2025-04-24 14:00 UTC is 10:00 EDT: inside the session -> hand-checked.
    assert edgar.read_acceptance(date(2025, 4, 24), f, s, close)["label"] == "during_session"
    # 2025-10-14 11:15 UTC is 07:15 EDT, but 2025-10-13 (D-1) is Columbus Day:
    # EDGAR was closed, so the time is not read as timing.
    assert edgar.read_acceptance(date(2025, 10, 14), f, s, close)["label"] == "edgar_holiday"
    # No 8-K within D-1 .. D+1.
    assert edgar.read_acceptance(date(2024, 6, 1), f, s, close) is None


def test_edgar_holidays():
    # Columbus Day = second Monday of October; Veterans Day 11-11 (2023: Saturday -> Friday 11-10).
    assert edgar.edgar_holidays(2025) == {date(2025, 10, 13), date(2025, 11, 11)}
    assert edgar.edgar_holidays(2024) == {date(2024, 10, 14), date(2024, 11, 11)}
    assert edgar.edgar_holidays(2023) == {date(2023, 10, 9), date(2023, 11, 10)}
