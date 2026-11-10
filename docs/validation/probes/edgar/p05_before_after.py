# p05 — Headline numbers before and after SEC EDGAR timing (phase 2, 2026-11-09).
#
# Compares a saved copy of the committed outputs from before timing.edgar was
# switched on (OLD: a folder holding data/derived/ and app/public/data/ as they
# were) with the repository's current ones (NEW). Prints, for H1-H7, the
# primary row's estimate, SE, p, Holm p and verdict (rejected at Holm 5%); the
# G1 calibrated rejection rates and gate flags; sample counts and exclusions;
# the timing statuses; the VX* bar iv; and every results row that changed.
# Reads committed files only (no price value is printed beyond what they hold).
#
# Run: .venv/bin/python docs/validation/probes/edgar/p05_before_after.py <OLD>

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

NEW = Path(__file__).resolve().parents[4]
OLD = Path(sys.argv[1])
HS = ["H1", "H2", "H3", "H4", "H5", "H6", "H7"]


def load(root: Path) -> dict:
    def js(kind):
        return json.loads((root / "app/public/data" / f"{kind}.json").read_text())["data"]
    return {"results": pd.read_parquet(root / "data/derived/results.parquet"),
            "events": pd.read_parquet(root / "data/derived/events.parquet"),
            "funnel": js("sample_funnel"), "tests": js("tests"), "meta": js("meta"),
            "vx": json.loads((root / "data/derived/vx_crosscheck.json").read_text())}


def primary(r, h):
    x = r[(r.hypothesis == h) & (r.role == "primary") & r.family.isin(["event_test", "regression"])]
    assert len(x) == 1, (h, len(x))
    return x.iloc[0]


def g1_rate(r, h):
    x = r[(r.measure == "g1:calibrated") & (r.hypothesis == h) & (r.role == "primary")]
    assert len(x) == 1, (h, len(x))
    return float(x.iloc[0].estimate)


o, n = load(OLD), load(NEW)
print(f"OLD params_hash {o['meta']['provenance']['params_hash'][:16]}; NEW {n['meta']['provenance']['params_hash'][:16]}")

print("\n1. H1-H7, primary rows (verdict: rejected when Holm p < 0.05)")
print(f"{'':4}{'statistic':18}{'estimate old -> new':34}{'SE old -> new':30}{'p old -> new':30}"
      f"{'Holm p old -> new':30}verdict old -> new")
for h in HS:
    a, b = primary(o["results"], h), primary(n["results"], h)
    def pair(c, fmt):
        x, y = a[c], b[c]
        fx = "nan" if pd.isna(x) else format(x, fmt)
        fy = "nan" if pd.isna(y) else format(y, fmt)
        same = (pd.isna(x) and pd.isna(y)) or (not pd.isna(x) and not pd.isna(y) and x == y)
        return f"{fx} -> {fy}{'' if same else ' *'}"
    va = "rejected" if a.p_holm < 0.05 else "not rejected"
    vb = "rejected" if b.p_holm < 0.05 else "not rejected"
    print(f"{h:4}{a.statistic:18}{pair('estimate', '.6g'):34}{pair('se', '.6g'):30}{pair('p_value', '.4g'):30}"
          f"{pair('p_holm', '.4g'):30}{va} -> {vb}")

print("\n2. Gate G1: calibrated rejection rate of the primary statistic at 5% (band "
      f"{n['tests']['g1']['band']}), and whether the hypothesis passes the gate")
for h in HS:
    ra, rb = g1_rate(o["results"], h), g1_rate(n["results"], h)
    pa = {x["hypothesis"]: x["pass"] for x in o["tests"]["g1"]["calibrated"]}[h]
    pb = {x["hypothesis"]: x["pass"] for x in n["tests"]["g1"]["calibrated"]}[h]
    print(f"   {h}: {ra:.4f} -> {rb:.4f}   pass {pa} -> {pb}")
print(f"   reps {o['tests']['g1']['reps']} -> {n['tests']['g1']['reps']}")

print("\n3. Sample")
for s_o, s_n in zip(o["funnel"]["by_sample"], n["funnel"]["by_sample"]):
    print(f"   events in {s_o['sample']}: {s_o['n_events']} -> {s_n['n_events']}")
for st_o, st_n in zip(o["funnel"]["steps"], n["funnel"]["steps"]):
    print(f"   funnel {st_o['step']}: {st_o['n_events']} -> {st_n['n_events']}")
print(f"   primary sample (meta): {o['meta']['sample']['n_events']} -> {n['meta']['sample']['n_events']}")
ex_o = o["events"]["exclusion_reason"].fillna("(none)").value_counts().to_dict()
ex_n = n["events"]["exclusion_reason"].fillna("(none)").value_counts().to_dict()
print(f"   exclusion reasons: {ex_o} -> {ex_n}")
d0o = o["events"].set_index("event_id")["day0_session"]
d0n = n["events"].set_index("event_id")["day0_session"]
moved = int((d0o.notna() & d0n.notna() & (d0o != d0n)).sum())
gained = d0n.index[d0o.isna() & d0n.notna()].tolist()
lost = int((d0o.notna() & d0n.isna()).sum())
print(f"   day 0: moved {moved}, newly defined {len(gained)} {gained}, lost {lost}")

print("\n4. Timing")
print(f"   statuses: {o['funnel']['timing_status_counts']} -> {n['funnel']['timing_status_counts']}")
print(f"   timing_source: {o['events']['timing_source'].value_counts(dropna=False).to_dict()} -> "
      f"{n['events']['timing_source'].value_counts(dropna=False).to_dict()}")
print(f"   lookups: {o['funnel']['lookups']} -> {n['funnel']['lookups']}")

print("\n5. VX* bar iv")
for k in ("n", "ratio", "verdict"):
    print(f"   {k}: {o['vx']['bar_iv'][k]} -> {n['vx']['bar_iv'][k]}")
print(f"   interval: {o['vx']['bar_iv']['events_bootstrap']} -> {n['vx']['bar_iv']['events_bootstrap']}")
print(f"   timing statuses of its events: {o['vx']['bar_iv']['events']['timing_status_counts']} -> "
      f"{n['vx']['bar_iv']['events']['timing_status_counts']}")
for sec in ("bar_i", "bar_ii", "bar_iii", "alignment_falsifier", "secondary"):
    print(f"   {sec}: {'identical' if o['vx'][sec] == n['vx'][sec] else 'CHANGED'}")

print("\n6. results.parquet rows whose estimate, SE, p, Holm p, q or n changed (keyed by result_id)")
ro, rn = o["results"].set_index("result_id"), n["results"].set_index("result_id")
assert ro.index.equals(rn.index) or set(ro.index) == set(rn.index)
rn = rn.loc[ro.index]
changed = pd.Series(False, index=ro.index)
for c in ("estimate", "se", "p_value", "p_holm", "q_bh", "n"):
    a, b = ro[c], rn[c]
    both = a.notna() & b.notna()
    changed |= (a.isna() != b.isna()) | (both & ~np.isclose(a.fillna(0).astype(float), b.fillna(0).astype(float),
                                                            rtol=1e-12, atol=0))
print(f"   {int(changed.sum())} of {len(ro)} rows; by family/role: "
      f"{ro[changed].groupby(['family', 'role']).size().to_dict()}")
for rid in ro.index[changed]:
    a, b = ro.loc[rid], rn.loc[rid]
    print(f"   {a.family:11}{a.role:12}{a['sample']:7}{str(a.model_id):22}{str(a.term):14}{a.statistic:17}"
          f"est {a.estimate:.6g} -> {b.estimate:.6g}; p {a.p_value:.4g} -> {b.p_value:.4g}")
