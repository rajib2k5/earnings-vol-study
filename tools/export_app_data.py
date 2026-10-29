# =============================================================================
# export_app_data.py — Write the JSON files that the React app reads.
#
# Run:  uv run python tools/export_app_data.py
#
# The app only draws charts; Python does all the computing. Milestone 2
# writes three files to app/public/data/, all in the envelope of
# src/earnings_vol/contract.py (schema 0.3.0):
#   meta.json           what the project is, where the data comes from, the
#                       primary sample and the parameters behind it
#   sample_funnel.json  how many events survive each rule (export/funnel.py)
#   iv_measures.json    how the implied move and the crush are distributed
#                       over the primary sample (export/iv_view.py):
#                       counts, quantiles and histograms only
#
# Inputs: only committed files (data/derived/*.parquet and params.yaml), so
# the committed JSON can be rebuilt and checked without the local cache.
# =============================================================================

import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from earnings_vol import contract, params as params_mod, schema, store
from earnings_vol.export import funnel, iv_view

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = ROOT / "app" / "public" / "data"
DERIVED = ROOT / "data" / "derived"
FILES = list(contract.KINDS)

# Where the data comes from, and whether values derived from it are in this
# git repo. `uses` says what we take from the source. `committed` is True when
# the repository holds values derived from the source (data/derived/ or
# app/public/data/; the About page shows "derived rows only"), False when
# nothing of it leaves this machine. The licence is "see source" where we
# could not confirm one: we do not guess a licence. The root DATA.md says
# what each source's terms restrict.
# The two DoltHub repos each contain a LICENSE.md with the title
# "Attribution-ShareAlike 4.0 International" (read from the repos' dolt_docs
# table). Wikipedia text is CC BY-SA 4.0 too. FRED marks DTB3 public domain
# and asks for a citation (the attribution below gives it). Since the owner's
# decision of 2026-10-29 the repository also holds two labels made from
# Yahoo prices (data/derived/README.md lists them); no Cboe value is committed.
# The timing labels are not made from Yahoo data: they come from documents,
# and a Yahoo gap only decides which events are looked up or read twice
# (data model §2.1, class F).
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
        "name": "FRED DTB3",
        "uses": "the 3-month Treasury bill rate: the discount factor and the carry inside the committed IVs and "
                "moves (the rate series itself stays local)",
        "url": "https://fred.stlouisfed.org/series/DTB3",
        "licence": "public domain (FRED asks for a citation)",
        "committed": True,
    },
    {
        "name": "FRED VIXCLS (Cboe VIX)",
        "uses": "the VIX close, for the market adjustment (local only)",
        "url": "https://fred.stlouisfed.org/series/VIXCLS",
        "licence": "Cboe copyright (see source)",
        "committed": False,
    },
    {
        "name": "Cboe single-stock volatility indices (VX*)",
        "uses": "VXAPL, VXAZN, VXGOG, VXGS, VXIBM, to validate our 30-day IV (local only; not run yet)",
        "url": "https://www.cboe.com/",
        "licence": "Cboe terms of use (see source)",
        "committed": False,
    },
    {
        "name": "Yahoo Finance",
        "uses": "daily prices and market caps, read with yfinance (local); committed: two labels made from "
                "them, security.in_universe and timing_check.gap_verdict_yf",
        "url": "https://finance.yahoo.com/",
        "licence": "Yahoo terms of service (see source)",
        "committed": True,
    },
]

# The licence that covers the committed DoltHub and Wikipedia data, and the
# attribution text that it asks us to show (with FRED's citation, and what is
# NOT under it). `applies_to` lists the sources (by `name`) that the licence
# covers.
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
        "selected, filtered and computed on by this project. The IVs and moves are computed with "
        "the rate FRED DTB3: Board of Governors of the Federal Reserve System (US), 3-Month Treasury "
        "Bill Secondary Market Rate, Discount Basis [DTB3], retrieved from FRED, Federal Reserve Bank "
        "of St. Louis, https://fred.stlouisfed.org/series/DTB3, 2026-10-29 (public domain). Not under "
        "CC BY-SA: the labels made from Yahoo Finance prices (security.in_universe and "
        "timing_check.gap_verdict_yf, and the share of gap contradictions built from it) fall under "
        "Yahoo's terms of service. No Cboe data is committed."
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
    names = ("events", "eps", "session", "security", "iv_daily", "event_iv", "timing_check")
    return {n: store.read_table(derived / f"{n}.parquet", store.committed_schema(schema.REGISTRY[n])) for n in names}


def provenance(p, code_commit: str) -> dict:
    return {"params_hash": p.params_hash, "code_commit": code_commit, "sample_label": "daily",
            "dolt_commits": {"earnings": p["dolt"]["earnings_commit"], "options": p["dolt"]["options_commit"]}}


def funnel_data(tables: dict, p, code_commit: str) -> dict:
    return funnel.funnel_data(tables["events"], tables["iv_daily"], tables["eps"], tables["session"],
                              tables["event_iv"], tables["timing_check"], p, provenance(p, code_commit))


def iv_measures_data(tables: dict, p, code_commit: str) -> dict:
    _, primary = funnel.run_steps(tables["events"], tables["iv_daily"], tables["eps"], tables["session"], p)
    return iv_view.iv_measures_data(primary, tables["event_iv"], provenance(p, code_commit))


def meta_data(tables: dict, p, code_commit: str, funnel_payload: dict | None = None) -> dict:
    fd = funnel_payload if funnel_payload is not None else funnel_data(tables, p, code_commit)
    w = p["windows"]
    return {
        "project": "earnings-vol-study",
        "milestone": 2,
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
                        help="folder for the JSON files (default: app/public/data)")
    args = parser.parse_args(argv)

    p = params_mod.load()
    commit = git_short_commit()
    tables = load_tables()
    fd = funnel_data(tables, p, commit)
    now = datetime.now(timezone.utc)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for kind, data in (("meta", meta_data(tables, p, commit, fd)), ("sample_funnel", fd),
                       ("iv_measures", iv_measures_data(tables, p, commit))):
        env = contract.envelope(kind, data, generated_at=now, source_commit=commit)
        out = args.out_dir / f"{kind}.json"
        out.write_text(contract.dumps(env), encoding="utf-8")
        print("Wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
