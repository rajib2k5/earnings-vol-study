# pd04 (claims 2a, 2c, 3, 4a): rebuild the events layer in memory from the
# local cache with the current params, write the committable tables to a
# scratch folder, byte-compare them with data/derived/, and recount.
# Also: the build-invariant violations with and without the can_enter_sample
# scope, and the orphan list checked against the eps_estimate oracle.
#
# Run: uv run --frozen python docs/validation/probes/m1-delta/pd04_rebuild_and_counts.py <scratch_dir>
import hashlib
import sys
from datetime import date
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "src"))
from earnings_vol import config, params as params_mod, schema, store  # noqa: E402
from earnings_vol.events import run, timing  # noqa: E402
from earnings_vol.ingest import prices  # noqa: E402

scratch = Path(sys.argv[1])
p = params_mod.load()
inp = run.load_inputs(p)
out = run.build(p, inp, lambda sym: prices.load(sym, config.raw_dir()))
for name in ("session", "security", "ticker_alias", "events", "eps"):
    store.write_derived(out[name], schema.REGISTRY[name], scratch)
    a = hashlib.sha256((scratch / f"{name}.parquet").read_bytes()).hexdigest()
    b = hashlib.sha256((REPO / "data/derived" / f"{name}.parquet").read_bytes()).hexdigest()
    print(f"{name:13s} rebuilt == committed (bytes): {a == b}")

eps = out["eps"]
vc = eps["match_status"].value_counts().to_dict()
n_orph, n_match = vc.get("orphan", 0), vc.get("matched", 0)
print("eps match_status:", dict(sorted(vc.items())), "rows", len(eps))
print(f"orphan rate = {n_orph} / ({n_orph} + {n_match}) = {n_orph / (n_orph + n_match):.4%}")
orph = eps[eps["match_status"] == "orphan"].sort_values(["security_id", "fiscal_period_end"])
print("orphans by security:", orph["security_id"].value_counts().sort_index().to_dict())
print("orphans by period end:", orph["fiscal_period_end"].astype(str).value_counts().sort_index().to_dict())

ev = out["events"]
print("events by sample:", ev["sample"].value_counts().sort_index().to_dict())

# 3: the invariant with and without the scope.
sessions = out["sessions"]
ranges = {k: p.date_range("samples", k) for k in ("daily", "mixed", "coarse")}
lf = date.fromisoformat(p["timing"]["lookup_from"])
nb = int(p["timing"]["lookup_sessions_before"])
tc = out["timing_check"]
trig = {e: timing.gap_triggered(r) for e, r in zip(tc["event_id"], tc.to_dict("records"))}
scoped, unscoped = [], []
for r in ev.itertuples(index=False):
    if r.timing_status != "not_checked":
        continue
    rs = timing.lookup_reasons(r.announce_date, r.timing_raw, trig.get(r.event_id, False), sessions, lf, nb, ranges)
    wide = {"all": (date(1900, 1, 1), date(2999, 12, 31))}
    ru = timing.lookup_reasons(r.announce_date, r.timing_raw, trig.get(r.event_id, False), sessions, lf, nb, wide)
    if rs:
        scoped.append(r.event_id)
    if ru:
        unscoped.append((r.event_id, r.sample, r.timing_raw, r.exclusion_reason))
print(f"\n3: violations scoped {len(scoped)} (lookup_violations in build: {len(out['lookup_violations'])}); "
      f"unscoped {len(unscoped)}")
dropped = [u for u in unscoped if u[0] not in set(scoped)]
print(f"dropped by the scope: {len(dropped)}; their samples: "
      f"{pd.Series([u[1] for u in dropped]).value_counts().to_dict()}")
for u in dropped:
    print("   ", u)
print("sampled not_checked events dropped by the scope:", [u for u in dropped if u[1] != "none"])

# 4a: every session in 2020-04-01 .. 2026-10-26 in exactly one range.
lo, hi = ranges["coarse"][0], ranges["daily"][1]
counts = {}
for dd in sessions.dates:
    if lo <= dd <= hi:
        k = sum(1 for a, b in ranges.values() if a <= dd <= b)
        counts[k] = counts.get(k, 0) + 1
print("\n4a: sessions in the span by number of ranges containing them:", counts)
print("ranges:", {k: (str(a), str(b)) for k, (a, b) in ranges.items()})
o = ev[ev["event_id"] == "ORCL:2024-09-09"][["event_id", "day0_session", "sample", "exclusion_reason"]]
print(o.to_string(index=False))
