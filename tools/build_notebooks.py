# =============================================================================
# build_notebooks.py — Make the notebooks from the code in src/.
#
# Run:    uv run python tools/build_notebooks.py          (write the notebooks)
#         uv run python tools/build_notebooks.py --check  (compare, write nothing)
#
# WHY A BUILD STEP
#   A notebook is a JSON file. If we edit it by hand, or let Jupyter write
#   outputs and run counts into it, git diffs become noise. So we generate it
#   from this file. The notebooks IMPORT the package (earnings_vol) and do not
#   copy its code, so src/ is the one source of truth.
#
# DETERMINISTIC
#   The same code always gives the same bytes: no outputs, no run counts, cell
#   ids "cell-00", "cell-01", ..., fixed metadata. That is what lets --check
#   compare the file on disk with a fresh build, and tests/test_notebooks_sync.py
#   run that check.
#
# OUTPUT
#   notebooks/00_scaffold_tour.ipynb   milestone 0: config and the envelope
#   notebooks/01_events.ipynb          milestone 1: sessions, day 0, the EPS
#                                      match and the sample funnel
#   notebooks/02_iv_measures.ipynb     milestone 2: Black-76, the session clock,
#                                      E and the implied move, the event-aware
#                                      30-day IV, and the committed measures
# =============================================================================

import argparse
import sys
from pathlib import Path

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

from earnings_vol import __version__, contract

ROOT = Path(__file__).resolve().parent.parent
NOTEBOOK_DIR = ROOT / "notebooks"
NOTEBOOK_PATH = NOTEBOOK_DIR / "00_scaffold_tour.ipynb"


def _finish(cells: list) -> nbformat.NotebookNode:
    """Wrap cells in a notebook with fixed metadata and ids cell-00, cell-01, ..."""
    nb = new_notebook(metadata={
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    })
    # nbformat 4.5 requires every cell to have an id. By default nbformat makes
    # a random id, which would change the bytes on every build. We set the ids
    # ourselves, below.
    nb.nbformat_minor = 5
    nb.cells = cells
    for i, cell in enumerate(nb.cells):
        cell["id"] = f"cell-{i:02d}"
    nbformat.validate(nb)
    return nb


def build_notebook() -> nbformat.NotebookNode:
    return _finish([
        new_markdown_cell(
            "# Scaffold tour\n\n"
            "This notebook imports the `earnings_vol` package. It does not "
            "copy the code. Run it with `uv run jupyter lab` from the project "
            "folder (or any Python where the package is installed).\n\n"
            f"Package version: `{__version__}`. "
            f"Contract schema version: `{contract.SCHEMA_VERSION}`. "
            "We write both numbers here when we build the notebook. If the "
            "code changes and we forget to build again, "
            "`tools/build_notebooks.py --check` tells us."
        ),
        new_markdown_cell(
            "## 1. Where the data lives\n"
            "`data_dir()` reads the environment variable `VOL_DATA_DIR`. If it "
            "is not set, it uses `~/data/vol-projects`."
        ),
        new_code_cell(
            "from earnings_vol import config\n"
            "\n"
            "print(config.data_dir())\n"
        ),
        new_markdown_cell(
            "## 2. The envelope for the app\n"
            "Python writes JSON, the React app only draws it. Every file has "
            "the same five keys. We pass a fixed time, so the output is the "
            "same on every run: 14:00 at +02:00 is 12:00 UTC."
        ),
        new_code_cell(
            "from datetime import datetime, timedelta, timezone\n"
            "\n"
            "from earnings_vol import contract\n"
            "\n"
            "when = datetime(2026, 10, 27, 14, 0, tzinfo=timezone(timedelta(hours=2)))\n"
            "env = contract.envelope(\"demo\", {\"answer\": 42}, generated_at=when,\n"
            "                        source_commit=\"abc1234\")\n"
            "print(contract.dumps(env))\n"
        ),
        new_markdown_cell(
            "## 3. Read the code\n"
            "`inspect.getsource` prints the code of `contract.envelope` as it is "
            "in `src/` right now. Read it line by line."
        ),
        new_code_cell(
            "import inspect\n"
            "\n"
            "print(inspect.getsource(contract.envelope))\n"
        ),
    ])


def build_events_notebook() -> nbformat.NotebookNode:
    """notebooks/01_events.ipynb: milestone 1, built from the committed tables."""
    return _finish([
        new_markdown_cell(
            "# Milestone 1: universe and events\n\n"
            "This notebook imports `earnings_vol` and reads the committed tables in "
            "`data/derived/`. It defines no logic of its own. The walkthrough is "
            "`docs/milestones/01-universe-and-events.md`.\n\n"
            "To rebuild the tables from the sources (it needs the Dolt clones and the "
            "network):\n\n"
            "```\n"
            "uv run python -m earnings_vol.ingest.run\n"
            "uv run python -m earnings_vol.events.run\n"
            "uv run python -m earnings_vol.measures.run\n"
            "uv run python tools/export_app_data.py\n"
            "```\n\n"
            f"Contract schema version: `{contract.SCHEMA_VERSION}`."
        ),
        new_markdown_cell(
            "## 1. Day 0 on the NYSE clock (ADR 0002 §2)\n"
            "Apple reported after the close on Thursday 2025-10-30, so day -1 is 10-30 "
            "and day 0 is Friday 10-31. Alphabet's calendar row of 2024-10-29 said BMO; "
            "the press release says after the close, which moves day 0 one session later."
        ),
        new_code_cell(
            "from datetime import date\n"
            "\n"
            "from earnings_vol.events import calendar\n"
            "\n"
            "eras = {\"weekly_from\": \"2019-02-09\", \"mwf_from\": \"2020-01-06\",\n"
            "        \"daily_from\": \"2024-09-11\", \"data_end\": \"2026-10-26\"}\n"
            "table = calendar.build_session_table(date(2024, 1, 1), date(2025, 12, 31), eras)\n"
            "sessions = calendar.Sessions(table[\"session_date\"].tolist())\n"
            "for d, label in [(date(2025, 10, 30), \"AMC\"), (date(2024, 10, 29), \"BMO\"),\n"
            "                 (date(2024, 10, 29), \"AMC\"), (date(2025, 5, 3), None)]:\n"
            "    day0, day_m1 = calendar.day0(d, label, sessions)\n"
            "    print(d, label, \"-> day -1\", day_m1, \" day 0\", day0)\n"
        ),
        new_markdown_cell(
            "## 2. The EPS-period match (ADR 0002 §3)\n"
            "Costco's quarters end mid-month and are stored as month-ends, so its May report "
            "(2025-05-29) comes 2 days *before* the stored end 2025-05-31. A period's window "
            "therefore opens early in its month: 14 days after the first, the rule in "
            "`params.yaml` (the 14 days keep a slow reporter's report out of the next "
            "period's window until it is 74 days late). The March report is missing from "
            "the calendar: the February period could reach 05-29 (lag 90), but the May period "
            "is nearer, so periods and events are paired one-to-one, nearest in total, and "
            "February is the orphan. It does not take the next quarter's report."
        ),
        new_code_cell(
            "from earnings_vol import params\n"
            "from earnings_vol.events.eps import match_periods\n"
            "\n"
            "em = params.load()[\"eps_match\"]   # window_start \"month_start+14\", lag_max_days 100\n"
            "out = match_periods([date(2024, 11, 30), date(2025, 2, 28), date(2025, 5, 31), date(2025, 8, 31)],\n"
            "                    [(date(2024, 12, 12), \"Q1\"), (date(2025, 5, 29), \"Q3\"), (date(2025, 9, 25), \"Q4\")],\n"
            "                    window_start=em[\"window_start\"], lag_max=em[\"lag_max_days\"],\n"
            "                    calendar_start=params.load().day(\"eps_match\", \"calendar_start\"))\n"
            "for period, (event, status) in sorted(out.items()):\n"
            "    print(period, event, status)\n"
        ),
        new_markdown_cell(
            "## 3. The committed tables and the sample funnel\n"
            "The same function that writes `app/public/data/sample_funnel.json`. Read the "
            "counts with its caveats, printed last. **Survivorship:** the 50 companies are "
            "today's largest S&P 500 members, so firms that shrank or left the index since "
            "2020 are missing and firms that grew are over-represented."
        ),
        new_code_cell(
            "from earnings_vol import params, schema, store\n"
            "from earnings_vol.export import funnel\n"
            "\n"
            "derived = params.ROOT / \"data\" / \"derived\"\n"
            "t = {n: store.read_table(derived / f\"{n}.parquet\", store.committed_schema(schema.REGISTRY[n]))\n"
            "     for n in (\"events\", \"eps\", \"session\", \"iv_daily\", \"event_iv\", \"timing_check\")}\n"
            "f = funnel.funnel_data(t[\"events\"], t[\"iv_daily\"], t[\"eps\"], t[\"session\"], t[\"event_iv\"],\n"
            "                       t[\"timing_check\"], params.load(), provenance={})\n"
            "for s in f[\"steps\"]:\n"
            "    print(f\"{s['n_events']:5d}  {s['label']}\")\n"
            "print(f[\"timing_status_counts\"])\n"
            "for c in f[\"caveats\"]:\n"
            "    print(\"Caveat:\", c)\n"
        ),
    ])


def build_iv_notebook() -> nbformat.NotebookNode:
    """notebooks/02_iv_measures.ipynb: milestone 2, from made-up numbers and the committed tables."""
    return _finish([
        new_markdown_cell(
            "# Milestone 2: IV measures\n\n"
            "This notebook imports `earnings_vol` and defines no logic of its own. The walkthrough is "
            "`docs/milestones/02-iv-measures.md`; the decisions are ADR 0003.\n\n"
            "To rebuild the tables from the option-chain extracts (it needs the local cache):\n\n"
            "```\n"
            "uv run python -m earnings_vol.events.run\n"
            "uv run python -m earnings_vol.measures.run --only snapshots\n"
            "uv run python -m earnings_vol.measures.run --only iv\n"
            "uv run python tools/export_app_data.py\n"
            "```\n\n"
            f"Contract schema version: `{contract.SCHEMA_VERSION}`."
        ),
        new_markdown_cell(
            "## 1. Black-76 on the parity forward (ADR 0003 §0 step 3)\n"
            "The price depends on sigma and T only through the total variance w = sigma^2 T, so a price pins "
            "down w and no day count enters. A made-up call: F = 100, K = 110, w = 0.04, DF = 0.99."
        ),
        new_code_cell(
            "from earnings_vol.measures import black\n"
            "\n"
            "price = float(black.black76(100.0, 110.0, 0.04, 0.99, True))\n"
            "print(f\"call {price:.6f}\")\n"
            "print(f\"w back from the price {black.implied_w(price, 100.0, 110.0, 0.99, True):.10f}\")\n"
            "print(\"a call above Black76(w = 4) has no root:\", black.implied_w(70.0, 100.0, 100.0, 1.0, True))\n"
        ),
        new_markdown_cell(
            "## 2. The clock: NYSE sessions to expiry (ADR 0003 §0 step 5)\n"
            "Sessions in (snapshot, expiry]: the expiry counts, the snapshot session does not. Thanksgiving "
            "2025 is closed and the half day after it counts as 1."
        ),
        new_code_cell(
            "from datetime import date\n"
            "\n"
            "from earnings_vol.events import calendar\n"
            "from earnings_vol.measures import chain\n"
            "\n"
            "eras = {\"weekly_from\": \"2019-02-09\", \"mwf_from\": \"2020-01-06\",\n"
            "        \"daily_from\": \"2024-09-11\", \"data_end\": \"2026-10-26\"}\n"
            "sessions = calendar.Sessions(calendar.build_session_table(date(2025, 1, 1), date(2025, 12, 31), eras)\n"
            "                             [\"session_date\"].tolist())\n"
            "for exp in (date(2025, 11, 14), date(2025, 11, 28)):\n"
            "    print(\"2025-10-30 ->\", exp, chain.tau_sessions(date(2025, 10, 30), exp, sessions), \"sessions,\",\n"
            "          (exp - date(2025, 10, 30)).days, \"calendar days\")\n"
        ),
        new_markdown_cell(
            "## 3. Event variance and the implied move (ADR 0003 §c)\n"
            "The AAPL worked example's two ATM total variances on day -1 (2025-10-30), both expiries spanning "
            "the 2025-10-31 day 0: w1 = 0.0034862510 at 11 sessions, w2 = 0.0056163135 at 20. "
            "E = (w1 tau2 - w2 tau1) / (tau2 - tau1)."
        ),
        new_code_cell(
            "from earnings_vol.measures import termstructure\n"
            "\n"
            "e, s2 = termstructure.event_variance(0.0034862510, 11, 0.0056163135, 20)\n"
            "moves = termstructure.implied_moves(e, s2)\n"
            "print(f\"E = {e:.8f}, sigma_d^2 = {s2:.4e} per session\")\n"
            "print(f\"implied move sqrt(E) = {moves['implied_move']:.4%}, \"\n"
            "      f\"expected |r0| = {moves['implied_abs_move_total']:.4%}\")\n"
            "print(f\"calendar clock instead: E = {termstructure.event_variance(0.0034862510, 15, 0.0056163135, 29)[0]:.8f}\")\n"
        ),
        new_markdown_cell(
            "## 4. The event-aware 30-day IV (ADR 0003 §b)\n"
            "Made-up two-component variances, sigma_d^2 = 0.0002 per session and E = 0.002, 25 sessions before "
            "day 0: clean expiries at 10 and 19 sessions, a spanning one at 30. The event-aware IV uses the "
            "clean class only; the blind one interpolates across the event and leaks E * 2/11 into the horizon."
        ),
        new_code_cell(
            "xs = [termstructure.Expiry(date(2026, 2, 13), 10, 0.0020, chain.annualised_iv(0.0020, 10), False),\n"
            "      termstructure.Expiry(date(2026, 2, 27), 19, 0.0038, chain.annualised_iv(0.0038, 19), False),\n"
            "      termstructure.Expiry(date(2026, 3, 13), 30, 0.0080, chain.annualised_iv(0.0080, 30), True)]\n"
            "day, _ = termstructure.day_measures(xs, sessions_to_event=25)\n"
            "print(day[\"cm30_method\"], f\"cm30 {day['cm30_iv']:.4f}, blind {day['cm30_blind_iv']:.4f}\")\n"
        ),
        new_markdown_cell(
            "## 5. The committed measures\n"
            "`data/derived/event_iv.parquet` holds one row per event (E, the implied move, the crushes, the "
            "realised move); `iv_daily.parquet` one row per company and session. The AAPL event of the worked "
            "example, read with the pipeline's DTB3 rate and its full chain."
        ),
        new_code_cell(
            "from earnings_vol import params, schema, store\n"
            "\n"
            "derived = params.ROOT / \"data\" / \"derived\"\n"
            "eiv = store.read_table(derived / \"event_iv.parquet\", schema.EVENT_IV).set_index(\"event_id\")\n"
            "r = eiv.loc[\"AAPL:2025-10-30\"]\n"
            "print(f\"E {r.evar_m1:.8f}, sqrt(E) {r.implied_move_m1:.4%}, cm30 crush {r.crush_mean_adj:.4f}, \"\n"
            "      f\"front crush {r.crush_front_fixed:.4f}, realised {r.realized_ret_0:.4%}\")\n"
            "print(eiv[\"implied_move_status\"].value_counts().to_dict())\n"
        ),
    ])


# name -> builder. The file is notebooks/<name>.ipynb.
NOTEBOOKS = {"00_scaffold_tour": build_notebook, "01_events": build_events_notebook, "02_iv_measures": build_iv_notebook}


def render(name: str = "00_scaffold_tour") -> str:
    """Return the notebook as the exact text that we write to disk."""
    text = nbformat.writes(NOTEBOOKS[name]())
    return text if text.endswith("\n") else text + "\n"


def check(path: Path | None = None, name: str = "00_scaffold_tour") -> bool:
    """True if the file on disk is byte-for-byte what a fresh build gives.

    With no path, every notebook in NOTEBOOKS is checked in NOTEBOOK_DIR.
    """
    if path is None:
        return all(check(NOTEBOOK_DIR / f"{n}.ipynb", n) for n in NOTEBOOKS)
    # Compare bytes, not text. read_text() turns "\r\n" and a lone "\r" into
    # "\n" on the way in, so a file with Windows line endings would look equal.
    return path.exists() and path.read_bytes() == render(name).encode("utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the notebooks from src/.")
    parser.add_argument("--check", action="store_true",
                        help="write nothing; exit 1 if the notebook on disk is out of date")
    args = parser.parse_args(argv)

    if args.check:
        stale = [n for n in NOTEBOOKS if not check(NOTEBOOK_DIR / f"{n}.ipynb", n)]
        if not stale:
            print(f"OK: {len(NOTEBOOKS)} notebooks in {NOTEBOOK_DIR} are in sync with src/")
            return 0
        print(f"OUT OF SYNC: {', '.join(stale)} differ from a fresh build "
              "(or do not exist). Run: uv run python tools/build_notebooks.py",
              file=sys.stderr)
        return 1

    NOTEBOOK_DIR.mkdir(parents=True, exist_ok=True)
    for n in NOTEBOOKS:
        path = NOTEBOOK_DIR / f"{n}.ipynb"
        path.write_text(render(n), encoding="utf-8")
        print("Wrote", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
