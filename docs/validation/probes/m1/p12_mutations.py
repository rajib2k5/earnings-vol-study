"""p12: mutation checks on a SCRATCH COPY of the tree (claims 12, 15, and the falsifiers of 2, 4, 5, 6, 7, 9).

  uv run python docs/validation/probes/m1/p12_mutations.py <scratch dir>

The working tree is never edited: tracked and untracked (not ignored) files (node_modules is ignored) are
copied to <scratch>/tree, each mutant is applied there, the whole Python suite runs against the
copy (PYTHONPATH=<copy>/src, tests/test_diagrams.py deselected: a parallel agent owns it), and
the file is restored from memory. SHA-256 of every working-tree source file is checked before
and after.
"""
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PY = REPO / ".venv" / "bin" / "python"

MUTANTS = [
    # (id, file, old, new, what it breaks)
    ("M1", "src/earnings_vol/events/calendar.py", 'if timing == "BMO":', 'if timing == "AMC":',
     "day0: BMO and AMC rows swapped"),
    ("M2", "src/earnings_vol/events/eps.py", "winner = min(claimants[eid], key=lambda p: (d - p).days)",
     "winner = max(claimants[eid], key=lambda p: (d - p).days)", "EPS tie: larger lag wins"),
    ("M3", "src/earnings_vol/export/funnel.py", "r.event_id, ez, orphans.get(sid, []),",
     "r.event_id, ez, [],", "orphan zones never reach the baseline"),
    ("M4", "src/earnings_vol/measures/snapshots.py", "ascending=[True, True, False, True]",
     "ascending=[True, True, True, True]", "keep the holiday copy instead of the session's own snapshot"),
    ("M5", "src/earnings_vol/ingest/edgar.py", "    ua = user_agent()\n    path = raw_dir",
     "    path = raw_dir", "EDGAR: User-Agent no longer checked first (NameError later, cache path unguarded)"),
    ("M6", "src/earnings_vol/events/timing.py", "if timing_raw is None and not weekend:",
     "if timing_raw is None:", "weekend NULL with no document -> ambiguous"),
    ("M7", "src/earnings_vol/ingest/dolt.py", "col = pc.cast(pc.cast(col, pa.string()), pa.float64())",
     "col = pc.cast(col, pa.float64())", "decimal cast direct (not correctly rounded)"),
    ("M8", "src/earnings_vol/events/eps.py", "if lo <= d <= hi", "if lo < d <= hi",
     "EPS window lower bound exclusive (lag 10 no longer matches)"),
    ("M9", "src/earnings_vol/events/timing.py", 'return "AMC" if hhmm >= close_time_et[release_date] else "BMO"',
     'return "AMC" if hhmm > close_time_et[release_date] else "BMO"', "a 16:00 release read as BMO"),
    ("M10", "src/earnings_vol/events/eps.py", "from earnings_vol.events import securities\n",
     "from earnings_vol.events import securities\n_LEAK = open(__file__).read()\nimport urllib.request as _u\n",
     "file I/O and a network import inside the pure events layer"),
    ("M11", "src/earnings_vol/export/funnel.py", 'obs = [status.get((s, m)) == "ok" and status.get((s, z)) == "ok"',
     'obs = [status.get((s, z)) == "ok"', "crush step checks day 0 only"),
    ("M12", "src/earnings_vol/events/timing.py", 'if sample != "none" and timing_raw is None:',
     'if timing_raw is None:', "invariant: NULL labels outside every sample also require a look-up"),
    ("M13", "src/earnings_vol/events/eps.py", "lag_min: int, lag_max: int,\n                  calendar_start: date) -> dict",
     "lag_min: int, lag_max: int,\n                  calendar_start: date) -> dict:\n    lag_min = lag_min - 20\n    return _mp(period_ends, events, lag_min=lag_min, lag_max=lag_max, calendar_start=calendar_start)\n\n\ndef _mp(period_ends, events, *, lag_min, lag_max, calendar_start) -> dict",
     "EPS window starts at -10 days instead of +10 (the fix p06 suggests): do tests pin the window?"),
]


def sha_all():
    out = {}
    for p in sorted((REPO / "src").rglob("*.py")):
        out[str(p.relative_to(REPO))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def main():
    scratch = Path(sys.argv[1]).resolve()
    tree = scratch / "tree"
    before = sha_all()
    if tree.exists():
        shutil.rmtree(tree)
    files = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=REPO, capture_output=True,
                           text=True, check=True).stdout.split("\n")
    for f in files:
        if not f or not (REPO / f).is_file():
            continue
        dst = tree / f
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / f, dst)
    env = {**os.environ, "PYTHONPATH": str(tree / "src")}
    chk = subprocess.run([str(PY), "-c", "import earnings_vol, sys; print(earnings_vol.__file__)"], cwd=tree, env=env,
                         capture_output=True, text=True)
    print("imports from:", chk.stdout.strip().replace(str(scratch), "$SCRATCH"))

    def run_suite():
        r = subprocess.run([str(PY), "-m", "pytest", "-q", "-p", "no:cacheprovider", "--deselect",
                            "tests/test_diagrams.py", "-W", "ignore"], cwd=tree, env=env, capture_output=True, text=True)
        failed = sorted({ln.split(" ")[1].split("::")[0] + "::" + ln.split("::")[1].split(" ")[0].split("[")[0]
                         for ln in r.stdout.splitlines() if ln.startswith(("FAILED", "ERROR"))})
        tail = [ln for ln in r.stdout.splitlines() if " passed" in ln or " failed" in ln or " error" in ln][-1:]
        return r.returncode, failed, tail

    rc, base_failed, tail = run_suite()
    print(f"baseline (unmutated copy): rc={rc} {tail} failed={base_failed}")
    for mid, rel, old, new, what in MUTANTS:
        path = tree / rel
        text = path.read_text()
        n = text.count(old)
        if n != 1:
            print(f"{mid}: SKIPPED, pattern found {n} times")
            continue
        path.write_text(text.replace(old, new))
        rc, failed, tail = run_suite()
        path.write_text(text)
        new_fail = sorted(set(failed) - set(base_failed))
        verdict = "KILLED" if new_fail else "SURVIVED"
        failed = new_fail
        print(f"{mid} [{what}]: {verdict} rc={rc} {tail}")
        for f in failed[:8]:
            print(f"      {f}")
    after = sha_all()
    print("working-tree src unchanged:", before == after)


if __name__ == "__main__":
    main()
