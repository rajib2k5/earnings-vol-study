"""p14: the universe rule and the P1 count (claims 13 P1, 14).

  uv run python docs/validation/probes/m1/p14_universe_and_p1.py

- recount ranks, the VX names, the rename table;
- late-start scan: a universe company whose calendar rows start after 2020-04 may hide a ticker change
  (one GROUP BY query on the project's MIRROR, never the shared clone, finds tickers whose rows END
  shortly before such a start);
- P1: NULL-label calendar rows of the 50 dated 2024-09-11 .. 2026-10-26.
"""
from datetime import date, timedelta

import pandas as pd

from earnings_vol import config, params as params_mod
from earnings_vol.events.run import DERIVED
from earnings_vol.ingest import dolt


def main():
    p = params_mod.load()
    sec = pd.read_parquet(DERIVED / "security.parquet")
    ev = pd.read_parquet(DERIVED / "events.parquet")
    al = pd.read_parquet(DERIVED / "ticker_alias.parquet")
    u = sec[sec.in_universe]
    print(f"rows {len(sec)}; ranked {sec.universe_rank.notna().sum()}; in_universe {len(u)}; "
          f"ranks of the 50: {sorted(u.universe_rank.astype(int))[:3]}..{sorted(u.universe_rank.astype(int))[-3:]}")
    print("unranked constituents:", sec[sec.universe_rank.isna()].security_id.tolist())
    print("VX names:", u[u.cboe_vx_index.notna()][["security_id", "universe_rank", "cboe_vx_index"]].to_dict("records"))
    print("aliases that are not the identity:", al[al.ticker != al.security_id].to_dict("records"))
    print("share classes dropped by params:", p["universe"]["drop_share_classes"],
          "; any of them in security:", sorted(set(p["universe"]["drop_share_classes"]) & set(sec.security_id)))

    first = ev.groupby("security_id").announce_date.min()
    late = first[first > date(2020, 4, 30)]
    print("universe companies whose calendar starts after 2020-04:", late.astype(str).to_dict())
    mirror = config.cache_dir() / "dolt_mirror" / "earnings"
    rng = dolt.query(mirror, "SELECT act_symbol, MIN(`date`) AS first, MAX(`date`) AS last, COUNT(*) AS n FROM "
                             f"{dolt.as_of('earnings_calendar', p['dolt']['earnings_commit'])} GROUP BY act_symbol"
                     ).to_pandas()
    rng["first"], rng["last"] = pd.to_datetime(rng["first"]).dt.date, pd.to_datetime(rng["last"]).dt.date
    for sid, d in late.items():
        cand = rng[(rng["last"] < d) & (rng["last"] >= d - timedelta(days=200)) & (rng.n >= 2)]
        print(f"  {sid} starts {d}: tickers whose rows end in the 200 days before: "
              f"{sorted(cand.act_symbol.tolist())[:25]}{' ...' if len(cand) > 25 else ''} ({len(cand)})")

    # P1
    win = ev[(ev.announce_date >= date(2024, 9, 11)) & (ev.announce_date <= date(2026, 10, 26))]
    nulls = win[win.timing_raw.isna()]
    print(f"P1: {len(nulls)} NULL of {len(win)} rows = {len(nulls) / len(win):.4%}:",
          nulls.event_id.tolist())
    d = ev[ev["sample"] == "daily"]
    print(f"P1 over the daily sample by day 0: {d.timing_raw.isna().sum()} of {len(d)}; all rows: "
          f"{ev.timing_raw.isna().sum()} of {len(ev)} = {ev.timing_raw.isna().mean():.4%}")


if __name__ == "__main__":
    main()
