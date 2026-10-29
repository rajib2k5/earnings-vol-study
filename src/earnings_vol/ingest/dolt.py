# =============================================================================
# dolt.py — Read the DoltHub data with the `dolt sql` command line, read-only.
#
# WHAT WE FOUND AT MILESTONE 1 (and why this file has a "mirror")
#   ADR 0001 §3 planned to run `dolt sql` inside the shared clones under
#   ~/data/vol-projects/dolthub/. Measured on 2026-10-29 with dolt 2.6.1, on a
#   private copy: even a pure `SELECT HASHOF('HEAD')` rewrites four files
#   under .dolt/ (noms/manifest, noms/journal.idx, the chunk journal and the
#   stats database). Their bytes stay the same, but their modification times
#   change, so the fingerprint guard trips. ADR 0001's rule for that case is
#   "switch to a private copy at once". So:
#
#     1. refresh_mirror() copies a shared clone into our own cache folder,
#        cache/dolt_mirror/<repo>/, and proves with a stat fingerprint (path,
#        size, mtime) that the shared clone did not change during the copy.
#        It never runs dolt inside the shared clone.
#     2. Every query runs in the mirror, pinned with AS OF '<commit>'.
#     3. guard() checks, around each batch, that the shared clone is untouched
#        (stat fingerprint) and that the mirror's data files kept their bytes
#        (content fingerprint: dolt touches mtimes there, which is harmless).
#
# THE THREE GUARDS OF ADR 0001 §3
#   1. Statement allowlist: check_statement() refuses anything but one
#      SELECT/WITH/SHOW/DESCRIBE statement.
#   2. Commit pinning: as_of() writes `table AS OF '<hash>'` with a checked hash.
#   3. Fingerprints: guard(), above.
#   And never `dolt sql-server`, which writes lock and info files.
#
# OUTPUT FORMAT
#   `dolt sql -r parquet` works on dolt 2.6.1 (measured 2026-10-29): dates come
#   back as timestamps, decimals as decimals, and SQL NULL as a real null. So
#   the CSV sentinel of ADR 0001 §3 is not needed. normalise() turns the types
#   into ours: date32 and float64.
# =============================================================================

import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from contextlib import contextmanager
from datetime import date
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

DOLT = os.environ.get("DOLT_BIN", "dolt")

# --- guard 1: the statement allowlist ------------------------------------------

_ALLOWED_START = ("SELECT", "WITH", "SHOW", "DESCRIBE")
# Whole words that may never appear anywhere in a query, even inside a string.
# Refusing a harmless literal now and then is the price of not parsing SQL.
_FORBIDDEN_WORDS = (
    "INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "DROP", "ALTER", "TRUNCATE", "RENAME",
    "GRANT", "REVOKE", "CALL", "SET", "LOCK", "UNLOCK", "LOAD", "HANDLER", "DO", "KILL",
    "START", "BEGIN", "COMMIT", "ROLLBACK", "SAVEPOINT", "USE", "INTO", "OUTFILE", "DUMPFILE",
    "MERGE", "RESET", "PREPARE", "EXECUTE", "DEALLOCATE", "ANALYZE", "OPTIMIZE", "FLUSH",
)
_FORBIDDEN_RE = re.compile(r"\b(" + "|".join(_FORBIDDEN_WORDS) + r")\b", re.IGNORECASE)
# A dolt_* name followed by "(" is a stored procedure or function call
# (dolt_commit(), dolt_gc(), ...). A dolt_* name without "(" is a system
# table such as dolt_log, which may be read.
_DOLT_CALL_RE = re.compile(r"\bdolt_\w+\s*\(", re.IGNORECASE)
_COMMIT_RE = re.compile(r"^[0-9a-v]{32}$")


class UnsafeQueryError(ValueError):
    """The query is not a single read-only statement."""


class DoltWriteError(RuntimeError):
    """A fingerprint changed: something wrote into a Dolt folder."""


def check_statement(sql: str) -> str:
    """Return `sql` stripped if it is one read-only statement; raise otherwise."""
    if not isinstance(sql, str) or not sql.strip():
        raise UnsafeQueryError("empty query")
    text = sql.strip()
    if ";" in text:
        raise UnsafeQueryError("a semicolon is refused: one statement per query")
    if "--" in text or "#" in text or "/*" in text:
        raise UnsafeQueryError("comments are refused: they can hide a second statement")
    first = text.split(None, 1)[0].upper()
    if first not in _ALLOWED_START:
        raise UnsafeQueryError(f"query must start with one of {_ALLOWED_START}, got {first!r}")
    if m := _FORBIDDEN_RE.search(text):
        raise UnsafeQueryError(f"forbidden word {m.group(1)!r}")
    if m := _DOLT_CALL_RE.search(text):
        raise UnsafeQueryError(f"dolt procedure or function call refused: {m.group(0)!r}")
    return text


# --- guard 2: commit pinning ----------------------------------------------------

def check_commit(commit: str) -> str:
    """A Dolt commit hash is 32 characters of 0-9 and a-v (base32)."""
    if not isinstance(commit, str) or not _COMMIT_RE.fullmatch(commit):
        raise ValueError(f"not a Dolt commit hash: {commit!r}")
    return commit


def as_of(table: str, commit: str) -> str:
    """`table` AS OF '<commit>', for the FROM clause of a pinned query."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table):
        raise ValueError(f"not a table name: {table!r}")
    return f"`{table}` AS OF '{check_commit(commit)}'"


def sql_list(values) -> str:
    """('A','B') for an IN clause. Only ticker-like strings are accepted."""
    out = []
    for v in values:
        if not re.fullmatch(r"[A-Za-z0-9.\-]{1,16}", v):
            raise ValueError(f"refusing to quote {v!r}")
        out.append(f"'{v}'")
    if not out:
        raise ValueError("empty IN list")
    return "(" + ",".join(out) + ")"


# --- guard 3: fingerprints ------------------------------------------------------

def stat_fingerprint(repo: Path) -> dict[str, tuple[int, int]]:
    """{relative path: (size, mtime_ns)} for everything under repo/, the clone
    folder itself and .dolt/ alike.

    Its keys are the set of file names, so a file added anywhere in the clone
    (beside .dolt/ too: the milestone-1 review found that blind spot) or
    removed from it is a difference, as is any touched file or folder.
    """
    root = Path(repo)
    out = {".": (0, root.stat().st_mtime_ns)}
    for p in sorted(root.rglob("*")):
        st = p.stat()
        out[str(p.relative_to(root))] = (st.st_size if p.is_file() else 0, st.st_mtime_ns)
    return out


# Files whose bytes are hashed in the content fingerprint. stats/ and temptf/
# are dolt's own scratch space.
#
# KNOWN BLIND SPOT (milestone-1 review, claim 1b): the large table files under
# noms/ are fingerprinted by path and size only, not hashed. They are
# content-addressed (the name is the hash of the bytes dolt wrote), so dolt
# itself never changes one in place; but a same-size change to one by anything
# else would go unseen. Hashing them would read the whole mirror (about 10 GB)
# around every batch, which is too slow. The shared clone does not depend on
# this: its stat fingerprint sees any write there, whatever the size.
_HASHED = ("noms/manifest", "noms/journal.idx", "repo_state.json", "config.json")
_JOURNAL = "noms/vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv"


def content_fingerprint(repo: Path) -> dict[str, tuple[int, str]]:
    """{relative path: (size, sha256 or "")} for the data files under repo/.dolt/."""
    root = Path(repo) / ".dolt"
    out = {}
    for p in sorted(root.rglob("*")):
        rel = str(p.relative_to(root))
        if not p.is_file() or rel.startswith(("stats/", "temptf/")):
            continue
        digest = ""
        if rel in _HASHED or rel == _JOURNAL:
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
        out[rel] = (p.stat().st_size, digest)
    return out


def diff_fingerprints(before: dict, after: dict) -> list[str]:
    """The paths that were added, removed or changed between two fingerprints."""
    return sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))


@contextmanager
def guard(shared: Path, mirror: Path):
    """Fail loudly if the shared clone changed at all, or the mirror's data did."""
    shared_before, mirror_before = stat_fingerprint(shared), content_fingerprint(mirror)
    yield
    changed_shared = diff_fingerprints(shared_before, stat_fingerprint(shared))
    changed_mirror = diff_fingerprints(mirror_before, content_fingerprint(mirror))
    if changed_shared:
        raise DoltWriteError(f"the shared clone {shared} changed during the batch: {changed_shared[:10]}")
    if changed_mirror:
        raise DoltWriteError(f"the mirror {mirror} data changed during the batch: {changed_mirror[:10]}")


def refresh_mirror(shared: Path, mirror: Path) -> bool:
    """Make `mirror` a byte-for-byte copy of the shared clone. True if it copied.

    The copy is skipped when the mirror already holds the same data files.
    Otherwise the shared clone is copied to a temporary folder next to the
    mirror, and the copy is kept only if the shared clone's stat fingerprint
    is the same before and after: a `dolt pull` by the hub in the middle of the
    copy would mix two versions.
    """
    shared, mirror = Path(shared), Path(mirror)
    if (mirror / ".dolt").is_dir() and content_fingerprint(mirror) == content_fingerprint(shared):
        return False
    tmp = mirror.with_name(mirror.name + ".copying")
    if tmp.exists():
        shutil.rmtree(tmp)
    before = stat_fingerprint(shared)
    shutil.copytree(shared, tmp, symlinks=True)
    changed = diff_fingerprints(before, stat_fingerprint(shared))
    if changed:
        shutil.rmtree(tmp)
        raise DoltWriteError(f"{shared} changed while it was being copied: {changed[:10]}")
    if content_fingerprint(tmp) != content_fingerprint(shared):
        shutil.rmtree(tmp)
        raise DoltWriteError(f"the copy of {shared} does not match it")
    if mirror.exists():
        shutil.rmtree(mirror)
    tmp.rename(mirror)
    return True


# --- running a query ------------------------------------------------------------

def query(repo: Path, sql: str) -> pa.Table:
    """Run one checked, read-only statement in `repo` and return it typed.

    `repo` must be a mirror, never the shared clone (see the header).
    --disable-auto-gc stops dolt from garbage-collecting the store as a side
    effect of the session.
    """
    text = check_statement(sql)
    proc = subprocess.run([DOLT, "sql", "--disable-auto-gc", "-r", "parquet", "-q", text],
                          cwd=repo, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"dolt sql failed ({proc.returncode}): {proc.stderr.decode(errors='replace')[:500]}")
    # use_threads=False: on this machine (aarch64, pyarrow 26) reading a 0-row
    # Parquet buffer with threads crashes the interpreter at exit.
    return normalise(pq.read_table(pa.BufferReader(proc.stdout), use_threads=False))


# Bumped whenever normalise() changes, so cached extracts made by an older
# version are queried again (extract_months compares it).
NORMALISE_VERSION = 2


def normalise(tbl: pa.Table) -> pa.Table:
    """Dolt's Parquet types to ours: timestamp -> date32, decimal -> float64.

    A decimal goes through its text form: pyarrow's direct decimal-to-float
    cast is not correctly rounded (decimal(5,4) 0.2678 became
    0.26780000000000004, measured 2026-10-29), while parsing "0.2678" gives the
    float nearest to it.

    Dolt returns a DATE column as a timestamp at midnight. A timestamp with a
    time of day is refused, not truncated: casting 2026-10-24T01:00 to a date
    would silently drop the hour (milestone-1 review, claim 9).
    """
    cols, fields = [], []
    for f, col in zip(tbl.schema, tbl.columns):
        if pa.types.is_timestamp(f.type):
            # all() skips nulls: False only if some value is not at midnight.
            if pc.all(pc.equal(col, pc.floor_temporal(col, unit="day"))).as_py() is False:
                raise ValueError(f"column {f.name!r} holds a time of day; only midnight timestamps "
                                 f"(Dolt DATE values) can become dates")
            col = pc.cast(col, pa.date32())
        elif pa.types.is_decimal(f.type):
            col = pc.cast(pc.cast(col, pa.string()), pa.float64())
        cols.append(col)
        fields.append(pa.field(f.name, col.type))
    return pa.Table.from_arrays(cols, schema=pa.schema(fields))


def head(repo: Path) -> str:
    return query(repo, "SELECT HASHOF('HEAD') AS h").column("h")[0].as_py()


def commit_exists(repo: Path, commit: str) -> bool:
    sql = f"SELECT COUNT(*) AS n FROM dolt_log WHERE commit_hash = '{check_commit(commit)}'"
    return query(repo, sql).column("n")[0].as_py() == 1


# --- monthly extracts with a cache ----------------------------------------------

def month_starts(first: date, last: date) -> list[date]:
    """The first day of every month from first's month to last's month."""
    out, y, m = [], first.year, first.month
    while (y, m) <= (last.year, last.month):
        out.append(date(y, m, 1))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def month_end(start: date) -> date:
    nxt = date(start.year + 1, 1, 1) if start.month == 12 else date(start.year, start.month + 1, 1)
    return date.fromordinal(nxt.toordinal() - 1)


def extract_months(repo: Path, table: str, columns: list[str], symbols: list[str], commit: str,
                   first: date, last: date, out_dir: Path, log=print) -> list[dict]:
    """Extract `table` for `symbols`, one query per calendar month, into out_dir.

    One file per month, <yyyy-mm>.parquet, with a manifest beside it. A month
    whose file exists for the same commit and symbol set is not queried again.
    The query filters on `date` first, the leading primary-key column. Returns
    one record per month: rows, seconds, cached or not.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    symbol_key = hashlib.sha256(",".join(sorted(symbols)).encode()).hexdigest()[:16]
    cols = ", ".join(f"`{c}`" for c in columns)
    records = []
    for start in month_starts(first, last):
        end = min(month_end(start), last)
        path = out_dir / f"{start:%Y-%m}.parquet"
        man = path.with_suffix(".manifest.json")
        if path.exists() and man.exists():
            meta = json.loads(man.read_text())
            if (meta.get("commit") == commit and meta.get("symbol_key") == symbol_key
                    and meta.get("last") == str(end) and meta.get("normalise") == NORMALISE_VERSION):
                records.append({**meta, "cached": True})
                continue
        sql = (f"SELECT {cols} FROM {as_of(table, commit)} "
               f"WHERE `date` BETWEEN '{start}' AND '{end}' AND act_symbol IN {sql_list(symbols)}")
        t0 = time.perf_counter()
        tbl = query(repo, sql)
        seconds = round(time.perf_counter() - t0, 2)
        pq.write_table(tbl, path, compression="zstd")
        meta = {"table": table, "commit": commit, "first": str(start), "last": str(end),
                "symbol_key": symbol_key, "n_symbols": len(symbols), "rows": tbl.num_rows,
                "normalise": NORMALISE_VERSION,
                "seconds": seconds, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        man.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")
        log(f"{table} {start:%Y-%m}: {tbl.num_rows} rows in {seconds} s")
        records.append({**meta, "cached": False})
    return records
