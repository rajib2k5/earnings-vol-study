"""C4.x probe for src/earnings_vol/contract.py. Run with the project's interpreter:
    uv run python docs/validation/probes/m0-code/contract_py_probe.py
Prints one line per case: input -> output or exception. Also writes the emitted
envelopes to the path in $PY_ENVELOPES_OUT (JSON lines) for the TypeScript side (C5.1).
"""
import json
import math
import os
from datetime import datetime, timedelta, timezone, tzinfo
from decimal import Decimal
from zoneinfo import ZoneInfo

import numpy as np

from earnings_vol import contract

def show(label, fn):
    try:
        out = fn()
        print(f"{label:58s} -> {out!r}")
        return out
    except Exception as e:
        print(f"{label:58s} -> RAISES {type(e).__name__}: {e}")
        return None

base = dict(generated_at=datetime(2026, 10, 27, 12, tzinfo=timezone.utc), source_commit="abc1234")
print("== C4.1 keys")
show("sorted keys", lambda: sorted(contract.envelope("meta", {}, **base)))

print("== C4.2 generated_at")
class NoOffset(tzinfo):
    def utcoffset(self, dt): return None
cases = {
    "utc": datetime(2026, 10, 27, 12, tzinfo=timezone.utc),
    "+02:00": datetime(2026, 10, 27, 14, tzinfo=timezone(timedelta(hours=2))),
    "+05:45 (Kathmandu)": datetime(2026, 10, 27, 17, 45, tzinfo=timezone(timedelta(hours=5, minutes=45))),
    "+00:00:30 seconds offset": datetime(2026, 10, 27, 12, 0, 30, tzinfo=timezone(timedelta(seconds=30))),
    "NY DST fold=0 01:30": datetime(2026, 11, 1, 1, 30, tzinfo=ZoneInfo("America/New_York")),
    "NY DST fold=1 01:30": datetime(2026, 11, 1, 1, 30, fold=1, tzinfo=ZoneInfo("America/New_York")),
    "microseconds .999999": datetime(2026, 10, 27, 12, 0, 0, 999999, tzinfo=timezone.utc),
    "year 999": datetime(999, 1, 1, tzinfo=timezone.utc),
    "year 1": datetime(1, 1, 1, tzinfo=timezone.utc),
    "naive": datetime(2026, 10, 27, 12),
    "tzinfo returning None": datetime(2026, 10, 27, 12, tzinfo=NoOffset()),
}
emitted = []
for k, v in cases.items():
    env = show(k, lambda v=v: contract.envelope("meta", {"milestone": 0}, generated_at=v, source_commit="abc1234")["generated_at"])
    if env is not None:
        emitted.append({"case": f"time {k}", "text": contract.dumps(contract.envelope("meta", {"milestone": 0}, generated_at=v, source_commit="abc1234"))})

print("== C4.3 dumps non-finite")
for label, val in [("float nan", math.nan), ("float inf", math.inf), ("float -inf", -math.inf),
                   ("np.float64 nan", np.float64("nan")), ("np.float32 nan", np.float32("nan")),
                   ("Decimal NaN", Decimal("NaN")), ("nan in tuple", (1.0, math.nan)),
                   ("nan as dict KEY", {math.nan: 1}), ("inf as dict KEY", {math.inf: 1}),
                   ("int 2**64", 2**64), ("int 10**400", 10**400), ("float 1e308", 1e308)]:
    out = show(label, lambda val=val: contract.dumps(contract.envelope("meta", {"x": val}, **base)))
    if out is not None:
        emitted.append({"case": f"value {label}", "text": out})

print("== type checks the Python side does NOT do (C5.1 asymmetry)")
for label, kind, data, commit in [("data is a list", "meta", [1, 2], "abc"), ("kind is int", 5, {}, "abc"),
                                  ("source_commit None", "meta", {}, None), ("data None", "meta", None, "abc")]:
    out = show(label, lambda kind=kind, data=data, commit=commit: contract.dumps(
        contract.envelope(kind, data, generated_at=base["generated_at"], source_commit=commit)))
    if out is not None:
        emitted.append({"case": f"pytype {label}", "text": out})

print("== C4.4 default json.dumps on NaN")
show("json.dumps(float('nan'))", lambda: json.dumps(float("nan")))
show("json.dumps({'x': inf})", lambda: json.dumps({"x": math.inf}))

out = os.environ.get("PY_ENVELOPES_OUT")
if out:
    with open(out, "w") as f:
        for e in emitted:
            f.write(json.dumps(e) + "\n")
    print("wrote", len(emitted), "emitted envelopes to $PY_ENVELOPES_OUT")
