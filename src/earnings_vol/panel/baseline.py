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
# Milestone 1 applied rules 1-3; the funnel applies rule 4 since milestone 2
# (export/funnel.py passes only sessions with a cm30_iv as observed).
#
# Milestone 3 adds event_centres() (moved here from the funnel, so the funnel
# and the panel place every zone the same way) and baseline_reasons(): why each
# session of the baseline range is or is not clean, for event_window_obs.
# =============================================================================

from dataclasses import dataclass

from earnings_vol.events import calendar


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


def event_centres(events, sessions: calendar.Sessions) -> list[tuple[str, list[int]]]:
    """[(event_id, [centre session index, ...])] for the zones of one security's events.

    `events` holds one security's rows of the events table. A duplicate_row is a second
    calendar row of another event's release: it has no zone of its own. An event with a
    day 0 is centred on it; one without (ambiguous or not checked) on both candidates,
    next(D) and D itself when D is a session (ADR 0004 §1).
    """
    centres = []
    for r in events.itertuples(index=False):
        if r.exclusion_reason == "duplicate_row":
            continue
        if r.day0_session is not None:
            centres.append((r.event_id, [sessions.index[r.day0_session]]))
        else:
            a = r.announce_date_used
            cands = [sessions.next_after(a)] + ([a] if sessions.is_session(a) else [])
            centres.append((r.event_id, [sessions.index[c] for c in cands]))
    return centres


# Why a session of the baseline range [-60, -22] is not clean, in this order (data model §3.10).
REASONS = ("other_event_zone", "orphan_zone", "not_observed", "null_iv")


def baseline_reasons(day0_index: int, own_id: str, event_zones: dict[str, list[tuple[int, int]]],
                     orphan_zones: list[tuple[int, int]], observed: set[int], has_iv: set[int],
                     window: tuple[int, int]) -> dict[int, str | None]:
    """{session index: None if clean, else the first rule it fails} over the baseline range.

    `observed` holds the sessions with an ok snapshot, `has_iv` those that also have a
    cm30_iv. The clean sessions are exactly those clean_baseline() counts when it is
    given `has_iv` as its observed set.
    """
    lo, hi = day0_index + window[0], day0_index + window[1]
    others = [z for eid, zs in event_zones.items() if eid != own_id for z in zs]
    out = {}
    for t in range(lo, hi + 1):
        if any(a <= t <= b for a, b in others):
            out[t] = "other_event_zone"
        elif any(a <= t <= b for a, b in orphan_zones):
            out[t] = "orphan_zone"
        elif t not in observed:
            out[t] = "not_observed"
        elif t not in has_iv:
            out[t] = "null_iv"
        else:
            out[t] = None
    return out
