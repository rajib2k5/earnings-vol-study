# Tests for panel/baseline.py (ADR 0004 §1) and export/funnel.py (the
# sample_funnel view), on hand-built fixtures with hand-counted answers.
#
# Mutations this module must catch (applied by hand, each seen to fail):
#   - clean_baseline counting a change whose earlier end is outside the window
# (Not a mutant: dropping the "skip the event's own zone" test changes nothing,
# because the own zone [-21, +10] never meets the baseline [-60, -22].)
#   - the funnel's crush step checking day 0 only
#   - the funnel's baseline step using fixed thresholds instead of the parameters
#   - a duplicate_row's zone counted in other events' baselines
#   - the funnel's timing_known step keeping a duplicate_row

from datetime import date

import pandas as pd
import pytest

from earnings_vol import params
from earnings_vol.events import calendar
from earnings_vol.export import funnel
from earnings_vol.panel.baseline import BaselineCount, clean_baseline, zones_of_events


def test_clean_baseline_hand_counted():
    # Day 0 at session 100: the baseline is sessions 40 .. 78 (rel_day -60 .. -22).
    # Another event centred at 50 blocks [29, 60]; an orphan zone blocks [75, 76];
    # sessions 45 and 46 are unobserved (already blocked anyway).
    # Clean: 61 .. 74 (14 sessions) and 77, 78 (2) = 16 sessions.
    # Changes with both ends clean: 61->62 .. 73->74 (13) and 77->78 (1) = 14.
    # 40 -> 41 would need 40 clean and is blocked; 60 -> 61 has a blocked start.
    zones = zones_of_events([("me", [100]), ("other", [50])], (-21, 10))
    assert zones == {"me": [(79, 110)], "other": [(29, 60)]}
    observed = set(range(0, 200)) - {45, 46}
    got = clean_baseline(100, "me", zones, [(75, 76)], observed, (-60, -22))
    assert got == BaselineCount(16, 14)
    assert not got.passes(20, 15) and got.passes(16, 14)


def test_clean_baseline_window_edge_change_is_not_counted():
    # Everything observed, nothing blocked: 39 sessions (40 .. 78) and 38 changes,
    # because the change 39 -> 40 starts outside the window.
    got = clean_baseline(100, "me", {"me": [(79, 110)]}, [], set(range(200)), (-60, -22))
    assert got == BaselineCount(39, 38)


def test_an_event_without_day0_blocks_around_both_candidates():
    zones = zones_of_events([("amb", [50, 51])], (-21, 10))
    assert zones == {"amb": [(29, 60), (30, 61)]}


@pytest.fixture(scope="module")
def sess_table():
    return calendar.build_session_table(date(2024, 1, 1), date(2026, 12, 31),
                                        {"weekly_from": "2019-02-09", "mwf_from": "2020-01-06",
                                         "daily_from": "2024-09-11", "data_end": "2026-10-26"})


def test_funnel_steps_hand_counted(sess_table):
    s = calendar.Sessions(sess_table["session_date"].tolist())
    ev = pd.DataFrame([
        # A: daily, everything observed -> survives every step.
        ("X:2025-05-30", "X", date(2025, 6, 2), date(2025, 5, 30), date(2025, 5, 30), None, "daily", "confirmed"),
        # B: daily, but day -1 (2025-08-29) has no snapshot -> removed at crush_observed.
        ("X:2025-08-29", "X", date(2025, 9, 2), date(2025, 8, 29), date(2025, 8, 29), None, "daily", "not_checked"),
        # C: no label, never looked up, on a session day -> removed at timing_known.
        ("X:2025-12-01", "X", None, None, date(2025, 12, 1), "timing_not_checked", "daily", "not_checked"),
        # D: day 0 in 2024-08 -> coarse, removed at daily_range.
        ("X:2024-08-01", "X", date(2024, 8, 2), date(2024, 8, 1), date(2024, 8, 1), None, "coarse", "not_checked"),
        # E: daily, but most of its baseline is unobserved -> removed at baseline_minimum.
        ("X:2026-05-29", "X", date(2026, 6, 1), date(2026, 5, 29), date(2026, 5, 29), None, "daily", "corrected"),
    ], columns=["event_id", "security_id", "day0_session", "day_m1_session", "announce_date_used",
                "exclusion_reason", "sample", "timing_status"]).astype(object)
    e0 = s.index[date(2026, 6, 1)]
    missing = {date(2025, 8, 29)} | {s.dates[i] for i in range(e0 - 60, e0 - 29)}   # E keeps -29 .. -22: 8
    snap = pd.DataFrame({"security_id": "X", "session_date": s.dates,
                         "snapshot_status": ["missing" if d in missing else "ok" for d in s.dates]})
    eps = pd.DataFrame(columns=["security_id", "fiscal_period_end", "event_id", "match_status"])
    p = params.load()
    out = funnel.funnel_data(ev, snap, eps, sess_table, p, {"x": 1})
    assert [(st["step"], st["n_events"], st["n_removed"]) for st in out["steps"]] == [
        ("calendar_events", 5, 0), ("timing_known", 4, 1), ("daily_range", 3, 1),
        ("crush_observed", 2, 1), ("baseline_minimum", 1, 1)]
    assert {b["sample"]: b["n_events"] for b in out["by_sample"]} == {"daily": 4, "mixed": 0, "coarse": 1, "none": 0}
    assert out["timing_status_counts"]["not_checked"] == 3 and out["timing_status_counts"]["ambiguous"] == 0
    assert out["lookups"] == {"n_done": 2, "complete": False}
    assert out["by_move_tercile"] is None and out["provenance"] == {"x": 1}
    assert funnel.sample_summary(ev, out, p)["n_events"] == 1


def test_a_duplicate_row_blocks_no_session_and_leaves_at_timing_known(sess_table):
    # R: a release with day 0 at session r. D: a second calendar row of R's release, 4 sessions
    # earlier with no label (duplicate_row; its candidates would be r-4 and r-3). A: day 0 at
    # r + 30, so its baseline is r-30 .. r+8. R's zone [r-21, r+10] blocks r-21 .. r+8, which
    # leaves r-30 .. r-22: 9 clean sessions and 8 changes. D's zones would also block
    # r-25 .. r-22 (5 sessions and 4 changes left), but D's release is R, whose zone is R's own.
    s = calendar.Sessions(sess_table["session_date"].tolist())
    r = s.index[date(2025, 6, 2)]
    assert s.dates[r - 4] == date(2025, 5, 27)          # Memorial Day 05-26 is closed
    a = r + 30
    ev = pd.DataFrame([
        ("X:2025-06-02", "X", date(2025, 6, 2), date(2025, 5, 30), date(2025, 6, 2), None, "daily", "not_checked"),
        ("X:2025-05-27", "X", None, None, date(2025, 5, 27), "duplicate_row", "daily", "not_checked"),
        (f"X:{s.dates[a]}", "X", s.dates[a], s.dates[a - 1], s.dates[a], None, "daily", "not_checked"),
    ], columns=["event_id", "security_id", "day0_session", "day_m1_session", "announce_date_used",
                "exclusion_reason", "sample", "timing_status"]).astype(object)
    snap = pd.DataFrame({"security_id": "X", "session_date": s.dates, "snapshot_status": "ok"})
    eps = pd.DataFrame(columns=["security_id", "fiscal_period_end", "event_id", "match_status"])
    p = params.load()
    counts = funnel.baseline_counts(ev, snap, eps, s, p["windows"])
    assert counts[f"X:{s.dates[a]}"] == BaselineCount(9, 8)
    assert "X:2025-05-27" not in counts
    out = funnel.funnel_data(ev, snap, eps, sess_table, p, {})
    assert [(st["step"], st["n_events"], st["n_removed"]) for st in out["steps"][:2]] == [
        ("calendar_events", 3, 0), ("timing_known", 2, 1)]
    assert out["steps"][1]["reason"] == "duplicate_row|timing_ambiguous|timing_not_checked"

