"""p14: mutation spot-check (claim 14), on a scratch copy of the repository only.

Five of the 47 mutants the milestone claims killed (C1-C5), and seven of this review's own (R1-R7)
that no test header lists. Each mutant is applied in place in the SCRATCH copy, the IV test modules
are run, and the file is restored and checked by SHA-256.
Usage: python p14_mutants.py <scratch repo copy> <python>
"""
import hashlib
import os
import subprocess
import sys
from pathlib import Path

repo, py = Path(sys.argv[1]), sys.argv[2]
assert "scratch" in str(repo) or "tmp" in str(repo), "refusing to mutate anything but a scratch copy"
TESTS = ["tests/test_iv_atom.py", "tests/test_termstructure.py", "tests/test_iv_pipeline.py",
         "tests/test_iv_worked_example.py", "tests/test_baseline_funnel.py", "tests/test_export_app_data.py"]
M = "src/earnings_vol/measures/"
MUTANTS = [
    ("C1 cm30 class split removed", M + "termstructure.py",
     "cls = [e for e in usable if e.spans == contains_event]", "cls = list(usable)"),
    ("C2 spans with > instead of >=", M + "tables.py",
     "sessions.as_of(exp) >= next_anchor[0]", "sessions.as_of(exp) > next_anchor[0]"),
    ("C3 baseline without the cm30 rule", "src/earnings_vol/export/funnel.py",
     'return (iv_daily["snapshot_status"] == "ok") & iv_daily["cm30_iv"].notna()',
     'return (iv_daily["snapshot_status"] == "ok")'),
    ("C4 quadratic unweighted", M + "chain.py",
     "1.0 / rel[sel])", "np.ones(sel.size))"),
    ("C5 front_fixed extrapolates", M + "event_iv.py",
     "termstructure.interpolate(ex, tau, 0)", "termstructure.interpolate(ex, tau, 99)"),
    ("R1 forward ties to the HIGHER strike", M + "forward.py",
     'chosen = np.argsort(gap, kind="mergesort")[:n_strikes]',
     "chosen = np.lexsort((-strike, gap))[:n_strikes]"),
    ("R2 T1* allows tau = 4 at day 0", M + "event_iv.py",
     ">= tau_min)\n    if not cands:", ">= tau_min - 1)\n    if not cands:"),
    ("R3 evar_m2 read at day -3", M + "event_iv.py",
     "m2_day = s.shift(ev.day0_session, -2)", "m2_day = s.shift(ev.day0_session, -3)"),
    ("R4 sigma_d fallback from the two LONGEST clean", M + "termstructure.py",
     "sigma_d2 = (clean[1].w - clean[0].w) / (clean[1].tau - clean[0].tau)",
     "sigma_d2 = (clean[-1].w - clean[-2].w) / (clean[-1].tau - clean[-2].tau)"),
    ("R5 quadratic window 3 sd instead of 2", M + "chain.py",
     "p.quadratic_max_sd * math.sqrt(w_ref)", "3.0 * math.sqrt(w_ref)"),
    ("R6 two_component drops E", M + "termstructure.py",
     "return s2 * h + event, \"two_component\", c, e", "return s2 * h, \"two_component\", c, e"),
    ("R7 quadratic w_ref = nearest strike always", M + "chain.py",
     "        w_ref = w0 if w0 > 0 else None", "        w_ref = None"),
]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


for name, rel, old, new in MUTANTS:
    f = repo / rel
    orig, h = f.read_text(), sha(f)
    if orig.count(old) != 1:
        print(f"{name}: PROBE_INVALID (anchor found {orig.count(old)} times)")
        continue
    f.write_text(orig.replace(old, new))
    try:
        r = subprocess.run([py, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *TESTS], cwd=repo,
                           capture_output=True, text=True, env={"PYTHONPATH": str(repo / "src"), "PATH": "/usr/bin:/bin", "HOME": os.environ["HOME"]})
    finally:
        f.write_text(orig)
    assert sha(f) == h, f"restore failed for {rel}"
    last = [ln for ln in r.stdout.splitlines() if ln.strip()][-1]
    failed = [ln for ln in r.stdout.splitlines() if ln.startswith("FAILED")]
    print(f"{name}: {'KILLED' if r.returncode else 'SURVIVED'} (rc={r.returncode}) {last}"
          + (f" | {failed[0][:110]}" if failed else ""))
print("all files restored (SHA-256 checked)")
