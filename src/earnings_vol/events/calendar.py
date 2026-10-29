# =============================================================================
# calendar.py — NYSE sessions, and day 0 (ADR 0002 §1, §2).
#
# THE CLOCK
#   Event time counts NYSE sessions, not calendar days. A session is a day the
#   exchange is open. Weekends and holidays are not sessions. A half day (13:00
#   close) is a session. The list comes from the exchange_calendars package
#   (calendar XNYS), pinned in pyproject.toml.
#
# DAY 0 (ADR 0002 §2)
#   Day 0 is the first session whose CLOSING option snapshot was taken after
#   the announcement. Day -1 is the last session whose closing snapshot came
#   before it. With D the announcement date:
#
#     timing                     day -1            day 0
#     BMO, D is a session        the session       D
#                                before D
#     AMC, D is a session        D                 the session after D
#     any, D is not a session    the last session  the first session
#                                before D          after D
#     unknown, D is a session    -- not defined: the event is excluded --
#
#   A release timed inside the session (09:30-16:00) is stored as BMO: D's
#   close follows the news, so day 0 is D (ADR 0002 §3).
# =============================================================================

from bisect import bisect_left, bisect_right
from datetime import date

import exchange_calendars as xcals
import pandas as pd


class Sessions:
    """A sorted list of session dates with the look-ups the events layer needs."""

    def __init__(self, dates: list[date]):
        if list(dates) != sorted(set(dates)):
            raise ValueError("session dates must be sorted and unique")
        self.dates = list(dates)
        self.index = {d: i for i, d in enumerate(self.dates)}

    def is_session(self, d: date) -> bool:
        return d in self.index

    def _check_range(self, d: date) -> None:
        if not self.dates[0] <= d <= self.dates[-1]:
            raise ValueError(f"{d} is outside the session table {self.dates[0]} .. {self.dates[-1]}")

    def next_after(self, d: date) -> date:
        """The first session strictly after d."""
        self._check_range(d)
        i = bisect_right(self.dates, d)
        if i >= len(self.dates):
            raise ValueError(f"no session after {d}")
        return self.dates[i]

    def prev_before(self, d: date) -> date:
        """The last session strictly before d."""
        self._check_range(d)
        i = bisect_left(self.dates, d)
        if i == 0:
            raise ValueError(f"no session before {d}")
        return self.dates[i - 1]

    def as_of(self, d: date) -> date:
        """d if it is a session, otherwise the last session before it (ADR 0002 §1)."""
        return d if d in self.index else self.prev_before(d)

    def first_on_or_after(self, d: date) -> date:
        return d if d in self.index else self.next_after(d)

    def shift(self, session: date, k: int) -> date:
        """The session k sessions after `session` (k < 0: before)."""
        i = self.index[session] + k
        if not 0 <= i < len(self.dates):
            raise ValueError(f"{k} sessions from {session} is outside the session table")
        return self.dates[i]

    def between(self, a: date, b: date) -> int:
        """Sessions from session a to session b: index(b) - index(a)."""
        return self.index[b] - self.index[a]


def build_session_table(start: date, end: date, eras: dict) -> pd.DataFrame:
    """The `session` table (data model §3.3) from XNYS, start..end inclusive.

    `eras` holds the snapshot-era boundaries from params.yaml (snapshot_eras):
    weekly from weekly_from, Mon/Wed/Fri from mwf_from, daily from daily_from
    up to data_end, and `none` outside.
    """
    cal = xcals.get_calendar("XNYS", start=str(start), end=str(end))
    sessions = cal.sessions
    closes = cal.closes.dt.tz_convert("America/New_York")
    weekly, mwf = date.fromisoformat(eras["weekly_from"]), date.fromisoformat(eras["mwf_from"])
    daily, data_end = date.fromisoformat(eras["daily_from"]), date.fromisoformat(eras["data_end"])
    rows = []
    for i, ts in enumerate(sessions):
        d = ts.date()
        close = closes.loc[ts]
        close_time = f"{close.hour:02d}:{close.minute:02d}"
        if d < weekly or d > data_end:
            era = "none"
        elif d < mwf:
            era = "weekly"
        elif d < daily:
            era = "mwf"
        else:
            era = "daily"
        rows.append({"session_date": d, "session_index": i, "is_half_day": close_time != "16:00",
                     "close_time_et": close_time, "era": era})
    return pd.DataFrame(rows, columns=["session_date", "session_index", "is_half_day", "close_time_et", "era"])


def day0(announce: date, timing: str | None, sessions: Sessions) -> tuple[date | None, date | None]:
    """(day 0, day -1) for an announcement on `announce` with timing BMO/AMC/None.

    Returns (None, None) when D is a session and the timing is unknown: then
    day 0 depends on the label, and nothing decides it (ADR 0002 §2, the
    `ambiguous` row).
    """
    if timing not in ("BMO", "AMC", None):
        raise ValueError(f"timing must be BMO, AMC or None, got {timing!r}")
    if not sessions.is_session(announce):
        # Weekend or holiday release: the news is out before the next open
        # whatever the label says.
        return sessions.next_after(announce), sessions.prev_before(announce)
    if timing == "BMO":
        return announce, sessions.prev_before(announce)
    if timing == "AMC":
        return sessions.next_after(announce), announce
    return None, None


def effective_day0(announce: date, day0_session: date | None, sessions: Sessions) -> date:
    """Day 0, or next(D) when day 0 is undefined (data model §3.7, exclusion_reason)."""
    return day0_session if day0_session is not None else sessions.next_after(announce)


def season(d: date) -> str:
    """The calendar quarter of a date, e.g. 2025Q1."""
    return f"{d.year}Q{(d.month - 1) // 3 + 1}"
