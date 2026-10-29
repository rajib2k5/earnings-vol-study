# The invariants of data model §3.7 and §3.8, checked on the COMMITTED tables
# in data/derived/ (no cache, no network), plus the check functions themselves
# on hand-built broken fixtures, so that a check that can never fail is caught.
#
# Mutations this module must catch (applied by hand, each seen to fail):
#   - one event's fiscal_period_end corrupted in the committed events.parquet
#     (invariant 3; the file was restored afterwards)
#   - check_chain without the traversal check (the detached loop below passes)
# The matcher's own mutants (window bounds, first-in-window, most-links-first,
# the tie order) are caught by tests/test_eps.py, on fixtures.

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from earnings_vol import schema, store
from earnings_vol.events import events as events_mod

DERIVED = Path(__file__).resolve().parents[1] / "data" / "derived"


@pytest.fixture(scope="module")
def ev():
    return store.read_table(DERIVED / "events.parquet", schema.EVENTS)


@pytest.fixture(scope="module")
def eps():
    return store.read_table(DERIVED / "eps.parquet", schema.EPS)


def test_1_every_linked_event_exists_and_is_linked_once(ev, eps):
    linked = eps["event_id"].dropna()
    assert set(linked) <= set(ev["event_id"])
    assert not linked.duplicated().any()


def test_2_linked_pairs_share_the_security(ev, eps):
    m = eps.dropna(subset=["event_id"]).merge(ev[["event_id", "security_id"]], on="event_id", suffixes=("", "_ev"))
    assert (m["security_id"] == m["security_id_ev"]).all()


def test_3_events_fiscal_period_end_is_the_linked_copy(ev, eps):
    link = dict(zip(eps["event_id"], eps["fiscal_period_end"]))
    for eid, fpe in zip(ev["event_id"], ev["fiscal_period_end"]):
        assert fpe == link.get(eid), eid   # None on both sides when unlinked


def test_4_null_event_iff_orphan_or_pre_calendar(eps):
    unlinked = eps["event_id"].isna()
    assert (unlinked == eps["match_status"].isin(["orphan", "pre_calendar"])).all()
    assert (eps["lag_days"].isna() == unlinked).all()


def test_5_every_link_is_in_its_window_and_the_links_keep_their_order(ev, eps):
    # The window: from 14 days after the first day of the period end's month to 100 days after
    # the period end. The assignment keeps order: a later period of a security never has an
    # earlier event.
    ann = dict(zip(ev["event_id"], ev["announce_date"]))
    linked = eps.dropna(subset=["event_id"])
    for r in linked.itertuples(index=False):
        lo = r.fiscal_period_end.replace(day=1) + timedelta(days=14)
        assert lo <= ann[r.event_id] <= r.fiscal_period_end + timedelta(days=100)
        assert r.lag_days == (ann[r.event_id] - r.fiscal_period_end).days
    for sid, g in linked.groupby("security_id"):
        days = [ann[e] for e in g.sort_values("fiscal_period_end")["event_id"]]
        assert days == sorted(days) and len(set(days)) == len(days), sid


def test_6_ticker_conflict_has_no_eps_values(eps):
    tc = eps[eps["match_status"] == "ticker_conflict"]
    assert tc["reported"].isna().all() and tc["estimate"].isna().all()


def test_chain_invariants_hold_on_the_committed_events(ev):
    assert events_mod.check_chain(ev) == []


def chain(rows):
    return pd.DataFrame(rows, columns=["event_id", "security_id", "announce_date", "prev_event_id",
                                       "next_event_id"], dtype=object)


def test_check_chain_finds_a_detached_loop():
    # A -> B is a correct chain. C <-> D is a loop that is attached to nothing.
    # Every link is mirrored and stays within one security, so only the
    # traversal from the first event can see that C and D are never reached.
    d = date(2025, 1, 1)
    rows = [("A", "X", d, None, "B"), ("B", "X", d + timedelta(1), "A", None),
            ("C", "X", d + timedelta(2), "D", "D"), ("D", "X", d + timedelta(3), "C", "C")]
    problems = events_mod.check_chain(chain(rows))
    assert any("visits 2 of 4" in p for p in problems), problems


def test_check_chain_finds_an_unmirrored_link_and_a_cross_security_link():
    d = date(2025, 1, 1)
    p1 = events_mod.check_chain(chain([("A", "X", d, None, "B"), ("B", "X", d + timedelta(1), None, None)]))
    assert any("prev_event_id = None" in p for p in p1)
    p2 = events_mod.check_chain(chain([("A", "X", d, None, "B"), ("B", "Y", d + timedelta(1), "A", None)]))
    assert any("crosses securities" in p for p in p2)


def test_duplicate_rows_have_no_link_and_one_row_per_release_is_kept(ev, eps):
    # ADR 0002 note 3 (delta review, claim 1a): BRK.B's Friday 2024-11-01 row beside its
    # Saturday 2024-11-02 release. The duplicate is excluded and unlinked; the release carries
    # the 2024-09-30 period.
    e = ev.set_index("event_id")
    assert e.loc["BRK.B:2024-11-01", "exclusion_reason"] == "duplicate_row"
    assert e.loc["BRK.B:2024-11-02", "fiscal_period_end"] == date(2024, 9, 30)
    dups = ev[ev["exclusion_reason"] == "duplicate_row"]
    assert dups["fiscal_period_end"].isna().all() and not set(dups["event_id"]) & set(eps["event_id"].dropna())
    # Every group of rows of one security within 14 days keeps exactly one row.
    for sid, g in ev.sort_values("announce_date_used").groupby("security_id"):
        days, kept = list(g["announce_date_used"]), list(g["exclusion_reason"] != "duplicate_row")
        groups = [[kept[0]]]
        for a, b, k in zip(days, days[1:], kept[1:]):
            if (b - a).days <= 14:
                groups[-1].append(k)
            else:
                groups.append([k])
        assert all(sum(grp) == 1 for grp in groups), sid


def test_7_a_period_whose_report_is_missing_does_not_take_the_next_one():
    # Covered on hand-built data in test_eps.py (the Costco- and Oracle-shaped fixtures).
    # 2025-06-30's report is missing; 2025-10-07 is 99 days after it but 7 after 2025-09-30.
    from earnings_vol.events.eps import match_periods
    out = match_periods([date(2025, 6, 30), date(2025, 9, 30)], [(date(2025, 10, 7), "A")],
                        window_start="month_start+14", lag_max=100, calendar_start=date(2020, 1, 22))
    assert out[date(2025, 9, 30)] == ("A", "matched") and out[date(2025, 6, 30)] == (None, "orphan")
