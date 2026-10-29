# =============================================================================
# snapshots.py — Map option snapshots to NYSE sessions (ADR 0002 §1) and say,
# for every (security, session), whether a usable snapshot exists.
#
# THE RULES
#   - as_of_session(snapshot date) = that date if it is a session, else the
#     last session before it. A Saturday snapshot (2019) is Friday's close; a
#     holiday snapshot is a copy of the session before.
#   - Two snapshots on one session: keep the one dated ON the session and drop
#     the other. Its drop reason is `stale_copy`, counted, never a status.
#   - A kept weekday snapshot whose bids and asks equal the previous kept
#     snapshot's EXACTLY, row for row, is `stale_repeat`: the vendor did not
#     refresh it. No measure uses it.
#   - A session with no snapshot is `missing`. Nothing is ever imputed.
#
# The result is the table `session_snapshot`: the first four columns of the
# planned `iv_daily` (data model §3.6), built early because the baseline
# counts of milestone 1 need to know which sessions are observed.
# =============================================================================

from datetime import date

import numpy as np
import pandas as pd

from earnings_vol.events.calendar import Sessions


def quote_digests(chain: pd.DataFrame) -> pd.DataFrame:
    """One row per (act_symbol, date): rows and an order-free digest of the quotes.

    Each quote row (expiration, strike, call_put, bid, ask) is hashed to a
    64-bit number and the numbers are summed per snapshot. The same set of
    rows always gives the same sum, so two snapshots with equal digests and
    equal row counts hold the same quotes (a false match has odds near 2**-64).
    """
    keys = chain[["expiration", "strike", "call_put", "bid", "ask"]]
    h = pd.util.hash_pandas_object(keys, index=False).to_numpy(dtype=np.uint64)
    frame = pd.DataFrame({"act_symbol": chain["act_symbol"].to_numpy(), "date": chain["date"].to_numpy(),
                          "h": h})
    g = frame.groupby(["act_symbol", "date"], sort=True)["h"]
    # uint64 sums wrap around modulo 2**64, which is what a hash sum wants.
    out = g.agg(lambda s: int(np.sum(s.to_numpy(), dtype=np.uint64))).rename("digest").reset_index()
    out["rows"] = g.size().to_numpy()
    return out


def build_session_snapshot(digests: pd.DataFrame, resolve, security_ids: list[str], sessions: Sessions,
                           first: date, last: date) -> tuple[pd.DataFrame, dict]:
    """The session_snapshot table and counts of the decisions made.

    `digests` has act_symbol, date, digest, rows. `resolve(ticker, day)` maps a
    source ticker to a security_id (ticker_alias). Rows cover every session
    from `first` to `last` for every security, observed or not.
    """
    d = digests.copy()
    d["security_id"] = [resolve(t, x) for t, x in zip(d["act_symbol"], d["date"])]
    d = d[d["security_id"].isin(security_ids)]
    d["session_date"] = [sessions.as_of(x) for x in d["date"]]
    d = d[(d["session_date"] >= first) & (d["session_date"] <= last)]
    d["on_session"] = d["date"] == d["session_date"]
    # Keep one snapshot per (security, session): the one dated on the session,
    # else the earliest (closest to that session's close).
    d = d.sort_values(["security_id", "session_date", "on_session", "date"], ascending=[True, True, False, True],
                      kind="mergesort")
    dup = d.duplicated(["security_id", "session_date"], keep="first")
    counts = {"snapshots": int(len(d)), "stale_copy_dropped": int(dup.sum())}
    kept = d[~dup].sort_values(["security_id", "session_date"], kind="mergesort")
    prev_digest = kept.groupby("security_id")["digest"].shift(1)
    prev_rows = kept.groupby("security_id")["rows"].shift(1)
    weekday = kept["on_session"]
    stale = weekday & (kept["digest"] == prev_digest) & (kept["rows"] == prev_rows)
    kept = kept.assign(status=np.where(stale, "stale_repeat", "ok"))
    counts["stale_repeat"] = int(stale.sum())
    by_key = {(s, x): (sd, st) for s, x, sd, st in zip(kept["security_id"], kept["session_date"], kept["date"],
                                                       kept["status"])}
    rows = []
    span = [x for x in sessions.dates if first <= x <= last]
    for sid in sorted(security_ids):
        for x in span:
            sd, st = by_key.get((sid, x), (None, "missing"))
            rows.append({"security_id": sid, "session_date": x, "snapshot_date": sd, "snapshot_status": st})
    out = pd.DataFrame(rows, columns=["security_id", "session_date", "snapshot_date", "snapshot_status"])
    counts["missing"] = int((out["snapshot_status"] == "missing").sum())
    counts["ok"] = int((out["snapshot_status"] == "ok").sum())
    return out, counts
