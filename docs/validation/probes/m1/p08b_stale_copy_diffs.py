"""p08b: what are the dropped non-session snapshots that are NOT copies of their session? (claim 7)

  uv run python docs/validation/probes/m1/p08b_stale_copy_diffs.py

For every dropped off-session snapshot H mapped to session S (S has its own snapshot):
  - identical(H, S)?  (p08: 1,905 of 2,101 yes)
  - for the others: share of (expiration, strike, call_put) keys whose bid/ask are equal in H and S;
    is H identical to the snapshot of the NEXT session after H?  of the session before S?
    is S's own snapshot identical to the session before S (S itself stale)?
Also: off-session snapshots that are KEPT, by year and era.
"""
from collections import Counter
from datetime import date

import pandas as pd
import pyarrow.parquet as pq

from earnings_vol import config, params as params_mod
from earnings_vol.events import calendar, securities
from earnings_vol.events.run import DERIVED

COLS = ["date", "act_symbol", "expiration", "strike", "call_put", "bid", "ask"]
KEY = ["expiration", "strike", "call_put"]


def main():
    p = params_mod.load()
    cdir = config.cache_dir() / "dolt" / f"options@{p['dolt']['options_commit']}" / "option_chain"
    files = sorted(cdir.glob("*.parquet"))
    s = calendar.Sessions(sorted(pd.read_parquet(DERIVED / "session.parquet").session_date))
    alias = pd.read_parquet(DERIVED / "ticker_alias.parquet")
    alias = alias.astype(object).where(alias.notna(), None)
    ids = set(pd.read_parquet(DERIVED / "security.parquet").query("in_universe").security_id)
    first, last = date(2020, 1, 2), date(2026, 10, 26)
    k = pd.concat([pq.read_table(f, columns=["date", "act_symbol"]).to_pandas(date_as_object=True).drop_duplicates()
                   for f in files], ignore_index=True)
    k["sid"] = [securities.resolve_on(a, d, alias) for a, d in zip(k.act_symbol, k.date)]
    k = k[k.sid.isin(ids)]
    k["session"] = [s.as_of(d) for d in k.date]
    k = k[(k.session >= first) & (k.session <= last)]
    k["on"] = k.date == k.session
    on = set(zip(k[k.on].sid, k[k.on].session))
    off = k[~k.on]
    dropped = off[[(a, b) in on for a, b in zip(off.sid, off.session)]]
    kept_off = off[[(a, b) not in on for a, b in zip(off.sid, off.session)]]
    print("kept off-session by year:", dict(sorted(Counter(d.year for d in kept_off.date).items())),
          "; in the daily era (>= 2024-09-11):", int((kept_off.date >= date(2024, 9, 11)).sum()))

    need = set()
    for r in dropped.itertuples():
        need |= {r.date, r.session, s.prev_before(r.session), s.next_after(r.date)}
    q = pd.concat([t[t.date.isin(need)] for t in
                   (pq.read_table(f, columns=COLS).to_pandas(date_as_object=True) for f in files)], ignore_index=True)
    q["sid"] = [securities.resolve_on(a, d, alias) for a, d in zip(q.act_symbol, q.date)]
    G = {key: g[KEY + ["bid", "ask"]].sort_values(KEY).reset_index(drop=True) for key, g in q.groupby(["sid", "date"])}

    def same(a, b):
        return a in G and b in G and G[a].equals(G[b])

    def share_equal(a, b):
        m = G[a].merge(G[b], on=KEY, suffixes=("_h", "_s"))
        if m.empty:
            return 0.0, 0
        eq = ((m.bid_h == m.bid_s) & (m.ask_h == m.ask_s)).mean()
        return float(eq), len(m)

    rows = []
    for r in dropped.itertuples():
        if same((r.sid, r.date), (r.sid, r.session)):
            continue
        sh, n = share_equal((r.sid, r.date), (r.sid, r.session))
        rows.append({"sid": r.sid, "holiday": r.date, "dow": r.date.strftime("%a"), "session": r.session,
                     "share_quotes_equal": round(sh, 3), "common_keys": n,
                     "H==next_session": same((r.sid, r.date), (r.sid, s.next_after(r.date))),
                     "H==prev_of_S": same((r.sid, r.date), (r.sid, s.prev_before(r.session))),
                     "S==prev_of_S (S stale)": same((r.sid, r.session), (r.sid, s.prev_before(r.session)))})
    d = pd.DataFrame(rows)
    print("dropped but not identical:", len(d))
    print(d.groupby(["holiday", "dow"]).agg(n=("sid", "size"), med_share_equal=("share_quotes_equal", "median"),
                                             H_eq_next=("H==next_session", "sum"),
                                             H_eq_prevS=("H==prev_of_S", "sum"),
                                             S_stale=("S==prev_of_S (S stale)", "sum")).to_string())


if __name__ == "__main__":
    main()
