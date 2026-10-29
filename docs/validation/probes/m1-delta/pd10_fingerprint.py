# pd10 (claim 7a): does dolt.stat_fingerprint see every kind of new path in a
# clone-shaped folder? Runs on a throw-away folder in a temp dir only.
#
# Run: uv run --frozen python docs/validation/probes/m1-delta/pd10_fingerprint.py
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "src"))
from earnings_vol.ingest import dolt  # noqa: E402


def fresh(root: Path) -> Path:
    (root / ".dolt" / "noms").mkdir(parents=True)
    (root / ".dolt" / "noms" / "manifest").write_bytes(b"m1")
    (root / ".dolt" / "repo_state.json").write_text("{}")
    (root / "README.md").write_text("clone")
    return root


cases = {
    "hidden file beside .dolt": lambda r: (r / ".hidden").write_text("x"),
    "file in a new nested dir": lambda r: ((r / "a" / "b").mkdir(parents=True), (r / "a" / "b" / "f").write_text("x")),
    "new empty dir": lambda r: (r / "emptydir").mkdir(),
    "file inside .dolt/": lambda r: (r / ".dolt" / "LOCK").write_text(""),
    "file in .dolt/noms": lambda r: (r / ".dolt" / "noms" / "LOCK").write_text(""),
    "symlink to a file outside": lambda r: os.symlink("/etc/hostname", r / "link"),
    "dangling symlink": lambda r: os.symlink("/nonexistent/x", r / "dangling"),
    "same-size overwrite, mtime restored": lambda r: (
        lambda st: ((r / "README.md").write_text("CLONE"),
                    os.utime(r / "README.md", ns=(st.st_atime_ns, st.st_mtime_ns))))((r / "README.md").stat()),
}
with tempfile.TemporaryDirectory() as tmp:
    for name, act in cases.items():
        r = fresh(Path(tmp) / name.replace(" ", "_").replace("/", "_"))
        before = dolt.stat_fingerprint(r)
        act(r)
        try:
            diff = dolt.diff_fingerprints(before, dolt.stat_fingerprint(r))
            print(f"{'SEEN  ' if diff else 'UNSEEN'} {name:38s} diff={diff}")
        except Exception as e:  # noqa: BLE001
            print(f"RAISES {name:38s} {type(e).__name__}: {e}")
