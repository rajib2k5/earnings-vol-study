"""p06b: which adjustment are the committed per-event values in event_paths.json? Counts only.

    uv run --frozen --offline --no-sync python docs/validation/probes/m5/p06b_per_event_adjustment.py

Compares each event's value at day -1 in event_paths.json per_event with (a) the stage's VIX-adjusted RUNUP
(runup_cboe) and (b) the mean-adjusted level ln(cm30 at day -1) - baseline_mean_ln_iv from the committed
event_measures. Prints how many of the 347 agree with each to 1e-3. Nothing per event is printed.
"""
import json
import math

import pandas as pd

ST = "/home/rajib2k5/data/vol-projects/earnings-vol-study/cache/stage/74bed6f4b1281810/"
ep = json.load(open("app/public/data/event_paths.json"))["data"]
i = ep["rel_days"].index(-1)
v = {e["event_id"]: e["values"][i] for e in ep["per_event"]}
st = pd.read_parquet(ST + "event_measures.parquet").set_index("event_id")
cm = pd.read_parquet("data/derived/event_measures.parquet").set_index("event_id")
n = a = b = 0
for eid, x in v.items():
    if x is None:
        continue
    n += 1
    r = st.at[eid, "runup_cboe"]
    a += (r == r) and abs(x - r) < 1e-3
    m = math.log(cm.at[eid, "cm30_m1"]) - cm.at[eid, "baseline_mean_ln_iv"] if cm.at[eid, "cm30_m1"] == cm.at[eid, "cm30_m1"] else float("nan")
    b += (m == m) and abs(x - m) < 1e-3
print(f"per-event day -1 values: {n}; equal to the VIX-adjusted run-up: {a}; equal to the mean-adjusted level: {b}")
