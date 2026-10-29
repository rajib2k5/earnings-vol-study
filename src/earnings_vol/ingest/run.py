# =============================================================================
# run.py — run_ingest(): fetch and extract every input of milestone 1.
#
# Run:  uv run python -m earnings_vol.ingest.run            (everything)
#       uv run python -m earnings_vol.ingest.run --only universe
#
# This is the thin I/O edge of the ingest layer (ADR 0001 §1). It writes only
# under raw_dir() and cache_dir(), and it never runs dolt in a shared clone:
# refresh_mirror() copies each clone first (see dolt.py).
#
# What it writes:
#   raw/wikipedia/sp500_<revid>.json        the pinned constituents revision
#   raw/yfinance/market_cap_<date>.csv      Yahoo market caps (local only)
#   raw/yfinance/<ticker>.parquet           Yahoo daily prices and actions (local only)
#   raw/fred/<series>.csv                   FRED DTB3 and VIXCLS
#   cache/dolt_mirror/<repo>/               private copies of the Dolt clones
#   cache/dolt/<repo>@<commit>/<table>.parquet          small tables
#   cache/dolt/<repo>@<commit>/<table>/<yyyy-mm>.parquet  option_chain by month
#   cache/universe.parquet                  the selection, before the events layer
#   cache/ingest_log.json                   timings and row counts of this run
# =============================================================================

import argparse
import json
import time
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from earnings_vol import config, params as params_mod
from earnings_vol.ingest import dolt, fred, prices, universe, wikipedia

REPOS = ("earnings", "options")


def mirror_dir(repo: str) -> Path:
    return config.cache_dir() / "dolt_mirror" / repo


def extract_dir(repo: str, commit: str) -> Path:
    return config.cache_dir() / "dolt" / f"{repo}@{commit}"


def refresh_mirrors(log=print) -> dict:
    """Copy each shared clone into the cache unless the mirror already matches it."""
    out = {}
    for repo in REPOS:
        t0 = time.perf_counter()
        copied = dolt.refresh_mirror(config.dolt_repo(repo), mirror_dir(repo))
        out[repo] = {"copied": copied, "seconds": round(time.perf_counter() - t0, 2)}
        log(f"mirror {repo}: {'copied' if copied else 'already current'} ({out[repo]['seconds']} s)")
    return out


def pinned_commits(p) -> dict:
    """The commits named in params.yaml, checked to exist in the mirrors."""
    commits = {"earnings": p["dolt"]["earnings_commit"], "options": p["dolt"]["options_commit"]}
    for repo, commit in commits.items():
        if not dolt.commit_exists(mirror_dir(repo), commit):
            raise RuntimeError(f"commit {commit} is not in the {repo} mirror")
    return commits


def eligible_symbols(p, commits: dict) -> set[str]:
    """Symbols with calendar rows from the daily era on and options on the last data date."""
    cal = dolt.query(mirror_dir("earnings"),
                     f"SELECT DISTINCT act_symbol FROM {dolt.as_of('earnings_calendar', commits['earnings'])} "
                     f"WHERE `date` >= '{p['snapshot_eras']['daily_from']}'")
    opt = dolt.query(mirror_dir("options"),
                     f"SELECT act_symbol FROM {dolt.as_of('volatility_history', commits['options'])} "
                     f"WHERE `date` = '{p['snapshot_eras']['data_end']}'")
    return set(cal.column("act_symbol").to_pylist()) & set(opt.column("act_symbol").to_pylist())


def build_universe(p, commits: dict, log=print) -> pd.DataFrame:
    u = p["universe"]
    doc = wikipedia.fetch_revision(int(u["wikipedia_revision"]), config.raw_dir())
    constituents = wikipedia.parse_constituents(wikipedia.wikitext(doc))
    log(f"wikipedia revision {u['wikipedia_revision']}: {len(constituents)} constituents")
    cap_path = config.raw_dir() / "yfinance" / f"market_cap_{u['rank_date']}.csv"
    if cap_path.exists():
        caps = pd.read_csv(cap_path)
    else:
        symbols = [s for s in constituents["symbol"] if s not in u["drop_share_classes"]]
        t0 = time.perf_counter()
        caps = universe.fetch_market_caps(symbols)
        log(f"market caps: {len(caps)} symbols in {time.perf_counter() - t0:.0f} s, "
            f"{caps['market_cap_yf'].isna().sum()} missing")
        cap_path.parent.mkdir(parents=True, exist_ok=True)
        caps.to_csv(cap_path, index=False)
    eligible = eligible_symbols(p, commits)
    sec = universe.select_universe(constituents, caps, eligible, n_largest=int(u["n_largest"]),
                                   force_include=list(u["force_include"]),
                                   drop_share_classes=list(u["drop_share_classes"]))
    log(f"universe: {int(sec['in_universe'].sum())} of {len(sec)} securities")
    return sec


def extract_small_tables(tickers: list[str], commits: dict, log=print) -> dict:
    """earnings_calendar, eps_history and eps_estimate for the universe, one query each."""
    out = {}
    specs = {
        "earnings_calendar": "act_symbol, `date`, `when`",
        "eps_history": "act_symbol, period_end_date, reported, estimate",
        "eps_estimate": "`date`, act_symbol, period, period_end_date, consensus, `count`, high, low",
    }
    base = extract_dir("earnings", commits["earnings"])
    base.mkdir(parents=True, exist_ok=True)
    for table, cols in specs.items():
        extra = " AND period = 'Current Quarter'" if table == "eps_estimate" else ""
        sql = (f"SELECT {cols} FROM {dolt.as_of(table, commits['earnings'])} "
               f"WHERE act_symbol IN {dolt.sql_list(tickers)}{extra}")
        t0 = time.perf_counter()
        tbl = dolt.query(mirror_dir("earnings"), sql)
        seconds = round(time.perf_counter() - t0, 2)
        pq.write_table(tbl, base / f"{table}.parquet", compression="zstd")
        out[table] = {"rows": tbl.num_rows, "seconds": seconds}
        log(f"{table}: {tbl.num_rows} rows in {seconds} s")
    return out


def extract_option_chain(tickers: list[str], commits: dict, first: date, last: date, log=print) -> list[dict]:
    cols = ["date", "act_symbol", "expiration", "strike", "call_put", "bid", "ask", "vol"]
    return dolt.extract_months(mirror_dir("options"), "option_chain", cols, tickers, commits["options"],
                               first, last, extract_dir("options", commits["options"]) / "option_chain", log=log)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Fetch and extract the milestone-1 inputs.")
    ap.add_argument("--only", choices=["mirrors", "universe", "small", "prices", "fred", "chain"], default=None)
    ap.add_argument("--chain-from", default=None, help="first option_chain month (default: daily era start)")
    args = ap.parse_args(argv)
    p = params_mod.load()
    log_path = config.cache_dir() / "ingest_log.json"
    record = json.loads(log_path.read_text()) if log_path.exists() else {}
    record["last_run_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    shared = {r: config.dolt_repo(r) for r in REPOS}
    before = {r: dolt.stat_fingerprint(shared[r]) for r in REPOS}
    want = (lambda step: args.only in (None, step))

    if want("mirrors"):
        record["mirrors"] = refresh_mirrors()
    commits = pinned_commits(p)
    record["commits"] = commits

    sec_path = config.cache_dir() / "universe.parquet"
    if want("universe") or not sec_path.exists():
        with dolt.guard(shared["earnings"], mirror_dir("earnings")), dolt.guard(shared["options"], mirror_dir("options")):
            sec = build_universe(p, commits)
        sec.to_parquet(sec_path)
    sec = pd.read_parquet(sec_path)
    ids = sorted(sec.loc[sec["in_universe"], "security_id"])
    tickers = universe.source_tickers(ids)
    record["tickers"] = tickers

    if want("small"):
        with dolt.guard(shared["earnings"], mirror_dir("earnings")):
            record["small_tables"] = extract_small_tables(tickers, commits)
    if want("prices"):
        # Yahoo keeps a renamed company's whole history under its current
        # ticker, so prices are fetched by security_id (META, not FB).
        record["prices"] = prices.download_all([universe.yahoo_symbol(t) for t in ids] + ["SPY"],
                                               config.raw_dir() / "yfinance")
    if want("fred"):
        record["fred"] = fred.download_all(["DTB3", "VIXCLS"], config.raw_dir() / "fred")
    if want("chain"):
        first = date.fromisoformat(args.chain_from or p["snapshot_eras"]["daily_from"])
        last = date.fromisoformat(p["snapshot_eras"]["data_end"])
        t0 = time.perf_counter()
        with dolt.guard(shared["options"], mirror_dir("options")):
            months = extract_option_chain(tickers, commits, first, last)
        record.setdefault("option_chain", {})[f"{first}..{last}"] = {
            "months": months, "wall_seconds": round(time.perf_counter() - t0, 1)}

    after = {r: dolt.stat_fingerprint(shared[r]) for r in REPOS}
    for r in REPOS:
        changed = dolt.diff_fingerprints(before[r], after[r])
        if changed:
            raise dolt.DoltWriteError(f"shared clone {r} changed during the run: {changed[:10]}")
    record["shared_clones_unchanged"] = True
    log_path.write_text(json.dumps(record, indent=2, sort_keys=True, default=str) + "\n")
    print("shared clones unchanged; log at", log_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
