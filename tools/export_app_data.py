# =============================================================================
# export_app_data.py — Write the JSON files that the React app reads.
#
# Run:  uv run python tools/export_app_data.py
#
# The app only draws charts; Python does all the computing. Milestone 1
# writes two files to app/public/data/, both in the envelope of
# src/earnings_vol/contract.py (schema 0.2.0):
#   meta.json           what the project is, where the data comes from, the
#                       primary sample and the parameters behind it
#   sample_funnel.json  how many events survive each rule (export/funnel.py)
#
# Inputs: only committed files (data/derived/*.parquet and params.yaml), so
# the committed JSON can be rebuilt and checked without the local cache.
# =============================================================================

import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from earnings_vol import contract, params as params_mod, schema, store
from earnings_vol.export import funnel

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = ROOT / "app" / "public" / "data"
DERIVED = ROOT / "data" / "derived"
FILES = ["meta", "sample_funnel"]

# Where the data comes from, and whether it is inside this git repo.
# `uses` says which tables or series we take from the source. `committed` is
# False when we must not share the data. The licence is "see source" when we
# could not confirm one: we do not guess a licence.
# The two DoltHub repos each contain a LICENSE.md with the title
# "Attribution-ShareAlike 4.0 International" (read from the repos' dolt_docs
# table). Wikipedia text is CC BY-SA 4.0 too. Only small derived tables go in
# data/derived/.
DATA_SOURCES = [
    {
        "name": "DoltHub post-no-preference/earnings",
        "uses": "earnings_calendar, eps_history, eps_estimate",
        "url": "https://www.dolthub.com/repositories/post-no-preference/earnings",
        "licence": "CC BY-SA 4.0",
        "committed": True,
    },
    {
        "name": "DoltHub post-no-preference/options",
        "uses": "option_chain, volatility_history",
        "url": "https://www.dolthub.com/repositories/post-no-preference/options",
        "licence": "CC BY-SA 4.0",
        "committed": True,
    },
    {
        "name": "Wikipedia List of S&P 500 companies",
        "uses": "company names, GICS sectors and CIKs (revision 1382178819)",
        "url": "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
        "licence": "CC BY-SA 4.0",
        "committed": True,
    },
    {
        "name": "FRED (Federal Reserve Bank of St. Louis)",
        "uses": "DTB3 (3-month T-bill rate); VIXCLS (VIX, a CBOE index)",
        "url": "https://fred.stlouisfed.org/",
        "licence": "see source",
        "committed": False,
    },
    {
        "name": "CBOE single-stock VIX indices",
        "uses": "VX* single-stock IV indices",
        "url": "https://www.cboe.com/",
        "licence": "see source",
        "committed": False,
    },
    {
        "name": "Yahoo Finance prices (via yfinance)",
        "uses": "daily prices, market caps (one-time universe rank)",
        "url": "https://finance.yahoo.com/",
        "licence": "see source",
        "committed": False,
    },
]

# The licence that covers the committed data, and the attribution text that
# the licence asks us to show. `applies_to` lists the sources (by `name`) that
# the licence covers.
DATA_LICENCE = {
    "name": "CC BY-SA 4.0",
    "url": "https://creativecommons.org/licenses/by-sa/4.0/",
    "applies_to": [
        "DoltHub post-no-preference/earnings",
        "DoltHub post-no-preference/options",
        "Wikipedia List of S&P 500 companies",
    ],
    "attribution": (
        "Contains data from the DoltHub repositories post-no-preference/earnings "
        "and post-no-preference/options, and from the Wikipedia List of S&P 500 companies "
        "(revision 1382178819), licensed under Creative Commons "
        "Attribution-ShareAlike 4.0 International (CC BY-SA 4.0). Changes: "
        "selected, filtered and computed on by this project. CBOE and Yahoo Finance data is "
        "downloaded locally for analysis and is never committed to this repository."
    ),
}


def git_short_commit() -> str:
    """Return the short hash of HEAD, or "uncommitted" if git cannot tell us.

    Git fails when there is no git, or when the repo has no commit yet. In both
    cases we still want a file, so we write "uncommitted" instead of crashing.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "uncommitted"
    return result.stdout.strip() or "uncommitted"


def load_tables(derived: Path = DERIVED) -> dict:
    """The committed tables the views are built from."""
    names = ("events", "eps", "session", "session_snapshot", "security")
    return {n: store.read_table(derived / f"{n}.parquet", schema.REGISTRY[n]) for n in names}


def provenance(p, code_commit: str) -> dict:
    return {"params_hash": p.params_hash, "code_commit": code_commit, "sample_label": "daily",
            "dolt_commits": {"earnings": p["dolt"]["earnings_commit"], "options": p["dolt"]["options_commit"]}}


def funnel_data(tables: dict, p, code_commit: str) -> dict:
    return funnel.funnel_data(tables["events"], tables["session_snapshot"], tables["eps"], tables["session"], p,
                              provenance(p, code_commit))


def meta_data(tables: dict, p, code_commit: str, funnel_payload: dict | None = None) -> dict:
    fd = funnel_payload if funnel_payload is not None else funnel_data(tables, p, code_commit)
    w = p["windows"]
    return {
        "project": "earnings-vol-study",
        "milestone": 1,
        "title": "Earnings and implied volatility: an event study",
        "data_sources": DATA_SOURCES,
        "data_licence": DATA_LICENCE,
        "sample": funnel.sample_summary(tables["events"], fd, p),
        "params": {
            "event_window": list(w["event_window"]),
            "baseline": list(w["baseline"]),
            "baseline_exclusion": list(w["exclusion_zone"]),
            "cm30_horizon_sessions": int(p["iv"]["cm30_horizon_sessions"]),
            "clock": "NYSE sessions (exchange_calendars XNYS)",
        },
        "files": list(FILES),
        "provenance": provenance(p, code_commit),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the JSON files for the app.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR,
                        help="folder for meta.json and sample_funnel.json (default: app/public/data)")
    args = parser.parse_args(argv)

    p = params_mod.load()
    commit = git_short_commit()
    tables = load_tables()
    fd = funnel_data(tables, p, commit)
    now = datetime.now(timezone.utc)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for kind, data in (("meta", meta_data(tables, p, commit, fd)), ("sample_funnel", fd)):
        env = contract.envelope(kind, data, generated_at=now, source_commit=commit)
        out = args.out_dir / f"{kind}.json"
        out.write_text(contract.dumps(env), encoding="utf-8")
        print("Wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
