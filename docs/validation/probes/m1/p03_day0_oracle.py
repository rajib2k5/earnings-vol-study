"""p03: day0() against ADR 0002 §2's oracle table, typed here from the ADR text (claim 2).

  uv run python docs/validation/probes/m1/p03_day0_oracle.py

The expected (day -1, day 0) pairs are copied by hand from the ADR's "Worked cases"
table, not from tests/test_calendar.py or the code. The session list is built by
the project's build_session_table (XNYS) and also checked directly against
exchange_calendars for the facts the table relies on.
"""
from datetime import date

import exchange_calendars as xcals

from earnings_vol.events import calendar

ORACLE = [  # (name, D, label, day -1, day 0) -- ADR 0002 §2 "Worked cases"
    ("AAPL Q4 FY25", date(2025, 10, 30), "AMC", date(2025, 10, 30), date(2025, 10, 31)),
    ("JPM Q3 2025 (Columbus Day session)", date(2025, 10, 14), "BMO", date(2025, 10, 13), date(2025, 10, 14)),
    ("Fri AMC, weekend", date(2025, 11, 7), "AMC", date(2025, 11, 7), date(2025, 11, 10)),
    ("Wed before Thanksgiving AMC", date(2025, 11, 26), "AMC", date(2025, 11, 26), date(2025, 11, 28)),
    ("Thu 2025-07-03 half day AMC", date(2025, 7, 3), "AMC", date(2025, 7, 3), date(2025, 7, 7)),
    ("Sat 2025-05-03, BMO", date(2025, 5, 3), "BMO", date(2025, 5, 2), date(2025, 5, 5)),
    ("Sat 2025-05-03, AMC", date(2025, 5, 3), "AMC", date(2025, 5, 2), date(2025, 5, 5)),
    ("Sat 2025-05-03, NULL", date(2025, 5, 3), None, date(2025, 5, 2), date(2025, 5, 5)),
    ("GOOGL Q3 2024 as corrected (AMC)", date(2024, 10, 29), "AMC", date(2024, 10, 29), date(2024, 10, 30)),
    ("NFLX Q3 2024 as corrected (AMC)", date(2024, 10, 17), "AMC", date(2024, 10, 17), date(2024, 10, 18)),
    # The ADR's "BMO, D is a session" rule applied to the calendar's wrong label (not an oracle row,
    # but the rule's first line): GOOGL as BMO -> day 0 = D.
    ("GOOGL as the calendar's BMO", date(2024, 10, 29), "BMO", date(2024, 10, 28), date(2024, 10, 29)),
    # Holiday (not weekend) release: Good Friday 2025-04-18, any label.
    ("Good Friday 2025-04-18 holiday, AMC", date(2025, 4, 18), "AMC", date(2025, 4, 17), date(2025, 4, 21)),
    # ADR: NULL timing, no document, D a session -> excluded (no day 0).
    ("NULL on a session (ambiguous row)", date(2025, 10, 30), None, None, None),
]


def main():
    tbl = calendar.build_session_table(date(2016, 1, 1), date(2027, 12, 31),
                                       {"weekly_from": "2019-02-09", "mwf_from": "2020-01-06",
                                        "daily_from": "2024-09-11", "data_end": "2026-10-26"})
    s = calendar.Sessions(tbl["session_date"].tolist())
    bad = 0
    for name, d, lab, m1, d0 in ORACLE:
        got0, gotm1 = calendar.day0(d, lab, s)
        ok = (got0, gotm1) == (d0, m1)
        bad += not ok
        print(f"{'OK ' if ok else 'BAD'} {name:40s} D={d} {str(lab):4s} -> day-1={gotm1} day0={got0}"
              f"{'' if ok else f'  EXPECTED day-1={m1} day0={d0}'}")
    # Direct exchange_calendars facts the table relies on.
    cal = xcals.get_calendar("XNYS", start="2024-01-01", end="2025-12-31")
    facts = {"2025-10-13 session (Columbus)": cal.is_session("2025-10-13"),
             "2025-11-11 session (Veterans)": cal.is_session("2025-11-11"),
             "2025-11-27 holiday (Thanksgiving)": not cal.is_session("2025-11-27"),
             "2025-07-04 holiday": not cal.is_session("2025-07-04"),
             "2025-04-18 holiday (Good Friday)": not cal.is_session("2025-04-18"),
             "2025-11-28 closes 13:00 ET": str(cal.closes.loc["2025-11-28"].tz_convert("America/New_York").time()) == "13:00:00",
             "2025-07-03 closes 13:00 ET": str(cal.closes.loc["2025-07-03"].tz_convert("America/New_York").time()) == "13:00:00"}
    for k, v in facts.items():
        bad += not v
        print(f"{'OK ' if v else 'BAD'} xcals: {k}")
    row = tbl[tbl.session_date.isin([date(2025, 11, 28), date(2025, 7, 3), date(2025, 10, 14)])]
    print(row.to_string(index=False))
    print("mismatches:", bad)


if __name__ == "__main__":
    main()
