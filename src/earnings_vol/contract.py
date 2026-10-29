# =============================================================================
# contract.py — The JSON "envelope" that Python gives to the React app.
#
# WHY AN ENVELOPE
#   The app only draws charts. It never computes. Python writes JSON files, the
#   app reads them. Every file has the same five keys, so the app can check
#   them in one place:
#
#     schema_version  which version of this contract wrote the file
#     kind            what the data is, e.g. "meta"
#     generated_at    when Python wrote it (ISO-8601, UTC, ends with "Z")
#     source_commit   the git commit of the code that wrote it
#     data            the content itself
#
#   If we change the shape of the envelope, we change SCHEMA_VERSION, and the
#   app can refuse files it does not understand.
# =============================================================================

import json
from datetime import datetime, timezone

# 0.2.0 (milestone 1): meta.json gained sample, params, files and provenance,
# and sample_funnel.json is new. The version covers the whole contract, so
# every file moves to it together (ADR 0001 §4).
SCHEMA_VERSION = "0.2.0"

# The largest whole number that a JavaScript number (a 64-bit float) holds
# exactly: 2**53 - 1. Above it, JSON.parse silently rounds an integer to the
# nearest float it can hold, so the app would draw a number Python never wrote.
MAX_SAFE_INT = 2**53 - 1


def envelope(kind: str, data: dict, *, generated_at: datetime, source_commit: str) -> dict:
    """Wrap `data` in the five-key envelope.

    We do NOT read the clock here. The caller passes `generated_at`, so a test
    can pass a fixed time and get the same output every run.
    """
    # The app refuses an envelope with the wrong types (contract.ts). Check them
    # here too, so the mistake fails at export and not in the browser.
    if not isinstance(kind, str) or not kind:
        raise TypeError(f"kind must be a non-empty str, got {kind!r}")
    if not isinstance(source_commit, str) or not source_commit:
        raise TypeError(f"source_commit must be a non-empty str, got {source_commit!r}")
    if not isinstance(data, dict):
        raise TypeError(f"data must be a dict, got {type(data).__name__}")

    # A datetime with no time zone is ambiguous: 14:00 in which city? Refuse
    # it, instead of guessing and writing a wrong "Z" time.
    if generated_at.tzinfo is None or generated_at.utcoffset() is None:
        raise ValueError("generated_at must be timezone-aware (naive datetime given)")

    # Convert to UTC first (14:00+02:00 is 12:00 UTC), then print with a "Z".
    utc = generated_at.astimezone(timezone.utc)
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": kind,
        "generated_at": utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_commit": source_commit,
        "data": data,
    }


def dumps(env: dict) -> str:
    """Turn an envelope into JSON text.

    allow_nan=False makes NaN and infinity raise an error. JSON has no way to
    write them: by default Python writes the bare token NaN, which the app's
    JSON.parse rejects with a SyntaxError. We prefer the error here, at export.
    sort_keys=True makes the text identical for the same data, so git diffs
    only show real changes.

    A whole number larger than MAX_SAFE_INT (in either direction) raises an
    error too. JSON can write it, but JavaScript cannot hold it exactly: the
    app would read a rounded number, or "Infinity" for a number with more than
    308 digits.
    """
    text = json.dumps(env, allow_nan=False, sort_keys=True, indent=2) + "\n"
    # Read the text back with json's own parser. It calls `parse_int` once for
    # every whole number in the text, at any depth, so we need no walk of our own.
    # (A number written with a "." or an "e", like 1e22, is a float: it is not
    # checked here.)
    json.loads(text, parse_int=_check_safe_int)
    return text


def _check_safe_int(digits: str) -> int:
    """Return int(digits), or raise ValueError if JavaScript cannot hold it exactly."""
    number = int(digits)
    if abs(number) > MAX_SAFE_INT:
        raise ValueError(
            f"integer {digits} is outside +-(2**53 - 1) = +-{MAX_SAFE_INT}: "
            "a JavaScript number cannot hold it exactly"
        )
    return number
