# Tests for src/earnings_vol/ingest/dolt.py: the three read-only guards of
# ADR 0001 §3, the mirror, the Parquet types and the monthly cache.
#
# Unit tests use fake folders and a fake query. Tests marked `dolt` run the
# real dolt binary: on a throw-away repository made with `dolt init` in
# tmp_path (with metrics off and a private DOLT_ROOT_PATH, so no network and no
# change to ~/.dolt), and, if the shared clones and the mirror exist, one real
# SELECT on the mirror. They are skipped when dolt is not installed.
#
# Mutations this module must catch (applied by hand, each seen to fail):
#   - check_statement without the forbidden-word scan
#   - check_statement accepting a trailing semicolon
#   - guard() comparing only the mirror (shared-clone changes missed)
#   - content_fingerprint hashing nothing (a changed manifest missed)
#   - extract_months ignoring the cache
#   - normalise() casting decimals directly to float (not correctly rounded)
#   - normalise() truncating a timestamp with a time of day to its date
#   - stat_fingerprint covering .dolt/ only (a file beside it missed)

import json
import os
import shutil
import subprocess
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pyarrow as pa
import pytest

from earnings_vol import config
from earnings_vol.ingest import dolt

HAS_DOLT = shutil.which(dolt.DOLT) is not None


@pytest.mark.parametrize("sql", [
    "SELECT * FROM t",
    "  select act_symbol, `date`, `when` FROM earnings_calendar AS OF 'abc' WHERE `date` > '2024-01-01'  ",
    "WITH x AS (SELECT 1 AS a) SELECT a FROM x",
    "SHOW TABLES",
    "DESCRIBE option_chain",
    "SELECT commit_hash FROM dolt_log",          # a dolt_* system TABLE may be read
    "SELECT HASHOF('HEAD') AS h",
])
def test_allowlist_accepts_read_only_statements(sql):
    assert dolt.check_statement(sql) == sql.strip()


@pytest.mark.parametrize("sql, why", [
    ("", "empty"),
    ("SELECT 1; DROP TABLE t", "semicolon"),
    ("SELECT 1;", "semicolon"),
    ("DELETE FROM t", "must start"),
    ("CALL dolt_commit('-m', 'x')", "must start"),
    ("SELECT dolt_commit('-am', 'x')", "dolt procedure"),
    ("SELECT DOLT_GC ()", "dolt procedure"),
    ("SELECT 1 -- DROP TABLE t", "comments"),
    ("SELECT 1 /* x */", "comments"),
    ("SELECT 1 # x", "comments"),
    ("SELECT * INTO OUTFILE '/tmp/x' FROM t", "INTO"),
    ("WITH x AS (SELECT 1) UPDATE t SET a = 1", "UPDATE"),
    ("SELECT 1 FROM t WHERE 1 = 1 UNION SELECT 1 FROM t FOR UPDATE", "UPDATE"),
    ("SHOW TABLES LOCK", "LOCK"),
    ("select * from t where x = 'a' and set_config()", None),   # 'set_config' is not the word SET: allowed
])
def test_allowlist_refuses_hostile_statements(sql, why):
    if why is None:
        dolt.check_statement(sql)
        return
    with pytest.raises(dolt.UnsafeQueryError, match=why):
        dolt.check_statement(sql)


def test_as_of_and_commit_checks():
    c = "fjrb6h5le9h1qiif2j4pl6cpaas7pnee"
    assert dolt.as_of("earnings_calendar", c) == f"`earnings_calendar` AS OF '{c}'"
    for bad in ("HEAD", "master", c[:-1], c + "x", "' OR 1=1 --".ljust(32, "a"), c.upper()):
        with pytest.raises(ValueError):
            dolt.as_of("earnings_calendar", bad)
    with pytest.raises(ValueError):
        dolt.as_of("t; DROP", c)


def test_sql_list_quotes_tickers_only():
    assert dolt.sql_list(["AAPL", "BRK.B"]) == "('AAPL','BRK.B')"
    for bad in (["A'B"], ["x) OR (1=1"], []):
        with pytest.raises(ValueError):
            dolt.sql_list(bad)


def fake_repo(root: Path) -> Path:
    (root / ".dolt" / "noms").mkdir(parents=True)
    (root / ".dolt" / "noms" / "manifest").write_bytes(b"manifest-v1")
    (root / ".dolt" / "noms" / "abcdef0123456789abcdef0123456789").write_bytes(b"x" * 100)
    (root / ".dolt" / "repo_state.json").write_text("{}")
    return root


def test_stat_fingerprint_sees_a_touch_but_content_does_not(tmp_path):
    repo = fake_repo(tmp_path / "r")
    s0, c0 = dolt.stat_fingerprint(repo), dolt.content_fingerprint(repo)
    m = repo / ".dolt" / "noms" / "manifest"
    st = m.stat()
    os.utime(m, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))   # same bytes, later mtime
    assert dolt.diff_fingerprints(s0, dolt.stat_fingerprint(repo)) == [".dolt/noms/manifest"]
    assert dolt.content_fingerprint(repo) == c0
    m.write_bytes(b"manifest-v2")                                       # same size, new bytes
    assert dolt.diff_fingerprints(c0, dolt.content_fingerprint(repo)) == ["noms/manifest"]


def test_guard_stops_on_a_change_in_either_folder(tmp_path):
    shared, mirror = fake_repo(tmp_path / "shared"), fake_repo(tmp_path / "mirror")
    with dolt.guard(shared, mirror):
        pass                                                            # nothing changed: no error
    with pytest.raises(dolt.DoltWriteError, match="shared clone"):
        with dolt.guard(shared, mirror):
            (shared / ".dolt" / "new_file").write_text("written")
    with pytest.raises(dolt.DoltWriteError, match="mirror"):
        with dolt.guard(shared, mirror):
            (mirror / ".dolt" / "noms" / "manifest").write_bytes(b"other")


def test_the_shared_clone_fingerprint_sees_a_new_file_anywhere_in_the_clone(tmp_path):
    # The review's blind spot: a file created next to .dolt/, outside it.
    shared, mirror = fake_repo(tmp_path / "shared"), fake_repo(tmp_path / "mirror")
    s0 = dolt.stat_fingerprint(shared)
    (shared / "stray.txt").write_text("x")
    assert "stray.txt" in dolt.diff_fingerprints(s0, dolt.stat_fingerprint(shared))
    (shared / "stray.txt").unlink()
    with pytest.raises(dolt.DoltWriteError, match="shared clone"):
        with dolt.guard(shared, mirror):
            (shared / "beside_dolt.json").write_text("{}")


def test_refresh_mirror_copies_once_and_then_reuses(tmp_path):
    shared = fake_repo(tmp_path / "shared")
    mirror = tmp_path / "cache" / "mirror"
    mirror.parent.mkdir()
    assert dolt.refresh_mirror(shared, mirror) is True
    assert (mirror / ".dolt" / "noms" / "manifest").read_bytes() == b"manifest-v1"
    assert dolt.refresh_mirror(shared, mirror) is False                 # already current
    (shared / ".dolt" / "noms" / "manifest").write_bytes(b"manifest-v2")  # the hub pulled
    assert dolt.refresh_mirror(shared, mirror) is True
    assert (mirror / ".dolt" / "noms" / "manifest").read_bytes() == b"manifest-v2"
    assert not (tmp_path / "cache" / "mirror.copying").exists()


def test_normalise_turns_dolt_types_into_ours():
    tbl = pa.table({
        "date": pa.array([pa.scalar(1792800000000000, pa.timestamp("us")).as_py()], pa.timestamp("us")),
        "iv": pa.array([Decimal("0.2678")], pa.decimal128(5, 4)),
        "when": pa.array([None], pa.string()),
    })
    out = dolt.normalise(tbl)
    assert out.schema.field("date").type == pa.date32()
    assert out.schema.field("iv").type == pa.float64() and out.column("iv")[0].as_py() == 0.2678
    assert out.column("when")[0].as_py() is None                        # a real null, no sentinel


def test_normalise_refuses_a_timestamp_with_a_time_of_day():
    # 2026-10-24T00:00 is a Dolt DATE and becomes a date; 2026-10-24T01:00 would lose its hour.
    midnight = pa.array([datetime(2026, 10, 24), None], pa.timestamp("us"))
    assert dolt.normalise(pa.table({"d": midnight})).column("d").to_pylist() == [date(2026, 10, 24), None]
    for t in (datetime(2026, 10, 24, 1, 0), datetime(2026, 10, 24, 0, 0, 0, 1)):
        with pytest.raises(ValueError, match="time of day"):
            dolt.normalise(pa.table({"d": pa.array([datetime(2026, 10, 23), t], pa.timestamp("us"))}))


def test_month_helpers():
    assert dolt.month_starts(date(2024, 11, 15), date(2025, 2, 1)) == \
        [date(2024, 11, 1), date(2024, 12, 1), date(2025, 1, 1), date(2025, 2, 1)]
    assert dolt.month_end(date(2024, 2, 1)) == date(2024, 2, 29)        # leap year
    assert dolt.month_end(date(2024, 12, 1)) == date(2024, 12, 31)


def test_extract_months_queries_each_month_once(monkeypatch, tmp_path):
    calls = []

    def fake_query(repo, sql):
        calls.append(sql)
        return pa.table({"date": pa.array([date(2025, 1, 2)], pa.date32()), "act_symbol": ["AAPL"]})

    monkeypatch.setattr(dolt, "query", fake_query)
    c = "fjrb6h5le9h1qiif2j4pl6cpaas7pnee"
    args = (tmp_path, "option_chain", ["date", "act_symbol"], ["AAPL"], c, date(2025, 1, 1), date(2025, 2, 10),
            tmp_path / "out")
    rec = dolt.extract_months(*args, log=lambda *_: None)
    assert [r["cached"] for r in rec] == [False, False] and len(calls) == 2
    # The query filters on date FIRST (the leading key) and is pinned with AS OF.
    assert "AS OF '" + c + "'" in calls[0] and "WHERE `date` BETWEEN '2025-01-01' AND '2025-01-31'" in calls[0]
    assert "BETWEEN '2025-02-01' AND '2025-02-10'" in calls[1]           # the last month stops at `last`
    rec2 = dolt.extract_months(*args, log=lambda *_: None)
    assert [r["cached"] for r in rec2] == [True, True] and len(calls) == 2
    # Another symbol set is another extract.
    dolt.extract_months(tmp_path, "option_chain", ["date"], ["AAPL", "MSFT"], c, date(2025, 1, 1),
                        date(2025, 1, 31), tmp_path / "out", log=lambda *_: None)
    assert len(calls) == 3


# --- the real dolt binary ---------------------------------------------------------

def dolt_env(tmp_path: Path) -> dict:
    root = tmp_path / "dolt_root"
    (root / ".dolt").mkdir(parents=True, exist_ok=True)
    (root / ".dolt" / "config_global.json").write_text(json.dumps({
        "metrics.disabled": "true", "user.name": "test", "user.email": "test@localhost"}))
    return {**os.environ, "DOLT_ROOT_PATH": str(root), "DOLT_DISABLE_EVENT_FLUSH": "1"}


@pytest.mark.dolt
@pytest.mark.skipif(not HAS_DOLT, reason="dolt is not installed")
def test_a_pure_select_touches_files_but_keeps_their_bytes(tmp_path, monkeypatch):
    # The milestone-1 finding, reproduced on a throw-away repository: dolt sql
    # rewrites files under .dolt/ on a SELECT. Their bytes stay the same, so the
    # mirror's content fingerprint holds while a stat fingerprint would trip.
    env = dolt_env(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    run = lambda *a: subprocess.run([dolt.DOLT, *a], cwd=repo, env=env, check=True, capture_output=True)  # noqa: E731
    run("init")
    run("sql", "-q", "CREATE TABLE t (d date primary key, v decimal(5,2)); INSERT INTO t VALUES ('2025-10-30', 1.25)")
    run("add", ".")
    run("commit", "-m", "fixture")
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    commit = dolt.head(repo)
    stat0, content0 = dolt.stat_fingerprint(repo), dolt.content_fingerprint(repo)
    out = dolt.query(repo, f"SELECT d, v FROM {dolt.as_of('t', commit)}")
    assert out.column("d")[0].as_py() == date(2025, 10, 30) and out.column("v")[0].as_py() == 1.25
    assert dolt.content_fingerprint(repo) == content0
    changed = dolt.diff_fingerprints(stat0, dolt.stat_fingerprint(repo))
    # The documented behaviour (ingest/dolt.py header, milestone 1 §6): the
    # manifest, the journal index and the chunk journal are rewritten, and so is
    # the stats database. If a later dolt stops touching them this fails, and
    # the mirror can be reconsidered (ADR 0001 §3).
    touched = {".dolt/noms/manifest", ".dolt/noms/journal.idx", ".dolt/" + dolt._JOURNAL}
    assert touched <= set(changed), changed
    assert any(c.startswith(".dolt/stats/") for c in changed), changed


@pytest.mark.dolt
@pytest.mark.skipif(not HAS_DOLT, reason="dolt is not installed")
def test_one_real_select_on_the_mirror_leaves_the_shared_clone_untouched():
    try:
        shared = config.dolt_repo("earnings")
    except FileNotFoundError:
        pytest.skip("no shared earnings clone")
    mirror = config.cache_dir() / "dolt_mirror" / "earnings"
    if not (mirror / ".dolt").is_dir():
        pytest.skip("no mirror yet (run python -m earnings_vol.ingest.run --only mirrors)")
    with dolt.guard(shared, mirror):
        n = dolt.query(mirror, "SELECT COUNT(*) AS n FROM `earnings_calendar` AS OF "
                               "'fjrb6h5le9h1qiif2j4pl6cpaas7pnee'").column("n")[0].as_py()
    assert n == 122113   # data model §1.1, measured through the DoltHub API on 2026-10-28
