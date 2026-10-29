"""p06: the EPS period match (claims 5a, 5b).

  uv run python docs/validation/probes/m1/p06_eps_match.py

1. Re-implements ADR 0002 §3's rule from its text (first event 10..100 days after the
   period end; a tie loser is an orphan; no event and a window starting before
   2020-01-22 is pre_calendar) and compares it with the committed eps.parquet.
2. Attacks the rule: for every orphan, is the company's announcement actually in the
   calendar, just outside the window? For every match, is the lag plausible for "its
   own" announcement (a lag of 86-100 days is the NEXT quarter's report)?
3. Sensitivity: the orphan count and rate with lag_min = 10, 0 and -10.
"""
import datetime as dt
from collections import Counter

import pandas as pd
import pyarrow.parquet as pq

from earnings_vol import config, params as params_mod
from earnings_vol.events import securities
from earnings_vol.events.run import DERIVED

CAL_START = dt.date(2020, 1, 22)


def match(periods, events, lo, hi):
    """Independent implementation from the ADR text. events: sorted [(date, id)]."""
    prop = {}
    for pe in periods:
        c = [(d, e) for d, e in events if lo <= (d - pe).days <= hi]
        prop[pe] = min(c) if c else None
    by_event = {}
    for pe, c in prop.items():
        if c:
            by_event.setdefault(c[1], []).append(pe)
    out = {}
    for pe, c in prop.items():
        if c is None:
            out[pe] = (None, "pre_calendar" if pe + dt.timedelta(days=lo) < CAL_START else "orphan")
        else:
            win = min(by_event[c[1]], key=lambda q: (c[0] - q).days)
            out[pe] = (c[1], "matched") if win == pe else (None, "orphan")
    return out


def main():
    p = params_mod.load()
    eps = pd.read_parquet(DERIVED / "eps.parquet")
    ev = pd.read_parquet(DERIVED / "events.parquet")
    hist = pq.read_table(config.cache_dir() / "dolt" / f"earnings@{p['dolt']['earnings_commit']}" /
                         "eps_history.parquet").to_pandas(date_as_object=True)
    alias = pd.read_parquet(DERIVED / "ticker_alias.parquet")
    alias = alias.astype(object).where(alias.notna(), None)
    hist["sid"] = [securities.resolve_any(t, alias) for t in hist.act_symbol]
    uni = set(ev.security_id)
    h = hist[hist.sid.isin(uni)]
    print(f"eps_history rows for the universe tickers: {len(h)}; distinct (security, period): "
          f"{h.groupby(['sid', 'period_end_date']).ngroups}; committed eps rows: {len(eps)}")

    ev_by = {s: sorted(zip(g.announce_date, g.event_id)) for s, g in ev.groupby("security_id")}
    for lo in (10, 0, -10):
        res = {}
        for s, g in eps.groupby("security_id"):
            res.update({(s, pe): v for pe, v in match(list(g.fiscal_period_end), ev_by.get(s, []), lo, 100).items()})
        st = Counter(v[1] for v in res.values())
        if lo == 10:
            diff = [(k, v, (r.event_id, r.match_status)) for k, v in res.items()
                    for r in [eps[(eps.security_id == k[0]) & (eps.fiscal_period_end == k[1])].iloc[0]]
                    if (v[0], v[1]) != ((None if pd.isna(r.event_id) else r.event_id), r.match_status)]
            print("independent matcher vs committed eps.parquet, differences:", diff)
        late = sorted((k[0], str(k[1]), v[0], (dt.date.fromisoformat(v[0].split(":")[1]) - k[1]).days)
                      for k, v in res.items() if v[0] and (dt.date.fromisoformat(v[0].split(":")[1]) - k[1]).days >= 70)
        print(f"lag_min={lo:>3}: {dict(st)}; orphan rate {st['orphan']}/{st['orphan'] + st['matched']} = "
              f"{st['orphan'] / (st['orphan'] + st['matched']):.4f}; matches with lag >= 70 days: {len(late)} {late}")

    print("\nOrphans (committed) whose company HAS a calendar row within 0..9 days after the period end:")
    n = 0
    for r in eps[eps.match_status == "orphan"].itertuples():
        near = [(str(d), (d - r.fiscal_period_end).days) for d, _ in ev_by[r.security_id]
                if 0 <= (d - r.fiscal_period_end).days < 10]
        if near:
            n += 1
            nxt = eps[(eps.security_id == r.security_id) & (eps.event_id == f"{r.security_id}:{near[0][0]}")]
            print(f"  {r.security_id} {r.fiscal_period_end}: calendar event {near}; that event is "
                  f"{'linked to period ' + str(nxt.fiscal_period_end.iloc[0]) if len(nxt) else 'linked to no period'}")
    print("  count:", n)
    print("\nOrphans of companies that were not yet public (PLTR listed 2020-09-30):",
          eps[(eps.match_status == "orphan") & (eps.security_id == "PLTR")].fiscal_period_end.astype(str).tolist())
    print("\nEvents linked to a period 86-100 days earlier (the next quarter's report taking the EPS of the one before):")
    m = eps[(eps.match_status == "matched") & (eps.lag_days.astype(float) >= 70)]
    print(m[["security_id", "fiscal_period_end", "event_id", "lag_days", "reported", "estimate"]].to_string(index=False))
    print("\nEvents with no EPS link at all, in the samples:")
    linked = set(eps.event_id.dropna())
    unl = ev[~ev.event_id.isin(linked) & ev["sample"].isin(["daily", "mixed", "coarse"])]
    print(unl.groupby(["security_id"]).size().sort_values(ascending=False).head(12).to_dict(),
          "total", len(unl))


if __name__ == "__main__":
    main()
