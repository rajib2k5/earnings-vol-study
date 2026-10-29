"""p04: timing statuses, the build invariant, and the look-up order (claims 3a-3c).

  uv run python docs/validation/probes/m1/p04_timing_and_invariant.py

Runs events.run.build() IN MEMORY from the local cache (no file is written), once
with the committed press_release_checks.csv and once with an empty one.
The status table and the invariant are re-derived here from ADR 0002 §3's text.
"""
import csv
import io
from collections import Counter
from datetime import date

import pandas as pd

from earnings_vol import config, params as params_mod
from earnings_vol.events import run as ev_run
from earnings_vol.ingest import prices

VOCAB = {"confirmed", "corrected", "inferred", "date_corrected", "no_document", "ambiguous", "not_checked"}
LOOKUP_FROM = date(2024, 9, 11)


def adr_status(row, timing_raw, is_session):
    """ADR 0002 §3 status table, written from the ADR text."""
    if row is None:
        return "not_checked"
    if row["found"] != "true":
        return "ambiguous" if (timing_raw is None and is_session) else "no_document"
    if row["release_date"] != row["announce_date"]:
        return "date_corrected"
    if not is_session:
        return "confirmed"           # non-session D: only the date is checked
    if timing_raw is None:
        return "inferred"
    return "confirmed" if row["label"] == timing_raw else "corrected"


def main():
    p = params_mod.load()
    inp = ev_run.load_inputs(p)
    raw = config.raw_dir()
    out = ev_run.build(p, inp, lambda s: prices.load(s, raw))
    ev, sessions = out["events"], out["sessions"]

    print("timing_status:", dict(sorted(Counter(ev.timing_status).items())))
    print("outside vocabulary:", sorted(set(ev.timing_status) - VOCAB))
    print("exclusion_reason:", dict(Counter(ev.exclusion_reason.fillna("(none)"))))

    rows = {f"{r['security_id']}:{r['announce_date']}": r for r in csv.DictReader(io.StringIO(inp["checks_text"]))}
    mism = []
    for r in ev.itertuples(index=False):
        exp = adr_status(rows.get(r.event_id), r.timing_raw, sessions.is_session(r.announce_date))
        if exp != r.timing_status:
            mism.append((r.event_id, exp, r.timing_status))
    print("status mismatches vs ADR table:", mism)
    committed = pd.read_parquet(ev_run.DERIVED / "events.parquet")
    same = committed.set_index("event_id")[["timing_status", "day0_session", "sample", "exclusion_reason"]]
    mine = ev.set_index("event_id")[["timing_status", "day0_session", "sample", "exclusion_reason"]]
    print("in-memory build == committed events.parquet on 4 key columns:",
          bool((same.astype(str) == mine.loc[same.index].astype(str)).all().all()))

    # --- the invariant -------------------------------------------------------------
    viol = out["lookup_violations"]
    print("code violations (with the 20 look-ups):", len(viol),
          dict(Counter(x for v in viol for x in v["reasons"])))
    tc = out["timing_check"].set_index("event_id")
    trig = {e: (tc.loc[e, "gap_verdict_yf"] == "contradicts") or (tc.loc[e, "outside_flag_yf"] is True)
            for e in tc.index}
    # ADR 0002 §3 build invariant, one sentence: `not_checked` is allowed only for an event with
    # announce_date before 2024-09-11, a non-NULL label and no gap trigger; plus the 10 labelled
    # sessions before 2024-09-11 are looked up too.
    edge = sessions.shift(sessions.first_on_or_after(LOOKUP_FROM), -10)
    adr_bad = set()
    for r in ev.itertuples(index=False):
        if r.timing_status != "not_checked":
            continue
        allowed = r.announce_date < edge and r.timing_raw is not None and not trig[r.event_id]
        if not allowed:
            adr_bad.add(r.event_id)
    code_bad = {v["event_id"] for v in viol}
    extra = sorted(adr_bad - code_bad)
    print("ADR-literal violations:", len(adr_bad), "; code reports:", len(code_bad))
    print("forbidden by the ADR sentence but NOT reported by the code:", len(extra))
    ex = ev[ev.event_id.isin(extra)][["event_id", "announce_date", "timing_raw", "sample"]]
    print(ex.assign(why=[("after daily end" if a > date(2026, 10, 26) else "") +
                         (" NULL label" if t is None else "") + (" gap trigger" if trig[e] else "")
                         for e, a, t in zip(ex.event_id, ex.announce_date, ex.timing_raw)])
          .groupby(["sample", "why"]).size().to_string())
    print("reported by the code but allowed by the ADR sentence:", sorted(code_bad - adr_bad))

    # --- with no look-ups at all: the 473 ---------------------------------------------
    header = inp["checks_text"].splitlines()[0] + "\n"
    out0 = ev_run.build(p, {**inp, "checks_text": header}, lambda s: prices.load(s, raw))
    v0 = out0["lookup_violations"]
    print("violations with no look-ups:", len(v0), dict(Counter(x for v in v0 for x in v["reasons"])))
    print("gap verdict on calendar labels:", dict(Counter(out0["timing_check"].gap_verdict_yf.fillna("(none)"))))
    print("gap verdict on labels in use:", dict(Counter(out["timing_check"].gap_verdict_yf.fillna("(none)"))))

    # --- look-up order --------------------------------------------------------------
    order = ev[(ev.announce_date >= edge)].sort_values(["announce_date", "security_id"], kind="mergesort")
    first = order.event_id.tolist()
    done = set(rows)
    print("first 21 in look-up order:", [(i + 1, e, e in done) for i, e in enumerate(first[:21])])
    print("NFLX 2024-10-17 position:", first.index("NFLX:2024-10-17") + 1,
          "; GOOGL 2024-10-29 position:", first.index("GOOGL:2024-10-29") + 1)
    print("CSV rows not in the first 19:", sorted(done - set(first[:19])))


if __name__ == "__main__":
    main()
