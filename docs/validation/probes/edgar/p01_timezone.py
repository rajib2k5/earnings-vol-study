# p01 — Is acceptanceDateTime a UTC instant ("Z") or New York wall time?
#
# Reads every fetched filing twice: as a UTC instant converted to New York
# time, and as New York wall time. Compares each reading with (A) the 20
# press-release look-ups, (B) the calendar labels, (C) the price-gap
# diagnostic of the committed stage (z values; counts only), (D) EDGAR's own
# filing date, which moves to the next business day for an 8-K accepted after
# 17:30 New York time, (E) EDGAR's hours (06:00-22:00 New York time), and
# (F) daylight saving: a company's release keeps its New York clock time.
# Also lists (G) the NYSE sessions on which no filing was accepted.
# Reads raw/edgar/ only (no request). Prints counts, dates and EDGAR times only.
#
# Run: .venv/bin/python docs/validation/probes/edgar/p01_timezone.py

import collections
from datetime import date, datetime, time as dtime, timezone

import numpy as np
import pandas as pd

from earnings_vol import config, params as params_mod
from earnings_vol.events import calendar, run, timing
from earnings_vol.ingest import edgar

NY = edgar.NY
p = params_mod.load()
st = calendar.build_session_table(p.day("sessions", "start"), p.day("sessions", "end"), p["snapshot_eras"])
S = calendar.Sessions(st["session_date"].tolist())
close = dict(zip(st["session_date"], st["close_time_et"]))
sel = pd.read_parquet(config.cache_dir() / "universe.parquet")
sel = sel[sel["in_universe"]].sort_values("security_id")
pred = edgar.parse_predecessors(edgar.PREDECESSORS_PATH.read_text(encoding="utf-8"))
M = {}
for sid, cik in zip(sel["security_id"], sel["cik"]):
    blocks = [edgar.merge_filings(*edgar.read_cached(c, config.raw_dir(), edgar.SINCE)) for c in [cik, *pred.get(sid, [])]]
    M[sid] = {k: sum((b[k] for b in blocks), []) for k in edgar.FILING_KEYS}


def parse(s, how):
    naive = datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%fZ")
    return naive.replace(tzinfo=timezone.utc) if how == "utc" else naive.replace(tzinfo=NY)


def f202(m, how):
    return sorted(({"accession": a, "accepted_utc": t, "accepted": parse(t, how)}
                   for f, i, a, t in zip(m["form"], m["items"], m["accessionNumber"], m["acceptanceDateTime"])
                   if f == "8-K" and "2.02" in (i or "").split(",")), key=lambda x: x["accepted"])


F = {how: {sid: f202(M[sid], how) for sid in M} for how in ("utc", "ny")}
n_all = sum(len(m["accessionNumber"]) for m in M.values())
print(f"filings read: {n_all} (51 CIKs); Item 2.02 8-Ks: {sum(len(v) for v in F['utc'].values())}")
inp = run.load_inputs(p)
chk = timing.parse_checks(inp["checks_text"], S, close)
STAGE = config.cache_dir() / "stage" / p.params_hash[:16]
ev = pd.read_parquet(STAGE / "events.parquet")
tc = pd.read_parquet(STAGE / "timing_check.parquet").set_index("event_id")


def hold(how, sid, d):
    """The reading with the holiday rule set aside: the time itself."""
    x = edgar.read_acceptance(d, F[how][sid], S, close)
    if x is None:
        return None, None
    loc = next(f for f in F[how][sid] if f["accession"] == x["accession"])["accepted"].astimezone(NY)
    return loc, edgar._label(loc, S, close)


print("\nA. the 20 press-release look-ups (ground truth): does the 8-K give the release's date and label?")
A = {h: collections.Counter() for h in ("utc", "ny")}
for r in chk.itertuples(index=False):
    cells = []
    for how in ("utc", "ny"):
        loc, lab = hold(how, r.security_id, r.announce_date)
        ok = loc is not None and loc.date() == r.release_date and lab == r.label
        A[how]["agree" if ok else lab or "no 8-K"] += 1
        cells.append(f"{how} {loc:%m-%d %H:%M} {lab:14s}")
    print(f"   {r.security_id:5s} {r.announce_date}  PR {r.release_date:%m-%d} {r.release_time_et if isinstance(r.release_time_et, str) else '--:--'} {r.label}  "
          + "  ".join(cells))
for how in A:
    print(f"   {how}: {dict(A[how])}")

print("\nB. calendar labels: labelled events on a session D (all 1,353 events of the committed stage)")
for how in ("utc", "ny"):
    c = collections.Counter()
    for r in ev.itertuples(index=False):
        if r.timing_raw not in ("BMO", "AMC") or not S.is_session(r.announce_date):
            continue
        x = edgar.read_acceptance(r.announce_date, F[how][r.security_id], S, close)
        c["no 8-K" if x is None else "edgar_holiday" if x["label"] == "edgar_holiday" else
          "other date" if x["ny_date"] != r.announce_date else x["label"] if x["label"] not in ("BMO", "AMC") else
          "agree" if x["label"] == r.timing_raw else "contradict"] += 1
    print(f"   {how}: n {sum(c.values())} {dict(sorted(c.items()))}")

print("\nC. the gap diagnostic on the 8-K's own label (session D, 8-K on D, z on both candidates)")
g = p["gap"]
for how in ("utc", "ny"):
    c = collections.Counter()
    for r in ev.itertuples(index=False):
        if not S.is_session(r.announce_date) or r.event_id not in tc.index:
            continue
        zb, za = tc.loc[r.event_id, "z_bmo_yf"], tc.loc[r.event_id, "z_amc_yf"]
        x = edgar.read_acceptance(r.announce_date, F[how][r.security_id], S, close)
        if not (np.isfinite(zb) and np.isfinite(za)) or x is None or x["ny_date"] != r.announce_date:
            continue
        if x["label"] not in ("BMO", "AMC"):
            c[x["label"]] += 1
            continue
        mine, other = (zb, za) if x["label"] == "BMO" else (za, zb)
        c["contradicts" if other >= g["z_min"] and other >= g["ratio"] * mine else
          "supports" if mine >= g["z_min"] and mine >= g["ratio"] * other else "quiet"] += 1
    print(f"   {how}: {dict(sorted(c.items()))}")

print("\nD. EDGAR's filing date against the acceptance time, 8-K and 8-K/A from 2020")
for how in ("utc", "ny"):
    c = collections.Counter()
    for m in M.values():
        for a, fd, form in zip(m["acceptanceDateTime"], m["filingDate"], m["form"]):
            loc = parse(a, how).astimezone(NY)
            if form not in ("8-K", "8-K/A") or loc.year < 2020:
                continue
            fdd = date.fromisoformat(fd)
            c[("from 17:30" if loc.time() >= dtime(17, 30) else "before 17:30",
               "same date" if fdd == loc.date() else "later date" if fdd > loc.date() else "EARLIER date")] += 1
    print(f"   {how}: {dict(sorted(c.items()))}")

print("\nE. acceptances outside EDGAR's 06:00-22:00 New York hours, all filings")
for how in ("utc", "ny"):
    out = sum(not dtime(6) <= parse(a, how).astimezone(NY).time() <= dtime(22)
              for m in M.values() for a in m["acceptanceDateTime"])
    print(f"   {how}: {out} of {n_all} ({out / n_all:.2%})")

print("\nF. daylight saving: each company's median Item 2.02 time (New York), EDT months minus EST months, 2020 on")
for how in ("utc", "ny"):
    d = {}
    for sid in M:
        mins = {True: [], False: []}
        for f in F[how][sid]:
            loc = f["accepted"].astimezone(NY)
            if loc.year >= 2020:
                mins[bool(loc.dst())].append(loc.hour * 60 + loc.minute)
        d[sid] = np.median(mins[True]) - np.median(mins[False])
    big = sorted(s for s, v in d.items() if abs(v) >= 45)
    print(f"   {how}: companies {len(d)}; median shift {np.median(list(d.values())):+.0f} min; "
          f"|shift| >= 45 min: {len(big)} {big if len(big) < 10 else ''}")

print("\nG. NYSE sessions 2020-01-02..2026-11-06 with no acceptance in any of the 51 CIKs (UTC reading)")
days = collections.Counter(parse(a, "utc").astimezone(NY).date() for m in M.values() for a in m["acceptanceDateTime"])
empty = [d for d in S.dates if date(2020, 1, 2) <= d <= date(2026, 11, 6) and days[d] == 0]
coded = set().union(*(edgar.edgar_holidays(y) for y in range(2020, 2027)))
print("   ", [f"{d} {d:%a}" for d in empty])
print("    all in edgar_holidays():", set(empty) <= coded, "; coded days that had acceptances:",
      sorted(str(d) for d in coded if days[d] > 0 and d <= date(2026, 11, 6)))
print("    weekend acceptances:", sum(v for d, v in days.items() if d.weekday() >= 5 and d.year >= 2020))
