# Tests for src/earnings_vol/ingest/cboe.py: the five VX* addresses, the request budget, the header and the CSV
# parser. No network: a fake session answers. The CSV values are made up (no Cboe number appears here).
#
# Mutations this module must catch (each applied by hand, the test seen to fail, the file restored and its SHA-256
# compared; docs/validation/vx-ledger.md §4, script docs/validation/probes/vx/mutants.py):
#   - C01 url() accepting any symbol
#   - C02 fetch retrying a 404
#   - C03 fetch with MAX_RETRIES + 1 retries (a fourth attempt)
#   - C04 parse_history dropping a duplicate date instead of refusing the file
#   - C05 parse_history reading the dates day first (DD/MM/YYYY)
#   - C06 the User-Agent carrying a contact address

import hashlib

import pytest
import requests

from earnings_vol.ingest import cboe

CSV = (b"DATE,OPEN,HIGH,LOW,CLOSE\n"
       b"01/03/2030,25.10,25.20,24.00,24.50\n"
       b"01/02/2030,26.00,26.10,25.00,25.50\n"
       b"02/01/2030,30.00,31.00,29.50,30.25\n")


class Resp:
    def __init__(self, code, body=b"", history=()):
        self.status_code, self.content, self.history = code, body, list(history)
        self.url = "https://cdn-api.example.invalid/x.csv"


class Session:
    """Answers each get() with the next scripted response (or raises it)."""

    def __init__(self, script):
        self.script, self.calls = list(script), []

    def get(self, url, headers, timeout, allow_redirects):
        self.calls.append({"url": url, "headers": dict(headers), "allow_redirects": allow_redirects})
        nxt = self.script.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


def test_url_names_exactly_the_five_indices():
    assert cboe.SYMBOLS == ("VXAPL", "VXAZN", "VXGOG", "VXGS", "VXIBM")
    assert cboe.url("VXGOG") == "https://cdn.cboe.com/api/global/us_indices/daily_prices/VXGOG_History.csv"
    with pytest.raises(ValueError):
        cboe.url("VIX")


def test_fetch_follows_the_redirect_and_sends_a_generic_user_agent():
    s = Session([Resp(200, CSV, history=[Resp(307)])])
    body, rec = cboe.fetch("VXAPL", s, sleep=lambda x: None)
    assert body == CSV and rec["attempts"] == 1 and rec["hops"] == [307, 200]
    [call] = s.calls
    assert call["allow_redirects"] is True
    assert call["headers"] == {"User-Agent": "earnings-vol-study/0.5 (research; "
                                             "+https://github.com/rajib2k5/earnings-vol-study)"}
    assert "@" not in call["headers"]["User-Agent"]          # no e-mail address


def test_fetch_retries_twice_at_most_and_never_on_a_client_error():
    waits = []
    s = Session([Resp(503), requests.ConnectionError("down"), Resp(200, CSV)])
    _, rec = cboe.fetch("VXIBM", s, sleep=waits.append)
    assert rec["attempts"] == 3 and waits == [5.0, 15.0]
    s = Session([Resp(503), Resp(429), Resp(500), Resp(200, CSV)])
    with pytest.raises(RuntimeError, match="after 3 attempt"):
        cboe.fetch("VXIBM", s, sleep=lambda x: None)
    assert len(s.calls) == 3
    s = Session([Resp(404), Resp(200, CSV)])
    with pytest.raises(RuntimeError, match="after 1 attempt"):
        cboe.fetch("VXIBM", s, sleep=lambda x: None)
    assert len(s.calls) == 1


def test_parse_history_reads_month_first_dates_and_sorts():
    df = cboe.parse_history(CSV.decode())
    assert [str(d) for d in df["date"]] == ["2030-01-02", "2030-01-03", "2030-02-01"]
    assert df["close"].tolist() == [25.5, 24.5, 30.25]


@pytest.mark.parametrize("text, match", [
    ("DATE,CLOSE\n01/02/2030,25.5\n01/02/2030,26.0\n", "duplicate"),
    ("DATE,OPEN\n01/02/2030,25.5\n", "unexpected Cboe columns"),
    ("DATE,CLOSE\n01/02/2030,n/a\n", "Unable to parse"),
])
def test_parse_history_refuses_a_broken_file(text, match):
    with pytest.raises(ValueError, match=match):
        cboe.parse_history(text)


def test_download_all_writes_each_file_and_describes_it(tmp_path):
    s = Session([Resp(200, CSV, history=[Resp(307)])])
    rec = cboe.download_all(tmp_path / "cboe", symbols=("VXGS",), session=s, log=lambda *a: None)
    path = tmp_path / "cboe" / "VXGS.csv"
    assert path.read_bytes() == CSV
    r = rec["VXGS"]
    assert (r["sha256"], r["bytes"], r["rows"]) == (hashlib.sha256(CSV).hexdigest(), len(CSV), 3)
    assert (r["first"], r["last"], r["attempts"]) == ("2030-01-02", "2030-02-01", 1)
    assert cboe.load("VXGS", tmp_path / "cboe")["close"].tolist() == [25.5, 24.5, 30.25]
