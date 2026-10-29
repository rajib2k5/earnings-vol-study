# =============================================================================
# baseline.py — Which sessions of an event's baseline are clean (ADR 0004 §1).
#
#   start from rel_day -60 .. -22 around day 0, then remove every session
#     1. inside [-21, +10] of ANOTHER event of the same security (for an event
#        without a day 0, around both candidate days D and next(D));
#     2. inside an orphan or pre-calendar EPS zone (period end + 10 .. + 60);
#     3. not observed: no snapshot, or a stale_repeat snapshot;
#     4. with no cm30_iv (known only from milestone 2 on; not applied here).
#   The event keeps its baseline if at least 20 sessions and at least 15
#   one-session changes (both ends clean) are left.
#
# Milestone 1 applies rules 1-3. Rule 4 can only remove more sessions, so the
# counts here are upper bounds of the final ones.
# =============================================================================

from dataclasses import dataclass


@dataclass(frozen=True)
class BaselineCount:
    n_sessions: int
    n_changes: int

    def passes(self, min_sessions: int, min_changes: int) -> bool:
        return self.n_sessions >= min_sessions and self.n_changes >= min_changes


def zones_of_events(centres: list[tuple[str, list[int]]], zone: tuple[int, int]) -> dict[str, list[tuple[int, int]]]:
    """{event_id: [(lo, hi)]}: an event's [-21, +10] zone around each of its centre sessions."""
    return {eid: [(c + zone[0], c + zone[1]) for c in cs] for eid, cs in centres}


def clean_baseline(day0_index: int, own_id: str, event_zones: dict[str, list[tuple[int, int]]],
                   orphan_zones: list[tuple[int, int]], observed: set[int],
                   window: tuple[int, int]) -> BaselineCount:
    """Count the clean sessions and clean one-session changes of one event.

    All dates are session indices. `event_zones` holds the zones of every
    event of the same security; the event's own zone is skipped. `observed`
    holds the indices of sessions with an ok snapshot.
    """
    lo, hi = day0_index + window[0], day0_index + window[1]
    blocked = [z for eid, zs in event_zones.items() if eid != own_id for z in zs] + list(orphan_zones)
    clean = [t for t in range(lo, hi + 1)
             if t in observed and not any(a <= t <= b for a, b in blocked)]
    cs = set(clean)
    changes = sum(1 for t in clean if t - 1 in cs)
    return BaselineCount(len(clean), changes)
