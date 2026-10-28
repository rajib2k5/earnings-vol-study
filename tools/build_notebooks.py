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
#   notebooks/00_scaffold_tour.ipynb
# =============================================================================

import argparse
import sys
from pathlib import Path

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

from earnings_vol import __version__, contract

ROOT = Path(__file__).resolve().parent.parent
NOTEBOOK_PATH = ROOT / "notebooks" / "00_scaffold_tour.ipynb"


def build_notebook() -> nbformat.NotebookNode:
    nb = new_notebook(metadata={
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    })
    # nbformat 4.5 requires every cell to have an id. By default nbformat makes
    # a random id, which would change the bytes on every build. We set the ids
    # ourselves, below.
    nb.nbformat_minor = 5
    nb.cells = [
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
    ]
    for i, cell in enumerate(nb.cells):
        cell["id"] = f"cell-{i:02d}"
    nbformat.validate(nb)
    return nb


def render() -> str:
    """Return the notebook as the exact text that we write to disk."""
    text = nbformat.writes(build_notebook())
    return text if text.endswith("\n") else text + "\n"


def check(path: Path | None = None) -> bool:
    """True if the file on disk is byte-for-byte what a fresh build gives."""
    path = NOTEBOOK_PATH if path is None else path
    # Compare bytes, not text. read_text() turns "\r\n" and a lone "\r" into
    # "\n" on the way in, so a file with Windows line endings would look equal.
    return path.exists() and path.read_bytes() == render().encode("utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the notebooks from src/.")
    parser.add_argument("--check", action="store_true",
                        help="write nothing; exit 1 if the notebook on disk is out of date")
    args = parser.parse_args(argv)

    if args.check:
        if check():
            print(f"OK: {NOTEBOOK_PATH} is in sync with src/")
            return 0
        print(f"OUT OF SYNC: {NOTEBOOK_PATH} differs from a fresh build "
              "(or does not exist). Run: uv run python tools/build_notebooks.py",
              file=sys.stderr)
        return 1

    NOTEBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
    NOTEBOOK_PATH.write_text(render(), encoding="utf-8")
    print("Wrote", NOTEBOOK_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
