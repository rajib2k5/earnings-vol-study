# =============================================================================
# store.py — Check a table against the schema registry, then write it.
#
# TWO DESTINATIONS
#   1. The stage cache, $VOL_DATA_DIR/earnings-vol-study/cache/stage/<hash>/.
#      Every column, class R included, plus a manifest (ADR 0001 §2): row
#      count, params_hash, Dolt commits, input hashes, code commit, write time.
#   2. data/derived/ in the repository (CC BY-SA 4.0). Only tables marked
#      committed. write_derived() drops every class-R column except those the
#      table names in keep_restricted (owner decision of 2026-10-29: real
#      Yahoo/Cboe/FRED values the app or the docs need may be committed), and
#      refuses any _yf or _cboe column that the registry did not call class R.
#
# IN MEMORY
#   A table is a pandas DataFrame whose columns are exactly the registry's, in
#   order. Dates are datetime.date objects (None for null), floats are float64
#   (NaN for null), and nullable integers are Python ints or None.
#
# A mismatch is an error, never a silent cast (ADR 0001 §2).
# =============================================================================

import hashlib
import json
import math
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from earnings_vol.schema import Table, has_restricted_suffix

ROOT = Path(__file__).resolve().parents[2]

_INT_RANGE = {"int16": (-(2**15), 2**15 - 1), "int32": (-(2**31), 2**31 - 1)}
_ARROW = {
    "string": pa.string(), "date32": pa.date32(), "int16": pa.int16(), "int32": pa.int32(),
    "float64": pa.float64(), "bool": pa.bool_(),
}


class SchemaError(ValueError):
    """A table does not match its entry in the schema registry."""


def _is_null(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v)) or v is pd.NA or v is pd.NaT


def _type_ok(v, dtype: str) -> bool:
    if dtype in ("string", "enum"):
        return isinstance(v, str)
    if dtype == "date32":
        # datetime is a subclass of date: a time of day would be lost, so refuse it.
        return isinstance(v, date) and not isinstance(v, datetime)
    if dtype in _INT_RANGE:
        return isinstance(v, (int, np.integer)) and not isinstance(v, (bool, np.bool_))
    if dtype == "float64":
        return isinstance(v, (float, np.floating)) and math.isfinite(v)
    if dtype == "bool":
        return isinstance(v, (bool, np.bool_))
    raise AssertionError(dtype)  # pragma: no cover - the registry allows no other dtype


def validate(df: pd.DataFrame, table: Table) -> None:
    """Raise SchemaError naming every rule `df` breaks; return None if it fits."""
    if tuple(df.columns) != table.names:
        raise SchemaError(f"{table.name}: columns {list(df.columns)} != registry {list(table.names)}")
    problems = []
    for col in table.columns:
        values = df[col.name].tolist()
        nulls = [i for i, v in enumerate(values) if _is_null(v)]
        if nulls and not col.nullable:
            problems.append(f"{col.name}: {len(nulls)} null(s) in a NOT NULL column (first row {nulls[0]})")
        bad = [v for v in values if not _is_null(v) and not _type_ok(v, col.dtype)]
        if bad:
            problems.append(f"{col.name}: {len(bad)} value(s) are not {col.dtype}, e.g. {bad[0]!r}")
            continue
        if col.dtype in _INT_RANGE:
            lo, hi = _INT_RANGE[col.dtype]
            out = [v for v in values if not _is_null(v) and not lo <= int(v) <= hi]
            if out:
                problems.append(f"{col.name}: {out[0]} is outside {col.dtype}")
        if col.dtype == "enum":
            unknown = sorted({v for v in values if not _is_null(v)} - set(col.enum))
            if unknown:
                problems.append(f"{col.name}: values {unknown} are not in {list(col.enum)}")
    for key in (table.primary_key, *table.unique):
        if key and df.duplicated(list(key)).any():
            dup = df[df.duplicated(list(key), keep=False)][list(key)].head(2).values.tolist()
            problems.append(f"key {key} is not unique, e.g. {dup}")
    if problems:
        raise SchemaError(f"{table.name}: " + "; ".join(problems))


def to_arrow(df: pd.DataFrame, table: Table) -> pa.Table:
    """Validate, then build the Arrow table with exactly the registry's types."""
    validate(df, table)
    arrays, fields = [], []
    for col in table.columns:
        values = [None if _is_null(v) else v for v in df[col.name].tolist()]
        if col.dtype == "enum":
            arr = pa.array(values, type=pa.string()).dictionary_encode()
        elif col.dtype in _INT_RANGE:
            arr = pa.array([None if v is None else int(v) for v in values], type=_ARROW[col.dtype])
        elif col.dtype == "bool":
            arr = pa.array([None if v is None else bool(v) for v in values], type=pa.bool_())
        elif col.dtype == "float64":
            arr = pa.array([None if v is None else float(v) for v in values], type=pa.float64())
        else:
            arr = pa.array(values, type=_ARROW[col.dtype])
        arrays.append(arr)
        fields.append(pa.field(col.name, arr.type, nullable=col.nullable))
    return pa.Table.from_arrays(arrays, schema=pa.schema(fields))


def from_arrow(tbl: pa.Table, table: Table) -> pd.DataFrame:
    """Turn a stored Arrow table back into the in-memory form, then validate it."""
    df = tbl.to_pandas(date_as_object=True, integer_object_nulls=True)
    for col in table.columns:
        if col.dtype in ("enum", "string"):
            df[col.name] = pd.Series([None if _is_null(v) else str(v) for v in df[col.name]],
                                     dtype=object, index=df.index)
        elif col.dtype == "float64":
            df[col.name] = df[col.name].astype("float64")
    validate(df, table)
    return df


def code_commit() -> str:
    """git HEAD, with "-dirty" when the working tree has changes; "uncommitted" without git."""
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True,
                               text=True, check=True).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "uncommitted"
    return f"{head}-dirty" if dirty else head


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_table(df: pd.DataFrame, table: Table, path: Path, *, params_hash: str,
                dolt_commits: dict, inputs: dict[str, str] | None = None,
                extra: dict | None = None, now: datetime | None = None) -> Path:
    """Write `df` to `path` (Parquet, zstd) and its manifest beside it.

    `inputs` maps an input's name to its SHA-256. `now` is the write time
    (UTC); a test passes a fixed one.
    """
    arrow = to_arrow(df, table)
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(arrow, path, compression="zstd")
    when = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    manifest = {
        "table": table.name,
        "rows": len(df),
        "params_hash": params_hash,
        "dolt_commits": dict(dolt_commits),
        "inputs": dict(sorted((inputs or {}).items())),
        "code_commit": code_commit(),
        "written_utc": when.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sha256": sha256_file(path),
        **(extra or {}),
    }
    manifest_path(path).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def manifest_path(path: Path) -> Path:
    return path.with_name(path.name.replace(".parquet", "") + ".manifest.json")


def read_table(path: Path, table: Table) -> pd.DataFrame:
    return from_arrow(pq.read_table(path), table)


def committed_schema(table: Table) -> Table:
    """The registry entry of the committed copy: the class-R columns removed, except those
    named in table.keep_restricted.

    Refuses a table that is not marked committed, and refuses any column that
    ends in _yf/_cboe but is not class R (a suffixed column that the registry
    forgot to call class R).
    """
    if not table.committed:
        raise SchemaError(f"{table.name} is local only (data model: Committed: no)")
    stray = [c.name for c in table.columns if c.licence != "R" and has_restricted_suffix(c.name)]
    if stray:
        raise SchemaError(f"{table.name}: {stray} end in _yf/_cboe but are not class R")
    keep = tuple(c for c in table.columns if c.licence != "R" or c.name in table.keep_restricted)
    return Table(table.name, keep, committed=True, unique=table.unique, keep_restricted=table.keep_restricted)


def committable(df: pd.DataFrame, table: Table) -> tuple[pd.DataFrame, Table]:
    """The part of a table that may be committed (committed_schema), and its schema."""
    sub = committed_schema(table)
    return df[list(sub.names)].reset_index(drop=True), sub


def write_derived(df: pd.DataFrame, table: Table, dest_dir: Path) -> Path:
    """Write the committable part of a table to data/derived/<name>.parquet.

    No manifest with a clock time is written here: the same data gives the
    same bytes, so a git diff shows only real changes.
    """
    sub_df, sub = committable(df, table)
    arrow = to_arrow(sub_df, sub)
    out = dest_dir / f"{table.name}.parquet"
    dest_dir.mkdir(parents=True, exist_ok=True)
    pq.write_table(arrow, out, compression="zstd")
    return out
