# pd01 (claims 1a, 1d): an independent oracle for the EPS period match.
#
# Oracle: eps_estimate's "Current Quarter" row names the quarter that has not
# been reported yet. So for an event on D, the Current-Quarter period end in the
# last weekly snapshot dated before D (prev) is the quarter D reports, IF the
# first snapshot after D (next) has rolled to a later period ("bracketed").
#
# Compared with: (i) the committed data/derived/eps.parquet; (ii) the matcher run
# with the pre-review rule (window_start=10), as the falsifier check: the oracle
# must disagree with the old rule's known wrong links.
#
# Run: uv run --frozen python docs/validation/probes/m1-delta/pd01_eps_oracle.py
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "src"))
from earnings_vol.events import eps as eps_mod  # noqa: E402

DATA = Path(os.environ.get("VOL_DATA_DIR", "~/data/vol-projects")).expanduser() / "earnings-vol-study"
EXT = DATA / "cache" / "dolt" / "earnings@fjrb6h5le9h1qiif2j4pl6cpaas7pnee"
ALIAS = {"FB": "META", "UTX": "RTX"}   # written by hand, not taken from the code


def rd(name):
    return pq.read_table(EXT / f"{name}.parquet").to_pandas(date_as_object=True)


est = rd("eps_estimate")
est = est[est["period"] == "Current Quarter"].copy()
est["sid"] = est["act_symbol"].map(lambda t: ALIAS.get(t, t))
snaps = {sid: g.sort_values("date")[["date", "period_end_date"]].drop_duplicates() for sid, g in est.groupby("sid")}

ev = pd.read_parquet(REPO / "data/derived/events.parquet")
for c in ("announce_date", "announce_date_used", "day_m1_session", "fiscal_period_end"):
    ev[c] = ev[c].map(lambda v: v if v is None or isinstance(v, date) else pd.Timestamp(v).date())
eps = pd.read_parquet(REPO / "data/derived/eps.parquet")
eps["fiscal_period_end"] = eps["fiscal_period_end"].map(lambda v: pd.Timestamp(v).date())


def oracle(sid, d):
    s = snaps.get(sid)
    if s is None:
        return None, None, "no_estimates"
    before = s[s["date"] < d]
    after = s[s["date"] > d]
    if before.empty or after.empty:
        return None, None, "no_bracket"
    b, a = before.iloc[-1], after.iloc[0]
    if (d - b["date"]).days > 21 or (a["date"] - d).days > 21:
        return b["period_end_date"], a["period_end_date"], "gap>21d"
    if b["period_end_date"] == a["period_end_date"]:
        return b["period_end_date"], a["period_end_date"], "no_roll"
    return b["period_end_date"], a["period_end_date"], "bracketed"


def compare(link: dict, label: str):
    rows = []
    for r in ev.itertuples(index=False):
        pb, pa, kind = oracle(r.security_id, r.announce_date)
        rows.append({"event_id": r.event_id, "sid": r.security_id, "D": r.announce_date, "oracle": pb,
                     "after": pa, "kind": kind, "linked": link.get(r.event_id)})
    df = pd.DataFrame(rows)
    br = df[df["kind"] == "bracketed"]
    bad = br[br["oracle"] != br["linked"]]
    print(f"[{label}] events {len(df)}; oracle kinds {df['kind'].value_counts().to_dict()}")
    print(f"[{label}] bracketed {len(br)}; agree {int((br['oracle'] == br['linked']).sum())}; disagree {len(bad)}")
    if len(bad):
        print(bad[["event_id", "oracle", "after", "linked"]].to_string(index=False))
    nr = df[df["kind"] == "no_roll"]
    print(f"[{label}] no_roll events (oracle saw no roll-over across D) {len(nr)}:")
    print(nr[["event_id", "oracle", "after", "linked"]].to_string(index=False))
    return df


committed = {e: p for e, p in zip(eps["event_id"], eps["fiscal_period_end"]) if isinstance(e, str)}
print("== committed eps.parquet ==")
dc = compare(committed, "committed")

# Falsifier check: the pre-review rule (+10 .. +100 days) through the same code path.
hist, estimates = rd("eps_history"), rd("eps_estimate")
aliases = pd.read_parquet(REPO / "data/derived/ticker_alias.parquet")
for c in ("valid_from", "valid_to"):
    aliases[c] = aliases[c].map(lambda v: None if v is None or pd.isna(v) else pd.Timestamp(v).date())
old = eps_mod.build_eps(hist, estimates, aliases, ev, window_start=10, lag_max=100, calendar_start=date(2020, 1, 22))
old_link = {e: p for e, p in zip(old["event_id"], old["fiscal_period_end"]) if isinstance(e, str)}
print("\n== falsifier: pre-review rule window_start=10 ==")
compare(old_link, "old_rule")

# Rebuild with the current rule from the cache and compare with the committed table.
new = eps_mod.build_eps(hist, estimates, aliases, ev, window_start="month_start", lag_max=100,
                        calendar_start=date(2020, 1, 22))
new_link = {e: p for e, p in zip(new["event_id"], new["fiscal_period_end"]) if isinstance(e, str)}
print("\nrebuild(current rule) link == committed link:", new_link == committed,
      "| status counts", new["match_status"].value_counts().sort_index().to_dict())

# 1d: events that sit in two or more periods' windows, and long lags.
per = eps.groupby("security_id")["fiscal_period_end"].apply(sorted).to_dict()
multi = []
for r in ev.itertuples(index=False):
    wins = [pe for pe in per.get(r.security_id, []) if pe.replace(day=1) <= r.announce_date <= pe + timedelta(days=100)]
    if len(wins) >= 2:
        multi.append((r.event_id, [str(w) for w in wins], str(committed.get(r.event_id))))
print(f"\n1d: events inside >= 2 periods' windows: {len(multi)}")
for m_ in multi:
    print("  ", m_, "oracle:", oracle(m_[0].split(":")[0], date.fromisoformat(m_[0].split(":")[1]))[::2])
lagged = eps.dropna(subset=["lag_days"])
print("lag_days distribution of links:", lagged["lag_days"].astype(int).describe().round(1).to_dict())
print("links with lag >= 60:", lagged[lagged["lag_days"].astype(int) >= 60][["security_id", "fiscal_period_end", "event_id", "lag_days"]].to_string(index=False))
print("links with lag < 0:", int((lagged["lag_days"].astype(int) < 0).sum()),
      lagged[lagged["lag_days"].astype(int) < 0]["security_id"].value_counts().to_dict())
