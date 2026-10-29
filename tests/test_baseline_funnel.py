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
# Milestone 2:
#   - the iv_usable step checking day -1 only
#   - the baseline counting sessions without a cm30_iv (rule 4 dropped)
#   - evar_nonpositive counting E < 0 instead of E <= 0
#   - the terciles cut by position in the file instead of by abs_move_cand_max
#   - the tercile ties broken by the later event_id
#   - mean_crush_mean_adj averaging with a missing crush as 0
#   - share_gap_contradicts over every event of the tercile instead of those with a verdict

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


def iv_frame(sessions, sid, missing=(), no_iv=()):
    """An iv_daily-like frame: every session of `sid` ok with a cm30_iv, except `missing` (no
    snapshot) and `no_iv` (a snapshot but no cm30_iv)."""
    return pd.DataFrame({"security_id": sid, "session_date": sessions,
                         "snapshot_status": ["missing" if d in missing else "ok" for d in sessions],
                         "cm30_iv": [None if d in missing or d in no_iv else 0.3 for d in sessions]}) \
        .astype({"cm30_iv": float})


EV_COLS = ["event_id", "security_id", "day0_session", "day_m1_session", "announce_date_used", "exclusion_reason",
           "sample", "timing_status", "gap_check_changed"]
NO_EPS = pd.DataFrame(columns=["security_id", "fiscal_period_end", "event_id", "match_status"])
NO_TC = pd.DataFrame(columns=["event_id", "gap_verdict_yf"])


def test_funnel_steps_hand_counted(sess_table):
    s = calendar.Sessions(sess_table["session_date"].tolist())
    ev = pd.DataFrame([
        # A: daily, everything observed -> survives every step.
        ("X:2025-05-30", "X", date(2025, 6, 2), date(2025, 5, 30), date(2025, 5, 30), None, "daily", "confirmed", False),
        # B: daily, but day -1 (2025-08-29) has no snapshot -> removed at crush_observed.
        ("X:2025-08-29", "X", date(2025, 9, 2), date(2025, 8, 29), date(2025, 8, 29), None, "daily", "not_checked",
         False),
        # C: no label, never looked up, on a session day -> removed at timing_known.
        ("X:2025-12-01", "X", None, None, date(2025, 12, 1), "timing_not_checked", "daily", "not_checked", False),
        # D: day 0 in 2024-08 -> coarse, removed at daily_range.
        ("X:2024-08-01", "X", date(2024, 8, 2), date(2024, 8, 1), date(2024, 8, 1), None, "coarse", "not_checked",
         False),
        # E: daily, but most of its baseline is unobserved -> removed at baseline_minimum.
        ("X:2026-05-29", "X", date(2026, 6, 1), date(2026, 5, 29), date(2026, 5, 29), None, "daily", "corrected",
         False),
        # F: daily, observed, but no cm30_iv on day 0 (2025-06-02) -> removed at iv_usable.
        ("Y:2025-06-02", "Y", date(2025, 6, 2), date(2025, 5, 30), date(2025, 6, 2), None, "daily", "not_checked",
         False),
        # G: daily, everything observed, but no cm30_iv on 22 of its 39 baseline sessions
        #    -> 17 clean sessions, removed at baseline_minimum by rule 4 alone.
        ("Y:2025-10-01", "Y", date(2025, 10, 1), date(2025, 9, 30), date(2025, 10, 1), None, "daily", "not_checked",
         False),
        # H: daily, everything usable -> survives.
        ("Y:2026-02-02", "Y", date(2026, 2, 2), date(2026, 1, 30), date(2026, 2, 2), None, "daily", "not_checked",
         False),
    ], columns=EV_COLS).astype(object)
    e0 = s.index[date(2026, 6, 1)]
    missing = {date(2025, 8, 29)} | {s.dates[i] for i in range(e0 - 60, e0 - 29)}   # E keeps -29 .. -22: 8
    g0 = s.index[date(2025, 10, 1)]
    no_iv_y = {date(2025, 6, 2)} | {s.dates[i] for i in range(g0 - 60, g0 - 38)}      # G keeps -38 .. -22: 17
    iv = pd.concat([iv_frame(s.dates, "X", missing=missing), iv_frame(s.dates, "Y", no_iv=no_iv_y)],
                   ignore_index=True)
    # E made up: A's E > 0 and H's E < 0 (the two survivors).
    eiv = pd.DataFrame({"event_id": ev["event_id"], "abs_move_cand_max": [0.01 * (i + 1) for i in range(8)],
                        "crush_mean_adj": [-0.1] * 8,
                        "evar_m1": [0.002, None, None, None, None, None, None, -0.0001]})
    p = params.load()
    out = funnel.funnel_data(ev, iv, NO_EPS, sess_table, eiv, NO_TC, p, {"x": 1})
    assert [(st["step"], st["n_events"], st["n_removed"]) for st in out["steps"]] == [
        ("calendar_events", 8, 0), ("timing_known", 7, 1), ("daily_range", 6, 1),
        ("crush_observed", 5, 1), ("iv_usable", 4, 1), ("baseline_minimum", 2, 2)]
    counts = funnel.baseline_counts(ev, iv, NO_EPS, s, p["windows"])
    assert counts["Y:2025-10-01"] == BaselineCount(17, 16)
    assert {b["sample"]: b["n_events"] for b in out["by_sample"]} == {"daily": 7, "mixed": 0, "coarse": 1, "none": 0}
    assert out["timing_status_counts"]["not_checked"] == 6 and out["timing_status_counts"]["ambiguous"] == 0
    assert out["lookups"] == {"n_done": 2, "complete": False}
    # A (E = 0.002) and H (E = -0.0001) are left: 2 events, 2 with an E, 1 with E <= 0, share 1/2.
    assert out["evar_nonpositive"] == {"n_events": 2, "n_identified": 2, "n": 1, "share": 0.5}
    assert out["provenance"] == {"x": 1}
    assert funnel.sample_summary(ev, out, p)["n_events"] == 2


def test_evar_nonpositive_counts_zero_as_nonpositive_and_null_as_unidentified(sess_table):
    # The same survivors with E = 0 (A) and no E (H): 2 events, 1 identified, 1 of it <= 0.
    s = calendar.Sessions(sess_table["session_date"].tolist())
    ev = pd.DataFrame([
        ("X:2025-05-30", "X", date(2025, 6, 2), date(2025, 5, 30), date(2025, 5, 30), None, "daily", "confirmed", False),
        ("Y:2026-02-02", "Y", date(2026, 2, 2), date(2026, 1, 30), date(2026, 2, 2), None, "daily", "not_checked",
         False),
    ], columns=EV_COLS).astype(object)
    iv = pd.concat([iv_frame(s.dates, "X"), iv_frame(s.dates, "Y")], ignore_index=True)
    eiv = pd.DataFrame({"event_id": ev["event_id"], "abs_move_cand_max": [0.01, 0.02], "crush_mean_adj": [-0.1, -0.2],
                        "evar_m1": [0.0, None]})
    out = funnel.funnel_data(ev, iv, NO_EPS, sess_table, eiv, NO_TC, params.load(), {})
    assert out["evar_nonpositive"] == {"n_events": 2, "n_identified": 1, "n": 1, "share": 1.0}
    assert "1 have no E at day -1" in out["evar_nonpositive_status"]


def test_move_terciles_hand_counted():
    # Daily: 7 events, one a duplicate row (left out) -> 6, so 2 per tercile:
    # rank r of 6 goes to tercile 1 + floor(3r/6): ranks 0,1 -> 1; 2,3 -> 2; 4,5 -> 3.
    # Sorted by abs_move_cand_max, ties by event_id: a (0.01), c (0.02, tie with b: "b" < "c" so b first),
    #   order a 0.01, b 0.02, c 0.02, d 0.05, e 0.08, f 0.09 -> terciles {a,b}, {c,d}, {e,f}.
    # The file lists them shuffled, so a cut by position would differ.
    # Mixed: one event with no move: left out, so its terciles are empty.
    # Gap verdicts (made up): a supports, b contradicts -> 1/2; c none, d quiet -> 0/1; e and f none -> null.
    rows = [("d", 0.05, "confirmed", True, -0.30), ("a", 0.01, "not_checked", False, -0.10),
            ("f", 0.09, "corrected", False, None), ("c", 0.02, "not_checked", False, -0.20),
            ("e", 0.08, "not_checked", True, -0.40), ("b", 0.02, "inferred", False, -0.12)]
    ev = pd.DataFrame([(eid, "daily", st, ch, None) for eid, _, st, ch, _ in rows]
                      + [("dup", "daily", "not_checked", False, "duplicate_row"),
                         ("m", "mixed", "not_checked", False, None)],
                      columns=["event_id", "sample", "timing_status", "gap_check_changed", "exclusion_reason"])
    eiv = pd.DataFrame({"event_id": [r[0] for r in rows] + ["dup", "m"],
                        "abs_move_cand_max": [r[1] for r in rows] + [0.5, None],
                        "crush_mean_adj": [r[4] for r in rows] + [-0.9, -0.9]})
    tc = pd.DataFrame({"event_id": ["a", "b", "d"], "gap_verdict_yf": ["supports", "contradicts", "quiet"]})
    got = {(t["sample"], t["tercile"]): t for t in funnel.move_terciles(ev, eiv, tc)}
    assert [(k, v["n_events"]) for k, v in got.items()] == [
        (("daily", 1), 2), (("daily", 2), 2), (("daily", 3), 2), (("mixed", 1), 0), (("mixed", 2), 0),
        (("mixed", 3), 0), (("coarse", 1), 0), (("coarse", 2), 0), (("coarse", 3), 0)]
    t1, t2, t3 = got[("daily", 1)], got[("daily", 2)], got[("daily", 3)]
    # {a, b}: not_checked + inferred; moves 0.01, 0.02 -> mean 0.015; crush -0.10, -0.12 -> -0.11.
    assert (t1["timing_status_counts"]["not_checked"], t1["timing_status_counts"]["inferred"]) == (1, 1)
    assert t1["mean_abs_move"] == 0.015 and t1["mean_crush_mean_adj"] == -0.11 and t1["n_crush"] == 2
    assert t1["share_gap_contradicts"] == 0.5 and t2["share_gap_contradicts"] == 0.0
    # {c, d}: d was changed by a gap check; crush -0.20, -0.30 -> -0.25; moves (0.02 + 0.05)/2 = 0.035.
    assert t2["n_gap_check_changed"] == 1 and t2["mean_crush_mean_adj"] == -0.25 and t2["mean_abs_move"] == 0.035
    # {e, f}: f has no crush, so the mean is e's alone (-0.40), over n_crush = 1.
    assert t3["mean_crush_mean_adj"] == -0.4 and t3["n_crush"] == 1 and t3["n_events"] == 2
    assert t3["timing_status_counts"]["corrected"] == 1 and t3["share_gap_contradicts"] is None
    assert got[("mixed", 1)]["mean_abs_move"] is None and got[("mixed", 1)]["mean_crush_mean_adj"] is None


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
        ("X:2025-06-02", "X", date(2025, 6, 2), date(2025, 5, 30), date(2025, 6, 2), None, "daily", "not_checked",
         False),
        ("X:2025-05-27", "X", None, None, date(2025, 5, 27), "duplicate_row", "daily", "not_checked", False),
        (f"X:{s.dates[a]}", "X", s.dates[a], s.dates[a - 1], s.dates[a], None, "daily", "not_checked", False),
    ], columns=EV_COLS).astype(object)
    iv = iv_frame(s.dates, "X")
    eiv = pd.DataFrame({"event_id": ev["event_id"], "abs_move_cand_max": [0.01, 0.02, 0.03],
                        "crush_mean_adj": [-0.1] * 3, "evar_m1": [0.001] * 3})
    p = params.load()
    counts = funnel.baseline_counts(ev, iv, NO_EPS, s, p["windows"])
    assert counts[f"X:{s.dates[a]}"] == BaselineCount(9, 8)
    assert "X:2025-05-27" not in counts
    out = funnel.funnel_data(ev, iv, NO_EPS, sess_table, eiv, NO_TC, p, {})
    assert [(st["step"], st["n_events"], st["n_removed"]) for st in out["steps"][:2]] == [
        ("calendar_events", 3, 0), ("timing_known", 2, 1)]
    assert out["steps"][1]["reason"] == "duplicate_row|timing_ambiguous|timing_not_checked"

