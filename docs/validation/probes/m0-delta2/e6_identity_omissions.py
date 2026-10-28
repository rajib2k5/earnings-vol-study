"""Delta-2 probe e6 (claim 6): is ADR 0003's list (:303-321) of what the identity check misses complete?

ADR 0003 names four bugs the identity check in research/prototypes/worked.py does not catch (forward, session
count, ATM interpolation, discount factor) and concludes that those four "each need their own hand-worked oracle".
This probe plants bugs the list does NOT name in a scratch copy of worked.py and records the exit code (non-zero =
caught by the identity check's assert) and the E it prints:
  n1  Black-76 d1 uses +w instead of +0.5w (the IV inversion itself is wrong)
  n2  OTM side swapped: in-the-money options are inverted instead of out-of-the-money ones
  n3  the quote used for the inversion is the bid, not the mid
Controls: m0 (unmutated) must exit 0 with E = 0.00088284; m1 (iv_reported loses 252) must exit non-zero.

Run from the repository root, scratch dir OUTSIDE the repository:
  .venv/bin/python docs/validation/probes/m0-delta2/e6_identity_omissions.py <scratch_dir>
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
MUT = {
    "m0 control": [],
    "m1 iv_reported loses 252 (must be caught)": [("np.sqrt(252 * w / tau)", "np.sqrt(w / tau)")],
    "n1 Black-76 d1 +w instead of +0.5w": [("d1 = (np.log(F / K) + 0.5 * w) / s", "d1 = (np.log(F / K) + w) / s")],
    "n2 ITM side inverted instead of OTM": [("cp, bid, ask = ('P', pb, pa) if K < F else ('C', cb, ca)",
                                             "cp, bid, ask = ('C', cb, ca) if K < F else ('P', pb, pa)")],
    "n3 bid instead of mid in the inversion": [("        mid = (bid + ask) / 2\n        if not leg_ok",
                                                "        mid = bid\n        if not leg_ok")],
}
res = {}
for name, subs in MUT.items():
    text = orig
    for a, b in subs:
        assert text.count(a) == 1, (name, a)
        text = text.replace(a, b)
    f = scratch / "worked_mut.py"
    f.write_text(text)
    r = subprocess.run([sys.executable, str(f)], capture_output=True, text=True)
    m = re.search(r"E = (\d\.\d+)$", r.stdout, re.M)
    err = (r.stderr.strip().splitlines() or [""])[-1][:90]
    res[name] = r.returncode
    print(f"{name:42s} rc={r.returncode} E={m.group(1) if m else '-':>12s} "
          f"{'CAUGHT' if r.returncode else 'NOT caught (exit 0)'} {err if r.returncode else ''}")
assert hashlib.sha256(SRC.read_text().encode()).hexdigest() == sha0, "repository file changed!"
print("repository worked.py sha256 unchanged:", sha0[:12])
ok_controls = res["m0 control"] == 0 and res["m1 iv_reported loses 252 (must be caught)"] != 0
uncaught = [k for k in res if k.startswith("n") and res[k] == 0]
print("RESULT: controls OK:", ok_controls, "| unlisted bugs the identity check misses:", uncaught)
raise SystemExit(0 if ok_controls and not uncaught else 1)
