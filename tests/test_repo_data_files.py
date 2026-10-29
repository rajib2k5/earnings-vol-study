"""The repository tracks no raw vendor file and no oversized data file (ADR 0001 §7, owner decision 2026-10-29).

Mutations this module must catch (applied by hand, each seen to fail; added after the milestone-2 review, claim 15b):
  - rule 7 removed (a gzip or zip copy passes)
  - rule 6 by name removed (an unregistered table, market_daily or chain_expiry in data/derived/ passes)
  - rule 6 allowing every registry table, not only the committed ones (market_daily passes)
  - rule 6 by content removed (a raw quote month re-serialised as iv_daily.parquet passes)
  - rule 6 by content comparing column sets loosely (a table with an extra column passes)
  - suffixes and folders compared case-sensitively again (Raw/DTB3.CSV passes)
  - an app file's `kind` field not checked (iv_measures.json holding another kind passes)
"""

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("check_data_files", REPO / "tools/licensing/check_data_files.py")
check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check)

MB = 1024 * 1024


@pytest.mark.skipif(shutil.which("git") is None or not (REPO / ".git").exists(), reason="needs a git checkout")
def test_tracked_files_hold_no_raw_vendor_file_and_no_oversized_data_file():
    # Rules 1-4 on the index; rule 5 too when the local vendor folder exists (it does not in CI).
    assert check.check(REPO, check.default_vendor_root()) == []


def test_allowed_paths_pass():
    files = [
        ("data/derived/events.parquet", 2 * MB),
        ("data/derived/iv_daily.parquet", 5 * MB),
        ("data/derived/README.md", 5_000),
        ("data/derived/LICENSE", 2_000),
        ("data/derived/earnings_calendar_30_large_caps.json", 40_000),
        ("data/manual/press_release_checks.csv", 10_000),
        ("app/public/data/sample_funnel.json", 9 * MB),  # under the 10 MB data limit
        ("app/public/data/meta.json", 4_000),
        ("app/public/data/iv_measures.json", 20_000),
        ("docs/architecture/out/erd.png", 2 * MB),  # not a data file: only the 50 MB limit applies
        ("tools/diagrams/diagram_kit/mermaid_reserved.json", 4_000),  # JSON outside data folders is not data
    ]
    assert check.problems(files) == []


@pytest.mark.parametrize(
    ("path", "size", "reason"),
    [
        ("data/raw/yfinance/AAPL.parquet", 1_000, "raw or cache folder"),
        ("notes/cache/x.json", 10, "raw or cache folder"),
        ("data/derived/dolt_mirror/options/x.bin", 10, "raw or cache folder"),
        ("fixtures/.dolt/noms/manifest", 10, "raw or cache folder"),
        ("data/derived/VIXCLS.csv", 10, "raw vendor download"),
        ("data/derived/market_cap_2026-10-29.csv", 10, "raw vendor download"),
        ("data/derived/spy_eod_2023.parquet", 10, "raw vendor download"),
        ("research/prices.parquet", 10, "outside data/derived/"),
        ("app/public/data/iv.csv", 10, "outside data/derived/"),
        # Case does not help (the review's T7b): a capital folder or suffix is the same rule.
        ("Raw/DTB3.CSV", 10, "raw or cache folder"),
        ("data/derived/VIXCLS.CSV", 10, "raw vendor download"),
        ("research/prices.CSV", 10, "outside data/derived/"),
        # Rule 7: compressed archives anywhere (the review's T3: a gzip copy of DTB3 in data/derived/ passed).
        ("data/derived/rates.csv.gz", 10, "compressed archive"),
        ("docs/notes/chain.zip", 10, "compressed archive"),
        ("research/x.tar.bz2", 10, "compressed archive"),
        ("research/x.xz", 10, "compressed archive"),
        ("research/x.7z", 10, "compressed archive"),
        ("research/x.tar", 10, "compressed archive"),
        ("research/x.parquet.zst", 10, "compressed archive"),
        ("research/x.tgz", 10, "compressed archive"),
        ("data/manual/OLD.CSV.GZ", 10, "compressed archive"),
        # Rule 6 by name: data/derived/ holds committed registry tables only (the review's T5 and T6).
        ("data/derived/option_chain_2021-04.parquet", 10, "not a file data/derived/ may hold"),
        ("data/derived/market_daily.parquet", 10, "not a file data/derived/ may hold"),     # local only
        ("data/derived/chain_expiry.parquet", 10, "not a file data/derived/ may hold"),     # local only
        ("data/derived/extra/events.parquet", 10, "not a file data/derived/ may hold"),
        ("data/derived/notes.txt", 10, "not a file data/derived/ may hold"),
        ("app/public/data/terrain.json", 10, "not <kind>.json"),
        ("app/public/data/meta.csv.json", 10, "not <kind>.json"),
        # 10 MB = 10,485,760 bytes; one byte over is refused for a data file.
        ("data/derived/iv_daily.parquet", 10 * MB + 1, "limit for a data file"),
        ("app/public/data/iv_measures.json", 10 * MB + 1, "limit for a data file"),
        # 50 MB = 52,428,800 bytes; one byte over is refused for any file.
        ("docs/images/hero.png", 50 * MB + 1, "hard limit"),
    ],
)
def test_refused_paths(path, size, reason):
    found = check.problems([(path, size)])
    assert len(found) == 1 and reason in found[0], found


def test_limits_are_inclusive_at_the_boundary():
    # Exactly at each limit passes; the rule is "over the limit".
    assert check.problems([("data/derived/iv_daily.parquet", 10 * MB), ("docs/b.png", 50 * MB)]) == []


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_the_index_is_read_not_the_folder(tmp_path):
    _git(tmp_path, "init", "-q")
    (tmp_path / "data/raw").mkdir(parents=True)
    (tmp_path / "data/raw/VIXCLS.csv").write_text("date,value\n")  # 11 bytes, staged below
    (tmp_path / "untracked.parquet").write_bytes(b"x")  # on disk only: must not be listed
    _git(tmp_path, "add", "data/raw/VIXCLS.csv")
    blobs = check.tracked_blobs(tmp_path)
    assert [(p, size) for p, _, size in blobs] == [("data/raw/VIXCLS.csv", 11)]
    # The staged blob's size counts, not the file on disk: grow the file after staging.
    (tmp_path / "data/raw/VIXCLS.csv").write_text("date,value\n" + "x" * 100)
    assert check.tracked_blobs(tmp_path)[0][2] == 11


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_a_renamed_copy_of_a_vendor_file_is_refused(tmp_path):
    repo, vendor = tmp_path / "repo", tmp_path / "vendor"
    (vendor / "raw/fred").mkdir(parents=True)
    (vendor / "cache/dolt/options@abc").mkdir(parents=True)
    (vendor / "cache/stage/1").mkdir(parents=True)
    (vendor / "raw/fred/made_up.csv").write_bytes(b"observation_date,X\n2001-01-02,1.5\n")
    (vendor / "cache/dolt/options@abc/2001-01.parquet").write_bytes(b"made-up raw dolt extract bytes")
    (vendor / "cache/stage/1/events.parquet").write_bytes(b"our own output, may be committed")
    (repo / "data/derived").mkdir(parents=True)
    _git(repo, "init", "-q")
    # A copy under an innocent name in an allowed folder passes rules 1-4 but not rule 5.
    (repo / "data/derived/summary.csv").write_bytes((vendor / "raw/fred/made_up.csv").read_bytes())
    # Same size, different bytes: must not be flagged.
    (repo / "data/derived/other.csv").write_bytes(b"observation_date,X\n2001-01-02,2.5\n")
    (repo / "data/derived/chain.parquet").write_bytes(b"made-up raw dolt extract bytes")
    (repo / "data/derived/events.parquet").write_bytes(b"our own output, may be committed")
    _git(repo, "add", "-A")
    found = sorted(check.copies(check.tracked_blobs(repo), check.vendor_files(vendor), repo))
    assert found == [
        "data/derived/chain.parquet: a byte-for-byte copy of the local vendor file 2001-01.parquet",
        "data/derived/summary.csv: a byte-for-byte copy of the local vendor file made_up.csv",
    ]
    # Rule 5 is part of check() whenever the vendor folder exists.
    assert set(found) <= set(check.check(repo, vendor))
    # Without the vendor folder (CI) rule 5 is skipped, but rule 6 still refuses every one of these files: three
    # names data/derived/ may not hold, and a registered name whose staged bytes are not Parquet.
    assert sorted(check.check(repo, None)) == [
        "data/derived/chain.parquet: not a file data/derived/ may hold (a committed table of the schema registry, "
        "README.md, LICENSE)",
        "data/derived/events.parquet: not a readable Parquet file",
        "data/derived/other.csv: not a file data/derived/ may hold (a committed table of the schema registry, "
        "README.md, LICENSE)",
        "data/derived/summary.csv: not a file data/derived/ may hold (a committed table of the schema registry, "
        "README.md, LICENSE)",
    ]


def _parquet(path: Path, columns: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.table(columns), path)


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_a_re_serialised_table_or_a_local_table_is_refused_without_the_vendor_folder(tmp_path):
    # The review's T5 and T6, in a scratch repository with no vendor folder (as in CI, so rule 5 cannot help).
    # Made-up rows only.
    _git(tmp_path, "init", "-q")
    raw_month = {"date": ["2001-01-02"], "act_symbol": ["ZZZ"], "expiration": ["2001-01-19"], "strike": [10.0],
                 "call_put": ["Call"], "bid": [1.0], "ask": [1.1]}
    # 1. A raw quote month re-serialised under a registered name, and under its own name.
    _parquet(tmp_path / "data/derived/iv_daily.parquet", raw_month)
    _parquet(tmp_path / "data/derived/option_chain_2001-01.parquet", raw_month)
    # 2. The local-only market_daily (its class-R VIX columns included), under its own name.
    _parquet(tmp_path / "data/derived/market_daily.parquet",
             {"session_date": ["2001-01-02"], "r_dtb3": [0.05], "r_cont": [0.051], "vix_close_cboe": [20.0],
              "ln_vix_cboe": [3.0]})
    # 3. A registered table with the right columns plus one more, in the wrong order or not.
    _parquet(tmp_path / "data/derived/ticker_alias.parquet",
             {"ticker": ["ZZZ"], "valid_from": ["2001-01-02"], "valid_to": [None], "security_id": ["ZZZ"],
              "extra": [1]})
    # 4. The control: session_snapshot with exactly its committed columns passes.
    want = list(check.store.committed_schema(check.schema.REGISTRY["session_snapshot"]).names)
    assert want == ["security_id", "session_date", "snapshot_date", "snapshot_status"]
    _parquet(tmp_path / "data/derived/session_snapshot.parquet", {c: ["x"] for c in want})
    _git(tmp_path, "add", "-A")
    found = sorted(check.check(tmp_path, None))
    assert [f.split(":")[0] for f in found] == ["data/derived/iv_daily.parquet", "data/derived/market_daily.parquet",
                                                "data/derived/option_chain_2001-01.parquet",
                                                "data/derived/ticker_alias.parquet"]
    assert "its columns ['date', 'act_symbol'" in found[0] and "committed iv_daily table" in found[0]
    assert "not a file data/derived/ may hold" in found[1] and "not a file data/derived/ may hold" in found[2]
    assert "committed ticker_alias table" in found[3]


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_a_gzip_copy_of_a_vendor_file_is_refused_with_or_without_the_vendor_folder(tmp_path):
    # The review's T3: rule 5 compares bytes, and a gzip copy has other bytes, so only rule 7 sees it.
    import gzip
    repo, vendor = tmp_path / "repo", tmp_path / "vendor"
    (vendor / "raw/fred").mkdir(parents=True)
    raw = b"observation_date,X\n2001-01-02,1.5\n"          # made up
    (vendor / "raw/fred/made_up.csv").write_bytes(raw)
    (repo / "data/derived").mkdir(parents=True)
    _git(repo, "init", "-q")
    (repo / "data/derived/rates.csv.gz").write_bytes(gzip.compress(raw, mtime=0))
    _git(repo, "add", "-A")
    assert check.copies(check.tracked_blobs(repo), check.vendor_files(vendor), repo) == []   # rule 5 is blind
    expected = ["data/derived/rates.csv.gz: a compressed archive"]
    assert check.check(repo, vendor) == expected and check.check(repo, None) == expected


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_an_app_file_must_carry_its_own_kind(tmp_path):
    _git(tmp_path, "init", "-q")
    (tmp_path / "app/public/data").mkdir(parents=True)
    (tmp_path / "app/public/data/meta.json").write_text(json.dumps({"kind": "meta", "data": {}}))
    (tmp_path / "app/public/data/iv_measures.json").write_text(json.dumps({"kind": "sample_funnel", "data": {}}))
    (tmp_path / "app/public/data/sample_funnel.json").write_text(json.dumps([1, 2, 3]))
    _git(tmp_path, "add", "-A")
    assert sorted(check.check(tmp_path, None)) == [
        "app/public/data/iv_measures.json: its kind is 'sample_funnel', not 'iv_measures'",
        "app/public/data/sample_funnel.json: not a JSON object",
    ]


def test_the_allow_lists_follow_the_registry_and_the_contract():
    # Every committed registry table, and only those; every contract kind, and only those.
    assert check.COMMITTED_TABLES == ("eps", "event_iv", "events", "iv_daily", "security", "session",
                                      "session_snapshot", "ticker_alias", "timing_check")
    assert check.contract.KINDS == ("meta", "sample_funnel", "iv_measures")
