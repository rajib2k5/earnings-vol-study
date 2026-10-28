# =============================================================================
# config.py — Where the data lives on disk.
#
# WHY A CONFIG FILE
#   The raw data (DoltHub clones, price downloads) is large and some of it may
#   not be shared, so it never goes inside the git repo. Every other file asks
#   this file "where is the data?" instead of writing a path by hand. To move
#   the data, set one environment variable: VOL_DATA_DIR.
#
# THE FOLDER LAYOUT
#   $VOL_DATA_DIR/                  (default ~/data/vol-projects; data_dir)
#       dolthub/<name>/             DoltHub clones. Shared by all projects, so
#                                   we only read them (dolt_repo).
#       earnings-vol-study/         This project's own folder (project_dir).
#           raw/                    Small sources that we download ourselves:
#                                   CBOE CSV files, yfinance prices (raw_dir).
#           cache/                  Files that we can build again: Parquet
#                                   extracts of the Dolt tables, and tables
#                                   derived from them (cache_dir).
#   The shared data folder that several projects read has one rule for this:
#   each project downloads its own small sources into
#   $VOL_DATA_DIR/<project>/raw/. The cache sits next to raw/, in the same
#   project folder.
#
# These functions only read the environment and the file system. They never
# use the network.
# =============================================================================

import os
from pathlib import Path

# The environment variable that moves all the data to another folder.
DATA_DIR_ENV = "VOL_DATA_DIR"

# Used when VOL_DATA_DIR is not set.
DEFAULT_DATA_DIR = "~/data/vol-projects"

# The name of this project's own folder inside the data folder.
PROJECT = "earnings-vol-study"


def data_dir() -> Path:
    """Return the root folder for all data.

    We use VOL_DATA_DIR if it is set. We expand "~" so that a value like
    "~/mydata" works. If it is not set, we use ~/data/vol-projects.
    """
    return Path(os.environ.get(DATA_DIR_ENV, DEFAULT_DATA_DIR)).expanduser()


def dolt_repo(name: str) -> Path:
    """Return the folder of a cloned DoltHub repo, e.g. dolt_repo("earnings").

    A cloned Dolt repo is a folder that has a ".dolt" folder inside it (as a
    git repo has ".git"). We check for both, because an empty folder with the
    right name is not a clone. If the clone is missing, we raise an error that
    says how to make it.

    The clones live in data_dir()/dolthub/, not in the project folder, because
    all projects share them. We never write into them.
    """
    path = data_dir() / "dolthub" / name
    if not (path / ".dolt").is_dir():
        raise FileNotFoundError(
            f"No Dolt clone at {path}. Clone it with:\n"
            f"  cd {path.parent} && dolt clone post-no-preference/{name}\n"
            f"(or set {DATA_DIR_ENV} to the folder that holds dolthub/{name})"
        )
    return path


def project_dir() -> Path:
    """Return this project's own folder: data_dir()/earnings-vol-study.

    Everything that this project writes goes below this folder. This function
    only builds the path. It does not make the folder: raw_dir() and
    cache_dir() do that when we ask for them.
    """
    return data_dir() / PROJECT


def raw_dir() -> Path:
    """Return the folder for the small sources that we download ourselves.

    The CBOE CSV files and the yfinance price downloads land here. Every project
    that uses the shared data folder that several projects read keeps its own
    downloads in $VOL_DATA_DIR/<project>/raw/. This is that folder.

    We make the folder if it does not exist yet, so the caller can write to it
    straight away.
    """
    path = project_dir() / "raw"
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_dir() -> Path:
    """Return the folder for files that we can build again.

    That means the Parquet extracts of the Dolt tables, and the tables that we
    derive from them on the way to the results. If you delete this folder, the
    next run builds the files again from the Dolt clones and from raw_dir().

    We make the folder if it does not exist yet, so the caller can write to it
    straight away.
    """
    path = project_dir() / "cache"
    path.mkdir(parents=True, exist_ok=True)
    return path
