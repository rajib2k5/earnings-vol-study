"""d02: mutants of the fix round's WIRING (delta claims 2, 4, 5, 7), on a SCRATCH COPY of the
repository. The working tree is never edited. Each mutant replaces one exact string in one file,
runs the FULL test suite (pytest -q, no -x, so every failing test is listed), restores the file
from bytes held in memory and checks its SHA-256. A kill only by tests/test_notebooks_sync.py
(which compares notebook cells with src/) is reported separately as NOTEBOOK-ONLY: it says the
source text changed, not that any behaviour is pinned.
Run: python docs/validation/probes/m3-delta/d02_wiring_mutants.py <scratch_repo> <venv python>
"""
import hashlib
import subprocess
import sys
from pathlib import Path

REPO = Path(sys.argv[1])
PY = sys.argv[2]
RES, RUN, G1, WIN = ("src/earnings_vol/stats/results.py", "src/earnings_vol/stats/run.py",
                     "src/earnings_vol/stats/g1.py", "src/earnings_vol/panel/window.py")
MUTANTS = [
    ("W1 event_test_rows never withholds (claim 5)", RES,
     "out.append(withhold(new) if role == \"robustness\" and (h, name) in mis_sized else new)", "out.append(new)"),
    ("W2 run_results passes no mis-sized rows (claim 5)", RUN,
     "mis_sized = results.oversized(report, float(st[\"alpha\"]))", "mis_sized = {}"),
    ("W3 run_results drops the season-cut row (claim 7)", RUN,
     "rows += results.season_cut_rows(f, st, rows, family, common)", "rows += []"),
    ("W4 H4 calibrated on the cm30 calibration again (claim 2)", RUN,
     "designs_sd = dict(designs, calibrated=dict(cal_sd[\"params\"]))", "designs_sd = dict(designs)"),
    ("W5 sigma_d design uses the cm30 usable mask (claim 2)", RUN,
     "des_sd = design(np.isfinite(f.sigma_d[union]))", "des_sd = design(f.usable[union])"),
    ("W6 sigma_d calibration from the cm30 series and CRUSH (claim 2)", RUN,
     "cal_sd = calibrate_on(f, sets_f[\"H4\"], \"dsigma_d\", st)", "cal_sd = calibrate_on(f, sets_f[\"H4\"], \"crush\", st)"),
    ("W7 replicate evaluates H4 on the FIRST (cm30) series (claim 2)", G1,
     "out.update(evaluate(d2, x2, m2, sets2, alpha, st, robust))", "out.update(evaluate(d, x, m, sets2, alpha, st, robust))"),
    ("W8 sig0 calibration ignored by the run: stress scale in the calibrated design (claim 1)", RUN,
     "designs = {\"calibrated\": dict(cal[\"params\"])}", "designs = {\"calibrated\": dict(cal[\"params\"], sig0=g1.SIG0)}"),
    ("W9 beta pool back to every clean change (claim 4)", WIN,
     "betas = abnormal.beta_by_security(sec, p.session, dX, dM, clean & base_ok[:, None])",
     "betas = abnormal.beta_by_security(sec, p.session, dX, dM, clean)"),
]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


killed = 0
for name, rel, old, new in MUTANTS:
    f = REPO / rel
    orig = f.read_bytes()
    h0 = sha(f)
    text = orig.decode()
    if text.count(old) != 1:
        print(f"{name}: PROBE_INVALID (anchor found {text.count(old)} times)", flush=True)
        continue
    f.write_text(text.replace(old, new))
    try:
        r = subprocess.run([PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-m", "not dolt"], cwd=REPO,
                           env={"PYTHONPATH": str(REPO / "src"), "PATH": "/usr/bin:/bin", "HOME": str(Path.home())},
                           capture_output=True, text=True, timeout=1800)
        last = [ln for ln in r.stdout.splitlines() if ln.strip()][-1] if r.stdout.strip() else r.stderr[-200:]
        failed = [ln.split(" ")[1] for ln in r.stdout.splitlines() if ln.startswith("FAILED")]
    finally:
        f.write_bytes(orig)
    ok = sha(f) == h0
    real = [t for t in failed if not t.startswith("tests/test_notebooks_sync.py")]
    status = "KILLED" if real else ("NOTEBOOK-ONLY" if failed else ("SURVIVED" if r.returncode == 0 else f"rc={r.returncode}"))
    killed += bool(real)
    print(f"{name}: {status} {failed} | {last[:90]} | restored sha256 ok={ok}", flush=True)
print(f"SUMMARY killed by a behavioural test {killed} of {len(MUTANTS)}")
