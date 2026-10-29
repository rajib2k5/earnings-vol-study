# Tests for src/earnings_vol/events/calendar.py: NYSE sessions and day 0.
#
# The day-0 cases are the oracle table of ADR 0002 §2, typed in by hand. The
# session facts (holidays, half days) are from the NYSE holiday list, checked
# by hand against the calendar printed in the test comments.
#
# Mutations this module must catch (each was applied by hand and seen to fail):
#   - BMO and AMC swapped in day0()
#   - a weekend release treated like its label (day 0 = D for "BMO")
#   - next_after() returning the date itself when it is a session
#   - is_half_day computed from the wrong close time

from datetime import date

import pytest

from earnings_vol.events import calendar

ERAS = {"weekly_from": "2019-02-09", "mwf_from": "2020-01-06", "daily_from": "2024-09-11",
        "data_end": "2026-10-26"}


@pytest.fixture(scope="module")
def table():
    return calendar.build_session_table(date(2016, 1, 1), date(2027, 12, 31), ERAS)


@pytest.fixture(scope="module")
def sessions(table):
    return calendar.Sessions(table["session_date"].tolist())


# ADR 0002 §2, "Worked cases": (D, label, day -1, day 0).
ORACLE = [
    # AAPL Q4 FY25, Thu 2025-10-30, AMC: day -1 is D, day 0 is Fri 10-31.
    (date(2025, 10, 30), "AMC", date(2025, 10, 30), date(2025, 10, 31)),
    # JPM Q3 2025, Tue 2025-10-14, BMO: Mon 10-13 (Columbus Day) IS a session.
    (date(2025, 10, 14), "BMO", date(2025, 10, 13), date(2025, 10, 14)),
    # Fri 2025-11-07 AMC: the weekend sits between, so day 0 is Mon 11-10.
    (date(2025, 11, 7), "AMC", date(2025, 11, 7), date(2025, 11, 10)),
    # Wed 2025-11-26 AMC: Thu 11-27 is Thanksgiving, day 0 is the half day Fri 11-28.
    (date(2025, 11, 26), "AMC", date(2025, 11, 26), date(2025, 11, 28)),
    # Thu 2025-07-03 (half day) AMC: Fri 07-04 is a holiday, then the weekend: Mon 07-07.
    (date(2025, 7, 3), "AMC", date(2025, 7, 3), date(2025, 7, 7)),
    # Sat 2025-05-03, any label: Fri 05-02 and Mon 05-05.
    (date(2025, 5, 3), "BMO", date(2025, 5, 2), date(2025, 5, 5)),
    (date(2025, 5, 3), "AMC", date(2025, 5, 2), date(2025, 5, 5)),
    (date(2025, 5, 3), None, date(2025, 5, 2), date(2025, 5, 5)),
    # GOOGL Q3 2024, Tue 2024-10-29, AMC after the correction: 10-29 and Wed 10-30.
    (date(2024, 10, 29), "AMC", date(2024, 10, 29), date(2024, 10, 30)),
    # NFLX Q3 2024, Thu 2024-10-17, AMC after the correction: 10-17 and Fri 10-18.
    (date(2024, 10, 17), "AMC", date(2024, 10, 17), date(2024, 10, 18)),
]


@pytest.mark.parametrize("d, label, m1, d0", ORACLE)
def test_day0_oracle_table(sessions, d, label, m1, d0):
    assert calendar.day0(d, label, sessions) == (d0, m1)


def test_wrong_label_moves_day0_by_one_session(sessions):
    # GOOGL 2024-10-29 as the calendar had it (BMO): day 0 would be 10-29 itself,
    # one session early, and day -1 Mon 10-28.
    assert calendar.day0(date(2024, 10, 29), "BMO", sessions) == (date(2024, 10, 29), date(2024, 10, 28))


def test_unknown_timing_on_a_session_day_has_no_day0(sessions):
    assert calendar.day0(date(2025, 10, 30), None, sessions) == (None, None)


def test_unknown_timing_text_is_an_error(sessions):
    with pytest.raises(ValueError):
        calendar.day0(date(2025, 10, 30), "Before market open", sessions)


def test_holidays_and_half_days(table):
    t = table.set_index("session_date")
    # 2025 NYSE closures checked here: New Year 01-01, the Carter day of mourning
    # 01-09, Good Friday 04-18, Independence Day 07-04, Thanksgiving 11-27,
    # Christmas 12-25.
    for closed in (date(2025, 1, 1), date(2025, 1, 9), date(2025, 4, 18), date(2025, 7, 4),
                   date(2025, 11, 27), date(2025, 12, 25)):
        assert closed not in t.index
    # Columbus Day and Veterans Day are sessions (EDGAR is closed, NYSE is not).
    assert date(2025, 10, 13) in t.index and date(2025, 11, 11) in t.index
    # Half days close at 13:00: 07-03, 11-28 and 12-24 in 2025.
    for half in (date(2025, 7, 3), date(2025, 11, 28), date(2025, 12, 24)):
        assert t.loc[half, "close_time_et"] == "13:00" and bool(t.loc[half, "is_half_day"])
    assert t.loc[date(2025, 10, 30), "close_time_et"] == "16:00"
    assert not bool(t.loc[date(2025, 10, 30), "is_half_day"])


def test_session_count_of_2025_is_250(table):
    # ADR 0002 Context: 2025 has 250 NYSE sessions (and 259 snapshot dates).
    n = sum(1 for d in table["session_date"] if d.year == 2025)
    assert n == 250


def test_daily_era_from_2024_09_11_to_data_end_has_533_sessions(table):
    # ADR 0004 Context: 533 sessions from 2024-09-11 to 2026-10-26.
    daily = table[table["era"] == "daily"]["session_date"]
    assert daily.min() == date(2024, 9, 11) and daily.max() == date(2026, 10, 26)
    assert len(daily) == 533


def test_eras(table):
    t = table.set_index("session_date")["era"]
    assert t[date(2019, 2, 8)] == "none"         # before the weekly snapshots
    assert t[date(2019, 2, 11)] == "weekly"
    assert t[date(2020, 1, 6)] == "mwf"
    assert t[date(2024, 9, 10)] == "mwf"         # the Tuesday between the eras
    assert t[date(2024, 9, 11)] == "daily"
    assert t[date(2026, 10, 27)] == "none"       # after the data end


def test_session_index_counts_sessions(table, sessions):
    # 2025-10-30 (Thu) to 2025-11-10 (Mon): 31, 3, 4, 5, 6, 7, 10 = 7 sessions later.
    assert sessions.between(date(2025, 10, 30), date(2025, 11, 10)) == 7
    assert sessions.shift(date(2025, 10, 30), 7) == date(2025, 11, 10)
    assert list(table["session_index"]) == list(range(len(table)))


def test_neighbours(sessions):
    assert sessions.next_after(date(2025, 10, 30)) == date(2025, 10, 31)   # strictly after
    assert sessions.prev_before(date(2025, 10, 30)) == date(2025, 10, 29)
    assert sessions.as_of(date(2024, 9, 2)) == date(2024, 8, 30)           # Labor Day -> Friday
    assert sessions.as_of(date(2025, 10, 30)) == date(2025, 10, 30)
    assert sessions.first_on_or_after(date(2025, 5, 3)) == date(2025, 5, 5)
    with pytest.raises(ValueError):
        sessions.next_after(date(2030, 1, 1))


def test_season():
    assert calendar.season(date(2025, 1, 2)) == "2025Q1"
    assert calendar.season(date(2025, 3, 31)) == "2025Q1"
    assert calendar.season(date(2025, 4, 1)) == "2025Q2"
    assert calendar.season(date(2025, 12, 31)) == "2025Q4"
