"""p07: the sample funnel, re-counted independently from committed tables (claims 5c, 6a-6c, 13 P3).

  uv run python docs/validation/probes/m1/p07_funnel_independent.py

The baseline rule is written here from ADR 0004 §1's text, not imported:
  baseline = sessions [d0-60, d0-22]; drop a session inside [-21, +10] of ANY OTHER event
  of the same security (both candidates D and next(D) for an event without day 0), inside
  an orphan/pre-calendar zone (period end + 10 .. + 60 sessions from the first session on
  or after the period end), or not observed (snapshot_status != ok). Keep the event if
  >= 20 clean sessions and >= 15 changes with both ends clean.
Then the same count with the orphan zones rebuilt from a corrected EPS match
(lag window -10..100 instead of 10..100; see p06), to measure what the matching defect does to 348.
"""
import datetime as dt
from collections import Counter

import numpy as np
import pandas as pd

from earnings_vol.events.run import DERIVED

D = DERIVED


def load():
    ev = pd.read_parquet(D / "events.parquet")
    ev = ev.astype(object).where(ev.notna(), None)
    eps = pd.read_parquet(D / "eps.parquet").astype(object)
    snap = pd.read_parquet(D / "session_snapshot.parquet")
    sess = sorted(pd.read_parquet(D / "session.parquet").session_date)
    return ev, eps, snap, sess


def count(ev, orphan_periods, snap, sess):
    idx = {d: i for i, d in enumerate(sess)}

    def nxt(d):
        return next(s for s in sess if s > d)

    def first_on_or_after(d):
        return next(s for s in sess if s >= d)

    ok = {(s, idx[d]) for s, d, st in zip(snap.security_id, snap.session_date, snap.snapshot_status) if st == "ok"}
    zones = {}
    for sid, pe in orphan_periods:
        b = idx[first_on_or_after(pe)]
        zones.setdefault(sid, []).append((b + 10, b + 60))
    centres = {}
    for r in ev.itertuples():
        if r.day0_session is not None:
            c = [idx[r.day0_session]]
        else:
            a = r.announce_date_used
            c = [idx[nxt(a)]] + ([idx[a]] if a in idx else [])
        centres[r.event_id] = (r.security_id, c)
    out = {}
    for r in ev.itertuples():
        if r.day0_session is None:
            continue
        d0 = idx[r.day0_session]
        blocked = [(c - 21, c + 10) for e, (s, cs) in centres.items() if s == r.security_id and e != r.event_id
                   for c in cs] + zones.get(r.security_id, [])
        clean = [t for t in range(d0 - 60, d0 - 21) if (r.security_id, t) in ok
                 and not any(a <= t <= b for a, b in blocked)]
        cs = set(clean)
        out[r.event_id] = (len(clean), sum(1 for t in clean if t - 1 in cs))
    return out


def funnel(ev, base, snap):
    st = {(s, d): x for s, d, x in zip(snap.security_id, snap.session_date, snap.snapshot_status)}
    s1 = ev
    s2 = s1[~s1.exclusion_reason.isin(["timing_ambiguous", "timing_not_checked"])]
    s3 = s2[s2["sample"] == "daily"]
    obs = [st.get((s, m)) == "ok" and st.get((s, z)) == "ok" for s, m, z in
           zip(s3.security_id, s3.day_m1_session, s3.day0_session)]
    s4 = s3[obs]
    s5 = s4[[base[e][0] >= 20 and base[e][1] >= 15 for e in s4.event_id]]
    return [s1, s2, s3, s4, s5]


def corrected_orphans(ev, eps):
    """Re-match with lag -10..100 (independent code; same first-event and tie rules)."""
    out = []
    by = {s: sorted(zip(g.announce_date, g.event_id)) for s, g in ev.groupby("security_id")}
    for s, g in eps.groupby("security_id"):
        prop = {}
        for pe in g.fiscal_period_end:
            c = [(d, e) for d, e in by.get(s, []) if -10 <= (d - pe).days <= 100]
            prop[pe] = min(c) if c else None
        claim = {}
        for pe, c in prop.items():
            if c:
                claim.setdefault(c[1], []).append(pe)
        for pe, c in prop.items():
            if c is None or min(claim[c[1]], key=lambda q: (c[0] - q).days) != pe:
                out.append((s, pe))       # orphan or pre_calendar: both are zones
    return out


def main():
    ev, eps, snap, sess = load()
    orph = [(s, pe) for s, pe, m in zip(eps.security_id, eps.fiscal_period_end, eps.match_status)
            if m in ("orphan", "pre_calendar")]
    base = count(ev, orph, snap, sess)
    steps = funnel(ev, base, snap)
    print("funnel (independent):", [len(x) for x in steps])
    s3, s4, s5 = steps[2], steps[3], steps[4]
    print("removed at crush_observed:")
    st = {(s, d): x for s, d, x in zip(snap.security_id, snap.session_date, snap.snapshot_status)}
    for r in s3[~s3.event_id.isin(s4.event_id)].itertuples():
        print(f"   {r.event_id:18s} day-1 {r.day_m1_session} {st.get((r.security_id, r.day_m1_session))}"
              f" day0 {r.day0_session} {st.get((r.security_id, r.day0_session))}")
    print("removed at baseline_minimum:")
    for r in s4[~s4.event_id.isin(s5.event_id)].itertuples():
        print(f"   {r.event_id:18s} clean={base[r.event_id]}")
    daily = s3.event_id
    n20 = sum(base[e][0] >= 20 and base[e][1] >= 15 for e in daily)
    vals = np.array([base[e][0] for e in daily])
    print(f"P3: {n20} of {len(daily)} daily events with day 0 have >=20 clean & >=15 changes; "
          f"clean sessions median {np.median(vals)}, p5 {np.percentile(vals, 5)}")
    print("securities among the final events:", s5.security_id.nunique(), "; among the 368 daily:",
          ev[ev["sample"] == "daily"].security_id.nunique())

    # Sensitivity: orphan zones from the corrected match.
    orph2 = corrected_orphans(ev, eps)
    base2 = count(ev, orph2, snap, sess)
    steps2 = funnel(ev, base2, snap)
    print("\nfunnel with zones from the corrected EPS match:", [len(x) for x in steps2])
    a, b = set(steps[4].event_id), set(steps2[4].event_id)
    print("  gained:", sorted(b - a), "\n  lost:  ", sorted(a - b))
    # Events whose baseline window contains a real (calendar-missing) COST announcement that the
    # as-built zones do not block: show the COST events and their clean counts both ways.
    for e in sorted(x for x in s3.event_id if x.startswith(("COST", "ORCL"))):
        print(f"  {e:18s} as built {base[e]}  corrected {base2[e]}")


if __name__ == "__main__":
    main()
