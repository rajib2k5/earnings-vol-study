# Tests for src/earnings_vol/events/events.py and securities.py on a small
# hand-built calendar: ticker resolution, timing, day 0, links, samples and
# exclusion reasons, and the look-up invariant.
#
# Mutations this module must catch (applied by hand, each seen to fail):
#   - resolve_on ignoring valid_to (an FB row after 2022-06-08 still resolving)
#   - sample decided by announce_date even when day 0 exists
#   - exclusion order: outside_samples checked before timing reasons
#   - enforce_lookup_invariant never raising
#   - a gap left between the sample ranges (coarse ending 2024-09-09 again)
#   - check_sample_ranges accepting a gap or an overlap
#   - finish_events without the duplicate_row branch (the duplicate becomes
#     timing_not_checked)
#   - duplicate_rows grouping with < instead of <= within_days
#   - duplicate_rows keeping the first of two equally supported rows instead
#     of stopping
#   - duplicate_rows ranking a press-release reading like a calendar label

from datetime import date

import pandas as pd
import pytest

from earnings_vol.events import calendar, events, securities
from earnings_vol.ingest import universe

ERAS = {"weekly_from": "2019-02-09", "mwf_from": "2020-01-06", "daily_from": "2024-09-11",
        "data_end": "2026-10-26"}
RANGES = {"daily": (date(2024, 12, 5), date(2026, 10, 26)), "mixed": (date(2024, 9, 12), date(2024, 12, 4)),
          "coarse": (date(2020, 4, 1), date(2024, 9, 11))}


@pytest.fixture(scope="module")
def sessions():
    t = calendar.build_session_table(date(2016, 1, 1), date(2027, 12, 31), ERAS)
    return calendar.Sessions(t["session_date"].tolist())


ALIASES = securities.build_ticker_alias(universe.alias_rows(["META", "AAPL", "RTX"]))


def test_alias_table():
    a = ALIASES.set_index("ticker")
    assert a.loc["FB", "valid_to"] == date(2022, 6, 8) and a.loc["META", "valid_from"] == date(2022, 6, 9)
    assert a.loc["UTX", "security_id"] == "RTX" and a.loc["RTX", "valid_from"] == date(2020, 4, 3)
    assert a.loc["AAPL", "valid_from"] == date(2016, 1, 1) and a.loc["AAPL", "valid_to"] is None


def test_resolve_on_uses_the_validity_dates():
    assert securities.resolve_on("FB", date(2022, 4, 27), ALIASES) == "META"
    assert securities.resolve_on("FB", date(2022, 6, 9), ALIASES) is None      # FB no longer valid
    assert securities.resolve_on("META", date(2022, 7, 27), ALIASES) == "META"
    assert securities.resolve_on("UTX", date(2020, 1, 28), ALIASES) == "RTX"
    assert securities.resolve_any("FB", ALIASES) == "META"
    assert securities.resolve_on("NOPE", date(2022, 1, 3), ALIASES) is None


CAL = pd.DataFrame({
    "act_symbol": ["FB", "META", "AAPL", "AAPL", "AAPL", "AAPL", "ZZZZ"],
    "date": [date(2022, 4, 27), date(2022, 7, 27), date(2024, 10, 31), date(2025, 1, 30), date(2025, 5, 1),
             date(2026, 11, 5), date(2025, 1, 30)],
    "when": ["After market close", "After market close", "After market close", None, "After market close",
             "After market close", "Before market open"],
}, dtype=object)


def build(sessions, checks=None):
    base = events.base_events(CAL, ALIASES, {"META", "AAPL"})
    checks = checks if checks is not None else pd.DataFrame(
        columns=["security_id", "announce_date", "found", "release_date", "label", "reread", "checked_on"])
    ev = events.build_events(base, checks, sessions, calendar_commit="c" * 32, sample_ranges=RANGES,
                             duplicate_days=14)
    empty_eps = pd.DataFrame(columns=["security_id", "fiscal_period_end", "event_id", "match_status"])
    return events.finish_events(ev, empty_eps, {}, sessions, (-60, 10)).set_index("event_id")


def test_base_events_resolve_and_filter(sessions):
    base = events.base_events(CAL, ALIASES, {"META", "AAPL"})
    # ZZZZ is not in the universe; FB 2022-04-27 becomes a META event.
    assert list(base["event_id"]) == ["AAPL:2024-10-31", "AAPL:2025-01-30", "AAPL:2025-05-01", "AAPL:2026-11-05",
                                      "META:2022-04-27", "META:2022-07-27"]
    assert base.set_index("event_id").loc["META:2022-04-27", "ticker_at_event"] == "FB"


def test_two_rows_giving_one_event_are_refused():
    cal = pd.DataFrame({"act_symbol": ["FB", "META"], "date": [date(2022, 4, 27)] * 2,
                        "when": ["After market close"] * 2}, dtype=object)
    aliases = securities.build_ticker_alias(universe.alias_rows(["META"])).copy()
    aliases.loc[aliases["ticker"] == "META", "valid_from"] = date(2016, 1, 1)   # overlap on purpose
    with pytest.raises(ValueError, match="two calendar rows"):
        events.base_events(cal, aliases, {"META"})


def test_day0_sample_links_and_exclusions(sessions):
    ev = build(sessions)
    # AAPL 2024-10-31 (Thu) AMC: day 0 Fri 11-01, inside the mixed range (09-12 .. 12-04).
    a = ev.loc["AAPL:2024-10-31"]
    assert (a["day0_session"], a["day_m1_session"], a["sample"], a["season"]) == \
        (date(2024, 11, 1), date(2024, 10, 31), "mixed", "2024Q4")
    assert a["prev_event_id"] is None and a["next_event_id"] == "AAPL:2025-01-30"
    # AAPL 2025-01-30 has no label, nobody looked it up, and it is a session day:
    # day 0 cannot be placed, so it is excluded (timing_not_checked).
    b = ev.loc["AAPL:2025-01-30"]
    assert b["day0_session"] is None and b["timing_status"] == "not_checked"
    assert b["exclusion_reason"] == "timing_not_checked"
    assert b["gap_sessions_prev"] is None
    # AAPL 2025-05-01 AMC: day 0 Fri 05-02 (daily). Its previous event has no day 0.
    c = ev.loc["AAPL:2025-05-01"]
    assert (c["day0_session"], c["sample"], c["exclusion_reason"]) == (date(2025, 5, 2), "daily", None)
    # A scheduled date after the data end: day 0 11-06 is outside every range.
    assert ev.loc["AAPL:2026-11-05", "exclusion_reason"] == "outside_samples"
    # META 2022-04-27 (filed as FB) and 2022-07-27, both AMC: day 0s 04-28 and 07-28.
    # Sessions after 04-28 up to and including 07-28: April 29 (1); May 21 (22 weekdays,
    # Memorial Day 05-30 closed); June 21 (22 weekdays, Juneteenth 06-20 closed); July 1-28
    # 19 (20 weekdays, 07-04 closed). 1 + 21 + 21 + 19 = 62.
    m = ev.loc["META:2022-07-27"]
    assert m["gap_sessions_prev"] == 62
    assert ev.loc["META:2022-04-27", "ticker_at_event"] == "FB"


def test_a_press_release_reading_changes_day0(sessions):
    checks = pd.DataFrame({"security_id": ["AAPL"], "announce_date": [date(2025, 1, 30)], "found": [True],
                           "release_date": [date(2025, 1, 30)], "label": ["AMC"], "reread": [False],
                           "checked_on": [date(2026, 10, 29)]}, dtype=object)
    b = build(sessions, checks).loc["AAPL:2025-01-30"]
    assert (b["timing_status"], b["timing_used"], b["day0_session"], b["exclusion_reason"]) == \
        ("inferred", "AMC", date(2025, 1, 31), None)


def test_checks_for_unknown_events_are_refused(sessions):
    base = events.base_events(CAL, ALIASES, {"AAPL"})
    checks = pd.DataFrame({"security_id": ["AAPL"], "announce_date": [date(2025, 1, 29)], "found": [True],
                           "release_date": [date(2025, 1, 29)], "label": ["AMC"], "reread": [False],
                           "checked_on": [date(2026, 10, 29)]}, dtype=object)
    with pytest.raises(ValueError, match="not in the calendar"):
        events.build_events(base, checks, sessions, calendar_commit="c" * 32, sample_ranges=RANGES,
                            duplicate_days=14)


def test_orphan_nearby(sessions):
    base = events.base_events(CAL, ALIASES, {"AAPL"})
    empty = pd.DataFrame(columns=["security_id", "announce_date", "found", "release_date", "label", "reread",
                                  "checked_on"])
    ev = events.build_events(base, empty, sessions, calendar_commit="c" * 32, sample_ranges=RANGES,
                             duplicate_days=14)
    d0 = sessions.index[date(2025, 5, 2)]
    # A zone that ends exactly 60 sessions before day 0 touches [-60, +10]; one that
    # ends 61 sessions before does not.
    touching = {"AAPL": [(d0 - 100, d0 - 60)]}
    apart = {"AAPL": [(d0 - 100, d0 - 61)]}
    eps0 = pd.DataFrame(columns=["security_id", "fiscal_period_end", "event_id", "match_status"])
    near = events.finish_events(ev, eps0, touching, sessions, (-60, 10)).set_index("event_id")
    far = events.finish_events(ev, eps0, apart, sessions, (-60, 10)).set_index("event_id")
    assert bool(near.loc["AAPL:2025-05-01", "orphan_nearby"]) is True
    assert bool(far.loc["AAPL:2025-05-01", "orphan_nearby"]) is False


def test_lookup_invariant_is_reported_and_enforced_when_complete(sessions):
    ev = build(sessions).reset_index()
    viol = events.lookup_violations(ev, {}, sessions, date(2024, 9, 11), 10, RANGES)
    # 2024-10-31, 2025-01-30 and 2025-05-01 are in the look-up era and unchecked;
    # 2026-11-05 is after the data end and META 2022 is before the era.
    assert sorted(v["event_id"] for v in viol) == ["AAPL:2024-10-31", "AAPL:2025-01-30", "AAPL:2025-05-01"]
    events.enforce_lookup_invariant(viol, lookups_complete=False)   # provisional: no error
    with pytest.raises(RuntimeError, match="3 events need a press-release look-up"):
        events.enforce_lookup_invariant(viol, lookups_complete=True)
    events.enforce_lookup_invariant([], lookups_complete=True)


def test_sample_follows_day0_and_timing_reasons_come_first(sessions):
    cal = pd.DataFrame({
        "act_symbol": ["AAPL", "AAPL"],
        # Wed 2024-12-04 AMC: announced in the mixed range, but day 0 is Thu 12-05,
        # the first day of the daily range, so the event is `daily`.
        # Thu 2026-11-05 with no label: after the data end AND undecidable; the
        # timing reason is reported, because it is checked first.
        "date": [date(2024, 12, 4), date(2026, 11, 5)],
        "when": ["After market close", None],
    }, dtype=object)
    base = events.base_events(cal, ALIASES, {"AAPL"})
    empty = pd.DataFrame(columns=["security_id", "announce_date", "found", "release_date", "label", "reread",
                                  "checked_on"])
    ev = events.build_events(base, empty, sessions, calendar_commit="c" * 32, sample_ranges=RANGES,
                             duplicate_days=14)
    eps0 = pd.DataFrame(columns=["security_id", "fiscal_period_end", "event_id", "match_status"])
    ev = events.finish_events(ev, eps0, {}, sessions, (-60, 10)).set_index("event_id")
    assert (ev.loc["AAPL:2024-12-04", "day0_session"], ev.loc["AAPL:2024-12-04", "sample"]) == \
        (date(2024, 12, 5), "daily")
    assert ev.loc["AAPL:2026-11-05", "sample"] == "none"
    assert ev.loc["AAPL:2026-11-05", "exclusion_reason"] == "timing_not_checked"


def test_the_project_sample_ranges_partition_the_timeline():
    # ADR 0004 §5: every day from the coarse start to the daily end is in exactly one sample,
    # and every day outside is in none. The review found 2024-09-10 and 09-11 in no sample.
    from datetime import timedelta
    from earnings_vol import params as params_mod
    p = params_mod.load()
    ranges = {k: p.date_range("samples", k) for k in ("daily", "mixed", "coarse")}
    events.check_sample_ranges(ranges)
    first, last = ranges["coarse"][0], ranges["daily"][1]
    d = first - timedelta(days=3)
    while d <= last + timedelta(days=3):
        inside = [k for k, (lo, hi) in ranges.items() if lo <= d <= hi]
        assert len(inside) == (1 if first <= d <= last else 0), d
        assert events.sample_of(d, ranges) == (inside[0] if inside else "none")
        d += timedelta(days=1)
    assert events.sample_of(date(2024, 9, 10), ranges) == "coarse"
    assert events.sample_of(date(2024, 9, 11), ranges) == "coarse"


@pytest.mark.parametrize("coarse_end, message", [
    (date(2024, 9, 9), "not contiguous"),     # the gap the review found
    (date(2024, 9, 12), "not contiguous"),    # an overlap with mixed
])
def test_check_sample_ranges_refuses_a_gap_or_an_overlap(coarse_end, message):
    ranges = dict(RANGES, coarse=(date(2020, 4, 1), coarse_end))
    with pytest.raises(ValueError, match=message):
        events.check_sample_ranges(ranges)
    with pytest.raises(ValueError, match="empty"):
        events.check_sample_ranges(dict(RANGES, mixed=(date(2024, 12, 4), date(2024, 9, 12))))


# --- duplicate calendar rows of one release (ADR 0002 §3, note 3; delta review, claim 1a) ---

# Berkshire-shaped: a Friday 2024-11-01 row with no label beside the real Saturday 2024-11-02
# release (BMO), as in the DoltHub calendar.
BRK = pd.DataFrame({
    "act_symbol": ["BRK.B", "BRK.B", "BRK.B", "BRK.B"],
    "date": [date(2024, 8, 3), date(2024, 11, 1), date(2024, 11, 2), date(2025, 2, 22)],
    "when": ["Before market open", None, "Before market open", "Before market open"],
}, dtype=object)
BRK_ALIASES = securities.build_ticker_alias(universe.alias_rows(["BRK.B"]))
NO_CHECKS = pd.DataFrame(columns=["security_id", "announce_date", "found", "release_date", "label", "reread",
                                  "checked_on"])


def build_brk(sessions, checks=NO_CHECKS):
    base = events.base_events(BRK, BRK_ALIASES, {"BRK.B"})
    ev = events.build_events(base, checks, sessions, calendar_commit="c" * 32, sample_ranges=RANGES,
                             duplicate_days=14)
    eps0 = pd.DataFrame(columns=["security_id", "fiscal_period_end", "event_id", "match_status"])
    return events.finish_events(ev, eps0, {}, sessions, (-60, 10))


def test_a_duplicate_calendar_row_is_excluded_before_any_timing_reason(sessions):
    ev = build_brk(sessions)
    assert events.duplicate_rows(ev, 14) == {"BRK.B:2024-11-01": "BRK.B:2024-11-02"}
    e = ev.set_index("event_id")
    # The Friday row has no label on a session day: without the duplicate rule it would be
    # timing_not_checked. It is a second row of the Saturday release, so it is duplicate_row.
    assert e.loc["BRK.B:2024-11-01", "exclusion_reason"] == "duplicate_row"
    assert e.loc["BRK.B:2024-11-01", "day0_session"] is None
    # The release keeps its day 0 (the Monday after the Saturday) and stays in its sample.
    r = e.loc["BRK.B:2024-11-02"]
    assert (r["day0_session"], r["sample"], r["exclusion_reason"]) == (date(2024, 11, 4), "mixed", None)
    # Both rows stay in the prev/next chain, which is over calendar rows.
    assert events.check_chain(ev) == []


def test_two_equally_supported_rows_of_one_release_stop_the_build(sessions):
    cal = BRK.assign(when=["Before market open", None, None, "Before market open"])
    base = events.base_events(cal, BRK_ALIASES, {"BRK.B"})
    with pytest.raises(ValueError, match="equally strong timing evidence"):
        events.build_events(base, NO_CHECKS, sessions, calendar_commit="c" * 32, sample_ranges=RANGES,
                            duplicate_days=14)


def test_a_press_release_reading_outranks_a_calendar_label(sessions):
    # A look-up of the Friday row that finds a release on that Friday, before the open, makes the
    # Friday row the release and the labelled Saturday row the duplicate.
    checks = pd.DataFrame({"security_id": ["BRK.B"], "announce_date": [date(2024, 11, 1)], "found": [True],
                           "release_date": [date(2024, 11, 1)], "label": ["BMO"], "reread": [False],
                           "checked_on": [date(2026, 10, 29)]}, dtype=object)
    e = build_brk(sessions, checks).set_index("event_id")
    assert e.loc["BRK.B:2024-11-02", "exclusion_reason"] == "duplicate_row"
    assert (e.loc["BRK.B:2024-11-01", "exclusion_reason"], e.loc["BRK.B:2024-11-01", "day0_session"]) == \
        (None, date(2024, 11, 1))


@pytest.mark.parametrize("second, grouped", [(date(2025, 3, 15), True), (date(2025, 3, 16), False)])
def test_rows_within_the_window_are_one_release(second, grouped):
    # 2025-03-01 (labelled) and a row 14 days later are one release; 15 days later they are two.
    ev = pd.DataFrame({"event_id": ["X:a", "X:b"], "security_id": ["X", "X"],
                       "announce_date_used": [date(2025, 3, 1), second],
                       "timing_source": ["calendar", None]}, dtype=object)
    assert events.duplicate_rows(ev, 14) == ({"X:b": "X:a"} if grouped else {})
