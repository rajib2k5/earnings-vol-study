# Tests for src/earnings_vol/events/timing.py: the timing label from documents
# (ADR 0002 §3), the gap diagnostic and the look-up rule.
#
# Mutations this module must catch (applied by hand, each seen to fail):
#   - resolve_timing: corrected and confirmed swapped
#   - resolve_timing: a NULL-label weekend release made `ambiguous`
#   - label_from_time: 16:00 read as BMO (the close is the boundary, inclusive)
#   - final_reading: a single disagreeing re-read accepted without a third reading
#   - gap_check: the verdict ratio test dropped (z >= 4 alone)
#   - overnight_gaps: the dividend not added back on the ex-date
#   - lookup_reasons without the can_enter_sample scope (the review's M12)
#   - can_enter_sample checking only next(D), or only D
#   - parse_checks accepting a source_kind outside its vocabulary
#   - parse_checks accepting a time without a time_source, or a time_source
#     without a time
#   - parse_checks accepting a not-found row with a time

import math
from datetime import date

import pandas as pd
import pytest

from earnings_vol.events import calendar, timing
from earnings_vol.events.timing import Reading

ERAS = {"weekly_from": "2019-02-09", "mwf_from": "2020-01-06", "daily_from": "2024-09-11",
        "data_end": "2026-10-26"}
GAP = {"scale_window": [-60, -22], "z_min": 4.0, "ratio": 3.0, "outside_window": [-3, 4], "outside_z_min": 6.0}


@pytest.fixture(scope="module")
def table():
    return calendar.build_session_table(date(2024, 1, 1), date(2026, 12, 31), ERAS)


@pytest.fixture(scope="module")
def sessions(table):
    return calendar.Sessions(table["session_date"].tolist())


@pytest.fixture(scope="module")
def close(table):
    return dict(zip(table["session_date"], table["close_time_et"]))


def test_parse_when_maps_the_three_source_values_and_refuses_others():
    assert timing.parse_when("Before market open") == "BMO"
    assert timing.parse_when("After market close") == "AMC"
    assert timing.parse_when(None) is None
    assert timing.parse_when(float("nan")) is None
    with pytest.raises(ValueError, match="unknown"):
        timing.parse_when("During market")
    with pytest.raises(ValueError):
        timing.parse_when("<NULL>")   # the old CSV sentinel must never be read as a label


@pytest.mark.parametrize("day, hhmm, expected", [
    (date(2025, 10, 30), "06:45", "BMO"),   # before 09:30
    (date(2025, 10, 30), "09:29", "BMO"),
    (date(2025, 10, 30), "09:30", "BMO"),   # inside the session: day 0 = D, stored as BMO
    (date(2025, 10, 30), "15:59", "BMO"),
    (date(2025, 10, 30), "16:00", "AMC"),   # at the close: AMC
    (date(2025, 10, 30), "16:30", "AMC"),
    (date(2025, 11, 28), "13:00", "AMC"),   # half day: the close is 13:00
    (date(2025, 11, 28), "12:59", "BMO"),
    (date(2025, 5, 3), "07:00", None),      # Saturday: the label cannot move day 0
])
def test_label_from_time(sessions, close, day, hhmm, expected):
    assert timing.label_from_time(day, hhmm, sessions, close) == expected


def R(found=True, d=date(2024, 10, 17), label="AMC", reread=False):
    return Reading(found, d if found else None, label if found else None, reread, date(2026, 10, 29))


@pytest.mark.parametrize("announce, raw, readings, status, used, source, date_used", [
    # Nobody looked: the calendar label stays.
    (date(2024, 10, 17), "BMO", [], "not_checked", "BMO", "calendar", date(2024, 10, 17)),
    (date(2024, 10, 17), None, [], "not_checked", None, None, date(2024, 10, 17)),
    # The release agrees / disagrees / fills a NULL.
    (date(2024, 10, 17), "AMC", [R()], "confirmed", "AMC", "press_release", date(2024, 10, 17)),
    (date(2024, 10, 17), "BMO", [R()], "corrected", "AMC", "press_release", date(2024, 10, 17)),
    (date(2024, 10, 17), None, [R()], "inferred", "AMC", "press_release", date(2024, 10, 17)),
    # The release is on another day (MS 2024: calendar 10-17, release 10-16 BMO).
    (date(2024, 10, 17), "BMO", [R(d=date(2024, 10, 16), label="BMO")], "date_corrected", "BMO",
     "press_release", date(2024, 10, 16)),
    # Looked up, nothing found.
    (date(2024, 10, 17), "BMO", [R(found=False)], "no_document", "BMO", "calendar", date(2024, 10, 17)),
    (date(2024, 10, 17), None, [R(found=False)], "ambiguous", None, None, date(2024, 10, 17)),
    # A weekend release: only the date is checked, it is never ambiguous.
    (date(2025, 5, 3), None, [R(found=False)], "no_document", None, None, date(2025, 5, 3)),
    (date(2025, 5, 3), "AMC", [R(d=date(2025, 5, 3), label="BMO")], "confirmed", "BMO", "press_release",
     date(2025, 5, 3)),
])
def test_resolve_timing_status_table(sessions, announce, raw, readings, status, used, source, date_used):
    out = timing.resolve_timing(announce, raw, readings, sessions)
    assert (out["timing_status"], out["timing_used"], out["timing_source"], out["announce_date_used"]) == \
        (status, used, source, date_used)
    assert out["gap_check_changed"] is False


def test_final_reading_needs_two_independent_readings_to_change_a_label():
    first = R(label="BMO")
    # A blind re-read that agrees: nothing changes.
    assert timing.final_reading([first, R(label="BMO", reread=True)]) == (first, False)
    # One disagreeing re-read is not enough: a third reading is required.
    with pytest.raises(ValueError, match="third"):
        timing.final_reading([first, R(label="AMC", reread=True)])
    # Second and third agree against the first: the label changes, and it is flagged.
    second = R(label="AMC", reread=True)
    assert timing.final_reading([first, second, R(label="AMC", reread=True)]) == (second, True)
    # Second and third disagree: the first stands.
    assert timing.final_reading([first, second, R(label="BMO", reread=True)]) == (first, False)
    with pytest.raises(ValueError, match="exactly one first reading"):
        timing.final_reading([R(reread=True)])


HEADER = ",".join(timing.CHECK_COLUMNS) + "\n"


def test_parse_checks_reads_a_valid_row(sessions, close):
    row = ("NFLX,2024-10-17,true,2024-10-17,16:00,announced_time,AMC,https://example.com/x,company,"
           "https://example.com/pre,2026-10-29,false,0.49,note\n")
    df = timing.parse_checks(HEADER + row, sessions, close)
    r = df.iloc[0]
    assert (r["label"], bool(r["found"]), r["release_date"], r["release_time_et"], r["basis"]) == \
        ("AMC", True, date(2024, 10, 17), "16:00", "announced_time")
    assert (r["source_kind"], r["time_source"]) == ("company", "https://example.com/pre")
    assert r["lookup_minutes"] == 0.49 and not bool(r["reread"])


@pytest.mark.parametrize("row, message", [
    # 16:20 on a full session is AMC, so a BMO label is inconsistent.
    ("NVDA,2024-08-28,true,2024-08-28,16:20,time_stamp,BMO,https://e.com/x,newswire,https://e.com/x,2026-10-29,"
     "false,,", "means AMC"),
    # The basis must say what the stored time is: a time stamp needs a time, a call time holds none
    # (the review found NFLX, JPM and PM with a stored release time labelled call_time).
    ("NVDA,2024-08-28,true,2024-08-28,,time_stamp,AMC,https://e.com/x,newswire,,2026-10-29,false,,", "need one"),
    ("NVDA,2024-08-28,true,2024-08-28,,announced_time,AMC,https://e.com/x,company,,2026-10-29,false,,", "need one"),
    ("JPM,2024-10-11,true,2024-10-11,07:00,call_time,BMO,https://e.com/x,company,https://e.com/t,2026-10-29,"
     "false,,", "hold a time"),
    ("NVDA,2024-08-28,true,,,call_time,AMC,https://e.com/x,company,,2026-10-29,false,,", "needs release_date"),
    ("NVDA,2024-08-28,true,2024-08-28,,call_time,AMC,http://e.com/x,company,,2026-10-29,false,,", "https"),
    ("NVDA,2024-08-28,true,2024-08-28,,call_time,AMC,https://e.com/x,,,2026-10-29,false,,", "source_kind"),
    ("NVDA,2024-08-28,true,2024-08-28,,call_time,AMC,https://e.com/x,blog,,2026-10-29,false,,", "source_kind"),
    ("NVDA,2024-08-28,yes,2024-08-28,,call_time,AMC,https://e.com/x,company,,2026-10-29,false,,", "true or false"),
    ("NVDA,2024-08-28,false,2024-08-28,,,AMC,,,,2026-10-29,false,,", "not found has no date"),
    ("NVDA,2024-08-28,false,,16:20,,,,,https://e.com/t,2026-10-29,false,,", "not found has no date, time"),
    # Where the time was read (delta review, claim 8a): a time needs its page, and only a time has one.
    ("NVDA,2024-08-28,true,2024-08-28,16:20,time_stamp,AMC,https://e.com/x,company,,2026-10-29,false,,",
     "needs the page it was read on"),
    ("GS,2024-10-15,true,2024-10-15,,call_time,BMO,https://e.com/x,company,https://e.com/t,2026-10-29,false,,",
     "needs the page it was read on"),
    ("NVDA,2024-08-28,true,2024-08-28,16:20,time_stamp,AMC,https://e.com/x,company,http://e.com/t,2026-10-29,"
     "false,,", "time_source must be an https"),
])
def test_parse_checks_refuses_bad_rows(sessions, close, row, message):
    with pytest.raises(ValueError, match=message):
        timing.parse_checks(HEADER + row + "\n", sessions, close)


def test_parse_checks_refuses_other_columns(sessions, close):
    with pytest.raises(ValueError, match="columns"):
        timing.parse_checks("security_id,announce_date\n", sessions, close)


def test_overnight_gap_is_market_adjusted_and_adds_back_dividends():
    d1, d2 = date(2025, 10, 30), date(2025, 10, 31)
    stock = pd.DataFrame({"date": [d1, d2], "open": [100.0, 104.0], "close": [100.0, 105.0],
                          "dividends": [0.0, 1.0]})
    market = pd.DataFrame({"date": [d1, d2], "open": [500.0, 505.0], "close": [500.0, 506.0],
                           "dividends": [0.0, 0.0]})
    g = timing.overnight_gaps(stock, market)
    # stock: ln((104 + 1)/100) = ln 1.05 = 0.0487902; market: ln(505/500) = ln 1.01 = 0.0099503
    # g = 0.0487902 - 0.0099503 = 0.0388399
    assert g[d2] == pytest.approx(math.log(1.05) - math.log(1.01), abs=1e-12)
    assert g[d2] == pytest.approx(0.0388399, abs=1e-7)
    assert d1 not in g   # no previous close


def gaps_around(sessions, anchor, values):
    """Every session within 70 of the anchor gets gap 0.01 (|g| = 0.01, so the
    median scale is 0.01), then `values` {offset: gap} override some."""
    out = {sessions.shift(anchor, k): 0.01 for k in range(-70, 8)}
    for k, v in values.items():
        out[sessions.shift(anchor, k)] = v
    return out


def test_gap_check_verdicts(sessions):
    d = date(2024, 10, 29)                        # GOOGL's Tuesday
    # Scale 0.01. Gap at next(D) 0.0650 -> z_A = 6.50; at D 0.0060 -> z_B = 0.60.
    gaps = gaps_around(sessions, d, {0: 0.0060, 1: 0.0650})
    bmo = timing.gap_check(d, "BMO", gaps, sessions, GAP)
    assert bmo["z_amc_yf"] == pytest.approx(6.50) and bmo["z_bmo_yf"] == pytest.approx(0.60)
    # BMO: the other candidate (A) has z 6.50 >= 4 and >= 3 x 0.60 = 1.80 -> contradicts.
    assert bmo["gap_verdict_yf"] == "contradicts" and timing.gap_triggered(bmo)
    # AMC: its own candidate has 6.50 >= 4 and >= 3 x 0.60 -> supports.
    assert timing.gap_check(d, "AMC", gaps, sessions, GAP)["gap_verdict_yf"] == "supports"
    # 6.50 against 3.0: 6.50 < 3 x 3.0 = 9.0, so neither side wins -> quiet.
    quiet = timing.gap_check(d, "BMO", gaps_around(sessions, d, {0: 0.03, 1: 0.0650}), sessions, GAP)
    assert quiet["gap_verdict_yf"] == "quiet" and not timing.gap_triggered(quiet)
    # No label: no verdict.
    assert timing.gap_check(d, None, gaps, sessions, GAP)["gap_verdict_yf"] is None


def test_gap_check_outside_flag(sessions):
    d = date(2024, 10, 29)
    # A z of 9 three sessions before D, candidates at z 1 and 2: 9 >= 6 and 9 >= 3 x 2.
    row = timing.gap_check(d, "BMO", gaps_around(sessions, d, {-3: 0.09, 0: 0.01, 1: 0.02}), sessions, GAP)
    assert row["outside_flag_yf"] is True and row["rel_day_max_outside_yf"] == -3
    assert row["z_max_outside_yf"] == pytest.approx(9.0)
    assert timing.gap_triggered(row)


def test_gap_check_weekend_release_has_one_candidate(sessions):
    d = date(2025, 5, 3)                          # Saturday
    row = timing.gap_check(d, "BMO", gaps_around(sessions, sessions.as_of(d), {1: 0.05}), sessions, GAP)
    assert math.isnan(row["z_bmo_yf"]) and row["z_amc_yf"] == pytest.approx(5.0)
    assert row["gap_verdict_yf"] is None


RANGES = {"daily": (date(2024, 12, 5), date(2026, 10, 26)), "mixed": (date(2024, 9, 12), date(2024, 12, 4)),
          "coarse": (date(2020, 4, 1), date(2024, 9, 11))}


@pytest.fixture(scope="module")
def wide():
    """Sessions 2019-2027: the look-up rule needs next(D) for dates of every sample."""
    return calendar.Sessions(calendar.build_session_table(date(2019, 1, 1), date(2027, 12, 31), ERAS)
                             ["session_date"].tolist())


def test_lookup_reasons(wide):
    lf = date(2024, 9, 11)

    def why(d, label, triggered=False):
        return timing.lookup_reasons(d, label, triggered, wide, lf, 10, RANGES)

    # Ten sessions before Wed 2024-09-11 is Tue 2024-08-27 (Labor Day 09-02 is skipped):
    # 09-10, 09, 06, 05, 04, 03, 08-30, 29, 28, 27.
    assert why(date(2024, 8, 27), "AMC") == ["daily_or_mixed_era"]
    assert why(date(2024, 8, 26), "AMC") == []
    assert why(date(2023, 5, 1), None) == ["null_label"]
    assert why(date(2023, 5, 1), "BMO", triggered=True) == ["gap_trigger"]
    assert why(date(2026, 10, 26), None) == ["daily_or_mixed_era", "null_label"]


def test_lookup_reasons_only_for_events_that_can_enter_a_sample(wide):
    # ADR 0002 §3's invariant, scoped (milestone-1 review, claim 3b): an event none of whose
    # candidate day-0 sessions, D and next(D), lies in a sample range needs no look-up.
    lf = date(2024, 9, 11)

    def why(d, label, triggered=False):
        return timing.lookup_reasons(d, label, triggered, wide, lf, 10, RANGES)

    # A date scheduled after the data end (Thu 2026-11-05): no look-up, with or without a label.
    assert why(date(2026, 11, 5), "AMC") == []
    assert why(date(2026, 11, 5), None) == []
    # Mon 2026-10-26 AMC has day 0 on 10-27 (no sample), but as BMO it would be day 0 10-26,
    # the last daily day: it can enter a sample, so it is looked up.
    assert why(date(2026, 10, 26), "AMC") == ["daily_or_mixed_era"]
    # Before the coarse sample: Fri 2020-03-27 (next 03-30) cannot enter; Tue 2020-03-31 can,
    # because next(D) = Wed 04-01 is the first coarse day.
    assert why(date(2020, 3, 27), None) == []
    assert why(date(2020, 3, 27), "BMO", triggered=True) == []
    assert why(date(2020, 3, 31), None) == ["null_label"]
    assert timing.can_enter_sample(date(2020, 3, 31), wide, RANGES)
    assert not timing.can_enter_sample(date(2026, 10, 27), wide, RANGES)
