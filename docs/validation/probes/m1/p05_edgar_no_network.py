"""p05: the EDGAR client makes no network request unless SEC_EDGAR_USER_AGENT holds a real contact (claim 4).

  uv run python docs/validation/probes/m1/p05_edgar_no_network.py

Every socket connect, getaddrinfo and requests.get is replaced by a recorder that
refuses, so no request can leave the machine even if the client were broken.
No request is ever made to sec.gov.
"""
import os
import socket
import tempfile
from pathlib import Path

ATTEMPTS = []


def _refuse(*a, **k):
    ATTEMPTS.append(a[:2])
    raise ConnectionRefusedError("probe: network blocked")


socket.socket.connect = _refuse
socket.socket.connect_ex = _refuse
socket.getaddrinfo = _refuse
socket.create_connection = _refuse

from earnings_vol.ingest import edgar  # noqa: E402

try:
    import requests  # noqa: E402
    requests.get = lambda *a, **k: _refuse(*a)
except ImportError:
    pass


def attempt(label, ua, cached):
    if ua is None:
        os.environ.pop(edgar.ENV, None)
    else:
        os.environ[edgar.ENV] = ua
    with tempfile.TemporaryDirectory() as d:
        raw = Path(d)
        if cached:
            (raw / "edgar").mkdir()
            (raw / "edgar" / "CIK0000320193.json").write_text("{}")
        before = len(ATTEMPTS)
        try:
            edgar.fetch_submissions("320193", raw)            # get=None: the real requests.get path
            res = "returned"
        except edgar.EdgarNotConfigured as e:
            res = f"EdgarNotConfigured ({str(e)[:50]})"
        except ConnectionRefusedError:
            res = "TRIED THE NETWORK"
        print(f"{label:52s} -> {res}; network attempts: {len(ATTEMPTS) - before}")


attempt("unset, no cache", None, False)
attempt("unset, cache present", None, True)
attempt("empty string", "", False)
attempt("whitespace", "   ", False)
attempt("no @", "Jane Doe research", False)
attempt("placeholder admin@example.org", "Jane admin@example.org", False)
attempt("placeholder x@test", "x@test", False)
attempt("placeholder x@localhost", "x@localhost", False)
attempt("RFC 2606 subdomain x@mail.example.com", "x@mail.example.com", False)
attempt("RFC 2606 TLD x@foo.example", "x@foo.example", False)
attempt("RFC 2606 TLD x@foo.test", "x@foo.test", False)
attempt("bare '@'", "@", False)
attempt("'a@b' (no domain dot)", "a@b", False)
attempt("real-looking (blocked here) owner@realdomain.net", "J Doe owner@realdomain.net", False)
os.environ.pop(edgar.ENV, None)
print("total network attempts:", len(ATTEMPTS))
