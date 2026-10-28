"""Probe: runtime checks of library-behaviour statements in docs/milestones/00-scaffold-and-design.md.

Usage (from the repo root; writes only into a fresh tempfile.mkdtemp() directory, so set
TMPDIR to a scratch folder):
    uv run python docs/validation/probes/m0-code/docs/doc_claims_probe.py

Each line prints LABEL: observed value. The ledger maps each to the doc sentence it tests.
"""

import importlib.util
import json
import math
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path.cwd()


def load_tool(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def show(label, value):
    print(f"{label}: {value!r}")


# --- section 2.2 NaN table -------------------------------------------------------------
show("py-default-nan", json.dumps({"x": float("nan")}))
show("py-default-inf", json.dumps({"x": float("inf")}))
try:
    json.dumps({"x": float("nan")}, allow_nan=False)
    show("py-allow_nan-False", "NO ERROR")
except ValueError as e:
    show("py-allow_nan-False", f"ValueError: {e}")
try:
    import numpy as np
    import pandas as pd

    show("pandas-to_json", pd.DataFrame({"x": [np.nan]}).to_json())
    show("pandas-version", pd.__version__)
except Exception as e:  # noqa: BLE001
    show("pandas-to_json", f"ERROR {e}")

# --- section 2.2 "strftime has no fraction field" ------------------------------------------
t = datetime(2026, 10, 27, 12, 0, 0, 123456, tzinfo=timezone.utc)
show("strftime-%f", t.strftime("%Y-%m-%dT%H:%M:%S.%fZ"))
show("astimezone 14:00+02:00", datetime(2026, 10, 27, 14, 0, tzinfo=timezone(timedelta(hours=2)))
     .astimezone(timezone.utc).isoformat())

# --- section 2.2 "dumps runs before write_text opens the file" -------------------------------
from earnings_vol import contract  # noqa: E402

work = Path(tempfile.mkdtemp(prefix="m0doc-"))
exporter = load_tool("export_app_data")
out = work / "meta.json"
out.write_text("OLD GOOD FILE\n", encoding="utf-8")
orig = exporter.meta_data
exporter.meta_data = lambda: {**orig(), "bad": math.nan}
try:
    exporter.main(["--out", str(out)])
    show("export-with-nan", "NO ERROR")
except ValueError as e:
    show("export-with-nan", f"ValueError: {e}")
show("old-file-after-failed-export", out.read_text(encoding="utf-8"))
exporter.meta_data = orig

# --- section 2.4: nbformat ids, format 4.5, check() "byte for byte" --------------------------
import nbformat  # noqa: E402
from nbformat.v4 import new_code_cell, new_notebook  # noqa: E402

show("nbformat-version", nbformat.__version__)
show("new_notebook-default-minor", new_notebook().nbformat_minor)
show("two-new_code_cell-ids-differ", new_code_cell("x")["id"] != new_code_cell("x")["id"])
show("example-random-id", new_code_cell("x")["id"])

builder = load_tool("build_notebooks")
good = builder.render()
crlf = work / "crlf.ipynb"
crlf.write_bytes(good.replace("\n", "\r\n").encode("utf-8"))
show("crlf-bytes-equal-render-bytes", crlf.read_bytes() == good.encode("utf-8"))
show("check(crlf-file)", builder.check(crlf))
cr = work / "cr.ipynb"
cr.write_bytes(good.replace("\n", "\r").encode("utf-8"))
show("check(cr-only-file)", builder.check(cr))
space = work / "space.ipynb"
space.write_text(good + " ", encoding="utf-8")
show("check(trailing-space) [falsifier control]", builder.check(space))

# "Bump either [version], forget to rebuild, and the check fails" (in-process bump, no repo edit)
import earnings_vol  # noqa: E402

disk = builder.NOTEBOOK_PATH
show("check(disk) before bump", builder.check(disk))
builder.__version__ = "9.9.9"  # the name build_notebooks imported
show("check(disk) after __version__ bump", builder.check(disk))
builder.__version__ = earnings_vol.__version__
builder.contract.SCHEMA_VERSION, saved = "9.9.9", builder.contract.SCHEMA_VERSION
show("check(disk) after SCHEMA_VERSION bump", builder.check(disk))
builder.contract.SCHEMA_VERSION = saved
show("first-cell-type", nbformat.reads(good, as_version=4).cells[0].cell_type)

# --- node half of the NaN table + Date.UTC rollover -------------------------------------------
js = r"""
const r = {};
try { JSON.parse('{"x": NaN}'); r.parse = 'NO THROW' } catch (e) { r.parse = `${e.name}: ${e.message}` }
r.stringify = JSON.stringify({ x: NaN });
r.dateUtcFeb30 = new Date(Date.UTC(2026, 1, 30)).toISOString();
r.node = process.version;
console.log(JSON.stringify(r));
"""
try:
    res = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True)
    show("node", res.stdout.strip())
except Exception as e:  # noqa: BLE001
    show("node", f"ERROR {e}")
print("python", sys.version.split()[0])
