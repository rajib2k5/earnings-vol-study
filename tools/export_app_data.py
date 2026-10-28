# =============================================================================
# export_app_data.py — Write the JSON files that the React app reads.
#
# Run:  uv run python tools/export_app_data.py
#
# The app only draws charts; Python does all the computing. Today (milestone 0)
# there is one file, app/public/data/meta.json. It says what the project is and
# where the data comes from: the table of data sources, the licence and the
# attribution text on the About page all come from here, and the app keeps no
# copy of them. Every file uses the envelope in src/earnings_vol/contract.py.
# =============================================================================

import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from earnings_vol import contract

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "app" / "public" / "data" / "meta.json"

# Where the data comes from, and whether it is inside this git repo.
# `uses` says which tables or series we take from the source. `committed` is
# False when we must not share the data. The licence is "see source" when we
# could not confirm one: we do not guess a licence.
# The two DoltHub repos each contain a LICENSE.md with the title
# "Attribution-ShareAlike 4.0 International" (read from the repos' dolt_docs
# table). Only small derived tables go in data/derived/.
DATA_SOURCES = [
    {
        "name": "DoltHub post-no-preference/earnings",
        "uses": "earnings_calendar, eps_history",
        "url": "https://www.dolthub.com/repositories/post-no-preference/earnings",
        "licence": "CC BY-SA 4.0",
        "committed": True,
    },
    {
        "name": "DoltHub post-no-preference/options",
        "uses": "option_chain",
        "url": "https://www.dolthub.com/repositories/post-no-preference/options",
        "licence": "CC BY-SA 4.0",
        "committed": True,
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
        "uses": "daily prices",
        "url": "https://finance.yahoo.com/",
        "licence": "see source",
        "committed": False,
    },
]

# The licence that covers the committed data, and the attribution text that
# the licence asks us to show. `applies_to` lists the sources (by `name`) that
# the licence covers. We only selected and filtered rows: we did not aggregate.
DATA_LICENCE = {
    "name": "CC BY-SA 4.0",
    "url": "https://creativecommons.org/licenses/by-sa/4.0/",
    "applies_to": [
        "DoltHub post-no-preference/earnings",
        "DoltHub post-no-preference/options",
    ],
    "attribution": (
        "Contains data from the DoltHub repositories post-no-preference/earnings "
        "and post-no-preference/options, licensed under Creative Commons "
        "Attribution-ShareAlike 4.0 International (CC BY-SA 4.0). Changes: "
        "selected and filtered by this project. CBOE and Yahoo Finance data is "
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


def meta_data() -> dict:
    return {
        "project": "earnings-vol-study",
        "milestone": 0,
        "title": "Earnings and implied volatility: an event study",
        "data_sources": DATA_SOURCES,
        "data_licence": DATA_LICENCE,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the JSON files for the app.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help="where to write meta.json (default: app/public/data/meta.json)")
    args = parser.parse_args(argv)

    env = contract.envelope(
        "meta", meta_data(),
        generated_at=datetime.now(timezone.utc),
        source_commit=git_short_commit(),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(contract.dumps(env), encoding="utf-8")
    print("Wrote", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
