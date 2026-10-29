"""p08: are the dropped non-session snapshots stale copies, and is no real session dropped? (claim 7)

  uv run python docs/validation/probes/m1/p08_stale_copy.py

Reads the local option_chain extracts (cache/dolt/options@<commit>/option_chain/*.parquet).
Compares quote SETS directly (sorted rows of expiration, strike, call_put, bid, ask), not the
64-bit hash sum the code uses, so a hash collision or a hashing bug cannot hide a difference.
"""
from collections import Counter
from datetime import date

import pandas as pd
import pyarrow.parquet as pq

from earnings_vol import config, params as params_mod
from earnings_vol.events import calendar, securities
from earnings_vol.events.run import DERIVED

COLS = ["date", "act_symbol", "expiration", "strike", "call_put", "bid", "ask"]


def main():
    p = params_mod.load()
    cdir = config.cache_dir() / "dolt" / f"options@{p['dolt']['options_commit']}" / "option_chain"
    files = sorted(cdir.glob("*.parquet"))
    sess_tbl = pd.read_parquet(DERIVED / "session.parquet")
    s = calendar.Sessions(sorted(sess_tbl.session_date))
    alias = pd.read_parquet(DERIVED / "ticker_alias.parquet")
    alias = alias.astype(object).where(alias.notna(), None)
    ids = set(pd.read_parquet(DERIVED / "security.parquet").query("in_universe").security_id)
    first, last = date(2020, 1, 2), date(2026, 10, 26)

    # pass 1: which (symbol, date) snapshots exist
    keys = []
    for f in files:
        t = pq.read_table(f, columns=["date", "act_symbol"]).to_pandas(date_as_object=True).drop_duplicates()
        keys.append(t)
    k = pd.concat(keys, ignore_index=True)
    k["sid"] = [securities.resolve_on(a, d, alias) for a, d in zip(k.act_symbol, k.date)]
    k = k[k.sid.isin(ids)]
    k["session"] = [s.as_of(d) for d in k.date]
    k = k[(k.session >= first) & (k.session <= last)]
    k["on"] = k.date == k.session
    print("snapshot company-dates read:", len(k), "; on a session:", int(k.on.sum()), "; off-session:", int((~k.on).sum()))
    on = set(zip(k[k.on].sid, k[k.on].session))
    off = k[~k.on]
    dropped = off[[ (a, b) in on for a, b in zip(off.sid, off.session)]]
    kept_off = off[[ (a, b) not in on for a, b in zip(off.sid, off.session)]]
    print("off-session snapshots whose session has its own snapshot (dropped):", len(dropped))
    print("off-session snapshots KEPT because their session has none:", len(kept_off),
          Counter(d.strftime("%a") for d in kept_off.date))
    print("weekday of dropped:", dict(Counter(d.strftime("%a") for d in dropped.date)))
    print("duplicate sessions with two OFF-session snapshots:", int(off.duplicated(["sid", "session"]).sum()))

    # pass 2: compare quote sets
    need = set(dropped.date) | set(dropped.session) | set(kept_off.date) | set(kept_off.session)
    need |= {s.prev_before(x) for x in kept_off.session}
    rows = []
    for f in files:
        t = pq.read_table(f, columns=COLS).to_pandas(date_as_object=True)
        rows.append(t[t.date.isin(need)])
    q = pd.concat(rows, ignore_index=True)
    q["sid"] = [securities.resolve_on(a, d, alias) for a, d in zip(q.act_symbol, q.date)]
    groups = {key: g[["expiration", "strike", "call_put", "bid", "ask"]].sort_values(
        ["expiration", "strike", "call_put"]).reset_index(drop=True) for key, g in q.groupby(["sid", "date"])}

    def same(a, b):
        ga, gb = groups.get(a), groups.get(b)
        return ga is not None and gb is not None and ga.equals(gb)

    eq = [same((r.sid, r.date), (r.sid, r.session)) for r in dropped.itertuples()]
    print("dropped snapshots identical to their session's own snapshot:", sum(eq), "of", len(eq))
    diff = dropped[[not e for e in eq]]
    if len(diff):
        print("NOT identical (first 15):")
        for r in diff.head(15).itertuples():
            ga, gb = groups.get((r.sid, r.date)), groups.get((r.sid, r.session))
            print(f"   {r.sid} {r.date} ({r.date:%a}) vs {r.session}: rows {len(ga)} vs {len(gb)}")
        print("   NOT identical by weekday:", dict(Counter(d.strftime("%a") for d in diff.date)),
              "by year:", dict(Counter(d.year for d in diff.date)))
    # Kept off-session snapshots: a copy of which session?
    for r in kept_off.itertuples():
        prev = s.prev_before(r.session)
        print(f"   kept off-session {r.sid} {r.date} ({r.date:%a}) as session {r.session}: "
              f"identical to snapshot of {prev}? {same((r.sid, r.date), (r.sid, prev))}")


if __name__ == "__main__":
    main()
