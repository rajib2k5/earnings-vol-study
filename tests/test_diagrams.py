# Tests for the diagrams in docs/architecture. The files in out/ must be exactly what
# the vendored toolkit (tools/diagrams/) builds from the specs. If you edit a spec and
# forget to rebuild, the first test fails. The PNG is left out (--no-png): its bytes are
# verified on aarch64 only, and it is a raster of the SVG that is checked.
#
# The toolkit runs in its own process, the way a person runs it.

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "tools" / "diagrams" / "build.py"
SPECS = ROOT / "docs" / "architecture" / "specs"
OUT = ROOT / "docs" / "architecture" / "out"

# The toolkit reads the specs with PyYAML. Skip only when that module is missing; the
# command that fixes it is in the skip reason.
pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("yaml") is None,
    reason="PyYAML is not installed: run with `uv run --frozen --group diagrams pytest`",
)


def check(specs: Path, out: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(BUILD), str(specs), "--out", str(out), "--check", "--no-png"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )


def test_diagrams_on_disk_are_in_sync_with_the_specs():
    result = check(SPECS, OUT)
    assert result.returncode == 0, (
        "Run: uv run --frozen --group diagrams python tools/diagrams/build.py "
        "docs/architecture/specs --out docs/architecture/out\n" + result.stderr
    )
    assert "5 spec(s) up to date" in result.stdout


def test_a_changed_spec_label_is_reported_out_of_sync(tmp_path):
    # Copy the specs and out/ elsewhere, change one label in the copy, and the check
    # must notice. This also shows that the check above can fail.
    specs = tmp_path / "specs"
    out = tmp_path / "out"
    shutil.copytree(SPECS, specs)
    shutil.copytree(OUT, out)
    assert check(specs, out).returncode == 0

    spec = specs / "process.yaml"
    text = spec.read_text(encoding="utf-8")
    assert "label: Pick milestone," in text
    spec.write_text(text.replace("label: Pick milestone,", "label: Pick a milestone,"), encoding="utf-8")

    result = check(specs, out)
    assert result.returncode == 1
    assert "diagrams out of date" in result.stderr
    assert "process.mmd" in result.stderr
