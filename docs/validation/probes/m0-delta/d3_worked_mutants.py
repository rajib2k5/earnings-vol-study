"""Delta probe 3b: can the new identity check in research/prototypes/worked.py fail, and on which planted bugs?

Copies worked.py into a scratch directory (never edits the repository), applies one textual mutation per run, runs
the copy with the same interpreter, and records the exit code and the E it prints. worked.py ends its identity check
with `assert check(...)`, so a caught bug gives a non-zero exit code.

Mutants:
  m1  iv_reported drops the 252 (the bug the check is designed for)          -> must be caught
  m2  forward rule back to the median over ALL strikes (ledger N1's bug)     -> is it caught?
  m3  E_wform denominator (t2 + t1) instead of (t2 - t1)                      -> is it caught?
  m4  E computed with 12 sessions instead of 11 for the first expiry          -> is it caught?
  m5  discount factor on a 360-day year instead of 365                        -> is it caught?
  m6  ATM interpolation uses the lower strike's w only                         -> is it caught?
Run (scratch dir outside the repository is required):
  uv run --no-sync --frozen python docs/validation/probes/m0-delta/d3_worked_mutants.py <scratch_dir>
"""
import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / "research" / "prototypes" / "worked.py"
scratch = Path(sys.argv[1]).resolve()
assert ROOT not in scratch.parents and scratch != ROOT, "scratch dir must be outside the repository"
scratch.mkdir(parents=True, exist_ok=True)
orig = SRC.read_text()
sha0 = hashlib.sha256(orig.encode()).hexdigest()

MUTANTS = {
    "m0 (unmutated control)": [],
    "m1 iv_reported loses 252": [("np.sqrt(252 * w / tau)", "np.sqrt(w / tau)")],
    "m2 forward over all strikes (N1)": [("if rule == 'adr4' else both", "if rule == 'never' else both")],
    "m3 E_wform denominator t2 + t1": [("return (w1 * t2 - w2 * t1) / (t2 - t1)", "return (w1 * t2 - w2 * t1) / (t2 + t1)")],
    "m4 E with 12 sessions": [("E = E_wform(w1, w2, 11, 20)", "E = E_wform(w1, w2, 12, 20)")],
    "m5 DF on 360-day year": [("cal_days[(snap, exp)] / 365)", "cal_days[(snap, exp)] / 360)")],
    "m6 ATM w = lower strike only": [("w0 = valid[lo] + (0 - kl) / (kh - kl) * (valid[hi] - valid[lo])", "w0 = valid[lo]")],
}

rows = []
for name, subs in MUTANTS.items():
    text = orig
    for a, b in subs:
        assert text.count(a) == 1, f"{name}: pattern not unique: {a!r}"
        text = text.replace(a, b)
    f = scratch / "worked_mut.py"
    f.write_text(text)
    r = subprocess.run([sys.executable, str(f)], capture_output=True, text=True)
    m = re.search(r"E = (\d\.\d+)$", r.stdout, re.M)
    caught = r.returncode != 0
    rows.append((name, r.returncode, m.group(1) if m else "-", caught))
    print(f"{name:36s} rc={r.returncode}  E printed {m.group(1) if m else '-':>12s}  -> "
          f"{'CAUGHT by the identity check' if caught else 'NOT caught (script exits 0)'}")
assert hashlib.sha256(SRC.read_text().encode()).hexdigest() == sha0, "repository file changed!"
print("repository worked.py sha256 unchanged:", sha0[:12])
ok = rows[0][1] == 0 and rows[1][3]
print("RESULT: identity check can fail (m1 caught, control passes):", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
