# Tests for src/earnings_vol/config.py. We use tmp_path (a fresh empty folder
# for each test) and monkeypatch (to set environment variables for one test
# only), so we never touch the real ~/data folder.

from pathlib import Path

import pytest

from earnings_vol import config


def test_data_dir_uses_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv("VOL_DATA_DIR", str(tmp_path / "mydata"))
    assert config.data_dir() == tmp_path / "mydata"


def test_data_dir_expands_tilde(monkeypatch, tmp_path):
    # "~" means the home folder. We set HOME to tmp_path, so
    # "~/mydata" must become tmp_path / "mydata".
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("VOL_DATA_DIR", "~/mydata")
    assert config.data_dir() == tmp_path / "mydata"


def test_data_dir_default(monkeypatch, tmp_path):
    # No env var: the default is ~/data/vol-projects. With HOME = tmp_path,
    # that is tmp_path / "data" / "vol-projects".
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("VOL_DATA_DIR", raising=False)
    assert config.data_dir() == tmp_path / "data" / "vol-projects"


def test_dolt_repo_missing_dir_raises_with_clone_hint(monkeypatch, tmp_path):
    monkeypatch.setenv("VOL_DATA_DIR", str(tmp_path))
    with pytest.raises(FileNotFoundError) as excinfo:
        config.dolt_repo("earnings")
    # The message must tell the learner how to fix it.
    assert "dolt clone post-no-preference/earnings" in str(excinfo.value)
    assert str(tmp_path / "dolthub" / "earnings") in str(excinfo.value)


def test_dolt_repo_dir_without_dot_dolt_raises(monkeypatch, tmp_path):
    # The folder exists but it is not a clone (no .dolt inside).
    monkeypatch.setenv("VOL_DATA_DIR", str(tmp_path))
    (tmp_path / "dolthub" / "options").mkdir(parents=True)
    with pytest.raises(FileNotFoundError, match="dolt clone post-no-preference/options"):
        config.dolt_repo("options")


def test_dolt_repo_returns_path_when_clone_exists(monkeypatch, tmp_path):
    monkeypatch.setenv("VOL_DATA_DIR", str(tmp_path))
    (tmp_path / "dolthub" / "earnings" / ".dolt").mkdir(parents=True)
    # data_dir / "dolthub" / name
    assert config.dolt_repo("earnings") == tmp_path / "dolthub" / "earnings"


def test_project_dir_is_inside_data_dir_and_not_created(monkeypatch, tmp_path):
    monkeypatch.setenv("VOL_DATA_DIR", str(tmp_path))
    # data_dir / "earnings-vol-study"
    expected = tmp_path / "earnings-vol-study"
    assert config.project_dir() == expected
    # project_dir only builds the path. raw_dir and cache_dir make folders.
    assert not expected.exists()


def test_project_dir_default(monkeypatch, tmp_path):
    # No env var: data_dir is tmp_path / "data" / "vol-projects" (see the
    # data_dir default test), so the project folder is one level below it.
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("VOL_DATA_DIR", raising=False)
    assert config.project_dir() == tmp_path / "data" / "vol-projects" / "earnings-vol-study"


def test_raw_dir_is_created_on_demand(monkeypatch, tmp_path):
    monkeypatch.setenv("VOL_DATA_DIR", str(tmp_path))
    # data_dir / "earnings-vol-study" / "raw"
    expected = tmp_path / "earnings-vol-study" / "raw"
    assert not expected.exists()
    result = config.raw_dir()
    assert result == expected
    assert isinstance(result, Path) and result.is_dir()
    # A second call must not fail when the folder is already there.
    assert config.raw_dir() == expected
    # It makes only its own folder: no cache folder, and nothing at the old
    # place (data_dir / "cache").
    assert not (tmp_path / "earnings-vol-study" / "cache").exists()
    assert not (tmp_path / "cache").exists()


def test_cache_dir_is_created_on_demand(monkeypatch, tmp_path):
    monkeypatch.setenv("VOL_DATA_DIR", str(tmp_path))
    # data_dir / "earnings-vol-study" / "cache"
    expected = tmp_path / "earnings-vol-study" / "cache"
    assert not expected.exists()
    result = config.cache_dir()
    assert result == expected
    assert isinstance(result, Path) and result.is_dir()
    # A second call must not fail when the folder is already there.
    assert config.cache_dir() == expected
    # It makes only its own folder: no raw folder, and nothing at the old
    # place (data_dir / "cache").
    assert not (tmp_path / "earnings-vol-study" / "raw").exists()
    assert not (tmp_path / "cache").exists()


def test_raw_and_cache_dirs_work_when_data_dir_does_not_exist_yet(monkeypatch, tmp_path):
    # Not even VOL_DATA_DIR itself is there yet: all levels must be made.
    data = tmp_path / "fresh" / "data"
    monkeypatch.setenv("VOL_DATA_DIR", str(data))
    assert config.raw_dir() == data / "earnings-vol-study" / "raw"
    assert config.cache_dir() == data / "earnings-vol-study" / "cache"
    assert (data / "earnings-vol-study" / "raw").is_dir()
    assert (data / "earnings-vol-study" / "cache").is_dir()
