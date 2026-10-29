# =============================================================================
# timing.py — The before/after-market label of each event, from documents
# (ADR 0002 §3, "The default rule"), and the price-gap diagnostic.
#
# THE LABEL COMES FROM DOCUMENTS, NEVER FROM PRICES
#   1. The calendar gives a label: BMO ("Before market open"), AMC ("After
#      market close") or nothing (SQL NULL).
#   2. A press-release look-up, recorded by hand as one row of
#      data/manual/press_release_checks.csv, gives the company's own timing.
#   3. resolve_timing() compares the two and sets timing_used and
#      timing_status. An event nobody looked up is `not_checked` and keeps the
#      calendar label.
#
# THE GAP ONLY DIAGNOSES (local only: Yahoo prices)
#   gap_check() measures the overnight price gap at the two candidate day-0
#   sessions. A gap that contradicts a label never changes it. It only
#   triggers a second, blind reading of the release (daily and mixed), or a
#   look-up (coarse). Every value it returns is class R (suffix _yf).
#
# NOT WIRED: SEC EDGAR. The owner approved it on 2026-10-28, but the contact
# string for its User-Agent has not arrived, so ingest/edgar.py refuses to run
# and no event has timing_source = "edgar" (ADR 0002 status note).
# =============================================================================

import csv
import math
import re
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from earnings_vol.events.calendar import Sessions

CALENDAR_LABELS = {"Before market open": "BMO", "After market close": "AMC"}

CHECK_COLUMNS = ["security_id", "announce_date", "found", "release_date", "release_time_et", "basis",
                 "label", "url", "source_kind", "time_source", "checked_on", "reread", "lookup_minutes", "note"]
# What release_time_et holds (ADR 0002 §3, "How a press release is read"):
#   time_stamp      the release's own time stamp (company page or newswire)
#   announced_time  the release time the company announced beforehand
#   release_text    no time: the label is the release's own words
#   call_time       no time: the label follows from the earnings-call time
BASES = ("time_stamp", "announced_time", "release_text", "call_time")
TIMED_BASES = ("time_stamp", "announced_time")
# What the url is: the company's own page, a newswire's copy, or a third-party
# re-host (kept only where neither of the first two could be found).
SOURCE_KINDS = ("company", "newswire", "aggregator")
# time_source (added after the delta review): the https:// page on which the
# stored release_time_et was read, the url itself when that page shows it. A
# row without a time has none.


def parse_when(value) -> str | None:
    """earnings_calendar.when -> BMO, AMC or None. Any other text is an error.

    data model §1.1 found exactly three values. A fourth would mean the source
    changed, and guessing its meaning could put day 0 on the wrong session.
    """
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if value not in CALENDAR_LABELS:
        raise ValueError(f"unknown earnings_calendar.when value {value!r}")
    return CALENDAR_LABELS[value]


def label_from_time(release_date: date, hhmm: str, sessions: Sessions, close_time_et: dict) -> str | None:
    """The label a release time gives (ADR 0002 §3, "How a press release is read").

    Before 09:30 New York time on a session: BMO. At or after the close (16:00,
    or 13:00 on a half day): AMC. In between: BMO, because D's close follows
    the news, which is what BMO means for day 0. On a non-session day the
    label does not matter (day 0 is the next session), so None.
    """
    if not re.fullmatch(r"\d\d:\d\d", hhmm or ""):
        raise ValueError(f"release time must be HH:MM, got {hhmm!r}")
    if not sessions.is_session(release_date):
        return None
    if hhmm < "09:30":
        return "BMO"
    return "AMC" if hhmm >= close_time_et[release_date] else "BMO"


@dataclass(frozen=True)
class Reading:
    found: bool
    release_date: date | None
    label: str | None
    reread: bool
    checked_on: date


def parse_checks(text: str, sessions: Sessions, close_time_et: dict) -> pd.DataFrame:
    """Read press_release_checks.csv and check every row; raise on the first bad one."""
    # csv reads any iterable of lines; keepends keeps a quoted field's line
    # breaks, as a file would (no io module in a pure middle module).
    reader = csv.DictReader(text.splitlines(keepends=True))
    if reader.fieldnames != CHECK_COLUMNS:
        raise ValueError(f"press_release_checks.csv columns {reader.fieldnames} != {CHECK_COLUMNS}")
    rows = []
    for n, r in enumerate(reader, start=2):
        where = f"press_release_checks.csv line {n}"
        found = {"true": True, "false": False}.get(r["found"])
        reread = {"true": True, "false": False}.get(r["reread"])
        if found is None or reread is None:
            raise ValueError(f"{where}: found and reread must be true or false")
        row = {
            "security_id": r["security_id"],
            "announce_date": date.fromisoformat(r["announce_date"]),
            "found": found,
            "release_date": date.fromisoformat(r["release_date"]) if r["release_date"] else None,
            "release_time_et": r["release_time_et"] or None,
            "basis": r["basis"] or None,
            "label": r["label"] or None,
            "url": r["url"] or None,
            "source_kind": r["source_kind"] or None,
            "time_source": r["time_source"] or None,
            "checked_on": date.fromisoformat(r["checked_on"]),
            "reread": reread,
            "lookup_minutes": float(r["lookup_minutes"]) if r["lookup_minutes"] else None,
            "note": r["note"],
        }
        if found:
            if row["release_date"] is None or row["label"] not in ("BMO", "AMC") or row["basis"] not in BASES:
                raise ValueError(f"{where}: a found release needs release_date, label BMO/AMC and a basis {BASES}")
            if not (row["url"] or "").startswith("https://"):
                raise ValueError(f"{where}: a found release needs its https:// url")
            if row["source_kind"] not in SOURCE_KINDS:
                raise ValueError(f"{where}: source_kind must be one of {SOURCE_KINDS}")
            # The basis says what the stored time is: a time needs a timed basis, and a
            # timed basis needs a time (milestone-1 review, claim 3d).
            if bool(row["release_time_et"]) != (row["basis"] in TIMED_BASES):
                raise ValueError(f"{where}: basis {row['basis']} with release_time_et "
                                 f"{row['release_time_et']!r}: only {TIMED_BASES} hold a time, and they need one")
            if row["release_time_et"]:
                implied = label_from_time(row["release_date"], row["release_time_et"], sessions, close_time_et)
                if implied is not None and implied != row["label"]:
                    raise ValueError(f"{where}: time {row['release_time_et']} on {row['release_date']} "
                                     f"means {implied}, but the label says {row['label']}")
        elif row["release_date"] or row["label"] or row["release_time_et"]:
            raise ValueError(f"{where}: a release that was not found has no date, time or label")
        elif row["source_kind"] is not None and row["source_kind"] not in SOURCE_KINDS:
            raise ValueError(f"{where}: source_kind must be one of {SOURCE_KINDS}")
        # Where the stored time was read (delta review, claim 8a): a time needs its page.
        if bool(row["time_source"]) != bool(row["release_time_et"]):
            raise ValueError(f"{where}: release_time_et {row['release_time_et']!r} with time_source "
                             f"{row['time_source']!r}: a stored time needs the page it was read on, and only a "
                             "time has one")
        if row["time_source"] and not row["time_source"].startswith("https://"):
            raise ValueError(f"{where}: time_source must be an https:// url")
        rows.append(row)
    return pd.DataFrame(rows, columns=CHECK_COLUMNS)


def final_reading(readings: list[Reading]) -> tuple[Reading, bool]:
    """The reading that decides, and whether a gap-triggered re-read changed it.

    ADR 0002 §3: the first reading stands unless a second (blind) reading
    disagrees with it AND a third blind reading agrees with the second.
    """
    first = [r for r in readings if not r.reread]
    rereads = [r for r in readings if r.reread]
    if len(first) != 1:
        raise ValueError(f"an event needs exactly one first reading, got {len(first)}")
    r1 = first[0]
    key = lambda r: (r.found, r.release_date, r.label)  # noqa: E731
    if not rereads:
        return r1, False
    r2 = rereads[0]
    if key(r2) == key(r1):
        return r1, False
    if len(rereads) < 2:
        raise ValueError("the second reading disagrees with the first: a third blind reading is needed")
    r3 = rereads[1]
    return (r2, True) if key(r3) == key(r2) else (r1, False)


def resolve_timing(announce: date, timing_raw: str | None, readings: list[Reading],
                   sessions: Sessions) -> dict:
    """timing_used, timing_status, timing_source, announce_date_used, gap_check_changed for one event."""
    out = {"timing_used": timing_raw, "timing_status": "not_checked",
           "timing_source": "calendar" if timing_raw else None,
           "announce_date_used": announce, "gap_check_changed": False}
    if not readings:
        return out
    r, changed = final_reading(readings)
    out["gap_check_changed"] = changed
    weekend = not sessions.is_session(announce)
    if not r.found:
        if timing_raw is None and not weekend:
            # Looked up, nothing found, and no label: day 0 cannot be placed.
            out.update(timing_used=None, timing_status="ambiguous", timing_source=None)
        else:
            out.update(timing_status="no_document")
        return out
    out.update(timing_used=r.label, timing_source="press_release")
    if r.release_date != announce:
        out.update(timing_status="date_corrected", announce_date_used=r.release_date)
    elif weekend or timing_raw == r.label:
        # For a non-session D only the date is checked; the label cannot move day 0.
        out.update(timing_status="confirmed")
    elif timing_raw is None:
        out.update(timing_status="inferred")
    else:
        out.update(timing_status="corrected")
    return out


# --- the price-gap diagnostic (ADR 0002 §3; local only) ------------------------

def overnight_gaps(stock: pd.DataFrame, market: pd.DataFrame) -> dict:
    """{session date: market-adjusted overnight log gap g_t}.

        g_t = ln((O_t + Div_t) / C_{t-1}) - ln((O^SPY_t + Div^SPY_t) / C^SPY_{t-1})

    Adding back the dividend paid on its ex-date t stops an ex-dividend drop
    from looking like news. The Yahoo prices are split-adjusted on both sides
    of the ratio, so a split creates no gap. C_{t-1} is the previous row's
    close. A day missing from either series has no gap.
    """
    def raw(df):
        o = df["open"].to_numpy() + df["dividends"].to_numpy()
        c_prev = np.concatenate([[np.nan], df["close"].to_numpy()[:-1]])
        with np.errstate(divide="ignore", invalid="ignore"):
            g = np.log(o / c_prev)
        return dict(zip(df["date"], g))
    s, m = raw(stock), raw(market)
    out = {}
    for d, g in s.items():
        if d in m and np.isfinite(g) and np.isfinite(m[d]):
            out[d] = float(g - m[d])
    return out


def gap_check(announce: date, label: str | None, gaps: dict, sessions: Sessions, p_gap) -> dict:
    """The timing_check row (data model §3.9) for one event, all values class R.

    Candidates: z_B at D (when D is a session) and z_A at next(D). The scale is
    the median |gap| over sessions [-60, -22] around as_of(D). Verdicts on
    `label` (ADR 0002 §3): it CONTRADICTS when the other candidate has z >= 4
    and z >= 3x the label's; it SUPPORTS in the reverse case; otherwise QUIET.
    No label, or no second candidate (a non-session D), gives no verdict.
    """
    anchor = sessions.as_of(announce)
    lo, hi = p_gap["scale_window"]
    scale_days = [sessions.shift(anchor, k) for k in range(lo, hi + 1)]
    scale_vals = [abs(gaps[d]) for d in scale_days if d in gaps]
    scale = float(np.median(scale_vals)) if len(scale_vals) >= 10 else np.nan

    def z(d):
        if d is None or d not in gaps or not np.isfinite(scale) or scale <= 0:
            return np.nan
        return abs(gaps[d]) / scale

    d_b = announce if sessions.is_session(announce) else None
    d_a = sessions.next_after(announce)
    z_b, z_a = z(d_b), z(d_a)
    row = {"gap_bmo_yf": gaps.get(d_b, np.nan) if d_b else np.nan, "gap_amc_yf": gaps.get(d_a, np.nan),
           "gap_scale_yf": scale, "z_bmo_yf": z_b, "z_amc_yf": z_a,
           "z_max_outside_yf": np.nan, "rel_day_max_outside_yf": None,
           "gap_verdict_yf": None, "outside_flag_yf": None}

    olo, ohi = p_gap["outside_window"]
    outside = [(k, sessions.shift(anchor, k)) for k in range(olo, ohi + 1)]
    outside = [(k, d) for k, d in outside if d not in (d_b, d_a) and np.isfinite(z(d))]
    if outside:
        k_max, d_max = max(outside, key=lambda kd: z(kd[1]))
        row["z_max_outside_yf"], row["rel_day_max_outside_yf"] = z(d_max), int(k_max)
        cand = max([v for v in (z_b, z_a) if np.isfinite(v)], default=np.nan)
        if np.isfinite(cand):
            row["outside_flag_yf"] = bool(z(d_max) >= p_gap["outside_z_min"] and z(d_max) >= p_gap["ratio"] * cand)

    if label in ("BMO", "AMC") and d_b is not None and np.isfinite(z_b) and np.isfinite(z_a):
        mine, other = (z_b, z_a) if label == "BMO" else (z_a, z_b)
        if other >= p_gap["z_min"] and other >= p_gap["ratio"] * mine:
            row["gap_verdict_yf"] = "contradicts"
        elif mine >= p_gap["z_min"] and mine >= p_gap["ratio"] * other:
            row["gap_verdict_yf"] = "supports"
        else:
            row["gap_verdict_yf"] = "quiet"
    return row


def gap_triggered(row: dict) -> bool:
    """Does the diagnostic ask for a (re-)reading? A contradiction or the outside flag."""
    return row.get("gap_verdict_yf") == "contradicts" or row.get("outside_flag_yf") is True


# --- the build invariant (ADR 0002 §3) ------------------------------------------

def can_enter_sample(announce: date, sessions: Sessions, ranges: dict[str, tuple[date, date]]) -> bool:
    """Can this event's day 0 fall in a sample under EITHER timing?

    The candidates are D itself (BMO; only if D is a session) and next(D)
    (AMC, or any label on a non-session D). An event none of whose candidates
    lies in a sample range (ADR 0004 §5) never reaches a test or the export,
    whatever its label: a date scheduled after the data end, or one before
    the coarse sample starts.
    """
    cands = [sessions.next_after(announce)] + ([announce] if sessions.is_session(announce) else [])
    return any(lo <= c <= hi for c in cands for lo, hi in ranges.values())


def lookup_reasons(announce: date, timing_raw: str | None, triggered: bool, sessions: Sessions,
                   lookup_from: date, sessions_before: int, ranges: dict[str, tuple[date, date]]) -> list[str]:
    """Why the default rule requires a look-up of this event; [] if it does not.

    ADR 0002 §3's build invariant, scoped (milestone-1 review, claim 3b) to
    the events that can_enter_sample(); for those:
    - D from `sessions_before` sessions before lookup_from (2024-09-11) on:
      every event, whatever the gap says, because any of them can land in
      `daily` or `mixed`;
    - a NULL label;
    - a labelled event whose gap contradicts its label or whose outside flag
      fires (the `coarse` trigger).
    """
    if not can_enter_sample(announce, sessions, ranges):
        return []
    reasons = []
    edge = sessions.shift(sessions.first_on_or_after(lookup_from), -sessions_before)
    if announce >= edge:
        reasons.append("daily_or_mixed_era")
    if timing_raw is None:
        reasons.append("null_label")
    if timing_raw is not None and triggered:
        reasons.append("gap_trigger")
    return reasons
