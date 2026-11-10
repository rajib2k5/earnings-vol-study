# p02 — EDGAR phase 1: what source 1 of ADR 0002 §3 gives the events that need a look-up.
#
# Builds the events layer twice IN MEMORY: as committed (press releases, then the
# calendar label) and with params timing.edgar = true (a copy of params.yaml in
# cache/edgar-phase1/). Writes only to $VOL_DATA_DIR/earnings-vol-study/cache/edgar-phase1/
# (events_edgar.parquet, outcomes.csv, report.json); never data/derived, the
# stage cache or the app. Reads EDGAR from raw/edgar/ only: no request.
# Prints counts, dates, labels and EDGAR times only (no price value).
#
# Run: .venv/bin/python docs/validation/probes/edgar/p02_phase1_outcomes.py

import collections
import json
from datetime import timedelta

import pandas as pd
import yaml

from earnings_vol import config, params as params_mod
from earnings_vol.events import calendar, run
from earnings_vol.ingest import edgar, prices

OUT = config.cache_dir() / "edgar-phase1"
OUT.mkdir(parents=True, exist_ok=True)
raw_params = yaml.safe_load(params_mod.DEFAULT_PATH.read_text(encoding="utf-8"))
raw_params["timing"]["edgar"] = True
(OUT / "params.yaml").write_text(yaml.safe_dump(raw_params, sort_keys=False), encoding="utf-8")
p0 = params_mod.load()
p1 = params_mod.load(OUT / "params.yaml")
inp = run.load_inputs(p0)
loader = lambda s: prices.load(s, config.raw_dir())   # noqa: E731
eload = run.edgar_loader(inp["selection"], config.raw_dir())
out0 = run.build(p0, inp, loader)
out1 = run.build(p1, inp, loader, edgar_loader=eload)
S = out1["sessions"]
e0 = out0["events"].set_index("event_id")
e1 = out1["events"].set_index("event_id")
scope = [v["event_id"] for v in out0["lookup_violations"]]
reasons = {v["event_id"]: v["reasons"] for v in out0["lookup_violations"]}
print(f"events {len(e1)}; need a look-up under the default rule: {len(scope)}; press-release rows: 20")

# The readings again, for the table (the build keeps only the outcome).
filings = {}
rows = []
for eid in scope:
    sid = e0.loc[eid, "security_id"]
    filings.setdefault(sid, eload(sid))
    x = edgar.read_acceptance(e0.loc[eid, "announce_date"], filings[sid], S,
                              dict(zip(out1["session"]["session_date"], out1["session"]["close_time_et"])))
    loc = edgar.parse_acceptance(x["accepted_utc"]).astimezone(edgar.NY) if x else None
    rows.append({"event_id": eid, "sample": e0.loc[eid, "sample"], "reasons": "+".join(reasons[eid]),
                 "announce_date": e0.loc[eid, "announce_date"], "calendar_label": e0.loc[eid, "timing_raw"],
                 "edgar_accession": x["accession"] if x else None,
                 "edgar_accepted_ny": loc.strftime("%Y-%m-%d %H:%M") if loc else None,
                 "edgar_reading": x["label"] if x else None, "n_8k_in_window": x["n_in_window"] if x else 0,
                 "outcome": out1["edgar_outcome"][eid], "timing_status": e1.loc[eid, "timing_status"],
                 "timing_used": e1.loc[eid, "timing_used"],
                 "day0_before": e0.loc[eid, "day0_session"], "day0_after": e1.loc[eid, "day0_session"]})
T = pd.DataFrame(rows)
T.to_csv(OUT / "outcomes.csv", index=False)

print("\n1. outcome of the", len(T), "look-ups")
print(T["outcome"].value_counts().sort_index().to_string())
print("\n   by sample")
print(pd.crosstab(T["outcome"], T["sample"], margins=True).to_string())
print("\n   by look-up reason")
print(pd.crosstab(T["outcome"], T["reasons"], margins=True).to_string())
res = T[T["outcome"].isin(["confirmed", "inferred"])]
print("\n2. resolved:", len(res), "by label used:",
      res["timing_used"].fillna("(non-session D: label not needed)").value_counts().sort_index().to_dict(),
      "by status:", res["timing_status"].value_counts().to_dict())

print("\n3. day 0 against the current (calendar-label) build, all 1353 events")
moved = [(e, e0.loc[e, "day0_session"], e1.loc[e, "day0_session"]) for e in e1.index
         if e0.loc[e, "day0_session"] != e1.loc[e, "day0_session"]]
kinds = collections.Counter("newly defined (NULL label inferred)" if a is None else "moved" if b is not None
                            else "lost" for _, a, b in moved)
print("   events whose day 0 differs:", len(moved), dict(kinds))
for e, a, b in moved:
    print(f"     {e}: {a} -> {b} ({e1.loc[e, 'timing_status']}, {e1.loc[e, 'timing_used']})")
print("   exclusion reasons before:", e0["exclusion_reason"].fillna("(none)").value_counts().to_dict())
print("   exclusion reasons after: ", e1["exclusion_reason"].fillna("(none)").value_counts().to_dict())
print("   sample before:", e0["sample"].value_counts().to_dict(), " after:", e1["sample"].value_counts().to_dict())

print("\n4. unresolved events: what the 8-K would give if it were taken (not applied)")
un = T[~T["outcome"].isin(["confirmed", "inferred"])]
for r in un.sort_values(["outcome", "event_id"]).itertuples(index=False):
    alt = None
    if isinstance(r.edgar_reading, str) and r.edgar_reading in ("BMO", "AMC", "outside_hours"):
        d = pd.Timestamp(r.edgar_accepted_ny).date()
        alt = calendar.day0(d, r.edgar_reading if S.is_session(d) else None, S)[0]
    acc = r.edgar_accepted_ny if isinstance(r.edgar_accepted_ny, str) else "-"
    rd = r.edgar_reading if isinstance(r.edgar_reading, str) else "-"
    print(f"   {r.outcome:15s} {r.event_id:18s} {r.sample:7s} cal {str(r.calendar_label):5s} "
          f"8-K {acc:17s} {rd:15s} day0 now {r.day0_before}  8-K day0 {alt}")

print("\n4b. no_8k events: the nearest Item 2.02 8-K within 14 days of D (for the hand check; not applied)")
for r in un[un["outcome"] == "no_8k"].sort_values("event_id").itertuples(index=False):
    sid = r.event_id.split(":")[0]
    near = [f["accepted"].astimezone(edgar.NY) for f in filings[sid]
            if abs((f["accepted"].astimezone(edgar.NY).date() - r.announce_date).days) <= 14]
    print(f"   {r.event_id:18s} {', '.join(f'{x:%Y-%m-%d %a %H:%M}' for x in near) or 'none within 14 days'}")

print("\n5. the 20 press-release look-ups against EDGAR")
chk = run.timing.parse_checks(inp["checks_text"], S, dict(zip(out1["session"]["session_date"],
                                                                 out1["session"]["close_time_et"])))
agree = collections.Counter()
for r in chk.itertuples(index=False):
    eid = f"{r.security_id}:{r.announce_date.isoformat()}"
    x = edgar.read_acceptance(r.announce_date, filings.setdefault(r.security_id, eload(r.security_id)), S,
                              dict(zip(out1["session"]["session_date"], out1["session"]["close_time_et"])))
    loc = edgar.parse_acceptance(x["accepted_utc"]).astimezone(edgar.NY)
    # The time itself, read even where the holiday rule refuses it:
    raw_label = edgar._label(loc, S, dict(zip(out1["session"]["session_date"], out1["session"]["close_time_et"])))
    same = loc.date() == r.release_date and raw_label == r.label
    kind = ("agrees" if same else "DISAGREES") + (" (holiday window: not read as timing)" if x["label"] == "edgar_holiday" else "")
    agree[kind] += 1
    print(f"   {eid:18s} PR {r.release_date} {r.release_time_et if isinstance(r.release_time_et, str) else '--:--'} {r.label}  8-K {loc:%Y-%m-%d %H:%M} "
          f"{raw_label:15s} {kind}; status kept {e1.loc[eid, 'timing_status']} ({e1.loc[eid, 'timing_source']}), "
          f"accession recorded {e1.loc[eid, 'edgar_accession'] is not None}")
print("  ", dict(agree))

print("\n6. coverage (milestone-1 EDGAR check): an Item 2.02 8-K on D-1..D+1")
for smp in ("daily", "mixed", "coarse"):
    ids = [e for e in e1.index if e1.loc[e, "sample"] == smp and e1.loc[e, "exclusion_reason"] != "duplicate_row"]
    n = sum(1 for e in ids if edgar.read_acceptance(
        e1.loc[e, "announce_date"], filings.setdefault(e1.loc[e, "security_id"], eload(e1.loc[e, "security_id"])),
        S, dict(zip(out1["session"]["session_date"], out1["session"]["close_time_et"]))) is not None)
    print(f"   {smp}: {n} of {len(ids)} ({n / len(ids):.1%})")

print("\n7. after EDGAR: the build invariant and job 1")
v1 = out1["lookup_violations"]
print("   not_checked events still needing a look-up:", len(v1),
      pd.Series([v["sample"] for v in v1]).value_counts().to_dict(),
      pd.Series([x for v in v1 for x in v["reasons"]]).value_counts().to_dict())
pg = out1["edgar_pending_gap_checks"]
tc1 = out1["timing_check"].set_index("event_id")
print("   EDGAR labels the gap contradicts or the outside flag questions (job 1, press-release check):", len(pg),
      "by sample", e1.loc[pg, "sample"].value_counts().to_dict(),
      "contradicts", int((tc1.loc[pg, "gap_verdict_yf"] == "contradicts").sum()),
      "outside flag", int((tc1.loc[pg, "outside_flag_yf"] == True).sum()),   # noqa: E712
      "of them in the 453:", len(set(pg) & set(scope)))
both = int(((tc1.loc[pg, "gap_verdict_yf"] == "contradicts") & (tc1.loc[pg, "outside_flag_yf"] == True)).sum())  # noqa: E712
print("   of the", len(pg), "both contradicted and flagged:", both)
for e in pg:
    print(f"     {e:18s} {e1.loc[e, 'sample']:7s} {e1.loc[e, 'timing_used']} verdict {tc1.loc[e, 'gap_verdict_yf']} "
          f"outside flag {tc1.loc[e, 'outside_flag_yf']} reasons {'+'.join(reasons.get(e, []))}")
print("   lookups_complete could be set true without the build stopping:", len(v1) == 0)
print("   eps table identical in both builds:", out0["eps"].equals(out1["eps"]))

rep = run.report(out1, p1)
(OUT / "report.json").write_text(json.dumps(rep, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
out1["events"].to_parquet(OUT / "events_edgar.parquet")
print("\nwritten:", sorted(x.name for x in OUT.iterdir()))
