"""p10b: why 285 events lack abs_move_cand_max, leg by leg in event_iv's order (claim 10, the "stated reasons").

Own implementation from the walkthrough's definition: legs (prev(D), D), (D, next(D)) for a session D,
else (prev(D), next(D)); a start is the ok session at its target or one before, an end at its target
or one after; the move needs an expiry with a forward on both ends and tau >= 5 at the end.
Reads stage chain_expiry, iv_daily, events, event_iv. Nothing from earnings_vol is imported.
Run from the repository root:  python docs/validation/probes/m2/p10b_move_reasons.py <stage dir>
"""
import sys
from bisect import bisect_left, bisect_right
from pathlib import Path

import pandas as pd

st = Path(sys.argv[1])
ce = pd.read_parquet(st / "chain_expiry.parquet", columns=["security_id", "session_date", "expiration", "forward", "tau_sessions"])
iv = pd.read_parquet(st / "iv_daily.parquet", columns=["security_id", "session_date", "snapshot_status"])
ev = pd.read_parquet(st / "events.parquet")
eiv = pd.read_parquet(st / "event_iv.parquet", columns=["event_id", "abs_move_cand_max"])
S = list(pd.read_parquet(st / "session.parquet")["session_date"])
IDX = {d: i for i, d in enumerate(S)}
ok = {(s, d) for s, d, x in zip(iv["security_id"], iv["session_date"], iv["snapshot_status"]) if x == "ok"}
fw = {}
for r in ce[ce["forward"].notna()].itertuples(index=False):
    fw.setdefault((r.security_id, r.session_date), {})[r.expiration] = r.tau_sessions
mm = ev.merge(eiv, on="event_id")
miss = mm[mm["abs_move_cand_max"].isna()]


def reason(sid, d):
    if d > S[-2]:
        return "beyond_session_table"
    legs = [(S[IDX[d] - 1], d), (d, S[IDX[d] + 1])] if d in IDX else [(S[bisect_left(S, d) - 1], S[bisect_right(S, d)])]
    for lo, hi in legs:
        a = next((x for x in (lo, S[IDX[lo] - 1]) if (sid, x) in ok), None)
        b = next((x for x in (hi, S[IDX[hi] + 1]) if (sid, x) in ok), None)
        if a is None or b is None:
            return "end_without_snapshot"
        fa, fb = fw.get((sid, a), {}), fw.get((sid, b), {})
        if not any(e in fb and fb[e] >= 5 for e in fa):
            return "no_common_forward"
    return "UNEXPLAINED"


miss = miss.assign(reason=[reason(s, d) for s, d in zip(miss["security_id"], miss["announce_date_used"])])
print(miss.groupby(["sample", "reason"]).size().to_string())
print("total", len(miss))
