# pd09 (claims 6a-6c): edgar.is_real_contact on reserved, malformed and real-world
# contact strings, and the zero-request property with sockets blocked.
#
# Run: uv run --frozen python docs/validation/probes/m1-delta/pd09_edgar_contact.py
import os
import socket
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "src"))
from earnings_vol.ingest import edgar  # noqa: E402

should_refuse = {
    # IANA special-use domain names (RFC 6761 registry) not in the coded list
    "RFC 8375 home.arpa": "Study x@router.home.arpa",
    "RFC 7686 .onion": "Study x@abcdefghijklmnop.onion",
    "RFC 9476 .alt": "Study x@foo.alt",
    "ICANN .internal (2024)": "Study x@corp.internal",
    "RFC 6762 local (control)": "Study x@printer.local",
    "RFC 2606 example.com (control)": "Study x@example.com",
    # Malformed local parts (RFC 5322 dot-atom: no leading/trailing/double dot)
    "leading dot": "Study .x@realdomain.net",
    "double dot": "Study x..y@realdomain.net",
    "trailing dot": "Study x.@realdomain.net",
    "local part only symbols": "Study %+-@realdomain.net",
    # Malformed domains
    "label > 63 chars": "Study x@" + "a" * 64 + ".com",
    "domain > 253 chars": "Study x@" + ".".join(["a" * 60] * 5) + ".com",
    # Obvious placeholders that are not RFC-reserved (out of the claim; recorded only)
    "placeholder yourdomain.com": "Study you@yourdomain.com",
    "placeholder email@domain.com": "Study email@domain.com",
}
should_accept = {
    "plain": "Earnings Study first.last@gmail.com",
    "sentence with full stop": "Earnings Study, contact first.last@gmail.com.",
    "angle brackets": "Earnings Study <first.last@gmail.com>",
    "apostrophe in local part": "Study o'brien@uni.edu",
    "IDN (punycode TLD)": "Study x@example-shop.xn--p1ai",
    "IDN (unicode local part)": "Study josé@uni.edu",
    "long new gTLD": "Study x@lab.photography",
    "SEC sample form": "Sample Company Name AdminContact@samplecompany.com",
}
print("== should be refused ==")
for k, v in should_refuse.items():
    print(f"  {'refused ' if not edgar.is_real_contact(v) else 'ACCEPTED'}  {k:34s} {v[:60]!r}")
print("== should be accepted ==")
for k, v in should_accept.items():
    print(f"  {'accepted' if edgar.is_real_contact(v) else 'REFUSED '}  {k:34s} {v[:60]!r}")

# 6c: zero requests with the variable unset; the default `get` (requests.get) path.
attempts = []


def blocked(*a, **k):
    attempts.append(a[:2])
    raise OSError("network blocked by probe")


socket.socket.connect = blocked
socket.create_connection = blocked
socket.getaddrinfo = blocked
import requests  # noqa: E402

requests.Session.request = lambda self, *a, **k: blocked(*a)
os.environ.pop(edgar.ENV, None)
outcomes = []
with tempfile.TemporaryDirectory() as tmp:
    for cik in ("320193", "0000320193"):
        try:
            edgar.fetch_submissions(cik, Path(tmp))
            outcomes.append("returned")
        except edgar.EdgarNotConfigured as e:
            outcomes.append("EdgarNotConfigured")
        except Exception as e:  # noqa: BLE001
            outcomes.append(type(e).__name__)
    # a cached file present: must still refuse (UA checked first)
    (Path(tmp) / "edgar").mkdir()
    (Path(tmp) / "edgar" / "CIK0000320193.json").write_text("{}")
    try:
        edgar.fetch_submissions("320193", Path(tmp))
        outcomes.append("cache returned")
    except edgar.EdgarNotConfigured:
        outcomes.append("EdgarNotConfigured (cache present)")
    # falsifier: a valid contact must reach the (blocked) network
    os.environ[edgar.ENV] = "Earnings Study first.last@gmail.com"
    try:
        edgar.fetch_submissions("789019", Path(tmp))
    except Exception as e:  # noqa: BLE001
        outcomes.append(f"with contact: {type(e).__name__}")
print("6c outcomes:", outcomes)
print("6c network attempts (all unset cases + the falsifier):", len(attempts))
