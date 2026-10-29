# Tests for tools/export_app_data.py. A test never writes into app/: it passes
# --out (a path inside tmp_path), or it moves DEFAULT_OUT into tmp_path first.

import json
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

# The expected tables are written out by hand here. They are NOT imported from
# the exporter: a test that reads its expected value from the code under test
# can never fail.
EXPECTED_DATA_SOURCES = [
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

EXPECTED_DATA_LICENCE = {
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


@pytest.fixture
def exporter(load_tool):
    return load_tool("export_app_data")


def run_export(exporter, tmp_path, kind="meta"):
    out = tmp_path / "deep" / "er"  # the folders do not exist yet
    assert exporter.main(["--out-dir", str(out)]) == 0
    return json.loads((out / f"{kind}.json").read_text(encoding="utf-8"))


def test_writes_envelope_with_five_keys(exporter, tmp_path):
    doc = run_export(exporter, tmp_path)
    assert set(doc) == {"schema_version", "kind", "generated_at", "source_commit", "data"}
    assert doc["schema_version"] == "0.2.0"
    assert doc["kind"] == "meta"
    # ISO-8601 UTC with a trailing Z, e.g. 2026-10-27T12:00:00Z
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", doc["generated_at"])
    assert doc["source_commit"]  # not empty


def test_meta_data_fields(exporter, tmp_path):
    data = run_export(exporter, tmp_path)["data"]
    assert set(data) == {"project", "milestone", "title", "data_sources", "data_licence", "sample", "params",
                         "files", "provenance"}
    assert data["project"] == "earnings-vol-study"
    assert data["milestone"] == 1
    assert data["title"] == "Earnings and implied volatility: an event study"


def test_data_sources_are_exactly_the_expected_table(exporter, tmp_path):
    # The whole table, value by value: name, uses, url, licence and committed
    # for each source, in this order. The About page draws this table.
    sources = run_export(exporter, tmp_path)["data"]["data_sources"]
    assert sources == EXPECTED_DATA_SOURCES


def test_data_licence_is_exactly_the_expected_value(exporter, tmp_path):
    # The About page shows `attribution` as written and links `url`.
    assert run_export(exporter, tmp_path)["data"]["data_licence"] == EXPECTED_DATA_LICENCE


def test_data_licence_covers_exactly_the_sources_that_name_its_licence(exporter, tmp_path):
    data = run_export(exporter, tmp_path)["data"]
    licence, sources = data["data_licence"], data["data_sources"]
    names = {s["name"] for s in sources}
    assert set(licence["applies_to"]) <= names  # no name that is not in the table
    for s in sources:
        assert (s["name"] in licence["applies_to"]) == (s["licence"] == licence["name"]), s["name"]


def test_cboe_and_yahoo_are_never_committed(exporter, tmp_path):
    # Only the two DoltHub repos (CC BY-SA 4.0) may have derived tables in git.
    sources = run_export(exporter, tmp_path)["data"]["data_sources"]
    committed = {s["name"]: s["committed"] for s in sources}
    assert committed == {
        "DoltHub post-no-preference/earnings": True,
        "DoltHub post-no-preference/options": True,
        "Wikipedia List of S&P 500 companies": True,
        "FRED (Federal Reserve Bank of St. Louis)": False,
        "CBOE single-stock VIX indices": False,
        "Yahoo Finance prices (via yfinance)": False,
    }


def test_git_short_commit_without_any_commit_is_uncommitted(exporter, monkeypatch, tmp_path):
    # A brand-new repo has no HEAD, so `git rev-parse` fails.
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    monkeypatch.setattr(exporter, "ROOT", tmp_path)
    assert exporter.git_short_commit() == "uncommitted"


def test_git_short_commit_returns_short_hash_after_a_commit(exporter, monkeypatch, tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com",
                    "-c", "commit.gpgsign=false",
                    "commit", "-q", "--allow-empty", "-m", "x"], cwd=tmp_path, check=True)
    monkeypatch.setattr(exporter, "ROOT", tmp_path)
    full = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True,
                          text=True, check=True).stdout.strip()
    short = exporter.git_short_commit()
    # `git rev-parse --short` gives 7 hex characters in a small repo (a larger
    # repo may need a few more). Without --short we would get all 40.
    assert re.fullmatch(r"[0-9a-f]{7,12}", short)
    assert len(short) < len(full)
    assert full.startswith(short)


def test_git_short_commit_without_git_is_uncommitted(exporter, monkeypatch):
    # An empty PATH means the "git" program cannot be found.
    monkeypatch.setenv("PATH", "")
    assert exporter.git_short_commit() == "uncommitted"


def test_default_out_dir_is_the_apps_public_data(exporter):
    # This is where the app looks for the files (app/src/lib/meta.ts: data/meta.json,
    # served from app/public/). The expected path is written out here, so a wrong
    # DEFAULT_OUT_DIR cannot hide behind the monkeypatch in the next test.
    assert (REPO / "tools" / "export_app_data.py").is_file()  # REPO is the repository root
    assert exporter.DEFAULT_OUT_DIR == REPO / "app" / "public" / "data"


def test_main_without_out_dir_writes_to_default_out_dir(exporter, monkeypatch, tmp_path):
    target = tmp_path / "somewhere"
    monkeypatch.setattr(exporter, "DEFAULT_OUT_DIR", target)
    assert exporter.main([]) == 0
    assert json.loads((target / "meta.json").read_text(encoding="utf-8"))["kind"] == "meta"
    assert json.loads((target / "sample_funnel.json").read_text(encoding="utf-8"))["kind"] == "sample_funnel"


# The files the app really serves. The expected folder is written out by hand
# (see test_default_out_dir_is_the_apps_public_data), not read from the exporter.
PUBLIC = REPO / "app" / "public" / "data"


def without_code_commit(data: dict) -> dict:
    """The data with provenance.code_commit removed: like source_commit it names
    the commit at export time, so it legitimately differs after every commit."""
    out = json.loads(json.dumps(data))
    out.get("provenance", {}).pop("code_commit", None)
    return out


@pytest.mark.parametrize("kind", ["meta", "sample_funnel"])
def test_committed_json_matches_what_the_exporter_writes(exporter, kind):
    # Nothing else ties the committed files to the exporter: the app reads the
    # files, the exporter owns the content, and a number edited by hand in a file
    # (or an exporter change that was never re-exported) would pass every other
    # test. `generated_at` and `source_commit` (and provenance.code_commit)
    # legitimately differ on each export, so they are not compared, only checked
    # to be present. The exporter reads only committed inputs (data/derived,
    # params.yaml), so this runs without the local cache.
    committed = json.loads((PUBLIC / f"{kind}.json").read_text(encoding="utf-8"))
    p = exporter.params_mod.load()
    tables = exporter.load_tables()
    fresh = exporter.funnel_data(tables, p, "x") if kind == "sample_funnel" else exporter.meta_data(tables, p, "x")
    assert set(committed) == {"schema_version", "kind", "generated_at", "source_commit", "data"}
    assert committed["schema_version"] == "0.2.0"
    assert committed["kind"] == kind
    assert committed["generated_at"] and committed["source_commit"]
    assert committed["data"]["provenance"]["code_commit"]
    assert without_code_commit(committed["data"]) == without_code_commit(json.loads(json.dumps(fresh))), (
        f"app/public/data/{kind}.json is out of date: run `uv run python tools/export_app_data.py`"
    )


def test_meta_lists_exactly_the_files_written(exporter, tmp_path):
    out = tmp_path / "o"
    assert exporter.main(["--out-dir", str(out)]) == 0
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert sorted(meta["data"]["files"]) == sorted(f.stem for f in out.glob("*.json")) == ["meta", "sample_funnel"]


def test_funnel_and_meta_agree_on_the_primary_sample(exporter, tmp_path):
    meta = run_export(exporter, tmp_path)["data"]
    fun = run_export(exporter, tmp_path, "sample_funnel")["data"]
    assert meta["sample"]["n_events"] == fun["steps"][-1]["n_events"]
    assert meta["provenance"] == fun["provenance"]
    assert meta["sample"]["day0_from"] == "2024-12-05" and meta["sample"]["day0_to"] == "2026-10-26"


def test_exported_json_has_no_restricted_field(exporter, tmp_path):
    # No _yf or _cboe key may leave the machine (ADR 0001 §7), at any depth.
    for kind in ("meta", "sample_funnel"):
        text = json.dumps(run_export(exporter, tmp_path, kind))
        keys = re.findall(r'"([A-Za-z0-9_]+)":', text)
        assert not [k for k in keys if k.endswith(("_yf", "_cboe"))], kind
