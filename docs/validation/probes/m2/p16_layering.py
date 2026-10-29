"""p16: the imports of the milestone-2 modules, listed by an own AST walk, and the layering test's
reaction to a planted violation in a scratch copy (claim 16).
Usage: python p16_layering.py <scratch repo copy> <python>
"""
import ast
import hashlib
import subprocess
import sys
from pathlib import Path

repo, py = Path(sys.argv[1]), sys.argv[2]
NEW = ["measures/black.py", "measures/forward.py", "measures/chain.py", "measures/termstructure.py",
       "measures/tables.py", "measures/event_iv.py", "measures/report.py", "export/iv_view.py", "export/funnel.py"]
for rel in NEW:
    tree = ast.parse((repo / "src/earnings_vol" / rel).read_text())
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            mods |= {f"{'.' * n.level}{n.module or ''}:{a.name}" for a in n.names}
    calls = sorted({n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                    and n.func.id in ("open", "exec", "eval", "getattr", "__import__")})
    print(f"{rel}: {sorted(mods)} banned-name calls: {calls}")


def run():
    r = subprocess.run([py, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_layering.py"], cwd=repo,
                       capture_output=True, text=True, env={"PYTHONPATH": str(repo / "src"), "PATH": "/usr/bin:/bin"})
    return r.returncode, [l for l in r.stdout.splitlines() if l.strip()][-1]


print("layering test, as is:", run())
for rel, plant in (("export/iv_view.py", "import pyarrow.parquet as _pq\n"),
                   ("measures/termstructure.py", "from earnings_vol.export import funnel as _f\n"),
                   ("measures/report.py", "def _w(df):\n    df.to_parquet('x')\n")):
    f = repo / "src/earnings_vol" / rel
    orig = f.read_text(); h = hashlib.sha256(orig.encode()).hexdigest()
    f.write_text(orig + plant)
    try:
        print(f"planted in {rel}: {plant.strip()!r} ->", run())
    finally:
        f.write_text(orig)
    assert hashlib.sha256(f.read_text().encode()).hexdigest() == h
print("restored (SHA-256 checked)")
