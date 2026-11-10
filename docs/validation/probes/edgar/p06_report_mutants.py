# p06 — Hand mutants for the look-up pins and EDGAR checks added to tools/report_numbers.py in phase 2
# (tests/test_report_numbers.py, R25-R30). Run on a scratch copy of the files the tests read, so the shared
# working tree is never mutated. Each: apply, run the named tests, expect a failure, restore, compare SHA-256.
# Run: .venv/bin/python docs/validation/probes/edgar/p06_report_mutants.py <scratch folder>
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
W = Path(tempfile.mkdtemp(prefix="report-mutants-", dir=sys.argv[1]))
for d in ("tools", "data/derived", "app/public/data", "docs/report"):
    shutil.copytree(REPO / d, W / d, ignore=shutil.ignore_patterns("__pycache__", "node_modules"))
for f in ("tests/test_report_numbers.py", "research/prototypes/rhobar_crush.out.txt", "README.md", "docs/prfaq.md",
          "docs/milestones/05-report-and-polish.md"):
    (W / f).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO / f, W / f)

RN, TF = "tools/report_numbers.py", "tests/test_report_numbers.py"
KEY = f"{TF}::test_key_numbers_from_the_committed_data"
STAGE = f"{TF}::test_the_pinned_lookup_count_is_compared_with_a_local_stage_report"
CROSS = f"{TF}::test_disagreeing_or_contradicting_data_fail_the_check"
MUT = [
    ("R25", 'put(f"lookups.{src}", fint(d["timing_source"].get(src, 0))',
     'put(f"lookups.{src}", fint(d["timing_source"].get("press_release", 0))', [KEY]),
    ("R26", 'd["timing_source"].get("press_release", 0) + d["timing_source"].get("edgar", 0), 0)',
     'fun["lookups"]["n_done"], 0)', [f"{CROSS}[look-ups by source]"]),
    ("R27", "if open_by != LOOKUPS_OPEN_BY_REASON:", "if False:", [STAGE]),
    ("R28", 'if ed["pending_gap_checks"] != LOOKUPS_GAP_QUESTIONED:', "if False:", [STAGE]),
    ("R29", '0 < iv["events"]["timing_status_counts"].get("not_checked", 0) < iv["events"]["n_events_five_names"] / 2),',
     "True),", [f"{CROSS}[VX timing]"]),
    ("R30", 'if not ed.get("on"):', "if False:", [STAGE]),
]
py = str(REPO / ".venv/bin/python")
base = subprocess.run([py, "-m", "pytest", "-q", "-p", "no:cacheprovider", TF], cwd=W, capture_output=True, text=True)
print("copy:", W.name)
print("baseline:", base.stdout.strip().splitlines()[-1])
for mid, old, new, tests in MUT:
    path = W / RN
    orig = path.read_bytes()
    h0 = hashlib.sha256(orig).hexdigest()
    s = orig.decode()
    assert s.count(old) == 1, (mid, s.count(old))
    path.write_text(s.replace(old, new))
    r = subprocess.run([py, "-m", "pytest", "-q", "-p", "no:cacheprovider", *tests], cwd=W, capture_output=True,
                       text=True)
    last = r.stdout.strip().splitlines()[-1]
    path.write_bytes(orig)
    h1 = hashlib.sha256(path.read_bytes()).hexdigest()
    print(f"{mid:4s} rc {r.returncode} {'KILLED' if r.returncode != 0 else 'SURVIVED'}  {last}  "
          f"restored sha256 {'ok' if h0 == h1 else 'MISMATCH'} {h1[:12]}")
for f in (RN, TF):
    same = hashlib.sha256((W / f).read_bytes()).hexdigest() == hashlib.sha256((REPO / f).read_bytes()).hexdigest()
    print(f"final {f} same as repo: {same}")
shutil.rmtree(W)
