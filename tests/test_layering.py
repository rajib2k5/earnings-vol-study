# ADR 0001 §1: "A layer imports only from layers to its left", and only the
# ends do I/O: a stage is a run_<stage>() shell (its run.py) around pure
# functions. This test parses every module with `ast` (real structure, not a
# text search) and fails on
#   1. an import of a layer further right (relative imports resolved first);
#   2. in a middle layer (events, measures, panel, stats, export), a module
#      other than run.py that imports anything outside an ALLOW-list, or calls
#      an I/O or dynamic-access function (delta review, claim 5a: the first
#      version was a deny-list, and 15 I/O forms passed it).
#
#   core (config, params, schema, store, contract)  <  ingest  <  events
#   <  measures  <  panel  <  stats  <  export
#
# The allow-list for a middle module other than run.py: pure stdlib modules
# (PURE_STDLIB), numpy, pandas, scipy, statsmodels, exchange_calendars (the
# XNYS session rules, computed in code: events/calendar.py needs it), params
# and schema, and middle modules of its own layer or one to its left.
# Everything else is refused, among it store, config, contract, ingest,
# io, importlib and builtins, and pandas.io and numpy's npyio.
#
# Mutations checked by hand, each seen to fail:
#   - `from earnings_vol.measures import forward` added to events/events.py
#   - `open(__file__)` added to events/eps.py (the review's M10)
#   - `import urllib.request` added to events/eps.py (the review's M10)
#   - every form of docs/validation/probes/m1-delta/pd08_layering_mutants.sh
#     (relative imports of store and ingest, left imports of ingest, np.load,
#     np.savetxt, pd.read_pickle, df.to_pickle, pd.read_html, pd.read_feather,
#     importlib, __import__, io.FileIO, getattr(builtins, ...), exec), run by
#     that script on a scratch copy of the tree, and a relative right-layer
#     import (`from ..measures import forward` in events/eps.py)

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "earnings_vol"
ORDER = ["core", "ingest", "events", "measures", "panel", "stats", "export"]


def layer_of(module: str) -> str:
    """earnings_vol.events.timing -> events; earnings_vol.store -> core."""
    parts = module.split(".")
    assert parts[0] == "earnings_vol", module
    return parts[1] if len(parts) > 1 and parts[1] in ORDER else "core"


def module_name(path: Path) -> tuple[str, bool]:
    """src/earnings_vol/events/eps.py -> ("earnings_vol.events.eps", False); a package's
    __init__.py -> (the package, True)."""
    rel = path.relative_to(SRC.parent).with_suffix("")
    if rel.parts[-1] == "__init__":
        return ".".join(rel.parts[:-1]), True
    return ".".join(rel.parts), False


def resolve(node: ast.ImportFrom, me: str, is_pkg: bool) -> str:
    """The absolute module of `from X import ...`: `from .. import store` in
    earnings_vol.events.eps -> earnings_vol."""
    if node.level == 0:
        return node.module
    pkg = me.split(".") if is_pkg else me.split(".")[:-1]
    base = pkg[:len(pkg) - (node.level - 1)]
    return ".".join(base + ([node.module] if node.module else []))


def imported_modules(source: str, me: str = "earnings_vol.events.fake", is_pkg: bool = False) -> list[str]:
    """Every earnings_vol module a source file imports, resolved to full names. A
    `from earnings_vol.x import name` counts as earnings_vol.x (its layer is x's)."""
    out = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            out += [a.name for a in node.names if a.name.split(".")[0] == "earnings_vol"]
        elif isinstance(node, ast.ImportFrom):
            mod = resolve(node, me, is_pkg)
            if mod.split(".")[0] != "earnings_vol":
                continue
            if mod == "earnings_vol":
                out += [f"earnings_vol.{a.name}" for a in node.names]   # from earnings_vol import events
            else:
                out.append(mod)
    return out


def violations(path: Path, source: str) -> list[str]:
    me, is_pkg = module_name(path)
    mine = layer_of(me)
    bad = []
    for mod in imported_modules(source, me, is_pkg):
        if ORDER.index(layer_of(mod)) > ORDER.index(mine):
            bad.append(f"{me} ({mine}) imports {mod} ({layer_of(mod)})")
    return bad


def test_no_module_imports_a_layer_to_its_right():
    found = []
    files = sorted(SRC.rglob("*.py"))
    assert len(files) >= 20                      # the walk really sees the package
    for f in files:
        found += violations(f, f.read_text(encoding="utf-8"))
    assert found == []


@pytest.mark.parametrize("source, n_bad", [
    ("from earnings_vol.measures import forward\n", 1),           # events -> measures: right
    ("import earnings_vol.export.funnel\n", 1),
    ("from earnings_vol import panel\n", 1),
    ("from earnings_vol.ingest import universe\nfrom earnings_vol import store\n", 0),   # left and core: fine
    ("def f():\n    from earnings_vol.stats import x\n", 1),       # a late import counts too
    ("from ..measures import forward\n", 1),                       # relative, resolved (delta review)
    ("from .. import panel\n", 1),
    ("from . import calendar\nfrom .. import schema\n", 0),        # own layer and core: fine
])
def test_the_checker_itself(source, n_bad):
    assert len(violations(SRC / "events" / "fake.py", source)) == n_bad


# --- the pure middle (ADR 0001 §1) -----------------------------------------------

MIDDLE = ("events", "measures", "panel", "stats", "export")
# The allow-list (see the header).
PURE_STDLIB = ("__future__", "abc", "bisect", "collections", "copy", "csv", "dataclasses", "datetime", "decimal",
               "enum", "fractions", "functools", "hashlib", "heapq", "itertools", "math", "numbers", "operator",
               "re", "statistics", "string", "textwrap", "types", "typing")
THIRD_PARTY = ("numpy", "pandas", "scipy", "statsmodels", "exchange_calendars")
CORE_ALLOWED = ("earnings_vol.params", "earnings_vol.schema")
# Submodules of allowed packages that read or write files.
IO_SUBMODULES = ("pandas.io", "numpy.lib.npyio", "numpy.lib._npyio_impl", "scipy.io", "statsmodels.iolib")
# Calls refused in a pure middle module, by the called name: file and process access, and
# dynamic code or attribute access that could reach them.
BANNED_NAMES = ("open", "exec", "eval", "compile", "__import__", "breakpoint", "input", "getattr", "setattr",
                "delattr", "globals", "locals", "vars")
# numpy's file functions and pandas' writers (pandas' readers all start with read_).
BANNED_ATTRS = ("open", "load", "save", "savez", "savez_compressed", "savetxt", "loadtxt", "genfromtxt", "fromfile",
                "tofile", "fromregex", "memmap", "dump", "to_parquet", "to_csv", "to_pickle", "to_feather", "to_hdf",
                "to_sql", "to_excel", "to_json", "to_html", "to_latex", "to_markdown", "to_stata", "to_orc",
                "to_xml", "to_clipboard", "to_gbq")
BANNED_PREFIXES = ("read_", "write_")


def _under(name: str, prefixes) -> bool:
    return any(name == m or name.startswith(m + ".") for m in prefixes)


def import_allowed(name: str, mine: str) -> bool:
    """May a middle module of layer `mine` import the absolute module `name`?"""
    top = name.split(".")[0]
    if top == "earnings_vol":
        if _under(name, CORE_ALLOWED):
            return True
        layer = layer_of(name)
        return layer in MIDDLE and ORDER.index(layer) <= ORDER.index(mine) and name != f"earnings_vol.{layer}.run" \
            and not name.startswith(f"earnings_vol.{layer}.run.")
    if top in PURE_STDLIB:
        return True
    return top in THIRD_PARTY and not _under(name, IO_SUBMODULES)


def io_violations(path: Path, source: str) -> list[str]:
    """Imports outside the allow-list, and I/O or dynamic-access calls, in a pure middle
    module; [] for run.py and for core and ingest."""
    rel = path.relative_to(SRC.parent).with_suffix("")
    if len(rel.parts) < 3 or rel.parts[1] not in MIDDLE or rel.parts[-1] == "run":
        return []
    me, is_pkg = module_name(path)
    mine = layer_of(me)
    tree = ast.parse(source)
    bad = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            bad += [f"{rel} imports {a.name}" for a in node.names if not import_allowed(a.name, mine)]
        elif isinstance(node, ast.ImportFrom):
            mod = resolve(node, me, is_pkg)
            # `from X import n`: X must be allowed, and so must X.n where n is a submodule
            # (from earnings_vol import store; from pandas import io). A plain name such as
            # `from datetime import date` passes as datetime.date, whose top is allowed.
            names = [mod] + [f"{mod}.{a.name}" for a in node.names if a.name != "*"]
            if mod == "earnings_vol":
                names = names[1:]
            bad += [f"{rel} imports {n}" for n in names if not import_allowed(n, mine)]
        elif isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name) and f.id in BANNED_NAMES:
                bad.append(f"{rel}:{node.lineno} calls {f.id}()")
            elif isinstance(f, ast.Attribute) and (f.attr in BANNED_ATTRS or f.attr.startswith(BANNED_PREFIXES)):
                bad.append(f"{rel}:{node.lineno} calls .{f.attr}()")
        elif isinstance(node, ast.Name) and node.id == "__builtins__":
            bad.append(f"{rel}:{node.lineno} uses __builtins__")
    return bad


def test_middle_modules_other_than_run_do_no_io():
    found = []
    files = sorted(SRC.rglob("*.py"))
    assert sum(1 for f in files if f.relative_to(SRC).parts[0] in MIDDLE) >= 10   # the walk sees the middle
    for f in files:
        found += io_violations(f, f.read_text(encoding="utf-8"))
    assert found == []


@pytest.mark.parametrize("where, source, n_bad", [
    ("events/eps.py", "x = open(__file__).read()\n", 1),
    ("events/eps.py", "import urllib.request\n", 1),
    ("events/eps.py", "from urllib import request\n", 2),            # urllib and urllib.request
    ("events/eps.py", "import subprocess\n", 1),
    ("events/eps.py", "from pathlib import Path\n", 2),
    ("events/eps.py", "import pyarrow.parquet as pq\n", 1),
    ("events/eps.py", "from pyarrow import parquet\n", 2),
    ("events/eps.py", "from earnings_vol import store\n", 1),
    ("export/funnel.py", "import pandas as pd\ndf = pd.read_parquet('x')\n", 1),
    ("panel/baseline.py", "def f(p):\n    return p.write_text('x')\n", 1),
    # The forms of the delta review's pd08, each alone:
    ("events/eps.py", "from .. import store as _s\n", 1),
    ("events/eps.py", "from ..ingest import dolt as _d\n", 2),       # earnings_vol.ingest and .dolt
    ("events/eps.py", "from earnings_vol.ingest import prices as _p\n", 2),
    ("events/eps.py", "from earnings_vol.ingest import dolt\n", 2),
    ("events/eps.py", "import numpy as np\nx = np.load('x.npy')\n", 1),
    ("events/eps.py", "import numpy as np\nnp.savetxt('x.txt', [1])\n", 1),
    ("events/eps.py", "import numpy as np\nnp.save('x.npy', [1])\n", 1),
    ("events/eps.py", "import pandas as pd\nx = pd.read_pickle('x.pkl')\n", 1),
    ("events/eps.py", "def f(df):\n    df.to_pickle('x.pkl')\n", 1),
    ("events/eps.py", "import pandas as pd\nx = pd.read_html('https://example.com')\n", 1),
    ("events/eps.py", "import pandas as pd\nx = pd.read_feather('x.feather')\n", 1),
    ("events/eps.py", "def f(df):\n    df.to_csv('x.csv')\n", 1),
    ("events/eps.py", "import importlib\n", 1),
    ("events/eps.py", "_sock = __import__('socket')\n", 1),
    ("events/eps.py", "import io\ndef f():\n    return io.FileIO('x')\n", 1),
    ("events/eps.py", "import builtins\ndef f():\n    return getattr(builtins, 'op' + 'en')('x')\n", 2),
    ("events/eps.py", "exec('import os')\n", 1),
    ("events/eps.py", "x = __builtins__\n", 1),
    ("events/eps.py", "from pandas import io\n", 1),                  # pandas.io
    ("events/eps.py", "import config\n", 1),                          # not on the list
    ("events/eps.py", "from earnings_vol.events import run\n", 1),    # a stage shell is not pure
    ("measures/forward.py", "from earnings_vol.export import funnel\n", 2),   # a layer to the right
    # Allowed:
    ("events/eps.py", "import numpy as np\nimport pandas as pd\nfrom datetime import date\nimport re\n"
                      "import exchange_calendars as xcals\nfrom earnings_vol import params, schema\n"
                      "from earnings_vol.events import calendar\nfrom . import securities\n"
                      "def f(df):\n    return df.to_numpy(), df.to_dict(), df['a'].tolist()\n", 0),
    ("export/funnel.py", "from earnings_vol.panel.baseline import clean_baseline\n"
                         "from earnings_vol.events.eps import orphan_zones\n", 0),       # to the left: fine
    ("events/run.py", "import subprocess\nx = open(__file__)\n", 0),          # the stage shell may
    ("ingest/dolt.py", "import subprocess\n", 0),                               # an end may
    ("store.py", "x = open(__file__)\n", 0),                                    # core may
])
def test_the_io_checker_itself(where, source, n_bad):
    assert len(io_violations(SRC / where, source)) == n_bad, io_violations(SRC / where, source)
