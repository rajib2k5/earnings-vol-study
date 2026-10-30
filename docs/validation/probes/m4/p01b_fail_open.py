"""p01b (claim 1): does the results run refuse to write H5-H7 rows without their G1 verdict?

(a) main() pointed at an empty scratch stage dir (no g1_report.json): must refuse.
(b) result_rows() with the real stage report minus every H5-H7 key (gate, primary, rates): the M3-style report.
    Pass: an exception. Fail: rows come out, and we print the roles H5-H7 get and the Holm family.
Run: uv run --frozen --no-sync python docs/validation/probes/m4/p01b_fail_open.py <scratch_dir>
Writes nothing outside <scratch_dir>.
"""
import copy
import json
import sys
from pathlib import Path

from earnings_vol import params as params_mod
from earnings_vol.events.run import stage_dir
from earnings_vol.stats import run

scratch = Path(sys.argv[1])
scratch.mkdir(parents=True, exist_ok=True)
p = params_mod.load()
real_stage = stage_dir(p)

# (a)
run.stage_dir = lambda _p: scratch
run.DERIVED = scratch  # belt and braces: nothing may reach data/derived
try:
    run.main([])
    print("(a) main() with no g1_report.json: WROTE (no refusal)")
except SystemExit as e:
    print("(a) main() with no g1_report.json: refused:", str(e)[:60])
run.stage_dir = stage_dir

# (b)
rep = json.loads((real_stage / "g1_report.json").read_text())
old = copy.deepcopy(rep)
for k in ("gate", "primary"):
    for h in ("H5", "H6", "H7"):
        old[k].pop(h, None)
for name in list(old["rates"]):
    for h in ("H5", "H6", "H7"):
        old["rates"][name].pop(h, None)
    if not old["rates"][name]:
        del old["rates"][name]
if old.get("remeasured"):
    for h in ("H5", "H6", "H7"):
        old["remeasured"]["rates"].pop(h, None)
f = run.load(p)
common = {"params_hash": p.params_hash, "code_commit": "probe"}
try:
    rows, summary = run.result_rows(f, p["stats"], old, common, p["drivers"])
except Exception as e:  # noqa: BLE001
    print("(b) result_rows without the H5-H7 gate: refused:", type(e).__name__, str(e)[:80])
    sys.exit(0)
print("(b) result_rows without the H5-H7 gate: produced", len(rows), "rows (no refusal)")
print("    holm family:", summary["holm_family"])
for r in rows:
    if r["family"] == "regression" and r["hypothesis"] in ("H5", "H6", "H7") and r["adjustment"] != "mean":
        print(f"    {r['hypothesis']} {r['statistic']:18s} role={r['role']:11s} p_holm={r['p_holm']} "
              f"p_value={'null' if r['p_value'] is None else 'set'}")
print("    H1-H4 p_holm:", {h: summary["holm"][h] for h in ("H1", "H2", "H3", "H4")})
