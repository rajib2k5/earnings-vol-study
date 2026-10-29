# Tests for src/earnings_vol/contract.py. The React app expects exactly five
# keys and schema_version "0.4.0", so these tests pin both.

import math
from datetime import datetime, timedelta, timezone, tzinfo

import pytest

from earnings_vol import contract

# 12:00 UTC on 27 Oct 2026 (the base time for these tests).
NOON_UTC = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)


def make(**overrides):
    args = dict(kind="demo", data={"a": 1}, generated_at=NOON_UTC, source_commit="abc1234")
    args.update(overrides)
    return contract.envelope(args.pop("kind"), args.pop("data"), **args)


def test_schema_version_is_what_the_app_expects():
    assert contract.SCHEMA_VERSION == "0.4.0"


def test_envelope_has_exactly_the_five_keys():
    env = make()
    assert set(env) == {"schema_version", "kind", "generated_at", "source_commit", "data"}


def test_envelope_values():
    env = make(data={"answer": 42})
    assert env["schema_version"] == "0.4.0"
    assert env["kind"] == "demo"
    assert env["source_commit"] == "abc1234"
    assert env["data"] == {"answer": 42}


def test_generated_at_utc_input_ends_with_z():
    assert make()["generated_at"] == "2026-10-27T12:00:00Z"


def test_generated_at_converted_from_plus_two_hours():
    # 14:00 at +02:00 is two hours ahead of UTC: 14:00 - 2:00 = 12:00 UTC.
    two_hours_east = timezone(timedelta(hours=2))
    when = datetime(2026, 10, 27, 14, 0, tzinfo=two_hours_east)
    assert make(generated_at=when)["generated_at"] == "2026-10-27T12:00:00Z"


def test_generated_at_converted_from_minus_five_hours_crosses_midnight():
    # 22:30 at -05:00 is five hours behind UTC: 22:30 + 5:00 = 27:30 = 03:30
    # on the next day (28 Oct).
    five_hours_west = timezone(timedelta(hours=-5))
    when = datetime(2026, 10, 27, 22, 30, tzinfo=five_hours_west)
    assert make(generated_at=when)["generated_at"] == "2026-10-28T03:30:00Z"


def test_generated_at_drops_fractions_of_a_second():
    when = datetime(2026, 10, 27, 12, 0, 0, 999999, tzinfo=timezone.utc)
    assert make(generated_at=when)["generated_at"] == "2026-10-27T12:00:00Z"


def test_naive_datetime_is_rejected():
    naive = datetime(2026, 10, 27, 12, 0)  # no tzinfo
    with pytest.raises(ValueError, match="timezone-aware"):
        make(generated_at=naive)


def test_datetime_whose_timezone_gives_no_offset_is_rejected():
    # Python calls a datetime "naive" also when its tzinfo returns None for
    # the offset. It has a tzinfo object, but still no usable offset.
    class NoOffset(tzinfo):
        def utcoffset(self, dt):
            return None

    with pytest.raises(ValueError, match="timezone-aware"):
        make(generated_at=datetime(2026, 10, 27, 12, 0, tzinfo=NoOffset()))


def test_dumps_exact_text_sorted_keys_indent_two_trailing_newline():
    # Keys are sorted: data, generated_at, kind, schema_version, source_commit.
    # Inside "data" the keys are sorted too: "a" before "b".
    env = make(data={"b": 2, "a": 1})
    expected = (
        "{\n"
        '  "data": {\n'
        '    "a": 1,\n'
        '    "b": 2\n'
        "  },\n"
        '  "generated_at": "2026-10-27T12:00:00Z",\n'
        '  "kind": "demo",\n'
        '  "schema_version": "0.4.0",\n'
        '  "source_commit": "abc1234"\n'
        "}\n"
    )
    assert contract.dumps(env) == expected


def test_dumps_is_stable():
    # Same content, different insertion order: the text must be identical.
    one = make(data={"x": 1, "y": 2})
    two = make(data={"y": 2, "x": 1})
    assert contract.dumps(one) == contract.dumps(two)
    assert contract.dumps(one) == contract.dumps(one)


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_dumps_rejects_nan_and_infinity(bad):
    # JSON cannot write these. Python's default writes a bare NaN token,
    # which the browser's JSON.parse rejects with a SyntaxError.
    with pytest.raises(ValueError):
        contract.dumps(make(data={"x": bad}))


def test_dumps_rejects_nan_nested_deep_in_data():
    with pytest.raises(ValueError):
        contract.dumps(make(data={"rows": [{"iv": 0.3}, {"iv": math.nan}]}))


@pytest.mark.parametrize("bad", [5, None, "", b"demo", ["demo"]])
def test_envelope_rejects_a_kind_that_is_not_a_non_empty_str(bad):
    with pytest.raises(TypeError, match="kind"):
        make(kind=bad)


@pytest.mark.parametrize("bad", [5, None, "", b"abc1234", ["abc1234"]])
def test_envelope_rejects_a_source_commit_that_is_not_a_non_empty_str(bad):
    with pytest.raises(TypeError, match="source_commit"):
        make(source_commit=bad)


@pytest.mark.parametrize("bad", [[], [("a", 1)], None, "text", 5, (1, 2)])
def test_envelope_rejects_data_that_is_not_a_dict(bad):
    # The app rejects a list or a null as `data` (contract.ts), so we refuse it
    # here, at export, instead of writing a file that the browser will not load.
    with pytest.raises(TypeError, match="data"):
        make(data=bad)


def test_envelope_accepts_an_empty_dict_as_data():
    assert make(data={})["data"] == {}


def test_dumps_accepts_the_largest_integers_that_javascript_holds_exactly():
    # 2**53 = 9007199254740992, so 2**53 - 1 = 9007199254740991 is the last whole
    # number a JavaScript number holds exactly. Its negative is also fine.
    text = contract.dumps(make(data={"hi": 9007199254740991, "lo": -9007199254740991}))
    assert '"hi": 9007199254740991' in text
    assert '"lo": -9007199254740991' in text


@pytest.mark.parametrize("bad", [
    9007199254740992,    # 2**53: the first integer that is too big
    -9007199254740992,   # -(2**53): the same on the negative side
    2**64,               # 18446744073709551616, arrives in the app as ...552000
    10**400,             # more than 308 digits: arrives in the app as Infinity
])
def test_dumps_rejects_integers_that_javascript_cannot_hold_exactly(bad):
    with pytest.raises(ValueError, match=r"2\*\*53"):
        contract.dumps(make(data={"x": bad}))


def test_dumps_rejects_a_too_big_integer_nested_deep_in_data():
    with pytest.raises(ValueError, match=r"2\*\*53"):
        contract.dumps(make(data={"rows": [{"n": 1}, {"n": [9007199254740992]}]}))


def test_dumps_does_not_check_floats():
    # 1e22 is a float, and JSON.parse reads a float as the same float. Only whole
    # numbers written without "." or "e" lose digits.
    assert '"x": 1e+22' in contract.dumps(make(data={"x": 1e22}))
