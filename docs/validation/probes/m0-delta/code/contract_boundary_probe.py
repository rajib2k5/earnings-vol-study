"""M0 delta review, claim 8c: envelope() type checks and the 2**53 rule in dumps().

Usage:
    python contract_boundary_probe.py <repo-root>

Imports earnings_vol.contract from <repo-root>/src (read only: nothing is written).
Run with PYTHONDONTWRITEBYTECODE=1 against the real repo. Prints one line per case:
ACCEPT (with the JSON value written) or REJECT (exception type and message).
"""
import collections
import json
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(sys.argv[1]).resolve() / "src"))
from earnings_vol import contract  # noqa: E402

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None

NOON = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)


def env(data):
    return contract.envelope("probe", data, generated_at=NOON, source_commit="abc1234")


def show(label, fn):
    try:
        out = fn()
        if isinstance(out, str) and out.startswith("{"):
            body = json.loads(out)["data"]
            out = json.dumps(body)[:90]
        print(f"ACCEPT  {label:52s} -> {out}")
    except Exception as e:  # noqa: BLE001 - we want to print any exception
        print(f"REJECT  {label:52s} -> {type(e).__name__}: {str(e)[:90]}")


M = 2**53
print("== dumps(): integer boundary")
for label, value in [
    ("2**53 - 1", M - 1), ("2**53", M), ("2**53 + 1", M + 1),
    ("-(2**53 - 1)", -(M - 1)), ("-(2**53)", -M), ("-(2**53) - 1", -M - 1),
    ("0", 0), ("-0 (int)", -0),
    ("10**400", 10**400), ("-10**400", -(10**400)),
    ("10**5000 (beyond int->str limit)", 10**5000),
]:
    show(label, lambda v=value: contract.dumps(env({"x": v})))

print("== dumps(): position of the integer")
show("2**53 nested in list in dict in list", lambda: contract.dumps(env({"r": [{"a": [1, M]}]})))
show("2**53 inside a tuple", lambda: contract.dumps(env({"t": (1, M)})))
show("2**64 as a dict KEY (json writes it as a string)", lambda: contract.dumps(env({2**64: "k"})))
show("2**53-1 as a dict key", lambda: contract.dumps(env({M - 1: "k"})))

print("== dumps(): types that are or look like integers")
show("True (bool is an int subclass)", lambda: contract.dumps(env({"b": True})))
show("False", lambda: contract.dumps(env({"b": False})))
if np is not None:
    show("numpy int64(5)", lambda: contract.dumps(env({"n": np.int64(5)})))
    show("numpy int64(2**60)", lambda: contract.dumps(env({"n": np.int64(2**60)})))
    show("numpy float64(1e20)", lambda: contract.dumps(env({"n": np.float64(1e20)})))
show("Decimal('1')", lambda: contract.dumps(env({"d": Decimal("1")})))


class BigIntSubclass(int):
    pass


show("int subclass holding 2**53", lambda: contract.dumps(env({"s": BigIntSubclass(M)})))

print("== dumps(): floats (not checked by design)")
for label, value in [
    ("1e16", 1e16), ("9007199254740993.0 (float of 2**53+1)", 9007199254740993.0),
    ("1e+20", 1e20), ("1e22", 1e22), ("2.0**60", 2.0**60), ("1.7976931348623157e308", 1.7976931348623157e308),
]:
    show(label, lambda v=value: contract.dumps(env({"f": v})))

print("== dumps(): strings that contain digits (no false rejection expected)")
show('{"note": "id 99999999999999999999"}', lambda: contract.dumps(env({"note": "id 99999999999999999999"})))
show('{"n": "9007199254740992"} (digits as string)', lambda: contract.dumps(env({"n": "9007199254740992"})))
show('key "99999999999999999999" (string key)', lambda: contract.dumps(env({"99999999999999999999": 1})))

print("== envelope(): types")
for label, kw in [
    ("kind=5", dict(kind=5)), ("kind=''", dict(kind="")), ("kind=b'meta'", dict(kind=b"meta")),
    ("kind=str subclass", dict(kind=type("S", (str,), {})("meta"))),
    ("source_commit=None", dict(source_commit=None)), ("source_commit=''", dict(source_commit="")),
    ("source_commit=12345 (int)", dict(source_commit=12345)),
    ("data=[]", dict(data=[])), ("data=None", dict(data=None)),
    ("data=OrderedDict()", dict(data=collections.OrderedDict(a=1))),
    ("data=collections.UserDict()", dict(data=collections.UserDict(a=1))),
    ("generated_at='2026-10-27T12:00:00Z' (str)", dict(generated_at="2026-10-27T12:00:00Z")),
    ("generated_at=date(2026,10,27)", dict(generated_at=date(2026, 10, 27))),
    ("generated_at=None", dict(generated_at=None)),
]:
    args = dict(kind="probe", data={"a": 1}, generated_at=NOON, source_commit="abc1234")
    args.update(kw)
    show(label, lambda a=args: "envelope ok, kind=%r data=%r" % (lambda e: (e["kind"], e["data"]))(contract.envelope(a.pop("kind"), a.pop("data"), **a)))

print("== parse_int sees the minus sign? (CPython json scanner detail)")
seen = []
json.loads('[-12, 34, {"k": -9007199254740992}]', parse_int=lambda s: seen.append(s) or int(s))
print("parse_int received:", seen)
