# Tests for src/earnings_vol/events/eps.py: the EPS-period match (data model
# §3.8, ADR 0002 §3, revised after the milestone-1 review and its delta
# review), on hand-built fixtures shaped like the cases the reviews found.
#
# Mutations this module must catch (each was applied by hand and seen to fail):
#   - the window's lower bound moved off "first of the month + 14 days" (one
#     day earlier or later; a fixed +10 days, the pre-review rule; a fixed
#     -31 days; the bare first of the month, the rule before the delta review)
#   - the upper bound made exclusive (lag 100 no longer matches)
#   - the assignment made "first event in the window" (Costco's February
#     period takes the May report)
#   - the assignment made "most links first" (a chain shifts by a quarter)
#   - a tie given to the later event
#   - pre_calendar decided without the "no event in the window" condition
#   - a ticker conflict keeping one side's values
#   - the cost of an unlinked period changed from lag_max + 1 (to + 100, the
#     delta review's mutant M-e, or to lag_max)
#   - build_eps linking a duplicate_row

from datetime import date

import pandas as pd
import pytest

from earnings_vol.events import eps, securities
from earnings_vol.ingest import universe

CAL0 = date(2020, 1, 22)
RULE = "month_start+14"   # params.yaml eps_match.window_start


def m(periods, events):
    return eps.match_periods(periods, events, window_start=RULE, lag_max=100, calendar_start=CAL0)


def test_the_rule_is_the_one_in_params():
    from earnings_vol import params
    em = params.load()["eps_match"]
    assert (em["window_start"], em["lag_max_days"]) == (RULE, 100)


def test_the_window_runs_from_14_days_after_the_first_of_the_month_to_100_days_after():
    # Period 2025-05-31: the window is 2025-05-15 (05-01 + 14, lag -16) .. 2025-09-08 (lag +100).
    assert eps.window(date(2025, 5, 31), RULE, 100) == (date(2025, 5, 15), date(2025, 9, 8))
    # February: 2025-02-28 -> 02-01 + 14 = 2025-02-15, a lag of -13.
    assert eps.window(date(2025, 2, 28), RULE, 100)[0] == date(2025, 2, 15)
    # "month_start" is the first of the month (+0, the rule before the delta review);
    # an int is a fixed lag after the stored end (the sensitivity table).
    assert eps.window(date(2025, 5, 31), "month_start", 100)[0] == date(2025, 5, 1)
    assert eps.window(date(2025, 5, 31), "month_start+7", 100)[0] == date(2025, 5, 8)
    assert eps.window(date(2025, 5, 31), -10, 100)[0] == date(2025, 5, 21)
    for bad in ("month_end", "month_start+", "month_start-3", "month_start+100", True):
        with pytest.raises(ValueError):
            eps.window(date(2025, 5, 31), bad, 100)


@pytest.mark.parametrize("announce, expected", [
    (date(2025, 5, 15), "matched"),    # 05-01 + 14 days, lag -16: the lower bound, inclusive
    (date(2025, 5, 14), "orphan"),     # one day earlier
    (date(2025, 9, 8), "matched"),     # 2025-05-31 + 100 days: the upper bound, inclusive
    (date(2025, 9, 9), "orphan"),      # + 101 days
])
def test_a_lag_exactly_at_each_bound(announce, expected):
    out = m([date(2025, 5, 31)], [(announce, "A")])
    assert out[date(2025, 5, 31)][1] == expected


def test_costco_shaped_quarters_link_to_their_own_reports():
    # Costco's quarters end mid-month (2024-11-24, 2025-02-16, 2025-05-11, 2025-08-31) and are
    # stored as month-ends. Its March report is absent from the calendar. Lags of the reports:
    # 12-12 - 11-30 = +12; 05-29 - 05-31 = -2; 09-25 - 08-31 = +25.
    # The 02-28 period could also reach 05-29 (lag +90), but the 05-31 period is nearer (2 days):
    # cost Feb orphan 101 + 2 = 103 against 90 + May orphan 101 = 191. So February is the orphan.
    periods = [date(2024, 11, 30), date(2025, 2, 28), date(2025, 5, 31), date(2025, 8, 31)]
    events = [(date(2024, 12, 12), "Q1"), (date(2025, 5, 29), "Q3"), (date(2025, 9, 25), "Q4")]
    assert m(periods, events) == {date(2024, 11, 30): ("Q1", "matched"), date(2025, 2, 28): (None, "orphan"),
                                  date(2025, 5, 31): ("Q3", "matched"), date(2025, 8, 31): ("Q4", "matched")}


def test_oracle_shaped_reports_nine_days_after_a_month_end_link_to_their_own_quarter():
    # Oracle reports 9 days after its quarter ends: 2024-09-09 for 2024-08-31 (the old +10 lower
    # bound missed it) and 2024-12-09 for 2024-11-30, which is exactly 100 days after 2024-08-31.
    periods = [date(2024, 8, 31), date(2024, 11, 30)]
    events = [(date(2024, 9, 9), "Q1"), (date(2024, 12, 9), "Q2")]
    assert m(periods, events) == {date(2024, 8, 31): ("Q1", "matched"), date(2024, 11, 30): ("Q2", "matched")}


def test_a_missing_report_is_an_orphan_and_no_chain_shifts():
    # As above, but the 2024-09-09 report is missing. 12-09 is 100 days after 08-31 and 03-10
    # is 100 days after 11-30, so the 08-31 period could take the next quarter's report.
    # (06-09 is 101 days after 02-28: outside every window.)
    # Shifted: 08-31 -> 12-09 (100) + 11-30 -> 03-10 (100) + a 02-28 orphan (101) = 301.
    # Own quarters: an 08-31 orphan (101) + 9 + 10 = 120. The 08-31 period is the orphan.
    periods = [date(2024, 8, 31), date(2024, 11, 30), date(2025, 2, 28)]
    events = [(date(2024, 12, 9), "Q2"), (date(2025, 3, 10), "Q3"), (date(2025, 6, 9), "Q4")]
    assert m(periods, events) == {date(2024, 8, 31): (None, "orphan"), date(2024, 11, 30): ("Q2", "matched"),
                                  date(2025, 2, 28): ("Q3", "matched")}


def test_a_chain_does_not_shift_to_gain_a_link():
    # The case "most links first" gets wrong. Periods 06-30, 09-30, 12-31; the 06-30 report is
    # missing; reports 7 and 8 days after 09-30 and 12-31, and a calendar date 2026-03-31 for a
    # period not in eps_history yet. Each event is within 100 days of the period before its own:
    # 10-07 - 06-30 = 99, 01-08 - 09-30 = 100, 03-31 - 12-31 = 90.
    # Shifted (3 links): 99 + 100 + 90 = 289. Unshifted: 101 (06-30 orphan) + 7 + 8 = 116.
    periods = [date(2025, 6, 30), date(2025, 9, 30), date(2025, 12, 31)]
    events = [(date(2025, 10, 7), "Q3"), (date(2026, 1, 8), "Q4"), (date(2026, 3, 31), "next")]
    assert m(periods, events) == {date(2025, 6, 30): (None, "orphan"), date(2025, 9, 30): ("Q3", "matched"),
                                  date(2025, 12, 31): ("Q4", "matched")}


def test_berkshire_shaped_february_report_stays_with_the_december_quarter():
    # Berkshire releases its Q4 in late February: 2025-02-28 is 59 days after 2024-12-31 and
    # 31 days before 2025-03-31. With the Q1 report missing, the March quarter could only take it
    # if its window reached back past 03-15; it does not, so 12-31 keeps it and 03-31 is an orphan.
    # (A fixed -31-day bound would admit it, and the nearer lag, 31 < 59, would give it to March.)
    periods = [date(2024, 12, 31), date(2025, 3, 31)]
    assert m(periods, [(date(2025, 2, 28), "Q4")]) == {date(2024, 12, 31): ("Q4", "matched"),
                                                        date(2025, 3, 31): (None, "orphan")}


def test_a_tie_goes_to_the_earlier_event():
    # 09-20 and 10-10 are both 10 days from 09-30: equal cost, so the earlier event is taken.
    out = m([date(2025, 9, 30)], [(date(2025, 9, 20), "A"), (date(2025, 10, 10), "B")])
    assert out == {date(2025, 9, 30): ("A", "matched")}


def test_pre_calendar_only_when_the_window_starts_before_the_calendar_and_holds_no_event():
    # 2020-01-31: window from 2020-01-15 < 2020-01-22, no event: pre_calendar.
    # 2020-02-29: window from 2020-02-15 >= 2020-01-22: an unmatched period is an orphan.
    out = m([date(2020, 1, 31), date(2020, 2, 29)], [])
    assert out == {date(2020, 1, 31): (None, "pre_calendar"), date(2020, 2, 29): (None, "orphan")}


def test_a_period_whose_window_event_went_elsewhere_is_an_orphan_even_before_the_calendar():
    # 2019-12-31 (window 2019-12-15 .. 2020-04-09) and 2020-03-31 both reach 2020-04-07
    # (lags 98 and 7). The March period keeps it. The December period's window starts before
    # the calendar, but it holds an event, so its own report is the missing one: orphan.
    out = m([date(2019, 12, 31), date(2020, 3, 31)], [(date(2020, 4, 7), "A")])
    assert out == {date(2019, 12, 31): (None, "orphan"), date(2020, 3, 31): ("A", "matched")}


ALIASES = securities.build_ticker_alias(universe.alias_rows(["META", "AAPL"]))


def test_dedupe_merges_agreeing_tickers_and_flags_a_conflict():
    hist = pd.DataFrame({
        "act_symbol": ["FB", "META", "FB", "META", "AAPL"],
        "period_end_date": [date(2021, 12, 31)] * 2 + [date(2022, 3, 31)] * 2 + [date(2025, 9, 30)],
        "reported": [3.67, 3.67, 2.72, 2.73, 1.85],
        "estimate": [3.78, 3.78, 2.54, 2.54, 1.77],
    })
    out = eps.dedupe_history(hist, ALIASES).set_index(["security_id", "fiscal_period_end"])
    assert out.loc[("META", date(2021, 12, 31)), ["reported", "estimate", "ticker_conflict"]].tolist() == \
        [3.67, 3.78, False]
    # 2.72 against 2.73: the two tickers disagree -> both values null.
    row = out.loc[("META", date(2022, 3, 31))]
    assert row["ticker_conflict"] and pd.isna(row["reported"]) and pd.isna(row["estimate"])
    assert len(out) == 3


def test_build_eps_values_and_consensus():
    events = pd.DataFrame({
        "event_id": ["AAPL:2025-10-30"], "security_id": ["AAPL"], "announce_date": [date(2025, 10, 30)],
        "announce_date_used": [date(2025, 10, 30)], "day_m1_session": [date(2025, 10, 30)],
        "exclusion_reason": [None],
    }, dtype=object)
    hist = pd.DataFrame({"act_symbol": ["AAPL"], "period_end_date": [date(2025, 9, 30)],
                         "reported": [1.85], "estimate": [1.77]})
    # Weekly consensus snapshots; the last one dated on or before day -1 (10-30) is 10-26.
    est = pd.DataFrame({
        "date": [date(2025, 10, 19), date(2025, 10, 26), date(2025, 11, 2)],
        "act_symbol": ["AAPL"] * 3, "period": ["Current Quarter"] * 3,
        "period_end_date": [date(2025, 9, 30)] * 3,
        "consensus": [1.74, 1.73, 9.99], "count": [9, 10, 8], "high": [1.80, 1.80, 9.99], "low": [1.59, 1.59, 9.0],
    })
    out = eps.build_eps(hist, est, ALIASES, events, window_start=RULE, lag_max=100, calendar_start=CAL0)
    r = out.iloc[0]
    assert (r["event_id"], r["match_status"], r["lag_days"]) == ("AAPL:2025-10-30", "matched", 30)  # 10-30 minus 09-30
    # surprise = 1.85 - 1.77 = 0.08
    assert r["surprise"] == pytest.approx(0.08)
    assert (r["consensus"], r["consensus_count"], r["consensus_date"]) == (1.73, 10, date(2025, 10, 26))
    # surprise_disp = (1.85 - 1.73) / (1.80 - 1.59) = 0.12 / 0.21 = 0.5714286
    assert r["surprise_disp"] == pytest.approx(0.12 / 0.21)


def test_orphan_zones_count_sessions_from_the_period_end():
    from earnings_vol.events import calendar
    t = calendar.build_session_table(date(2024, 1, 1), date(2024, 12, 31),
                                     {"weekly_from": "2019-02-09", "mwf_from": "2020-01-06",
                                      "daily_from": "2024-09-11", "data_end": "2026-10-26"})
    s = calendar.Sessions(t["session_date"].tolist())
    table = pd.DataFrame({"security_id": ["GS"], "fiscal_period_end": [date(2024, 6, 30)],
                          "match_status": ["orphan"]})
    zones = eps.orphan_zones(table, s, (10, 60))
    # 2024-06-30 is a Sunday; the first session on or after it is Mon 07-01.
    base = s.index[date(2024, 7, 1)]
    assert zones == {"GS": [(base + 10, base + 60)]}
    # +10 sessions from 07-01 is 07-16 (07-04 is a holiday): 2,3,5,8,9,10,11,12,15,16.
    assert s.dates[base + 10] == date(2024, 7, 16)


# --- the delta review's shapes (docs/validation/probes/m1-delta/pd02_eps_shapes.py) -------------

def test_s1_a_slow_reporter_keeps_its_report_when_the_next_one_is_missing():
    # Reports 66 days after the period; the Q2 report is missing. 2024-06-05 is 66 days after
    # 03-31 and 25 days before 06-30. The 06-30 window opens on 06-15, so only 03-31 can take it.
    # (Under the bare first of the month, 06-30 took it: lag -25 beats 66, and 03-31 was the orphan.)
    out = m([date(2024, 3, 31), date(2024, 6, 30), date(2024, 9, 30)],
            [(date(2024, 6, 5), "Q1"), (date(2024, 12, 5), "Q3")])
    assert out == {date(2024, 3, 31): ("Q1", "matched"), date(2024, 6, 30): (None, "orphan"),
                   date(2024, 9, 30): ("Q3", "matched")}


def test_s2_a_complete_slow_chain_does_not_shift():
    # Lags 65 and 66 days, every report present. Each report falls 25-27 days before the next
    # period's stored end, before that period's window opens (the 15th), so no link can move.
    # (Under the bare first of the month the whole chain shifted: cost 101 + 26 + 25 + 26 = 178
    # against 65 + 66 + 66 + 66 = 263.)
    periods = [date(2023, 12, 31), date(2024, 3, 31), date(2024, 6, 30), date(2024, 9, 30)]
    events = [(date(2024, 3, 5), "Q4"), (date(2024, 6, 5), "Q1"), (date(2024, 9, 4), "Q2"), (date(2024, 12, 5), "Q3")]
    assert m(periods, events) == {date(2023, 12, 31): ("Q4", "matched"), date(2024, 3, 31): ("Q1", "matched"),
                                  date(2024, 6, 30): ("Q2", "matched"), date(2024, 9, 30): ("Q3", "matched")}


def test_s4_a_berkshire_q4_release_on_1_march_stays_with_december():
    # Saturday 2025-03-01 is 60 days after 2024-12-31; the Q1 report is missing. The 03-31 window
    # opens on 03-15, so December keeps it and March is the orphan.
    out = m([date(2024, 12, 31), date(2025, 3, 31), date(2025, 6, 30)],
            [(date(2025, 3, 1), "Q4"), (date(2025, 8, 2), "Q2")])
    assert out == {date(2024, 12, 31): ("Q4", "matched"), date(2025, 3, 31): (None, "orphan"),
                   date(2025, 6, 30): ("Q2", "matched")}


@pytest.mark.parametrize("announce, owner", [
    (date(2023, 3, 14), date(2022, 12, 31)),   # lag 73: before the 03-31 window opens (03-15)
    (date(2023, 3, 15), date(2023, 3, 31)),    # lag 74: inside it, and moving is cheaper
])
def test_a_link_moves_to_the_next_period_only_from_74_days_late(announce, owner):
    # What the rule still gets wrong, stated exactly (ADR 0002 §3): 2023-03-01 is 60 days after
    # 2022-12-31, and the 03-31 window opens 14 days later, at lag 74. With the Q1 report missing,
    # a lag-74 report goes to March: 101 (December unlinked) + 16 = 117 < 74 + 101 = 175.
    out = m([date(2022, 12, 31), date(2023, 3, 31)], [(announce, "R")])
    assert out[owner] == ("R", "matched")


@pytest.mark.parametrize("b_day, linked", [
    (date(2025, 10, 28), {date(2025, 6, 30): "A", date(2025, 9, 30): "B"}),    # adds 100 days: take it
    (date(2025, 10, 29), {date(2025, 6, 30): "A", date(2025, 9, 30): "B"}),    # adds 101: a tie, the link wins
    (date(2025, 10, 30), {date(2025, 6, 30): None, date(2025, 9, 30): "A"}),   # adds 102: leave 06-30 unlinked
])
def test_an_unlinked_period_costs_lag_max_plus_one(b_day, linked):
    # The exchange rate between links and orphans (mutant M-e of the delta review). A = 2025-09-20
    # is in both windows: lag 82 from 06-30, -10 from 09-30. B is 28-30 days after 09-30 and
    # outside 06-30's window (lag 120+). Two links cost 82 + |B lag|; one link costs 101 + 10.
    # So the second link is taken while 82 + lag_B - 10 <= 101, i.e. lag_B <= 29.
    out = m([date(2025, 6, 30), date(2025, 9, 30)], [(date(2025, 9, 20), "A"), (b_day, "B")])
    assert {pe: e for pe, (e, _) in out.items()} == linked


def test_build_eps_never_links_a_duplicate_row():
    # BRK.B (ADR 0002 note 3): a Friday 2024-11-01 row with no label beside the real Saturday
    # 2024-11-02 release. The Friday row is nearer the 2024-09-30 period (lag 32 against 33), so
    # it would win if it were matched; as a duplicate_row it is skipped.
    events = pd.DataFrame({
        "event_id": ["BRK.B:2024-11-01", "BRK.B:2024-11-02"], "security_id": ["BRK.B"] * 2,
        "announce_date": [date(2024, 11, 1), date(2024, 11, 2)],
        "announce_date_used": [date(2024, 11, 1), date(2024, 11, 2)],
        "day_m1_session": [None, date(2024, 11, 1)], "exclusion_reason": ["duplicate_row", None],
    }, dtype=object)
    hist = pd.DataFrame({"act_symbol": ["BRK.B"], "period_end_date": [date(2024, 9, 30)],
                         "reported": [1.5], "estimate": [1.25]})
    est = pd.DataFrame(columns=["date", "act_symbol", "period", "period_end_date", "consensus", "count", "high",
                                "low"])
    aliases = securities.build_ticker_alias(universe.alias_rows(["BRK.B"]))
    out = eps.build_eps(hist, est, aliases, events, window_start=RULE, lag_max=100, calendar_start=CAL0)
    assert out[["event_id", "match_status", "lag_days"]].values.tolist() == [["BRK.B:2024-11-02", "matched", 33]]
