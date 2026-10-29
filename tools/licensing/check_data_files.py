"""Check that git tracks no raw vendor file and no oversized data file (owner decision 2026-10-29).

    uv run python tools/licensing/check_data_files.py

The repository commits the real data the app and the docs need, but never bulk raw files (ADR 0001 §7).
It reads what git tracks or has staged (the index, ``git ls-files -s``), not the folder on disk, so a staged
file is checked before the commit. A tracked path is refused when:

1. it lies in a raw or cache folder (``raw/``, ``cache/``, ``dolt_mirror``, ``.dolt/``, ``yfinance/``);
2. its name is a known raw download (``VIXCLS.csv``, ``DTB3.csv``, ``market_cap_*.csv``, a Kaggle
   ``*_eod_*.parquet`` chain);
3. it is a data file (``.parquet``, ``.csv``, ``.feather``, ``.arrow``) outside ``data/derived/`` and
   ``data/manual/``;
4. it is a data file (those, or a ``.json`` in a data folder) over ``DATA_LIMIT`` bytes, or any file over
   ``HARD_LIMIT`` bytes (the size of the staged blob);
5. its staged blob is a byte-for-byte copy of a local raw or cached vendor file under any name. Its git blob hash
   equals that file's ``git hash-object``. The files compared are the vendor downloads in
   ``$VOL_DATA_DIR/earnings-vol-study/raw/`` and the raw Dolt extracts in ``cache/dolt/``. The pipeline's own
   outputs, in ``cache/stage/`` and elsewhere, and the Dolt mirrors are not compared. Only files of a matching size are
   hashed, so this stays fast. Rule 5 is skipped when that folder is absent (CI), and a copy that was edited
   escapes it;
6. it is not on the allow-list of its folder (added after the milestone-2 review, claim 15b). This rule needs no
   local file, so it holds in CI too:

   - ``data/derived/`` holds only ``README.md``, ``LICENSE``, the milestone-0
     ``earnings_calendar_30_large_caps.json``, and ``<name>.parquet`` for a table the schema registry marks
     ``committed``. That staged blob must be a Parquet file whose columns are exactly those of the table's committed
     copy (``store.committed_schema``), in order;
   - ``app/public/data/`` holds only ``<kind>.json`` for a kind of the JSON contract (``contract.KINDS``), and its
     ``kind`` field must say that kind.

   So a raw ``option_chain`` month, re-serialised under any name, a local-only table (``market_daily``,
   ``chain_expiry``) or an unregistered table is refused;
7. it is a compressed archive (its last suffix is ``.gz``, ``.zip``, ``.bz2``, ``.xz``, ``.7z``, ``.tar``, ``.zst``
   or ``.tgz``, so ``x.csv.gz`` and ``x.tar.gz`` too), anywhere in the tree: no rule above can look inside one.

Rules 1, 2, 3 and 7 compare suffixes and folder names in lower case (``Raw/DTB3.CSV`` is refused). What still
passes: data under a suffix that is neither a table nor an archive, outside ``data/derived/`` and
``app/public/data/`` (a ``.txt``, ``.tsv``, ``.npy``, a notebook with data in its outputs); in ``data/manual/``, a
vendor file edited by one byte (rule 6 does not cover that folder); a raw table whose columns were renamed to those
of a registered one; and anything in git history. Only the index is read, and only when the tests run: there is no
commit hook.

Exit 0 clean, 1 something refused. ``tests/test_repo_data_files.py`` runs it on every test run.
"""

from __future__ import annotations

import fnmatch
import json
import os
import subprocess
import sys
from pathlib import Path, PurePosixPath

import pyarrow as pa
import pyarrow.parquet as pq

from earnings_vol import contract, schema, store

DATA_LIMIT = 10 * 1024 * 1024
HARD_LIMIT = 50 * 1024 * 1024
RAW_DIRS = ("raw", "cache", "dolt_mirror", ".dolt", "yfinance")
RAW_NAMES = ("vixcls.csv", "dtb3.csv", "market_cap_*.csv", "*_eod_*.parquet")
TABLE_SUFFIXES = (".parquet", ".csv", ".feather", ".arrow")
ARCHIVE_SUFFIXES = (".gz", ".zip", ".bz2", ".xz", ".7z", ".tar", ".zst", ".tgz")
DATA_DIRS = ("data/derived/", "data/manual/")
JSON_DATA_DIRS = DATA_DIRS + ("app/public/data/",)
DERIVED_DIR, APP_DATA_DIR = "data/derived/", "app/public/data/"
# Rule 6: the files data/derived/ may hold besides the committed tables.
DERIVED_OTHER = ("README.md", "LICENSE", "earnings_calendar_30_large_caps.json")
COMMITTED_TABLES = tuple(sorted(name for name, t in schema.REGISTRY.items() if t.committed))
REPO = Path(__file__).resolve().parents[2]


def _allowed_name(path: str) -> str | None:
    """Rule 6 by name: None if the path may be tracked, else why not."""
    if path.startswith(DERIVED_DIR):
        name = path[len(DERIVED_DIR):]
        if name in DERIVED_OTHER or (name.endswith(".parquet") and name[:-len(".parquet")] in COMMITTED_TABLES):
            return None
        return "not a file data/derived/ may hold (a committed table of the schema registry, README.md, LICENSE)"
    if path.startswith(APP_DATA_DIR):
        name = path[len(APP_DATA_DIR):]
        if name.endswith(".json") and name[:-len(".json")] in contract.KINDS:
            return None
        return f"not <kind>.json for a kind of the JSON contract {contract.KINDS}"
    return None


def problems(files: list[tuple[str, int]]) -> list[str]:
    """Rules 1 to 4, 6 by name and 7: messages for ``(path, size in bytes)`` pairs with ``/`` separators.

    A path gets at most one message from rules 1, 2, 7, 3 and 6 (the first that applies), plus one for its size.
    """
    out = []
    for path, size in files:
        p = PurePosixPath(path.lower())
        is_table = p.suffix in TABLE_SUFFIXES
        is_json_data = p.suffix == ".json" and path.startswith(JSON_DATA_DIRS)
        not_allowed = _allowed_name(path)
        if any(part in RAW_DIRS for part in p.parts[:-1]):
            out.append(f"{path}: in a raw or cache folder")
        elif any(fnmatch.fnmatchcase(p.name, pattern) for pattern in RAW_NAMES):
            out.append(f"{path}: a raw vendor download")
        elif p.suffix in ARCHIVE_SUFFIXES:
            out.append(f"{path}: a compressed archive")
        elif is_table and not path.startswith(DATA_DIRS):
            out.append(f"{path}: a data table outside data/derived/ and data/manual/")
        elif not_allowed:
            out.append(f"{path}: {not_allowed}")
        if size > HARD_LIMIT:
            out.append(f"{path}: {size} bytes, over the {HARD_LIMIT}-byte hard limit")
        elif (is_table or is_json_data) and size > DATA_LIMIT:
            out.append(f"{path}: {size} bytes, over the {DATA_LIMIT}-byte limit for a data file")
    return out


def tracked_blobs(repo: Path = REPO) -> list[tuple[str, str, int]]:
    """``(path, blob sha, blob size)`` for every path in the index: tracked files and staged changes."""
    listed = subprocess.run(["git", "ls-files", "-s", "-z"], cwd=repo, capture_output=True, check=True).stdout
    entries = []
    for record in listed.split(b"\0"):
        if not record:
            continue
        meta, path = record.split(b"\t", 1)
        mode, sha, _stage = meta.split()
        if mode != b"160000":  # skip submodules, which have no blob
            entries.append((path.decode(), sha.decode()))
    shas = "\n".join(sha for _, sha in entries) + "\n"
    sizes = subprocess.run(["git", "cat-file", "--batch-check=%(objectname) %(objectsize)"], cwd=repo,
                           input=shas.encode(), capture_output=True, check=True).stdout.decode().split("\n")
    size_of = {line.split()[0]: int(line.split()[1]) for line in sizes if line.strip() and "missing" not in line}
    return [(path, sha, size_of[sha]) for path, sha in entries]


def blob(repo: Path, sha: str) -> bytes:
    """The staged content of one blob (what a commit would hold, not the file on disk)."""
    return subprocess.run(["git", "cat-file", "blob", sha], cwd=repo, capture_output=True, check=True).stdout


def content_problems(blobs: list[tuple[str, str, int]], repo: Path = REPO) -> list[str]:
    """Rule 6 by content: a registered table's columns, an app file's kind (paths whose names rule 6 allows)."""
    out = []
    for path, sha, size in blobs:
        if size > DATA_LIMIT or _allowed_name(path) is not None:
            continue                           # refused already by rules 4 or 6
        if path.startswith(DERIVED_DIR) and path.endswith(".parquet"):
            name = path[len(DERIVED_DIR):-len(".parquet")]
            want = list(store.committed_schema(schema.REGISTRY[name]).names)
            try:
                got = pq.read_schema(pa.BufferReader(blob(repo, sha))).names
            except (pa.ArrowException, OSError, ValueError):
                out.append(f"{path}: not a readable Parquet file")
                continue
            if got != want:
                out.append(f"{path}: its columns {got} are not those of the committed {name} table {want}")
        elif path.startswith(APP_DATA_DIR):
            kind = path[len(APP_DATA_DIR):-len(".json")]
            try:
                got_kind = json.loads(blob(repo, sha)).get("kind")
            except (ValueError, AttributeError):
                out.append(f"{path}: not a JSON object")
                continue
            if got_kind != kind:
                out.append(f"{path}: its kind is {got_kind!r}, not {kind!r}")
    return out


VENDOR_SUBDIRS = ("raw", "cache/dolt")


def vendor_files(root: Path | None) -> list[Path]:
    """The vendor downloads (``raw/``) and the raw Dolt extracts (``cache/dolt/``) under ``root``."""
    if root is None or not root.is_dir():
        return []
    out = []
    for sub in VENDOR_SUBDIRS:
        for folder, _dirs, names in os.walk(root / sub):
            out.extend(Path(folder) / n for n in names)
    return out


def copies(blobs: list[tuple[str, str, int]], vendor: list[Path], repo: Path = REPO) -> list[str]:
    """Rule 5: tracked blobs that equal a vendor file byte for byte, whatever their name."""
    by_size: dict[int, list[tuple[str, str]]] = {}
    for path, sha, size in blobs:
        by_size.setdefault(size, []).append((path, sha))
    candidates = [f for f in vendor if f.stat().st_size in by_size]
    if not candidates:
        return []
    hashed = subprocess.run(["git", "hash-object", "--stdin-paths"], cwd=repo, capture_output=True, check=True,
                            input="\n".join(str(f) for f in candidates).encode()).stdout.decode().split()
    out = []
    for f, sha in zip(candidates, hashed):
        for path, blob_sha in by_size[f.stat().st_size]:
            if blob_sha == sha:
                out.append(f"{path}: a byte-for-byte copy of the local vendor file {f.name}")
    return out


def default_vendor_root() -> Path | None:
    base = Path(os.environ.get("VOL_DATA_DIR", "~/data/vol-projects")).expanduser() / "earnings-vol-study"
    return base if base.is_dir() else None


def check(repo: Path = REPO, vendor_root: Path | None = None) -> list[str]:
    blobs = tracked_blobs(repo)
    return (problems([(p, size) for p, _, size in blobs]) + content_problems(blobs, repo)
            + copies(blobs, vendor_files(vendor_root), repo))


def main() -> int:
    root = default_vendor_root()
    found = check(REPO, root)
    for line in found:
        print(line)
    note = "" if root else " (no local vendor folder, so rule 5 was skipped)"
    print(f"{len(found)} problem(s) in tracked files{note}" if found
          else f"clean: no raw vendor file and no oversized data file{note}")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
